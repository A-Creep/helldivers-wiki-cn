# -*- coding: utf-8 -*-
"""范围确认：把页面分成 KEEP(战斗实用) / DROP(叙事背景等) / MAYBE"""

import re
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

db = sqlite3.connect("wiki_local.db")
db.row_factory = sqlite3.Row
rows = db.execute(
    "SELECT title FROM pages WHERE ns=0 AND is_redirect=0 ORDER BY title").fetchall()
titles = [r["title"] for r in rows]

# ---------------- DROP 规则（叙事/背景/彩蛋/补丁/社区/外观） ----------------
DROP_RE = [
    r"^\d+\.\d+",                      # 补丁版本页
    r"(major order|galactic war|battle log|battles|/battles|news)",
    r"(history|timeline|lore|story|characters|character|people|personnel)",
    r"(super earth|federation|government|ministry|propaganda|dissident)",
    r"(events|event|factions|faction|species|memorial|museum)",
    r"(festival|liberty day|judgment day|april fools|scavenger war|reckoning)",
    r"(salute|handshake|hug|high-five|squat|flex|clap|draw|head tap|tip hat|bow|wave|point|pose|emote)",
    r"(pattern|camo|cosmetic|flag of|banner|emblem|cape of|cloak of|veil of|mantle|regalia|finery|garland|canopy)",
    r"(corporations|corporation|company|studios|entertainment|wiki$|community|mods|media|discord)",
    r"(sprite|sandbox|scratchpad|fanon|disambiguation|placeholder|/wip|/old$|/in depth|/2024$|/2025$)",
    r"(cup of liber|case of |premium light beer|library card|handwritten note|hastily written note|maintenance report|captain's log|payroll|words scribbled|welcome sign|vending machine|forklift|hand carts|cars$|poster$|graves$|corn farm|farm$|greenhouse|solar farm|cargo container|exploding barrels|barrels$|flower$|plant$|shrub$|mushroom$|rock$|boulder|stash$|note$|scribble|verdict|judgement|judgment)",
    r"^(the void|the gloom|the breach|supercolony|meridian black hole|dark fluid|dark fluid vessel|hive world|hive worlds|moradesh|termicide|element-710|e-710|e-711|dark energy|conventional black hole|center of science|pandora base|database one|cyberstan megafactory|deep mantle forge complex|maximum security city|tyranny park|tyranny park 2|freedom peak|wall of martyrs|martyr's bay|monument to liberty|liberty ridge|freedom's beacon|eye of liberty|eye of freedom|bastion of integrity|last great war|rise of the cyborgs|against the tyrant cloud|the reclamation|operation|the great host|the helldivers|helldiver|helldivers 2|helldivers wiki|invasion fleet|jet brigade factories|factory hub|morgunson|perma cura|permacura|ampudyn|ståhl|stahl arms|arrowhead|sony|rogue 5|pelican 1|pelican shuttle|extraction shuttle|extraction zone|extraction$|hellpod$|reinforcement pods|civilian|seaf soldier|seaf artillery|facility operator|service technician|ship master|democracy officer|general brasch|stefan holmes|coretta kelly|minor characters|major truth|mindless masses|the weir|dragonroach|scavenger$|voteless$|wretch$|crusher$|gazer$|harvester$|overseer$|watcher$|scout$|trooper$|raider$|marauder$|commissar$|berserker$|hulk$|war strider|factory strider|tank$|barrager tank|shredder tank|annihilator tank|impaler$|charger$|bile titan|bile spewer|nursing spewer|hunter$|stalker$|shrieker$|brood commander|hive guard|hive lord|hive queen|alpha commander|alpha warrior|warrior$|skitter$|pouncer$|brawler$|wraith$|scout strider|reinforced scout strider|incendiary rocket raider|rocket raider|mg raider|pyro trooper|jet brigade)",
]

# 明确叙事/背景的标题（不因包含实用词而误收）
DROP_EXACT = {
    "Campaigns", "The Gloom", "The Void", "Supercolony", "Termicide",
    "E-711 Extraction Facility", "Element-710", "Dark Fluid", "Dark Fluid Vessel",
    "Hive World", "Hive Worlds", "Center of Science", "Database One",
    "Democracy Space Station", "DSS Logistics Hub", "Operations (disambiguation)",
}

# ---------------- KEEP 规则（战斗实用） ----------------
WEAPON_RE = re.compile(
    r"^(AR|PLAS|SG|LAS|SMG|P|G|CQC|K|RS|EAT|RL|FAF|JAR|R|DBS|GP|CB|FLAM|ARC|MG|MLS|TD|TX|MP|M|S|GL|E/GL|A/|B/|AX/|SH|FX|MD|TM|I|O|VE|SC|SR|ST|StA|STA|VG|TED|APW|NUX|MS|M6C|M7S|M90A|MA5C|S-11|SR-|40-K|G/40|G/SH|CPG|CPH|CPR|KDM|EAT|EXO|FRV)\b",
    re.I)

ENEMY_WORDS = [
    "bile", "charger", "spewer", "hunter", "stalker", "scavenger", "warrior",
    "brood", "impaler", "shrieker", "hive", "hulk", "strider", "tank", "trooper",
    "raider", "commissar", "berserker", "devastator", "overseer", "harvester",
    "watcher", "voteless", "wretch", "crusher", "gazer", "scout", "marauder",
    "brawler", "wraith", "skitter", "pouncer", "termadon", "fleshmob",
    "appropriators", "mindless", "annihilator", "barrager", "shredder",
    "factory", "bot", "bug", "illuminate", "cyborg", "predator", "rupture",
    "spore", "jet brigade", "incineration", "alpha", "nursing", "assault",
    "commando", "raider", "raider's", "enemy", "weak", "weakness", "boss",
]

MISSION_WORDS = [
    "mission", "objective", "eradicate", "evacuate", "extract", "blitz",
    "activate", "destroy", "collect", "recover", "retrieve", "launch",
    "sabotage", "upload", "distribute", "intercept", "purge", "seize",
    "clear", "repel", "terminate", "conduct", "deploy", "secure", "defend",
    "rescue", "neutralize", "raze", "restart", "enable", "start", "annex",
    "suppress", "halt", "call the", "demolition", "operation", "campaign",
    "extraction", "defense", "invasion", "nuke", "prospecting", "drill",
    "bunker", "checkpoint", "control center", "communications",
]

MECHANIC_WORDS = [
    "damage", "armor", "ammo", "recoil", "reload", "health", "stat", "stats",
    "weak", "combat", "stealth", "spawn", "difficulty", "reinforce", "stance",
    "effects", "environment", "biomes", "hazard", "storm", "weather",
    "hellpod", "currency", "medal", "requisition", "super credits", "stores",
    "levels", "guides", "training manual", "game version", "map", "sample",
    "supplies", "supply", "personal orders", "galactic terminal",
    "ship", "module", "super destroyer", "bridge", "hangar", "engineering",
    "acquisition center", "warbond", "superstore", "cosmetics",
    "troubleshoot", "steam", "linux", "fps", "config", "settings", "crash",
    "audio problems", "input problems", "gpu", "virtual memory", "gameguard",
    "visual c++", "cross-platform", "shader", "error code",
    "scope", "sight", "magazine", "muzzle", "foregrip", "choke", "heatsink",
    "laser", "underbarrel", "duckbill", "compensator", "flash hider", "grip",
    "stock", "attachments", "biome", "environment", "storm", "weather",
    "blizzard", "sandstorm", "tornado", "meteor", "acid", "extreme cold",
    "intense heat", "tremors", "ion storm", "rainstorm", "fog", "volcanic",
    "lava", "swamp", "forest", "tundra", "jungle", "moor", "plains",
    "canyon", "badlands", "oasis", "deadlands", "boneyard", "burial",
    "undergrowth", "concrete jungle", "scorched", "fractured planet",
    "emplacement", "turret", "cannon", "barrage", "strike", "airdrop",
    "resupply", "reinforcement", "hive breaker", "seismic", "nuke", "mine",
    "mines", "mortar", "tesla", "shield", "pack", "backpack", "jump pack",
    "hover pack", "warp pack", "vehicle", "mech", "exosuit", "frv", "gater",
    "rocket pod", "gas", "flamethrower", "arc", "laser", "railgun", "spear",
    "commando", "autocannon", "machine gun", "sniper", "fabricator",
    "outpost", "nest", "lair", "base", "bunker", "checkpoint",
    "control center", "communications array", "detector tower",
    "seismic probe", "shuttle", "pelican", "cargo", "ammo", "stash",
    "cache", "pickup", "sample", "sssd", "research", "data", "drone",
    "radar", "tower", "generator", "relay", "pump", "refinery", "factory",
    "forge", "hub", "stronghold", "camp", "fortress", "spire", "exospire",
    "egg", "nursery", "hatchery", "larva", "gateway", "warp", "mineral",
    "oil", "gas", "chlorine", "polystyrene", "scrap", "titanium", "salt",
    "module", "advanced", "crew", "construction", "filtration", "monitoring",
    "optimization", "upgrade", "launch process", "request process",
    "targeting", "signature", "recon", "electronic countermeasures",
    "dynamic tracking", "rapid acquisition", "streamlined",
    "superior packing", "motivational", "flexible reinforcement",
    "increased reinforcement", "supplement", "stim", "grenade",
]

def is_keep(t: str) -> bool:
    tl = t.lower()
    if WEAPON_RE.match(t):
        return True
    if any(w in tl for w in ENEMY_WORDS):
        return True
    if any(w in tl for w in MISSION_WORDS):
        return True
    if any(w in tl for w in MECHANIC_WORDS):
        return True
    # 护甲/装备前缀
    if re.match(r"^(B|CE|CM|CW|DP|EX|FS|GS|IE|O|PH|RE|SA|SC|TG|TR|UF|AF|AC|AD|CPG|CPH|CPR|DS|KDM|SR)-\d", t):
        return True
    # 型号模式：A-35 / BP-32 / BR-14 / 10x Sniper Scope / G-10
    if re.match(r"^(\d+x\s|[A-Za-z][A-Za-z0-9/]*-?\d)", t):
        return True
    return False

def is_drop(t: str) -> bool:
    tl = t.lower()
    if t in DROP_EXACT:
        return True
    for pat in DROP_RE:
        if re.search(pat, tl):
            return True
    return False

keep, drop, maybe = [], [], []
for t in titles:
    if is_drop(t):
        drop.append(t)
    elif is_keep(t):
        keep.append(t)
    else:
        maybe.append(t)

print(f"KEEP : {len(keep)}")
print(f"DROP : {len(drop)}")
print(f"MAYBE: {len(maybe)}")
with open("keep_pages.txt", "w", encoding="utf-8") as fp:
    fp.write("\n".join(keep))
with open("drop_pages.txt", "w", encoding="utf-8") as fp:
    fp.write("\n".join(drop))
with open("maybe_pages.txt", "w", encoding="utf-8") as fp:
    fp.write("\n".join(maybe))
print("\n--- MAYBE 前 120 ---")
print("\n".join(maybe[:120]))
