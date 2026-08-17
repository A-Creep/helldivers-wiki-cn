# Helldivers 2（绝地潜兵2）Wiki 本地化工具

把 helldivers.wiki.gg 的 **Helldivers 2 英文内容**同步到本地 → 提取待翻译文本（保留 wikitext
结构）→ 人工翻译 → 回填生成汉化版 → 制作离线 EXE 阅读器。

自动排除：Helldivers 1 一代内容（分类树 + 标题启发式）、非英语子页（/ru /zh /de 等）。

## 文件说明

| 文件 | 作用 |
|------|------|
| `wiki_extractor.py` | 主工具（同步/提取/导入/构建/统计） |
| `config.json` | 配置（API 地址、数据库路径、延迟等） |
| `glossary.json` | 术语表：匹配的文本自动锁定翻译，不重复翻译 |
| `wiki_local.db` | SQLite 数据库（页面 + 翻译记忆库） |
| `untranslated.json` | 待翻译文本（53,400 条） |
| `untranslated.csv` | 同上，Excel 友好版（在 translated 列填写译文） |
| `output_zh/*.wiki.txt` | 构建出的汉化 wikitext |

## 常用命令

```bash
python wiki_extractor.py init                        # 初始化数据库
python wiki_extractor.py sync --refresh-excludes     # 重建一代排除表 + 全量同步
python wiki_extractor.py sync                        # 增量同步（只拉变更页）
python wiki_extractor.py extract                     # 提取待译文本 → untranslated.json
python wiki_extractor.py extract --changed-only      # 只提取变更页面
python wiki_extractor.py extract --format csv        # 导出 CSV（Excel 翻译用）
python wiki_extractor.py import translated.json      # 导入翻译
python wiki_extractor.py build                       # 生成汉化 wikitext
python wiki_extractor.py stats                       # 统计（页面/文本块/翻译进度）
python wiki_extractor.py update                      # 一键：增量同步+提取新增+构建
```

## 翻译流程

1. 用 Excel 打开 `untranslated.csv`，在 `translated` 列填写译文（保留 `hash` 不动）。
2. 保存后交回（或自行转成 translated.json，格式见下）。
3. 导入：`python wiki_extractor.py import translated.json`
4. 构建 + 制作离线 EXE 阅读器（下一步）。

translated.json 格式：

```json
[
  { "hash": "a1b2c3d4e5f67890", "translated": "战略配备", "status": "translated" }
]
```

## 增量更新（网站内容变更后）

```bash
python wiki_extractor.py sync
python wiki_extractor.py extract --changed-only
```

只会提取新增/变更文本，已有翻译不受影响。

## Phase 2：离线阅读器 EXE（已完成）

- `python build_mirror.py`：抓取文章渲染 HTML → `output_zh/site`（原站正文、去广告、图片本地化）
- `python compress_images.py`：大 PNG/GIF 转 WebP，压缩图片体积
- `python classify2.py`：按标题粗分 实用/叙事 页面，输出 keep_pages.txt / drop_pages.txt / maybe_pages.txt
- `python build_subset.py`：按确认范围裁剪出 `output_zh/site_subset`（战斗实用页 + 补丁页）
- `app.py` + PyInstaller：单文件 EXE（内置 WebView2 窗口，无 DevTools）

打包命令：
```bash
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name "Helldivers2WikiCN" `
  --add-data "output_zh/site_subset;site" `
  --hidden-import "webview.platforms.edgechromium" `
  --hidden-import "webview.platforms.winforms" `
  --collect-all clr_loader --collect-all pythonnet `
  app.py
```

产物：`dist/Helldivers2WikiCN.exe`（约 440MB，双击即用；首次启动解压约 20~30 秒）。
