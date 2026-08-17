# -*- coding: utf-8 -*-
"""按 wikitext infobox 类型给子集页面分类，输出 page_cats.json"""

import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_site import build_keep_set

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

db = sqlite3.connect("wiki_local.db")
db.row_factory = sqlite3.Row
keep = build_keep_set()

INFOBOX_RE = re.compile(r"\{\{\s*Infobox\s+([A-Za-z][A-Za-z ]{0,40})", re.I)
PARAM_RE = re.compile(r"^\s*\|?\s*([A-Za-z_ ]+?)\s*=\s*(.*?)\s*$", re.M)

rows = {r["title"]: r["content"] or "" for r in db.execute(
    "SELECT title, content FROM pages WHERE ns=0 AND is_redirect=0")}

result = {}
for t in keep:
    content = rows.get(t, "")
    m = INFOBOX_RE.search(content)
    itype = m.group(1).strip().lower() if m else ""
    itype = " ".join(itype.split())
    params = {}
    if m:
        block = content[m.end():m.end() + 8000]
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("}}"):
                break
            pm = re.match(r"\|?\s*([A-Za-z_ ]+?)\s*=\s*(.*)$", line)
            if pm:
                k = pm.group(1).strip().lower()
                v = pm.group(2).strip()
                if k and v and k not in params:
                    params[k] = v
    result[t] = {"type": itype, "params": params}

with open("page_cats.json", "w", encoding="utf-8") as fp:
    json.dump(result, fp, ensure_ascii=False, indent=0)

# 统计
from collections import Counter
c = Counter(v["type"] for v in result.values() if v["type"])
print("页面总数:", len(result))
for k, n in c.most_common(30):
    print(f"  {n:5d}  {k}")
