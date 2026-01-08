import json
import random
import argparse
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple

random.seed(42)

ROOMS = [
    "bathroom", "kitchen", "bedroom", "living_room", 
    "dining_room", "study", "balcony", "hallway", "entryway", "default"
]

ROOM_ALIASES_ZH = {
    "bathroom": ["廁所", "浴室", "洗手間"],
    "kitchen": ["廚房"],
    "bedroom": ["房間", "臥室", "主臥"],
    "living_room": ["客廳", "大廳"],
    "dining_room": ["餐廳", "飯廳"],      
    "study": ["書房", "辦公室", "工作區"], 
    "balcony": ["陽台", "露台"],          
    "hallway": ["走廊", "過道"],          
    "entryway": ["玄關", "門口"],         
    "default": ["家裡", "全部", "所有地方"],
}

ROOM_ALIASES_EN = {
    "bathroom": ["bathroom", "restroom"],
    "kitchen": ["kitchen"],
    "bedroom": ["bedroom"],
    "living_room": ["living room"],
    "dining_room": ["dining room"],       
    "study": ["study", "office", "workspace"], 
    "balcony": ["balcony", "terrace"],    
    "hallway": ["hallway", "corridor"],   
    "entryway": ["entryway", "foyer"],    
    "default": ["the house", "everywhere"],
}

EXTRA_ROOM_ALIASES_ZH = {
    "guest_room": ["客房"],
    "kids_room": ["小孩房", "兒童房"],
    "garage": ["車庫"],
    "basement": ["地下室"],
    "attic": ["頂樓"],
    "closet": ["儲藏室", "衣帽間"],
}

EXTRA_ROOM_ALIASES_EN = {
    "guest_room": ["guest room"],
    "kids_room": ["kids room", "children's room"],
    "garage": ["garage"],
    "basement": ["basement"],
    "attic": ["attic"],
    "closet": ["closet", "pantry"],
}

EXTRA_ROOM_TO_TARGET = {
    "guest_room": "bedroom",
    "kids_room": "bedroom",
    "garage": "default",
    "basement": "default",
    "attic": "default",
    "closet": "default",
}

SWITCH_DEVICES = [
    "fan", "humidifier", "diffuser", "plug", "air_purifier",
    "dehumidifier", "heater", "coffee_maker", "rice_cooker",
    "kettle", "water_heater", "washer", "dryer", "oven",
]

SWITCH_DEV_ZH = {
    "fan": ["風扇", "電扇", "循環扇"],
    "humidifier": ["加濕器", "水氧機"],
    "diffuser": ["香氛機", "擴香"],
    "plug": ["插座", "插頭", "電源"],
    "air_purifier": ["空氣清淨機", "清淨機"],
    "dehumidifier": ["除濕機"],
    "heater": ["暖氣", "暖爐", "電暖器"],
    "coffee_maker": ["咖啡機"],
    "rice_cooker": ["電鍋", "電子鍋"],
    "kettle": ["熱水壺", "快煮壺"],
    "water_heater": ["熱水器"],
    "washer": ["洗衣機"],
    "dryer": ["烘衣機"],
    "oven": ["烤箱"],
}

SWITCH_DEV_EN = {
    "fan": ["fan", "ceiling fan", "desk fan", "ventilator"],
    "humidifier": ["humidifier"],
    "diffuser": ["diffuser", "aroma diffuser"],
    "plug": ["plug", "socket", "outlet", "smart plug"],
    "air_purifier": ["air purifier", "purifier"],
    "dehumidifier": ["dehumidifier"],
    "heater": ["heater", "radiator", "space heater"],
    "coffee_maker": ["coffee maker", "coffee machine"],
    "rice_cooker": ["rice cooker"],
    "kettle": ["kettle", "electric kettle"],
    "water_heater": ["water heater", "boiler"],
    "washer": ["washer", "washing machine"],
    "dryer": ["dryer", "clothes dryer"],
    "oven": ["oven"],
}

DEVICE_VARIANTS_EN = {
    "light": ["light", "lights", "lamp", "lamps", "lighting", "LEDs", "strip lights", "ceiling light", "reading lamp", "spotlight", "chandelier", "downlight"],
    "ac": ["AC", "air conditioner", "A/C", "cooling unit", "air con", "thermostat", "climate control"],
    "tv": ["TV", "television", "telly", "screen", "display", "monitor", "smart TV"],
    "vacuum": ["vacuum", "robot vacuum", "roomba", "sweeper", "bot", "cleaner", "mopping robot"],
    "curtain": ["curtain", "drapes", "shades", "blinds", "shutters", "blackout curtains", "roller shades"],
    "speaker": ["speaker", "sound system", "audio", "woofer", "bluetooth speaker"],
    "soundbar": ["soundbar", "sound bar"],
}

DEVICE_VARIANTS_ZH = {
    "light": ["燈", "電燈", "照明", "光", "檯燈", "吊燈", "吸頂燈", "落地燈", "壁燈", "LED燈", "嵌燈"],
    "ac": ["冷氣", "空調", "冷氣機", "暖氣", "恆溫器"],
    "tv": ["電視", "電視機", "螢幕", "顯示器"],
    "vacuum": ["掃地機", "吸塵器", "機器人", "掃地機器人", "拖地機", "掃拖機"],
    "curtain": ["窗簾", "布簾", "百葉窗", "捲簾", "遮光簾", "紗簾"],
    "speaker": ["喇叭", "音響", "揚聲器", "藍芽喇叭"],
    "soundbar": ["聲霸", "家庭劇院"],
}

ADJECTIVES_EN = ["main", "big", "small", "ceiling", "floor", "desk", "bedside", "reading", "smart", "old", "new"]
ADJECTIVES_ZH = ["主", "大", "小", "天花板", "地板", "桌上", "床頭", "閱讀", "智慧", "舊", "新"]

FILLERS_EN = ["uh", "um", "like", "you know", "actually", "er", "ah", "maybe", "please", "hmm", "well"]
FILLERS_ZH = ["那個", "呃", "嗯", "就是", "那個...應...", "阿", "好像是", "麻煩", "欸", "我想"]

PREFIXES_EN = ["Could you", "Please", "Can you", "Hey,", "I need you to", "Would you mind to", "Just", "Quickly", "Go ahead and", "Time to", "Help me"]
PREFIXES_ZH = ["麻煩", "請", "幫我", "可以幫我", "那個", "欸", "快速", "我想", "這時候", "去"]

def pick_room(weight_default: float = 0.25) -> str:
    if random.random() < weight_default:
        return "default"
    return random.choice([r for r in ROOMS if r != "default"])

def zh_room(room: str) -> str:
    return random.choice(ROOM_ALIASES_ZH[room])

def en_room(room: str) -> str:
    return random.choice(ROOM_ALIASES_EN[room])

def clamp_conf(x: float) -> float:
    return max(0.0, min(1.0, round(x, 2)))

def pick_room_word_and_target(base_target: str) -> Tuple[str, str, str]:
    lang = "mix"
    if random.random() < 0.70:
        if random.random() < 0.5:
            lang = "zh"
            return zh_room(base_target), base_target, lang
        lang = "en"
        return en_room(base_target), base_target, lang

    extra_key = random.choice(list(EXTRA_ROOM_TO_TARGET.keys()))
    normalized_target = EXTRA_ROOM_TO_TARGET[extra_key]
    
    if random.random() < 0.5:
        lang = "zh"
        room_word = random.choice(EXTRA_ROOM_ALIASES_ZH[extra_key])
    else:
        lang = "en"
        room_word = random.choice(EXTRA_ROOM_ALIASES_EN[extra_key])
        
    return room_word, normalized_target, lang

def _value_to_str(v):
    if v is None: return None
    if isinstance(v, bool): return "true" if v else "false"
    return str(v)

def _value_to_num(v):
    if v is None: return None
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)): return float(v)
    try:
        return float(str(v))
    except Exception:
        return None

def make_slots(device=None, value=None, unit=None, mode=None, scene=None, duration_sec=None) -> Dict[str, Any]:
    return {
        "device": device,
        "value": _value_to_str(value),
        "value_num": _value_to_num(value),
        "unit": unit,
        "mode": mode,
        "scene": scene,
        "duration_sec": duration_sec,
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
    conf = clamp_conf(base_conf + random.uniform(-0.08, 0.06))
    return Example("command", domain, action, target, state, slots, text, conf)

def emit_transcript(text, base_conf=0.15) -> Example:
    conf = clamp_conf(base_conf + random.uniform(-0.10, 0.10))
    return Example("transcript", "unknown", "none", None, None, make_slots(), text, conf)

def inject_noise(text: str, lang: str, prob: float = 0.45) -> str:
    if random.random() > prob:
        return text

    words = text.split()
    if not words: return text

    fillers = FILLERS_ZH if lang == "zh" else FILLERS_EN
    
    if random.random() < 0.3:
        words.insert(0, random.choice(fillers) + "...")
    
    if len(words) > 2 and random.random() < 0.4:
        idx = random.randint(1, len(words)-1)
        words.insert(idx, random.choice(fillers))

    if random.random() < 0.2:
        idx = random.randint(0, len(words)-1)
        words.insert(idx, words[idx])

    return " ".join(words)

def get_granular_device(dev_type: str, lang: str) -> str:
    if lang == "zh":
        variants = DEVICE_VARIANTS_ZH.get(dev_type, [dev_type])
        base = random.choice(variants)
        if random.random() < 0.25:
            adj = random.choice(ADJECTIVES_ZH)
            return f"{adj}{base}"
        return base
    else:
        variants = DEVICE_VARIANTS_EN.get(dev_type, [dev_type])
        base = random.choice(variants)
        if random.random() < 0.25:
            adj = random.choice(ADJECTIVES_EN)
            return f"{adj} {base}"
        return base

def get_granular_switch(dev_type: str, lang: str) -> str:
    if lang == "zh":
        variants = SWITCH_DEV_ZH.get(dev_type, [dev_type])
        base = random.choice(variants)
        if random.random() < 0.15:
            adj = random.choice(ADJECTIVES_ZH)
            return f"{adj}{base}"
        return base
    else:
        variants = SWITCH_DEV_EN.get(dev_type, [dev_type])
        base = random.choice(variants)
        if random.random() < 0.15:
            adj = random.choice(ADJECTIVES_EN)
            return f"{adj} {base}"
        return base

def gen_lights() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    
    dev_word = get_granular_device("light", lang)
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"

    if lang == "zh":
        verbs = ["打開", "開一下", "開啟", "啟動", "亮起來"] if onoff == "on" else ["關掉", "關一下", "關閉", "熄滅"]
        verb = random.choice(verbs)
        prefix = random.choice(PREFIXES_ZH) if random.random() < 0.4 else ""
        
        structure = random.choice([
            f"{prefix}{verb}{room_word}{dev_word}",
            f"{prefix}{room_word}{dev_word}{verb}",
            f"把{room_word}{dev_word}{verb}",
            f"{room_word}{dev_word}幫我{verb}"
        ])
    else:
        verbs = ["turn on", "switch on", "activate", "enable", "power on"] if onoff == "on" else ["turn off", "switch off", "deactivate", "disable", "kill", "cut"]
        verb = random.choice(verbs)
        prefix = random.choice(PREFIXES_EN) if random.random() < 0.4 else ""
        
        structure = random.choice([
            f"{prefix} {verb} the {room_word} {dev_word}",
            f"{prefix} {verb} the {dev_word} in the {room_word}",
            f"{room_word} {dev_word} {verb}",
            f"{prefix} make the {room_word} {dev_word} {onoff}"
        ])
    
    phr = inject_noise(structure.strip(), lang)
    return emit_command("lights", action, norm_target, onoff, make_slots(device="light"), phr, 0.92)

def gen_switches() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev = random.choice(SWITCH_DEVICES)
    dev_word = get_granular_switch(dev, lang)
    
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"

    if lang == "zh":
        verbs = ["打開", "開一下", "開啟"] if onoff == "on" else ["關掉", "關一下", "關閉"]
        verb = random.choice(verbs)
        prefix = random.choice(PREFIXES_ZH) if random.random() < 0.4 else ""
        
        structure = random.choice([
            f"{prefix}幫我把{room_word}{dev_word}{verb}",
            f"{prefix}{room_word}{dev_word}{verb}",
            f"{dev_word}在{room_word}{verb}"
        ])
    else:
        verbs = ["turn on", "switch on", "start"] if onoff == "on" else ["turn off", "switch off", "stop"]
        verb = random.choice(verbs)
        prefix = random.choice(PREFIXES_EN) if random.random() < 0.4 else ""
        
        structure = random.choice([
            f"{prefix} {verb} the {dev_word} in the {room_word}",
            f"{prefix} {verb} the {room_word} {dev_word}",
            f"{room_word} {dev_word} {verb}"
        ])

    final_target = norm_target if room_word in structure else "default"
    phr = inject_noise(structure.strip(), lang)
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
            phr = f"{room_word}{dev_word}{v}" if random.random() < 0.6 else f"把{dev_word}{v}"
        else:
            v = "turn on" if onoff == "on" else "turn off"
            phr = f"{v} the {room_word} {dev_word}" if random.random() < 0.6 else f"{v} the {dev_word}"
        
        final_target = norm_target if room_word in phr else "default"
        phr = inject_noise(phr, lang)
        return emit_command("climate", action, final_target, onoff, make_slots(device="ac"), phr, 0.90)

    if style == "set":
        temp = random.randint(16, 30)
        if lang == "zh":
            phr = random.choice([
                f"{room_word}{dev_word}調到{temp}度", 
                f"溫度設為{temp}",
                f"幫我把{room_word}氣溫設在{temp}"
            ])
        else:
            phr = random.choice([
                f"set {room_word} {dev_word} to {temp} degrees", 
                f"make it {temp} degrees in the {room_word}",
                f"change temp to {temp}"
            ])
        
        final_target = norm_target if room_word in phr else "default"
        phr = inject_noise(phr, lang)
        return emit_command("climate", "set", final_target, None, make_slots(device="thermostat", value=temp, unit="c", mode="setpoint"), phr, 0.86)

    if style == "mode":
        mode = random.choice(["cool", "heat", "dry", "fan_only"])
        if lang == "zh":
            zh_mode = {"cool": "冷房", "heat": "暖房", "dry": "除濕", "fan_only": "送風"}[mode]
            phr = f"{room_word}{dev_word}切到{zh_mode}"
        else:
            phr = f"set {room_word} {dev_word} mode to {mode}"
        
        final_target = norm_target if room_word in phr else "default"
        phr = inject_noise(phr, lang)
        return emit_command("climate", "set", final_target, None, make_slots(device="ac", mode=mode), phr, 0.82)

    if style == "delta":
        delta = random.randint(1, 5)
        inc = random.choice([True, False])
        if lang == "zh":
            phr = f"溫度調{'高' if inc else '低'}{delta}度"
        else:
            phr = f"turn the temperature {'up' if inc else 'down'} by {delta} degrees"
        
        phr = inject_noise(phr, lang)
        return emit_command("climate", "increase" if inc else "decrease", "default", None, make_slots(device="thermostat", value=delta, unit="c"), phr, 0.76)

    phr_opts = [
        (f"{room_word}好熱", True, "cool"), (f"{room_word}有點冷", True, "heat"),
        ("有點悶", False, "cool"), ("It's too hot", False, "cool"), ("I'm freezing", False, "heat"),
    ]
    base_phr, uses_room, mode = random.choice(phr_opts)
    final_target = norm_target if uses_room else "default"
    phr = inject_noise(base_phr, lang)
    return emit_command("climate", "turn_on", final_target, "on", make_slots(device="ac", mode=mode), phr, 0.60)

def gen_media() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    style = random.choice(["tv_power", "audio_power", "playback", "volume", "source", "implicit"])
    
    if style == "tv_power":
        dev_word = get_granular_device("tv", lang)
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"
        if lang == "zh":
            phr = f"幫我{room_word}{dev_word}{'打開' if onoff == 'on' else '關掉'}"
        else:
            phr = f"turn {onoff} the {room_word} {dev_word}"
        
        phr = inject_noise(phr, lang)
        return emit_command("media", action, norm_target, onoff, make_slots(device="tv"), phr, 0.86)

    if style == "audio_power":
        dev = random.choice(["speaker", "soundbar"])
        dev_word = get_granular_device(dev, lang)
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"
        if lang == "zh":
            phr = f"{room_word}{dev_word}{'開一下' if onoff == 'on' else '關一下'}"
        else:
            phr = f"switch {onoff} the {room_word} {dev_word}"
        
        phr = inject_noise(phr, lang)
        return emit_command("media", action, norm_target, onoff, make_slots(device=dev), phr, 0.82)

    if style == "playback":
        if lang == "zh":
            map_zh = {
                "pause": ["暫停播放", "先暫停"],
                "resume": ["繼續放", "恢復播放"],
                "stop": ["停止", "不要放了"],
                "next": ["下一首", "切歌"],
                "previous": ["上一首", "回上一首"]
            }
            action = random.choice(list(map_zh.keys()))
            phr = random.choice(map_zh[action])
        else:
            map_en = {
                "pause": ["pause music", "pause"],
                "resume": ["resume playback", "continue music"],
                "stop": ["stop", "stop music"],
                "next": ["next track", "skip song"],
                "previous": ["previous song", "go back"]
            }
            action = random.choice(list(map_en.keys()))
            phr = random.choice(map_en[action])
        
        phr = inject_noise(phr, lang)
        return emit_command("media", action, "default", None, make_slots(device="music"), phr, 0.80)

    if style == "volume":
        direction = random.choice(["increase", "decrease"])
        val = random.randint(1, 20)
        if lang == "zh":
            phr = f"音量調{'大' if direction == 'increase' else '小'}{val}"
        else:
            phr = f"turn volume {'up' if direction == 'increase' else 'down'} to {val}"
        
        phr = inject_noise(phr, lang)
        return emit_command("media", direction, "default", None, make_slots(device="volume", value=val, unit="step"), phr, 0.78)

    if style == "source":
        src = random.choice(["HDMI1", "HDMI2", "YouTube", "Netflix", "Spotify"])
        if lang == "zh":
            phr = f"電視切到{src}"
        else:
            phr = f"switch TV input to {src}"
        phr = inject_noise(phr, lang)
        return emit_command("media", "set", "default", None, make_slots(device="tv", mode="source", value=src), phr, 0.78)

    phr = random.choice(["太吵了", "小聲一點", "聽不到耶", "It’s too loud", "I can’t hear it"])
    phr = inject_noise(phr, lang)
    if ("聽不到" in phr) or ("hear" in phr):
        return emit_command("media", "increase", "default", None, make_slots(device="volume", value=2, unit="step"), phr, 0.62)
    return emit_command("media", "decrease", "default", None, make_slots(device="volume", value=2, unit="step"), phr, 0.62)

def gen_covers() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("curtain", lang)
    style = random.choice(["openclose", "position", "implicit"])

    if style == "openclose":
        oc = random.choice(["open", "close"])
        if lang == "zh":
            v = "打開" if oc == "open" else "拉上"
            phr = f"把{room_word}{dev_word}{v}"
        else:
            phr = f"{oc} the {room_word} {dev_word}"
        
        phr = inject_noise(phr, lang)
        return emit_command("covers", oc, norm_target, None, make_slots(device="curtain"), phr, 0.88)

    if style == "position":
        pos = random.randint(0, 100)
        if lang == "zh":
            phr = f"{room_word}{dev_word}開到{pos}%"
        else:
            phr = f"set {room_word} {dev_word} to {pos} percent"
        
        phr = inject_noise(phr, lang)
        return emit_command("covers", "set", norm_target, None, make_slots(device="curtain", mode="position", value=pos, unit="percent"), phr, 0.84)

    phr = random.choice(["太亮了", "陽光好大", "Make it darker", "Too bright in here"])
    phr = inject_noise(phr, lang)
    return emit_command("covers", "close", "default", None, make_slots(device="curtain"), phr, 0.66)

def gen_locks() -> Example:
    lang = "zh" if random.random() < 0.5 else "en"
    act = random.choice(["lock", "unlock"])
    
    if lang == "zh":
        phr = random.choice(["把門鎖上", "鎖門", "大門解鎖", "開門"])
        if ("解鎖" in phr) or (phr == "開門"): act = "unlock"
        else: act = "lock"
    else:
        phr = f"{act} the front door"
    
    phr = inject_noise(phr, lang)
    return emit_command("locks", act, "default", None, make_slots(device="front_door"), phr, 0.84)

def gen_vacuum() -> Example:
    base_room = pick_room(weight_default=0.0)
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("vacuum", lang)
    
    actions = ["start", "stop", "pause", "resume", "dock", "set"]
    act = random.choice(actions)

    if lang == "zh":
        v_map = {
            "start": ["開始掃地", "啟動", "掃地"], 
            "stop": ["停止", "不要掃了"], 
            "pause": ["暫停"], 
            "resume": ["繼續"], 
            "dock": ["回去充電", "回充"], 
            "set": [f"去掃{room_word}"]
        }
        phr = f"{dev_word}{random.choice(v_map[act])}"
    else:
        v_map = {
            "start": ["start cleaning", "start"], 
            "stop": ["stop", "stop cleaning"], 
            "pause": ["pause"], 
            "resume": ["resume"], 
            "dock": ["dock", "return home"], 
            "set": [f"clean the {room_word}"]
        }
        phr = f"{random.choice(v_map[act])} the {dev_word}"

    if act == "set":
        target = norm_target
        slots = make_slots(device="robot_vacuum", mode="room", value=norm_target)
    else:
        target = "default"
        slots = make_slots(device="robot_vacuum")

    phr = inject_noise(phr, lang)
    return emit_command("vacuum", act, target, None, slots, phr, 0.84)

def gen_timer() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    style = random.choice(["set", "cancel", "query"])
    
    if style == "set":
        val = random.randint(1, 120)
        is_sec = random.random() < 0.2
        unit = "sec" if is_sec else "min"
        duration = val if is_sec else val * 60
        
        if lang == "zh":
            u_str = "秒" if is_sec else "分鐘"
            phr = f"幫我計時{val}{u_str}"
        else:
            u_str = "seconds" if is_sec else "minutes"
            phr = f"set a timer for {val} {u_str}"
            
        phr = inject_noise(phr, lang)
        final_target = norm_target if room_word in phr else "default"
        
        return emit_command("timer", "set", final_target, None, make_slots(device="timer", value=val, unit=unit, duration_sec=None), phr, 0.90)

    if style == "cancel":
        phr = "取消計時" if lang == "zh" else "cancel the timer"
        phr = inject_noise(phr, lang)
        return emit_command("timer", "stop", "default", None, make_slots(device="timer", mode="cancel"), phr, 0.86)

    phr = "還有多久" if lang == "zh" else "how much time left"
    phr = inject_noise(phr, lang)
    return emit_command("timer", "query", "default", None, make_slots(device="timer", mode="remaining"), phr, 0.76)

def gen_scene() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    scene = random.choice(["movie", "sleep", "away", "relax", "dinner", "work"])
    
    if lang == "zh":
        phr = f"開啟{scene}模式"
    else:
        phr = f"activate {scene} scene"
        
    phr = inject_noise(phr, lang)
    
    final_target = norm_target if room_word in phr else "default"

    return emit_command("scene", "set", final_target, None, make_slots(device="scene", scene=scene), phr, 0.78)

def gen_query() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    qtype = random.choice(["light_state", "temp", "lock_state", "vacuum_state"])

    if qtype == "light_state":
        phr = f"{room_word}燈有開嗎" if lang == "zh" else f"is the {room_word} light on"
        return emit_command("query", "query", norm_target, None, make_slots(device="light", mode="state"), inject_noise(phr, lang), 0.86)
    
    if qtype == "temp":
        phr = f"{room_word}幾度" if lang == "zh" else f"what's the temp in {room_word}"
        return emit_command("query", "query", norm_target, None, make_slots(device="temperature", mode="current", unit="c"), inject_noise(phr, lang), 0.86)

    return emit_command("query", "query", "default", None, make_slots(device="generic"), inject_noise("what's going on", lang), 0.50)

def gen_transcript() -> Example:
    texts = [
        "Hello there", "今天天氣好冷", "我晚點再說", "你覺得怎麼樣", "哈哈哈",
        "turn on the light... uh actually never mind", "我剛剛說到哪",
        "我想開心一點", "Turn on your charm",
        "幫我訂披薩", "Order a pizza", "I want to buy a new vacuum",
        "我想買一台掃地機", "Buy me a new TV", "幫我網購一台冷氣",
        "電視壞掉了怎麼辦", "冷氣好像有點怪怪的", "門鎖是不是該換了",
        "窗簾好漂亮", "掃地機卡住了", "The vacuum is stuck"
    ]
    t = random.choice(texts)
    lang = "zh" if any(ord(c) > 128 for c in t) else "en"
    t = inject_noise(t, lang)
    base = 0.08 if ("Hello" in t or "哈哈" in t) else 0.15
    return emit_transcript(t, base)

GENERATORS = [
    ("lights", gen_lights), ("switches", gen_switches), ("climate", gen_climate),
    ("media", gen_media), ("covers", gen_covers), ("locks", gen_locks),
    ("vacuum", gen_vacuum), ("timer", gen_timer), ("scene", gen_scene),
    ("query", gen_query), ("transcript", gen_transcript),
]

def generate(n: int, transcript_ratio: float = 0.30) -> List[Example]:
    weights = {
        "lights": 0.14, "switches": 0.14, "climate": 0.12, "media": 0.12,
        "covers": 0.10, "locks": 0.06, "vacuum": 0.09, "timer": 0.08,
        "scene": 0.06, "query": 0.12, "transcript": transcript_ratio,
    }
    total = sum(weights.values())
    for k in weights: weights[k] /= total

    name_to_fn = {name: fn for name, fn in GENERATORS}
    names = list(weights.keys())
    probs = [weights[n] for n in names]

    out = []
    
    batch_size = 1000
    generated = 0
    while generated < n:
        current_batch = min(batch_size, n - generated)
        choices = random.choices(names, probs, k=current_batch)
        for domain in choices:
            out.append(name_to_fn[domain]())
        generated += current_batch
        
    return out

def row_to_target_json(row: dict) -> dict:
    slots = row.get("slots") or {}
    norm_slots = {**make_slots(), **slots}
    obj = {
        "type": row.get("type"),
        "domain": row.get("domain"),
        "action": row.get("action"),
        "target": row.get("target"),
        "state": row.get("state"),
        "slots": norm_slots,
        "raw_text": row.get("raw_text", ""),
        "confidence": float(row.get("confidence", 0.0)),
    }
    if obj["type"] != "command":
        obj["domain"] = "unknown"
        obj["action"] = "none"
        obj["target"] = None
        obj["state"] = None
        obj["slots"] = make_slots()
    return obj

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="smart_home_multidomain.jsonl")
    p.add_argument("--n", type=int, default=5000)
    p.add_argument("--transcript_ratio", type=float, default=0.30)
    args = p.parse_args()

    data = generate(args.n, args.transcript_ratio)
    with open(args.out, "w", encoding="utf-8") as f:
        for ex in data:
            f.write(json.dumps(asdict(ex), ensure_ascii=False) + "\n")
    print(f"Wrote {args.n} examples to {args.out}")

if __name__ == "__main__":
    main()