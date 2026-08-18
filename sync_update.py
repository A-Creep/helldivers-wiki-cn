#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""绝地潜兵2 中文百科 —— 一键增量同步脚本（任务 D）

流程：
    检测变更页（wiki_extractor sync，按 revid 对比）
    → 删除变更页渲染缓存（zh_cache.jsonl）
    → build_site.py 只重渲染变更页（其余命中缓存）
    → strip_hd1.py → apply_zh_terms.py → generate_index_pages.py
    → verify_links.py → validate_site.py
    → [--package 打包离线 EXE] → [--push 镜像同步 + GitHub 推送]

默认行为（无额外参数）：
    联网增量同步 + 增量重建 + 链接检查 + 健康度校验；
    无变更时秒级退出，不做重建/打包/推送。

联网与 git push 默认走代理 http://127.0.0.1:7890（本机 hosts 被
Watt Toolkit 改过，直连 GitHub 会 502/CONNECT 404）。
"""

import argparse
import json
import os
import re
import sqlite3
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
SITE_FINAL = ROOT / "output_zh" / "site_final"
CACHE_FILE = SITE_FINAL / "zh_cache.jsonl"
PAGES_DIR = SITE_FINAL / "pages"
DEFAULT_MIRROR = Path("G:/Codex项目/helldivers-wiki-mirror")
DEFAULT_PROXY = "http://127.0.0.1:7890"
GIT_NAME = "A-Creep"
GIT_EMAIL = "A-Creep@users.noreply.github.com"


# ---------------------------------------------------------------- 工具函数

def run(label, cmd, cwd=ROOT, allow_fail=False):
    """运行子进程并透传输出；失败时默认终止整个流程。"""
    t0 = time.time()
    print(f"\n[{label}] 执行: {cmd[0]} {' '.join(str(c) for c in cmd[1:])}")
    proc = subprocess.run([str(c) for c in cmd], cwd=str(cwd))
    cost = time.time() - t0
    if proc.returncode != 0 and not allow_fail:
        print(f"[{label}] 失败（退出码 {proc.returncode}，耗时 {cost:.0f}s）")
        raise SystemExit(1)
    print(f"[{label}] 完成（退出码 {proc.returncode}，耗时 {cost:.0f}s）")
    return proc.returncode


def proxy_alive(proxy_url):
    try:
        u = urlparse(proxy_url)
        host = u.hostname or "127.0.0.1"
        port = u.port or 7890
        with socket.create_connection((host, port), timeout=3):
            return True
    except Exception:
        return False


def apply_proxy(proxy_url):
    """按进程设置代理环境变量，requests / urllib 会自动读取。"""
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url
    os.environ["NO_PROXY"] = os.environ.get("NO_PROXY", "localhost,127.0.0.1")
    print(f"[Proxy] 本进程代理: {proxy_url}")


def step_proxy(args):
    if args.no_proxy:
        print("[Proxy] --no-proxy：直连，不走代理")
        return
    if proxy_alive(args.proxy):
        apply_proxy(args.proxy)
    else:
        print(f"[Proxy] 警告: 代理 {args.proxy} 未开放。")
        print("[Proxy] 如需访问 GitHub，请先启动 Clash：")
        print('        Start-Process "G:\\桌面文件\\Clash\\Clash for Windows.exe"')
        print("[Proxy] 继续执行（访问 wiki.gg 可能直连可用，git push 会失败）")


# ---------------------------------------------------------------- 同步

def step_sync(args):
    """增量同步，返回 (changed, ran_sync)。
    changed=None 表示全量重建（--force）；changed=[] 表示无变更。
    """
    if args.skip_sync:
        print("[Sync] --skip-sync：跳过联网同步，按现有 DB/缓存重建")
        return (list(args.invalidate), False)

    sys.path.insert(0, str(ROOT))
    from wiki_extractor import (CONFIG, ExclusionBuilder, SyncEngine,
                                TranslationDB, WikiClient, load_config_file)

    load_config_file()  # 读取 config.json（已 chdir 到项目根）
    db = TranslationDB(CONFIG["db_path"])
    client = WikiClient(CONFIG["wiki_api"], delay=CONFIG["request_delay"])

    # 兼容 wiki_extractor.upsert_page 的 ON CONFLICT(pageid) 缺陷：
    # 同名页不同 pageid（或重命名页）会触发 UNIQUE(title) 冲突。
    # 这里在运行时替换为 title 优先的 upsert，不改动 wiki_extractor.py。
    def safe_upsert(page):
        try:
            db.conn.execute("""
                INSERT INTO pages (pageid, title, ns, revid, parentid,
                                   timestamp, content, is_redirect, last_sync)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(title) DO UPDATE SET
                    pageid=excluded.pageid, ns=excluded.ns,
                    revid=excluded.revid, parentid=excluded.parentid,
                    timestamp=excluded.timestamp, content=excluded.content,
                    is_redirect=excluded.is_redirect,
                    last_sync=excluded.last_sync
            """, (page.pageid, page.title, page.ns, page.revid, page.parentid,
                  page.timestamp, page.content, int(page.is_redirect)))
        except sqlite3.IntegrityError:
            # 重命名页（同 pageid 不同 title）回退按 pageid 更新
            db.conn.execute("""
                UPDATE pages SET title=?, ns=?, revid=?, parentid=?,
                       timestamp=?, content=?, is_redirect=?,
                       last_sync=datetime('now')
                WHERE pageid=?
            """, (page.title, page.ns, page.revid, page.parentid,
                  page.timestamp, page.content, int(page.is_redirect),
                  page.pageid))

    db.upsert_page = safe_upsert

    if args.refresh_excludes:
        print("[Sync] 重建一代内容排除列表 ...")
        n_cat, n_page = ExclusionBuilder(client, db).build()
        print(f"[Sync] 一代分类 {n_cat} 个，排除页面 {n_page} 个")

    changed = []
    if args.force:
        print("[Sync] --force：全部页面视为变更，全量重建")
        SyncEngine(client, db).sync_all(
            namespace=CONFIG.get("namespace", 0), force=True)
        db.conn.close()
        return (None, True)

    # 拦截 get_changed_pages，记录本次变更页标题
    orig_get_changed = db.get_changed_pages

    def capture(remote_revids):
        titles = orig_get_changed(remote_revids)
        changed.extend(titles)
        return titles

    db.get_changed_pages = capture
    SyncEngine(client, db).sync_all(namespace=CONFIG.get("namespace", 0))
    db.conn.close()

    if args.invalidate:
        extra = [t for t in args.invalidate if t not in changed]
        if extra:
            print(f"[Sync] --invalidate 追加 {len(extra)} 个页面")
            changed.extend(extra)
    return (changed, True)


def invalidate_cache(changed):
    """删除变更页对应的渲染缓存行；changed=None 时清空缓存全量重建。"""
    if changed is None:
        if CACHE_FILE.exists() and CACHE_FILE.stat().st_size:
            CACHE_FILE.write_text("", encoding="utf-8")
            print("[Cache] 已清空渲染缓存（全量重建）")
        return
    if not changed or not CACHE_FILE.exists():
        print("[Cache] 无缓存需删除")
        return

    bad = set(changed)
    tmp = CACHE_FILE.with_name("zh_cache.jsonl.tmp")
    removed = 0
    total = 0
    with open(CACHE_FILE, encoding="utf-8") as fin, \
            open(tmp, "w", encoding="utf-8") as fout:
        for line in fin:
            total += 1
            try:
                title = json.loads(line).get("t")
            except Exception:
                title = None
            if title in bad:
                removed += 1
                continue
            fout.write(line)
    if removed:
        os.replace(tmp, CACHE_FILE)
        print(f"[Cache] 已删除 {removed}/{total} 条变更页缓存")
    else:
        tmp.unlink(missing_ok=True)
        print(f"[Cache] 缓存 {total} 条，变更页均不在缓存中（新增页会自动渲染）")


# ---------------------------------------------------------------- 重建

def step_build():
    run("build_site", [sys.executable, "build_site.py"])


def step_strip():
    run("strip_hd1", [sys.executable, "strip_hd1.py"])


def step_terms():
    run("apply_zh_terms", [sys.executable, "apply_zh_terms.py"])


def step_lead_check():
    """重建后引导句残留复核（防回退）。

    apply_zh_terms 是渲染后处理（改 pages/*.html），不写回 zh_cache.jsonl；
    build_site 重建页面时会从缓存覆盖这些修改，若 apply_zh_terms 某次未命中，
    引导句会回退为英文残留（实测 Drum_Magazine 回退）。这里在 terms 后扫描
    LEAD_PAGE_FIXES 精确映射的页面是否仍含期望中文引导句；发现缺失先尝试
    单文件重跑 apply_zh_terms 自动修复（全量 terms 偶发未命中的兜底），
    修复后复核仍缺失才终止发布。
    """
    try:
        sys.path.insert(0, str(ROOT))
        from apply_zh_terms import LEAD_PAGE_FIXES, apply_file
    except Exception as e:
        print(f"[LeadCheck] 无法读取 LEAD_PAGE_FIXES，跳过复核: {e}")
        return

    def detect():
        out = []
        for fname, fix in LEAD_PAGE_FIXES.items():
            path = PAGES_DIR / fname
            if not path.exists():
                continue
            html = path.read_text(encoding="utf-8", errors="replace")
            plain = re.sub(r"<[^>]+>", "", fix)
            expect = plain.strip()[:12]
            if expect and expect not in html:
                out.append((fname, expect))
        return out

    hits = detect()
    if hits:
        print(f"[LeadCheck] 检测到 {len(hits)} 个 LEAD 页面引导句回退，"
              "尝试单文件重跑 apply_zh_terms 自动修复 ...")
        for fname, _ in hits:
            path = PAGES_DIR / fname
            if path.exists():
                try:
                    apply_file(str(path))
                except Exception as e:
                    print(f"[LeadCheck] 单文件修复失败 {fname}: {e}")
        hits = detect()
    if hits:
        print(f"[LeadCheck] 检测到 {len(hits)} 个 LEAD 页面引导句回退（期望中文句缺失）：")
        for f, exp in hits[:30]:
            print(f"   - {f} | 期望含「{exp}」")
        print("[LeadCheck] 请重跑 `python apply_zh_terms.py` 或 "
              "`python sync_update.py --skip-sync --invalidate <标题>` 后重新验证；"
              "流程已终止，未打包/未推送。")
        raise SystemExit(1)
    print(f"[LeadCheck] 引导句残留复核通过（LEAD_PAGE_FIXES {len(LEAD_PAGE_FIXES)} 页均命中中文引导句）")


def step_index():
    run("generate_index_pages", [sys.executable, "generate_index_pages.py"])


def step_verify():
    run("verify_links", [sys.executable, "verify_links.py"])


def step_validate():
    run("validate_site", [sys.executable, "validate_site.py", "--report"])


# ---------------------------------------------------------------- 打包

def kill_running_exe():
    """打包前结束占用 dist EXE 的进程（best-effort）。"""
    proc = subprocess.run(
        ["taskkill", "/IM", "Helldivers2WikiCN.exe", "/F"],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        print("[Package] 已结束正在运行的 Helldivers2WikiCN.exe")
    elif "not found" in out.lower():
        print("[Package] 无运行中的 Helldivers2WikiCN.exe")
    else:
        print(f"[Package] taskkill 提示: {out.strip()[:120]}")


def step_package():
    kill_running_exe()
    run("PyInstaller", [sys.executable, "-m", "PyInstaller",
                        "--noconfirm", "--clean", "Helldivers2WikiCN.spec"])
    exe = ROOT / "dist" / "Helldivers2WikiCN.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / 1024 / 1024
        print(f"[Package] 产物: {exe}（{size_mb:.0f}MB）")
    else:
        print("[Package] 警告: 未找到 dist/Helldivers2WikiCN.exe")


# ---------------------------------------------------------------- 镜像推送

def sync_mirror(mirror):
    """robocopy 增量同步 site_final → 镜像仓库。
    只对镜像仓管理的站点目录（pages/images/categories）做 /MIR 镜像，
    顶层再拷贝站点文件；不使用根目录 /MIR，避免删除镜像仓保留的
    README/PROGRESS/辅助脚本/.gitignore。
    """
    mirror = Path(mirror)
    print(f"[Mirror] 同步 {SITE_FINAL} → {mirror}")
    sub_dirs = ["pages", "images", "categories"]
    for name in sub_dirs:
        src = SITE_FINAL / name
        dst = mirror / name
        if not src.exists():
            print(f"[Mirror] 跳过不存在目录: {src}")
            continue
        code = run("robocopy", ["robocopy", src, dst, "/MIR", "/XD", ".git",
                                "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
                                "/R:2", "/W:2"], cwd=ROOT, allow_fail=True)
        if code >= 8:
            print(f"[Mirror] robocopy {name} 失败（退出码 {code}）")
            raise SystemExit(1)
    top_files = ["index.html", "patch_notes.html", "theme.css",
                 "titles_cn.json", "missing_images.txt"]
    code = run("robocopy", ["robocopy", SITE_FINAL, mirror, *top_files,
                            "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
                            "/R:2", "/W:2"], cwd=ROOT, allow_fail=True)
    if code >= 8:
        print(f"[Mirror] robocopy 顶层文件失败（退出码 {code}）")
        raise SystemExit(1)
    print("[Mirror] 站点文件同步完成")


def ensure_git_identity(mirror):
    for key, value in (("user.name", GIT_NAME), ("user.email", GIT_EMAIL)):
        p = subprocess.run(["git", "config", "--get", key], cwd=str(mirror),
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode != 0:
            subprocess.run(["git", "config", key, value], cwd=str(mirror),
                           check=True)
            print(f"[Git] 已设置仓库级 {key} = {value}")


def git_push(args, mirror, changed_note):
    mirror = Path(mirror)
    ensure_git_identity(mirror)
    run("git add", ["git", "add", "-A"], cwd=mirror)

    message = args.message or f"站点{changed_note} {time.strftime('%Y-%m-%d')}"
    proc = subprocess.run(
        ["git", "commit", "-m", message], cwd=str(mirror),
        capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and "nothing to commit" in out.lower():
        print("[Git] 无内容可提交，跳过推送")
        return
    if proc.returncode != 0:
        print(out[-2000:])
        raise SystemExit(f"[Git] commit 失败（退出码 {proc.returncode}）")
    print(f"[Git] 已提交: {message}")

    if args.no_proxy:
        run("git push", ["git", "push", "origin", "main"], cwd=mirror)
    else:
        run("git push", ["git", "-c", f"http.proxy={args.proxy}",
                         "-c", f"https.proxy={args.proxy}",
                         "push", "origin", "main"], cwd=mirror)
    print("[Git] 推送完成（origin: main）")


def step_push(args, changed_note):
    sync_mirror(args.mirror)
    git_push(args, args.mirror, changed_note)


# ---------------------------------------------------------------- 主流程

def build_parser():
    ap = argparse.ArgumentParser(
        description="绝地潜兵2 中文百科 一键增量同步（检测变更→重建→验证→打包→推送）")
    ap.add_argument("--skip-sync", action="store_true",
                    help="不联网同步，仅按现有 DB/缓存重建（离线修复/测试用）")
    ap.add_argument("--force", action="store_true",
                    help="强制全量同步并清空缓存全量重建")
    ap.add_argument("--refresh-excludes", action="store_true",
                    help="同步前重建一代内容排除列表")
    ap.add_argument("--invalidate", action="append", default=[],
                    help="强制重渲染指定页面标题（可重复），无需等变更")
    ap.add_argument("--no-verify", action="store_true", help="跳过链接检查")
    ap.add_argument("--no-validate", action="store_true", help="跳过健康度校验")
    ap.add_argument("--package", action="store_true",
                    help="校验通过后打包离线 EXE（PyInstaller，约 5-10 分钟）")
    ap.add_argument("--push", action="store_true",
                    help="镜像同步到 helldivers-wiki-mirror 并推 GitHub（走代理）")
    ap.add_argument("--all", dest="all_steps", action="store_true",
                    help="等价于 --package --push")
    ap.add_argument("--mirror", default=str(DEFAULT_MIRROR),
                    help=f"镜像仓库路径（默认 {DEFAULT_MIRROR}）")
    ap.add_argument("--proxy", default=DEFAULT_PROXY,
                    help=f"代理地址（默认 {DEFAULT_PROXY}）")
    ap.add_argument("--no-proxy", action="store_true", help="不走代理直连")
    ap.add_argument("--message", help="git 提交信息（默认自动生成）")
    return ap


def main():
    ap = build_parser()
    args = ap.parse_args()
    os.chdir(ROOT)
    t_start = time.time()

    print("=" * 70)
    print("绝地潜兵2 中文百科 · 一键增量同步")
    print("=" * 70)

    step_proxy(args)

    # 1. 同步并检测变更
    changed, ran_sync = step_sync(args)

    # 2. 无变更快速退出（无 --force/--invalidate/--skip-sync 时）
    if (ran_sync and not changed and not args.invalidate):
        print(f"\n[Sync] 无变更，跳过重建/打包/推送（共耗时 {time.time()-t_start:.0f}s）")
        return 0

    if changed is None:
        changed_note = "全量重建"
    else:
        changed_note = f"增量同步（{len(changed)} 页）"
        print(f"\n[变更] {len(changed)} 个页面:")
        for t in changed[:50]:
            print("   -", t)
        if len(changed) > 50:
            print(f"   ... 其余 {len(changed)-50} 个省略")

    # 3. 删缓存 → 重建
    invalidate_cache(changed)
    step_build()
    step_strip()
    step_terms()
    step_lead_check()
    step_index()

    # 4. 验证
    if not args.no_verify:
        step_verify()
    else:
        print("[Verify] --no-verify：跳过链接检查")
    if not args.no_validate:
        step_validate()
    else:
        print("[Validate] --no-validate：跳过健康度校验")

    # 5. 打包 / 推送（可选）
    do_package = args.package or args.all_steps
    do_push = args.push or args.all_steps
    if do_package:
        step_package()
    if do_push:
        step_push(args, changed_note)

    print(f"\n[完成] 全部步骤结束（共耗时 {time.time()-t_start:.0f}s）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
