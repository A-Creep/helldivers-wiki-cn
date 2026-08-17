# -*- coding: utf-8 -*-
"""二次压缩：>150KB 的图缩到最大宽 1280，重编码 webp q78"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "output_zh", "site_final", "images")
MAX_W = 1280
MIN_SIZE = 150 * 1024
QUALITY = 78


def work(path):
    name = os.path.basename(path)
    try:
        size = os.path.getsize(path)
        if size < MIN_SIZE:
            return None
        ext = os.path.splitext(name)[1].lower()
        if ext not in (".webp", ".jpg", ".jpeg"):
            return None
        im = Image.open(path)
        frames = []
        if getattr(im, "is_animated", False):
            try:
                while True:
                    im.seek(len(frames))
                    frames.append(im.convert("RGB").copy())
            except EOFError:
                pass
        else:
            frames = [im.convert("RGB")]
        changed = False
        for i, f in enumerate(frames):
            if f.width > MAX_W:
                r = MAX_W / f.width
                frames[i] = f.resize((MAX_W, max(1, int(f.height * r))), Image.LANCZOS)
                changed = True
        out = os.path.join(IMAGES, name)
        if len(frames) > 1:
            frames[0].save(out, "WEBP", save_all=True, append_images=frames[1:],
                           quality=QUALITY, method=6, loop=getattr(im, "info", {}).get("loop", 0))
        else:
            frames[0].save(out, "WEBP" if ext == ".webp" else "JPEG",
                           quality=QUALITY, method=6,
                           **({"optimize": True} if ext != ".webp" else {}))
        newsize = os.path.getsize(out)
        return name, size, newsize, changed
    except Exception as e:
        return ("ERR", name, str(e)[:80], 0)


def main():
    files = [os.path.join(IMAGES, f) for f in os.listdir(IMAGES)]
    total_before = 0
    total_after = 0
    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(work, p) for p in files]
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r and r[0] != "ERR":
                total_before += r[1]
                total_after += r[2]
            elif r and r[0] == "ERR":
                print("ERR", r[1], r[2], flush=True)
            if done % 500 == 0:
                print(f"[C2] {done}/{len(files)}", flush=True)
    print(f"[C2] 完成：{total_before/1024/1024:.0f}MB -> {total_after/1024/1024:.0f}MB", flush=True)


if __name__ == "__main__":
    main()
