# -*- coding: utf-8 -*-
"""构建后健康度扫描（适配本机管线：output_zh/site_final + wiki_local.db）

用法:
  python validate_site.py             # 扫描并打印问题
  python validate_site.py --report    # 额外输出 validate_report.json

检查项:
  high   : 应有 infobox 但缺失 druid-infobox（对照 wiki_local.db 的 {{Infobox）
  high   : 页面被截断（缺 </html>）
  medium : mw-editsection 编辑按钮残留
  medium : 教程视频图库条目残留
  low    : 跳主页链接（除页眉"首页/品牌"外）
  low    : 中文后接问号等翻译残留
"""

import argparse
import json
import os
import re
import sqlite3

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "output_zh", "site_final")
PAGES = os.path.join(SITE, "pages")
REPORT = os.path.join(ROOT, "validate_report.json")
DB_PATH = os.path.join(ROOT, "wiki_local.db")

# {{Infobox Basic}} 是 POI 类页面用的非 druid 模板，允许无 druid-infobox
ALLOWED_NON_DRUID = ("Infobox Basic", "Infobox Basic2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    should_have = {}
    for r in db.execute(
            "SELECT title, content FROM pages WHERE ns=0 AND is_redirect=0"):
        wt = r["content"] or ""
        m = re.search(r"\{\{\s*(Infobox[^|} ]*)", wt)
        if m:
            should_have[r["title"]] = m.group(1)

    issues = []
    for fname in sorted(os.listdir(PAGES)):
        if not fname.endswith(".html"):
            continue
        path = os.path.join(PAGES, fname)
        html = open(path, encoding="utf-8", errors="replace").read()
        title = fname[:-5].replace("_", "/")

        # 1. infobox 缺失（high）
        tpl = should_have.get(title)
        if tpl and tpl not in ALLOWED_NON_DRUID and "druid-infobox" not in html:
            issues.append({
                "severity": "high", "page": title, "type": "missing_infobox",
                "detail": f"wikitext 含 {tpl} 但页面无 druid-infobox"})
        # 2. 截断（high）
        if "</html>" not in html:
            issues.append({
                "severity": "high", "page": title, "type": "truncated",
                "detail": "页面缺少 </html>，可能被截断"})
        # 3. 编辑按钮（medium）
        if "mw-editsection" in html:
            issues.append({
                "severity": "medium", "page": title, "type": "editsection",
                "detail": "残留 mw-editsection 编辑按钮"})
        # 4. 教程视频图注（medium）
        if re.search(r"gallerytext\">[^<]*(?:Tutorial Video|教学视频|教程视频|Demonstrating Use)",
                     html, re.I):
            issues.append({
                "severity": "medium", "page": title, "type": "video_caption",
                "detail": "图库含教程视频条目"})
        # 5. 跳主页链接（low）
        for m in re.finditer(r'<a\b[^>]*href="(?:\.\./)?index\.html"[^>]*>([\s\S]*?)</a>',
                             html):
            txt = re.sub(r"<[^>]+>", "", m.group(1))
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt and not re.search(r"首页|主页|返回首页|绝地潜兵2 离线百科", txt):
                issues.append({
                    "severity": "low", "page": title, "type": "home_link",
                    "detail": f"跳主页链接文案: {txt[:40]}"})
                break
        # 6. 中文问号残留（low）
        for q in re.findall(r"[\u4e00-\u9fff]\?", html):
            if q not in ("什么？", "吗？", "呢？", "吧？", "啊？"):
                issues.append({
                    "severity": "low", "page": title, "type": "question_mark",
                    "detail": f"问号残留: {q}"})
                break

    high = [i for i in issues if i["severity"] == "high"]
    medium = [i for i in issues if i["severity"] == "medium"]
    low = [i for i in issues if i["severity"] == "low"]
    print(f"[Validate] 页面 {len(os.listdir(PAGES))} | 高危 {len(high)} | "
          f"中危 {len(medium)} | 低危 {len(low)}")
    for i in high:
        print("  [HIGH]", i["page"], "|", i["detail"])
    for i in medium:
        print("  [MED ]", i["page"], "|", i["detail"])
    for i in low[:20]:
        print("  [LOW ]", i["page"], "|", i["detail"])
    if args.report:
        json.dump(issues, open(REPORT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"[Validate] 报告已写入 {REPORT}")
    return 1 if high else 0


if __name__ == "__main__":
    raise SystemExit(main())
