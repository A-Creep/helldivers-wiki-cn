# -*- coding: utf-8 -*-
"""按 infobox 类型生成中文分类索引页

列表型小类（敌人/武器/战略配备/护甲/任务/生物群系/环境危害/地点）生成索引页；
机制单页类小类（伤害/战斗/效果/难度等）直接链接原站页面，不生成索引页。
Acquisitions 分类整体移除。
"""

import html as html_lib
import json
import os
import re
import sys
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "output_zh", "site_final")
PAGES = os.path.join(SITE, "pages")
CAT_DIR = os.path.join(SITE, "categories")

CATS = json.load(open(os.path.join(ROOT, "page_cats.json"), encoding="utf-8"))
TMAP = json.load(open(os.path.join(SITE, "titles_cn.json"), encoding="utf-8"))
CONV = json.load(open(os.path.join(ROOT, "output_zh", "site", "images_conv.json"),
                       encoding="utf-8")) if os.path.exists(
    os.path.join(ROOT, "output_zh", "site", "images_conv.json")) else {}

# 从渲染缓存提取每页第一张图（infobox 主图）
IMGS = {}
try:
    for line in open(os.path.join(SITE, "zh_cache.jsonl"), encoding="utf-8"):
        it = json.loads(line)
        h = it["h"]
        for m in re.finditer(r'<img[^>]+src="([^"]+)"', h):
            src = m.group(1)
            if "/images/" in src:
                path = urllib.parse.urlparse(src).path
                base = urllib.parse.unquote(os.path.basename(path))
                base = re.sub(r'[<>:"/\\|?*]', "_", base)
                bl = base.lower()
                if any(x in bl for x in ("disambig", "unknown", "placeholder",
                                         "question", "missing", "noimage", "no-image",
                                         "fallback")):
                    continue
                local = CONV.get(base, base)
                IMGS[it["t"]] = "../images/" + urllib.parse.quote(local)
                break
except Exception:
    pass


def zh(t):
    return TMAP.get(t, {}).get("zh") or t


def link_item(t):
    z = html_lib.escape(zh(t))
    e = html_lib.escape(t)
    en_span = f'<span class="cat-en">{e}</span>' if zh(t) != t else ""
    img = IMGS.get(t, "")
    if img:
        return (f'<a class="cat-item" href="../pages/{html_lib.escape(TMAP[t]["file"])}">'
                f'<span class="cat-thumb"><img loading="lazy" src="{html_lib.escape(img)}" alt=""></span>'
                f'<span class="cat-name">{z}</span>'
                f'{en_span}</a>')
    initial = (zh(t) or t)[:1].upper()
    return (f'<a class="cat-item cat-nothumb" data-initial="{html_lib.escape(initial)}" '
            f'href="../pages/{html_lib.escape(TMAP[t]["file"])}">'
            f'<span class="cat-name">{z}</span>'
            f'{en_span}</a>')


def render(groups, title, desc=""):
    body = []
    if desc:
        body.append(f'<p class="home-sub">{desc}</p>')
    real = [g for g in groups if g[1]]
    if len(real) > 1:
        filters = ['<button class="cat-filter active" data-target="__all__">全部</button>']
        filters += [
            f'<button class="cat-filter" data-target="{html_lib.escape(g[0])}">'
            f'{html_lib.escape(g[0])}</button>'
            for g in real
        ]
        body.append('<div class="cat-filters">' + "".join(filters) + "</div>")
    for gname, items in groups:
        if not items:
            continue
        body.append(f'<div class="cat-group" data-group="{html_lib.escape(gname)}">')
        body.append(f'<h2 class="cat-group-title">{html_lib.escape(gname)}</h2>')
        body.append('<div class="cat-card-grid">' + "".join(link_item(t) for t in items) + "</div>")
        body.append("</div>")
    body.append('<div class="no-result" style="display:none">未找到词条，试试英文名或部分关键词</div>')
    esc = html_lib.escape(title)
    return f"""<!DOCTYPE html>
<html lang="zh-CN" class="theme-helldiver view-dark">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc} - 绝地潜兵2 离线百科</title>
<link rel="stylesheet" href="../theme.css">
</head>
<body>
<header class="site-header">
  <a class="brand" href="../index.html">🪖 绝地潜兵2 离线百科</a>
  <div class="header-right">
    <input id="q" class="search-input" type="search" placeholder="搜索中英文词条…"
           onkeydown="if(event.key==='Enter'){{location='../index.html?q='+encodeURIComponent(this.value);}}">
    <a class="btn" href="../patch_notes.html">📜 更新日志</a>
    <a class="btn" href="../index.html">首页</a>
  </div>
</header>
<main class="content">
  <h1 class="page-title">{esc}</h1>
  <div class="mw-parser-output">{''.join(body)}</div>
</main>
<script>
(function(){{
  const btns = Array.from(document.querySelectorAll('.cat-filter'));
  const groups = Array.from(document.querySelectorAll('.cat-group'));
  const no = document.querySelector('.no-result');
  function apply(target){{
    let shown = 0;
    groups.forEach(g => {{
      const ok = target === '__all__' || g.dataset.group === target;
      g.style.display = ok ? '' : 'none';
      if (ok) shown += 1;
    }});
    if (no) no.style.display = shown ? 'none' : '';
    btns.forEach(b => b.classList.toggle('active', b.dataset.target === target));
  }}
  btns.forEach(b => b.addEventListener('click', () => apply(b.dataset.target)));
}})();
</script>
<footer class="site-footer">离线汉化版 · 内容版权归 The Helldivers Wiki / wiki.gg 贡献者所有 · 仅供个人学习交流</footer>
</body>
</html>
"""


def write(fname, title, groups, desc=""):
    os.makedirs(CAT_DIR, exist_ok=True)
    with open(os.path.join(CAT_DIR, fname), "w", encoding="utf-8") as fp:
        fp.write(render(groups, title, desc))
    print(f"[Idx] {fname} 分组 {len([g for g in groups if g[1]])}", flush=True)


def bucket(items, rules):
    b = {name: [] for name, _ in rules}
    b["其他"] = []
    for t in items:
        for name, pat in rules:
            if pat.search(t):
                b[name].append(t)
                break
        else:
            b["其他"].append(t)
    return [(k, sorted(v, key=lambda x: (zh(x) or x).lower())) for k, v in b.items() if v]


def of_type(*types):
    return [t for t, v in CATS.items() if v["type"] in types]


def param(t, k):
    return (CATS[t]["params"] or {}).get(k, "")


def main():
    # 重建 categories 目录
    if os.path.isdir(CAT_DIR):
        for f in os.listdir(CAT_DIR):
            os.remove(os.path.join(CAT_DIR, f))
    os.makedirs(CAT_DIR, exist_ok=True)

    # ---- 敌人 ----
    en_rules = [
        ("终结族", re.compile(r"(terminid|bile|charger|spewer|hunter|stalker|scavenger|"
                               r"warrior|brood|impaler|shrieker|hive|nursing|alpha|"
                               r"pouncer|skitter|termadon|dragonroach)", re.I)),
        ("机器人", re.compile(r"(automaton|hulk|strider|tank|trooper|raider|commissar|"
                               r"berserker|devastator|scout|marauder|brawler|wraith|"
                               r"shredder|annihilator|barrager|factory|war strider|"
                               r"jet brigade|incineration|cyborg)", re.I)),
        ("光能者", re.compile(r"(illuminate|voteless|wretch|crusher|gazer|harvester|"
                               r"overseer|watcher|mindless|appropriate)", re.I)),
        ("特殊变体", re.compile(r"(spore burst|rupture|predator strain)", re.I)),
    ]
    enemies = []
    for t in of_type("enemy"):
        fac = param(t, "faction").lower()
        if "terminid" in fac:
            enemies.append(("终结族", t))
        elif "automaton" in fac or "cyborg" in fac or "jet" in fac or "incineration" in fac:
            enemies.append(("机器人", t))
        elif "illuminate" in fac or "appropriate" in fac:
            enemies.append(("光能者", t))
        else:
            enemies.append(("其他", t))
    groups = {}
    for g, t in enemies:
        groups.setdefault(g, []).append(t)
    write("enemies.html", "敌人",
          [(g, sorted(v, key=lambda x: (zh(x) or x).lower()))
           for g, v in groups.items()],
          "按阵营查阅敌人单位与弱点")

    # ---- 武器 ----
    def wgroup(t):
        cat = param(t, "weapon_category").lower()
        wtype = param(t, "weapon_type").lower()
        if CATS[t]["type"] == "throwable":
            return "手雷/投掷物"
        if CATS[t]["type"] == "attachment":
            return "配件"
        if "melee" in wtype:
            return "近战"
        if "secondary" in cat or "pistol" in wtype or "sidearm" in wtype:
            return "副武器"
        return "主武器"

    wb = {}
    for t in of_type("weapon", "throwable", "attachment"):
        wb.setdefault(wgroup(t), []).append(t)
    write("weapons.html", "武器",
          [(g, sorted(v, key=lambda x: (zh(x) or x).lower()))
           for g, v in wb.items()],
          "主武器 / 副武器 / 支援武器 / 近战 / 手雷 / 配件")

    # ---- 战略配备 ----
    sb = {}
    for t in of_type("stratagem", "support weapon"):
        p = param(t, "permit_type").lower()
        if "supply" in p:
            sb.setdefault("补给型", []).append(t)
        elif CATS[t]["type"] == "support weapon":
            sb.setdefault("补给型", []).append(t)
        elif "defens" in p:
            sb.setdefault("防御型", []).append(t)
        elif "offens" in p:
            sb.setdefault("进攻型", []).append(t)
        else:
            sb.setdefault("其他", []).append(t)
    write("stratagems.html", "战略配备",
          [(g, sorted(v, key=lambda x: (zh(x) or x).lower()))
           for g, v in sb.items()],
          "进攻 / 防御 / 补给")

    # ---- 护甲 / 被动 ----
    armors = of_type("armor")
    write("armors.html", "护甲",
          [("护甲套装", sorted(armors, key=lambda x: (zh(x) or x).lower()))])
    passives = of_type("armor passive")
    write("passives.html", "护甲被动",
          [("全部", sorted(passives, key=lambda x: (zh(x) or x).lower()))])

    # ---- 强化资源 ----
    boosters = [t for t in TMAP if "Booster" in t]
    write("boosters.html", "强化资源",
          [("全部", sorted(boosters, key=lambda x: (zh(x) or x).lower()))])

    # ---- 任务 ----
    missions = of_type("mission")
    write("missions.html", "任务",
          [("全部", sorted(missions, key=lambda x: (zh(x) or x).lower()))])

    # ---- 生物群系 / 环境危害 / 地点 ----
    biomes = of_type("biome")
    write("biomes.html", "生物群系",
          [("全部", sorted(biomes, key=lambda x: (zh(x) or x).lower()))])
    hazards = of_type("hazard")
    write("env_hazards.html", "环境危害",
          [("全部", sorted(hazards, key=lambda x: (zh(x) or x).lower()))])
    pois = of_type("poi", "structure")
    write("poi.html", "次要地点",
          [("全部", sorted(pois, key=lambda x: (zh(x) or x).lower()))])

    # ---- 更新首页 NAV（索引页替换原站列表页；机制单页保持原站链接） ----
    nav_map = {
        "Weapons.html": "weapons.html",
        "Stratagems.html": "stratagems.html",
        "Armor.html": "armors.html",
        "Armor_Passives.html": "passives.html",
        "Boosters.html": "boosters.html",
        "Factions.html": "enemies.html",
        "Missions.html": "missions.html",
        "Biomes.html": "biomes.html",
        "Environmental_Hazards.html": "env_hazards.html",
        "Minor_Places_of_Interest.html": "poi.html",
    }
    idx = os.path.join(SITE, "index.html")
    html = open(idx, encoding="utf-8").read()
    for old, new in nav_map.items():
        html = html.replace(f'href="pages/{old}"', f'href="categories/{new}"')
    open(idx, "w", encoding="utf-8").write(html)
    print("[Idx] 首页 NAV 已更新", flush=True)


if __name__ == "__main__":
    main()
