"""用 Kimi 批量翻译剩余文本（hash<tab>source 格式，逐批上传翻译）"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, ".")
from build_site import build_keep_set

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
KIMI = r"G:\Codex项目\kimi-agent\kimi_agent.py"
KIMI_HIST = r"G:\Codex项目\kimi-agent\kimi_session\history.jsonl"
OUT = os.path.join(ROOT, "kimi_translate")
os.makedirs(OUT, exist_ok=True)


def pending_keep():
    keep = build_keep_set()
    db = sqlite3.connect(os.path.join(ROOT, "wiki_local.db"))
    rows = db.execute(
        "SELECT source_hash, source_text, page_title FROM translations "
        "WHERE page_title IN ({}) AND (translated_text IS NULL OR translated_text='')"
        " ORDER BY page_title, length(source_text) DESC".format(
            ",".join("?" * len(keep))), list(keep)).fetchall()
    return rows


def write_batch(items, path):
    with open(path, "w", encoding="utf-8") as fp:
        for h, s, _p in items:
            s = s.replace("\t", " ").replace("\n", " ").strip()
            fp.write(f"{h}\t{s}\n")


def parse_answer(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            h, zh = line.split("\t", 1)
        else:
            m = re.match(r"^([0-9a-f]{16})\s+(.*)$", line)
            if not m:
                continue
            h, zh = m.group(1), m.group(2)
        h = h.strip().lower()
        zh = zh.strip()
        if re.fullmatch(r"[0-9a-f]{16}", h) and zh and zh != "[保留原文]":
            out.append({"hash": h, "translated": zh})
    return out


def ask_kimi(batch_path, idx):
    q = (
        "请逐行翻译下面文件中的英文为简体中文（绝地潜兵2游戏术语，参考官方译名："
        "Helldivers=绝地潜兵、Terminid=终结族、Automaton=机器人、Illuminate=光能者、"
        "Stratagem=战略配备、Super Earth=超级地球、Managed Democracy=管理式民主）。"
        "每一行格式为：16位哈希<TAB>英文原文。请保持每行一个译文，输出格式完全一致："
        "哈希<TAB>中文译文。译文必须是一行，不要分点、不要解释、不要额外文字。"
        "无法翻译的专名保留原文。"
    )
    try:
        cmd = [sys.executable, KIMI, "--ask", q, "--upload", batch_path,
               "--timeout", "300", "--json"]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=400)
        lines = [json.loads(l) for l in open(KIMI_HIST, encoding="utf-8").read().splitlines()]
        last = lines[-1]
        answer = last.get("answer") or ""
        if not answer:
            print("[T] kimi_agent 未取到回答，尝试从页面抓取...", flush=True)
            r = subprocess.run(
                [sys.executable, r"G:\Codex项目\kimi-agent\read_last_answer.py",
                 "--name", "绝地潜兵术语翻译"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=420)
            out = r.stdout
            if "=== 全部消息合并 ===" in out:
                answer = out.split("=== 全部消息合并 ===", 1)[1]
        return answer
    except Exception as e:
        print(f"[T] ask_kimi 异常: {e}", flush=True)
        return ""


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    items = pending_keep()
    print(f"待翻译 keep 页条目: {len(items)}")
    if limit:
        items = items[:limit]
    idx = 0
    done_all = 0
    while items:
        batch = []
        total = 0
        while items and total < 25000:
            _h, s, _p = items[0]
            if total + len(s) > 26000 and batch:
                break
            batch.append(items.pop(0))
            total += len(s)
        idx += 1
        bp = os.path.join(OUT, f"batch_{idx:03d}.txt")
        write_batch(batch, bp)
        print(f"[T] 批次 {idx}: {len(batch)} 条 -> Kimi ...", flush=True)
        answer = ask_kimi(bp, idx)
        parsed = parse_answer(answer)
        for attempt in range(3):
            if parsed:
                break
            print(f"[T] 批次 {idx} 解析 0 条，等待 Kimi 完成后重试 ({attempt+1}/3)...", flush=True)
            time.sleep(60)
            r = subprocess.run(
                [sys.executable, r"G:\Codex项目\kimi-agent\read_last_answer.py",
                 "--name", "绝地潜兵术语翻译"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=420)
            out = r.stdout
            if "=== 全部消息合并 ===" in out:
                answer = out.split("=== 全部消息合并 ===", 1)[1]
                parsed = parse_answer(answer)
        print(f"[T] 批次 {idx}: 解析 {len(parsed)} 条", flush=True)
        if parsed:
            tp = os.path.join(OUT, f"translated_{idx:03d}.json")
            with open(tp, "w", encoding="utf-8") as fp:
                json.dump(parsed, fp, ensure_ascii=False)
            subprocess.run([sys.executable, os.path.join(ROOT, "wiki_extractor.py"),
                            "import", tp], check=True)
            done_all += len(parsed)
        else:
            print(f"[T] 批次 {idx} 连续失败，暂停等待（避免打断 Kimi）", flush=True)
            break
        with open(os.path.join(OUT, "progress.txt"), "w", encoding="utf-8") as fp:
            fp.write(f"batches={idx} done={done_all}\n")
    print(f"[T] 完成，共导入 {done_all} 条")


if __name__ == "__main__":
    main()
