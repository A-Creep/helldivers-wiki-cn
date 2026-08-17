# -*- coding: utf-8 -*-
"""离线阅读器：内置 WebView2 窗口，浏览本地镜像"""

import os
import sys

import webview


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def main():
    log_dir = os.path.dirname(os.path.abspath(sys.executable))
    log_path = os.path.join(log_dir, "app_error.log")
    def log(msg):
        try:
            with open(log_path, "a", encoding="utf-8") as fp:
                fp.write(msg + "\n")
        except Exception:
            pass
    try:
        index = resource_path(os.path.join("site", "index.html"))
        if not os.path.exists(index):
            index = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site", "index.html")
        log(f"index exists: {os.path.exists(index)} -> {index}")
        webview.create_window(
            "绝地潜兵2 离线百科（汉化版）",
            index,
            width=1440,
            height=920,
            min_size=(1024, 700),
            text_select=True,
        )
        log("window created, starting...")
        gui = os.environ.get("HD2GUI", "edgechromium")
        log(f"starting gui={gui}")
        webview.start(gui=gui)
        log("start returned")
    except Exception as e:
        import traceback
        with open(log_path, "a", encoding="utf-8") as fp:
            fp.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
