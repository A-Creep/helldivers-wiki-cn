# 绝地潜兵2 离线汉化百科（Helldivers 2 离线 Wiki 汉化版）

把 helldivers.wiki.gg 的绝地潜兵2 内容本地化并打包成离线可查的百科阅读器。
本仓库同时包含：

- **静态站**（仓库根目录）：`index.html` / `pages/` / `categories/` / `images/`，可直接部署到 GitHub Pages 离线浏览
- **源码**：生成该静态站的全部 Python 脚本与主题
- **设计稿/截图**：`ui_shots/*.png`（界面截图，含长截图，供 UI 评审参考）

## 技术栈

- **抓取与解析**：Python 3.11 + MediaWiki API（`action=parse`）+ `mwparserfromhell`
- **翻译**：规则引擎 + 官方词典（`game_loc/en_cn_by_key.json`，来自游戏解包 265 个 strings JSON）+ Kimi 网页批量翻译
- **站点生成**：`build_site.py`（汉化 wikitext → parse 渲染中文 HTML → 路径重写/去广告/去视频/清 HD1）
- **主题**：纯 CSS（`site_theme.css`），wiki.gg Helldivers 深色风格（双栏：右侧固定 300px infobox + 正文高密度）
- **图片**：Pillow 压缩（WebP，宽 ≤1280，质量 72-78）
- **桌面端**：`app.py`（pywebview + EdgeChromium）→ PyInstaller 单文件 EXE
- **Kimi 辅助**：Playwright 网页自动化（`kimi_agent`，外部仓库）

## 目录结构

```
index.html / patch_notes.html / theme.css   # 首页、更新日志、主题
pages/          # 词条页（敌人/武器/装备/战略配备/任务等）
categories/     # 分类索引页（卡片网格 + 筛选）
images/         # 本地化图片（WebP，宽≤1280）
build_site.py   # 主构建：汉化渲染 + 路径重写 + 清理
apply_zh_terms.py   # 渲染后模板/UI 英文术语汉化
generate_index_pages.py  # 分类索引页生成
verify_links.py  # 全站链接完整性检查（HTMLParser）
strip_hd1.py     # 清理绝地潜兵1 相关内容
compress*.py     # 图片压缩
app.py           # 桌面阅读器入口
build_exe.ps1    # PyInstaller 打包脚本
```

## 构建流程

```bash
python build_site.py          # 生成 output_zh/site_final（含中文渲染）
python strip_hd1.py           # 清理 HD1
python apply_zh_terms.py      # 术语汉化
python generate_index_pages.py
python verify_links.py        # 全站链接检查
# 打包 EXE（Windows）：
python -m PyInstaller --onefile --windowed --name Helldivers2WikiCN --add-data "output_zh/site_final;site" app.py
```

## 设计说明（供 UI 评审）

- 双栏布局：正文流式 + 右侧固定 300px infobox（金色标题栏 #d4a017）
- 图片严格限宽：infobox 渲染图 ≤150×180、部位图 ≤60px、武器图 ≤180×120、图标 16-24px
- 表格 `table-layout: fixed`，表头已汉化（部位/生命值/护甲值/位置/耐久/主血量占比）
- 导航模板可折叠、金左边框、派系图标 ≤20px
- 1920×1080 / 1366×768 无横向滚动条
- `ui_shots/` 内为各页面长截图（敌人/武器/战略配备/护甲/任务/首页/分类）

## 在线访问

部署到 GitHub Pages 后，直接访问 Pages URL 即可浏览完整静态站（无需构建）。
