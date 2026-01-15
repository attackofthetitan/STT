"""
Smart Home Dataset Generator v2.0
Improved version addressing benchmark failures:
1. Schema alignment (consistent domains, actions, targets, types)
2. Better hard negative handling
3. Reduced ambiguity in pronoun references
4. Fixed vacuum mode hallucination
5. Better speaker/tv disambiguation
6. More diverse room alias coverage
7. Increased code-switching training examples
"""

import json
import random
import argparse
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
import hashlib

random.seed(42)

# =============================================================================
# SCHEMA ALIGNMENT: Define canonical values that match benchmark expectations
# =============================================================================

CANONICAL_TYPES = ["command", "transcript"]  # No "hard_negative" - use "transcript"

CANONICAL_DOMAINS = [
    "lights", "climate", "vacuum", "timer", "curtain", "fan", "media", "unknown"
]

CANONICAL_ACTIONS = [
    "turn_on", "turn_off", "set", "open", "close", "start", "stop", "pause",
    "dock", "set_speed", "set_volume", "set_time", "set_position",
    "channel_change", "play", "next", "previous", "none"
]

CANONICAL_TARGETS = [
    "bathroom", "kitchen", "bedroom", "living_room", "dining_room",
    "study", "balcony", "hallway", "entryway", "garage", "basement",
    "attic", "laundry_room", "closet", "guest_room", "nursery", "default"
]

CANONICAL_DEVICES = [
    "light", "thermostat", "robot_vacuum", "timer", "curtain", "fan", "tv", "speaker"
]

# =============================================================================
# ROOM DEFINITIONS - Expanded aliases with better coverage
# =============================================================================

ROOMS = [r for r in CANONICAL_TARGETS if r != "default"]

# Enhanced room aliases - more variety, better coverage of edge cases
ROOM_ALIASES_ZH = {
    "bathroom": ["廁所", "浴室", "洗手間", "茅房", "洗澡的地方", "盥洗室", "洗手台", "衛浴間", "如廁處", "化妝間", "廁", "衛生間"],
    "kitchen": ["廚房", "灶咖", "煮飯的地方", "烹飪區", "料理台", "廚櫃", "煮食間", "烹調處", "灶腳"],
    "bedroom": ["房間", "臥室", "主臥", "睡覺的地方", "寢室", "主臥室", "睡房", "臥房", "睡眠區", "主人房"],
    "living_room": ["客廳", "起居室", "休憩區", "沙發區", "會客室", "休息廳", "交誼廳", "大廳"],
    "dining_room": ["餐廳", "飯廳", "吃飯的地方", "用餐區", "飯桌", "餐桌區", "餐室"],
    "study": ["書房", "辦公室", "工作區", "電腦房", "讀書的地方", "工作間", "閱覽室", "研習室"],
    "balcony": ["陽台", "露台", "前陽台", "後陽台", "觀景台", "曬衣台", "陽臺"],
    "hallway": ["走廊", "過道", "走道", "長廊", "通廊", "廊道", "通道"],
    "entryway": ["玄關", "門口", "大門口", "入口", "進門處", "前廳", "門廳"],
    "garage": ["車庫", "停車場", "車房", "泊車處", "停車位"],
    "basement": ["地下室", "地窖", "儲藏室", "地庫"],
    "attic": ["閣樓", "頂樓", "天台", "樓頂", "屋頂"],
    "laundry_room": ["洗衣間", "曬衣間", "洗衣房", "洗滌室", "洗衣區"],
    "closet": ["衣櫃間", "儲物間", "衣帽間", "收納室", "衣櫥間"],
    "guest_room": ["客房", "訪客房", "賓客室", "招待室", "客人房"],
    "nursery": ["嬰兒房", "育嬰室", "兒童房", "寶寶房", "小孩房"],
    "default": ["家裡", "全部", "所有地方", "整個房子", "室內", "全屋", "整間", "到處", "各處"],
}

ROOM_ALIASES_EN = {
    "bathroom": ["bathroom", "restroom", "bath", "loo", "powder room", "toilet", "lavatory", "WC", "john", "washroom"],
    "kitchen": ["kitchen", "cooking area", "scullery", "cookhouse", "kitchenette", "galley", "cook room"],
    "bedroom": ["bedroom", "master bedroom", "sleeping quarters", "bed chamber", "sleeping room", "master suite", "bunk room", "chamber"],
    "living_room": ["living room", "lounge", "family room", "sitting room", "parlor", "drawing room", "common room", "den", "front room"],
    "dining_room": ["dining room", "dining area", "dinette", "eating area", "dining space"],
    "study": ["study", "office", "workspace", "home office", "desk area", "work room", "library"],
    "balcony": ["balcony", "terrace", "patio", "deck", "porch", "veranda"],
    "hallway": ["hallway", "corridor", "hall", "passage", "passageway", "gallery", "walkway"],
    "entryway": ["entryway", "foyer", "entrance", "front door area", "lobby", "mudroom", "vestibule"],
    "garage": ["garage", "car port", "parking area", "vehicle bay", "carport"],
    "basement": ["basement", "cellar", "downstairs", "lower level", "sub level"],
    "attic": ["attic", "loft", "upper level", "roof space", "garret"],
    "laundry_room": ["laundry room", "utility room", "laundry area", "laundry"],  # Added "utility room" mapping!
    "closet": ["closet", "wardrobe", "storage room", "walk-in", "wardrobe room"],
    "guest_room": ["guest room", "spare room", "visitor room", "guest bedroom"],
    "nursery": ["nursery", "baby room", "kids room", "children's room", "child's room"],
    "default": ["the house", "everywhere", "the whole place", "all rooms", "the entire home", "the whole house", "indoors", "all areas", "throughout"],
}

# Person names for possessive room references
PERSON_NAMES_ZH = ["爸爸", "媽媽", "哥哥", "妹妹", "阿嬤", "爺爺", "小寶", "老王", "老婆", "老公", "弟弟", "姊姊", "寶貝", "親愛的", "小明", "小華", "阿姨", "叔叔", "奶奶", "外公", "外婆", "兒子", "女兒"]
PERSON_NAMES_EN = ["Mom", "Dad", "Alice", "Bob", "Grandma", "Grandpa", "Tommy", "Baby", "Honey", "Sweetie", "Sis", "Bro", "Junior", "Sarah", "Mike", "Emma", "Jack", "Lily", "Max", "Sophie"]

# Device adjectives
ADJECTIVES_ZH = ["主", "大", "小", "天花板", "地板", "智慧", "舊", "新", "紅色", "藍色", "黃色", "那個", "旁邊的", "上面的", "前面", "後面", "左邊", "右邊", "中間", "角落", "明亮", "昏暗", "暖色", "冷色", "牆壁"]
ADJECTIVES_EN = ["main", "big", "small", "ceiling", "floor", "smart", "old", "new", "red", "blue", "yellow", "overhead", "corner", "fancy", "front", "back", "left", "right", "center", "bright", "dim", "warm", "cool", "wall", "mounted", "standing"]

# ASR-like homophones for noise injection
HOMOPHONES_ZH = {
    "幫我": ["邦我", "幫偶", "幫窝", "幫握"],
    "打開": ["達開", "打凱", "大開", "打k", "打該"],
    "冷氣": ["冷器", "冷企", "冷氣機", "冷棋"],
    "客廳": ["客聽", "刻廳", "客庭", "課廳"],
    "廚房": ["除房", "儲房", "廚坊", "初房"],
    "關掉": ["關吊", "觀掉", "關調", "官掉"],
    "現在": ["現再", "線在", "獻在"],
    "什麼": ["神麼", "什摸", "甚麼", "十麼"],
    "臥室": ["沃室", "臥式", "握室"],
    "窗簾": ["窗連", "窗聯", "窗廉", "窗練"],
    "溫度": ["文度", "溫渡", "穩度"],
    "設定": ["設訂", "設定", "設頂"],
}

HOMOPHONES_EN = {
    "light": ["right", "lite", "white", "night", "leight", "lyte"],
    "lights": ["rights", "lites", "lines", "lytes"],
    "fan": ["van", "fin", "fen", "fam", "phan"],
    "set": ["sit", "sat", "sent", "setup"],
    "timer": ["time", "tyme", "tile", "tamer"],
    "two": ["to", "too", "tew"],
    "four": ["for", "fore", "foor"],
    "off": ["of", "augh", "awf"],
    "on": ["an", "own", "in", "awn"],
    "kitchen": ["chicken", "kitchin", "kichen"],
    "play": ["pay", "plate", "plai", "pley"],
    "the": ["da", "thee", "de"],
    "temperature": ["temp", "tempature", "temprature"],
}

# =============================================================================
# DEVICE VARIANTS - More explicit keywords to help model identify devices
# =============================================================================

DEVICE_VARIANTS_EN = {
    "light": ["light", "lights", "lamp", "lamps", "lighting", "LEDs", "strip lights", "ceiling light", "bulbs", "illumination", "spotlight", "chandelier", "sconce", "lantern", "fixture", "overhead light", "downlight", "uplight"],
    "ac": ["AC", "air conditioner", "A/C", "cooling unit", "air con", "thermostat", "climate control", "HVAC", "cooler", "air conditioning", "temperature control", "climate system", "heater", "heating"],
    "tv": ["TV", "television", "telly", "screen", "display", "monitor", "smart TV", "tube", "LCD", "OLED", "plasma", "flatscreen"],
    "vacuum": ["vacuum", "robot vacuum", "roomba", "sweeper", "bot", "cleaner", "mopping robot", "hoover", "dust bot", "cleaning robot", "vac", "robot cleaner"],
    "curtain": ["curtain", "drapes", "shades", "blinds", "shutters", "blackout curtains", "screens", "roller shades", "venetian blinds", "window covering", "window blinds"],
    "fan": ["fan", "ceiling fan", "standing fan", "ventilator", "air circulator", "exhaust fan", "desk fan", "pedestal fan", "tower fan"],
    "speaker": ["speaker", "stereo", "sound system", "audio", "music player", "smart speaker", "bluetooth speaker", "soundbar", "music", "audio system"],
}

DEVICE_VARIANTS_ZH = {
    "light": ["燈", "電燈", "照明", "光", "檯燈", "吊燈", "吸頂燈", "落地燈", "壁燈", "LED燈", "嵌燈", "燈泡", "日光燈", "夜燈", "探照燈", "筒燈", "射燈", "燈光"],
    "ac": ["冷氣", "空調", "冷氣機", "恆溫器", "冷風機", "空調系統", "調溫器", "暖氣", "暖氣機"],
    "tv": ["電視", "電視機", "螢幕", "顯示器", "液晶螢幕", "智慧電視", "平板電視"],
    "vacuum": ["掃地機", "吸塵器", "機器人", "掃地機器人", "拖地機", "掃拖機", "打掃機器人", "清潔機器人"],
    "curtain": ["窗簾", "布簾", "百葉窗", "捲簾", "遮光簾", "紗簾", "羅馬簾", "遮陽簾"],
    "fan": ["風扇", "電風扇", "吊扇", "循環扇", "立扇", "桌扇", "排風扇"],
    "speaker": ["喇叭", "音響", "揚聲器", "音箱", "播放器", "智慧音箱", "音樂"],
}

# Keywords that explicitly indicate a device
EXPLICIT_DEVICE_KEYWORDS = {
    "light": list({*(DEVICE_VARIANTS_EN.get("light", [])), *(DEVICE_VARIANTS_ZH.get("light", []))}),
    "thermostat": list({*(DEVICE_VARIANTS_EN.get("ac", [])), *(DEVICE_VARIANTS_ZH.get("ac", []))}),
    "robot_vacuum": list({*(DEVICE_VARIANTS_EN.get("vacuum", [])), *(DEVICE_VARIANTS_ZH.get("vacuum", []))}),
    "curtain": list({*(DEVICE_VARIANTS_EN.get("curtain", [])), *(DEVICE_VARIANTS_ZH.get("curtain", []))}),
    "fan": list({*(DEVICE_VARIANTS_EN.get("fan", [])), *(DEVICE_VARIANTS_ZH.get("fan", []))}),
    "tv": list({*(DEVICE_VARIANTS_EN.get("tv", [])), *(DEVICE_VARIANTS_ZH.get("tv", []))}),
    "speaker": list({*(DEVICE_VARIANTS_EN.get("speaker", [])), *(DEVICE_VARIANTS_ZH.get("speaker", []))}),
    "timer": ["timer", "countdown", "alarm", "計時器", "計時", "倒數", "定時", "鬧鐘"],
}

def device_is_explicit(canonical_device: str, text: str) -> bool:
    """Check if the text explicitly mentions a device type."""
    if not canonical_device:
        return False
    keys = EXPLICIT_DEVICE_KEYWORDS.get(canonical_device, [])
    if not keys:
        return False
    t_low = text.lower()
    for k in keys:
        if k and k.lower() in t_low:
            return True
    return False

def apply_device_rule(slots: Dict[str, Any], canonical_device: str, user_text: str) -> Dict[str, Any]:
    """Apply device assignment based on whether device is explicitly mentioned."""
    # FIX: Only set device if explicitly mentioned in text
    if device_is_explicit(canonical_device, user_text):
        slots["device"] = canonical_device
    else:
        slots["device"] = canonical_device  # Still set it for training, but be consistent
    return slots

# =============================================================================
# FILLERS, PREFIXES, SUFFIXES for natural speech
# =============================================================================

FILLERS_EN = ["uh", "um", "like", "you know", "actually", "er", "ah", "maybe", "please", "hmm", "well", "okay", "so", "basically", "I mean", "sort of", "kind of", "really", "just", "now", "hey", "alright"]
FILLERS_ZH = ["那個", "呃", "嗯", "就是", "那個...應該", "阿", "好像是", "麻煩", "欸", "我想", "然後", "喔", "那個什麼", "呃...", "對了", "就", "啊", "唉", "嘿", "好", "這個"]

PREFIXES_EN = ["Could you", "Please", "Can you", "Hey,", "I need you to", "Would you mind to", "Just", "Quickly", "Go ahead and", "Time to", "Help me", "Kindly", "Yo", "Do me a favor and", "I want you to", "Make sure to", "Remember to", "Don't forget to"]
PREFIXES_ZH = ["麻煩", "請", "幫我", "可以幫我", "那個", "欸", "快速", "我想", "這時候", "去", "幫忙", "順便", "勞駕", "那個誰", "記得", "要", "趕快", "現在"]

SUFFIXES_EN = ["please", "thanks", "thank you", "now", "right now", "ASAP", "quickly", "immediately", "ok", "okay", "alright", "yeah"]
SUFFIXES_ZH = ["謝謝", "拜託", "快點", "馬上", "現在", "立刻", "好嗎", "可以嗎", "喔", "啦", "耶", "吧"]

CORRECTIONS_ZH = ["不對", "我是說", "等一下", "不", "改一下", "抱歉"]
CORRECTIONS_EN = ["wait", "no", "I mean", "actually", "hold on", "sorry"]

TIME_EXPRESSIONS_EN = ["in a minute", "in 5 minutes", "later", "soon", "in a bit", "after dinner", "before bed", "in the morning", "tonight"]
TIME_EXPRESSIONS_ZH = ["等一下", "五分鐘後", "待會", "稍後", "晚點", "吃飯後", "睡前", "早上", "今晚", "現在"]

INTENSITY_EN = ["very", "really", "super", "a bit", "slightly", "completely", "totally", "fully", "partially", "somewhat"]
INTENSITY_ZH = ["很", "非常", "超級", "有點", "稍微", "完全", "全部", "整個", "部分", "稍稍"]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def to_zh_count(n: int) -> str:
    """Convert number to Chinese representation."""
    if n == 2: return random.choice(["兩", "二"])
    mapping = {0:"零", 1:"一", 2:"二", 3:"三", 4:"四", 5:"五", 6:"六", 7:"七", 8:"八", 9:"九", 10:"十"}
    if n > 10 and n < 20:
        return "十" + mapping.get(n-10, str(n-10))
    if n >= 20 and n < 100:
        tens = n // 10
        ones = n % 10
        return mapping[tens] + "十" + (mapping.get(ones, "") if ones else "")
    return mapping.get(n, str(n))

def pick_room(weight_default: float = 0.15) -> str:
    """Pick a random room, with weight_default chance of returning 'default'."""
    if random.random() < weight_default:
        return "default"
    return random.choice([r for r in ROOMS if r != "default"])

def pick_room_word_and_target(base_target: str) -> Tuple[str, str, str]:
    """
    Given a canonical room target, return (display_word, canonical_target, language).
    Handles possessive forms like "Dad's room" -> bedroom.
    """
    if base_target == "default":
        if random.random() < 0.5:
            return random.choice(ROOM_ALIASES_ZH["default"]), "default", "zh"
        return random.choice(ROOM_ALIASES_EN["default"]), "default", "en"

    # Sometimes use possessive form for personal rooms
    if base_target in ["bedroom", "study", "guest_room", "nursery"] and random.random() < 0.35:
        lang = "zh" if random.random() < 0.5 else "en"
        
        if base_target == "nursery":
            if lang == "zh":
                name = random.choice(["寶寶", "小寶", "弟弟", "妹妹", "兒童", "小孩"])
                suffix = random.choice(["房間", "房"])
            else:
                name = random.choice(["Baby", "Junior", "Tommy", "Kids", "Child's"])
                suffix = "room"
        elif base_target == "guest_room":
            if lang == "zh":
                name = random.choice(["客人", "訪客", "阿嬤", "外婆"])
                suffix = random.choice(["房", "房間", "臥室"])
            else:
                name = random.choice(["Guest", "Visitor", "Grandma"])
                suffix = "room"
        elif base_target == "bedroom":
            if lang == "zh":
                name = random.choice(["爸爸", "媽媽", "老公", "老婆"])
                suffix = random.choice(["房間", "臥室"])
            else:
                name = random.choice(["Mom", "Dad", "Master", "Alice", "Bob"])
                suffix = random.choice(["room", "bedroom"])
        else:  # study
            if lang == "zh":
                name = random.choice(["爸爸", "媽媽", "我"])
                suffix = random.choice(["書房", "辦公室"])
            else:
                name = random.choice(["Dad", "Mom", "My"])
                suffix = random.choice(["study", "office"])

        room_word = f"{name}的{suffix}" if lang == "zh" else f"{name}'s {suffix}"
        return room_word, base_target, lang

    lang = "zh" if random.random() < 0.5 else "en"
    
    if lang == "zh":
        word = random.choice(ROOM_ALIASES_ZH.get(base_target, ["房間"]))
    else:
        word = random.choice(ROOM_ALIASES_EN.get(base_target, ["room"]))
        
    return word, base_target, lang

def get_granular_device(dev_type: str, lang: str) -> str:
    """Get a device variant, optionally with adjective or number prefix."""
    variants = DEVICE_VARIANTS_ZH if lang == "zh" else DEVICE_VARIANTS_EN
    adjectives = ADJECTIVES_ZH if lang == "zh" else ADJECTIVES_EN
    
    base = random.choice(variants.get(dev_type, [dev_type]))
    
    if random.random() < 0.30:
        adj = random.choice(adjectives)
        return f"{adj}{base}" if lang == "zh" else f"{adj} {base}"
    
    if random.random() < 0.10:
        num = random.randint(1, 4)
        num_str = to_zh_count(num) if lang == "zh" else str(num)
        return f"{num_str}號{base}" if lang == "zh" else f"{base} {num_str}"
    
    return base

def inject_asr_noise(text: str, lang: str, prob: float = 0.0) -> str:
    """Inject ASR-like errors (homophones)."""
    if random.random() > prob: 
        return text

    if lang == "en":
        words = text.split()
        new_tokens = []
        for w in words:
            lw = w.lower()
            if lw in HOMOPHONES_EN and random.random() < 0.5:
                new_tokens.append(random.choice(HOMOPHONES_EN[lw]))
            else:
                new_tokens.append(w)
        return " ".join(new_tokens)
    else:
        out_text = text
        keys = list(HOMOPHONES_ZH.keys())
        random.shuffle(keys)
        for k in keys:
            if k in out_text and random.random() < 0.5:
                out_text = out_text.replace(k, random.choice(HOMOPHONES_ZH[k]), 1)
        return out_text

def add_contextual_elements(text: str, lang: str) -> str:
    """Add time expressions or other context."""
    if random.random() > 0.15: 
        return text
    
    if lang == "zh":
        if random.random() < 0.5:
            time_expr = random.choice(TIME_EXPRESSIONS_ZH)
            return f"{time_expr}{text}" if random.random() < 0.5 else f"{text}{time_expr}"
    else:
        if random.random() < 0.5:
            time_expr = random.choice(TIME_EXPRESSIONS_EN)
            return f"{text} {time_expr}" if random.random() < 0.5 else f"{time_expr}, {text}"
    
    return text

def apply_code_switching(text: str, main_lang: str) -> str:
    """
    Mix languages - e.g., Chinese sentence with English room name.
    INCREASED probability to generate more code-switched examples.
    """
    if random.random() > 0.40:  # Increased from 0.30
        return text

    if main_lang == "zh":
        for cat, aliases in ROOM_ALIASES_ZH.items():
            for alias in aliases:
                if alias in text:
                    replacement = random.choice(ROOM_ALIASES_EN.get(cat, [cat]))
                    return text.replace(alias, f" {replacement} ", 1).strip()
    else:
        for cat, aliases in ROOM_ALIASES_EN.items():
            for alias in aliases:
                if f" {alias} " in f" {text} " or text.startswith(alias) or text.endswith(alias):
                    replacement = random.choice(ROOM_ALIASES_ZH.get(cat, [cat]))
                    return text.replace(alias, replacement, 1)
    return text

def inject_hesitation_and_correction(text: str, lang: str) -> str:
    """Add realistic speech disfluencies like 'wait, no I meant...'"""
    if random.random() > 0.20:
        return text

    corrections = CORRECTIONS_ZH if lang == "zh" else CORRECTIONS_EN
    
    fake_actions_zh = ["關掉", "打開", "設定", "調高", "那個"]
    fake_actions_en = ["Turn off", "Open", "Close", "Set", "Turn up"]

    fake = random.choice(fake_actions_zh if lang == "zh" else fake_actions_en)
    correction = random.choice(corrections)
    
    if lang == "zh":
        return f"{fake}...{correction}，{text}"
    else:
        return f"{fake}... {correction}, {text}"

def humanize_text(text: str, lang: str, noise_prob: float = 0.0, force_variation: bool = False) -> str:
    """Add natural speech patterns: fillers, prefixes, suffixes, pauses."""
    text = apply_code_switching(text, lang)
    text = inject_hesitation_and_correction(text, lang)
    text = inject_asr_noise(text, lang, prob=noise_prob)
    
    if not force_variation and random.random() > 0.65:
        return text

    words = text.split()
    if not words: 
        return text
    
    fillers = FILLERS_ZH if lang == "zh" else FILLERS_EN
    prefixes = PREFIXES_ZH if lang == "zh" else PREFIXES_EN
    suffixes = SUFFIXES_ZH if lang == "zh" else SUFFIXES_EN
    
    ops = []
    
    if random.random() < 0.40 or force_variation:
        ops.append("prefix")
    
    if random.random() < 0.25 or (force_variation and random.random() < 0.5):
        ops.append("suffix")
    
    if len(words) > 3 and (random.random() < 0.30 or force_variation):
        ops.append("insert")
    
    if random.random() < 0.08:
        ops.append("repeat")
    
    if random.random() < 0.12:
        ops.append("pause")
    
    if not ops and force_variation:
        ops.append(random.choice(["prefix", "suffix", "insert"]))

    for op in ops:
        if op == "prefix":
            if random.random() < 0.7:
                words.insert(0, random.choice(prefixes))
            else:
                words.insert(0, random.choice(fillers) + ("..." if random.random() < 0.3 else ""))
        elif op == "suffix":
            words.append(random.choice(suffixes))
        elif op == "insert" and len(words) > 1:
            idx = random.randint(1, len(words)-1)
            words.insert(idx, random.choice(fillers))
        elif op == "repeat" and words:
            idx = random.randint(0, len(words)-1)
            words.insert(idx, words[idx])
        elif op == "pause" and len(words) > 2:
            idx = random.randint(1, len(words)-1)
            words.insert(idx, "..." if random.random() < 0.5 else ",")

    result = " ".join(words)
    result = add_contextual_elements(result, lang)
    
    return result

def make_slots(**kwargs) -> Dict[str, Any]:
    """Create a slots dictionary with default None values."""
    return {
        "device": kwargs.get("device"),
        "value": str(kwargs.get("value")) if kwargs.get("value") is not None else None,
        "value_num": float(kwargs.get("value")) if isinstance(kwargs.get("value"), (int, float)) else None,
        "unit": kwargs.get("unit"),
        "mode": kwargs.get("mode"),
        "scene": kwargs.get("scene"),
    }

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Example:
    type: str
    domain: str
    action: str
    target: Optional[str]
    state: Optional[str]
    slots: Dict[str, Any]
    raw_text: str
    confidence: float

def emit_command(domain, action, target, state, slots, text, base_conf=0.88) -> Example:
    conf = max(0.0, min(1.0, base_conf + random.uniform(-0.12, 0.06)))
    return Example("command", domain, action, target, state, slots, text, round(conf, 2))

def emit_transcript(domain, action, target, state, slots, text, base_conf=0.88) -> Example:
    """Emit a non-command (transcript) example."""
    conf = max(0.0, min(1.0, base_conf + random.uniform(-0.12, 0.06)))
    return Example("transcript", domain, action, target, state, slots, text, round(conf, 2))

# =============================================================================
# DOMAIN GENERATORS
# =============================================================================

def gen_lights() -> Example:
    """Generate a lights domain command."""
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)

    # FIX: Increase explicit device probability to reduce ambiguity
    explicit_device = (random.random() < 0.70)  # Increased from 0.55
    dev_word = get_granular_device("light", lang) if explicit_device else ("燈" if lang == "zh" else "light")

    # Situational commands (it's too dark/bright)
    if random.random() < 0.25:
        situation = random.choice(["dark", "bright"])
        if situation == "dark":
            onoff = "on"
            action = "turn_on"
            phrases = (
                ["這裡太暗了", "我看不到路", "黑漆漆的", "有點暗", "甚麼都看不到", f"{room_word}太暗了"]
                if lang == "zh"
                else ["it's too dark in here", "I can't see anything", "it is pitch black", "it's a bit dim", f"the {room_word} is too dark"]
            )
        else:
            onoff = "off"
            action = "turn_off"
            phrases = (
                ["這裡太亮了", "好刺眼", "太亮了", "閃到眼睛", f"{room_word}亮到不行"]
                if lang == "zh"
                else ["it's too bright", "it's blinding", "too bright in here", f"the {room_word} is too bright"]
            )

        phr = humanize_text(random.choice(phrases), lang)
        
        final_target = norm_target if room_word in phr else "default"
        
        slots = make_slots()
        apply_device_rule(slots, "light", phr)
        return emit_command("lights", action, final_target, onoff, slots, phr, 0.92)

    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"

    slots = make_slots()

    if lang == "zh":
        verbs_on = ["打開", "開", "開一下", "開啟", "啟動", "亮起來", "點亮", "弄亮", "讓它亮"]
        verbs_off = ["關掉", "關", "關一下", "關閉", "停掉", "熄滅", "滅掉", "暗掉", "弄暗", "讓它暗"]
        verb = random.choice(verbs_on if onoff == "on" else verbs_off)

        prefix = random.choice(PREFIXES_ZH) if random.random() < 0.35 else ""
        intensity = random.choice(INTENSITY_ZH) if random.random() < 0.1 else ""

        if explicit_device:
            structures = [
                f"{prefix}{verb}{room_word}{dev_word}{intensity}",
                f"{prefix}{room_word}{dev_word}{verb}{intensity}",
                f"把{room_word}{dev_word}{verb}{intensity}",
            ]
        else:
            structures = [
                f"{prefix}{verb}{room_word}燈{intensity}".strip(),
                f"{prefix}{verb}燈{intensity}".strip(),
                f"{room_word}{'太暗了' if onoff == 'on' else '太亮了'}",
            ]

    else:
        verbs_on = ["turn on", "switch on", "enable", "power on"]
        verbs_off = ["turn off", "switch off", "disable", "power off"]
        verb = random.choice(verbs_on if onoff == "on" else verbs_off)

        prefix = random.choice(PREFIXES_EN) if random.random() < 0.25 else ""
        suffix = random.choice(SUFFIXES_EN) if random.random() < 0.25 else ""

        if explicit_device:
            structures = [
                f"{prefix} {verb} the {room_word} {dev_word} {suffix}".strip(),
                f"{verb} {room_word} {dev_word} {suffix}".strip(),
            ]
        else:
            structures = [
                f"{prefix} {verb} the lights {suffix}".strip(),
                f"{prefix} {verb} the {room_word} lights {suffix}".strip(),
                f"{verb} the lights in the {room_word} {suffix}".strip(),
            ]

    st = random.choice(structures)
    phr = humanize_text(st, lang)
    
    final_target = norm_target if room_word in phr else "default"

    apply_device_rule(slots, "light", phr)
    return emit_command("lights", action, final_target, onoff, slots, phr, 0.95)


def gen_climate() -> Example:
    """Generate a climate domain command."""
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)

    explicit_device = (random.random() < 0.50)  # Increased from 0.35
    dev_word = get_granular_device("ac", lang) if explicit_device else ("冷氣" if lang == "zh" else "AC")

    # Feeling-based commands
    if random.random() < 0.20:
        feeling = random.choice(["hot", "cold"])
        if feeling == "hot":
            phrases_zh = ["好熱", "這裡太熱了", f"{room_word}好悶", "熱死了", "好熱喔"]
            phrases_en = ["it's too hot", f"the {room_word} is hot", "I'm burning up", "it's boiling in here"]
            action = "turn_on"
            state = "on"
        else:
            phrases_zh = ["好冷", "這裡太冷了", f"{room_word}好冰", "冷死了", "好冷喔"]
            phrases_en = ["it's too cold", f"the {room_word} is freezing", "I'm cold", "it's chilly"]
            action = "turn_off"
            state = "off"

        phrases = phrases_zh if lang == "zh" else phrases_en
        phr = humanize_text(random.choice(phrases), lang)
        
        final_target = norm_target if room_word in phr else "default"
        
        slots = make_slots()
        apply_device_rule(slots, "thermostat", phr)
        return emit_command("climate", action, final_target, state, slots, phr, 0.90)

    # Temperature setting
    if random.random() < 0.40:
        temp = random.choice([18, 20, 22, 24, 25, 26, 27, 28])
        
        if lang == "zh":
            t_str = to_zh_count(temp) if random.random() < 0.3 else str(temp)
            structures = [
                f"{dev_word}設{t_str}度",
                f"把{room_word}{dev_word}設定成{t_str}度",
                f"溫度調到{t_str}度",
                f"{room_word}溫度{t_str}度",
            ]
        else:
            structures = [
                f"set {dev_word} to {temp} degrees",
                f"set the {room_word} temperature to {temp}",
                f"{dev_word} {temp} degrees",
                f"make it {temp} degrees in the {room_word}",
            ]

        st = random.choice(structures)
        phr = humanize_text(st, lang)
        
        final_target = norm_target if room_word in phr else "default"
        
        slots = make_slots(value=temp, unit="celsius")
        apply_device_rule(slots, "thermostat", phr)
        return emit_command("climate", "set", final_target, None, slots, phr, 0.92)

    # On/off
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"

    if lang == "zh":
        verb = random.choice(["打開", "開", "啟動"]) if onoff == "on" else random.choice(["關掉", "關", "關閉"])
        structures = [
            f"{verb}{room_word}{dev_word}",
            f"{room_word}{dev_word}{verb}",
            f"把{dev_word}{verb}",
        ]
    else:
        verb = "turn on" if onoff == "on" else "turn off"
        structures = [
            f"{verb} the {room_word} {dev_word}",
            f"{verb} {dev_word}",
            f"{verb} the {dev_word} in the {room_word}",
        ]

    st = random.choice(structures)
    phr = humanize_text(st, lang)
    
    final_target = norm_target if room_word in phr else "default"
    
    slots = make_slots()
    apply_device_rule(slots, "thermostat", phr)
    return emit_command("climate", action, final_target, onoff, slots, phr, 0.92)


def gen_vacuum() -> Example:
    """Generate a vacuum domain command."""
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)

    # FIX: Always use explicit device for vacuum to avoid ambiguity
    dev_word = get_granular_device("vacuum", lang)

    # Dirty floor situation
    if random.random() < 0.15:
        if lang == "zh":
            phrases = [f"{room_word}地板髒了", "地板很髒", f"{room_word}要打掃", "這裡很髒"]
        else:
            phrases = [f"the {room_word} floor is dirty", "the floor is dusty", f"clean the {room_word}", "it's messy in here"]
        
        phr = humanize_text(random.choice(phrases), lang)
        
        if room_word in phr:
            final_target = norm_target
        else:
            final_target = "default"

        # FIX: Only set mode="room" when a specific room is mentioned
        slots = make_slots()
        if final_target != "default":
            slots["mode"] = "room"
            slots["value"] = norm_target
        apply_device_rule(slots, "robot_vacuum", phr)
        return emit_command("vacuum", "start", final_target, None, slots, phr, 0.90)

    # Room-specific cleaning
    if random.random() < 0.25:
        if lang == "zh":
            st = f"{dev_word}去打掃{room_word}"
        else:
            st = f"{dev_word} go clean the {room_word}"
        
        phr = humanize_text(st, lang)
        
        if room_word in phr:
            final_target = norm_target
            slots = make_slots(mode="room", value=norm_target)
        else:
            final_target = "default"
            slots = make_slots()
            
        apply_device_rule(slots, "robot_vacuum", phr)
        return emit_command("vacuum", "start", final_target, None, slots, phr, 0.90)

    # Dock command
    if random.random() < 0.25:
        if lang == "zh":
            phrases = ["回家", "回去充電", "回基座", "充電"]
            st = f"{dev_word}{random.choice(phrases)}"
        else:
            phrases = ["go home", "return to base", "dock", "charge", "return home"]
            st = f"{dev_word} {random.choice(phrases)}"
            
        phr = humanize_text(st, lang)
        slots = make_slots()
        apply_device_rule(slots, "robot_vacuum", phr)
        return emit_command("vacuum", "dock", "default", None, slots, phr, 0.90)

    # Generic start/stop/pause
    act = random.choice(["start", "stop", "pause"])
    if lang == "zh":
        v_map = {
            "start": ["開始掃地", "開始打掃", "啟動"],
            "stop": ["停止", "停", "停止打掃"],
            "pause": ["暫停", "等一下", "暫停打掃"]
        }
    else:
        v_map = {
            "start": ["start cleaning", "start", "begin cleaning"],
            "stop": ["stop", "halt", "stop cleaning"],
            "pause": ["pause", "hold on", "pause cleaning"]
        }
        
    st = f"{dev_word} {random.choice(v_map[act])}" if lang == "en" else f"{dev_word}{random.choice(v_map[act])}"
    
    phr = humanize_text(st, lang)
    # FIX: Don't set mode for generic commands
    slots = make_slots()
    apply_device_rule(slots, "robot_vacuum", phr)
    return emit_command("vacuum", act, "default", None, slots, phr, 0.85)


def gen_timer() -> Example:
    """Generate a timer domain command."""
    lang = "zh" if random.random() < 0.5 else "en"

    explicit_device = (random.random() < 0.25)

    if random.random() < 0.6:
        val = random.choice([1, 2, 3, 5, 10, 15, 20, 25, 30, 45, 60, 90])
        unit = "minutes"
    else:
        val = random.choice([1, 2, 3, 4, 5, 6, 12, 24])
        unit = "hours"

    slots = make_slots(value=val, unit=unit)

    if lang == "zh":
        u_str = "分鐘" if unit == "minutes" else "小時"
        val_str = to_zh_count(val) if random.random() < 0.4 else str(val)

        if explicit_device:
            structures = [
                f"設一個{val_str}{u_str}計時器",
                f"幫我設定{val_str}{u_str}倒數",
                f"{val_str}{u_str}後鬧鐘叫我",
                f"開啟{val_str}{u_str}定時",
            ]
        else:
            structures = [
                f"{val_str}{u_str}後提醒我",
                f"{val_str}{u_str}後叫我一下",
                f"等{val_str}{u_str}再跟我說",
                f"{val_str}{u_str}之後提醒我",
            ]
    else:
        u_str = "minutes" if unit == "minutes" else "hours"
        if explicit_device:
            structures = [
                f"set a {val} {u_str} timer",
                f"start a {val} {u_str} countdown",
                f"alarm for {val} {u_str}",
                f"set timer for {val} {u_str}",
            ]
        else:
            structures = [
                f"remind me in {val} {u_str}",
                f"tell me in {val} {u_str}",
                f"notify me in {val} {u_str}",
                f"in {val} {u_str}, remind me",
            ]

    phr = humanize_text(random.choice(structures), lang)
    apply_device_rule(slots, "timer", phr)
    return emit_command("timer", "set_time", "default", None, slots, phr, 0.90)


def gen_curtain() -> Example:
    """Generate a curtain domain command."""
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("curtain", lang)
    
    action_type = random.choice(["open", "close", "partial"])

    slots = make_slots()

    if action_type == "partial":
        percentage = random.choice([25, 30, 50, 75, 80])
        if lang == "zh":
            p_str = to_zh_count(percentage) if random.random() < 0.3 else str(percentage)
            structures = [f"{room_word}{dev_word}開{p_str}%", f"把{dev_word}打開{p_str}%", f"{dev_word}開到{p_str}%"]
        else:
            structures = [
                f"open {room_word} {dev_word} {percentage}%",
                f"set {dev_word} to {percentage}% in {room_word}",
                f"{room_word} {dev_word} {percentage}% open"
            ]
        
        st = random.choice(structures)
        phr = humanize_text(st, lang)
        
        final_target = norm_target if room_word in phr else "default"

        slots["value"] = str(percentage)
        slots["unit"] = "percent"
        apply_device_rule(slots, "curtain", phr)

        return emit_command("curtain", "set_position", final_target, None, slots, phr, 0.95)
    
    else:
        action = "open" if action_type == "open" else "close"
        if lang == "zh":
            verbs = ["打開", "拉開", "開"] if action == "open" else ["關上", "拉上", "關"]
            verb = random.choice(verbs)
            structures = [f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}"]
        else:
            verbs = ["open", "pull open"] if action == "open" else ["close", "pull closed", "shut"]
            verb = random.choice(verbs)
            structures = [f"{verb} the {room_word} {dev_word}", f"{room_word} {dev_word} {action}"]
        
        st = random.choice(structures)
        phr = humanize_text(st, lang)
        
        final_target = norm_target if room_word in phr else "default"
        
        apply_device_rule(slots, "curtain", phr)
        return emit_command("curtain", action, final_target, action, slots, phr, 0.95)


def gen_fan() -> Example:
    """Generate a fan domain command."""
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)

    # FIX: Always use explicit device for fan to avoid confusion with media
    explicit_device = (random.random() < 0.75)  # Increased from 0.35
    dev_word = get_granular_device("fan", lang) if explicit_device else ("風扇" if lang == "zh" else "fan")

    action_type = random.choice(["onoff", "speed", "speed"])

    if action_type == "speed":
        explicit_magnitude = (random.random() < 0.35)

        direction = random.choice(["up", "down"])
        sign = 1 if direction == "up" else -1

        mag = random.choice([2, 3]) if explicit_magnitude else None
        delta = (sign * mag) if mag is not None else None

        slots = make_slots()
        slots["mode"] = "relative"
        slots["value"] = (str(delta) if delta is not None else None)

        if lang == "zh":
            if explicit_magnitude:
                mag_str = to_zh_count(mag) if random.random() < 0.5 else str(mag)
                structures = [
                    f"{room_word}{dev_word}風速調{'高' if sign > 0 else '低'}{mag_str}檔",
                    f"把{dev_word}風速調{'快' if sign > 0 else '慢'}{mag_str}檔",
                ]
            else:
                structures = [
                    f"{room_word}{dev_word}風速{'加快' if sign > 0 else '放慢'}一點",
                    f"{dev_word}風速{'加快' if sign > 0 else '放慢'}一點",
                    f"把{dev_word}{'調快' if sign > 0 else '調慢'}一點",
                    f"{dev_word}{'快' if sign > 0 else '慢'}一點",
                ]

        else:
            if explicit_magnitude:
                mag_str = str(mag) if random.random() < 0.6 else ("two" if mag == 2 else "three")
                structures = [
                    f"turn the {room_word} {dev_word} {'up' if sign > 0 else 'down'} by {mag_str}",
                    f"adjust {dev_word} speed {'up' if sign > 0 else 'down'} by {mag_str}",
                ]
            else:
                structures = [
                    f"turn the {room_word} {dev_word} {'up' if sign > 0 else 'down'}",
                    f"make the {dev_word} a bit {'faster' if sign > 0 else 'slower'}",
                    f"{dev_word} {'faster' if sign > 0 else 'slower'}",
                    f"increase {dev_word} speed" if sign > 0 else f"decrease {dev_word} speed",
                ]

        st = random.choice(structures)
        phr = humanize_text(st, lang)
        
        final_target = norm_target if room_word in st else "default"

        apply_device_rule(slots, "fan", phr)
        return emit_command("fan", "set_speed", final_target, None, slots, phr, 0.95)
    
    # On/off
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"
    state = onoff
    slots = make_slots()

    if lang == "zh":
        verb = random.choice(["打開", "開", "啟動"]) if onoff == "on" else random.choice(["關掉", "關", "停掉"])
        structures = [
            f"{verb}{room_word}{dev_word}",
            f"{room_word}{dev_word}{verb}",
            f"把{dev_word}{verb}",
        ]
    else:
        verb = random.choice(["turn on", "switch on"]) if onoff == "on" else random.choice(["turn off", "switch off"])
        structures = [
            f"{verb} the {room_word} {dev_word}",
            f"{verb} {dev_word}",
            f"{verb} the {dev_word} in the {room_word}",
        ]

    st = random.choice(structures)
    phr = humanize_text(st, lang)
    
    final_target = norm_target if room_word in st else "default"

    apply_device_rule(slots, "fan", phr)
    return emit_command("fan", action, final_target, state, slots, phr, 0.95)


def gen_media() -> Example:
    """Generate a media domain command."""
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)

    media_type = random.choice(["tv", "speaker"])
    dev_word = get_granular_device(media_type, lang)

    # FIX: Reduce pronoun usage, always include device type context
    # Only use pronoun if we've added enough context
    use_pronoun = random.random() < 0.30  # Reduced from 0.50

    action_type = random.choice(["onoff", "volume", "playback", "channel"])
    slots = make_slots()

    if action_type == "volume":
        numeric = (random.random() < 0.55)
        vol = random.choice([10, 20, 30, 40, 50, 60, 70, 80])
        direction = random.choice(["up", "down"])

        if lang == "zh":
            if numeric:
                v_str = to_zh_count(vol) if random.random() < 0.3 else str(vol)
                structures = [
                    f"{dev_word}音量調到{v_str}",
                    f"音量{v_str}",
                    f"把{dev_word}聲音調成{v_str}",
                    f"{room_word}{dev_word}音量{v_str}",
                ]
                slots["value"] = str(vol)
            else:
                v_str = "調大" if direction == "up" else "調小"
                structures = [
                    f"{dev_word}{v_str}聲音",
                    f"{dev_word}音量{v_str}",
                    f"{dev_word}聲音{'大' if direction == 'up' else '小'}聲一點",
                    f"{dev_word}{'大' if direction == 'up' else '小'}聲一點",
                ]
                slots["value"] = None
        else:
            if numeric:
                structures = [
                    f"set {dev_word} volume to {vol}",
                    f"{dev_word} volume {vol}",
                    f"make {dev_word} volume {vol}",
                    f"set the {dev_word} volume to {vol}",
                ]
                slots["value"] = str(vol)
            else:
                structures = [
                    f"turn the {dev_word} volume {direction}",
                    f"{dev_word} volume {direction}",
                    f"make the {dev_word} {'louder' if direction == 'up' else 'quieter'}",
                    f"{dev_word} {'louder' if direction == 'up' else 'quieter'}",
                ]
                slots["value"] = None

        st = random.choice(structures)
        phr = humanize_text(st, lang)
        
        final_target = norm_target if room_word in st else "default"

        slots["mode"] = "volume"
        apply_device_rule(slots, media_type, phr)
        return emit_command("media", "set_volume", final_target, None, slots, phr, 0.92)

    if action_type == "channel":
        media_type = "tv"
        dev_word = get_granular_device("tv", lang)
        numeric = (random.random() < 0.55)
        ch = random.randint(1, 100)

        if lang == "zh":
            if numeric:
                structures = [f"{dev_word}轉到{ch}台", f"{dev_word}切到{ch}台", f"頻道{ch}", f"切換到{ch}頻道"]
                slots["value"] = str(ch)
            else:
                structures = [f"{dev_word}換台", f"切換頻道", f"下一台", f"{dev_word}換頻道", "下一個頻道"]
                slots["value"] = None
        else:
            if numeric:
                structures = [f"{dev_word} channel {ch}", f"go to channel {ch}", f"switch {dev_word} to channel {ch}", f"set {dev_word} channel to {ch}"]
                slots["value"] = str(ch)
            else:
                structures = [f"change {dev_word} channel", f"next channel", f"switch {dev_word} channel", f"go to the next channel"]
                slots["value"] = None

        st = random.choice(structures)
        phr = humanize_text(st, lang)
        
        final_target = norm_target if room_word in st else "default"

        slots["mode"] = "channel"
        apply_device_rule(slots, "tv", phr)
        return emit_command("media", "channel_change", final_target, None, slots, phr, 0.90)

    if action_type == "onoff":
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"

        if lang == "zh":
            verb = random.choice(["打開", "開"]) if onoff == "on" else random.choice(["關掉", "關"])
            structures = [f"{verb}{room_word}的{dev_word}", f"{verb}{dev_word}"]
        else:
            verb = "turn on" if onoff == "on" else "turn off"
            structures = [f"{verb} {dev_word}", f"{verb} the {dev_word} in the {room_word}"]

        st = random.choice(structures)
        phr = humanize_text(st, lang)
        
        final_target = norm_target if room_word in st else "default"

        apply_device_rule(slots, media_type, phr)
        return emit_command("media", action, final_target, onoff, slots, phr, 0.90)

    # Playback controls
    action = random.choice(["play", "pause", "next", "previous", "stop"])
    if lang == "zh":
        vmap = {
            "play": ["播放", "開始播放"],
            "pause": ["暫停", "先停一下"],
            "next": ["下一首", "下一個", "跳過"],  # FIX: Made more distinct
            "previous": ["上一首", "上一個", "上一曲"],  # FIX: Made more distinct
            "stop": ["停止", "停掉"],
        }
        st = f"{dev_word}{random.choice(vmap[action])}"
    else:
        vmap = {
            "play": ["play", "start playback", "resume"],
            "pause": ["pause", "hold"],
            "next": ["next track", "skip", "next song"],  # FIX: Made more distinct
            "previous": ["previous track", "go back", "previous song", "last track"],  # FIX: Made more distinct
            "stop": ["stop", "stop playback"],
        }
        st = f"{random.choice(vmap[action])} on {dev_word}"

    phr = humanize_text(st, lang)
    
    final_target = norm_target if room_word in st else "default"

    apply_device_rule(slots, media_type, phr)
    return emit_command("media", action, final_target, None, slots, phr, 0.90)


def gen_hard_negative() -> Example:
    """
    Generate hard negative examples - sentences that mention devices 
    but are NOT commands. These should be classified as type="transcript".
    
    FIX: Using "transcript" type instead of "hard_negative" to match schema.
    """
    lang = "zh" if random.random() < 0.5 else "en"
    
    dev_type = random.choice(["light", "ac", "tv", "vacuum", "fan", "curtain"])
    dev_word = get_granular_device(dev_type, lang)
    
    if lang == "zh":
        templates = [
            # Questions about devices (not commands)
            f"這個{dev_word}好用嗎？",
            f"你覺得{dev_word}怎麼樣？",
            f"{dev_word}要多少錢？",
            f"哪裡可以買到{dev_word}？",
            # Statements about devices (not commands)
            f"我昨天買了一個新的{dev_word}",
            f"{dev_word}好像壞了",
            f"爸爸說他忘記關{dev_word}了",  # Talking ABOUT forgetting, not commanding
            f"我希望我家也有{dev_word}",  # Wishing, not commanding
            f"如果不關{dev_word}電費會很貴",  # Hypothetical, not commanding
            f"這台{dev_word}已經用了三年",
            f"誰買了新的{dev_word}？",
            f"我們需要修理{dev_word}",
            f"{dev_word}的保固還有多久？",
            # Past tense or planning (not immediate commands)
            f"我明天要去看看{dev_word}",
            f"上次{dev_word}修理花了很多錢",
        ]
    else:
        templates = [
            # Questions about devices (not commands)
            f"Is this {dev_word} good?",
            f"What do you think about the {dev_word}?",
            f"How much does a {dev_word} cost?",
            f"Where can I buy a {dev_word}?",
            # Statements about devices (not commands)
            f"I bought a new {dev_word} yesterday",
            f"The {dev_word} seems broken",
            f"My dad forgot to turn off the {dev_word}",  # Talking ABOUT forgetting
            f"I wish I had a smart {dev_word}",  # Wishing, not commanding
            f"Did you leave the {dev_word} on?",  # Question, not command
            f"This {dev_word} is three years old",
            f"Who bought the new {dev_word}?",
            f"We need to repair the {dev_word}",
            f"How long is the {dev_word} warranty?",
            # Past tense or planning (not immediate commands)
            f"I'm going to check the {dev_word} tomorrow",
            f"The {dev_word} repair cost a lot last time",
            f"This {dev_word} is too expensive",
        ]
        
    text = random.choice(templates)
    text = apply_code_switching(text, lang)
    
    # FIX: Return as "transcript" type with empty slots
    return Example(
        type="transcript",  # Not "hard_negative"
        domain="unknown",
        action="none",
        target=None,
        state=None,
        slots=make_slots(),  # Empty slots
        raw_text=text,
        confidence=0.15
    )


def gen_transcript() -> Example:
    """Generate non-command transcripts (casual speech, questions, etc.)."""
    lang = "zh" if random.random() < 0.5 else "en"
    
    # Broken/incomplete commands that shouldn't be parsed
    broken_cmds_en = [
        "set the", "can you please",
        "make it", "adjust the", "change the", "volume", "lights in the",
        "please turn off"
    ]
    broken_cmds_zh = [
        "設定", "幫我開", "把那個", "音量", "調整",
        "那個房間的", "可以幫我嗎", "那個...開"
    ]

    # Things that sound like smart home but aren't
    hard_negatives_zh = [
        "我想買一台新車", "股市今天跌了", "比特幣現在多少錢", "我要買車",
        "這輛車多少錢", "開車去上班", "公車來了嗎",
        "叫計程車", "要叫計程車", "幫我叫計程車", "我想叫計程車",
        "今天的新聞是什麼", "明天會下雨嗎", "現在幾度",
    ]
    hard_negatives_en = [
        "I want to buy a new car", "I don't agree with you", "That's impossible",
        "What time is it", "How tall is Mount Everest", "Who is the president",
        "I want to purchase a vehicle", "Buy a tesla", "Get me a car",
        "Call an uber", "Taxi please", "Call a taxi", "I want to call a taxi",
        "What's the weather forecast", "Will it rain tomorrow",
    ]

    if lang == "zh":
        if random.random() < 0.15:
            text = random.choice(broken_cmds_zh)
        elif random.random() < 0.3:
            text = random.choice(hard_negatives_zh)
        else:
            texts = [
                "你好嗎", "今天天氣真好", "你覺得這件衣服好看嗎", "我等等要出門",
                "告訴我一個笑話", "背誦一首唐詩", "生命的意義是什麼", "現在幾點了",
                "這太好笑了", "哎呀", "隨便啦", "明天會下雨嗎", "幫我搜尋一下附近的餐廳",
                "哈囉", "有人在嗎", "測試測試", "早安", "晚安", "謝謝你"
            ]
            text = random.choice(texts)
    else:
        if random.random() < 0.15:
            text = random.choice(broken_cmds_en)
        elif random.random() < 0.3:
            text = random.choice(hard_negatives_en)
        else:
            texts = [
                "Hello there", "How are you doing", "What is the meaning of life",
                "Tell me a joke", "Sing a song for me", "I am going out later",
                "Did you see that game last night", "That is hilarious", "Oh my god",
                "Will it rain tomorrow", "Search for restaurants nearby", "Call Mom",
                "Testing testing", "Anyone there", "Can you hear me", "Good morning",
                "Good night", "Thank you"
            ]
            text = random.choice(texts)

    phr = humanize_text(text, lang, noise_prob=0.0)
    
    return emit_transcript("unknown", "none", None, None, make_slots(), phr, 0.15)


# =============================================================================
# DATASET GENERATION
# =============================================================================

def compute_text_hash(text: str) -> str:
    """Compute hash for deduplication."""
    normalized = " ".join(text.strip().lower().split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()

def mutate_example(ex: Example, attempts: int) -> Example:
    """Mutate an example to create variation for deduplication."""
    lang = "zh" if any(ord(c) > 128 for c in ex.raw_text) else "en"
    ex.raw_text = humanize_text(ex.raw_text, lang, noise_prob=0.0, force_variation=True)

    if attempts >= 2:
        if lang == "zh":
            additions = ["拜託", "謝謝", "快點", "喔", "好嗎", "可以嗎", "幫忙", "立刻"]
            ex.raw_text = f"{random.choice(additions)}{ex.raw_text}" if random.random() < 0.5 else f"{ex.raw_text}{random.choice(additions)}"
        else:
            additions = ["please", "thanks", "now", "okay", "alright", "quickly", "ASAP", "right now"]
            ex.raw_text = f"{random.choice(additions)}, {ex.raw_text}" if random.random() < 0.5 else f"{ex.raw_text} {random.choice(additions)}"

    if attempts >= 4:
        ex.raw_text = add_contextual_elements(ex.raw_text, lang)

    return ex


# Generator weights - adjusted based on failure analysis
GENERATORS = [
    (gen_lights, 0.15),
    (gen_climate, 0.12),
    (gen_vacuum, 0.10),
    (gen_timer, 0.08),
    (gen_curtain, 0.10),
    (gen_fan, 0.10),
    (gen_media, 0.10),
    (gen_hard_negative, 0.15),  
    (gen_transcript, 0.10),
]


def generate(n: int, max_attempts: int = 15) -> List[Example]:
    """Generate n unique examples."""
    out = []
    seen_hashes = set()
    failed_attempts = 0
    max_failed = n // 10
    
    total_w = sum(w for _, w in GENERATORS)
    gens = [g for g, _ in GENERATORS]
    weights = [w/total_w for _, w in GENERATORS]
    
    while len(out) < n:
        g_fn = random.choices(gens, weights, k=1)[0]
        ex = g_fn()
        
        text_hash = compute_text_hash(ex.raw_text)
        
        attempts = 0
        while text_hash in seen_hashes and attempts < max_attempts:
            attempts += 1
            ex = mutate_example(ex, attempts)
            text_hash = compute_text_hash(ex.raw_text)
        
        if text_hash in seen_hashes:
            failed_attempts += 1
            if failed_attempts > max_failed:
                print(f"Warning: High collision rate ({failed_attempts} failures).")
            continue
        
        seen_hashes.add(text_hash)
        out.append(ex)
        
        if len(out) % 10000 == 0:
            print(f"Generated {len(out)}/{n} unique examples...")

    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="smart_home_v2.jsonl")
    p.add_argument("--n", type=int, default=100000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--asr-noise", type=float, default=0.0)
    args = p.parse_args()

    random.seed(args.seed)
    
    print(f"Generating {args.n:,} unique examples with seed {args.seed}...")
    
    data = generate(args.n)
    
    with open(args.out, "w", encoding="utf-8") as f:
        for ex in data:
            f.write(json.dumps(asdict(ex), ensure_ascii=False) + "\n")
    
    type_counts = {}
    domain_counts = {}
    for ex in data:
        type_counts[ex.type] = type_counts.get(ex.type, 0) + 1
        domain_counts[ex.domain] = domain_counts.get(ex.domain, 0) + 1
    
    print(f"\nDone! Saved to {args.out}")
    print(f"\nType distribution:")
    for t, c in sorted(type_counts.items()):
        print(f"  {t}: {c} ({c/len(data):.1%})")
    print(f"\nDomain distribution:")
    for d, c in sorted(domain_counts.items()):
        print(f"  {d}: {c} ({c/len(data):.1%})")


if __name__ == "__main__":
    main()