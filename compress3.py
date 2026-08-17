import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "output_zh", "site_final", "images")
MAX_W = 1024
MIN_SIZE = 500 * 1024
QUALITY = 72


def work(path):
    name = os.path.basename(path)
    try:
        if os.path.getsize(path) < MIN_SIZE:
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
        for i, f in enumerate(frames):
            if f.width > MAX_W:
                r = MAX_W / f.width
                frames[i] = f.resize((MAX_W, max(1, int(f.height * r))), Image.LANCZOS)
        out = os.path.join(IMAGES, name)
        if len(frames) > 1:
            frames[0].save(out, "WEBP", save_all=True, append_images=frames[1:],
                           quality=QUALITY, method=6, loop=getattr(im, "info", {}).get("loop", 0))
        else:
            frames[0].save(out, "WEBP" if ext == ".webp" else "JPEG",
                           quality=QUALITY, method=6,
                           **({"optimize": True} if ext != ".webp" else {}))
        return name, os.path.getsize(out)
    except Exception as e:
        return ("ERR", name, str(e)[:80])


def main():
    files = [os.path.join(IMAGES, f) for f in os.listdir(IMAGES)]
    before = sum(os.path.getsize(p) for p in files if os.path.getsize(p) >= MIN_SIZE)
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(work, p) for p in files]
        for fut in as_completed(futs):
            r = fut.result()
            if r and r[0] == "ERR":
                print("ERR", r[1], r[2], flush=True)
    after = sum(os.path.getsize(p) for p in files)
    print(f"[C3] 大图 {before/1024/1024:.0f}MB -> 总 {after/1024/1024:.0f}MB", flush=True)


if __name__ == "__main__":
    main()
