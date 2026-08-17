# -*- coding: utf-8 -*-
"""构建离线镜像（Phase 2）

1. 通过 MediaWiki parse API 拉取每篇文章的渲染 HTML（文章正文，不含广告/皮肤）
2. 重写内部链接 -> 本地页面；图片 -> 本地 images/（仅下载文章实际引用的图片）
3. 用绝地潜兵主题色包裹成离线可浏览的站点（去广告）
4. 生成 index.html 首页 + 搜索
"""

import hashlib
import html as html_lib
import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

WIKI_BASE = "https://helldivers.wiki.gg"
API = "https://helldivers.wiki.gg/api.php"
USER_AGENT = "HD2WikiLocalizer/1.0 (offline mirror builder)"

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "output_zh", "site")
PAGES_DIR = os.path.join(SITE, "pages")
IMAGES_DIR = os.path.join(SITE, "images")
CACHE_FILE = os.path.join(SITE, "mirror_cache.jsonl")
TITLES_JSON = os.path.join(SITE, "titles.json")
INDEX_HTML = os.path.join(SITE, "index.html")
THEME_CSS = os.path.join(SITE, "theme.css")

PAGE_WORKERS = 3
IMAGE_WORKERS = 10

_lock = threading.Lock()
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_session.headers["Accept-Language"] = "en-US"


def http_get(url: str, timeout: int = 60) -> bytes:
    resp = _session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def sanitize_filename(title: str, ext: str = ".html") -> str:
    t = title.strip().replace(" ", "_")
    t = re.sub(r"[<>:\"/\\|?*]", "_", t)
    t = re.sub(r"_+", "_", t)
    t = t.strip("._")
    if len(t) > 150:
        t = t[:150]
    return t + ext


def local_image_name(url: str) -> str:
    """根据 /images/ 路径生成本地文件名（URL 解码、去查询串）"""
    path = urllib.parse.urlparse(url).path
    base = os.path.basename(path)
    base = urllib.parse.unquote(base)
    base = re.sub(r"[<>:\"/\\|?*]", "_", base)
    return base or "img"


def page_template(title: str, body_html: str) -> str:
    esc = html_lib.escape(title)
    return f"""<!DOCTYPE html>
<html lang="zh-CN" class="theme-helldiver">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc} - 绝地潜兵2 离线百科</title>
<link rel="stylesheet" href="theme.css">
</head>
<body>
<header class="site-header">
  <a class="brand" href="index.html">🪖 绝地潜兵2 离线百科</a>
  <div class="header-right">
    <input id="q" class="search-input" type="search" placeholder="搜索页面…"
           onkeydown="if(event.key==='Enter'){{location='index.html?q='+encodeURIComponent(this.value);}}">
    <a class="btn" href="index.html">首页</a>
  </div>
</header>
<main class="content">
  <h1 class="page-title">{esc}</h1>
  <div class="mw-parser-output">{body_html}</div>
</main>
<footer class="site-footer">离线汉化版 · 内容版权归 The Helldivers Wiki / wiki.gg 贡献者所有 · 仅供个人学习交流</footer>
</body>
</html>
"""


REDIRECT_RE = re.compile(r"#REDIRECT\s*\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]", re.I)


def redirect_stub(title: str, target_file: str) -> str:
    esc = html_lib.escape(title)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta http-equiv="refresh" content="0;url={html_lib.escape(target_file)}">
<title>{esc} - 重定向</title></head>
<body><p><a href="{html_lib.escape(target_file)}">跳转到 {html_lib.escape(target_file)}</a></p></body>
</html>
"""


class MirrorBuilder:
    def __init__(self):
        self.db = sqlite3.connect(os.path.join(ROOT, "wiki_local.db"))
        self.db.row_factory = sqlite3.Row
        os.makedirs(PAGES_DIR, exist_ok=True)
        os.makedirs(IMAGES_DIR, exist_ok=True)
        self.title_file = {}       # title -> 页面文件名
        self.file_title = {}       # 文件名 -> title
        self.image_urls = {}       # url -> localname
        self.file_image_local = {} # "File:xxx" -> localname
        self.failures = []

    def build_title_map(self):
        rows = self.db.execute(
            "SELECT title, is_redirect FROM pages WHERE ns=0").fetchall()
        used = set()
        for r in rows:
            f = sanitize_filename(r["title"])
            if f in used:
                i = 2
                cand = sanitize_filename(f"{r['title']}_{i}")
                while cand in used:
                    i += 1
                    cand = sanitize_filename(f"{r['title']}_{i}")
                f = cand
            used.add(f)
            self.title_file[r["title"]] = f
            self.file_title[f] = r["title"]
        with open(TITLES_JSON, "w", encoding="utf-8") as fp:
            json.dump(self.title_file, fp, ensure_ascii=False, indent=0)

    # ---------- 页面 ----------
    def fetch_page_html(self, title: str):
        params = urllib.parse.urlencode({
            "action": "parse", "page": title, "prop": "text|images",
            "formatversion": 2, "format": "json",
        })
        url = f"{API}?{params}"
        for attempt in range(6):
            try:
                resp = _session.get(url, timeout=45)
                if resp.status_code == 429:
                    time.sleep(5 + attempt * 4)
                    continue
                resp.raise_for_status()
                raw = resp.content
                data = json.loads(raw.decode("utf-8"))
                if "error" in data:
                    return title, "", []
                parse = data.get("parse", {})
                return title, parse.get("text", ""), parse.get("images", [])
            except Exception as e:
                if attempt < 5:
                    time.sleep(2 + attempt)
                    continue
                return title, "", []

    def process_content_pages(self, limit: int = 0):
        rows = self.db.execute(
            "SELECT title FROM pages WHERE ns=0 AND is_redirect=0 ORDER BY title").fetchall()
        titles = [r["title"] for r in rows]
        if limit:
            titles = titles[:limit]
        cache = self.load_cache()
        todo = [t for t in titles if t not in cache]
        print(f"[Mirror] 共 {len(titles)} 个内容页，缓存命中 {len(titles) - len(todo)}，"
              f"待拉取 {len(todo)}", flush=True)
        for _t, (_h, urls) in cache.items():
            for u in urls:
                self.image_urls[u] = local_image_name(u)
        if not todo:
            self.finalize_pages(cache)
            return
        done = 0
        results = []
        with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as ex:
            futs = {ex.submit(self.fetch_page_html, t): t for t in todo}
            for fut in as_completed(futs):
                title, html, images = fut.result()
                done += 1
                if not html:
                    with _lock:
                        self.failures.append(title)
                    print(f"[Mirror] 失败({done}/{len(todo)}): {title}", flush=True)
                    continue
                # 记录 File: 标题 -> 本地图片名（由 images prop 提供）
                for im in images:
                    if im.startswith("File:"):
                        path = f"/images/{urllib.parse.quote(im[5:].replace(' ', '_'))}"
                        self.file_image_local[im] = local_image_name(path)
                rewritten, urls = self.rewrite_html(html, title)
                for u in urls:
                    self.image_urls[u] = local_image_name(u)
                cache[title] = (rewritten, urls)
                self.append_cache(title, rewritten, urls)
                if done % 50 == 0:
                    print(f"[Mirror] 页面 {done}/{len(todo)}", flush=True)
        print(f"[Mirror] 内容页拉取完成，失败 {len(self.failures)} 个", flush=True)
        if self.failures:
            with open(os.path.join(SITE, "failed_pages.txt"), "w", encoding="utf-8") as fp:
                fp.write("\n".join(self.failures))
        self.finalize_pages(cache)

    def load_cache(self) -> dict:
        cache = {}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as fp:
                for line in fp:
                    try:
                        item = json.loads(line)
                        cache[item["t"]] = (item["h"], item["u"])
                    except Exception:
                        continue
        return cache

    def append_cache(self, title: str, rewritten: str, urls: list):
        with open(CACHE_FILE, "a", encoding="utf-8") as fp:
            fp.write(json.dumps({"t": title, "h": rewritten, "u": urls},
                                ensure_ascii=False) + "\n")

    def finalize_pages(self, cache: dict):
        self.resolve_image_names()
        for title, (rewritten, urls) in cache.items():
            for i, u in enumerate(urls):
                name = self.image_urls[u]
                rewritten = rewritten.replace(f"__IMG_{i}__", f"images/{name}")
            self.save_page(title, rewritten)
        print(f"[Mirror] 已写出 {len(cache)} 个页面", flush=True)

    def resolve_image_names(self):
        """处理图片本地重名：不同 URL 同 basename 时加 hash 前缀"""
        used = {}
        final = {}
        for u, base in self.image_urls.items():
            name = base
            k = name.lower()
            if k in used and used[k] != u:
                h = hashlib.md5(u.encode("utf-8")).hexdigest()[:8]
                stem, ext = os.path.splitext(name)
                name = f"{h}_{stem}{ext}"
                k = name.lower()
            used[k] = u
            final[u] = name
        self.image_urls = final

    def save_page(self, title: str, html: str):
        fname = self.title_file.get(title)
        if not fname:
            return
        with open(os.path.join(PAGES_DIR, fname), "w", encoding="utf-8") as fp:
            fp.write(page_template(title, html))

    def rewrite_html(self, html: str, title: str) -> tuple:
        """返回 (改写后的 html, 图片绝对 URL 列表)"""
        urls = []

        def img_src(m):
            attrs = m.group(0)
            urls_local = []
            def repl_src(mm):
                u = mm.group(1)
                if u.startswith("/images/") or "helldivers.wiki.gg/images/" in u:
                    absu = u if u.startswith("http") else WIKI_BASE + u
                    urls_local.append(absu)
                    return f'src="__IMG_{len(urls) + len(urls_local) - 1}__"'
                return mm.group(0)
            attrs = re.sub(r'src="([^"]+)"', repl_src, attrs)
            def repl_srcset(mm):
                parts = []
                for cand in mm.group(1).split(","):
                    cand = cand.strip()
                    if not cand:
                        continue
                    u = cand.split(" ")[0]
                    if u.startswith("/images/") or "helldivers.wiki.gg/images/" in u:
                        absu = u if u.startswith("http") else WIKI_BASE + u
                        urls_local.append(absu)
                        parts.append(f'__IMG_{len(urls) + len(urls_local) - 1}__ ' + " ".join(cand.split(" ")[1:]))
                    else:
                        parts.append(cand)
                return f'srcset="{", ".join(parts)}"'
            attrs = re.sub(r'srcset="([^"]+)"', repl_srcset, attrs)
            urls.extend(urls_local)
            return attrs

        html = re.sub(r"<img\b[^>]*>", img_src, html, flags=re.I)

        def href_link(m):
            u = m.group(1)
            if u.startswith("/wiki/"):
                rest = urllib.parse.unquote(u[len("/wiki/"):])
                frag = ""
                if "#" in rest:
                    rest, frag = rest.split("#", 1)
                rest = rest.replace("_", " ")
                if rest in self.title_file:
                    return f'href="{self.title_file[rest]}{("#" + frag) if frag else ""}"'
                if rest.startswith("File:") and rest in self.file_image_local:
                    loc = self.file_image_local[rest]
                    return f'href="images/{loc}"'
                # 未知页面 -> 首页
                return 'href="index.html"'
            if u.startswith("/images/"):
                absu = WIKI_BASE + u
                urls.append(absu)
                return f'href="__IMG_{len(urls) - 1}__"'
            return m.group(0)

        html = re.sub(r'href="([^"]+)"', href_link, html)
        # 去掉外链跳转/广告脚本痕迹
        html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.I | re.S)
        html = re.sub(r"<iframe\b[^>]*>.*?</iframe>", "", html, flags=re.I | re.S)
        return html, urls

    # ---------- 重定向 ----------
    def process_redirects(self):
        rows = self.db.execute(
            "SELECT title, content FROM pages WHERE ns=0 AND is_redirect=1").fetchall()
        n = 0
        for r in rows:
            fname = self.title_file.get(r["title"])
            if not fname:
                continue
            m = REDIRECT_RE.search(r["content"] or "")
            target = m.group(1).strip().replace("_", " ") if m else ""
            tf = self.title_file.get(target, "index.html")
            with open(os.path.join(PAGES_DIR, fname), "w", encoding="utf-8") as fp:
                fp.write(redirect_stub(r["title"], tf))
            n += 1
        print(f"[Mirror] 重定向页 {n} 个", flush=True)

    # ---------- 图片 ----------
    def download_images(self):
        items = list(self.image_urls.items())
        print(f"[Mirror] 共 {len(items)} 个图片 URL，开始下载 ...", flush=True)
        ok = 0
        done = 0
        with ThreadPoolExecutor(max_workers=IMAGE_WORKERS) as ex:
            futs = []
            for u, name in items:
                futs.append(ex.submit(self._dl_one, u, name))
            for fut in as_completed(futs):
                done += 1
                if fut.result():
                    ok += 1
                if done % 200 == 0:
                    print(f"[Mirror] 图片 {done}/{len(items)}", flush=True)
        print(f"[Mirror] 图片下载完成 {ok}/{len(items)}", flush=True)

    def _dl_one(self, url: str, name: str) -> bool:
        path = os.path.join(IMAGES_DIR, name)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return True
        for attempt in range(3):
            try:
                raw = http_get(url, timeout=90)
                tmp = path + ".part"
                with open(tmp, "wb") as fp:
                    fp.write(raw)
                os.replace(tmp, path)
                return True
            except Exception:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        return False

    # ---------- 主题 ----------
    def write_theme(self):
        css = """/* 绝地潜兵2 离线百科主题（去广告、深色、仿 wiki.gg 风格） */
:root{--bg:#0d1117;--bg2:#161c26;--panel:#1c2430;--line:#2b3648;--text:#d7dee8;
--muted:#8b98ab;--accent:#f5a623;--accent2:#ffd27a;--link:#ffb84d;--danger:#e5534b;}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);
font:15px/1.65 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
.site-header{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:16px;
background:linear-gradient(180deg,#10151d,#0b0f15);border-bottom:2px solid var(--accent);
padding:10px 20px;flex-wrap:wrap}
.brand{font-weight:700;font-size:17px;color:var(--accent2);letter-spacing:.5px}
.header-right{margin-left:auto;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.search-input{min-width:260px;background:var(--panel);border:1px solid var(--line);
color:var(--text);border-radius:6px;padding:7px 12px;outline:none}
.search-input:focus{border-color:var(--accent)}
.btn{background:var(--panel);border:1px solid var(--line);color:var(--accent2);
border-radius:6px;padding:7px 14px}
.btn:hover{text-decoration:none;border-color:var(--accent)}
.content{max-width:1100px;margin:0 auto;padding:24px 20px 60px}
.page-title{border-bottom:2px solid var(--accent);padding-bottom:10px;font-size:26px}
.site-footer{text-align:center;color:var(--muted);font-size:12px;padding:18px}
/* 文章正文 */
.mw-parser-output img{max-width:100%;height:auto;border-radius:4px}
.mw-parser-output table{border-collapse:collapse;margin:10px 0}
.mw-parser-output table,.mw-parser-output th,.mw-parser-output td{border:1px solid var(--line)}
.mw-parser-output th,.mw-parser-output td{padding:6px 10px;background:var(--panel)}
.mw-parser-output th{background:#202a3a;color:var(--accent2)}
.mw-parser-output .infobox{float:right;margin:0 0 12px 16px;max-width:320px;background:var(--panel);
border:1px solid var(--line);border-radius:6px;padding:8px}
.mw-parser-output h1,.mw-parser-output h2,.mw-parser-output h3,.mw-parser-output h4{color:var(--accent2)}
.mw-parser-output .mw-headline{border-bottom:1px solid var(--line);padding-bottom:4px}
.mw-parser-output .hatnote,.mw-parser-output .dablink{color:var(--muted);font-size:13px}
.mw-parser-output .thumbinner,.mw-parser-output .gallerybox{background:var(--panel);
border:1px solid var(--line);border-radius:6px;padding:4px}
.mw-parser-output .thumbcaption,.mw-parser-output .gallerytext{color:var(--muted);font-size:12px}
.mw-parser-output blockquote{border-left:4px solid var(--accent);margin:8px 0;
padding:6px 14px;background:var(--panel);border-radius:4px}
.mw-parser-output code,.mw-parser-output pre{background:#0a0e14;border:1px solid var(--line);
border-radius:4px;padding:1px 5px}
/* 首页 */
.home-title{text-align:center;margin:36px 0 8px;font-size:30px;color:var(--accent2)}
.home-sub{text-align:center;color:var(--muted);margin-bottom:26px}
.home-search{display:block;margin:0 auto 26px;width:min(640px,90%);background:var(--panel);
border:1px solid var(--line);color:var(--text);border-radius:8px;padding:12px 16px;font-size:16px}
.page-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:6px 18px;
max-width:1200px;margin:0 auto;padding:0 16px}
.page-list a{color:var(--text);padding:3px 8px;border-radius:4px;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}
.page-list a:hover{background:var(--panel);color:var(--accent2);text-decoration:none}
.stats{text-align:center;color:var(--muted);font-size:13px;margin-bottom:16px}
"""
        with open(THEME_CSS, "w", encoding="utf-8") as fp:
            fp.write(css)

    # ---------- 首页 ----------
    def write_index(self):
        pages = []
        for title, fname in self.title_file.items():
            pages.append({"t": title, "f": fname})
        pages.sort(key=lambda x: x["t"].lower())
        data = json.dumps(pages, ensure_ascii=False)
        n = len(pages)
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>绝地潜兵2 离线百科（汉化版）</title>
<link rel="stylesheet" href="theme.css">
</head>
<body>
<header class="site-header">
  <span class="brand">🪖 绝地潜兵2 离线百科</span>
  <div class="header-right"><a class="btn" href="index.html">首页</a></div>
</header>
<main>
  <h1 class="home-title">绝地潜兵2 离线百科</h1>
  <p class="home-sub">本地汉化版 · 离线可查 · 共 {n} 个页面</p>
  <input id="q" class="home-search" type="search" placeholder="输入关键词搜索（如：强袭虫、民主空间站、SG-225）…" autofocus>
  <div class="stats" id="stats">加载中…</div>
  <div class="page-list" id="list"></div>
</main>
<footer class="site-footer">离线汉化版 · 内容版权归 The Helldivers Wiki / wiki.gg 贡献者所有 · 仅供个人学习交流</footer>
<script>
const PAGES = {data};
const list = document.getElementById('list');
const stats = document.getElementById('stats');
const q = document.getElementById('q');
function norm(s){{return s.toLowerCase();}}
function render(){{
  const kw = norm(q.value.trim());
  const items = kw ? PAGES.filter(p => norm(p.t).includes(kw) || norm(p.f).includes(kw)) : PAGES;
  stats.textContent = kw ? `找到 {n} 页中的 ${{items.length}} 页` : `共 {n} 个页面，输入关键词过滤`;
  list.innerHTML = items.map(p => `<a href="pages/${{p.f}}">${{p.t}}</a>`).join('');
}}
q.addEventListener('input', render);
const params = new URLSearchParams(location.search);
if (params.get('q')) {{ q.value = params.get('q'); }}
render();
</script>
</body>
</html>
"""
        with open(INDEX_HTML, "w", encoding="utf-8") as fp:
            fp.write(html)

    def run(self, limit: int = 0):
        self.build_title_map()
        self.process_content_pages(limit)
        self.process_redirects()
        self.write_theme()
        self.write_index()
        self.download_images()
        # 图片下载完后回写页面里的引用名（本地重名已统一），并统计
        print("[Mirror] 完成", flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    MirrorBuilder().run(args.limit)
