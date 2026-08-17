import os
import re
import shutil
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "output_zh", "site", "images")
DST = os.path.join(ROOT, "output_zh", "site_final", "images")
PAGES = os.path.join(ROOT, "output_zh", "site_final", "pages")

FIX = {
    "1000px-Terminids.webp.png": "1000px-Terminids.webp.webp",
    "1007px-Penta_City_Planetside_2.png": "1007px-Penta_City_Planetside_2.webp",
}

# 下载缺失的 svg
url = "https://helldivers.wiki.gg/images/DSS_Action_Fallback_Icon.svg"
try:
    r = requests.get(url, headers={"User-Agent": "HD2WikiLocalizer/1.0"}, timeout=30)
    r.raise_for_status()
    with open(os.path.join(SRC, "DSS_Action_Fallback_Icon.svg"), "wb") as fp:
        fp.write(r.content)
    print("downloaded DSS_Action_Fallback_Icon.svg")
except Exception as e:
    print("download fail", e)

for old, new in FIX.items():
    s = os.path.join(SRC, new)
    if os.path.exists(s):
        shutil.copy2(s, os.path.join(DST, new))
        print("copied", new)
    else:
        print("missing source", new)

# 改写页面引用
n_pages = 0
for f in os.listdir(PAGES):
    if not f.endswith(".html"):
        continue
    p = os.path.join(PAGES, f)
    html = open(p, encoding="utf-8").read()
    orig = html
    for old, new in FIX.items():
        html = html.replace(f"../images/{old}", f"../images/{new}")
    if html != orig:
        open(p, "w", encoding="utf-8").write(html)
        n_pages += 1
print("patched pages:", n_pages)
