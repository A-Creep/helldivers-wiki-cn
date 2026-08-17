# -*- coding: utf-8 -*-
"""检测并修复缺失 infobox / 被截断的页面（适配本机管线）

用法:
  python fix_broken_pages.py --dry-run   # 只检测
  python fix_broken_pages.py --fix       # 删除坏页面的缓存行并重建站点

原理:
  1. 对照 wiki_local.db：wikitext 有 {{Infobox 但渲染缓存无 druid-infobox
  2. 检查页面是否被截断（缺 </html>）
  3. --fix：从 zh_cache.jsonl 删除坏页面对应行 -> 调用 build_site.py 重渲染
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "output_zh", "site_final")
PAGES = os.path.join(SITE, "pages")
CACHE = os.path.join(SITE, "zh_cache.jsonl")
DB_PATH = os.path.join(ROOT, "wiki_local.db")
ALLOWED_NON_DRUID = ("Infobox Basic", "Infobox Basic2")


def detect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    should_have = {}
    for r in db.execute(
            "SELECT title, content FROM pages WHERE ns=0 AND is_redirect=0"):
        wt = r["content"] or ""
        m = re.search(r"\{\{\s*(Infobox[^|} ]*)", wt)
        if m:
            should_have[r["title"]] = m.group(1)

    bad = []
    for fname in sorted(os.listdir(PAGES)):
        if not fname.endswith(".html"):
            continue
        path = os.path.join(PAGES, fname)
        html = open(path, encoding="utf-8", errors="replace").read()
        title = fname[:-5].replace("_", "/")
        tpl = should_have.get(title)
        if tpl and tpl not in ALLOWED_NON_DRUID and "druid-infobox" not in html:
            bad.append((title, "missing_infobox"))
        elif "</html>" not in html:
            bad.append((title, "truncated"))
    return bad


def fix(bad_titles):
    if not os.path.exists(CACHE):
        print("[Fix] 缓存不存在:", CACHE)
        return
    lines = open(CACHE, encoding="utf-8").read().splitlines()
    kept = []
    removed = 0
    for line in lines:
        try:
            it = json.loads(line)
        except Exception:
            kept.append(line)
            continue
        if it.get("t") in bad_titles:
            removed += 1
        else:
            kept.append(line)
    open(CACHE, "w", encoding="utf-8").write("\n".join(kept) + "\n")
    print(f"[Fix] 已从缓存移除 {removed} 个条目，开始重建站点...")
    code = subprocess.call([sys.executable, os.path.join(ROOT, "build_site.py")],
                           cwd=ROOT)
    print(f"[Fix] build_site.py 退出码 {code}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()

    bad = detect()
    print(f"[Fix] 检测到 {len(bad)} 个坏页面")
    for t, why in bad:
        print(f"   {t} | {why}")
    if args.fix and bad:
        fix({t for t, _ in bad})
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
