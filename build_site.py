# -*- coding: utf-8 -*-
"""统一改版：汉化渲染 + 原站主题 + 正确路径 + 分类首页 + 补丁合并

1. 确定子集页面（战斗实用 + 补丁 + 原站小类列表页）
2. 用翻译表生成汉化 wikitext -> parse 渲染中文 HTML（带断点缓存）
3. 重写链接/图片路径（../images/，应用 WebP 映射），应用原站主题
4. 标题中英映射，首页按原站分类导航，补丁页合并成更新日志
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
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_extractor import TranslationDB, Builder

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://helldivers.wiki.gg/api.php"
UA = "HD2WikiLocalizer/1.0 (zh offline builder)"
SITE = os.path.join(ROOT, "output_zh", "site_final")
PAGES_DIR = os.path.join(SITE, "pages")
IMAGES_SRC = os.path.join(ROOT, "output_zh", "site", "images")
IMAGES_DIR = os.path.join(SITE, "images")
CACHE_FILE = os.path.join(SITE, "zh_cache.jsonl")
CONV_MAP = json.load(open(os.path.join(ROOT, "output_zh", "site", "images_conv.json"),
                          encoding="utf-8")) if os.path.exists(
    os.path.join(ROOT, "output_zh", "site", "images_conv.json")) else {}
CONV_MAP.setdefault("1007px-Penta_City_Planetside_2.png",
                    "1007px-Penta_City_Planetside_2.webp")
CONV_MAP.setdefault("1000px-Terminids.webp.png",
                    "1000px-Terminids.webp.webp")
CONV_MAP.setdefault("512px-Tyrant_Hunter_Cape_Armory.png",
                    "Tyrant_Hunter_Cape_Armory.webp")

WORKERS = 4
_session = requests.Session()
_session.headers["User-Agent"] = UA
_lock = threading.Lock()
_build_lock = threading.Lock()

# 原站导航（大类 -> 小类）；Acquisitions 整体移除，Cosmetics/Planets 移除
NAV = [
    ("Equipment", "装备", [
        ("Weapons", "武器"), ("Stratagems", "战略配备"), ("Armor", "护甲"),
        ("Armor Passives", "护甲被动"), ("Boosters", "强化资源"),
    ]),
    ("Game Mechanics", "游戏机制", [
        ("Factions", "敌人"), ("Damage", "伤害"), ("Combat", "战斗"),
        ("Missions", "任务"), ("Difficulty", "难度"),
        ("Second Galactic War Mechanics", "银河战争机制"), ("Effects", "效果"),
        ("Environmental Hazards", "环境危害"), ("Status Effects", "状态效果"),
        ("Achievements", "成就"),
    ]),
    ("Locations", "地点", [
        ("Biomes", "生物群系"), ("Minor Places of Interest", "次要地点"),
    ]),
]


def load_lines(p):
    if not os.path.exists(p):
        return []
    return [l.strip() for l in open(p, encoding="utf-8") if l.strip()]


def build_keep_set():
    db = sqlite3.connect(os.path.join(ROOT, "wiki_local.db"))
    titles = [r[0] for r in db.execute(
        "SELECT title FROM pages WHERE ns=0 AND is_redirect=0")]
    keep = set(titles)

    # ---- 明确舍弃：叙事/背景/战史/彩蛋/表情/外观/社区/物件 ----
    drop_pat = re.compile(
        r"(major order|galactic war|battle log|/battles|news$|news/|history|timeline|"
        r"\blore\b|characters|people|personnel|ministry|federation|government|"
        r"propaganda|dissident|events$|event:|species|memorial|museum|festival|"
        r"liberty day|judgment|april fools|scavenger war|reckoning|"
        r"battle tracker|at ease|big stretch|big whoop|badge of order|"
        r"blazing samaritan|authoritarian light|agent of oblivion|agitator|"
        r"alcubierre|atmospheric interference|atmospheric monitoring|"
        r"automaton orbital superweapon|automaton remains|biome name|"
        r"center for|c\.o\.b|case of|cup of|liber-tea|library card|"
        r"handwritten|scribbled|welcome sign|captain's log|maintenance report|"
        r"payroll|vending|forklift|hand carts|cars\b|poster\b|graves\b|"
        r"corn farm|farm\b|greenhouse|solar farm|cargo container|"
        r"exploding barrels|flower|plant\b|shrub\b|mushroom|moor\b|boneyard|"
        r"burial|deforester|executioner's canopy|monument|wall of|glory|"
        r"tapestry|testament|diagram of|ode to|vision of|proof of|schema|"
        r"rightful occupier|conductor of|standard of|stars and|strength in|"
        r"thumb of|thundering|welcome to|you're next|per democrasum|"
        r"united in|harbinger of|order of the|pillars of|seal of|pride of|"
        r"protector of|reaper of|shield of|spirit of|starship|voyage|"
        r"memorial|salute|handshake|hug|high-five|squat|flex|clapping|"
        r"draw!|head tap|tip hat|bow|wave|pose|emote|pattern|camo|cosmetic|"
        r"flag of|banner|emblem|cloak of|veil of|mantle|regalia|finery|"
        r"garland|canopy|corporations|corporation|company|studios|"
        r"entertainment|community|mods|media|discord|sprite|sandbox|"
        r"scratchpad|fanon|disambiguation|placeholder|/wip|/old$|/2024$|/2025$|"
        r"cup of|case of)",
        re.I)
    # 行星/星系页：以这些词结尾的专名（保守名单）
    planet_re = re.compile(
        r"(sector|prime|secundus|iii\b|iv\b|v\b|vi\b|vii\b|viii\b|ix\b|xi\b|"
        r"xii\b|pass\b|bay\b|cove\b|harbor\b|port\b|rock\b|beach\b|vale\b|"
        r"ridge\b|creek\b|wells\b|venture\b)$", re.I)

    keep_all = set(titles)
    drop = set()
    for t in titles:
        if drop_pat.search(t):
            drop.add(t)
            continue
        if planet_re.search(t):
            drop.add(t)

    # 强制保留：敌人
    enemy_re = re.compile(
        r"(bile|charger|spewer|hunter|stalker|scavenger|warrior|brood|impaler|"
        r"shrieker|hive|hulk|strider|tank|trooper|raider|commissar|berserker|"
        r"devastator|overseer|harvester|watcher|voteless|wretch|crusher|gazer|"
        r"marauder|brawler|wraith|skitter|pouncer|termadon|fleshmob|"
        r"appropriators|mindless|annihilator|barrager|shredder|factory|"
        r"illuminate|cyborg|predator|rupture|spore|jet brigade|incineration|"
        r"alpha commander|nursing|assault raider|commando|enemy|boss|factions|"
        r"automaton|terminid|bug)",
        re.I)
    # 强制保留：武器/装备型号
    model_re = re.compile(
        r"^(\d+x\s|[A-Z][A-Z0-9/]*-\d|[A-Z][A-Z0-9/]*/[A-Z])", re.I)
    # 强制保留：任务/机制关键词
    keep_word_re = re.compile(
        r"(mission|objective|damage|combat|difficulty|effects|environmental|"
        r"status effect|achievement|biome|planet|weapon|stratagem|armor|booster|"
        r"passive|currency|store|level|warbond|superstore|cosmetic|equipment|"
        r"weak|recoil|reload|ammo|\bstat\b|\bstats\b|hellpod|reinforce|sample|supplies|"
        r"module|ship|super destroyer|troubleshoot|steam|linux|fps|config|"
        r"crash|error code|settings|guide|training manual|game version|"
        r"personal orders|galactic terminal|war bond|warbonds|extract|"
        r"evacuate|eradicate|defend|destroy|collect|recover|retrieve|launch|"
        r"sabotage|upload|distribute|intercept|purge|seize|clear|repel|"
        r"terminate|conduct|deploy|secure|rescue|neutralize|raze|restart|"
        r"enable|start|annex|suppress|halt|blitz|operation|campaign)",
        re.I)

    final = set()
    for t in titles:
        if t in drop and not (
                enemy_re.search(t) or model_re.match(t) or keep_word_re.search(t)):
            continue
        final.add(t)
    # 原站小类列表页
    for _cat, _cn, items in NAV:
        for en, _zh in items:
            final.add(en)
    final.add("Factions")
    return final


def sanitize_filename(title):
    t = title.strip().replace(" ", "_")
    t = re.sub(r"[<>:\"/\\|?*]", "_", t)
    t = re.sub(r"_+", "_", t).strip("._")
    return (t[:150] if len(t) > 150 else t) + ".html"


def build_title_map(keep):
    """en -> zh 标题映射"""
    mapping = {}
    try:
        g = json.load(open("glossary.json", encoding="utf-8"))
        for en, zh in g.items():
            if zh and isinstance(zh, str):
                mapping[en.strip()] = zh.strip()
    except Exception:
        pass
    try:
        for line in open(os.path.join(ROOT, "game_loc", "official_terms.txt"),
                         encoding="utf-8"):
            if "=>" in line:
                en, zh = line.split("=>", 1)
                mapping[en.strip()] = zh.strip()
    except Exception:
        pass
    db = sqlite3.connect(os.path.join(ROOT, "wiki_local.db"))
    for r in db.execute(
            "SELECT source_text, translated_text FROM translations "
            "WHERE context='heading' AND translated_text IS NOT NULL "
            "AND translated_text <> ''"):
        mapping.setdefault(r[0].strip(), r[1].strip())
    extra_title = {
        "Eradicate Terminid Swarm": "剿灭终结族虫群",
        "Evacuate Colonists": "撤离殖民者",
        "A/AC-8 Autocannon Sentry": "机炮哨戒炮",
        "Orbital Precision Strike": "轨道精准打击",
        "Eagle Airstrike": "飞鹰空袭",
        "P-4 Senator": "P-4参议员",
        "B-01 Tactical": "B-01战术",
        "FS-38 Eradicator": "FS-38根除者",
        "APW-1 Anti-Materiel Rifle": "APW-1反器材步枪",
        "StA-52 Assault Rifle": "StA-52突击步枪",
        "40-K Meltagun": "40-K熔体枪",
        "A/AC-8 Autocannon Sentry": "A/AC-8机炮哨戒炮",
        "FAF-14 Spear": "FAF-14飞矛",
        "MG-206 Heavy Machine Gun": "MG-206重型机枪",
        "MG-43 Machine Gun": "MG-43机枪",
        "AC-8 Autocannon": "AC-8机炮",
        "EAT-17 Expendable Anti-Tank": "EAT-17消耗性反坦克",
        "MGX-42 Bullet Storm": "MGX-42弹幕风暴",
        "MLS-4X Commando": "MLS-4X突击兵",
        "FAF-14 Spear": "FAF-14飞矛",
        "Support Weapons": "支援武器",
        "Weapons": "武器",
        "Stratagems": "战略配备",
        "Armor": "护甲",
    }
    mapping.update(extra_title)
    out = {}
    for t in keep:
        zh = mapping.get(t) or mapping.get(t.replace(" ", "_")) or ""
        out[t] = {"file": sanitize_filename(t), "zh": zh}
    return out


def render_zh(title: str, zh_wikitext: str) -> str:
    for attempt in range(6):
        try:
            r = _session.post(API, data={
                "action": "parse", "text": zh_wikitext, "title": title,
                "prop": "text", "formatversion": 2, "format": "json",
            }, timeout=60)
            if r.status_code == 429:
                time.sleep(5 + attempt * 4)
                continue
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                return ""
            return d["parse"]["text"]
        except Exception as e:
            if attempt < 5:
                time.sleep(2 + attempt)
                continue
            print(f"[render] 最终失败 {title}: {type(e).__name__} {str(e)[:200]}", flush=True)
            return ""
    return ""


class SiteBuilder:
    def __init__(self, keep, title_map):
        self.keep = keep
        self.title_map = title_map
        self.tm = TranslationDB(os.path.join(ROOT, "wiki_local.db"))
        self.builder = Builder(self.tm, os.path.join(ROOT, "output_zh"))
        self.db = sqlite3.connect(os.path.join(ROOT, "wiki_local.db"))
        self.db.row_factory = sqlite3.Row
        os.makedirs(PAGES_DIR, exist_ok=True)
        os.makedirs(IMAGES_DIR, exist_ok=True)
        self.cache = self.load_cache()

    # ---- 缓存 ----
    def load_cache(self):
        c = {}
        if os.path.exists(CACHE_FILE):
            for line in open(CACHE_FILE, encoding="utf-8"):
                try:
                    it = json.loads(line)
                    c[it["t"]] = it["h"]
                except Exception:
                    continue
        return c

    def append_cache(self, title, html):
        with open(CACHE_FILE, "a", encoding="utf-8") as fp:
            fp.write(json.dumps({"t": title, "h": html}, ensure_ascii=False) + "\n")

    # ---- 汉化渲染 ----
    def build_all(self):
        rows = self.db.execute(
            "SELECT * FROM pages WHERE ns=0 AND is_redirect=0").fetchall()
        todo = []
        for r in rows:
            if r["title"] in self.keep and r["title"] not in self.cache:
                todo.append(r)
        print(f"[Site] 需汉化渲染 {len(todo)} 页（缓存 {len(self.cache)}）", flush=True)
        done = 0

        def work(row):
            try:
                local_tm = TranslationDB(os.path.join(ROOT, "wiki_local.db"))
                local_builder = Builder(local_tm, os.path.join(ROOT, "output_zh"))
                zh = local_builder.build_page(row)
                local_tm.conn.close()
                html = render_zh(row["title"], zh)
                return row["title"], html
            except Exception as e:
                print(f"[work] {row['title']}: {type(e).__name__} {str(e)[:200]}", flush=True)
                return row["title"], ""

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(work, r) for r in todo]
            for fut in as_completed(futs):
                title, html = fut.result()
                done += 1
                if html:
                    self.cache[title] = html
                    self.append_cache(title, html)
                else:
                    print(f"[Site] 渲染失败: {title}", flush=True)
                if done % 25 == 0:
                    print(f"[Site] 渲染 {done}/{len(todo)}", flush=True)
        print(f"[Site] 汉化渲染完成 {len(self.cache)} 页", flush=True)

    # ---- HTML 重写 ----
    def rewrite_html(self, html, title, page_path=""):
        cur = os.path.dirname(page_path) if page_path else ""

        def rel(t):
            if not cur:
                return t
            return os.path.relpath(t, cur).replace("\\", "/")

        index_rel = rel("index.html")
        urls = []

        def local_img(u):
            path = urllib.parse.urlparse(u).path
            base = urllib.parse.unquote(os.path.basename(path))
            base = re.sub(r"[<>:\"/\\|?*]", "_", base)
            return CONV_MAP.get(base, base)

        def img_src(m):
            attrs = m.group(0)
            urls_local = []

            srcm = re.search(r'src="([^"]+)"', attrs)
            add_icon = False
            if srcm:
                u0 = srcm.group(1)
                base0 = urllib.parse.unquote(
                    os.path.basename(urllib.parse.urlparse(u0).path))
                if base0.lower().endswith(".svg") and re.search(
                        r"(?i)(damage|armor|penetrat|fire|reload|magazine|capacity|"
                        r"recoil|faction|difficulty|stratagem|medal|currency|reward|"
                        r"ballistic|explosive|electric|chemical|acid|gas|melee|"
                        r"stagger|shield|arc|icon|arrow)", base0):
                    add_icon = True
            if add_icon:
                if re.search(r'\bclass="', attrs):
                    attrs = re.sub(r'class="([^"]*)"',
                                   lambda mm: 'class="wiki-icon ' + mm.group(1) + '"',
                                   attrs, count=1)
                else:
                    attrs = attrs.replace("<img ", '<img class="wiki-icon" ', 1)

            def repl_src(mm):
                u = mm.group(1)
                if u.startswith("/images/") or "helldivers.wiki.gg/images/" in u:
                    absu = u if u.startswith("http") else "https://helldivers.wiki.gg" + u
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
                        absu = u if u.startswith("http") else "https://helldivers.wiki.gg" + u
                        urls_local.append(absu)
                        parts.append(f'__IMG_{len(urls) + len(urls_local) - 1}__ ' +
                                     " ".join(cand.split(" ")[1:]))
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
                if rest in self.title_map:
                    return f'href="{self.title_map[rest]["file"]}{("#" + frag) if frag else ""}"'
                return f'href="{index_rel}"'
            if u.startswith("/images/"):
                absu = "https://helldivers.wiki.gg" + u
                urls.append(absu)
                return f'href="__IMG_{len(urls) - 1}__"'
            return m.group(0)

        html = re.sub(r'href="([^"]+)"', href_link, html)
        html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.I | re.S)
        html = re.sub(r"<iframe\b[^>]*>.*?</iframe>", "", html, flags=re.I | re.S)
        html = re.sub(r"<video\b[^>]*>.*?</video>", "", html, flags=re.I | re.S)
        html = re.sub(r"<source\b[^>]*>", "", html, flags=re.I)
        html = re.sub(
            r"<(p|div|span|li)[^>]*>[\s\S]*?Weapon not found[\s\S]*?</\1>",
            "", html, flags=re.I)
        html = re.sub(
            r"<(p|div|span|li)[^>]*>[\s\S]*?No Passive found[\s\S]*?</\1>",
            "", html, flags=re.I)
        html = re.sub(r"Syntax Error\s*", "", html, flags=re.I)
        html = re.sub(r"(致命|庞大|小|中型|大型)\?", r"\1", html)
        html = re.sub(r"<sup>\s*\?\s*</sup>", "", html, flags=re.I)
        # infobox 金色标题栏显示英文词条名（页面 h1 已是中文，避免重复）
        html = re.sub(
            r'(<div class="druid-title">)[^<]*(</div>)',
            lambda m: m.group(1) + html_lib.escape(title) + m.group(2),
            html, count=1)
        # 删除空表格（只有表头、无数据单元格）
        def drop_empty_table(m):
            block = m.group(0)
            return "" if "<td" not in block else block
        html = re.sub(
            r"<table[^>]*>(?:(?!<table)[\s\S])*?</table>",
            drop_empty_table, html, flags=re.I)
        # 删除消歧义提示（This article is about / This 条款 is about ... For the ... see）
        html = re.sub(
            r"<(i|p|td|div)[^>]*>[\s\S]*?(?:This\s+条款\s+is\s+about|This\s+article\s+is\s+about)"
            r"[\s\S]*?</\1>", "", html, flags=re.I)
        html = re.sub(r'\bhref=(["\'])index\.html\1', f'href="{index_rel}"', html)
        for i, u in enumerate(urls):
            html = html.replace(f"__IMG_{i}__",
                                f"../images/{urllib.parse.quote(local_img(u))}")
        return html

    def page_template(self, title, body, page_path=""):
        cur = os.path.dirname(page_path) if page_path else ""

        def rel(t):
            if not cur:
                return t
            return os.path.relpath(t, cur).replace("\\", "/")

        css_href = rel("theme.css")
        index_href = rel("index.html")
        meta = self.title_map.get(title, {"zh": ""})
        zh = meta["zh"]
        display = zh or title
        esc = html_lib.escape(title)
        ed = html_lib.escape(display)
        return f"""<!DOCTYPE html>
<html lang="zh-CN" class="theme-helldiver view-dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{ed} - 绝地潜兵2 离线百科</title>
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<header class="site-header">
  <a class="brand" href="{index_href}">🪖 绝地潜兵2 离线百科</a>
  <div class="header-right">
    <input id="q" class="search-input" type="search" placeholder="搜索中英文词条…"
           onkeydown="if(event.key==='Enter'){{location='{index_href}?q='+encodeURIComponent(this.value);}}">
    <a class="btn" href="{rel('patch_notes.html')}">📜 更新日志</a>
    <a class="btn" href="{index_href}">首页</a>
  </div>
</header>
<main class="content">
  <h1 class="page-title">{ed}</h1>
  <div class="breadcrumb">{esc}</div>
  <div class="mw-parser-output">{body}</div>
</main>
<footer class="site-footer">离线汉化版 · 内容版权归 The Helldivers Wiki / wiki.gg 贡献者所有 · 仅供个人学习交流</footer>
</body>
</html>
"""

    def write_pages(self):
        n = 0
        for title, html in self.cache.items():
            if title not in self.keep:
                continue
            fname = self.title_map[title]["file"]
            rewritten = self.rewrite_html(html, title, page_path=f"pages/{fname}")
            with open(os.path.join(PAGES_DIR, fname), "w", encoding="utf-8") as fp:
                fp.write(self.page_template(title, rewritten, page_path=f"pages/{fname}"))
            n += 1
        print(f"[Site] 已写出 {n} 个页面", flush=True)

    # ---- 重定向 ----
    def write_redirects(self):
        rows = self.db.execute(
            "SELECT title, content FROM pages WHERE ns=0 AND is_redirect=1").fetchall()
        n = 0
        for r in rows:
            if r["title"] not in self.title_map:
                continue
            m = re.search(r"#REDIRECT\s*\[\[([^\]|#]+)", r["content"] or "", re.I)
            if not m:
                continue
            target = m.group(1).strip().replace("_", " ")
            if target not in self.title_map:
                continue
            fname = self.title_map[r["title"]]["file"]
            tf = self.title_map[target]["file"]
            with open(os.path.join(PAGES_DIR, fname), "w", encoding="utf-8") as fp:
                fp.write(f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="0;url={tf}">
<title>{html_lib.escape(r['title'])} - 重定向</title></head>
<body><p><a href="{tf}">跳转</a></p></body></html>""")
            n += 1
        print(f"[Site] 重定向 {n}", flush=True)

    # ---- 图片 ----
    def copy_images(self):
        refs = set()
        for f in os.listdir(PAGES_DIR):
            if not f.endswith(".html"):
                continue
            html = open(os.path.join(PAGES_DIR, f), encoding="utf-8").read()
            refs |= set(re.findall(r'(?:src|href)="\.\./images/([^"#?]+)', html))
            for m in re.finditer(r'srcset="([^"]+)"', html):
                for cand in m.group(1).split(","):
                    cand = cand.strip()
                    if cand.startswith("../images/"):
                        refs.add(cand.split()[0][len("../images/"):])
        import shutil
        copied = 0
        missing = []
        for name in sorted(refs):
            s = os.path.join(IMAGES_SRC, name)
            if os.path.exists(s):
                shutil.copy2(s, os.path.join(IMAGES_DIR, name))
                copied += 1
            else:
                missing.append(name)
        print(f"[Site] 图片 {copied} 张（缺失 {len(missing)}）", flush=True)
        if missing:
            open(os.path.join(SITE, "missing_images.txt"), "w", encoding="utf-8").write(
                "\n".join(missing[:500]))

    def patch_titles(self):
        pat = re.compile(r"^\d+\.\d+")
        out = [t for t in self.cache if t in self.keep and pat.match(t)]

        def key(t):
            try:
                return [int(x) for x in t.split(".")[:4]]
            except Exception:
                return [0]

        out.sort(key=key, reverse=True)
        return out

    def write_patch_notes(self):
        pts = self.patch_titles()
        if not pts:
            return
        groups = []
        for idx, t in enumerate(pts):
            body = self.rewrite_html(self.cache[t], t)
            body = body.replace("../images/", "images/")
            body = re.sub(
                r'href="(?!http|#|index\.html)([^"]+\.html)',
                r'href="pages/\1"', body)
            summary = re.sub(r"<[^>]+>", " ", body)
            summary = re.sub(r"\s+", " ", summary).strip()
            dm = re.search(r"(\d{4}-\d{2}-\d{2})", summary)
            summary = ("更新日期：" + dm.group(1)) if dm else "点击展开查看变更详情"
            open_cls = " patch-open" if idx == 0 else ""
            groups.append(
                f'<div class="patch-group{open_cls}"><div class="patch-head" onclick="'
                f'this.parentElement.classList.toggle(\'patch-open\')">'
                f'<span class="arrow">▶</span>{html_lib.escape(t)}'
                f'<span class="en" style="margin-left:8px;font-size:12px;color:#888">'
                f'{html_lib.escape(self.title_map[t]["zh"])}</span></div>'
                f'<div class="patch-summary">{html_lib.escape(summary)}</div>'
                f'<div class="patch-body">{body}</div></div>')
        body = "".join(groups)
        html = self.page_template("Patch Notes", f'<div id="patch-list">{body}</div>',
                                  page_path="patch_notes.html")
        html = html.replace("Patch Notes", "更新日志（补丁说明）")
        with open(os.path.join(SITE, "patch_notes.html"), "w", encoding="utf-8") as fp:
            fp.write(html)
        print(f"[Site] 更新日志 {len(pts)} 个版本", flush=True)

    def write_index(self):
        pat = re.compile(r"^\d+\.\d+")
        try:
            cats = json.load(open(os.path.join(ROOT, "page_cats.json"), encoding="utf-8"))
        except Exception:
            cats = {}
        label_map = {
            "enemy": "敌人", "weapon": "武器", "support weapon": "武器",
            "throwable": "武器", "attachment": "配件", "stratagem": "战略配备",
            "armor": "护甲", "armor passive": "护甲", "mission": "任务",
            "biome": "生物群系", "hazard": "环境", "poi": "地点",
            "structure": "地点", "game version": "补丁",
        }

        def cat_label(t):
            return label_map.get(cats.get(t, {}).get("type", ""), "其他")

        pages = []
        for t in sorted(self.keep):
            if t not in self.cache:
                continue
            if pat.match(t):
                continue
            m = self.title_map.get(t, {})
            pages.append({"t": t, "f": m.get("file", ""), "zh": m.get("zh", ""),
                          "c": cat_label(t)})
        pages.sort(key=lambda x: (x["zh"] or x["t"]).lower())
        data = json.dumps(pages, ensure_ascii=False)

        def cat_html():
            out = []
            for en, cn, items in NAV:
                lis = []
                for sub, subcn in items:
                    m = self.title_map.get(sub)
                    href = m["file"] if m else "index.html"
                    lis.append(
                        f'<li><a href="pages/{href}">{html_lib.escape(subcn)}'
                        f'<span class="en">{html_lib.escape(sub)}</span></a></li>')
                out.append(
                    f'<div class="cat-card"><h2>{html_lib.escape(cn)}'
                    f'<span class="en">{html_lib.escape(en)}</span></h2>'
                    f'<ul>{"".join(lis)}</ul></div>')
            return "".join(out)

        n = len(pages)
        html = f"""<!DOCTYPE html>
<html lang="zh-CN" class="theme-helldiver view-dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>绝地潜兵2 离线百科（汉化版）</title>
<link rel="stylesheet" href="theme.css">
</head>
<body>
<header class="site-header">
  <span class="brand">🪖 绝地潜兵2 离线百科</span>
  <div class="header-right">
    <a class="btn" href="patch_notes.html">📜 更新日志</a>
    <a class="btn" href="index.html">首页</a>
  </div>
</header>
<main>
  <h1 class="home-title">绝地潜兵2 离线百科</h1>
  <p class="home-sub">汉化版 · 离线可查 · 共 {n} 个词条 · 支持中英文搜索</p>
  <input id="q" class="home-search" type="search"
         placeholder="搜索：强袭虫 / Bile Titan / SG-225 / 战略配备…" autofocus>
  <div class="stats" id="stats">输入关键词过滤词条</div>
  <div class="search-tabs" id="tabs" style="display:none"></div>
  <div class="cat-grid">{cat_html()}</div>
  <div class="search-list" id="list" style="display:none"></div>
  <div class="no-result" id="noresult" style="display:none">未找到词条，试试英文名或部分关键词</div>
</main>
<footer class="site-footer">离线汉化版 · 内容版权归 The Helldivers Wiki / wiki.gg 贡献者所有 · 仅供个人学习交流</footer>
<script>
const PAGES = {data};
const list = document.getElementById('list');
const stats = document.getElementById('stats');
const grid = document.querySelector('.cat-grid');
const q = document.getElementById('q');
const tabs = document.getElementById('tabs');
const noresult = document.getElementById('noresult');
function norm(s){{return s.toLowerCase();}}
function hl(text, kw){{
  if (!kw) return text;
  const i = norm(text).indexOf(kw);
  if (i < 0) return text;
  return text.slice(0, i) + '<mark>' + text.slice(i, i + kw.length) + '</mark>' + text.slice(i + kw.length);
}}
let curCat = '__all__';
function render(){{
  const kw = norm(q.value.trim());
  if (!kw) {{
    grid.style.display = '';
    list.style.display = 'none';
    tabs.style.display = 'none';
    noresult.style.display = 'none';
    stats.textContent = '输入关键词过滤词条';
    curCat = '__all__';
    return;
  }}
  grid.style.display = 'none';
  const all = PAGES.filter(p => norm(p.t).includes(kw) || norm(p.zh).includes(kw) || norm(p.f).includes(kw));
  const catsUsed = [...new Set(all.map(p => p.c))];
  tabs.style.display = '';
  tabs.innerHTML = ['<button class="cat-filter' + (curCat === '__all__' ? ' active' : '') +
    '" data-cat="__all__">全部</button>'].concat(
    catsUsed.map(c => '<button class="cat-filter' + (curCat === c ? ' active' : '') +
      '" data-cat="' + c + '">' + c + '</button>')
  ).join('');
  const items = curCat === '__all__' ? all : all.filter(p => p.c === curCat);
  stats.textContent = curCat === '__all__'
    ? `找到 ${{all.length}} 个词条`
    : `${{curCat}}：${{items.length}} 个（共 ${{all.length}} 个匹配）`;
  list.style.display = items.length ? '' : 'none';
  noresult.style.display = items.length ? 'none' : '';
  list.innerHTML = items.map(p =>
    `<a class="sr" href="pages/${{p.f}}" title="${{p.t}}">` +
    `<span class="sr-text">` +
    `<span class="sr-name">${{p.zh ? hl(p.zh, q.value.trim()) : p.t}}</span>` +
    `<span class="sr-en">${{hl(p.t, q.value.trim())}}</span></span>` +
    `<span class="sr-cat">${{p.c}}</span></a>`
  ).join('');
}}
tabs.addEventListener('click', (e) => {{
  const b = e.target.closest('.cat-filter');
  if (!b) return;
  curCat = b.dataset.cat;
  render();
}});
q.addEventListener('input', render);
const params = new URLSearchParams(location.search);
if (params.get('q')) {{ q.value = params.get('q'); render(); }}
</script>
</body>
</html>
"""
        with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as fp:
            fp.write(html)
        print(f"[Site] 首页完成（{n} 词条）", flush=True)

    def run(self):
        self.build_all()
        self.write_pages()
        self.write_redirects()
        self.copy_images()
        self.write_patch_notes()
        self.write_index()
        import shutil
        shutil.copy2(os.path.join(ROOT, "site_theme.css"), os.path.join(SITE, "theme.css"))
        print("[Site] 页面阶段完成", flush=True)


def main():
    os.makedirs(SITE, exist_ok=True)
    keep = build_keep_set()
    try:
        cats = json.load(open(os.path.join(ROOT, "page_cats.json"), encoding="utf-8"))
        drop_types = {"planet", "lore", "npc", "soundtrack", "subfaction",
                      "capecard", "cosmetic", "pattern", "sector", "lore event"}
        keep = {t for t in keep if cats.get(t, {}).get("type", "") not in drop_types}
        keep = {t for t in keep if "helldivers wiki" not in t.lower()}
    except Exception as e:
        print(f"[Site] page_cats 加载失败，跳过类型过滤: {e}", flush=True)
    tmap = build_title_map(keep)
    with open(os.path.join(SITE, "titles_cn.json"), "w", encoding="utf-8") as fp:
        json.dump(tmap, fp, ensure_ascii=False, indent=0)
    print(f"[Site] 子集 {len(keep)} 页", flush=True)
    SiteBuilder(keep, tmap).run()


if __name__ == "__main__":
    main()
