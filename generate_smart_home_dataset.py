import json
import random
import argparse
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple

random.seed(42)

ROOMS = ["bathroom", "kitchen", "bedroom", "living_room", "default"]

ROOM_ALIASES_ZH = {
    "bathroom": ["廁所", "浴室", "洗手間"],
    "kitchen": ["廚房"],
    "bedroom": ["房間", "臥室", "主臥", "我的房間"],
    "living_room": ["客廳", "大廳"],
    "default": ["家裡", "全部", "所有地方"],
}
ROOM_ALIASES_EN = {
    "bathroom": ["bathroom", "restroom"],
    "kitchen": ["kitchen"],
    "bedroom": ["bedroom"],
    "living_room": ["living room"],
    "default": ["the house", "everywhere"],
}

EXTRA_ROOM_ALIASES_ZH = {
    "study": ["書房", "辦公室"],
    "dining": ["餐廳"],
    "hallway": ["走廊"],
    "balcony": ["陽台"],
    "entryway": ["玄關", "門口"],
    "guest_room": ["客房"],
    "kids_room": ["小孩房", "兒童房"],
    "garage": ["車庫"],
    "basement": ["地下室"],
    "attic": ["頂樓"],
}
EXTRA_ROOM_ALIASES_EN = {
    "study": ["study", "office"],
    "dining": ["dining room"],
    "hallway": ["hallway", "corridor"],
    "balcony": ["balcony"],
    "entryway": ["entryway", "foyer"],
    "guest_room": ["guest room"],
    "kids_room": ["kids room", "children's room"],
    "garage": ["garage"],
    "basement": ["basement"],
    "attic": ["attic"],
}

EXTRA_ROOM_TO_TARGET = {
    "study": "bedroom",
    "dining": "living_room",
    "entryway": "living_room",
    "guest_room": "bedroom",
    "kids_room": "bedroom",
    "hallway": "default",
    "balcony": "default",
    "garage": "default",
    "basement": "default",
    "attic": "default",
}

SWITCH_DEVICES = [
    "fan", "humidifier", "diffuser", "plug", "air_purifier",
    "dehumidifier", "heater", "coffee_maker", "rice_cooker",
    "kettle", "water_heater", "washer", "dryer", "oven",
]
SWITCH_DEV_ZH = {
    "fan": "風扇",
    "humidifier": "加濕器",
    "diffuser": "香氛機",
    "plug": "插座",
    "air_purifier": "空氣清淨機",
    "dehumidifier": "除濕機",
    "heater": "暖氣",
    "coffee_maker": "咖啡機",
    "rice_cooker": "電鍋",
    "kettle": "熱水壺",
    "water_heater": "熱水器",
    "washer": "洗衣機",
    "dryer": "烘衣機",
    "oven": "烤箱",
}

MEDIA_AUDIO_DEVICES = ["speaker", "soundbar"]

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

def pick_room_word_and_target(base_target: str) -> Tuple[str, str]:
    if random.random() < 0.70:
        if random.random() < 0.5:
            return zh_room(base_target), base_target
        return en_room(base_target), base_target

    extra_key = random.choice(list(EXTRA_ROOM_TO_TARGET.keys()))
    normalized_target = EXTRA_ROOM_TO_TARGET[extra_key]
    if random.random() < 0.5:
        room_word = random.choice(EXTRA_ROOM_ALIASES_ZH[extra_key])
    else:
        room_word = random.choice(EXTRA_ROOM_ALIASES_EN[extra_key])
    return room_word, normalized_target

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

def resolve_target(text: str, room_word: str, norm_target: str) -> str:
    if room_word in text:
        return norm_target
    return "default"

def gen_lights() -> Example:
    base_room = pick_room()
    room_word, norm_target = pick_room_word_and_target(base_room)
    
    style = random.choice(["zh", "en", "mix", "implicit"])
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"

    if style == "zh":
        phr = random.choice([
            f"幫我開{room_word}燈", f"請把{room_word}燈打開", f"{room_word}燈開一下",
        ]) if onoff == "on" else random.choice([
            f"幫我關{room_word}燈", f"請把{room_word}燈關掉", f"{room_word}燈關一下",
        ])
        return emit_command("lights", action, norm_target, onoff, make_slots(device="light"), phr, 0.92)

    if style == "en":
        phr = random.choice([
            f"Turn on the {room_word} lights", f"Switch on the {room_word} light",
        ]) if onoff == "on" else random.choice([
            f"Turn off the {room_word} lights", f"Switch off the {room_word} light",
        ])
        return emit_command("lights", action, norm_target, onoff, make_slots(device="light"), phr, 0.92)

    if style == "mix":
        phr = random.choice([
            f"turn on {room_word}燈", f"Turn off {room_word}燈",
            f"{room_word} light on", f"{room_word} light off",
        ])
        inferred = "on" if ("on" in phr and "off" not in phr) else "off"
        act = "turn_on" if inferred == "on" else "turn_off"
        return emit_command("lights", act, norm_target, inferred, make_slots(device="light"), phr, 0.85)

    # Implicit - often implies current room (default) unless room explicitly named
    phr_opts = [
        (f"{room_word}有點暗", True),
        (f"{room_word}太暗了", True),
        (f"{room_word}太亮了", True),
        ("有點暗耶", False),
        ("太亮了", False),
        ("Make it brighter", False),
        ("It's too bright", False),
    ]
    phr, uses_room = random.choice(phr_opts)
    final_target = norm_target if uses_room else "default"
    
    if ("太亮" in phr) or ("too bright" in phr):
        return emit_command("lights", "turn_off", final_target, "off", make_slots(device="light"), phr, 0.70)
    return emit_command("lights", "turn_on", final_target, "on", make_slots(device="light"), phr, 0.70)

def gen_switches() -> Example:
    base_room = pick_room()
    room_word, norm_target = pick_room_word_and_target(base_room)
    dev = random.choice(SWITCH_DEVICES)
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"
    style = random.choice(["zh", "en", "mix", "implicit"])

    if style == "zh":
        name = SWITCH_DEV_ZH[dev]
        phr = random.choice([
            f"幫我把{room_word}{name}打開", f"{room_word}{name}開一下",
        ]) if onoff == "on" else random.choice([
            f"幫我把{room_word}{name}關掉", f"{room_word}{name}關一下",
        ])
        return emit_command("switches", action, norm_target, onoff, make_slots(device=dev), phr, 0.86)

    if style == "en":
        phr = random.choice([
            f"Turn on the {dev} in the {room_word}", f"Switch on the {dev}",
        ]) if onoff == "on" else random.choice([
            f"Turn off the {dev} in the {room_word}", f"Switch off the {dev}",
        ])
        final_target = norm_target if room_word in phr else "default"
        return emit_command("switches", action, final_target, onoff, make_slots(device=dev), phr, 0.84)

    if style == "implicit":
        phr_opts = [
            (f"{room_word}好悶", True),
            (f"{room_word}有點臭", True),
            (f"{room_word}太潮了", True),
            (f"It's too humid in the {room_word}", True),
            (f"It smells in the {room_word}", True),
            ("空氣不太好", False),
            ("有點悶", False),
            ("好潮濕", False),
        ]
        phr, uses_room = random.choice(phr_opts)
        final_target = norm_target if uses_room else "default"

        if ("潮" in phr) or ("humid" in phr):
            return emit_command("switches", "turn_on", final_target, "on", make_slots(device="dehumidifier"), phr, 0.65)
        if ("悶" in phr):
            return emit_command("switches", "turn_on", final_target, "on", make_slots(device="fan"), phr, 0.62)
        return emit_command("switches", "turn_on", final_target, "on", make_slots(device="air_purifier"), phr, 0.62)

    phr = random.choice([f"turn on {room_word} {dev}", f"turn off {room_word} {dev}"])
    inferred = "on" if "on" in phr else "off"
    act = "turn_on" if inferred == "on" else "turn_off"
    return emit_command("switches", act, norm_target, inferred, make_slots(device=dev), phr, 0.80)

def gen_climate() -> Example:
    base_room = pick_room()
    room_word, norm_target = pick_room_word_and_target(base_room)
    style = random.choice(["zh_power", "en_power", "set", "mode", "delta", "implicit"])

    if style == "zh_power":
        phr = random.choice([f"開{room_word}冷氣", f"{room_word}冷氣打開", "冷氣打開"])
        final_target = norm_target if room_word in phr else "default"
        return emit_command("climate", "turn_on", final_target, "on", make_slots(device="ac", mode="cool"), phr, 0.90)

    if style == "en_power":
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"
        phr = random.choice([
            f"Turn {onoff} the AC in the {room_word}", f"Switch {onoff} the air conditioner"
        ])
        final_target = norm_target if room_word in phr else "default"
        return emit_command("climate", action, final_target, onoff, make_slots(device="ac"), phr, 0.88)

    if style == "set":
        temp = random.choice([18, 20, 22, 24, 26, 28])
        phr = random.choice([
            f"{room_word}冷氣調到{temp}度", f"Set the {room_word} temperature to {temp}", f"把溫度設{temp}度"
        ])
        final_target = norm_target if room_word in phr else "default"
        return emit_command("climate", "set", final_target, None, make_slots(device="thermostat", value=temp, unit="c", mode="setpoint"), phr, 0.86)

    if style == "mode":
        mode = random.choice(["cool", "heat", "dry", "fan_only"])
        zh_mode = {"cool": "冷房", "heat": "暖房", "dry": "除濕", "fan_only": "送風"}[mode]
        phr = random.choice([f"{room_word}冷氣切到{zh_mode}", f"Set AC mode to {mode}"])
        final_target = norm_target if room_word in phr else "default"
        return emit_command("climate", "set", final_target, None, make_slots(device="ac", mode=mode), phr, 0.82)

    if style == "delta":
        delta = random.choice([1, 2, 3])
        inc = random.choice([True, False])
        phr = random.choice([
            f"溫度調高{delta}度" if inc else f"溫度調低{delta}度",
            f"Make it {delta} degrees warmer" if inc else f"Make it {delta} degrees cooler",
        ])
        return emit_command("climate", "increase" if inc else "decrease", "default", None, make_slots(device="thermostat", value=delta, unit="c"), phr, 0.76)

    phr_opts = [
        (f"{room_word}好熱", True), (f"{room_word}有點冷", True),
        ("有點悶", False), ("It's too hot", False), ("I'm freezing", False),
    ]
    phr, uses_room = random.choice(phr_opts)
    final_target = norm_target if uses_room else "default"

    if ("熱" in phr) or ("too hot" in phr):
        return emit_command("climate", "turn_on", final_target, "on", make_slots(device="ac", mode="cool"), phr, 0.62)
    if ("冷" in phr) or ("freezing" in phr):
        return emit_command("climate", "set", final_target, None, make_slots(device="ac", mode="heat"), phr, 0.58)
    return emit_command("climate", "turn_on", final_target, "on", make_slots(device="ac", mode="cool"), phr, 0.58)

def gen_media() -> Example:
    base_room = pick_room()
    room_word, norm_target = pick_room_word_and_target(base_room)
    style = random.choice(["tv_power", "audio_power", "playback", "volume", "source", "implicit"])

    if style == "tv_power":
        onoff = random.choice(["on", "off"])
        phr = random.choice([
            f"Turn {onoff} the TV in the {room_word}", f"{'開' if onoff == 'on' else '關'}一下{room_word}電視",
            f"Turn {onoff} the TV"
        ])
        final_target = norm_target if room_word in phr else "default"
        action = "turn_on" if onoff == "on" else "turn_off"
        return emit_command("media", action, final_target, onoff, make_slots(device="tv"), phr, 0.86)

    if style == "audio_power":
        dev = random.choice(MEDIA_AUDIO_DEVICES)
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"
        zh_name = "喇叭" if dev == "speaker" else "soundbar"
        phr = random.choice([
            f"{room_word}{zh_name}{'打開' if onoff == 'on' else '關掉'}",
            f"Turn {onoff} the {dev} in the {room_word}",
        ])
        return emit_command("media", action, norm_target, onoff, make_slots(device=dev), phr, 0.82)

    if style == "playback":
        action = random.choice(["pause", "resume", "stop"])
        phr = random.choice(["Pause the music", "繼續播放", "Stop playback", "先暫停一下"])
        return emit_command("media", action, "default", None, make_slots(device="music"), phr, 0.80)

    if style == "volume":
        direction = random.choice(["increase", "decrease"])
        val = random.choice([1, 2, 3, 5, 10])
        phr = random.choice([
            f"Volume {'up' if direction == 'increase' else 'down'} {val}",
            "小聲一點" if direction == "decrease" else "大聲一點",
        ])
        return emit_command("media", direction, "default", None, make_slots(device="volume", value=val, unit="step"), phr, 0.78)

    if style == "source":
        src = random.choice(["HDMI1", "HDMI2", "YouTube", "Netflix"])
        phr = random.choice([f"Switch TV to {src}", f"電視切到{src}"])
        return emit_command("media", "set", "default", None, make_slots(device="tv", mode="source", value=src), phr, 0.78)

    phr = random.choice(["太吵了", "小聲一點", "聽不到耶", "It’s too loud", "I can’t hear it"])
    if ("聽不到" in phr) or ("can’t hear" in phr):
        return emit_command("media", "increase", "default", None, make_slots(device="volume", value=2, unit="step"), phr, 0.62)
    return emit_command("media", "decrease", "default", None, make_slots(device="volume", value=2, unit="step"), phr, 0.62)

def gen_covers() -> Example:
    base_room = pick_room()
    room_word, norm_target = pick_room_word_and_target(base_room)
    
    # Explicitly map text keywords to device types
    # (Device Type, List of keywords to use in text)
    device_map = [
        ("curtain", ["curtain", "窗簾", "布簾"]),
        ("blinds", ["blinds", "百葉窗", "捲簾"])
    ]
    dev_type, keywords = random.choice(device_map)
    dev_word = random.choice(keywords) # Use this specific word in the text
    
    style = random.choice(["openclose", "position", "implicit"])

    if style == "openclose":
        oc = random.choice(["open", "close"])
        phr = random.choice([
            f"{oc.title()} the {room_word} {dev_word}",
            f"把{room_word}{dev_word}{'打開' if oc == 'open' else '拉上'}",
            f"{oc.title()} the {dev_word}"
        ])
        final_target = norm_target if room_word in phr else "default"
        return emit_command("covers", oc, final_target, None, make_slots(device=dev_type), phr, 0.88)

    if style == "position":
        pos = random.choice([10, 25, 50, 75, 90])
        phr = random.choice([
            f"Set the {room_word} {dev_word} to {pos}%", 
            f"{room_word}{dev_word}開{pos}%",
            f"{dev_word}開到{pos}%",
        ])
        final_target = norm_target if room_word in phr else "default"
        return emit_command("covers", "set", final_target, None, make_slots(device=dev_type, mode="position", value=pos, unit="percent"), phr, 0.84)

    # Implicit (defaults to curtain usually)
    phr = random.choice([
        "太亮了把窗簾拉起來", "陽光好大", "Make it darker", "It's too bright by the window"
    ])
    return emit_command("covers", "close", "default", None, make_slots(device="curtain"), phr, 0.66)

def gen_locks() -> Example:
    style = random.choice(["en", "zh", "ambiguous"])
    if style == "en":
        act = random.choice(["lock", "unlock"])
        phr = random.choice(["Lock the front door", "Lock the door"]) if act == "lock" else random.choice(["Unlock the front door", "Unlock the door"])
        return emit_command("locks", act, "default", None, make_slots(device="front_door"), phr, 0.86)

    if style == "zh":
        phr = random.choice(["門鎖上", "把門鎖起來", "解鎖大門", "開門"])
        if ("解鎖" in phr) or (phr == "開門"):
            return emit_command("locks", "unlock", "default", None, make_slots(device="front_door"), phr, 0.78)
        return emit_command("locks", "lock", "default", None, make_slots(device="front_door"), phr, 0.82)

    phr = random.choice(["我回來了", "我出門了，門記得鎖"])
    if "鎖" in phr:
        return emit_command("locks", "lock", "default", None, make_slots(device="front_door"), phr, 0.68)
    return emit_transcript(phr, 0.18)

def gen_vacuum() -> Example:
    base_room = pick_room(weight_default=0.0)
    room_word, norm_target = pick_room_word_and_target(base_room)
    
    # 1. Start/Stop/Pause/Resume Logic
    # Tuple: (Action, Phrase List)
    actions = [
        ("start", ["Start vacuuming", "開始掃地", "掃地機啟動", "Clean the floor"]),
        ("stop", ["Stop the robot vacuum", "停止掃地", "不要掃了", "Stop vacuuming"]),
        ("pause", ["Pause the vacuum", "暫停掃地機", "先暫停一下"]),
        ("resume", ["Resume cleaning", "繼續掃", "繼續工作"]),
        ("set", [f"掃一下{room_word}", f"Clean the {room_word}"]) # Room mode
    ]
    
    act, phrases = random.choice(actions)
    phr = random.choice(phrases)
    
    # Special handling for "room" mode
    if act == "set":
        return emit_command("vacuum", "set", norm_target, None, make_slots(device="robot_vacuum", mode="room", value=norm_target), phr, 0.78)
        
    # Standard handling
    return emit_command("vacuum", act, "default", None, make_slots(device="robot_vacuum"), phr, 0.84)

def gen_timer() -> Example:
    style = random.choice(["set", "cancel", "query"])
    if style == "set":
        minutes = random.choice([1, 3, 5, 10, 15, 30, 45, 60])
        base_room = pick_room()
        room_word, norm_target = pick_room_word_and_target(base_room)
        phr = random.choice([
            f"幫我計時{minutes}分鐘", f"Set a {minutes} minute timer", f"在{room_word}設{minutes}分鐘計時"
        ])
        final_target = norm_target if room_word in phr else "default"
        return emit_command("timer", "set", final_target, None, make_slots(device="timer", value=minutes, unit="min", duration_sec=minutes * 60), phr, 0.90)

    if style == "cancel":
        phr = random.choice(["Cancel the timer", "把計時器取消", "停止計時"])
        return emit_command("timer", "stop", "default", None, make_slots(device="timer", mode="cancel"), phr, 0.86)

    phr = random.choice(["還剩多久？", "timer 還有幾分鐘", "How much time left?"])
    return emit_command("timer", "query", "default", None, make_slots(device="timer", mode="remaining"), phr, 0.76)

def gen_scene() -> Example:
    base_room = pick_room()
    room_word, norm_target = pick_room_word_and_target(base_room)
    scene = random.choice(["movie", "sleep", "away", "relax", "dinner", "work"])
    
    phr_opts = [
        (f"{scene} mode", False),
        (f"切到{scene}模式", False),
        (f"{room_word}開電影模式" if scene == "movie" else f"啟動{scene}模式", scene == "movie"),
        ("Good night", False), ("I'm leaving", False),
        (f"Set {scene} scene", False)
    ]
    phr, uses_room = random.choice(phr_opts)
    if phr == "Good night": scene = "sleep"
    if phr == "I'm leaving": scene = "away"
    
    final_target = norm_target if uses_room else "default"
    return emit_command("scene", "set", final_target, None, make_slots(device="scene", scene=scene), phr, 0.78)

def gen_query() -> Example:
    base_room = pick_room()
    room_word, norm_target = pick_room_word_and_target(base_room)
    qtype = random.choice(["light_state", "temp", "lock_state", "vacuum_state", "timer_remaining"])

    if qtype == "light_state":
        phr = random.choice([f"{room_word}燈有開嗎", f"Is the {room_word} light on?"])
        return emit_command("query", "query", norm_target, None, make_slots(device="light", mode="state"), phr, 0.86)

    if qtype == "temp":
        phr = random.choice([f"{room_word}現在幾度？", f"What's the temperature in the {room_word}?"])
        return emit_command("query", "query", norm_target, None, make_slots(device="temperature", mode="current", unit="c"), phr, 0.86)

    if qtype == "lock_state":
        phr = random.choice(["門有鎖嗎", "Is the front door locked?"])
        return emit_command("query", "query", "default", None, make_slots(device="door_lock", mode="state"), phr, 0.80)

    if qtype == "timer_remaining":
        phr = random.choice(["計時器還剩多久", "Timer remaining?", "How much time left on the timer?"])
        return emit_command("query", "query", "default", None, make_slots(device="timer", mode="remaining"), phr, 0.76)

    phr = random.choice(["掃地機在工作嗎", "Is the vacuum running?"])
    return emit_command("query", "query", "default", None, make_slots(device="robot_vacuum", mode="state"), phr, 0.78)

def gen_transcript() -> Example:
    texts = [
        # Chat
        "Hello there", "今天天氣好冷", "我晚點再說", "你覺得怎麼樣", "哈哈哈",
        "turn on the light... uh actually never mind", "我剛剛說到哪",
        "我想開心一點", "Turn on your charm",
        # Shopping / Ordering (CRITICAL NEGATIVES)
        "幫我訂披薩", "Order a pizza", "I want to buy a new vacuum",
        "我想買一台掃地機", "Buy me a new TV", "幫我網購一台冷氣",
        # Maintenance
        "電視壞掉了怎麼辦", "冷氣好像有點怪怪的", "門鎖是不是該換了",
        "窗簾好漂亮", "掃地機卡住了", "The vacuum is stuck"
    ]
    t = random.choice(texts)
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
    for _ in range(n):
        domain = random.choices(names, probs, k=1)[0]
        out.append(name_to_fn[domain]())
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