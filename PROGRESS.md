# 汉化进度（自动更新）

## 2026-08-18 任务 D：打包发布（自动执行，后续沿用）
- EXE：`dist\Helldivers2WikiCN.exe` 约 463MB（PyInstaller 96s；基线 1143 页 0 高危，未重复 GUI 冒烟，沿用 E 已验证的打包流程）
- 镜像推送：main **3667637 → 689b11b**（站点 1143 页 + 文档快照 + sync_update.py）
- 修复 `sync_update.py`：git/taskkill 输出捕获改为 utf-8 + errors=replace，避免 GBK 解码告警
- 用户约定：之后管线跑完**自动执行打包 + 推送**，不再逐次确认

## 2026-08-18 任务 D：最终验收（增量管线跑通）
- 执行 `python sync_update.py`：真实增量发现 5 个新增/变更页（Biomes、Castellan's Creed Legendary Warbond、Gazer Spire、Hydrobius - Void、Illuminate）→ 只重渲染 5 页（缓存命中其余）→ 校验 **176,715 个链接全绿、1143 页 0 高危/0 中危/0 低危**
- 补拉 3 张原站新图（Illuminate_Gazer_Spire 等，wiki API imageinfo 解析 thumburl）
- 当前本地 site_final：**1143 页 / 8,169 图 / missing_images 165 条**；未打包、未推送，线上镜像保持 E 的 `3667637`

## 2026-08-18 通知：kimi_agent 已修复（任务 B）
- 完成检测：出现 `===回答完毕===` 立即返回；回答提取不受虚拟列表抖动影响（复杂问题 435–645s 均完整取回）
- 会话管理：默认每次新开会话，成功后自动删除 Kimi 侧对话（保留 `--keep-conversation` 选项）
- 给 Kimi 的镜像站链接必须完整 URL（`https://a-creep.github.io/helldivers-wiki-cn/...`），kimi_recheck3/4.txt 已改好
- 其他任务可直接放心调用 `kimi_agent.py` / `kimi_help.py`

## 2026-08-18 任务 E：站点渲染质量巡检（全站修复轮）
- **删除图集/媒体章节**：词条页"图集 / Gallery / Media"整节图库（h2/h3 级，含 gallery 网格）全站删除，保留"变体"小图库；删除边界不越过 `</main>`（修复过 Durgen_Battles 尾标签被吞的截断问题）。逻辑写入 `build_site.py` 与 `apply_zh_terms.py` 双保险。
- **术语表扩充**（`apply_zh_terms.py`）：Push Force→推力、Demo Force→爆破力、Spread→散射、Sway→晃动、Weapon Level→武器等级、Spare Magazines/Spare Mags→备用弹匣、Starting Magazines→初始弹匣、Mags from Supply→补给弹匣数、ROUNDS→发、START MAGS/MAX MAGS→初始/最大弹匣、FULL/PARTIAL 换弹→完整/部分换弹、ZOOM→变焦、Medals→奖章、Front/Side/Rear→正面/侧面/后部、Yes/No/None→是/否/无、ExDR→爆炸抗性 等。
- **病句修复**：`the <b>X</b> is a/an 中文` → `X 是 中文`（覆盖 `<p>`/infobox 描述/带链接与图标变体），67 页机翻病句清零。
- **模板残留清理**（`build_site.py`）：Lua error 报错块（scribunto-error）、导航模板 ranger-meta / "View or edit this template" 元信息全站移除。
- **验收基线（当前）**：1141 页，高危 0 / 中危 0 / 低危 0；`fix_broken_pages.py --dry-run` 0 坏页；`verify_links.py` 链接全部正常（176,541 个，页面去图集后引用减少）；`missing_images.txt` 现 162 条（随构建重写）。
- **EXE 与镜像**：`dist\Helldivers2WikiCN.exe` 重新打包（约 494MB），冒烟通过（index 正常加载、窗口标题"绝地潜兵2 中文百科"）；镜像已推 GitHub `main`（commit 3667637）。

## 2026-08-18 通知：给 Kimi 的站点链接规范
- 凡交给 Kimi 的镜像站页面引用必须写**完整 URL**（`https://a-creep.github.io/helldivers-wiki-cn/...`），禁止相对路径（`categories/xxx.html`、`pages/xxx.html`、`index.html`）——Kimi 会把裸路径当可访问链接跳转并误判"搜索失败/内容缺失"
- 已自查：`kimi_review_new.txt` / `kimi_recheck*.txt` 提问清单中的站点链接均为完整 URL；`同步与打包指南.md` 已新增第 9 节规范；`kimi_question.txt` 已注明其中路径为代码/本地路径非线上链接

## 2026-08-18 任务 D：增量同步与工程文档（项目更名"绝地潜兵2 中文百科"）
- **新增** `sync_update.py` 一键增量同步：检测变更页（revid 对比）→ 删变更页缓存行 → build_site 只重渲染变更页 → strip → terms → index → verify → validate → 可选打包/镜像推送
- **新增** `同步与打包指南.md`：完整管线与耗时、增量流程、robocopy 镜像同步、git 推送（7890 代理）、FAQ 速查
- **README/PROGRESS 补全**：项目名统一为"绝地潜兵2 中文百科"；补充目录结构、快速上手、产物说明
- 脚本行为：无变更时秒级退出；`--invalidate 标题` 可强制重渲染单页；`--package`/`--push`/`--all` 走完整发布
- 打包仍以 `Helldivers2WikiCN.spec` 为准（数据 `output_zh/site_final`；注意 build_exe.ps1 的 add-data 是旧路径）
- **实测**：真实增量同步发现 31 个变更页 → 只重渲染 20 页（缓存命中其余）→ 校验 353,723 链接全绿、高危 0
- **补拉图片**：变更页新增引用 9 张原站新图（wiki API imageinfo 解析 thumburl 下载），已补入 site/site_final 图片目录
- **注意**：期间发现另一会话并发跑 `apply_zh_terms.py` 曾短暂造成"页面截断"假象；构建管线应单会话串行执行

## 2026-08-17 词条页布局规范（wiki.gg 风格）已落地
- 双栏：正文流式 + 右侧固定 300px infobox（float:right，金 #d4a017 标题栏）
- infobox：渲染图 ≤150×180、键值紧凑、小图标 16px、分区小标题条
- 结构/攻击表：table-layout:fixed、表头汉化（部位/生命值/护甲值/位置/耐久/主血量占比）、图 ≤70px
- 武器配置：双栏卡片、图 ≤180×120、紧凑属性表
- 导航模板 ranger/navbox：显示为可折叠深色框、金左边框、图标 ≤20px、密集链接
- 全局图片兜底 + 分区上限；1920×1080 无横向滚动（scrollW==clientW 验证）
- 产物：`dist/Helldivers2WikiCN.exe`（462MB，窗口验证正常）

## 2026-08-17 汉化推进（Kimi 批量）
- 已翻译：13,290 / 50,057（26.6%），待译 35,866
- 新增：敌人/武器/战备等 keep 页已全部人工翻完；本轮通过 Kimi 网页批量再导入 ~671 条（补丁/机制短文本）
- 工具：`translate_batch.py`（按 2.5 万字符分批 -> kimi_agent 提问 -> read_last_answer 抓取 -> parse -> import）
- 已知限制：Kimi 网页自动提取不稳定（偶发抓空/会话跳转），单批建议 ≤300 条，失败会自动暂停不插话
- 剩余 3.5 万条（多为叙事/设置/补丁长文）量大，后续可继续分批跑

## 2026-08-17 UI 终版（Kimi 多轮评审后）
- **产物**：`dist/Helldivers2WikiCN.exe`（约 462MB，窗口验证正常）
- 已修复：战略指令箭头图标 26px、派系图标限宽、正文大图 ≤720px、Attack Data/Passive 报错块删除、英文 navbox/ranger 导航模板隐藏、infobox 字段术语扩充、任务页/哨戒炮标题中文、搜索纵向列表+高亮+分类筛选、更新日志摘要+默认展开、全站导航统一、链接 20 万+ 全绿

## 2026-08-17 UI 优化轮（Kimi 三组评审后）
- **产物**：`dist/Helldivers2WikiCN.exe`（约 504MB，窗口验证正常）
- 首页搜索：纵向列表 + 关键词高亮 + 分类筛选 Tab + 空状态提示
- 分类索引页：卡片缩略图（infobox 主图，跳过占位/fallback 图标）+ 首字母色块占位 + 筛选标签 + 响应式列数
- 词条页：infobox 图片限宽、行高压缩、隐藏重复 druid 标题、TOC 样式
- 更新日志：摘要显示更新日期、默认展开最新版、全局导航统一“更新日志 + 首页”
- 图片：三轮压缩（WebP q78→q72、宽 1280→1024），图片合计 424MB
- 链接检查：216,816 个链接全部正常（verify_links.py HTMLParser 版）
- Kimi 提问遵循：一问一等、每会话≤10 张图、尽量复用会话、优先文件/截图提问

## 2026-08-17 第三轮修复（Kimi 协助）
- **产物**：`dist/Helldivers2WikiCN.exe`（约 504MB）
- 索引页移入 `categories/`，修复 Windows 大小写不敏感覆盖词条页的问题（成就/难度/武器等打不开已修）
- 分类页改为卡片排版（缩略图 + 中文名 + 英文名）
- rewrite_html/page_template 按页面位置动态计算相对路径，修复 pages/ 下“首页”链接 404
- verify_links.py 改用 HTMLParser 全站检查，206198 个链接全部正常
- 视频（.mp4）全部移除，不下载
- HD1 清理：删除跨游戏提示块、含 HD1 的 navbox/章节、title 残留

## 离线 EXE（2026-08-17 第二轮改版）
- **产物**：`dist/Helldivers2WikiCN.exe`（单文件，约 449MB）
- **窗口**：内置 WebView2（edgechromium），无 DevTools，无广告
- **数据**：`output_zh/site_final`（战斗实用子集：1513 页 + 9120 图，598MB）
  - 汉化已实装：翻译表 -> 汉化 wikitext -> parse 渲染中文 HTML（1527 页已渲染缓存）
  - 主题：原站 Helldivers 配色（深灰黑背景 / #ffee33 黄 / #ff1980 品红 / #991A51 边框）
  - 首页：原站侧边栏四组分类（Acquisitions/Equipment/Game Mechanics/Locations）+ 中英文搜索
  - 分类索引页：每个小类生成中文索引页（enemies/weapons/stratagems/armors/...），不照搬原站英文列表页、无 HD1 分区
  - 术语汉化：apply_zh_terms.py 渲染后替换模板/UI 英文（Faction→阵营、Damage Type→伤害类型、Health→生命值…）
  - 更新日志：93 个补丁版本合并成 patch_notes.html 折叠页
  - 路径已修复：页面 CSS `../theme.css`、图片 `../images/`
  - 标题汉化：敌人/武器/护甲等核心词条中文标题（吐酸泰坦、强袭虫、AR-23 解放者…）
- **图片**：已压缩（大 PNG/GIF → WebP + 二次缩放 1280/q78），缺图 0
- **构建流程**：build_site.py（汉化渲染+缓存）→ compress2.py → generate_index_pages.py → apply_zh_terms.py → PyInstaller

## 当前统计（2026-08-18）
- 页面总数：3,225（其中重定向 1,282）；site_final 保留子集：1,143 页
- 总文本块：50,057；已翻译：13,319（锁定 901）；待翻译：35,837
- site_final 页面：1,143；图片：8,169 张（missing_images.txt 记录 165 个缺失引用，随页面更新浮动）
- 链接检查（E 图集/Media 删除后口径）：176,715 个全部正常（D 当天删除前实测为 353,723，口径不同属预期）
- 上次同步：2026-08-18（增量更新 31 页）；上次操作：sync 增量
- 已完页：敌人、武器、战略配备、护甲、近战、手雷、SEAF士兵、Major Orders of 2024（954）、Major Orders of 2025（全部）
- 进行中：Major Orders 主页面（1,486 待译，已完成 75；批次文件 game_loc/mo_main_00.txt 起）
- 下一步顺序：Major Orders 主页面 → Galactic War（1,231）→ 行星战史/Battle Log → 其余叙事页

## 已导入的翻译文件（本会话新增）
- translated_mo25_013.json（150）
- translated_mo24_000.json ~ translated_mo24_011.json（954）
- translated_mo24_gap.json（75，补齐 75–149 行缺口）
- translated_fix_82b2.json（1，修正 mo24_003 中的 hash 笔误）
- translated_mo_main_000.json（75）

## 待处理批次文件
- game_loc/mo24_pending.txt（0 剩余，全部完成）
- game_loc/mo_main_pending.txt（1486，已完成前 75，从第 75 行继续）

## 术语约定（官方对齐）
- Major Order=重要指令；Stratagem=战略配备；Hellpod=绝地喷射舱
- 终结族=Terminid；机器人=Automaton；光能者=Illuminate；生化人=Cyborg；无票者=Voteless
- 阴霾=Gloom（加引号）；暗液体=Dark Fluid；暗物质=Dark Energy；711元素=E-711
- 民主空间站=DSS；超级拓殖地=Supercolony；收复行动=The Reclamation；快速拆解行动=Operation Swift Disassembly
- 日期格式：2184年9月12日

## 工具
- export_pending.py <LIKE模式> <输出>：导出待译清单（context\tsource\thash）
- check_batch.py <批次文件>：检查某批次剩余待译
- overlap.py <批次文件>：检查是否与已译文本重复
- q.py <SQL> [limit]：查询数据库
