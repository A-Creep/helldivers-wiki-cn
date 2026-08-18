# 绝地潜兵2 中文百科（Helldivers 2 中文 Wiki）

把 [helldivers.wiki.gg](https://helldivers.wiki.gg) 的 **Helldivers 2 英文内容**同步到本地 → 提取待翻译文本（保留 wikitext 结构）→ 人工/Kimi 翻译 → 回填生成汉化版 → 构建离线中文站点 → 打包离线 EXE 阅读器 → 发布镜像仓库。

自动排除：Helldivers 1 一代内容（分类树 + 标题启发式）、非英语子页（/ru /zh /de 等）。

## 快速开始（10 分钟上手）

```powershell
cd G:\Codex项目\helldivers-wiki-localizer

# 1. 看当前状态（页面数/翻译进度/上次同步）
python wiki_extractor.py stats

# 2. 日常增量：检测原站变更 → 只重渲染变更页 → 链接检查 → 健康度校验
python sync_update.py

# 3. 全量发布：上面的流程 + 打包 EXE + 镜像同步推 GitHub（走 7890 代理）
python sync_update.py --all
```

联网/推 GitHub 必须走代理 `http://127.0.0.1:7890`（Clash for Windows；本机 hosts 被 Watt Toolkit 改过，直连推送会 502）。完整流程与常见问题见 [同步与打包指南.md](同步与打包指南.md)。

## 目录结构

| 路径/文件 | 作用 |
|-----------|------|
| `wiki_extractor.py` | 主工具（同步/提取/导入/构建/统计，含 `ask-kimi` 求助入口） |
| `sync_update.py` | **一键增量同步**：检测变更页→删缓存→重建→验证→打包→镜像推送 |
| `config.json` | 配置（API 地址、数据库路径、请求延迟等） |
| `wiki_local.db` | SQLite 数据库（页面 + 翻译记忆库） |
| `glossary.json` | 术语表：命中文本自动锁定翻译 |
| `untranslated.json` / `untranslated.csv` | 待翻译文本（JSON / Excel 友好版） |
| `output_zh/site` | 原站镜像（渲染 HTML + 原始图片，build_mirror.py 产物） |
| `output_zh/site_final` | **离线中文站点**（约 1146 页 + 汉化缓存 `zh_cache.jsonl`） |
| `dist/Helldivers2WikiCN.exe` | 离线阅读器（内置 WebView2 窗口，约 487MB） |
| `同步与打包指南.md` | 完整管线、增量流程、镜像推送、FAQ |
| `PROGRESS.md` | 版本与进度记录 |

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

# 站点构建管线（见 同步与打包指南.md）
python build_site.py            # 汉化渲染约 1146 页（断点缓存 zh_cache.jsonl）
python strip_hd1.py             # 清除 HD1 残留块/navbox/章节
python apply_zh_terms.py        # 渲染后术语/UI 英文替换
python generate_index_pages.py  # 重建分类索引页 + 更新首页 NAV
python verify_links.py          # 全站链接完整性检查
python validate_site.py --report # 健康度扫描（高危必须为 0）

# 打包 / 镜像推送
python -m PyInstaller --noconfirm --clean Helldivers2WikiCN.spec
python sync_update.py --push    # 镜像同步 + git 推送（走代理）
```

## 增量同步（原站内容变更后）

```bash
python sync_update.py
```

原理：`wiki_extractor.py sync` 按 **revid 对比**找出新增/变更页 → 删除这些页在 `zh_cache.jsonl` 的渲染缓存 → `build_site.py` 只重渲染缺失缓存页（其余命中缓存）→ strip/terms/index → verify/validate。无变更时秒级退出。

翻译提取是独立环节：`python wiki_extractor.py extract --changed-only` 只提取新增/变更文本，已有翻译不受影响。

## 翻译流程

1. 用 Excel 打开 `untranslated.csv`，在 `translated` 列填写译文（保留 `hash` 不动）。
2. 保存后交回（或转成 translated.json，格式见下）。
3. 导入：`python wiki_extractor.py import translated.json`
4. 重建站点：`python sync_update.py --skip-sync`

translated.json 格式：

```json
[
  { "hash": "a1b2c3d4e5f67890", "translated": "战略配备", "status": "translated" }
]
```

## 离线阅读器 EXE

- 数据：`output_zh/site_final`（汉化离线站点）
- 打包：`python -m PyInstaller --noconfirm --clean Helldivers2WikiCN.spec`
- 产物：`dist/Helldivers2WikiCN.exe`（约 487MB，双击即用；首次启动解压约 20~30 秒）
- 打包前若提示 EXE 被占用：`taskkill /IM Helldivers2WikiCN.exe /F`

## 发布镜像仓库

`G:\Codex项目\helldivers-wiki-mirror`（origin = `https://github.com/A-Creep/helldivers-wiki-cn.git`）是发布镜像：站点根目录 + 项目文档快照。同步方式见 [同步与打包指南.md](同步与打包指南.md) 第 5 节，或直接：

```powershell
python sync_update.py --push
```

给 Kimi 等外部工具引用站点页面时，一律使用完整 URL（如 `https://a-creep.github.io/helldivers-wiki-cn/categories/stratagems.html`），禁止写 `categories/stratagems.html` 这类相对路径——Kimi 会当链接直接跳转并误判为内容缺失。

## 相关文档

- [同步与打包指南.md](同步与打包指南.md)：完整管线/耗时、增量同步、镜像推送、常见问题速查
- [PROGRESS.md](PROGRESS.md)：版本与进度记录
- `任务分解/`：各子任务说明（A 翻译术语 / B kimi_agent / D 增量同步与工程文档 / E 站点渲染质量巡检）
