import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "output_zh", "site_final")
IMAGES = os.path.join(SITE, "images")
MAX_W = 1280
QUALITY = 78


def collect_refs():
    refs = set()
    for dp, _dn, fs in os.walk(SITE):
        for f in fs:
            if not f.endswith(".html"):
                continue
            h = open(os.path.join(dp, f), encoding="utf-8").read()
            refs |= set(re.findall(r'(?:src|href)="\.\.?/images/([^"#?]+)', h))
            for m in re.finditer(r'srcset="([^"]+)"', h):
                for cand in m.group(1).split(","):
                    cand = cand.strip()
                    mm = re.match(r"\.\.?/images/([^ ]+)", cand)
                    if mm:
                        refs.add(mm.group(1))
    return refs


def shrink(path):
    name = os.path.basename(path)
    try:
        ext = os.path.splitext(name)[1].lower()
        if ext not in (".webp", ".jpg", ".jpeg"):
            return None
        im = Image.open(path)
        w, hgt = im.size
        if w <= MAX_W:
            return None
        r = MAX_W / w
        im2 = im.convert("RGB").resize((MAX_W, max(1, int(hgt * r))), Image.LANCZOS)
        im2.save(path, "WEBP" if ext == ".webp" else "JPEG", quality=QUALITY, method=6,
                 **({"optimize": True} if ext != ".webp" else {}))
        return name, w, os.path.getsize(path)
    except Exception as e:
        return ("ERR", name, str(e)[:80])


def main():
    refs = collect_refs()
    print("引用图片数:", len(refs))
    removed = 0
    freed = 0
    for f in os.listdir(IMAGES):
        if f not in refs:
            p = os.path.join(IMAGES, f)
            freed += os.path.getsize(p)
            os.remove(p)
            removed += 1
    print(f"删除未引用图 {removed} 张，释放 {freed/1024/1024:.0f}MB")

    files = [os.path.join(IMAGES, f) for f in os.listdir(IMAGES)]
    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(shrink, p) for p in files]
        for fut in as_completed(futs):
            r = fut.result()
            if r and r[0] == "ERR":
                print("ERR", r[1], r[2], flush=True)
            done += 1
    total = sum(os.path.getsize(os.path.join(IMAGES, f)) for f in os.listdir(IMAGES))
    print(f"[C4] 完成，图片共 {total/1024/1024:.0f}MB")


if __name__ == "__main__":
    main()
