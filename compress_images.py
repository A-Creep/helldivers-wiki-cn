# -*- coding: utf-8 -*-
"""压缩镜像图片：大 PNG/GIF 转 WebP，并同步改写页面引用"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(ROOT, "output_zh", "site", "images")
PAGES = os.path.join(ROOT, "output_zh", "site", "pages")
MAP_FILE = os.path.join(ROOT, "output_zh", "site", "images_conv.json")

PNG_MIN = 40 * 1024        # 大于 40KB 的 PNG 才转换
PNG_QUALITY = 82
GIF_QUALITY = 80
MAX_W = 1600               # 超过此宽度缩放
GIF_MAX_W = 1200
WORKERS = 8


def convert(path: str):
    """返回 (old_name, new_name) 或 None"""
    name = os.path.basename(path)
    size = os.path.getsize(path)
    ext = os.path.splitext(name)[1].lower()
    if ext == ".png" and size < PNG_MIN:
        return None
    if ext not in (".png", ".gif"):
        return None
    try:
        im = Image.open(path)
        frames = []
        if getattr(im, "is_animated", False):
            try:
                while True:
                    im.seek(len(frames))
                    frames.append(im.convert("RGBA" if ext == ".png" else "RGB").copy())
            except EOFError:
                pass
        else:
            frames = [im.convert("RGBA" if ext == ".png" else "RGB")]
        if not frames:
            return None
        max_w = GIF_MAX_W if ext == ".gif" else MAX_W
        for i, f in enumerate(frames):
            if f.width > max_w:
                r = max_w / f.width
                frames[i] = f.resize((max_w, int(f.height * r)), Image.LANCZOS)
        new_name = os.path.splitext(name)[0] + ".webp"
        new_path = os.path.join(IMAGES, new_name)
        kw = dict(quality=GIF_QUALITY if ext == ".gif" else PNG_QUALITY, method=6)
        if len(frames) > 1:
            frames[0].save(new_path, "WEBP", save_all=True, append_images=frames[1:],
                           loop=getattr(im, "info", {}).get("loop", 0), **kw)
        else:
            frames[0].save(new_path, "WEBP", **kw)
        if os.path.exists(new_path) and os.path.getsize(new_path) > 0:
            return name, new_name
    except Exception as e:
        print(f"[Err] {name}: {e}", flush=True)
    return None


def main(limit: int = 0):
    files = [os.path.join(IMAGES, f) for f in os.listdir(IMAGES)
             if os.path.splitext(f)[1].lower() in (".png", ".gif")]
    if limit:
        files = files[:limit]
    print(f"[Compress] 待处理 {len(files)} 张 (PNG/GIF)", flush=True)
    mapping = {}
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(convert, p) for p in files]
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r:
                mapping[r[0]] = r[1]
            if done % 500 == 0:
                print(f"[Compress] {done}/{len(files)}", flush=True)
    with open(MAP_FILE, "w", encoding="utf-8") as fp:
        json.dump(mapping, fp, ensure_ascii=False, indent=0)
    print(f"[Compress] 转换 {len(mapping)} 张，改写页面引用 ...", flush=True)
    n_pages = 0
    for f in os.listdir(PAGES):
        p = os.path.join(PAGES, f)
        if not f.endswith(".html"):
            continue
        with open(p, "r", encoding="utf-8") as fp:
            html = fp.read()
        orig = html
        for old, new in mapping.items():
            html = html.replace(f"images/{old}", f"images/{new}")
        if html != orig:
            with open(p, "w", encoding="utf-8") as fp:
                fp.write(html)
            n_pages += 1
    # 删除已转换的旧文件
    removed = 0
    for old in mapping:
        p = os.path.join(IMAGES, old)
        if os.path.exists(p):
            os.remove(p)
            removed += 1
    print(f"[Compress] 完成：改写页面 {n_pages}，删除旧图 {removed}", flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    main(args.limit)
