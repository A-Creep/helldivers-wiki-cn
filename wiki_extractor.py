#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helldivers 2 Wiki.gg 本地化工具（绝地潜兵2）
================================================
功能：
1. 通过 MediaWiki API 增量同步 Helldivers 2 页面到本地 SQLite
   （自动排除 Helldivers 1 / 一代分类 / 非英语子页）
2. 用 mwparserfromhell 从 wikitext 精确提取可翻译文本块，保留结构标记
3. 维护翻译记忆库（SQLite），增量更新时不丢已有翻译
4. 导出 untranslated.json 供人工翻译，导入 translated.json
5. 生成汉化版 wikitext（output_zh/*.wiki.txt）

用法：
    python wiki_extractor.py init                       # 初始化数据库
    python wiki_extractor.py sync                       # 增量同步 HD2 页面
    python wiki_extractor.py sync --force               # 强制全量同步
    python wiki_extractor.py extract                    # 提取未翻译文本
    python wiki_extractor.py extract --changed-only     # 只提取变更页面
    python wiki_extractor.py import translated.json     # 导入翻译
    python wiki_extractor.py build                      # 生成汉化 wikitext
    python wiki_extractor.py stats                      # 查看统计
    python wiki_extractor.py full                       # sync → extract → build
    python wiki_extractor.py update                     # 增量 sync → 提取新增 → build
    python wiki_extractor.py ask-kimi "问题" [--context 文件]  # 遇到难题自动问 Kimi 网页版
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

try:
    import mwparserfromhell
except ImportError:
    print("[FATAL] 缺少 mwparserfromhell，请先运行: pip install mwparserfromhell")
    sys.exit(1)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ===================== 默认配置 =====================
DEFAULT_CONFIG = {
    "wiki_api": "https://helldivers.wiki.gg/api.php",
    "wiki_base": "https://helldivers.wiki.gg",
    "db_path": "wiki_local.db",
    "output_dir": "output_zh",
    "untranslated_file": "untranslated.json",
    "images_dir": "output_zh/images",
    "request_delay": 0.6,
    "batch_size": 50,
    "user_agent": "HD2WikiLocalizer/1.0 (offline localization tool)",
    "glossary_file": "glossary.json",
}

CONFIG = dict(DEFAULT_CONFIG)


def load_config_file(path: Optional[str] = None) -> None:
    """配置文件优先级: 默认 < config.json < 命令行参数(由调用方覆盖)"""
    candidates = [path] if path else ["config.json"]
    for p in candidates:
        if p and os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                CONFIG.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
                print(f"[Config] 已加载 {p}")
            except Exception as e:
                print(f"[Config] 读取 {p} 失败: {e}")
            return


def load_glossary() -> Dict[str, str]:
    path = CONFIG.get("glossary_file", "glossary.json")
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


# ===================== 数据模型 =====================

@dataclass
class WikiPage:
    title: str
    pageid: int
    ns: int
    revid: int
    parentid: int
    timestamp: str
    content: str = ""
    is_redirect: bool = False


@dataclass
class TextBlock:
    """可翻译文本块"""
    block_id: str          # SHA256 前 16 位，翻译记忆库 key
    source_text: str       # 纯文本（不含 wikitext 标记）
    context: str           # heading / paragraph / template_param / table_cell / list_item / link_display / image_caption / formatting / blockquote / html
    page_title: str
    placeholder: str       # __TRANS_BLOCK_<hash>__


# ===================== MediaWiki API 客户端 =====================

class WikiClient:
    def __init__(self, api_url: str, delay: float = 0.5, user_agent: str = ""):
        self.api_url = api_url
        self.delay = delay
        self.user_agent = user_agent or CONFIG["user_agent"]
        self.failed_titles: List[str] = []

    def _request(self, params: Dict, max_retries: int = 5) -> Dict:
        params["format"] = "json"
        url = f"{self.api_url}?{urllib.parse.urlencode(params, safe=':/')}"
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept-Language": "en-US",
                        "Accept-Encoding": "gzip",
                    },
                )
                with urllib.request.urlopen(req, timeout=40) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                        raw = gzip.decompress(raw)
                    data = json.loads(raw.decode("utf-8"))
                if "error" in data:
                    print(f"[API Error] {url[:120]}... -> {data['error']}")
                    return {}
                return data
            except urllib.error.HTTPError as e:
                status = e.code
                if status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    backoff = 2 ** attempt
                    print(f"[Retry] HTTP {status}，{backoff}s 后重试 ({attempt + 1}/{max_retries})")
                    if status == 429:
                        self.delay = min(self.delay * 2, 5.0)
                    time.sleep(backoff)
                    continue
                print(f"[API Error] HTTP {status}: {url[:120]}...")
                return {}
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                if attempt < max_retries - 1:
                    backoff = 2 ** attempt
                    print(f"[Retry] 网络错误 {e}，{backoff}s 后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(backoff)
                    continue
                print(f"[API Error] 网络错误: {e}")
                return {}
        return {}

    def get_all_pages(self, namespace: int = 0, apcontinue: str = "") -> Tuple[List[Dict], str]:
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": namespace,
            "aplimit": "max",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        data = self._request(params)
        pages = data.get("query", {}).get("allpages", [])
        next_cursor = data.get("continue", {}).get("apcontinue", "")
        if data:
            time.sleep(self.delay)
        return pages, next_cursor

    def get_all_pages_full(self, namespace: int = 0) -> List[Dict]:
        pages, cursor = [], ""
        while True:
            batch, cursor = self.get_all_pages(namespace, cursor)
            pages.extend(batch)
            if not cursor:
                break
        return pages

    def get_latest_revids(self, titles: List[str]) -> Dict[str, int]:
        """批量查询最新 revid（不含内容，用于增量检测）"""
        result: Dict[str, int] = {}
        for i in range(0, len(titles), CONFIG["batch_size"]):
            batch = titles[i:i + CONFIG["batch_size"]]
            params = {
                "action": "query",
                "prop": "revisions",
                "titles": "|".join(batch),
                "rvprop": "ids",
            }
            data = self._request(params)
            for p in data.get("query", {}).get("pages", {}).values():
                if "missing" in p:
                    continue
                revs = p.get("revisions") or []
                if revs:
                    result[p["title"]] = revs[0].get("revid", 0)
            if data:
                time.sleep(self.delay)
        return result

    def get_revisions(self, titles: List[str]) -> List[Dict]:
        """批量拉取最新 revision 全文，自动处理 rvcontinue 分页"""
        all_pages: Dict[str, Dict] = {}
        for i in range(0, len(titles), CONFIG["batch_size"]):
            batch = titles[i:i + CONFIG["batch_size"]]
            cursor = ""
            while True:
                params = {
                    "action": "query",
                    "prop": "revisions",
                    "titles": "|".join(batch),
                    "rvslots": "main",
                    "rvprop": "ids|timestamp|content",
                }
                if cursor:
                    params["rvcontinue"] = cursor
                data = self._request(params)
                if not data:
                    self.failed_titles.extend(batch)
                    break
                for p in data.get("query", {}).get("pages", {}).values():
                    all_pages[p["title"]] = p
                cursor = data.get("continue", {}).get("rvcontinue", "")
                if not cursor:
                    break
                time.sleep(self.delay)
            if data:
                time.sleep(self.delay)
        return list(all_pages.values())

    def get_category_members(self, category: str, cmtype: str, cmnamespace: int,
                             cmcontinue: str = "") -> Tuple[List[Dict], str]:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": cmtype,
            "cmnamespace": cmnamespace,
            "cmlimit": "max",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        data = self._request(params)
        members = data.get("query", {}).get("categorymembers", [])
        next_cursor = data.get("continue", {}).get("cmcontinue", "")
        if data:
            time.sleep(self.delay)
        return members, next_cursor

    def get_all_categories(self, prefix: str = "") -> List[str]:
        """列出全部分类名（可选前缀过滤）"""
        cats: List[str] = []
        cursor = ""
        while True:
            params = {"action": "query", "list": "allcategories", "aclimit": "max"}
            if prefix:
                params["acprefix"] = prefix
            if cursor:
                params["accontinue"] = cursor
            data = self._request(params)
            cats.extend(c.get("*", "") for c in data.get("query", {}).get("allcategories", []))
            cursor = data.get("continue", {}).get("accontinue", "")
            if not cursor:
                break
            time.sleep(self.delay)
        return cats

    def get_parse_html(self, title: str) -> Tuple[str, List[str]]:
        """获取页面的渲染 HTML（Phase 2 镜像用），返回 (html, images)"""
        params = {
            "action": "parse",
            "page": title,
            "prop": "text|images",
            "formatversion": 2,
        }
        data = self._request(params)
        if not data:
            return "", []
        parse = data.get("parse", {})
        html = parse.get("text", "")
        images = parse.get("images", [])
        return html, images


# ===================== 数据库层 =====================

class TranslationDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            pageid INTEGER PRIMARY KEY,
            title TEXT UNIQUE NOT NULL,
            ns INTEGER DEFAULT 0,
            revid INTEGER,
            parentid INTEGER,
            timestamp TEXT,
            content TEXT,
            is_redirect INTEGER DEFAULT 0,
            last_sync TEXT DEFAULT (datetime('now')),
            last_extracted TEXT
        );
        CREATE TABLE IF NOT EXISTS translations (
            source_hash TEXT PRIMARY KEY,
            source_text TEXT NOT NULL,
            translated_text TEXT,
            context TEXT,
            page_title TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            detail TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS excluded_pages (
            title TEXT PRIMARY KEY,
            reason TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_trans_status ON translations(status);
        CREATE INDEX IF NOT EXISTS idx_trans_page ON translations(page_title);
        """)
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(pages)")]
        if "last_extracted" not in cols:
            self.conn.execute("ALTER TABLE pages ADD COLUMN last_extracted TEXT")
        self.conn.commit()

    def upsert_page(self, page: WikiPage):
        self.conn.execute("""
            INSERT INTO pages (pageid, title, ns, revid, parentid, timestamp, content, is_redirect, last_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(pageid) DO UPDATE SET
                title=excluded.title, ns=excluded.ns, revid=excluded.revid,
                parentid=excluded.parentid, timestamp=excluded.timestamp,
                content=excluded.content, is_redirect=excluded.is_redirect,
                last_sync=excluded.last_sync
        """, (page.pageid, page.title, page.ns, page.revid, page.parentid,
              page.timestamp, page.content, int(page.is_redirect)))

    def get_page_by_title(self, title: str) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM pages WHERE title=?", (title,))
        return cur.fetchone()

    def get_page_revid(self, title: str) -> Optional[int]:
        row = self.get_page_by_title(title)
        return row["revid"] if row else None

    def get_all_pages(self) -> List[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM pages ORDER BY title")
        return cur.fetchall()

    def get_changed_pages(self, remote_revids: Dict[str, int]) -> List[str]:
        changed = []
        for title, revid in remote_revids.items():
            local = self.get_page_revid(title)
            if local != revid:
                changed.append(title)
        return changed

    def get_translation(self, source_hash: str) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM translations WHERE source_hash=?", (source_hash,))
        return cur.fetchone()

    def upsert_translation(self, block: TextBlock, translated: str = "", status: str = "pending"):
        """关键：ON CONFLICT 时只更新原文/上下文/来源页，绝不覆盖已有翻译"""
        h = block.block_id
        self.conn.execute("""
            INSERT INTO translations (source_hash, source_text, translated_text, context, page_title, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_hash) DO UPDATE SET
                source_text=excluded.source_text, context=excluded.context,
                page_title=excluded.page_title, updated_at=datetime('now')
        """, (h, block.source_text, translated, block.context, block.page_title, status))

    def update_translation(self, source_hash: str, translated: str, status: str = "translated"):
        self.conn.execute("""
            UPDATE translations SET translated_text=?, status=?, updated_at=datetime('now')
            WHERE source_hash=?
        """, (translated, status, source_hash))

    def set_last_extracted(self, title: str):
        self.conn.execute(
            "UPDATE pages SET last_extracted=datetime('now') WHERE title=?", (title,))

    def commit(self):
        self.conn.commit()

    def get_stats(self) -> Dict:
        pages = self.conn.execute("SELECT COUNT(*) c FROM pages").fetchone()["c"]
        redirects = self.conn.execute(
            "SELECT COUNT(*) c FROM pages WHERE is_redirect=1").fetchone()["c"]
        blocks = self.conn.execute("SELECT COUNT(*) c FROM translations").fetchone()["c"]
        translated = self.conn.execute(
            "SELECT COUNT(*) c FROM translations WHERE status='translated'").fetchone()["c"]
        locked = self.conn.execute(
            "SELECT COUNT(*) c FROM translations WHERE status='locked'").fetchone()["c"]
        pending = self.conn.execute(
            "SELECT COUNT(*) c FROM translations WHERE status='pending' OR translated_text IS NULL").fetchone()["c"]
        last_sync = self.conn.execute(
            "SELECT MAX(last_sync) m FROM pages").fetchone()["m"]
        last_log = self.conn.execute(
            "SELECT detail FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
        return {
            "pages": pages, "redirects": redirects, "blocks": blocks,
            "translated": translated, "locked": locked, "pending": pending,
            "last_sync": last_sync, "last_log": last_log["detail"] if last_log else None,
        }

    def log(self, action: str, detail: str = ""):
        self.conn.execute("INSERT INTO sync_log (action, detail) VALUES (?, ?)", (action, detail))
        self.conn.commit()

    # ---- 排除页（一代 / 非英语） ----
    def get_excluded_titles(self) -> set:
        rows = self.conn.execute("SELECT title FROM excluded_pages").fetchall()
        return {r["title"] for r in rows}

    def add_excluded(self, title: str, reason: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO excluded_pages (title, reason) VALUES (?, ?)",
            (title, reason))
        self.conn.commit()

    def clear_excluded(self):
        self.conn.execute("DELETE FROM excluded_pages")
        self.conn.commit()


# ===================== Wikitext 解析器（核心） =====================

class ContentParser:
    """
    基于 mwparserfromhell 的精确文本提取器。
    - 只替换纯文本内容，保留 == / {{}} / | / [[]] / ''' 等所有标记
    - 占位符 __TRANS_BLOCK_<sha256前16位>__
    - 跳过纯数字、纯标点、模板名、参数名、CSS、HTML 属性、thumb 等关键字
    """

    PLACEHOLDER_PREFIX = "__TRANS_BLOCK_{hash}__"
    SKIP_TAGS = {"ref", "nowiki", "pre", "syntaxhighlight", "source", "math", "chem",
                 "gallery", "imagemap", "templatestyles", "poem", "timeline", "comment",
                 "noinclude", "includeonly", "onlyinclude"}
    SKIP_KEYWORDS = re.compile(
        r"^(thumb|frame|frameless|left|right|center|none|border|top|bottom|\d+px|"
        r"x\d+px|\d+pxx\d+px|upright|upright=\d+(\.\d+)?|link=.*|alt=.*|page=.*)$",
        re.IGNORECASE)
    PURE_SYMBOLS = re.compile(r"^[\d\s.,!?%\-—:;'\"()\[\]{}=+|*/\\<>~^&@#$]+$")
    MAGIC_WORDS = re.compile(r"^__[A-Z_]+__$")
    BARE_TAG = re.compile(r"^</?[a-z]+>$", re.IGNORECASE)
    IMAGE_FILE = re.compile(r"\.(?:png|jpe?g|gif|svg|webp|ico|ogg|mp3|wav|mp4|webm|tga|bmp)$", re.IGNORECASE)
    SINGLE_LETTER = re.compile(r"^[\"']?[A-Za-z][\"']?$")
    PLURAL_FRAG = re.compile(r"^s(?: |'|,|\.)")

    def __init__(self):
        self.blocks: List[TextBlock] = []

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _make_placeholder(self, h: str) -> str:
        return self.PLACEHOLDER_PREFIX.format(hash=h)

    def _make_block(self, text: str, context: str, page_title: str) -> Optional[str]:
        raw = text.strip()
        if len(raw) < 3:
            return None
        if self.PURE_SYMBOLS.fullmatch(raw):
            return None
        if self.SKIP_KEYWORDS.fullmatch(raw):
            return None
        if self.MAGIC_WORDS.fullmatch(raw):
            return None
        if self.BARE_TAG.fullmatch(raw):
            return None
        if self.IMAGE_FILE.search(raw):
            return None
        if self.SINGLE_LETTER.fullmatch(raw):
            return None
        if self.PLURAL_FRAG.match(raw) and len(raw) < 40:
            return None
        if "__TRANS_BLOCK_" in raw:
            return None
        h = self._hash(raw)
        ph = self._make_placeholder(h)
        self.blocks.append(TextBlock(
            block_id=h, source_text=raw, context=context,
            page_title=page_title, placeholder=ph))
        return ph

    def parse(self, wikitext: str, page_title: str) -> str:
        """解析 wikitext，返回带占位符的版本，self.blocks 记录所有文本块"""
        self.blocks = []
        try:
            code = mwparserfromhell.parse(wikitext)
            self._process_wikicode(code, page_title)
            return str(code)
        except Exception as e:
            print(f"[Parser Warn] {page_title}: {e}")
            return wikitext

    def _process_wikicode(self, wc, page_title: str, context: str = "paragraph"):
        pending_override = None
        for node in list(wc.nodes):
            if pending_override is not None:
                if type(node).__name__ == "Text":
                    self._process_text_node(node, page_title, context, pending_override)
                    pending_override = None
                    continue
            self._process_node(node, wc, page_title, context)
            if type(node).__name__ == "Tag" and (node.tag or "").lower() == "li":
                pending_override = "list_item"

    def _process_node(self, node, parent, page_title: str, context: str):
        name = type(node).__name__
        if name == "Text":
            self._process_text_node(node, page_title, context)
        elif name == "Heading":
            self._process_wikicode(node.title, page_title, "heading")
        elif name == "Template":
            for param in node.params:
                self._process_wikicode(param.value, page_title, "template_param")
        elif name == "Wikilink":
            self._process_wikilink(node, page_title)
        elif name == "ExternalLink":
            self._process_external_link(node, page_title)
        elif name == "Tag":
            tag = (node.tag or "").lower()
            if tag in ("b", "i"):
                tag_context = "formatting"
            elif tag == "li":
                tag_context = "list_item"
            elif tag in ("table", "tr", "td", "th", "caption"):
                tag_context = "table_cell"
            elif tag in self.SKIP_TAGS:
                tag_context = None
            else:
                tag_context = "html"
            if tag_context is not None and node.contents is not None:
                self._process_wikicode(node.contents, page_title, tag_context)
        # Comment / Argument 等节点直接跳过

    def _process_wikilink(self, node, page_title: str):
        title = str(node.title or "")
        lower = title.lower()
        if lower.startswith(("file:", "image:")):
            # 图片链接：只处理最后一个 caption 段，跳过 thumb/尺寸等关键字
            if node.text is None:
                return
            parts = str(node.text).split("|")
            if parts and not self.SKIP_KEYWORDS.fullmatch(parts[-1].strip()):
                parts[-1] = self._process_segment(parts[-1], "image_caption", page_title)
            try:
                node.text = "|".join(parts)
            except Exception:
                pass
        else:
            # 普通链接：只处理显示文本（保留目标）
            if node.text is None:
                return
            self._process_wikicode(node.text, page_title, "link_display")

    def _process_external_link(self, node, page_title: str):
        title = getattr(node, "title", None)
        if title is None or str(title).strip() in ("", "None"):
            return
        # mwparserfromhell 0.7.x: ExternalLink.title 是纯字符串
        processed = self._process_segment(str(title), "link_display", page_title)
        try:
            node.title = processed
        except Exception:
            pass

    def _process_text_node(self, node, page_title: str, context: str, override: Optional[str] = None):
        lines = str(node.value).split("\n")
        processed = []
        cur_override = override
        for line in lines:
            line_context = cur_override if (cur_override and line.strip()) else context
            processed.append(self._process_line(line, page_title, line_context))
            if not line.strip():
                cur_override = None
        node.value = "\n".join(processed)

    def _process_line(self, line: str, page_title: str, context: str) -> str:
        stripped = line.strip()
        if not stripped:
            return line
        if stripped.startswith("|") or stripped.startswith("!"):
            return self._process_table_line(line, page_title)
        m = re.match(r"^([*#;:]+)(.*)$", line)
        if m:
            markers, content = m.group(1), m.group(2)
            return markers + self._process_segment(content, "list_item", page_title)
        return self._process_segment(line, context, page_title)

    def _process_segment(self, segment: str, context: str, page_title: str) -> str:
        if not segment or not segment.strip():
            return segment
        # 剥掉粗体/斜体引号，保留在原文中
        m_lead = re.match(r"^('{2,5})", segment)
        m_trail = re.search(r"('{2,5})$", segment)
        q_lead = m_lead.group(1) if m_lead else ""
        q_trail = m_trail.group(1) if m_trail else ""
        core = segment[len(q_lead):]
        if q_trail:
            core = core[:len(core) - len(q_trail)]
        # 段内可能有行内粗体/斜体标记：按引号切分，标记原位保留，只提取纯文本片段
        fmt_context = "formatting" if re.search(r"'{2,5}", core) else context
        parts = re.split(r"('{2,5})", core)
        out = []
        for part in parts:
            if not part:
                continue
            if re.fullmatch(r"'{2,5}", part):
                out.append(part)
                continue
            pre = part[:len(part) - len(part.lstrip())]
            post = part[len(part.rstrip()):]
            body = part.strip()
            ph = self._make_block(body, fmt_context, page_title)
            if ph is None:
                out.append(part)
            else:
                out.append(pre + ph + post)
        return q_lead + "".join(out) + q_trail

    def _process_table_line(self, line: str, page_title: str) -> str:
        stripped = line.strip()
        if stripped.startswith("|-") or stripped.startswith("|}"):
            return line
        m = re.match(r"^(\s*)(\||!)(\+?)(.*)$", line)
        if not m:
            return line
        pre, cellchar, plus, rest = m.group(1), m.group(2), m.group(3), m.group(4)
        if plus == "+":
            return pre + cellchar + "+" + self._process_segment(rest, "table_cell", page_title)
        sep = "||" if cellchar == "|" else "!!"
        cells = rest.split(sep)
        out = [self._process_table_cell(c, page_title) for c in cells]
        return pre + cellchar + sep.join(out)

    def _process_table_cell(self, cell: str, page_title: str) -> str:
        if not cell.strip():
            return cell
        m = re.match(r"^([^|]*\|)(.*)$", cell)
        if m:
            attrs, content = m.group(1), m.group(2)
            return attrs + self._process_segment(content, "table_cell", page_title)
        return self._process_segment(cell, "table_cell", page_title)

    def restore(self, templated_text: str, translations: Dict[str, str]) -> str:
        """把占位符替换为翻译文本（translations: hash -> 文本）"""
        def repl(m: re.Match) -> str:
            h = m.group(1)
            return translations.get(h, m.group(0))
        return re.sub(r"__TRANS_BLOCK_([0-9a-f]{16})__", repl, templated_text)


# ===================== HD1 / 非英语排除 =====================

LANG_SUFFIXES = ("/ru", "/zh", "/zh-hans", "/zh-hant", "/pt-br", "/de", "/es", "/fr",
                 "/it", "/ja", "/ko", "/pl", "/uk", "/tr", "/cs", "/da", "/fi", "/hu",
                 "/nl", "/no", "/sv", "/ar", "/he", "/hi", "/id", "/ms", "/th", "/vi")


def title_is_lang_subpage(title: str) -> bool:
    return title.lower().endswith(LANG_SUFFIXES)


def title_is_hd1_heuristic(title: str) -> bool:
    t = title.strip()
    if t.lower().startswith("helldivers 1"):
        return True
    if " (helldivers 1)" in t.lower():
        return True
    return False


class ExclusionBuilder:
    """收集 Helldivers 1 分类树下的全部页面，写入 excluded_pages 表"""

    HD1_ROOTS = ["Category:Helldivers 1", "Category:Community (Helldivers 1)"]

    def __init__(self, client: WikiClient, db: TranslationDB):
        self.client = client
        self.db = db

    def build(self) -> Tuple[int, int]:
        self.db.clear_excluded()
        roots = self._find_roots()
        excluded_pages: Dict[str, str] = {}
        visited: set = set()
        queue: List[str] = list(roots)
        while queue:
            cat = queue.pop(0)
            if cat in visited:
                continue
            visited.add(cat)
            cursor = ""
            while True:
                members, cursor = self.client.get_category_members(
                    cat, "page|subcat", "0|14", cursor)
                for m in members:
                    if m.get("ns") == 0:
                        excluded_pages[m["title"]] = f"HD1 category: {cat}"
                    elif m.get("ns") == 14:
                        sub = m.get("title", "")
                        if sub not in visited:
                            queue.append(sub)
                if not cursor:
                    break
            print(f"[Exclude] 已扫描 {cat}（累计排除页 {len(excluded_pages)}）")
        for title, reason in excluded_pages.items():
            self.db.add_excluded(title, reason)
        self.db.commit()
        self.db.log("exclude", f"HD1 categories scanned: {len(visited)}, pages excluded: {len(excluded_pages)}")
        return len(visited), len(excluded_pages)

    def _find_roots(self) -> List[str]:
        roots = list(self.HD1_ROOTS)
        prefix_cats = self.client.get_all_categories(prefix="Helldivers 1")
        for c in prefix_cats:
            roots.append(f"Category:{c}")
        return list(dict.fromkeys(roots))


def title_should_exclude(title: str, db_excluded: set) -> bool:
    if title in db_excluded:
        return True
    if title_is_hd1_heuristic(title):
        return True
    if title_is_lang_subpage(title):
        return True
    return False


# ===================== 同步引擎 =====================

class SyncEngine:
    def __init__(self, client: WikiClient, db: TranslationDB):
        self.client = client
        self.db = db

    def sync_all(self, namespace: int = 0, force: bool = False):
        print(f"[Sync] 获取远程页面列表 namespace={namespace} ...")
        remote = self.client.get_all_pages_full(namespace)
        print(f"[Sync] 远程共 {len(remote)} 个页面")

        db_excluded = self.db.get_excluded_titles()
        filtered = [p for p in remote
                    if not title_should_exclude(p["title"], db_excluded)]
        print(f"[Sync] 排除一代/非英语后剩余 {len(filtered)} 个页面")

        titles = [p["title"] for p in filtered]
        if force:
            changed = titles
            print(f"[Sync] --force：全部 {len(changed)} 个页面视为变更")
        else:
            print(f"[Sync] 检测最新 revid ...")
            revids = self.client.get_latest_revids(titles)
            changed = self.db.get_changed_pages(revids)
            print(f"[Sync] 发现 {len(changed)} 个新增/变更页面")

        if not changed:
            self.db.log("sync", f"no changes, {len(titles)} pages checked")
            print("[Sync] 无需更新")
            return

        self.client.failed_titles = []
        for i in range(0, len(changed), CONFIG["batch_size"]):
            batch = changed[i:i + CONFIG["batch_size"]]
            pages_data = self.client.get_revisions(batch)
            for p in pages_data:
                revs = p.get("revisions") or []
                if not revs:
                    continue
                rev = revs[0]
                content = ""
                slots = rev.get("slots") or {}
                main = slots.get("main") or {}
                content = main.get("*", "")
                page = WikiPage(
                    title=p.get("title", ""), pageid=p.get("pageid", 0),
                    ns=p.get("ns", 0), revid=rev.get("revid", 0),
                    parentid=rev.get("parentid", 0), timestamp=rev.get("timestamp", ""),
                    content=content, is_redirect="#REDIRECT" in content.upper()[:80]
                )
                if page.title:
                    self.db.upsert_page(page)
            self.db.commit()
            done = min(i + CONFIG["batch_size"], len(changed))
            print(f"[Sync] 已处理 {done}/{len(changed)}")

        if self.client.failed_titles:
            print(f"[Sync] 以下 {len(self.client.failed_titles)} 个标题请求失败：")
            for t in self.client.failed_titles[:50]:
                print("  -", t)
        self.db.commit()
        self.db.log("sync", f"updated {len(changed)} pages (ns={namespace})")
        print(f"[Sync] 完成，共更新 {len(changed)} 个页面")


# ===================== 提取引擎 =====================

class ExtractEngine:
    def __init__(self, db: TranslationDB):
        self.db = db

    def extract_all(self, output_file: str, output_format: str = "json",
                    changed_only: bool = False):
        pages = self.db.get_all_pages()
        if changed_only:
            pages = [p for p in pages
                     if p["last_extracted"] is None or p["last_extracted"] < p["last_sync"]]

        glossary = load_glossary()
        glossary_lower = {k.lower(): v for k, v in glossary.items()}
        untranslated = []
        seen: set = set()
        total_blocks = 0
        processed_pages = 0

        def lookup_glossary(text: str) -> Optional[str]:
            if text in glossary:
                return glossary[text]
            return glossary_lower.get(text.lower())

        for row in pages:
            if row["is_redirect"] or not row["content"]:
                continue
            parser = ContentParser()
            parser.parse(row["content"], row["title"])
            for block in parser.blocks:
                total_blocks += 1
                existing = self.db.get_translation(block.block_id)
                if not existing:
                    g = lookup_glossary(block.source_text)
                    if g:
                        self.db.upsert_translation(block, g, "locked")
                        continue
                    self.db.upsert_translation(block)
                elif existing["status"] == "pending" and not existing["translated_text"]:
                    g = lookup_glossary(block.source_text)
                    if g:
                        self.db.update_translation(block.block_id, g, "locked")
                        continue
                else:
                    continue
                if block.block_id not in seen:
                    seen.add(block.block_id)
                    untranslated.append({
                        "hash": block.block_id, "source": block.source_text,
                        "context": block.context, "page": block.page_title,
                    })
            self.db.set_last_extracted(row["title"])
            processed_pages += 1
            if processed_pages % 20 == 0:
                self.db.commit()
            if processed_pages % 200 == 0:
                print(f"[Extract] 已处理 {processed_pages}/{len(pages)} 页，"
                      f"文本块 {total_blocks}，待译 {len(untranslated)}")

        self.db.commit()
        if output_format == "csv":
            with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
                import csv
                w = csv.writer(f)
                w.writerow(["hash", "source", "context", "page"])
                for item in untranslated:
                    w.writerow([item["hash"], item["source"], item["context"], item["page"]])
        else:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(untranslated, f, ensure_ascii=False, indent=2)

        print(f"[Extract] 处理页数 {processed_pages}，总文本块 {total_blocks}，"
              f"未翻译 {len(untranslated)}，已导出到 {output_file}")
        self.db.log("extract", f"pages={processed_pages} blocks={total_blocks} pending={len(untranslated)}")

    def import_translations(self, input_file: str):
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        for item in data:
            h = item.get("hash")
            trans = item.get("translated", "")
            status = item.get("status", "translated")
            if h and trans:
                self.db.update_translation(h, trans, status)
                count += 1
        self.db.commit()
        print(f"[Import] 已导入 {count} 条翻译")
        self.db.log("import", f"imported {count}")


# ===================== 构建器 =====================

class Builder:
    def __init__(self, db: TranslationDB, output_dir: str):
        self.db = db
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def build_page(self, page_row: sqlite3.Row) -> str:
        parser = ContentParser()
        templated = parser.parse(page_row["content"], page_row["title"])
        trans_map: Dict[str, str] = {}
        for block in parser.blocks:
            row = self.db.get_translation(block.block_id)
            if row and row["translated_text"]:
                trans_map[block.block_id] = row["translated_text"]
            else:
                trans_map[block.block_id] = block.source_text
        return parser.restore(templated, trans_map)

    def build_all(self):
        pages = self.db.get_all_pages()
        built, skipped = 0, 0
        for row in pages:
            if row["is_redirect"] or not row["content"]:
                skipped += 1
                continue
            zh_text = self.build_page(row)
            safe_title = row["title"].replace("/", "_").replace(":", "_")
            path = os.path.join(self.output_dir, f"{safe_title}.wiki.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(zh_text)
            built += 1
        print(f"[Builder] 已生成 {built} 个页面（跳过 {skipped} 个）到 {self.output_dir}")
        self.db.log("build", f"built={built} skipped={skipped}")


# ===================== Kimi 自动求助 =====================

KIMI_AGENT_DIR = r"G:\Codex项目\kimi-agent"


def ask_kimi_for_help(problem: str, snippet: str = None, context_file: str = None,
                      upload_files: List[str] = None, download_dir: str = None) -> str:
    """
    遇到搞不定的 wikitext / 解析问题时，自动向 Kimi 网页版提问。

    委托给全局共享模块 kimi_help.py（位于 G:\\Codex项目\\kimi-agent），
    未安装 Playwright 或未登录时给出明确提示，不影响工具本身。

    Args:
        problem: 问题描述
        snippet: 相关 wikitext/代码片段（可选）
        context_file: 上下文文件路径（可选，优先级高于 snippet）
        upload_files: 需要一起上传的文件路径列表（可选）
        download_dir: 下载 Kimi 返回的附件/产物的目录（可选）

    Returns:
        Kimi 的回答文本（失败时返回空字符串）
    """
    try:
        if KIMI_AGENT_DIR not in sys.path:
            sys.path.insert(0, KIMI_AGENT_DIR)
        from kimi_help import ask_kimi
    except ImportError:
        print(f"[Kimi] 未找到 kimi_help.py（预期位置: {KIMI_AGENT_DIR}\\kimi_help.py）")
        print("[Kimi] 请先安装依赖: pip install playwright && python -m playwright install chromium")
        return ""

    result = ask_kimi(
        problem,
        snippet=snippet,
        context_file=context_file,
        upload_files=upload_files,
        download_dir=download_dir,
    )
    if result.get("error"):
        print(f"[Kimi] 提问失败: {result['error']}")
        print(f"[Kimi] 请确认已登录: python \"{KIMI_AGENT_DIR}\\kimi_agent.py\" --login")
        return ""
    if result.get("downloads"):
        print(f"[Kimi] 已下载 {len(result['downloads'])} 个附件/产物")
    return result.get("answer", "")


# ===================== CLI 入口 =====================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Helldivers 2 Wiki 本地化工具（自动排除一代内容）")
    parser.add_argument("--config", default=None, help="配置文件路径（默认 config.json）")
    parser.add_argument("--db", default=None, help="SQLite 数据库路径")
    parser.add_argument("--output", default=None, help="构建输出目录")
    parser.add_argument("--delay", type=float, default=None, help="API 请求间隔秒数")
    parser.add_argument("--namespace", type=int, default=None, help="命名空间（默认 0）")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="初始化数据库")

    sync_p = sub.add_parser("sync", help="增量同步 HD2 页面")
    sync_p.add_argument("--force", action="store_true", help="强制全量同步")
    sync_p.add_argument("--refresh-excludes", action="store_true",
                        help="重新扫描一代分类并刷新排除列表")

    ext_p = sub.add_parser("extract", help="提取未翻译文本")
    ext_p.add_argument("--changed-only", action="store_true", help="只提取变更页面")
    ext_p.add_argument("--format", choices=["json", "csv"], default="json")

    imp_p = sub.add_parser("import", help="导入翻译结果 JSON")
    imp_p.add_argument("file", help="翻译结果 JSON 文件路径")

    sub.add_parser("build", help="生成汉化版 wikitext")
    sub.add_parser("stats", help="显示统计信息")
    sub.add_parser("full", help="sync → extract → build")
    sub.add_parser("update", help="增量 sync → 提取新增 → build")
    ask_p = sub.add_parser("ask-kimi", help="遇到问题自动向 Kimi 网页版提问")
    ask_p.add_argument("problem", help="问题描述")
    ask_p.add_argument("--snippet", help="相关 wikitext/代码片段（直接传文本）")
    ask_p.add_argument("--context", help="上下文文件路径（优先于 --snippet）")
    ask_p.add_argument("--upload", action="append", default=[],
                       help="上传文件（可重复使用，或用逗号分隔多个路径）")
    ask_p.add_argument("--download-dir", default=None,
                       help="下载 Kimi 返回的附件/产物到该目录")
    return parser


def apply_cli_overrides(args) -> None:
    if args.db:
        CONFIG["db_path"] = args.db
    if args.output:
        CONFIG["output_dir"] = args.output
    if args.delay is not None:
        CONFIG["request_delay"] = args.delay
    if args.namespace is not None:
        CONFIG["namespace"] = args.namespace


def main():
    parser = build_parser()
    args = parser.parse_args()
    load_config_file(args.config)
    apply_cli_overrides(args)
    namespace = CONFIG.get("namespace", 0)

    if not args.command:
        parser.print_help()
        return

    db = TranslationDB(CONFIG["db_path"])
    client = WikiClient(CONFIG["wiki_api"], delay=CONFIG["request_delay"])

    if args.command == "init":
        print(f"[Init] 数据库已初始化: {CONFIG['db_path']}")
        print("[Init] 建议下一步: python wiki_extractor.py sync --refresh-excludes")
        return

    if args.command == "sync":
        if args.refresh_excludes:
            print("[Sync] 重建一代内容排除列表 ...")
            n_cat, n_page = ExclusionBuilder(client, db).build()
            print(f"[Sync] 一代分类 {n_cat} 个，排除页面 {n_page} 个")
        SyncEngine(client, db).sync_all(namespace=namespace, force=args.force)

    elif args.command == "extract":
        ExtractEngine(db).extract_all(
            CONFIG["untranslated_file"],
            output_format=args.format,
            changed_only=args.changed_only)

    elif args.command == "import":
        ExtractEngine(db).import_translations(args.file)

    elif args.command == "build":
        Builder(db, CONFIG["output_dir"]).build_all()

    elif args.command == "stats":
        s = db.get_stats()
        print("===== 本地化统计 =====")
        print(f"页面总数      : {s['pages']}（其中重定向 {s['redirects']}）")
        print(f"文本块总数    : {s['blocks']}")
        print(f"已翻译        : {s['translated']}（锁定 {s['locked']}）")
        print(f"待翻译        : {s['pending']}")
        print(f"上次同步      : {s['last_sync']}")
        if s["last_log"]:
            print(f"上次操作      : {s['last_log']}")

    elif args.command == "full":
        print("\n[Full] Step 1/3: 同步远程页面 ...")
        SyncEngine(client, db).sync_all(namespace=namespace)
        print("\n[Full] Step 2/3: 提取未翻译文本 ...")
        ExtractEngine(db).extract_all(CONFIG["untranslated_file"])
        print("\n[Full] Step 3/3: 生成汉化文件 ...")
        Builder(db, CONFIG["output_dir"]).build_all()
        print(f"\n[Full] 全部完成！待翻译文件: {CONFIG['untranslated_file']}")

    elif args.command == "update":
        print("\n[Update] 1/3: 增量同步 ...")
        SyncEngine(client, db).sync_all(namespace=namespace)
        print("\n[Update] 2/3: 提取新增/变更文本 ...")
        ExtractEngine(db).extract_all(
            CONFIG["untranslated_file"], changed_only=True)
        print("\n[Update] 3/3: 重新生成汉化文件 ...")
        Builder(db, CONFIG["output_dir"]).build_all()
        print(f"\n[Update] 完成。新待译文本在 {CONFIG['untranslated_file']}")

    elif args.command == "ask-kimi":
        uploads = []
        for u in args.upload:
            uploads.extend(p.strip() for p in u.split(",") if p.strip())
        answer = ask_kimi_for_help(
            args.problem, args.snippet, args.context,
            upload_files=uploads or None, download_dir=args.download_dir)
        if answer:
            print("\n" + "=" * 60)
            print("Kimi 的回答:")
            print("=" * 60)
            print(answer)
            print("=" * 60)


if __name__ == "__main__":
    main()
