import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PAGES = "output_zh/site_final/pages"


def remove_blocks(html):
    """删除含 HD1/跨游戏提示的 hatnote/dablink/mbox 块"""
    pat = re.compile(
        r"<(?P<tag>div|p|span|table|blockquote)[^>]*class=\"[^\"]*"
        r"(?:hatnote|dablink|mbox|dismissable)[^\"]*\"[^>]*>"
        r"[\s\S]*?</(?P=tag)>", re.I)
    out = []
    changed = False
    pos = 0
    for m in pat.finditer(html):
        block = m.group(0)
        low = block.lower()
        if ("looking for something that isn't here" in low or
                "helldivers 1" in low or "helldivers™" in low or
                "绝地潜兵 1" in low or "绝地潜兵1" in low or
                "this article is about" in low and "helldivers 1" in low):
            out.append(html[pos:m.start()])
            pos = m.end()
            changed = True
    out.append(html[pos:])
    return "".join(out), changed


def clean_title_attrs(html):
    html, n1 = re.subn(
        r'title="[^"]*[Hh]elldivers\s*1[^"]*"', 'title=""', html)
    html, n2 = re.subn(
        r'title="[^"]*绝地潜兵\s*1[^"]*"', 'title=""', html)
    return html, n1 + n2


def remove_navboxes(html):
    """删除包含 Helldivers 1 / 绝地潜兵 1 的 navbox 板块"""
    out = []
    pos = 0
    changed = False
    i = 0
    n = len(html)
    while i < n:
        m = re.compile(r"<(table|div)\b[^>]*class=\"[^\"]*navbox[^\"]*\"[^>]*>", re.I).search(html, i)
        if not m:
            break
        tag = m.group(1)
        start = m.start()
        i = m.end()
        depth = 1
        scan = html[i:]
        j = 0
        while j < len(scan) and depth:
            op = re.compile(r"<" + tag + r"\b", re.I).search(scan, j)
            cl = re.compile(r"</" + tag + r">", re.I).search(scan, j)
            if cl is None:
                break
            if op is not None and op.start() < cl.start():
                depth += 1
                j = op.end()
            else:
                depth -= 1
                j = cl.end()
        if depth > 0:
            # 标签未闭合（解析异常）：跳过不删，防止截断整页
            i = m.end()
            continue
        end = i + j
        block = html[start:end]
        low = block.lower()
        if ("helldivers 1" in low or "绝地潜兵 1" in low or "绝地潜兵1" in low or
                "hd1" in low):
            out.append(html[pos:start])
            pos = end
            i = end
            changed = True
        else:
            i = end
    out.append(html[pos:])
    return "".join(out), changed


def remove_tabs(html):
    """删除原站跨游戏切换标签页（table.tabs，含 HD1 链接）"""
    pat = re.compile(
        r"<table[^>]*class=\"[^\"]*\btabs\b[^\"]*\"[^>]*>[\s\S]*?</table>", re.I)
    out = []
    pos = 0
    changed = False
    for m in pat.finditer(html):
        block = m.group(0)
        low = block.lower()
        if ("helldivers 1" in low or "绝地潜兵 1" in low or "绝地潜兵1" in low):
            out.append(html[pos:m.start()])
            pos = m.end()
            changed = True
    out.append(html[pos:])
    return "".join(out), changed


def remove_hd1_sections(html):
    """删除标题为 绝地潜兵1/Helldivers 1 的章节（到下一个同级/更高级标题）"""
    pat = re.compile(
        r"<h([23])[^>]*>(?:(?!</h\1>)[\s\S])*?"
        r"(?:绝地潜兵\s*1|helldivers\s*1)(?:(?!</h\1>)[\s\S])*?</h\1>",
        re.I)
    out = []
    pos = 0
    changed = False
    for m in pat.finditer(html):
        lvl = int(m.group(1))
        start = m.start()
        nxt = re.compile(r"<h[1-" + str(lvl) + r"]\b", re.I).search(html, m.end())
        end = nxt.start() if nxt else len(html)
        # 不能删掉页面模板尾部（正文容器 </main> 之后）
        main_end = html.find("</main>", m.end())
        if main_end != -1:
            end = min(end, main_end)
        out.append(html[pos:start])
        pos = end
        changed = True
    out.append(html[pos:])
    return "".join(out), changed


def main():
    total_blocks = 0
    total_titles = 0
    n_files = 0
    for f in sorted(os.listdir(PAGES)):
        if not f.endswith(".html"):
            continue
        p = os.path.join(PAGES, f)
        html = open(p, encoding="utf-8").read()
        orig = html
        html, b = remove_blocks(html)
        html, t = clean_title_attrs(html)
        html, nv = remove_navboxes(html)
        html, tb = remove_tabs(html)
        html, sec = remove_hd1_sections(html)
        if html != orig:
            open(p, "w", encoding="utf-8").write(html)
            n_files += 1
            total_blocks += b
            total_titles += t
            total_blocks += nv
            total_blocks += tb
            total_blocks += sec
    print(f"[HD1] 处理 {n_files} 个文件，删除块 {total_blocks}，清 title {total_titles}")


if __name__ == "__main__":
    main()
