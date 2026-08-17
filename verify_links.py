"""全站链接完整性检查（HTMLParser + 双重解码 + 大小写不敏感）"""

import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SITE_ROOT = Path("output_zh/site_final").resolve()


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        elif tag in ("img", "script", "link", "source"):
            if "src" in attrs:
                self.links.append(attrs["src"])
            if "href" in attrs:
                self.links.append(attrs["href"])


def decode_link(raw):
    d = urllib.parse.unquote(raw)          # URL 百分号解码
    d = d.split("#")[0].split("?")[0]      # 去掉锚点/查询
    return d


def build_index():
    idx = {}
    for p in SITE_ROOT.rglob("*"):
        if p.is_file():
            rel = p.relative_to(SITE_ROOT).as_posix()
            idx[rel.lower()] = rel
    return idx


def main():
    idx = build_index()
    missing = []
    checked = 0
    for hf in SITE_ROOT.rglob("*.html"):
        content = hf.read_text(encoding="utf-8")
        parser = LinkExtractor()
        parser.feed(content)
        for raw in parser.links:
            if not raw:
                continue
            if raw.startswith(("http://", "https://", "mailto:", "tel:",
                               "javascript:", "data:", "mw-data:", "#")):
                continue
            href = decode_link(raw)
            if not href:
                continue
            target = SITE_ROOT / href.lstrip("/") if href.startswith("/") \
                else hf.parent / href
            try:
                rel_target = target.resolve().relative_to(SITE_ROOT).as_posix()
            except (ValueError, OSError):
                rel_target = target.as_posix()
            checked += 1
            if rel_target.lower() not in idx:
                missing.append((hf.relative_to(SITE_ROOT).as_posix(), raw, href, rel_target))
    print(f"检查链接 {checked} 个")
    if missing:
        print(f"缺失 {len(missing)} 个：")
        for f, raw, href, exp in missing[:80]:
            print(f"  {f} | raw={raw[:60]} | exp={exp}")
        sys.exit(1)
    print("全部链接正常")


if __name__ == "__main__":
    main()
