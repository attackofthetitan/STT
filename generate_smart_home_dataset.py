import json
import random
import argparse
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
import hashlib

random.seed(42)

# =============================================================================
# SCHEMA ALIGNMENT
# =============================================================================

CANONICAL_TYPES = ["command", "transcript"]
CANONICAL_DOMAINS = ["lights", "climate", "vacuum", "timer", "curtain", "fan", "media", "unknown"]
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
CANONICAL_DEVICES = ["light", "thermostat", "robot_vacuum", "timer", "curtain", "fan", "tv", "speaker"]

# =============================================================================
# ROOM DEFINITIONS
# =============================================================================

ROOMS = [r for r in CANONICAL_TARGETS if r != "default"]

ROOM_ALIASES_ZH = {
    "bathroom": ["廁所", "浴室", "洗手間"],
    "kitchen": ["廚房"],
    "bedroom": ["臥室", "主臥", "臥房"],
    "living_room": ["客廳"],
    "dining_room": ["餐廳", "飯廳"],
    "study": ["書房", "辦公室"],
    "balcony": ["陽台", "露台"],
    "hallway": ["走廊", "走道"],
    "entryway": ["玄關", "門口"],
    "garage": ["車庫"],
    "basement": ["地下室"],
    "attic": ["閣樓"],
    "laundry_room": ["洗衣間", "洗衣房"],
    "closet": ["衣櫃間", "儲物間"],
    "guest_room": ["客房"],
    "nursery": ["嬰兒房", "兒童房"],
    "default": ["家裡", "全部", "全屋"],
}

ROOM_ALIASES_EN = {
    "bathroom": ["bathroom", "restroom"],
    "kitchen": ["kitchen"],
    "bedroom": ["bedroom", "master bedroom"],
    "living_room": ["living room", "lounge"],
    "dining_room": ["dining room"],
    "study": ["study", "office"],
    "balcony": ["balcony", "patio", "porch"],
    "hallway": ["hallway", "corridor", "hall"],
    "entryway": ["entryway", "foyer", "entrance"],
    "garage": ["garage"],
    "basement": ["basement", "cellar"],
    "attic": ["attic", "loft"],
    "laundry_room": ["laundry room", "laundry"],
    "closet": ["closet", "storage room"],
    "guest_room": ["guest room", "spare room"],
    "nursery": ["nursery", "baby room", "kids room"],
    "default": ["the house", "everywhere"],
}

# Build a combined lookup for detecting rooms in text
def build_room_detection_map() -> Dict[str, str]:
    """
    Build a map from all room aliases (lowercased) to their canonical room name.
    This is used to detect which room (if any) is mentioned in the final text.
    """
    detection_map = {}
    for room, aliases in ROOM_ALIASES_ZH.items():
        if room == "default":
            continue  # Don't detect "default" aliases as specific rooms
        for alias in aliases:
            detection_map[alias.lower()] = room
    for room, aliases in ROOM_ALIASES_EN.items():
        if room == "default":
            continue
        for alias in aliases:
            detection_map[alias.lower()] = room
    return detection_map

ROOM_DETECTION_MAP = build_room_detection_map()

def detect_room_in_text(text: str) -> Optional[str]:
    """
    Scan the text for any known room alias and return the canonical room name.
    Returns None if no room is detected (should use "default" as target).
    
    Checks longer aliases first to avoid partial matches.
    Uses word boundaries for short English words to avoid false positives
    (e.g., "floor" should not match "loo").
    """
    import re
    text_lower = text.lower()
    
    # Sort aliases by length (descending) to match longer phrases first
    sorted_aliases = sorted(ROOM_DETECTION_MAP.keys(), key=len, reverse=True)
    
    for alias in sorted_aliases:
        # For short English words (<=4 chars, ASCII only), require word boundaries
        # This prevents "floor" from matching "loo", "den" from matching "garden", etc.
        if len(alias) <= 4 and alias.isascii():
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_lower):
                return ROOM_DETECTION_MAP[alias]
        else:
            # For longer phrases or non-ASCII (Chinese), simple substring match is fine
            if alias in text_lower:
                return ROOM_DETECTION_MAP[alias]
    
    return None


# =============================================================================
# OTHER DEFINITIONS
# =============================================================================

PERSON_NAMES_ZH = ["爸爸", "媽媽", "哥哥", "妹妹", "阿嬤", "爺爺", "小寶", "老婆", "老公"]
PERSON_NAMES_EN = ["Mom", "Dad", "Alice", "Bob", "Grandma", "Tommy", "Honey"]

ADJECTIVES_ZH = ["主", "大", "小", "天花板", "智慧", "舊", "新", "紅色", "藍色", "黃色", "角落", "牆壁"]
ADJECTIVES_EN = ["main", "big", "small", "ceiling", "floor", "smart", "old", "new", "red", "blue", "corner", "wall"]

HOMOPHONES_ZH = {
    "幫我": ["邦我", "幫偶"],
    "打開": ["達開", "大開"],
    "冷氣": ["冷器", "冷企"],
    "客廳": ["客聽", "刻廳"],
    "廚房": ["除房", "儲房"],
    "關掉": ["關吊", "觀掉"],
}

HOMOPHONES_EN = {
    "light": ["right", "lite"],
    "lights": ["rights", "lites"],
    "fan": ["van", "fin"],
    "off": ["of", "awf"],
    "on": ["an", "own"],
}

DEVICE_VARIANTS_EN = {
    "light": ["light", "lights", "lamp", "lamps", "LEDs", "ceiling light", "bulbs", "lantern"],
    "ac": ["AC", "air conditioner", "thermostat", "climate control", "HVAC", "heater"],
    "tv": ["TV", "television", "telly", "screen", "display", "smart TV"],
    "vacuum": ["vacuum", "robot vacuum", "roomba", "sweeper", "cleaner", "vac"],
    "curtain": ["curtain", "curtains", "drapes", "shades", "blinds", "shutters", "window shades", "window blinds", "roller shades", "blackout curtains"],
    "fan": ["fan", "ceiling fan", "standing fan", "ventilator", "desk fan"],
    "speaker": ["speaker", "stereo", "sound system", "audio", "smart speaker", "music"],
}

DEVICE_VARIANTS_ZH = {
    "light": ["燈", "電燈", "照明", "檯燈", "吊燈", "吸頂燈", "LED燈", "燈泡", "夜燈"],
    "ac": ["冷氣", "空調", "冷氣機", "恆溫器", "暖氣"],
    "tv": ["電視", "電視機", "螢幕", "顯示器", "智慧電視"],
    "vacuum": ["掃地機", "吸塵器", "掃地機器人", "拖地機", "清潔機器人"],
    "curtain": ["窗簾", "布簾", "百葉窗", "捲簾", "遮光簾"],
    "fan": ["風扇", "電風扇", "吊扇", "循環扇", "立扇"],
    "speaker": ["喇叭", "音響", "揚聲器", "播放器", "智慧音箱"],
}

EXPLICIT_DEVICE_KEYWORDS = {
    "light": list({*(DEVICE_VARIANTS_EN.get("light", [])), *(DEVICE_VARIANTS_ZH.get("light", []))}),
    "thermostat": list({*(DEVICE_VARIANTS_EN.get("ac", [])), *(DEVICE_VARIANTS_ZH.get("ac", []))}),
    "robot_vacuum": list({*(DEVICE_VARIANTS_EN.get("vacuum", [])), *(DEVICE_VARIANTS_ZH.get("vacuum", []))}),
    "curtain": list({*(DEVICE_VARIANTS_EN.get("curtain", [])), *(DEVICE_VARIANTS_ZH.get("curtain", []))}),
    "fan": list({*(DEVICE_VARIANTS_EN.get("fan", [])), *(DEVICE_VARIANTS_ZH.get("fan", []))}),
    "tv": list({*(DEVICE_VARIANTS_EN.get("tv", [])), *(DEVICE_VARIANTS_ZH.get("tv", []))}),
    "speaker": list({*(DEVICE_VARIANTS_EN.get("speaker", [])), *(DEVICE_VARIANTS_ZH.get("speaker", []))}),
    "timer": ["timer", "countdown", "alarm", "計時器", "倒數", "定時", "鬧鐘"],
}

FILLERS_EN = ["uh", "um", "like", "you know", "actually", "please", "well", "okay", "just", "hey"]
FILLERS_ZH = ["那個", "呃", "嗯", "就是", "麻煩", "欸", "我想", "喔", "好", "這個"]

PREFIXES_EN = ["Could you", "Please", "Can you", "Hey,", "Just", "Help me", "Kindly"]
PREFIXES_ZH = ["麻煩", "請", "幫我", "可以幫我", "欸", "我想", "幫忙"]

SUFFIXES_EN = ["please", "thanks", "now", "right now", "quickly", "okay"]
SUFFIXES_ZH = ["謝謝", "拜託", "快點", "馬上", "現在", "好嗎", "喔"]

CORRECTIONS_ZH = ["不對", "我是說", "等一下", "不", "改一下"]
CORRECTIONS_EN = ["wait", "no", "I mean", "actually", "hold on"]

TIME_EXPRESSIONS_EN = ["in a minute", "later", "soon", "after dinner", "before bed"]
TIME_EXPRESSIONS_ZH = ["等一下", "待會", "稍後", "睡前", "現在"]

INTENSITY_EN = ["very", "really", "a bit", "slightly", "completely"]
INTENSITY_ZH = ["很", "非常", "有點", "稍微", "完全"]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def to_zh_count(n: int) -> str:
    if n == 2: return random.choice(["兩", "二"])
    mapping = {0:"零", 1:"一", 2:"二", 3:"三", 4:"四", 5:"五", 6:"六", 7:"七", 8:"八", 9:"九", 10:"十"}
    if 10 < n < 20:
        return "十" + mapping.get(n-10, str(n-10))
    if 20 <= n < 100:
        tens, ones = n // 10, n % 10
        return mapping[tens] + "十" + (mapping.get(ones, "") if ones else "")
    return mapping.get(n, str(n))

def pick_room(weight_default: float = 0.20) -> str:
    if random.random() < weight_default:
        return "default"
    return random.choice(ROOMS)

def pick_room_word(room: str, lang: str) -> str:
    """Pick a random alias for the given room in the given language."""
    if room == "default":
        aliases = ROOM_ALIASES_ZH["default"] if lang == "zh" else ROOM_ALIASES_EN["default"]
    else:
        aliases = ROOM_ALIASES_ZH.get(room, []) if lang == "zh" else ROOM_ALIASES_EN.get(room, [])
    if not aliases:
        return room
    return random.choice(aliases)

def get_granular_device(dev_type: str, lang: str) -> str:
    variants = DEVICE_VARIANTS_ZH if lang == "zh" else DEVICE_VARIANTS_EN
    adjectives = ADJECTIVES_ZH if lang == "zh" else ADJECTIVES_EN
    
    base = random.choice(variants.get(dev_type, [dev_type]))
    
    if random.random() < 0.25:
        adj = random.choice(adjectives)
        return f"{adj}{base}" if lang == "zh" else f"{adj} {base}"
    
    if random.random() < 0.08:
        num = random.randint(1, 3)
        num_str = to_zh_count(num) if lang == "zh" else str(num)
        return f"{num_str}號{base}" if lang == "zh" else f"{base} {num_str}"
    
    return base

def inject_asr_noise(text: str, lang: str, prob: float = 0.0) -> str:
    if random.random() > prob:
        return text
    homophones = HOMOPHONES_ZH if lang == "zh" else HOMOPHONES_EN
    if lang == "en":
        words = text.split()
        new_tokens = []
        for w in words:
            lw = w.lower()
            if lw in homophones and random.random() < 0.4:
                new_tokens.append(random.choice(homophones[lw]))
            else:
                new_tokens.append(w)
        return " ".join(new_tokens)
    else:
        out = text
        for k, v in homophones.items():
            if k in out and random.random() < 0.4:
                out = out.replace(k, random.choice(v), 1)
        return out

def apply_code_switching(text: str, main_lang: str) -> str:
    """Mix languages - replace a room name with its equivalent in the other language."""
    if random.random() > 0.35:
        return text
    
    if main_lang == "zh":
        for room, aliases in ROOM_ALIASES_ZH.items():
            if room == "default":
                continue
            for alias in aliases:
                if alias in text:
                    replacement = random.choice(ROOM_ALIASES_EN.get(room, [room]))
                    return text.replace(alias, f" {replacement} ", 1).strip()
    else:
        for room, aliases in ROOM_ALIASES_EN.items():
            if room == "default":
                continue
            for alias in aliases:
                # Check with word boundaries
                if f" {alias} " in f" {text} " or text.lower().startswith(alias.lower()) or text.lower().endswith(alias.lower()):
                    replacement = random.choice(ROOM_ALIASES_ZH.get(room, [room]))
                    # Case-insensitive replace
                    import re
                    pattern = re.compile(re.escape(alias), re.IGNORECASE)
                    return pattern.sub(replacement, text, count=1)
    return text

def inject_hesitation_and_correction(text: str, lang: str) -> str:
    if random.random() > 0.30:  # Increased from 0.15 for better correction coverage
        return text
    corrections = CORRECTIONS_ZH if lang == "zh" else CORRECTIONS_EN
    fake_actions = ["關掉", "打開", "設定"] if lang == "zh" else ["Turn off", "Open", "Set"]
    fake = random.choice(fake_actions)
    correction = random.choice(corrections)
    return f"{fake}...{correction}，{text}" if lang == "zh" else f"{fake}... {correction}, {text}"

def humanize_text(text: str, lang: str, noise_prob: float = 0.0) -> str:
    """Add natural speech patterns - fillers, prefixes, suffixes, code-switching."""
    text = apply_code_switching(text, lang)
    text = inject_hesitation_and_correction(text, lang)
    text = inject_asr_noise(text, lang, prob=noise_prob)
    
    if random.random() > 0.60:
        return text

    fillers = FILLERS_ZH if lang == "zh" else FILLERS_EN
    prefixes = PREFIXES_ZH if lang == "zh" else PREFIXES_EN
    suffixes = SUFFIXES_ZH if lang == "zh" else SUFFIXES_EN
    
    words = text.split()
    if not words:
        return text
    
    if random.random() < 0.35:
        words.insert(0, random.choice(prefixes))
    if random.random() < 0.20:
        words.append(random.choice(suffixes))
    if len(words) > 3 and random.random() < 0.20:
        idx = random.randint(1, len(words)-1)
        words.insert(idx, random.choice(fillers))
    
    return " ".join(words)

def make_slots(**kwargs) -> Dict[str, Any]:
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
    conf = max(0.0, min(1.0, base_conf + random.uniform(-0.10, 0.05)))
    return Example("command", domain, action, target, state, slots, text, round(conf, 2))

def emit_transcript(domain, action, target, state, slots, text, base_conf=0.15) -> Example:
    conf = max(0.0, min(1.0, base_conf + random.uniform(-0.10, 0.05)))
    return Example("transcript", domain, action, target, state, slots, text, round(conf, 2))


def finalize_target(text: str) -> str:
    """
    Determine the target based on what room aliases appear in the FINAL text.
    This is the KEY FUNCTION - it ensures ground truth matches what model can see.
    """
    detected = detect_room_in_text(text)
    return detected if detected else "default"


# =============================================================================
# DOMAIN GENERATORS
# =============================================================================

def gen_lights() -> Example:
    """Generate a lights domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"
    
    # Sometimes include room, sometimes not
    include_room_in_structure = (base_room != "default") and (random.random() < 0.75)
    room_word = pick_room_word(base_room, lang) if include_room_in_structure else ""

    explicit_device = random.random() < 0.70
    dev_word = get_granular_device("light", lang) if explicit_device else ("燈" if lang == "zh" else "light")

    # Situational commands - increased to 30% for more "human" inference training
    if random.random() < 0.30:
        situation = random.choice(["dark", "bright", "dark", "dark"])  # Bias toward dark (more common)
        if situation == "dark":
            onoff, action = "on", "turn_on"
            if lang == "zh":
                if include_room_in_structure:
                    phrases = [f"{room_word}太暗了", f"{room_word}看不到", f"{room_word}黑黑的"]
                else:
                    phrases = ["這裡太暗了", "看不到路", "有點暗", "好暗", "看不清楚", "黑漆漆的", "太暗了"]
            else:
                if include_room_in_structure:
                    phrases = [f"the {room_word} is too dark", f"it's dark in the {room_word}", f"can't see in the {room_word}"]
                else:
                    phrases = ["it's too dark", "I can't see", "it's dim", "too dark", "can't see anything", "it's pitch black", "I need some light"]
        else:
            onoff, action = "off", "turn_off"
            if lang == "zh":
                if include_room_in_structure:
                    phrases = [f"{room_word}太亮了", f"{room_word}好刺眼"]
                else:
                    phrases = ["這裡太亮了", "好刺眼", "太亮了", "眼睛好痛", "亮到受不了"]
            else:
                if include_room_in_structure:
                    phrases = [f"the {room_word} is too bright", f"too bright in the {room_word}"]
                else:
                    phrases = ["it's too bright", "it's blinding", "too bright", "my eyes hurt", "way too bright"]

        raw_text = humanize_text(random.choice(phrases), lang)
        final_target = finalize_target(raw_text)  # Detect from final text!
        slots = make_slots(device="light")
        return emit_command("lights", action, final_target, onoff, slots, raw_text, 0.92)

    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"
    slots = make_slots(device="light")

    if lang == "zh":
        verbs = ["打開", "開", "開啟"] if onoff == "on" else ["關掉", "關", "關閉"]
        verb = random.choice(verbs)
        if include_room_in_structure:
            structures = [f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}", f"把{room_word}{dev_word}{verb}"]
        else:
            structures = [f"{verb}{dev_word}", f"把{dev_word}{verb}"]
    else:
        verbs = ["turn on", "switch on"] if onoff == "on" else ["turn off", "switch off"]
        verb = random.choice(verbs)
        if include_room_in_structure:
            structures = [f"{verb} the {room_word} {dev_word}", f"{verb} {room_word} {dev_word}"]
        else:
            structures = [f"{verb} the {dev_word}", f"{verb} {dev_word}"]

    st = random.choice(structures)
    raw_text = humanize_text(st, lang)
    final_target = finalize_target(raw_text)  # Detect from final text!
    return emit_command("lights", action, final_target, onoff, slots, raw_text, 0.95)


def gen_climate() -> Example:
    """Generate a climate domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"
    
    include_room_in_structure = (base_room != "default") and (random.random() < 0.70)
    room_word = pick_room_word(base_room, lang) if include_room_in_structure else ""

    explicit_device = random.random() < 0.55
    dev_word = get_granular_device("ac", lang) if explicit_device else ("冷氣" if lang == "zh" else "AC")

    # Feeling-based commands - increased to 25% for more "human" inference
    if random.random() < 0.25:
        feeling = random.choice(["hot", "cold", "hot", "hot"])  # Bias toward hot (more common AC use case)
        if feeling == "hot":
            if lang == "zh":
                if include_room_in_structure:
                    phrases = [f"{room_word}好悶", f"{room_word}好熱", f"{room_word}太熱了"]
                else:
                    phrases = ["好熱", "太熱了", "熱死了", "好悶", "快中暑了", "流汗了", "受不了這個熱"]
            else:
                if include_room_in_structure:
                    phrases = [f"the {room_word} is hot", f"it's too hot in the {room_word}", f"the {room_word} is stuffy"]
                else:
                    phrases = ["it's too hot", "I'm burning up", "it's so hot", "I'm sweating", "it's stuffy", "the heat is killing me"]
            action, state = "turn_on", "on"
        else:
            if lang == "zh":
                if include_room_in_structure:
                    phrases = [f"{room_word}好冰", f"{room_word}好冷", f"{room_word}太冷了"]
                else:
                    phrases = ["好冷", "太冷了", "冷死了", "發抖了", "冷到受不了"]
            else:
                if include_room_in_structure:
                    phrases = [f"the {room_word} is freezing", f"it's cold in the {room_word}"]
                else:
                    phrases = ["it's too cold", "I'm freezing", "it's freezing", "I'm shivering", "way too cold"]
            action, state = "turn_off", "off"

        raw_text = humanize_text(random.choice(phrases), lang)
        final_target = finalize_target(raw_text)
        slots = make_slots(device="thermostat")
        return emit_command("climate", action, final_target, state, slots, raw_text, 0.90)

    # Temperature setting
    if random.random() < 0.35:
        temp = random.choice([18, 20, 22, 24, 25, 26, 27, 28])
        if lang == "zh":
            t_str = to_zh_count(temp) if random.random() < 0.3 else str(temp)
            if include_room_in_structure:
                structures = [f"{room_word}{dev_word}設{t_str}度", f"把{room_word}溫度調到{t_str}度"]
            else:
                structures = [f"{dev_word}設{t_str}度", f"溫度調到{t_str}度"]
        else:
            if include_room_in_structure:
                structures = [f"set {room_word} {dev_word} to {temp} degrees", f"set the {room_word} temperature to {temp}"]
            else:
                structures = [f"set {dev_word} to {temp} degrees", f"set temperature to {temp}"]

        st = random.choice(structures)
        raw_text = humanize_text(st, lang)
        final_target = finalize_target(raw_text)
        slots = make_slots(device="thermostat", value=temp, unit="celsius")
        return emit_command("climate", "set", final_target, None, slots, raw_text, 0.92)

    # On/off
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"

    if lang == "zh":
        verb = random.choice(["打開", "開", "啟動"]) if onoff == "on" else random.choice(["關掉", "關", "關閉"])
        if include_room_in_structure:
            structures = [f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}"]
        else:
            structures = [f"{verb}{dev_word}", f"把{dev_word}{verb}"]
    else:
        verb = "turn on" if onoff == "on" else "turn off"
        if include_room_in_structure:
            structures = [f"{verb} the {room_word} {dev_word}", f"{verb} {dev_word} in the {room_word}"]
        else:
            structures = [f"{verb} the {dev_word}", f"{verb} {dev_word}"]

    st = random.choice(structures)
    raw_text = humanize_text(st, lang)
    final_target = finalize_target(raw_text)
    slots = make_slots(device="thermostat")
    return emit_command("climate", action, final_target, onoff, slots, raw_text, 0.92)


def gen_vacuum() -> Example:
    """Generate a vacuum domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"
    
    dev_word = get_granular_device("vacuum", lang)

    # Room-specific cleaning
    if random.random() < 0.30 and base_room != "default":
        room_word = pick_room_word(base_room, lang)
        
        if lang == "zh":
            structures = [f"{dev_word}去打掃{room_word}", f"打掃{room_word}", f"{room_word}要打掃"]
        else:
            structures = [f"{dev_word} go clean the {room_word}", f"clean the {room_word}", f"vacuum the {room_word}"]
        
        st = random.choice(structures)
        raw_text = humanize_text(st, lang)
        final_target = finalize_target(raw_text)
        
        # Only set mode="room" if we actually detected a room
        if final_target != "default":
            slots = make_slots(device="robot_vacuum", mode="room", value=final_target)
        else:
            slots = make_slots(device="robot_vacuum")
        return emit_command("vacuum", "start", final_target, None, slots, raw_text, 0.90)

    # Dock command
    if random.random() < 0.25:
        if lang == "zh":
            phrases = ["回家", "回去充電", "回基座", "充電"]
            st = f"{dev_word}{random.choice(phrases)}"
        else:
            phrases = ["go home", "return to base", "dock", "charge"]
            st = f"{dev_word} {random.choice(phrases)}"
            
        raw_text = humanize_text(st, lang)
        slots = make_slots(device="robot_vacuum")
        return emit_command("vacuum", "dock", "default", None, slots, raw_text, 0.90)

    # Generic start/stop/pause
    act = random.choice(["start", "stop", "pause"])
    if lang == "zh":
        v_map = {"start": ["開始掃地", "啟動", "開始打掃"], "stop": ["停止", "停"], "pause": ["暫停", "等一下"]}
        st = f"{dev_word}{random.choice(v_map[act])}"
    else:
        v_map = {"start": ["start cleaning", "start"], "stop": ["stop", "halt"], "pause": ["pause", "hold"]}
        st = f"{dev_word} {random.choice(v_map[act])}"
    
    raw_text = humanize_text(st, lang)
    slots = make_slots(device="robot_vacuum")
    return emit_command("vacuum", act, "default", None, slots, raw_text, 0.85)


def gen_timer() -> Example:
    """Generate a timer domain command."""
    lang = "zh" if random.random() < 0.5 else "en"

    if random.random() < 0.6:
        val = random.choice([1, 2, 3, 5, 10, 15, 20, 30, 45, 60])
        unit = "minutes"
    else:
        val = random.choice([1, 2, 3, 4, 5, 6])
        unit = "hours"

    slots = make_slots(device="timer", value=val, unit=unit)

    if lang == "zh":
        u_str = "分鐘" if unit == "minutes" else "小時"
        val_str = to_zh_count(val) if random.random() < 0.4 else str(val)
        structures = [
            f"設一個{val_str}{u_str}計時器", 
            f"{val_str}{u_str}後提醒我", 
            f"倒數{val_str}{u_str}",
            f"計時{val_str}{u_str}",
            f"設定{val_str}{u_str}倒數計時",
        ]
    else:
        u_str = unit
        structures = [
            f"set a {val} {u_str} timer", 
            f"remind me in {val} {u_str}", 
            f"timer {val} {u_str}", 
            f"remind me in {val} {u_str}", 
            f"alert me in {val} {u_str}",
        ]

    raw_text = humanize_text(random.choice(structures), lang)
    return emit_command("timer", "set_time", "default", None, slots, raw_text, 0.90)


def gen_curtain() -> Example:
    """Generate a curtain domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"
    
    include_room_in_structure = (base_room != "default") and (random.random() < 0.70)
    room_word = pick_room_word(base_room, lang) if include_room_in_structure else ""
    
    dev_word = get_granular_device("curtain", lang)
    
    action_type = random.choice(["open", "close", "partial"])
    slots = make_slots(device="curtain")

    if action_type == "partial":
        percentage = random.choice([25, 30, 50, 75, 80])
        if lang == "zh":
            p_str = str(percentage)
            if include_room_in_structure:
                structures = [f"{room_word}{dev_word}開{p_str}%", f"把{room_word}{dev_word}開到{p_str}%"]
            else:
                structures = [f"{dev_word}開{p_str}%", f"把{dev_word}開到{p_str}%"]
        else:
            if include_room_in_structure:
                structures = [f"open {room_word} {dev_word} {percentage}%", f"set {room_word} {dev_word} to {percentage}%"]
            else:
                structures = [f"open {dev_word} {percentage}%", f"set {dev_word} to {percentage}%"]
        
        st = random.choice(structures)
        raw_text = humanize_text(st, lang)
        final_target = finalize_target(raw_text)
        slots["value"] = str(percentage)
        slots["unit"] = "percent"
        return emit_command("curtain", "set_position", final_target, None, slots, raw_text, 0.95)
    
    action = "open" if action_type == "open" else "close"
    if lang == "zh":
        verbs = ["打開", "拉開", "開"] if action == "open" else ["關上", "拉上", "關"]
        verb = random.choice(verbs)
        if include_room_in_structure:
            structures = [f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}"]
        else:
            structures = [f"{verb}{dev_word}", f"把{dev_word}{verb}"]
    else:
        verbs = ["open", "pull open"] if action == "open" else ["close", "shut"]
        verb = random.choice(verbs)
        if include_room_in_structure:
            structures = [f"{verb} the {room_word} {dev_word}", f"{verb} {room_word} {dev_word}"]
        else:
            structures = [f"{verb} the {dev_word}", f"{verb} {dev_word}"]
    
    st = random.choice(structures)
    raw_text = humanize_text(st, lang)
    final_target = finalize_target(raw_text)
    return emit_command("curtain", action, final_target, action, slots, raw_text, 0.95)


def gen_fan() -> Example:
    """Generate a fan domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"
    
    include_room_in_structure = (base_room != "default") and (random.random() < 0.65)
    room_word = pick_room_word(base_room, lang) if include_room_in_structure else ""

    dev_word = get_granular_device("fan", lang)
    action_type = random.choice(["onoff", "speed", "speed"])

    if action_type == "speed":
        direction = random.choice(["up", "down"])
        sign = 1 if direction == "up" else -1
        
        explicit_magnitude = random.random() < 0.30
        mag = random.choice([2, 3]) if explicit_magnitude else None
        delta = (sign * mag) if mag else None

        slots = make_slots(device="fan", mode="relative")
        if delta:
            slots["value"] = str(delta)

        if lang == "zh":
            if explicit_magnitude:
                mag_str = str(mag)
                if include_room_in_structure:
                    structures = [f"{room_word}{dev_word}風速調{'高' if sign > 0 else '低'}{mag_str}檔"]
                else:
                    structures = [f"{dev_word}風速調{'高' if sign > 0 else '低'}{mag_str}檔", f"風速{'加' if sign > 0 else '減'}{mag_str}檔"]
            else:
                if include_room_in_structure:
                    structures = [f"{room_word}{dev_word}{'快' if sign > 0 else '慢'}一點"]
                else:
                    structures = [f"{dev_word}{'快' if sign > 0 else '慢'}一點", f"風扇{'大' if sign > 0 else '小'}一點"]
        else:
            if explicit_magnitude:
                if include_room_in_structure:
                    structures = [f"turn the {room_word} {dev_word} {'up' if sign > 0 else 'down'} by {mag}"]
                else:
                    structures = [f"turn {dev_word} {'up' if sign > 0 else 'down'} by {mag}", f"fan speed {'up' if sign > 0 else 'down'} {mag}"]
            else:
                if include_room_in_structure:
                    structures = [f"turn the {room_word} {dev_word} {'up' if sign > 0 else 'down'}"]
                else:
                    structures = [f"turn {dev_word} {'up' if sign > 0 else 'down'}", f"fan {'faster' if sign > 0 else 'slower'}"]

        st = random.choice(structures)
        raw_text = humanize_text(st, lang)
        final_target = finalize_target(raw_text)
        return emit_command("fan", "set_speed", final_target, None, slots, raw_text, 0.95)
    
    # On/off
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"
    slots = make_slots(device="fan")

    if lang == "zh":
        verb = random.choice(["打開", "開", "啟動"]) if onoff == "on" else random.choice(["關掉", "關", "停掉"])
        if include_room_in_structure:
            structures = [f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}"]
        else:
            structures = [f"{verb}{dev_word}", f"把{dev_word}{verb}"]
    else:
        verb = random.choice(["turn on", "switch on"]) if onoff == "on" else random.choice(["turn off", "switch off"])
        if include_room_in_structure:
            structures = [f"{verb} the {room_word} {dev_word}", f"{verb} {room_word} {dev_word}"]
        else:
            structures = [f"{verb} the {dev_word}", f"{verb} {dev_word}"]

    st = random.choice(structures)
    raw_text = humanize_text(st, lang)
    final_target = finalize_target(raw_text)
    return emit_command("fan", action, final_target, onoff, slots, raw_text, 0.95)


def gen_media() -> Example:
    """Generate a media domain command."""
    lang = "zh" if random.random() < 0.5 else "en"

    action_type = random.choice(["onoff", "volume_explicit", "volume_generic", "playback", "playback", "channel"])

    if action_type == "volume_generic":
        # Generic volume - no device specified, so don't expect model to guess
        numeric = random.random() < 0.50
        vol = random.choice([10, 20, 30, 40, 50, 60, 70, 80])
        direction = random.choice(["up", "down"])

        if numeric:
            if lang == "zh":
                structures = [f"音量調到{vol}", f"音量{vol}"]
            else:
                structures = [f"set volume to {vol}", f"volume {vol}"]
            slots = make_slots(value=str(vol), mode="volume")  # No device!
        else:
            if lang == "zh":
                structures = [f"音量{'調大' if direction == 'up' else '調小'}", f"{'大' if direction == 'up' else '小'}聲一點"]
            else:
                structures = [f"volume {'up' if direction == 'up' else 'down'}", f"{'louder' if direction == 'up' else 'quieter'}"]
            slots = make_slots(mode="volume")  # No device!

        raw_text = humanize_text(random.choice(structures), lang)
        return emit_command("media", "set_volume", "default", None, slots, raw_text, 0.92)

    if action_type == "volume_explicit":
        # Explicit device volume
        media_type = random.choice(["tv", "speaker"])
        dev_word = get_granular_device(media_type, lang)
        
        numeric = random.random() < 0.50
        vol = random.choice([10, 20, 30, 40, 50, 60, 70, 80])

        if numeric:
            if lang == "zh":
                structures = [f"{dev_word}音量調到{vol}", f"{dev_word}音量{vol}"]
            else:
                structures = [f"set {dev_word} volume to {vol}", f"{dev_word} volume {vol}"]
            slots = make_slots(device=media_type, value=str(vol), mode="volume")
        else:
            direction = random.choice(["up", "down"])
            if lang == "zh":
                structures = [f"{dev_word}{'大' if direction == 'up' else '小'}聲一點"]
            else:
                structures = [f"{dev_word} {'louder' if direction == 'up' else 'quieter'}"]
            slots = make_slots(device=media_type, mode="volume")

        raw_text = humanize_text(random.choice(structures), lang)
        return emit_command("media", "set_volume", "default", None, slots, raw_text, 0.92)

    if action_type == "channel":
        dev_word = get_granular_device("tv", lang)
        
        numeric = random.random() < 0.50
        ch = random.randint(1, 100)

        if numeric:
            if lang == "zh":
                structures = [f"轉到{ch}台", f"{dev_word}切到{ch}台"]
            else:
                structures = [f"channel {ch}", f"switch to channel {ch}"]
            slots = make_slots(device="tv", value=str(ch), mode="channel")
        else:
            if lang == "zh":
                structures = ["換台", "下一台", "切換頻道"]
            else:
                structures = ["change channel", "next channel"]
            slots = make_slots(device="tv", mode="channel")

        raw_text = humanize_text(random.choice(structures), lang)
        return emit_command("media", "channel_change", "default", None, slots, raw_text, 0.90)

    if action_type == "onoff":
        media_type = random.choice(["tv", "speaker"])
        dev_word = get_granular_device(media_type, lang)
        
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"

        if lang == "zh":
            verb = random.choice(["打開", "開"]) if onoff == "on" else random.choice(["關掉", "關"])
            structures = [f"{verb}{dev_word}"]
        else:
            verb = "turn on" if onoff == "on" else "turn off"
            structures = [f"{verb} {dev_word}", f"{verb} the {dev_word}"]

        raw_text = humanize_text(random.choice(structures), lang)
        slots = make_slots(device=media_type)
        return emit_command("media", action, "default", onoff, slots, raw_text, 0.90)

    # Playback
    media_type = random.choice(["tv", "speaker"])
    dev_word = get_granular_device(media_type, lang)
    
    action = random.choice(["play", "pause", "next", "previous", "stop", "next", "previous"])  # Extra weight for next/previous
    if lang == "zh":
        vmap = {"play": "播放", "pause": "暫停", "next": "下一首", "previous": "上一首", "stop": "停止"}
        # More variety in structure
        if action in ["next", "previous"]:
            structures = [f"{dev_word}{vmap[action]}", f"{vmap[action]}", f"切{vmap[action]}"]
        else:
            structures = [f"{dev_word}{vmap[action]}"]
        st = random.choice(structures)
    else:
        vmap = {"play": "play", "pause": "pause", "next": "next track", "previous": "previous track", "stop": "stop"}
        st = f"{vmap[action]} on {dev_word}"

    raw_text = humanize_text(st, lang)
    slots = make_slots(device=media_type)
    return emit_command("media", action, "default", None, slots, raw_text, 0.90)


def gen_hard_negative() -> Example:
    """Generate hard negatives - mentions devices but NOT commands."""
    lang = "zh" if random.random() < 0.5 else "en"
    
    dev_type = random.choice(["light", "ac", "tv", "vacuum", "fan", "curtain"])
    dev_word = get_granular_device(dev_type, lang)
    room = random.choice(ROOMS)
    room_word = pick_room_word(room, lang)
    
    if lang == "zh":
        # Questions about devices
        questions = [
            f"這個{dev_word}好用嗎？",
            f"你覺得{dev_word}怎麼樣？",
            f"{dev_word}要多少錢？",
            f"{room_word}的{dev_word}是什麼牌子？",
            f"這台{dev_word}保固多久？",
            f"{dev_word}耗電嗎？",
            f"哪裡可以買到這種{dev_word}？",
            f"{dev_word}怎麼清潔？",
            f"這{dev_word}有遙控器嗎？",
            f"{dev_word}可以連WiFi嗎？",
        ]
        
        # Past tense / Completed actions (not requests)
        past_tense = [
            f"我昨天買了一個新的{dev_word}",
            f"我已經關掉{room_word}的{dev_word}了",
            f"我剛剛開過{dev_word}",
            f"我上週修好了{dev_word}",
            f"{dev_word}昨天自己關掉了",
            f"我把舊的{dev_word}丟了",
            f"安裝師傅剛裝好{dev_word}",
            f"我忘記我有沒有關{dev_word}",
        ]
        
        # Statements about device state (observations, not commands)
        observations = [
            f"{dev_word}好像壞了",
            f"{room_word}的{dev_word}不會動",
            f"這台{dev_word}已經用了三年",
            f"{dev_word}發出怪聲",
            f"{dev_word}閃爍不停",
            f"這個{dev_word}好吵",
            f"{dev_word}需要換了",
            f"{room_word}的{dev_word}沒反應",
            f"{dev_word}好像沒電了",
            f"這{dev_word}該保養了",
        ]
        
        # Third person / Reported speech
        third_person = [
            f"爸爸說他忘記關{dev_word}了",
            f"媽媽叫我去關{dev_word}",
            f"老公說{dev_word}壞了",
            f"小孩把{dev_word}打開了",
            f"隔壁的{dev_word}好吵",
            f"誰買了新的{dev_word}？",
            f"誰開的{dev_word}？",
            f"他們家的{dev_word}很高級",
        ]
        
        # Wishes / Hypotheticals
        hypotheticals = [
            f"我希望我家也有{dev_word}",
            f"如果不關{dev_word}電費會很貴",
            f"要是{dev_word}會自動關就好了",
            f"如果{dev_word}壞了怎麼辦",
            f"我在考慮買新的{dev_word}",
            f"應該要換一台{dev_word}",
            f"不知道該不該修{dev_word}",
            f"我想要智慧型的{dev_word}",
        ]
        
        # Questions that look like commands but aren't
        tricky_questions = [
            f"你有關{dev_word}嗎？",
            f"{dev_word}開著嗎？",
            f"誰去開一下{dev_word}好嗎？",
            f"可以請別人關{dev_word}嗎？",
            f"需要開{dev_word}嗎？",
            f"要不要關{dev_word}？",
            f"{room_word}的{dev_word}是不是開著？",
            # Add patterns with adjectives (like 角落掃地機)
            f"角落的{dev_word}開著嗎？",
            f"那邊的{dev_word}是開的嗎？",
            f"新買的{dev_word}好用嗎？",
            f"舊的{dev_word}還能用嗎？",
            f"智慧{dev_word}連線了嗎？",
            f"主臥的{dev_word}有開嗎？",
        ]
        
        templates = questions + past_tense + observations + third_person + hypotheticals + tricky_questions
        
    else:
        # Questions about devices
        questions = [
            f"Is this {dev_word} good?",
            f"What do you think about the {dev_word}?",
            f"How much does a {dev_word} cost?",
            f"What brand is the {room_word} {dev_word}?",
            f"How long is the warranty on this {dev_word}?",
            f"Does the {dev_word} use a lot of electricity?",
            f"Where can I buy this {dev_word}?",
            f"How do you clean the {dev_word}?",
            f"Does this {dev_word} have a remote?",
            f"Can the {dev_word} connect to WiFi?",
        ]
        
        # Past tense / Completed actions
        past_tense = [
            f"I bought a new {dev_word} yesterday",
            f"I already turned off the {room_word} {dev_word}",
            f"I just turned on the {dev_word} earlier",
            f"I fixed the {dev_word} last week",
            f"The {dev_word} turned off by itself yesterday",
            f"I threw away the old {dev_word}",
            f"The installer just set up the {dev_word}",
            f"I forgot if I turned off the {dev_word}",
        ]
        
        # Statements about device state
        observations = [
            f"The {dev_word} seems broken",
            f"The {room_word} {dev_word} won't work",
            f"This {dev_word} is three years old",
            f"The {dev_word} is making a weird noise",
            f"The {dev_word} keeps flickering",
            f"This {dev_word} is so loud",
            f"The {dev_word} needs to be replaced",
            f"The {room_word} {dev_word} isn't responding",
            f"The {dev_word} seems dead",
            f"This {dev_word} needs maintenance",
        ]
        
        # Third person / Reported speech
        third_person = [
            f"My dad forgot to turn off the {dev_word}",
            f"Mom told me to turn off the {dev_word}",
            f"My husband said the {dev_word} is broken",
            f"The kids turned on the {dev_word}",
            f"The neighbor's {dev_word} is so loud",
            f"Who bought the new {dev_word}?",
            f"Who turned on the {dev_word}?",
            f"Their {dev_word} is so fancy",
        ]
        
        # Wishes / Hypotheticals
        hypotheticals = [
            f"I wish I had a smart {dev_word}",
            f"If we don't turn off the {dev_word} the bill will be high",
            f"I wish the {dev_word} would turn off automatically",
            f"What if the {dev_word} breaks",
            f"I'm thinking about getting a new {dev_word}",
            f"We should probably replace the {dev_word}",
            f"Not sure if we should fix the {dev_word}",
            f"I want a smart {dev_word}",
        ]
        
        # Tricky questions that look like commands
        tricky_questions = [
            f"Did you turn off the {dev_word}?",
            f"Is the {dev_word} on?",
            f"Can someone else turn on the {dev_word}?",
            f"Could you ask someone to close the {dev_word}?",
            f"Do we need to turn on the {dev_word}?",
            f"Should we turn off the {dev_word}?",
            f"Is the {room_word} {dev_word} still on?",
            f"Did you leave the {dev_word} on?",
        ]
        
        templates = questions + past_tense + observations + third_person + hypotheticals + tricky_questions
        
    text = random.choice(templates)
    
    return Example(
        type="transcript",
        domain="unknown",
        action="none",
        target=None,
        state=None,
        slots=make_slots(),
        raw_text=text,
        confidence=0.15
    )


def gen_transcript() -> Example:
    """Generate non-command transcripts with high variety."""
    lang = "zh" if random.random() < 0.5 else "en"
    
    if lang == "zh":
        # Greetings & Social
        greetings = [
            "你好嗎", "哈囉", "早安", "晚安", "午安", "嗨", "掰掰", "再見",
            "好久不見", "最近怎麼樣", "吃飽了嗎", "你好", "大家好",
        ]
        
        # Questions (non-device related)
        questions = [
            "現在幾點了", "明天會下雨嗎", "今天星期幾", "外面幾度",
            "等等要不要出去", "晚餐吃什麼", "你覺得呢", "這樣可以嗎",
            "有人在嗎", "誰在家", "小孩睡了嗎", "爸媽回來了嗎",
            "功課寫完了嗎", "垃圾車來了嗎", "快遞到了嗎", "門鈴是誰",
        ]
        
        # Statements & Observations - removed phrases that imply smart home actions
        # "好熱喔/好冷喔" → could mean adjust AC (removed)
        # "出太陽了" → could mean turn off lights/close curtains (removed)
        statements = [
            "今天天氣真好", "下雨了",
            "我等等要出門", "我回來了", "我出門了", "我在忙", "我在睡覺",
            "股市今天跌了", "塞車塞好久", "好累喔", "肚子好餓",
            "今天上班好忙", "作業好多", "考試考完了", "放假了",
        ]
        
        # Requests (non-smart home)
        requests = [
            "告訴我一個笑話", "幫我叫計程車", "幫我訂餐廳", "幫我查路線",
            "幫我翻譯這個", "幫我算一下", "幫我記住這個", "提醒我一下",
            "播放音樂", "唱首歌", "說個故事", "念新聞給我聽",
        ]
        
        # Thinking aloud / Filler
        filler = [
            "測試測試", "嗯...", "讓我想想", "等一下喔", "稍等",
            "我想想看", "怎麼說呢", "話說", "對了", "啊", "喔",
            "算了", "沒事", "好吧", "隨便", "都可以",
        ]
        
        # Life events / Stories
        life = [
            "我昨天買了新衣服", "我剛下班", "我要去接小孩", "我在等公車",
            "明天要開會", "這週末要出遊", "我在想晚餐", "我忘記帶鑰匙",
            "手機快沒電了", "我找不到錢包", "我迷路了", "我到了",
            "我想買一台新車", "我在考慮換工作", "我要去運動", "我在追劇",
        ]
        
        # Expressions / Emotions
        emotions = [
            "太棒了", "好煩喔", "怎麼辦", "糟糕", "完蛋了", "太好了",
            "不會吧", "真的假的", "傻眼", "無言", "好笑", "好可愛",
            "好厲害", "太扯了", "受不了", "好感動", "好期待", "緊張",
        ]
        
        # Commands to other services (not smart home)
        other_services = [
            "導航到最近的加油站", "搜尋附近的餐廳", "打電話給媽媽",
            "傳訊息給老公", "查一下明天的行程", "新增一個備忘錄",
            "翻譯成英文", "今天的新聞", "股票漲了沒", "匯率多少",
        ]
        
        # Numbers / Random utterances
        random_utterances = [
            "一二三四五", "ABCD", "測試一二三", "喂喂喂", "哈哈哈",
            "啦啦啦", "唔...", "蛤", "什麼", "真的嗎",
        ]
        
        all_texts = (greetings + questions + statements + requests + 
                     filler + life + emotions + other_services + random_utterances)
        
    else:
        # Greetings & Social
        greetings = [
            "Hello there", "Hey", "Hi", "Good morning", "Good night", "Good evening",
            "Goodbye", "See you later", "What's up", "How are you", "How's it going",
            "Long time no see", "Nice to meet you", "Take care", "Have a good day",
        ]
        
        # Questions (non-device related)
        questions = [
            "What time is it", "Will it rain tomorrow", "What day is it",
            "What's the weather like", "What should we have for dinner",
            "Anyone there", "Who's home", "Are the kids asleep", "Did mom call",
            "Is the mail here", "Did the package arrive", "Who's at the door",
            "What do you think", "Is that okay", "Does that work for you",
            "Where are my keys", "Have you seen my phone", "What was I saying",
        ]
        
        # Statements & Observations - removed phrases that imply smart home actions
        # "The sun is out" → could mean turn off lights (removed)
        # "It's so hot/freezing" → could mean adjust AC (removed)
        statements = [
            "Nice weather today", "It's raining",
            "I'm going out later", "I'm back", "I'm leaving",
            "I'm busy right now", "I'm trying to sleep", "Traffic was terrible",
            "I'm so tired", "I'm hungry", "Work was crazy today", "Finally weekend",
            "I have so much homework", "The exam is over", "I'm on vacation",
        ]
        
        # Requests (non-smart home)
        requests = [
            "Tell me a joke", "Call me a taxi", "Book a restaurant",
            "Look up directions", "Translate this for me", "Calculate this",
            "Remind me later", "Set a reminder", "Play some music", "Sing a song",
            "Tell me a story", "Read me the news", "What's in the news",
        ]
        
        # Thinking aloud / Filler
        filler = [
            "Testing testing", "Hmm", "Let me think", "Hold on", "One moment",
            "Let me see", "How do I say this", "By the way", "Oh right", "Ah",
            "Never mind", "Forget it", "Okay then", "Whatever", "Sure",
            "I guess", "Maybe", "I don't know", "Not sure", "Interesting",
        ]
        
        # Life events / Stories  
        life = [
            "I bought new clothes yesterday", "I just got off work", 
            "I need to pick up the kids", "I'm waiting for the bus",
            "I have a meeting tomorrow", "We're going on a trip this weekend",
            "I'm thinking about dinner", "I forgot my keys", 
            "My phone is dying", "I can't find my wallet", "I'm lost", "I'm here",
            "I want to buy a car", "I'm considering a job change", 
            "I'm going to work out", "I'm watching a show", "I just woke up",
        ]
        
        # Expressions / Emotions
        emotions = [
            "That's awesome", "So annoying", "What do I do", "Oh no", "Great",
            "No way", "Really", "I can't believe it", "That's hilarious", "So cute",
            "Amazing", "That's crazy", "I can't take it", "So touching", 
            "I'm so excited", "I'm nervous", "Finally", "Thank goodness",
        ]
        
        # Commands to other services (not smart home)
        other_services = [
            "Navigate to the nearest gas station", "Search for nearby restaurants",
            "Call mom", "Text my husband", "Check my schedule for tomorrow",
            "Add a note", "Translate to Spanish", "What's today's news",
            "How's the stock market", "What's the exchange rate", "Search for recipes",
        ]
        
        # Random utterances / Gibberish
        random_utterances = [
            "One two three four five", "A B C D", "Testing one two three",
            "Hello hello hello", "Haha", "La la la", "Hmm...", "Huh",
            "What", "Seriously", "Okay okay", "Yeah yeah", "No no no",
        ]
        
        all_texts = (greetings + questions + statements + requests +
                     filler + life + emotions + other_services + random_utterances)
    
    text = random.choice(all_texts)
    raw_text = humanize_text(text, lang, noise_prob=0.0)
    return emit_transcript("unknown", "none", None, None, make_slots(), raw_text, 0.15)


def gen_abandoned_correction() -> Example:
    """
    Generate examples where user starts a command but abandons/corrects to nothing.
    These should be labeled as 'transcript' not 'command'.
    
    Fixes: "Turn off... I mean, Testing testing" → transcript
    """
    lang = "zh" if random.random() < 0.5 else "en"
    
    if lang == "zh":
        fake_starts = [
            "打開", "關掉", "關", "開", "設定", "調整", 
            "把...那個", "幫我把", "可以幫我"
        ]
        corrections = ["不對", "我是說", "等一下", "改一下", "算了", "沒事"]
        non_command_endings = [
            "測試測試", "沒事", "算了", "我想想", "等一下再說",
            "你好", "謝謝", "我忘了", "什麼來著", ""
        ]
        
        fake = random.choice(fake_starts)
        correction = random.choice(corrections)
        ending = random.choice(non_command_endings)
        
        if ending:
            text = f"{fake}...{correction}，{ending}"
        else:
            text = f"{fake}...{correction}"
            
    else:
        fake_starts = [
            "Turn off", "Turn on", "Open", "Close", "Set", 
            "Hey can you", "Please", "Could you"
        ]
        corrections = ["wait", "no", "I mean", "actually", "hold on", "never mind"]
        non_command_endings = [
            "testing testing", "never mind", "forget it", "let me think",
            "hello", "thanks", "I forgot", "what was it", ""
        ]
        
        fake = random.choice(fake_starts)
        correction = random.choice(corrections)
        ending = random.choice(non_command_endings)
        
        if ending:
            text = f"{fake}... {correction}, {ending}"
        else:
            text = f"{fake}... {correction}"
    
    return Example(
        type="transcript",
        domain="unknown",
        action="none",
        target=None,
        state=None,
        slots=make_slots(),
        raw_text=text,
        confidence=0.15
    )


def gen_ambiguous_short_phrase() -> Example:
    """
    Generate short ambiguous phrases without clear device/action context.
    These should be 'transcript' since intent cannot be determined.
    
    Fixes: "下一台" (next one - next what?) → transcript
    """
    lang = "zh" if random.random() < 0.5 else "en"
    
    if lang == "zh":
        # Directional / Relative - AVOID media command conflicts
        # NOTE: 下一台/上一台 are valid channel commands, removed
        directional = [
            "下一個", "上一個", "前一個", "後一個",
            "左邊", "右邊", "上面", "下面", "這邊", "那邊",
        ]
        
        # Quantity / Intensity
        quantity = [
            "多一點", "少一點", "再多一點", "再少一點", "一半",
            "全部", "一點點", "很多", "太多", "太少", "剛好",
        ]
        
        # Speed / Volume / Brightness (without device) - ONLY truly ambiguous
        # NOTE: 大聲點/小聲點 are valid volume commands, don't include
        # NOTE: 亮一點/暗一點 could be light commands, don't include  
        # NOTE: 熱一點/冷一點 could be climate commands, don't include
        adjustments = [
            "快一點", "慢一點",
            "高一點", "低一點", "強一點", "弱一點",
            "大一點", "小一點", "長一點", "短一點",
        ]
        
        # Action words without context - AVOID playback command conflicts
        # NOTE: 停/暫停/繼續 could be valid playback commands
        actions = [
            "再一次", "開始", "結束",
            "重來", "取消", "確定", "返回", "下一步", "上一步",
        ]
        
        # Affirmations / Negations
        responses = [
            "好", "好的", "可以", "不行", "不要", "要", "是", "不是",
            "對", "不對", "好了", "可以了", "夠了", "不夠", "沒有",
            "有", "知道了", "了解", "收到", "OK",
        ]
        
        # Filler / Incomplete
        filler = [
            "這個", "那個", "什麼", "哪個", "誰", "怎樣",
            "然後", "所以", "還有", "而且", "但是", "不過",
            "嗯", "喔", "啊", "欸", "蛤", "呃",
        ]
        
        # Numbers without context
        numbers = [
            "一", "二", "三", "五", "十", "二十", "三十",
            "百分之五十", "一半", "兩倍", "三分之一",
        ]
        
        phrases = directional + quantity + adjustments + actions + responses + filler + numbers
        
    else:
        # Directional / Relative - AVOID media command conflicts
        # NOTE: "Next"/"Previous" alone could be valid playback commands
        directional = [
            "Next one", "Last one", "First one",
            "Left", "Right", "Up", "Down", "This way", "That way",
            "Forward", "Back", "Before", "After",
        ]
        
        # Quantity / Intensity
        quantity = [
            "More", "Less", "A little more", "A little less", "Half",
            "All", "Just a bit", "A lot", "Too much", "Too little", "Just right",
            "Double", "Triple", "Maximum", "Minimum",
        ]
        
        # Adjustments without device - ONLY truly ambiguous ones
        # NOTE: "Louder/Quieter" are valid volume commands, don't include here
        # NOTE: "Brighter/Dimmer" could be light commands, don't include here
        adjustments = [
            "Faster", "Slower",
            "Higher", "Lower", "Stronger", "Weaker", 
            "Bigger", "Smaller", "Longer", "Shorter",
        ]
        
        # Action words without context - AVOID playback command conflicts
        # NOTE: Stop/Pause/Continue could be valid playback commands
        actions = [
            "Again", "Start", "End",
            "Restart", "Cancel", "Confirm", "Go back", "Next step", "Undo",
            "Repeat", "Skip", "Finish",
        ]
        
        # Affirmations / Negations
        responses = [
            "Yes", "No", "Okay", "OK", "Sure", "Nope", "Yeah", "Nah",
            "Alright", "Fine", "Good", "Done", "Enough", "Not enough",
            "Got it", "I see", "Roger", "Copy", "Understood",
        ]
        
        # Filler / Incomplete
        filler = [
            "This one", "That one", "What", "Which", "Who", "How",
            "Then", "So", "Also", "And", "But", "However",
            "Hmm", "Oh", "Ah", "Uh", "Huh", "Um", "Er",
        ]
        
        # Numbers without context
        numbers = [
            "One", "Two", "Three", "Five", "Ten", "Twenty", "Thirty",
            "Fifty percent", "Half", "Double", "One third", "A quarter",
        ]
        
        phrases = directional + quantity + adjustments + actions + responses + filler + numbers
    
    text = random.choice(phrases)
    
    return Example(
        type="transcript",
        domain="unknown",
        action="none",
        target=None,
        state=None,
        slots=make_slots(),
        raw_text=text,
        confidence=0.15
    )


# =============================================================================
# DATASET GENERATION
# =============================================================================

def compute_text_hash(text: str) -> str:
    normalized = " ".join(text.strip().lower().split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()

def mutate_example(ex: Example, attempts: int) -> Example:
    lang = "zh" if any(ord(c) > 128 for c in ex.raw_text) else "en"
    
    if attempts >= 2:
        additions_zh = ["拜託", "謝謝", "快點", "喔", "好嗎"]
        additions_en = ["please", "thanks", "now", "okay", "quickly"]
        additions = additions_zh if lang == "zh" else additions_en
        if random.random() < 0.5:
            ex.raw_text = f"{random.choice(additions)} {ex.raw_text}"
        else:
            ex.raw_text = f"{ex.raw_text} {random.choice(additions)}"
    
    return ex


GENERATORS = [
    (gen_lights, 0.10),
    (gen_climate, 0.10),
    (gen_vacuum, 0.10),
    (gen_timer, 0.10),
    (gen_curtain, 0.10),
    (gen_fan, 0.10),
    (gen_media, 0.10),
    (gen_hard_negative, 0.11),           # Reduced slightly
    (gen_transcript, 0.13),               # Reduced slightly  
    (gen_abandoned_correction, 0.03),     # NEW: correction → abandonment
    (gen_ambiguous_short_phrase, 0.03),   # NEW: ambiguous short phrases
]


def generate(n: int, max_attempts: int = 15) -> List[Example]:
    out = []
    seen_hashes = set()
    
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
            continue
        
        seen_hashes.add(text_hash)
        out.append(ex)
        
        if len(out) % 10000 == 0:
            print(f"Generated {len(out)}/{n} examples...")

    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="smart_home_mega.jsonl")
    p.add_argument("--n", type=int, default=100000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    random.seed(args.seed)
    
    print(f"Generating {args.n:,} examples with seed {args.seed}...")
    
    data = generate(args.n)
    
    with open(args.out, "w", encoding="utf-8") as f:
        for ex in data:
            f.write(json.dumps(asdict(ex), ensure_ascii=False) + "\n")
    
    # Stats
    type_counts = {}
    domain_counts = {}
    target_counts = {}
    for ex in data:
        type_counts[ex.type] = type_counts.get(ex.type, 0) + 1
        domain_counts[ex.domain] = domain_counts.get(ex.domain, 0) + 1
        target_counts[ex.target or "None"] = target_counts.get(ex.target or "None", 0) + 1
    
    print(f"\nDone! Saved to {args.out}")
    print(f"\nType distribution: {dict(type_counts)}")
    print(f"\nTarget distribution (top 10):")
    for t, c in sorted(target_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {t}: {c} ({c/len(data):.1%})")


if __name__ == "__main__":
    main()