# -*- coding: utf-8 -*-
"""渲染后术语替换：把 HTML 文本节点里的模板/UI 英文替换为中文

覆盖 infobox 字段名、导航框、章节标题等模板层英文（翻译表覆盖不到的）。
只处理标签之间的文本，不动属性/URL/文件名。
"""

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(ROOT, "output_zh", "site_final", "pages")

# 手写高频 UI / 模板词（长词在前，防止短词先替换）
TERMS = [
    # 章节/结构
    ("Change History", "变更历史"), ("List of Stratagems", "战略配备列表"),
    ("Support Weapons", "支援武器"), ("Stratagem Types", "战略配备类型"),
    ("Offensive Permit", "进攻许可"), ("Supply Permit", "补给许可"),
    ("Defensive Permit", "防御许可"), ("Environmental Hazards", "环境危害"),
    ("Status Effects", "状态效果"), ("Galactic War Mechanics", "银河战争机制"),
    ("Minimum Difficulty", "最低难度"), ("Size Class", "体型级别"),
    ("Damage Type", "伤害类型"), ("Damage Types", "伤害类型"),
    ("Fire Damage Multiplier", "火焰伤害倍率"),
    ("Fire Stagger Threshold", "火焰硬直阈值"), ("Stagger Force", "硬直力度"),
    ("Durable Damage", "耐久伤害"), ("Explosion Damage", "爆炸伤害"),
    ("Area Damage", "范围伤害"), ("Projectile Damage", "投射物伤害"),
    ("Total Damage", "总伤害"), ("Fire Rate", "射速"), ("Fire Delay", "射击延迟"),
    ("Magazine Size", "弹匣容量"), ("Magazine", "弹匣"), ("Capacity", "容量"),
    ("Reload Time", "换弹时间"), ("Reload", "换弹"), ("Recoil", "后坐力"),
    ("Aiming Time", "瞄准时间"), ("Switch Time", "切换时间"),
    ("Draw Time", "拔枪时间"), ("Stow Time", "收枪时间"),
    ("Wield Time", "持枪时间"), ("Rounds Per Salvo", "每次齐射弹数"),
    ("Salvoes", "齐射次数"), ("Charges", "充能次数"), ("Uses", "使用次数"),
    ("Ammo", "弹药"), ("Penetration", "穿透"), ("Mass", "质量"),
    ("Speed", "速度"), ("Health", "生命值"), ("Armor", "护甲"),
    ("Damage", "伤害"), ("Stats", "属性"), ("Stat", "属性"),
    ("Description", "描述"), ("Overview", "概述"), ("Acquisition", "获取"),
    ("Weaponry", "武器库"), ("Armory", "军械库"), ("Gallery", "图库"),
    ("References", "参考"), ("See Also", "另见"), ("Trivia", "杂项"),
    ("Notes", "备注"), ("Strategy", "策略"), ("Tactics", "战术"),
    ("General", "基本信息"), ("Technical", "技术信息"),
    ("Game Version", "游戏版本"), ("Release Date", "发布日期"),
    ("Chronology", "时间线"), ("Blog Post", "博客文章"),
    ("Next", "下一个"), ("Previous", "上一个"),
    ("Faction", "阵营"), ("Factions", "阵营"), ("Class", "级别"),
    ("Category", "类别"), ("Rarity", "稀有度"), ("Tags", "标签"),
    ("Usage", "使用"), ("Contents", "目录"), ("Patch", "补丁"),
    ("Update", "更新"), ("Stats", "属性"), ("Lore", "背景"),
    ("Quote", "引文"), ("Title", "标题"), ("Author", "作者"),
    ("Content", "内容"), ("Difficulty", "难度"), ("Mission", "任务"),
    ("Objective", "目标"), ("Target", "目标"), ("Location", "位置"),
    ("Planet", "行星"), ("Sector", "分区"), ("Biome", "生物群系"),
    ("Weather", "天气"), ("Hazard", "危害"), ("Threat", "威胁"),
    ("Warning", "警告"), ("Danger", "危险"), ("Info", "信息"),
    ("Important", "重要"), ("Example", "示例"), ("Types", "类型"),
    ("Type", "类型"), ("Effects", "效果"), ("Effect", "效果"),
    ("Bleeding", "流血"), ("Burning", "燃烧"), ("Poison", "中毒"),
    ("Gas", "毒气"), ("Acid", "酸"), ("Fire", "火焰"), ("Explosion", "爆炸"),
    ("Blunt", "钝击"), ("Piercing", "穿刺"), ("Melee", "近战"),
    ("Ranged", "远程"), ("Light", "轻型"), ("Medium", "中型"),
    ("Heavy", "重型"), ("Super Heavy", "超重型"),
    ("Stratagem Details", "战略配备详情"), ("Permit Type", "许可类型"),
    ("Stratagem Code", "战略配备代码"), ("Base Cooldown", "基础冷却"),
    ("Weapon Details", "武器详情"), ("Weapon Category", "武器类别"),
    ("Weapon Type", "武器类型"), ("Firing Modes", "射击模式"),
    ("Traits", "特性"), ("Standard Damage", "标准伤害"),
    ("Armor Penetration", "护甲穿透"), ("Fire Rate", "射速"),
    ("Ammo", "弹药"), ("Capacity", "容量"), ("Handling", "操控性"),
    ("Ergonomics", "人体工学"), ("Procurement", "获取途径"),
    ("Unlock Level", "解锁等级"), ("Unlock Cost", "解锁费用"),
    ("Source", "来源"), ("Last updated", "最后更新"),
    ("Current patch", "当前补丁"), ("Applicable Ship Modules", "适用舰船模块"),
    ("See also", "另见"), ("Support Weapons", "支援武器"),
    ("Call-in Time", "呼叫时间"), ("Cooldown", "冷却"),
    ("Uses", "使用次数"), ("Minimap", "小地图"), ("Call In", "呼叫"),
    ("Stratagem", "战略配备"), ("Damage Type", "伤害类型"),
    ("Fire Damage", "火焰伤害"), ("Explosive", "爆炸"), ("Ballistic", "弹道"),
    ("Energy", "能量"), ("Chemical", "化学"), ("Electric", "电"),
    ("Shock", "电击"), ("Stagger", "硬直"), ("Stagger Threshold", "硬直阈值"),
    ("Weak Points", "弱点"), ("Weak Spot", "弱点"),
    ("Combat Role", "战斗定位"), ("Special", "特殊"),
    ("Heavy (AP-HE)", "重型（穿甲高爆）"), ("Medium (Shrapnel)", "中型（破片）"),
    ("Standard", "标准"), ("Moderate", "中等"),
    ("Light (AP)", "轻型（穿甲）"), ("Heavy (AP)", "重型（穿甲）"),
    ("Medium (AP)", "中型（穿甲）"),
    ("Streamlined Request Process", "精简申请流程"),
    ("Morale Augmentation", "士气强化"), ("Dynamic Tracking", "动态追踪"),
    ("Targeting Software Upgrade", "瞄准软件升级"),
    ("Superior Packing Methodology", "卓越封装方法"),
    ("Motivational Shocks", "激励电击"), ("Rapid Launch System", "快速发射系统"),
    ("Electronic Countermeasures", "电子对抗措施"),
    ("Advanced Construction", "高级建造"), ("Advanced Crew Training", "高级船员训练"),
    ("Advanced Filtration", "高级过滤"), ("Atmospheric Monitoring", "大气监测"),
    ("Expert Extraction Pilot", "专家撤离飞行员"),
    ("Reinforced Crew Training", "强化船员训练"),
    ("Payload Upgrades", "载荷升级"), ("Explosive Upgrades", "爆炸物升级"),
    ("Concussive Padding", "减震衬垫"), ("Galactic Map", "银河地图"),
    ("Ship Management Terminal", "舰船管理终端"),
    ("Body Armor", "身体护甲"), ("Helmet", "头盔"), ("Armor Type", "护甲类型"),
    ("Speed", "速度"), ("Stamina", "耐力"), ("Passive", "被动"),
    ("Passive Ability", "被动能力"), ("Acquisition", "获取"),
    ("Main Objective Info", "主要目标信息"),
    ("Minimum Difficulty", "最低难度"), ("Maximum Difficulty", "最高难度"),
    ("Time Limit", "时间限制"), ("Maps At Each Difficulty", "各难度地图"),
    ("Default", "默认"), ("Upgraded", "已升级"), ("Part Name", "部件名称"),
    ("Constitution", "构造"), ("Projectile", "投射物"), ("Penetration", "穿透"),
    ("Rearm Time", "重新装填时间"), ("DPS", "每秒伤害"), ("Reload", "换弹"),
    ("Recoil", "后坐力"), ("Detailed Weapon Statistics", "详细武器数据"),
    ("Stratagem Statistics", "战略配备数据"), ("Tactical Information", "战术信息"),
    ("Change History", "变更历史"), ("Armor Details", "护甲详情"),
    ("Weapon Details", "武器详情"), ("Superstore", "超级商店"),
    ("Sway Modifier", "晃动修正"), ("Drag Factor", "阻力系数"),
    ("Trivial", "简单"), ("Easy", "容易"), ("Medium", "中等"),
    ("Challenging", "挑战"), ("Hard", "困难"), ("Extreme", "极难"),
    ("Suicide Mission", "自杀任务"), ("Impossible", "不可能"),
    ("Helldive", "绝地潜兵难度"), ("Super Helldive", "超级绝地潜兵难度"),
    ("Cost", "费用"), ("Media", "媒体"), ("Trivia", "杂项"),
    ("Description", "描述"), ("Constitution", "构造"),
    ("Fatal", "致命"), ("Health", "生命值"),
    ("Part Name", "部位"), ("AV", "护甲值"), ("Durable", "耐久"),
    ("% To Main", "主血量占比"), ("To Main", "对主血量"),
    ("Location", "位置"), ("Main Health", "主生命值"),
    ("Attack", "攻击"), ("Attacks", "攻击"), ("Melee Attack", "近战攻击"),
    ("Ranged Attack", "远程攻击"), ("Range", "射程"), ("Arc", "弧度"),
    ("Splash", "溅射"), ("AoE", "范围效果"),
    ("Slight Angle", "小角度"), ("Large Angle", "大角度"),
    ("Main Objective", "主要目标"), ("Optional Objective", "可选目标"),
    ("Objectives", "目标"), ("Outposts", "哨站"),
    ("Conduct Geological Survey", "进行地质勘测"),
    ("Evacuate High-Value Assets", "撤离高价值资产"),
    ("Damage Modifier", "伤害修正"), ("DPS", "每秒伤害"),
    ("Stagger Damage", "硬直伤害"), ("Demolition", "爆破"),
    ("Explosion Radius", "爆炸半径"), ("Drop", "掉落"),
    ("Weight", "重量"), ("Throwable", "投掷物"),
    ("Spawning", "生成"), ("Behavior", "行为"), ("Behaviour", "行为"),
    ("Anatomy", "结构解析"), ("Weapons Loadout", "武器配置"),
    ("Trivia", "轶事"), ("References", "参考"), ("Media", "媒体"),
    ("Minutes", "分钟"), ("Seconds", "秒"), ("Bombs", "炸弹"),
    ("Salvos", "齐射"), ("CoolDown", "冷却"), ("Cooldown", "冷却"),
    ("Tactical Information", "战术信息"), ("Spawning", "生成"),
    ("Known Issues", "已知问题"), ("Known Issue", "已知问题"),
    ("Overview", "概述"), ("Usage", "使用"), ("Tips", "技巧"),
    ("Example", "示例"), ("Gallery", "图库"), ("Footnotes", "脚注"),
    ("Change History", "变更历史"),
    ("Overflow Cap", "溢出上限"), ("Small", "小型"), ("Lethal", "致命"),
    ("Tactical Information", "战术信息"), ("Weapons Loadout", "武器配置"),
]

# 从 glossary 补充短词条（仅 1-3 个英文词、中文 ≤ 6 字，避免误替换句子）
try:
    g = json.load(open(os.path.join(ROOT, "glossary.json"), encoding="utf-8"))
    for en, zh in g.items():
        en = en.strip()
        zh = str(zh).strip()
        if not en or not zh or len(en.split()) > 3 or len(zh) > 8:
            continue
        words = en.split()
        if not (len(words) >= 2 or len(en) >= 7):
            continue  # 单短词容易误伤正文（match/set/may 等），跳过
        if re.search(r"[^A-Za-z \-']", en):
            continue
        if en.lower() in ("a", "an", "the", "and", "of", "for", "to", "in", "on"):
            continue
        TERMS.append((en, zh))
except Exception:
    pass

# 去重、长词优先
seen = {}
for en, zh in TERMS:
    key = en.lower()
    if key not in seen or len(en) > len(seen[key][0]):
        seen[key] = (en, zh)
TERMS = sorted(seen.values(), key=lambda x: -len(x[0]))

TEXT_RE = re.compile(r"(?<=>)([^<>]*?)(?=<)")


def repl_segment(seg):
    for en, zh in TERMS:
        if en.lower() not in seg.lower():
            continue
        pat = re.compile(r"(?<![A-Za-z])" + re.escape(en) + r"(?![A-Za-z])", re.I)
        seg = pat.sub(zh, seg)
    seg = re.sub(r"([\u4e00-\u9fff])\?", r"\1", seg)
    return seg


def apply_file(path):
    html = open(path, encoding="utf-8").read()
    html = TEXT_RE.sub(lambda m: repl_segment(m.group(1)), html)
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(html)


def main():
    n = 0
    for f in sorted(os.listdir(PAGES)):
        if f.endswith(".html"):
            apply_file(os.path.join(PAGES, f))
            n += 1
    print(f"[Terms] 已处理 {n} 个页面")


if __name__ == "__main__":
    main()
