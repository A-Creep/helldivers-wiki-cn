# -*- coding: utf-8 -*-
"""按确认范围裁剪离线镜像：只保留战斗实用页 + 补丁页"""

import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "output_zh", "site")
PAGES = os.path.join(SITE, "pages")
IMAGES = os.path.join(SITE, "images")
OUT = os.path.join(ROOT, "output_zh", "site_subset")
OUT_PAGES = os.path.join(OUT, "pages")
OUT_IMAGES = os.path.join(OUT, "images")


def load_lines(p):
    if not os.path.exists(p):
        return []
    return [l.strip() for l in open(p, encoding="utf-8") if l.strip()]


def build_keep_set():
    keep = set(load_lines("keep_pages.txt"))
    # 补丁页：纯文字为主，保留（用户确认）
    patch_re = re.compile(r"^\d+\.\d+")
    with open(os.path.join(SITE, "titles.json"), encoding="utf-8") as fp:
        titles = json.load(fp)
    patch = {t for t in titles if patch_re.match(t)}
    keep |= patch
    # MAYBE：默认保留，剔除明确背景项
    maybe = load_lines("maybe_pages.txt")
    drop_pat = re.compile(
        r"(sector|prime|secundus|iii\b|iv\b|v\b|vi\b|vii\b|viii\b|ix\b|xi\b|xii\b|"
        r"pass\b|bay\b|cove\b|harbor\b|port\b|rock\b|beach\b|vale\b|ridge\b|"
        r"battle tracker|at ease|big stretch|big whoop|badge of order|"
        r"blazing samaritan|authoritarian light|agent of oblivion|agitator|"
        r"alcubierre|atmospheric interference|atmospheric monitoring|"
        r"automaton orbital superweapon|automaton remains|biome name|"
        r"center for|confined|chart |c\.o\.b|case of|cup of|"
        r"liber-tea|library card|handwritten|scribbled|welcome sign|"
        r"captain's log|maintenance report|payroll|vending|forklift|"
        r"hand carts|cars\b|poster\b|graves\b|corn farm|farm\b|greenhouse|"
        r"solar farm|cargo container|exploding barrels|flower|plant\b|shrub|"
        r"mushroom|moor\b|boneyard|burial|deforester|executioner's canopy|"
        r"monument|wall of|glory|tapestry|testament|diagram of|ode to|"
        r"vision of|proof of|schema|rightful occupier|conductor of|"
        r"standard of|stars and|strength in|thumb of|thundering|"
        r"welcome to|you're next|per democrasum|united in|harbinger of|"
        r"order of the|pillars of|seal of|pride of|protector of|"
        r"reaper of|shield of|spirit of|starship|voyage|memorial)",
        re.I)
    for t in maybe:
        if drop_pat.search(t):
            continue
        keep.add(t)
    return keep


IMG_REF = re.compile(r'(?:src|href)="images/([^"#?]+)"')
SRCSET_REF = re.compile(r'srcset="([^"]+)"')
LINK_REF = re.compile(r'href="([^"#]+)(#[^"]*)?"')


def collect_image_refs(html):
    names = set()
    for m in IMG_REF.finditer(html):
        names.add(m.group(1))
    for m in SRCSET_REF.finditer(html):
        for cand in m.group(1).split(","):
            cand = cand.strip()
            if cand.startswith("images/"):
                names.add(cand.split(" ")[0][len("images/"):])
    return names


def main():
    keep = build_keep_set()
    with open(os.path.join(SITE, "titles.json"), encoding="utf-8") as fp:
        titles = json.load(fp)
    keep_files = set()
    missing = []
    for t in keep:
        f = titles.get(t)
        if f and os.path.exists(os.path.join(PAGES, f)):
            keep_files.add(f)
        elif t:
            missing.append(t)
    print(f"[Subset] 保留页面 {len(keep_files)} / {len(keep)}（缺文件 {len(missing)}）", flush=True)

    os.makedirs(OUT_PAGES, exist_ok=True)
    os.makedirs(OUT_IMAGES, exist_ok=True)
    img_names = set()
    for f in sorted(keep_files):
        src = os.path.join(PAGES, f)
        dst = os.path.join(OUT_PAGES, f)
        html = open(src, encoding="utf-8").read()
        # 失效链接改写为首页
        def fix_link(m):
            target = m.group(1)
            if target.endswith(".html") and target != "index.html":
                if target not in keep_files:
                    return 'href="index.html"'
            return m.group(0)
        html = LINK_REF.sub(fix_link, html)
        open(dst, "w", encoding="utf-8").write(html)
        img_names |= collect_image_refs(html)
    # 复制图片
    copied = 0
    for name in sorted(img_names):
        s = os.path.join(IMAGES, name)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(OUT_IMAGES, name))
            copied += 1
        else:
            print(f"[Subset] 缺图: {name}", flush=True)
    # 主题
    shutil.copy2(os.path.join(SITE, "theme.css"), os.path.join(OUT, "theme.css"))
    # 重建首页
    pages = [{"t": t, "f": titles[t]} for t in sorted(keep) if titles.get(t) in keep_files]
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
  <p class="home-sub">战斗实用版 · 离线可查 · 共 {n} 个页面</p>
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
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    size_mb = sum(os.path.getsize(os.path.join(dp, f))
                  for dp, _, fs in os.walk(OUT) for f in fs) / 1024 / 1024
    print(f"[Subset] 完成：页面 {n}，图片 {copied}，总大小 {size_mb:.0f} MB", flush=True)


if __name__ == "__main__":
    main()
