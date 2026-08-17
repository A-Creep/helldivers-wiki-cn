# 汉化进度（自动更新）

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

## 当前统计（2026-08-16）
- 总文本块：50,057；已翻译：12,619；待翻译：36,537
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
