import json
import random
import argparse
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple

random.seed(42)

# ==========================================
# 1. CONSTANTS & LINGUISTIC RESOURCES
# ==========================================

ROOMS = [
    "bathroom", "kitchen", "bedroom", "living_room", 
    "dining_room", "study", "balcony", "hallway", "entryway", "default"
]

# Expanded Room Aliases with colloquialisms
ROOM_ALIASES_ZH = {
    "bathroom": ["廁所", "浴室", "洗手間", "茅房", "洗澡的地方"],
    "kitchen": ["廚房", "灶咖", "煮飯的地方"],
    "bedroom": ["房間", "臥室", "主臥", "睡覺的地方", "寢室"],
    "living_room": ["客廳", "大廳", "起居室"],
    "dining_room": ["餐廳", "飯廳", "吃飯的地方"],      
    "study": ["書房", "辦公室", "工作區", "電腦房"], 
    "balcony": ["陽台", "露台"],          
    "hallway": ["走廊", "過道", "走道"],          
    "entryway": ["玄關", "門口", "大門口"],         
    "default": ["家裡", "全部", "所有地方", "整個房子"],
}

ROOM_ALIASES_EN = {
    "bathroom": ["bathroom", "restroom", "bath", "loo", "powder room"],
    "kitchen": ["kitchen", "cooking area"],
    "bedroom": ["bedroom", "master bedroom", "sleeping quarters", "bed chamber"],
    "living_room": ["living room", "lounge", "family room", "sitting room"],
    "dining_room": ["dining room", "dining area"],       
    "study": ["study", "office", "workspace", "home office", "desk area"], 
    "balcony": ["balcony", "terrace", "patio", "deck"],    
    "hallway": ["hallway", "corridor", "hall"],   
    "entryway": ["entryway", "foyer", "entrance", "front door area"],    
    "default": ["the house", "everywhere", "the whole place", "all rooms"],
}

EXTRA_ROOM_TO_TARGET = {
    "guest_room": "bedroom", "kids_room": "bedroom", "nursery": "bedroom",
    "garage": "default", "basement": "default", "attic": "default",
    "closet": "default", "den": "living_room"
}

EXTRA_ROOM_ALIASES_ZH = {
    "guest_room": ["客房", "客用臥室"],
    "kids_room": ["小孩房", "兒童房", "寶貝房間"],
    "nursery": ["育嬰室", "嬰兒房"],
    "garage": ["車庫", "停車場"],
    "basement": ["地下室", "地窖"],
    "attic": ["頂樓", "閣樓"],
    "closet": ["儲藏室", "衣帽間", "更衣室"],
    "den": ["起居室", "休閒室", "視聽室"]
}

EXTRA_ROOM_ALIASES_EN = {
    "guest_room": ["guest room", "guest bedroom"],
    "kids_room": ["kids room", "children's room", "child's room"],
    "nursery": ["nursery", "baby's room"],
    "garage": ["garage", "car port"],
    "basement": ["basement", "cellar", "downstairs"],
    "attic": ["attic", "loft", "upstairs"],
    "closet": ["closet", "pantry", "walk-in closet", "storage"],
    "den": ["den", "man cave", "lounge"]
}

PERSON_NAMES_ZH = ["爸爸", "媽媽", "哥哥", "妹妹", "阿嬤", "爺爺", "小寶", "老王", "老婆", "老公"]
PERSON_NAMES_EN = ["Mom", "Dad", "Alice", "Bob", "Grandma", "Tommy", "Baby", "Honey"]

# Homophones for ASR Error Injection (Simulating microphone misinterpretation)
HOMOPHONES_ZH = {
    "幫我": ["邦我", "幫偶"],
    "打開": ["達開", "打凱", "大開"],
    "冷氣": ["冷器", "冷企"],
    "客廳": ["客聽", "刻廳"],
    "廚房": ["除房", "儲房"],
    "關掉": ["關吊", "觀掉"],
    "現在": ["現再", "線在"],
    "什麼": ["神麼", "什摸"],
    "臥室": ["沃室", "臥式"],
    "窗簾": ["窗連", "窗聯"]
}

HOMOPHONES_EN = {
    "light": ["right", "lite", "white", "night"],
    "lights": ["rights", "lites"],
    "fan": ["van", "fin", "fen"],
    "set": ["sit", "sat"],
    "timer": ["time", "tyme"],
    "two": ["to", "too"],
    "four": ["for", "fore"],
    "off": ["of"],
    "on": ["an", "own"],
    "kitchen": ["chicken", "kitchin"],
    "play": ["pay", "plate"]
}

SWITCH_DEVICES = [
    "fan", "humidifier", "diffuser", "plug", "air_purifier",
    "dehumidifier", "heater", "coffee_maker", "rice_cooker",
    "kettle", "water_heater", "washer", "dryer", "oven", "dishwasher"
]

SWITCH_DEV_EN = {
    "fan": ["fan", "ceiling fan", "desk fan", "ventilator", "blower"],
    "humidifier": ["humidifier", "mister"],
    "diffuser": ["diffuser", "scent machine", "aroma diffuser"],
    "plug": ["plug", "socket", "outlet", "smart plug", "switch"],
    "air_purifier": ["air purifier", "purifier", "air filter"],
    "dehumidifier": ["dehumidifier", "de-humidifier"],
    "heater": ["heater", "radiator", "space heater", "warmer"],
    "coffee_maker": ["coffee maker", "coffee machine", "espresso machine"],
    "rice_cooker": ["rice cooker", "steamer"],
    "kettle": ["kettle", "electric kettle", "water boiler", "tea pot"],
    "water_heater": ["water heater", "boiler"],
    "washer": ["washer", "washing machine", "laundry machine"],
    "dryer": ["dryer", "clothes dryer", "tumbler"],
    "oven": ["oven", "stove", "range"],
    "dishwasher": ["dishwasher", "dish washer"]
}

SWITCH_DEV_ZH = {
    "fan": ["風扇", "電扇", "循環扇", "抽風機"],
    "humidifier": ["加濕器", "水氧機"],
    "diffuser": ["香氛機", "擴香", "香燻機"],
    "plug": ["插座", "插頭", "電源", "開關"],
    "air_purifier": ["空氣清淨機", "清淨機", "濾清器"],
    "dehumidifier": ["除濕機"],
    "heater": ["暖氣", "暖爐", "電暖器", "暖風機"],
    "coffee_maker": ["咖啡機"],
    "rice_cooker": ["電鍋", "電子鍋"],
    "kettle": ["熱水壺", "快煮壺", "燒水壺"],
    "water_heater": ["熱水器"],
    "washer": ["洗衣機"],
    "dryer": ["烘衣機"],
    "oven": ["烤箱"],
    "dishwasher": ["洗碗機"]
}

DEVICE_VARIANTS_EN = {
    "light": ["light", "lights", "lamp", "lamps", "lighting", "LEDs", "strip lights", "ceiling light", "bulbs", "illumination"],
    "ac": ["AC", "air conditioner", "A/C", "cooling unit", "air con", "thermostat", "climate control", "HVAC"],
    "tv": ["TV", "television", "telly", "screen", "display", "monitor", "smart TV"],
    "vacuum": ["vacuum", "robot vacuum", "roomba", "sweeper", "bot", "cleaner", "mopping robot"],
    "curtain": ["curtain", "drapes", "shades", "blinds", "shutters", "blackout curtains", "screens"],
    "speaker": ["speaker", "sound system", "audio", "woofer", "bluetooth speaker", "music player"],
    "soundbar": ["soundbar", "sound bar"],
}

DEVICE_VARIANTS_ZH = {
    "light": ["燈", "電燈", "照明", "光", "檯燈", "吊燈", "吸頂燈", "落地燈", "壁燈", "LED燈", "嵌燈", "燈泡"],
    "ac": ["冷氣", "空調", "冷氣機", "恆溫器"],
    "tv": ["電視", "電視機", "螢幕", "顯示器"],
    "vacuum": ["掃地機", "吸塵器", "機器人", "掃地機器人", "拖地機", "掃拖機"],
    "curtain": ["窗簾", "布簾", "百葉窗", "捲簾", "遮光簾", "紗簾"],
    "speaker": ["喇叭", "音響", "揚聲器", "藍芽喇叭"],
    "soundbar": ["聲霸", "家庭劇院"],
}

ADJECTIVES_EN = ["main", "big", "small", "ceiling", "floor", "desk", "bedside", "reading", "smart", "old", "new"]
ADJECTIVES_ZH = ["主", "大", "小", "天花板", "地板", "桌上", "床頭", "閱讀", "智慧", "舊", "新"]

FILLERS_EN = ["uh", "um", "like", "you know", "actually", "er", "ah", "maybe", "please", "hmm", "well", "okay", "so", "basically"]
FILLERS_ZH = ["那個", "呃", "嗯", "就是", "那個...應...", "阿", "好像是", "麻煩", "欸", "我想", "然後", "喔", "那個什麼"]

PREFIXES_EN = ["Could you", "Please", "Can you", "Hey,", "I need you to", "Would you mind to", "Just", "Quickly", "Go ahead and", "Time to", "Help me"]
PREFIXES_ZH = ["麻煩", "請", "幫我", "可以幫我", "那個", "欸", "快速", "我想", "這時候", "去", "幫忙", "順便"]

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def to_zh_count(n: int) -> str:
    """Converts a number to Chinese count format (using 兩 for 2)."""
    if n == 2:
        return "兩"
    # Basic mapping for 0-10
    mapping = {0:"零", 1:"一", 3:"三", 4:"四", 5:"五", 6:"六", 7:"七", 8:"八", 9:"九", 10:"十"}
    if n in mapping:
        return mapping[n]
    return str(n)

def pick_room(weight_default: float = 0.25) -> str:
    if random.random() < weight_default:
        return "default"
    return random.choice([r for r in ROOMS if r != "default"])

def pick_room_word_and_target(base_target: str) -> Tuple[str, str, str]:
    """Selects a room name with Named Entity Injection."""
    # Handle Default
    if base_target == "default":
        if random.random() < 0.5:
            return random.choice(ROOM_ALIASES_ZH["default"]), "default", "zh"
        else:
            return random.choice(ROOM_ALIASES_EN["default"]), "default", "en"

    # Named Entity Injection (e.g., "Dad's room" instead of "Bedroom")
    if random.random() < 0.15 and base_target in ["bedroom", "study"]:
        if random.random() < 0.5:
            name = random.choice(PERSON_NAMES_ZH)
            # "Dad's room" or "Dad's study"
            suffix = "房間" if base_target == "bedroom" else "書房"
            return f"{name}的{suffix}", base_target, "zh"
        else:
            name = random.choice(PERSON_NAMES_EN)
            suffix = "room" if base_target == "bedroom" else "study"
            return f"{name}'s {suffix}", base_target, "en"

    # Standard Room Aliases
    lang = "mix"
    if random.random() < 0.5:
        lang = "zh"
        # Check standard rooms
        if base_target in ROOM_ALIASES_ZH:
            word = random.choice(ROOM_ALIASES_ZH[base_target])
        # Check extra rooms (garage, etc.)
        elif base_target in EXTRA_ROOM_TO_TARGET: 
             # For extra rooms, we need to map the generated key (e.g. garage) to aliases
             # But the input base_target is usually standard. 
             # Logic fix: We handle extra rooms by randomly picking them if base is standard?
             # No, simple lookup.
            word = "房間" # Fallback
    else:
        lang = "en"
        if base_target in ROOM_ALIASES_EN:
            word = random.choice(ROOM_ALIASES_EN[base_target])
        else:
            word = "room"

    # If we didn't get a word (because base_target might be normalized), fallback
    if lang == "zh" and base_target not in ROOM_ALIASES_ZH:
        word = "房間"
    if lang == "en" and base_target not in ROOM_ALIASES_EN:
        word = "room"
        
    return word, base_target, lang

def get_granular_device(dev_type: str, lang: str) -> str:
    """Returns a device name, potentially with an adjective."""
    variants = DEVICE_VARIANTS_ZH if lang == "zh" else DEVICE_VARIANTS_EN
    adjectives = ADJECTIVES_ZH if lang == "zh" else ADJECTIVES_EN
    
    base = random.choice(variants.get(dev_type, [dev_type]))
    
    if random.random() < 0.20:
        adj = random.choice(adjectives)
        return f"{adj}{base}" if lang == "zh" else f"{adj} {base}"
    return base

def get_granular_switch(dev_type: str, lang: str) -> str:
    variants = SWITCH_DEV_ZH if lang == "zh" else SWITCH_DEV_EN
    adjectives = ADJECTIVES_ZH if lang == "zh" else ADJECTIVES_EN
    
    base = random.choice(variants.get(dev_type, [dev_type]))
    
    if random.random() < 0.15:
        adj = random.choice(adjectives)
        return f"{adj}{base}" if lang == "zh" else f"{adj} {base}"
    return base

def inject_asr_noise(text: str, lang: str, prob: float = 0.08) -> str:
    """Injects ASR-like errors (homophones) into the text."""
    if random.random() > prob:
        return text

    if lang == "en":
        words = text.split()
        new_tokens = []
        for w in words:
            lw = w.lower()
            if lw in HOMOPHONES_EN and random.random() < 0.4:
                new_tokens.append(random.choice(HOMOPHONES_EN[lw]))
            else:
                new_tokens.append(w)
        return " ".join(new_tokens)
    else:
        # Simple substring replacement for ZH
        out_text = text
        keys = list(HOMOPHONES_ZH.keys())
        random.shuffle(keys)
        for k in keys:
            if k in out_text and random.random() < 0.4:
                out_text = out_text.replace(k, random.choice(HOMOPHONES_ZH[k]), 1)
        return out_text

def humanize_text(text: str, lang: str, noise_prob: float = 0.1) -> str:
    """Adds fillers, pauses, repeats, and ASR noise."""
    text = inject_asr_noise(text, lang, prob=noise_prob)
    
    if random.random() > 0.6:
        return text

    words = text.split()
    if not words: return text

    fillers = FILLERS_ZH if lang == "zh" else FILLERS_EN
    
    # Prepend filler
    if random.random() < 0.25:
        words.insert(0, random.choice(fillers) + ("..." if random.random() < 0.5 else ""))
    
    # Insert filler mid-sentence
    if len(words) > 3 and random.random() < 0.3:
        idx = random.randint(1, len(words)-1)
        words.insert(idx, random.choice(fillers))

    # Stutter/Repeat
    if random.random() < 0.1:
        idx = random.randint(0, len(words)-1)
        words.insert(idx, words[idx])

    return " ".join(words)

def make_slots(device=None, value=None, unit=None, mode=None, scene=None) -> Dict[str, Any]:
    return {
        "device": device,
        "value": str(value) if value is not None else None,
        "value_num": float(value) if isinstance(value, (int, float)) else None,
        "unit": unit,
        "mode": mode,
        "scene": scene,
    }

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
    conf = max(0.0, min(1.0, base_conf + random.uniform(-0.1, 0.05)))
    return Example("command", domain, action, target, state, slots, text, round(conf, 2))

def emit_transcript(text, base_conf=0.15) -> Example:
    conf = max(0.0, min(1.0, base_conf + random.uniform(-0.1, 0.1)))
    return Example("transcript", "unknown", "none", None, None, make_slots(), text, round(conf, 2))

# ==========================================
# 3. GENERATORS
# ==========================================

def gen_lights() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("light", lang)
    
    # 10% Chance for Context "It"
    if random.random() < 0.1:
        dev_word = "它" if lang == "zh" else "it"

    if random.random() < 0.15: # Complaints
        if lang == "zh":
            phr = random.choice(["這裡太暗了", "我看不到", "好黑喔", "幫我點燈", "把光打亮", "太亮了眼睛痛"])
            action = "turn_on" if "暗" in phr or "黑" in phr or "看不到" in phr else "turn_off"
        else:
            phr = random.choice(["It's too dark in here", "I can't see anything", "It's pitch black", "Way too bright", "Kill the lights"])
            action = "turn_on" if "dark" in phr or "see" in phr or "black" in phr else "turn_off"
        
        state = "on" if action == "turn_on" else "off"
        return emit_command("lights", action, "default", state, make_slots(device="light"), humanize_text(phr, lang), 0.75)

    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"

    if lang == "zh":
        verbs = ["打開", "開一下", "開啟", "啟動", "亮起來", "點亮"] if onoff == "on" else ["關掉", "關一下", "關閉", "熄滅", "滅掉"]
        verb = random.choice(verbs)
        prefix = random.choice(PREFIXES_ZH) if random.random() < 0.4 else ""
        structure = random.choice([
            f"{prefix}{verb}{room_word}{dev_word}",
            f"{prefix}{room_word}{dev_word}{verb}",
            f"把{room_word}{dev_word}{verb}",
            f"{room_word}{dev_word}幫我{verb}",
            f"{verb}{room_word}的{dev_word}" 
        ])
    else:
        verbs = ["turn on", "switch on", "activate", "power on", "hit"] if onoff == "on" else ["turn off", "switch off", "kill", "cut", "shut off"]
        verb = random.choice(verbs)
        prefix = random.choice(PREFIXES_EN) if random.random() < 0.4 else ""
        structure = random.choice([
            f"{prefix} {verb} the {room_word} {dev_word}",
            f"{prefix} {verb} the {dev_word} in the {room_word}",
            f"{room_word} {dev_word} {verb}",
            f"{prefix} make the {room_word} {dev_word} {onoff}",
            f"{verb} {dev_word} {room_word}"
        ])
    
    # If using "it", force context dependency flag in mind (omitted for JSON simplicity here)
    phr = humanize_text(structure.strip(), lang)
    return emit_command("lights", action, norm_target, onoff, make_slots(device="light"), phr, 0.92)

def gen_switches() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev = random.choice(SWITCH_DEVICES)
    dev_word = get_granular_switch(dev, lang)
    
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"
    is_heavy = dev in ["washer", "dryer", "oven", "dishwasher"]
    
    if lang == "zh":
        if is_heavy and onoff == "off":
             verbs = ["停止", "停掉", "關掉", "暫停"]
        else:
            verbs = ["打開", "開一下", "開啟", "運作"] if onoff == "on" else ["關掉", "關一下", "關閉", "停止"]
        verb = random.choice(verbs)
        prefix = random.choice(PREFIXES_ZH) if random.random() < 0.4 else ""
        structure = random.choice([
            f"{prefix}幫我把{room_word}{dev_word}{verb}",
            f"{prefix}{room_word}{dev_word}{verb}",
            f"{dev_word}在{room_word}{verb}",
            f"{room_word}的{dev_word}{verb}"
        ])
    else:
        if is_heavy and onoff == "off":
             verbs = ["stop", "halt", "turn off", "cancel"]
        else:
            verbs = ["turn on", "switch on", "start", "run", "boot"] if onoff == "on" else ["turn off", "switch off", "stop", "shutdown"]
        verb = random.choice(verbs)
        prefix = random.choice(PREFIXES_EN) if random.random() < 0.4 else ""
        structure = random.choice([
            f"{prefix} {verb} the {dev_word} in the {room_word}",
            f"{prefix} {verb} the {room_word} {dev_word}",
            f"{room_word} {dev_word} {verb}",
            f"{verb} that {dev_word}"
        ])

    has_room = room_word in structure
    phr = humanize_text(structure.strip(), lang)
    final_target = norm_target if has_room else "default"
    return emit_command("switches", action, final_target, onoff, make_slots(device=dev), phr, 0.86)

def gen_climate() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    style = random.choice(["power", "set", "mode", "delta", "implicit"])
    dev_word = get_granular_device("ac", lang)

    if style == "power":
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"
        if lang == "zh":
            v = "打開" if onoff == "on" else "關掉"
            st = f"{room_word}{dev_word}{v}"
        else:
            v = "turn on" if onoff == "on" else "turn off"
            st = f"{v} the {room_word} {dev_word}"
        return emit_command("climate", action, norm_target, onoff, make_slots(device="ac"), humanize_text(st, lang), 0.90)

    if style == "set":
        temp = random.randint(16, 30)
        if lang == "zh":
            # Chinese numerals for temperature
            t_str = to_zh_count(temp) if temp <= 10 or random.random() < 0.3 else str(temp)
            st = random.choice([
                f"{room_word}{dev_word}調到{t_str}度", 
                f"溫度設為{t_str}",
                f"{dev_word}調到{t_str}度"
            ])
        else:
            st = random.choice([
                f"set {room_word} {dev_word} to {temp} degrees", 
                f"make it {temp} degrees in the {room_word}",
                f"set {dev_word} to {temp}"
            ])
        
        final_target = norm_target if room_word in st else "default"
        return emit_command("climate", "set_temperature", final_target, None, 
                           make_slots(device="thermostat", value=temp, unit="celsius", mode="setpoint"), 
                           humanize_text(st, lang), 0.86)

    if style == "mode":
        mode = random.choice(["cool", "heat", "dry", "fan_only"])
        if lang == "zh":
            zh_mode = {"cool": "冷房", "heat": "暖房", "dry": "除濕", "fan_only": "送風"}[mode]
            st = f"{room_word}{dev_word}切到{zh_mode}"
        else:
            st = f"set {room_word} {dev_word} mode to {mode}"
        
        return emit_command("climate", "set_mode", norm_target, None, 
                           make_slots(device="ac", mode=mode), humanize_text(st, lang), 0.82)

    if style == "delta":
        delta = random.randint(1, 5)
        inc = random.choice([True, False])
        if lang == "zh":
            d_str = to_zh_count(delta)
            st = f"溫度調{'高' if inc else '低'}{d_str}度"
        else:
            st = f"turn the temperature {'up' if inc else 'down'} by {delta} degrees"
        return emit_command("climate", "increase" if inc else "decrease", "default", None, 
                           make_slots(device="thermostat", value=delta, unit="celsius"), humanize_text(st, lang), 0.76)

    # Implicit
    opts = [
        (f"{room_word}好熱", True, "cool"), (f"{room_word}有點冷", True, "heat"),
        ("It's too hot", False, "cool"), ("I'm freezing", False, "heat"),
        ("好濕喔", False, "dry"), ("It's too humid", False, "dry")
    ]
    base_phr, uses_room, mode = random.choice(opts)
    final_target = norm_target if uses_room else "default"
    return emit_command("climate", "turn_on", final_target, "on", make_slots(device="ac", mode=mode), humanize_text(base_phr, lang), 0.60)

def gen_media() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    style = random.choice(["tv_power", "audio_power", "playback", "volume", "source"])
    
    if style == "tv_power":
        dev_word = get_granular_device("tv", lang)
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"
        st = f"幫我{room_word}{dev_word}{'打開' if onoff == 'on' else '關掉'}" if lang == "zh" else f"turn {onoff} the {room_word} {dev_word}"
        return emit_command("media", action, norm_target, onoff, make_slots(device="tv"), humanize_text(st, lang), 0.86)

    if style == "playback":
        if lang == "zh":
             st = random.choice(["暫停播放", "繼續放", "下一首", "上一首"])
             act = {"暫停播放":"pause", "繼續放":"resume", "下一首":"next", "上一首":"previous"}[st]
        else:
             st = random.choice(["pause music", "resume playback", "next track", "previous song"])
             act = "pause" if "pause" in st else "resume" if "resume" in st else "next" if "next" in st else "previous"
        return emit_command("media", act, "default", None, make_slots(device="music"), humanize_text(st, lang), 0.80)

    if style == "volume":
        direction = random.choice(["increase", "decrease"])
        val = random.randint(1, 20)
        if lang == "zh":
             # "Volume up by 2" -> "音量大兩格"
             v_str = to_zh_count(val)
             st = f"音量調{'大' if direction == 'increase' else '小'}{v_str}"
        else:
             st = f"turn volume {'up' if direction == 'increase' else 'down'} to {val}"
        return emit_command("media", direction, "default", None, make_slots(device="volume", value=val, unit="percent"), humanize_text(st, lang), 0.78)

    st = f"電視切到HDMI 1" if lang == "zh" else "switch TV input to HDMI 1"
    return emit_command("media", "set", "default", None, make_slots(device="tv", mode="source", value="HDMI 1"), humanize_text(st, lang), 0.78)

def gen_covers() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("curtain", lang)
    style = random.choice(["openclose", "position"])

    if style == "openclose":
        oc = random.choice(["open", "close"])
        if lang == "zh":
            v = "打開" if oc == "open" else "拉上"
            st = f"把{room_word}{dev_word}{v}"
        else:
            st = f"{oc} the {room_word} {dev_word}"
        return emit_command("covers", oc, norm_target, None, make_slots(device="curtain"), humanize_text(st, lang), 0.88)

    # Position
    pos = random.choice([20, 50, 80])
    if lang == "zh":
        st = f"{room_word}{dev_word}開到{pos}%"
    else:
        st = f"set {room_word} {dev_word} to {pos} percent"
    return emit_command("covers", "set_position", norm_target, None, make_slots(device="curtain", mode="position", value=pos, unit="percent"), humanize_text(st, lang), 0.84)

def gen_locks() -> Example:
    lang = "zh" if random.random() < 0.5 else "en"
    act = random.choice(["lock", "unlock"])
    if lang == "zh":
        st = random.choice(["把門鎖上", "鎖門", "門鎖起來"]) if act == "lock" else random.choice(["大門解鎖", "開門", "幫我開鎖"])
    else:
        st = f"{act} the front door"
    return emit_command("locks", act, "default", None, make_slots(device="front_door"), humanize_text(st, lang), 0.84)

def gen_vacuum() -> Example:
    base_room = pick_room(weight_default=0.0)
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("vacuum", lang)
    act = random.choice(["start", "stop", "dock", "set"])

    if lang == "zh":
        v_map = {
            "start": ["開始掃地", "啟動"], "stop": ["停止", "不要掃了"], 
            "dock": ["回去充電", "回家"], "set": [f"去掃{room_word}", f"清理{room_word}"]
        }
        st = f"{dev_word}{random.choice(v_map[act])}"
    else:
        v_map = {
            "start": ["start cleaning", "start"], "stop": ["stop cleaning", "stop"],
            "dock": ["dock", "return home"], "set": [f"clean the {room_word}", f"go to {room_word}"]
        }
        st = f"{random.choice(v_map[act])} the {dev_word}"

    if act == "set":
        return emit_command("vacuum", act, norm_target, None, make_slots(device="robot_vacuum", mode="room", value=norm_target), humanize_text(st, lang), 0.84)
    return emit_command("vacuum", act, "default", None, make_slots(device="robot_vacuum"), humanize_text(st, lang), 0.84)

def gen_timer() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    style = random.choice(["set", "cancel", "query"])
    
    if style == "set":
        val = random.randint(1, 120)
        is_sec = random.random() < 0.2
        unit = "seconds" if is_sec else "minutes"
        
        if lang == "zh":
            u_str = "秒" if is_sec else "分鐘"
            val_str = to_zh_count(val)
            st = f"幫我計時{val_str}{u_str}"
        else:
            u_str = "seconds" if is_sec else "minutes"
            st = f"set a timer for {val} {u_str}"
        
        has_room = room_word in st
        final_target = norm_target if has_room else "default"
        return emit_command("timer", "set_time", final_target, None, make_slots(device="timer", value=val, unit=unit), humanize_text(st, lang), 0.90)

    if style == "cancel":
        st = "取消計時" if lang == "zh" else "cancel the timer"
        return emit_command("timer", "stop", "default", None, make_slots(device="timer", mode="cancel"), humanize_text(st, lang), 0.86)

    st = "還有多久" if lang == "zh" else "how much time left"
    return emit_command("timer", "query", "default", None, make_slots(device="timer", mode="remaining"), humanize_text(st, lang), 0.76)

def gen_scene() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    scene = random.choice(["movie", "sleep", "away", "relax", "dinner", "party"])
    st = f"開啟{scene}模式" if lang == "zh" else f"activate {scene} scene"
    return emit_command("scene", "set_scene", "default", None, make_slots(device="scene", scene=scene), humanize_text(st, lang), 0.78)

def gen_query() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    qtype = random.choice(["light_state", "temp", "lock_state"])

    if qtype == "light_state":
        st = f"{room_word}燈有開嗎" if lang == "zh" else f"is the {room_word} light on"
        return emit_command("query", "query", norm_target, None, make_slots(device="light", mode="state"), humanize_text(st, lang), 0.86)
    
    if qtype == "temp":
        st = f"{room_word}幾度" if lang == "zh" else f"what's the temp in {room_word}"
        return emit_command("query", "query", norm_target, None, make_slots(device="temperature", mode="current", unit="celsius"), humanize_text(st, lang), 0.86)

    st = "門有鎖嗎" if lang == "zh" else "is the door locked"
    return emit_command("query", "query", "default", None, make_slots(device="lock", mode="state"), humanize_text(st, lang), 0.82)

def gen_transcript() -> Example:
    texts = [
        "Hello there", "今天天氣好冷", "我晚點再說", "你覺得怎麼樣", "哈哈哈",
        "turn on the light... uh actually never mind", "我剛剛說到哪",
        "What is the meaning of life?", "Tell me a joke"
    ]
    t = random.choice(texts)
    lang = "zh" if any(ord(c) > 128 for c in t) else "en"
    return emit_transcript(humanize_text(t, lang, noise_prob=0.0), 0.15)

# ==========================================
# 4. CORRECTION LOGIC
# ==========================================

def apply_correction(ex: Example) -> Example:
    """Wraps a valid command in a correction pattern."""
    if ex.type != "command" or ex.target == "default" or not ex.target:
        return ex
        
    false_room = pick_room()
    while false_room == "default" or false_room == ex.target:
        false_room = pick_room()
        
    is_zh = any(ord(c) > 128 for c in ex.raw_text)
    
    if is_zh:
        false_word = random.choice(ROOM_ALIASES_ZH.get(false_room, ["那個房間"]))
        correction = random.choice(["不對", "我是說", "喔不是", "等一下", "改錯了"])
        false_start = f"把{false_word}..."
        new_text = f"{false_start} {correction} {ex.raw_text}"
    else:
        false_word = random.choice(ROOM_ALIASES_EN.get(false_room, ["that room"]))
        correction = random.choice(["actually", "no wait", "sorry", "I mean", "scratch that"])
        false_start = f"Turn on the {false_word}..."
        new_text = f"{false_start} {correction} {ex.raw_text}"
    
    ex.raw_text = new_text
    ex.confidence -= 0.15
    return ex

# ==========================================
# 5. MAIN EXECUTION
# ==========================================

GENERATORS = [
    (gen_lights, 0.15), (gen_switches, 0.15), (gen_climate, 0.12),
    (gen_media, 0.12), (gen_covers, 0.10), (gen_locks, 0.05),
    (gen_vacuum, 0.08), (gen_timer, 0.08), (gen_scene, 0.05),
    (gen_query, 0.05), (gen_transcript, 0.05)
]

def generate(n: int) -> List[Example]:
    out = []
    
    # Normalize weights
    total_w = sum(w for _, w in GENERATORS)
    gens = [g for g, _ in GENERATORS]
    weights = [w/total_w for _, w in GENERATORS]
    
    batch_size = 100
    generated = 0
    
    while generated < n:
        batch = min(batch_size, n - generated)
        choices = random.choices(gens, weights, k=batch)
        
        for g_fn in choices:
            ex = g_fn()
            
            # Apply Correction Pattern (12% chance)
            if random.random() < 0.12:
                ex = apply_correction(ex)
                
            out.append(ex)
            
        generated += batch
    return out

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="smart_home_multidomain.jsonl")
    p.add_argument("--n", type=int, default=5000)
    args = p.parse_args()

    data = generate(args.n)
    with open(args.out, "w", encoding="utf-8") as f:
        for ex in data:
            f.write(json.dumps(asdict(ex), ensure_ascii=False) + "\n")
            
    print(f"Generated {args.n} highly variable examples to {args.out}")

if __name__ == "__main__":
    main()