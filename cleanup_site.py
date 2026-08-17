import os
import shutil
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SITE = "output_zh/site_final"
PAGES = os.path.join(SITE, "pages")

# 删除不在词条映射里的残留页面文件（被 DROP 的背景页/旧索引页）
try:
    tmap = json.load(open(os.path.join(SITE, "titles_cn.json"), encoding="utf-8"))
    keep_files = {v["file"].lower() for v in tmap.values()}
    extra = 0
    for f in os.listdir(PAGES):
        if f.endswith(".html") and f.lower() not in keep_files:
            os.remove(os.path.join(PAGES, f))
            extra += 1
    print("removed non-keep pages:", extra)
except Exception as e:
    print("skip map cleanup:", e)

# 删除 pages 下残留的旧索引页（特征：含 .page-list 分组结构的生成页）
removed = 0
for f in os.listdir(PAGES):
    if not f.endswith(".html"):
        continue
    p = os.path.join(PAGES, f)
    try:
        html = open(p, encoding="utf-8").read()
    except Exception:
        continue
    if 'class="page-list"' in html and 'class="cat-card-grid"' not in html:
        os.remove(p)
        removed += 1
print("removed stale index pages:", removed)

# 复制主题
shutil.copy2("site_theme.css", os.path.join(SITE, "theme.css"))
print("theme copied")
