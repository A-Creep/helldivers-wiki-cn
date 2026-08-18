# 汉化进度（自动更新）

## 2026-08-19 任务 D：工程文档补全（T-D-002）
- 补全 README / PROGRESS / 同步与打包指南并刷新基线：site_final 1146 页、177,304 链接全绿、0 高危/0 中危/0 低危、EXE 487MB、missing_images 162 条
- 同步更新本地与镜像仓文档副本；T-D-001 仍阻塞于 A 入库，未跑发布管线

## 2026-08-19 任务 D：敌人分类页种族配色发布
- S #90 派单：E 的敌人分类页种族配色（#81/#84，机器人 #ff6161 / 终结族 #ffb901 / 光能族 #cd8aea，仅 enemies 分类页生效）统一发布；D 执行 `python sync_update.py --skip-sync --all` 完整管线：
  - 验收：177,304 链接全绿、1146 页 0 高危/0 中危/0 低危；enemies.html 含 faction-auto/termi/illum 三类阵营类、theme.css 三色号就位；LeadCheck 自动修复 1 页后 18 页引导句全部命中中文
  - EXE 487MB（dist\Helldivers2WikiCN.exe，打包前 taskkill 结束占用实例）；镜像 main **fc1d28e6 → bb3c221d**

## 2026-08-18 任务 D：#76 双配色主题切换收尾发布
- E 实现双主题（CSS 变量 + html.view-alt 切换，header 切换按钮 + localStorage，默认配色1 黄字/黑黄边框；配色2 紫红边框/蓝字）后，D 跑完整管线：
  - 验收：177,304 链接全绿、1146 页 0 高危/0 中危/0 低危；theme.css 双主题变量与词条页"切换配色"按钮/toggleTheme 验证通过
  - EXE 487MB；镜像 main **fdb65d5d → 86cf2563**

## 2026-08-18 任务 D：#69 附件段名术语生效收尾发布
- E #67 新增术语（Optics→瞄准镜 / Underbarrel→下挂 / Muzzle→枪口 / Choke→喉缩）后，D 执行完整管线（--skip-sync）：
  - 验收：177,304 链接全绿、1146 页 0 高危/0 中危/0 低危；10x_Sniper_Scope 面包屑实测"配件 → 瞄准镜 → 10倍狙击镜"，全站无 Optics 英文段名残留
  - EXE 487MB；镜像 main **9e05d6f5 → ce0f21d1**

## 2026-08-18 任务 D：Kimi 审阅修复收尾发布（#57 串行管线）
- D 修复：`build_site.py` drop_pat 表情词 `flex` → `\bflex\b`（消除 Reflex Sight / Reflex Sight Mk2 keep 误伤）；重跑 classify → page_cats 两附件补 type=attachment
- E 完成页面修复 + UI/UX/样式改造（引导句/返回按钮/面包屑/筛选顺序/1100px/Infobox 320px/颜色中性化/Anatomy 自适应/武器卡片网格）后，D 统一跑完整管线：
  - 验收：**177,304 链接全绿、1146 页 0 高危/0 中危/0 低危**（Reflex Sight 2 页已入站点；Drum 回退被 lead_check 自动修复）
  - EXE 486MB；镜像 main **c9249795 → c6af3614**

## 2026-08-18 任务 D：武器分类修复（S 派单 P0）+ 串行收尾发布
- 排查（S #30 派单，只读）：原站 Weapons 三组 98 武器全部在 DB（无漏收录）；根因 `page_cats.json` 42 个武器 type 为空
- P0 修复（D）：`classify_by_infobox.py` 正则支持下划线 `{{Infobox_Weapon` 与裸 `{{Weapon` 模板 → 重跑 page_cats.json → 原站 98 武器 0 空 type（weapon 36→78），params 补齐
- E P2 二级分组 + A P1 标题/词表就绪后，D 执行串行完整管线并发布：
  - 验收：177,123 链接全绿、1144 页 0 高危；weapons 分类页主要武器 53 / 次要武器 25 / 投掷武器 21 / 配件 28（子分类二级分组、官方组名）
  - EXE 485MB；镜像 main **a8004470 → 9c0acd1e**
- 加固：`sync_update.py` `step_lead_check` 支持回退自动单文件修复（Drum 回退自动修复，模拟测试通过）

## 2026-08-18 任务 D：全量重建发布（A 今日翻译生效）
- 背景：A 今日累计导入 +3,052 条翻译（translated 16,486 / pending 32,670），需重建站点生效；因导入未更新 updated_at，采用全量重建确保不漏
- 执行：清空 `zh_cache.jsonl` → 全量重渲染 1143 页（886s）→ strip → terms（首次 Drum 引导句未命中，LeadCheck 拦截；单文件重跑 apply_zh_terms 修复后二次 terms 通过）→ index → verify → validate
- 补拉 12 张全量重渲染后新引用图片（CE-64 Grenadier、PH-9 Predator 缩略图、Cape 系列、Obtruder、行星图等；直连 wiki.gg，代理当时未启动）
- 验收：**177,057 链接全绿、1143 页 0 高危/0 中危/0 低危**；EXE 484MB；镜像 main **1ac7050 → 697ecff**
- 期间发现：Clash 代理未运行（7890 不通）→ 已启动；wiki.gg 渲染/补图可直连，git push 需代理

## 2026-08-18 任务 D：引导句回退防护（响应 E #11）
- 现象：E 发现 D 重建后 Drum_Magazine 引导句回退为英文残留（缓存与 apply_zh_terms 后处理脱节：build_site 从 zh_cache.jsonl 重写页面会覆盖 terms 后处理成果）
- 改进：`sync_update.py` 新增 `step_lead_check`（terms 后、verify 前）——校验 LEAD_PAGE_FIXES 18 页均含期望中文引导句，缺失即终止发布并提示重跑 terms / 单页 invalidate；已通过回退模拟测试
- 当前本地与镜像均无回退（Drum 等 18 页引导句为中文），main = 05e5b34

## 2026-08-18 任务 D：增量验收 + 自动发布（15 页变更）
- `sync_update.py` 真实增量：15 个新增/变更页（Campaigns、Deadlands、Desert Cliffs、PH-9 Predator、Missions、Difficulty 等）→ **只重渲染 14 页**（缓存命中其余）→ 校验 **176,707 链接全绿、1143 页 0 高危/0 中危/0 低危**
- 补拉 13 张原站新图（PH-9 Predator 装甲/头盔、Hydrobius Void 行星系列、Senge 23 Void 等，wiki API imageinfo 解析 thumburl）
- EXE：`dist\Helldivers2WikiCN.exe` 约 475MB（PyInstaller 48s）
- 镜像：main **7f801d4 → 1c4b5d9**（15 页增量 + 13 图 + 站点文件）

## 2026-08-18 任务 E：Kimi 第六轮复检 → 引导句全量复核（待机轮）
- **Kimi 第六轮结果**：21 项中 16 项 ✅；5 项 ❌ 已全部处理：
  - Jet_Brigade_Hulk_Bruiser / Drum_Magazine / Crashed_Ship 引导句残留 → 修复根因：LEAD_PAGE_FIXES 段落正则上限 900 字符不足（Jet_Brigade 引导句段 906 字符）→ 放宽至 2000；Drum 重跑完整管线后生效；Crashed 本地早已修复（Kimi 抓取旧缓存）。
  - enemies.html / stratagems.html"截断" → 本地文件完整（4 组 / 8 组、`</html>` 收尾），系 Kimi 抓取工具渲染截断误判。
- **复核**：18 页引导句全部通顺中文；H1 中文标题生效；三件套全绿（1143 页 0 高危、坏页 0、链接 176,681 全绿）；EXE 打包冒烟通过。
- **镜像**：已推 `main` **7f801d4**。

## 2026-08-18 任务 E：应用 A 补译标题 → 重建 → H1 中文化（待机轮）
- 收到 A 协作说明：A 已补译 H1 纯英文标题（Seismic Probe→地震探测仪、Crashed Ship→坠毁飞船、AR-59 Suppressor→AR-59 消音器、Hangar→机库，另补 150 条空标题，持久化至 glossary.json）。
- E 执行重建管线：build_site → strip_hd1 → apply_zh_terms → generate_index_pages → verify → validate。
- **H1 已生效**：地震探测仪/坠毁飞船/AR-59 消音器/机库 4 页验证通过；Jet Brigade Hulk Bruiser 暂无中文标题（A 未补，留待 A 或用户决定）。
- **验收**：1143 页 0 高危/0 中危/0 低危；坏页 0；链接 176,694 全绿。
- **发布**：EXE 重新打包冒烟通过；镜像已推 `main` **fec1fd0**（应用 A 标题后的站点产物）。
- 备注：打包时遇 EXE 被残留进程占用（WinError 5），taskkill 后重打成功；巡检频率已按协作约定改为每 1 分钟。

## 2026-08-18 任务 E：Kimi 第五轮复检 → 引导句残留收尾
- **复检结果**：分类页/图集删除/术语表字段/链接健康全部 ✅；剩余问题为正文引导句半翻译残留（"the X 是"、"the X is a 中文"、"A X is" 等模式）。
- **修复（`apply_zh_terms.py`，基于 D 增量后的最新产物）**：
  - 通用规则：`the <b>X</b> 是`（111 页）、`the <b>X</b> is a/an 中文`（59 页）、`A <b>X</b> is`、`the X 在……的第N页解锁`（7 页）。
  - `LEAD_PAGE_FIXES` 精确映射 17 页完整中文引导句：Hunter/Hulk 系、Drum Magazine、Hangar、Crashed Ship、Seismic Probe、FAF-14、EAT-17、APW-1、GR-8、MG-206、DSS、GATER、Bug Breach/Nest、Robotics Workshop。
- **验收**：1143 页高危 0/中危 0/低危 0；坏页 0；链接 176,682 全绿；EXE 重新打包冒烟通过；镜像已推 `main` **c3fc0fe**（仅站点内容，未动 D 的文档文件）。
- 说明：D 的 PROGRESS/README/指南/sync_update.py 由 D 维护；E 在 D 推送 689b11b 之后继续推送了 c3fc0fe，镜像仓库当前 main = c3fc0fe。

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
- 已知坑：`kimi_agent.py --json` 在 Windows 控制台直接输出时，若回答含 emoji（如 ⚠️）会因 GBK 编码崩溃（回答已取回但未落盘）；规避：用 `--output 文件.json` 让脚本直接写文件

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

## 当前统计（2026-08-19）
- 页面总数：3,225（其中重定向 1,282）；site_final 保留子集：1,146 页
- 总文本块：50,057；已翻译：19,075（锁定 901）；待翻译：30,081
- site_final 页面：1,146；图片：8,169 张（missing_images.txt 记录 162 个缺失引用，随页面更新浮动）
- 链接检查（E 图集/Media 删除后口径）：177,304 个全部正常
- 上次发布：2026-08-19 敌人分类页种族配色（镜像 main bb3c221d，PROGRESS 57ee3fa2）；上次操作：sync_update.py --skip-sync --all
- 已完页：敌人、武器、战略配备、护甲、近战、手雷、SEAF士兵、Major Orders of 2024（954）、Major Orders of 2025（全部）
- 进行中：Major Orders 主页面（A 翻译驱动已暂停；批次文件 game_loc/mo_main_pending.txt 从第 75 行继续）
- 下一步顺序：Major Orders 主页面 → Galactic War → 行星战史/Battle Log → 其余叙事页

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
