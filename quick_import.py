import json
import os
import re
import subprocess
import sys

sys.path.insert(0, ".")
from translate_batch import parse_answer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
KIMI_DIR = r"G:\Codex项目\kimi-agent"


def grab(name):
    r = subprocess.run(
        [sys.executable, os.path.join(KIMI_DIR, "read_last_answer.py"),
         "--name", name],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300)
    out = r.stdout
    marker = "=== 全部消息合并 ==="
    if marker in out:
        return out.split(marker, 1)[1]
    return ""


def main():
    answer = grab("绝地潜兵术语翻译")
    parsed = parse_answer(answer)
    print("解析条数:", len(parsed))
    if parsed:
        tp = os.path.join(ROOT, "kimi_translate", "grabbed.json")
        with open(tp, "w", encoding="utf-8") as fp:
            json.dump(parsed, fp, ensure_ascii=False)
        subprocess.run([sys.executable, os.path.join(ROOT, "wiki_extractor.py"),
                        "import", tp], check=True)


if __name__ == "__main__":
    main()
