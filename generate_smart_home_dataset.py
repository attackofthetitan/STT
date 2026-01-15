import json
import random
import argparse
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
import hashlib

random.seed(42)

ROOMS = [
    "bathroom", "kitchen", "bedroom", "living_room", 
    "dining_room", "study", "balcony", "hallway", "entryway", 
    "garage", "basement", "attic", "laundry_room", "closet",
    "guest_room", "nursery", "default"
]

ROOM_ALIASES_ZH = {
    "bathroom": ["廁所", "浴室", "洗手間", "茅房", "洗澡的地方", "盥洗室", "洗手台", "衛浴間", "如廁處", "化妝間"],
    "kitchen": ["廚房", "灶咖", "煮飯的地方", "烹飪區", "料理台", "廚櫃", "煮食間", "烹調處"],
    "bedroom": ["房間", "臥室", "主臥", "睡覺的地方", "寢室", "主臥室", "睡房", "臥房", "睡眠區"],
    "living_room": ["客廳", "起居室", "休憩區", "沙發區", "會客室", "休息廳", "交誼廳"], 
    "dining_room": ["餐廳", "飯廳", "吃飯的地方", "用餐區", "飯桌", "餐桌區"],
    "study": ["書房", "辦公室", "工作區", "電腦房", "讀書的地方", "工作間", "閱覽室", "研習室"],
    "balcony": ["陽台", "露台", "前陽台", "後陽台", "觀景台", "曬衣台"],
    "hallway": ["走廊", "過道", "走道", "長廊", "通廊", "廊道", "通道"],
    "entryway": ["玄關", "門口", "大門口", "入口", "進門處", "前廳", "門廳"],
    "garage": ["車庫", "停車場", "車房", "泊車處"],
    "basement": ["地下室", "地窖", "儲藏室", "地庫"],
    "attic": ["閣樓", "頂樓", "天台", "樓頂"],
    "laundry_room": ["洗衣間", "曬衣間", "洗衣房", "洗滌室"],
    "closet": ["衣櫃間", "儲物間", "衣帽間", "收納室"],
    "guest_room": ["客房", "訪客房", "賓客室", "招待室"],
    "nursery": ["嬰兒房", "育嬰室", "兒童房", "寶寶房"],
    "default": ["家裡", "全部", "所有地方", "整個房子", "室內", "全屋", "整間", "到處", "各處"],
}

ROOM_ALIASES_EN = {
    "bathroom": ["bathroom", "restroom", "bath", "loo", "powder room", "toilet", "lavatory", "WC", "john"],
    "kitchen": ["kitchen", "cooking area", "scullery", "cookhouse", "kitchenette", "galley", "cook room"],
    "bedroom": ["bedroom", "master bedroom", "sleeping quarters", "bed chamber", "sleeping room", "master suite", "bunk room", "chamber"],
    "living_room": ["living room", "lounge", "family room", "sitting room", "parlor", "drawing room", "common room", "den"],
    "dining_room": ["dining room", "dining area", "dinette", "eating area", "dining space"],
    "study": ["study", "office", "workspace", "home office", "desk area", "work room", "library"], 
    "balcony": ["balcony", "terrace", "patio", "deck", "porch"],
    "hallway": ["hallway", "corridor", "hall", "passage", "passageway", "gallery", "walkway"],
    "entryway": ["entryway", "foyer", "entrance", "front door area", "lobby", "mudroom"],
    "garage": ["garage", "car port", "parking area", "vehicle bay"],
    "basement": ["basement", "cellar", "downstairs", "lower level", "sub level"],
    "attic": ["attic", "loft", "upper level", "roof space", "garret"],
    "laundry_room": ["laundry room", "utility room", "laundry area"],
    "closet": ["closet", "wardrobe", "storage room", "walk-in"],
    "guest_room": ["guest room", "spare room", "visitor room", "guest bedroom"],
    "nursery": ["nursery", "baby room", "kids room", "children's room"],
    "default": ["the house", "everywhere", "the whole place", "all rooms", "the entire home", "the whole house", "indoors", "all areas", "throughout"],
}

PREFIXES_EN = ["Could you", "Please", "Can you", "Hey,", "I need you to", "Would you mind to", "Just", "Quickly", "Go ahead and", "Time to", "Help me", "Kindly", "Yo", "Do me a favor and", "I want you to", "Make sure to", "Remember to", "Don't forget to"]
PREFIXES_ZH = ["麻煩", "請", "幫我", "可以幫我", "那個", "欸", "快速", "我想", "這時候", "去", "幫忙", "順便", "勞駕", "那個誰", "記得", "要", "趕快", "現在"]

SUFFIXES_EN = ["please", "thanks", "thank you", "now", "right now", "ASAP", "quickly", "immediately", "ok", "okay", "alright", "yeah"]
SUFFIXES_ZH = ["謝謝", "拜託", "快點", "馬上", "現在", "立刻", "好嗎", "可以嗎", "喔", "啦", "耶", "吧"]

TIME_EXPRESSIONS_EN = ["in a minute", "in 5 minutes", "later", "soon", "in a bit", "after dinner", "before bed", "in the morning", "tonight"]
TIME_EXPRESSIONS_ZH = ["等一下", "五分鐘後", "待會", "稍後", "晚點", "吃飯後", "睡前", "早上", "今晚", "現在"]

INTENSITY_EN = ["very", "really", "super", "a bit", "slightly", "completely", "totally", "fully", "partially", "somewhat"]
INTENSITY_ZH = ["很", "非常", "超級", "有點", "稍微", "完全", "全部", "整個", "部分", "稍稍"]

DEVICE_VARIANTS_EN = {
    "light": ["light", "lights", "lamp", "lamps", "lighting", "LEDs", "strip lights", "ceiling light", "bulbs", "illumination", "spotlight", "chandelier", "sconce", "lantern", "fixture", "overhead light", "downlight", "uplight"],
    "ac": ["AC", "air conditioner", "A/C", "cooling unit", "air con", "thermostat", "climate control", "HVAC", "cooler", "air conditioning", "temperature control", "climate system"],
    "tv": ["TV", "television", "telly", "screen", "display", "monitor", "smart TV", "tube", "LCD", "OLED", "plasma", "flatscreen"],
    "vacuum": ["vacuum", "robot vacuum", "roomba", "sweeper", "bot", "cleaner", "mopping robot", "hoover", "dust bot", "cleaning robot", "vac"],
    "curtain": ["curtain", "drapes", "shades", "blinds", "shutters", "blackout curtains", "screens", "roller shades", "venetian blinds", "window covering"],
    "fan": ["fan", "ceiling fan", "standing fan", "ventilator", "air circulator", "exhaust fan", "desk fan"],
    "speaker": ["speaker", "stereo", "sound system", "audio", "music player", "smart speaker", "bluetooth speaker"],
}

DEVICE_VARIANTS_ZH = {
    "light": ["燈", "電燈", "照明", "光", "檯燈", "吊燈", "吸頂燈", "落地燈", "壁燈", "LED燈", "嵌燈", "燈泡", "日光燈", "夜燈", "探照燈", "筒燈", "射燈", "燈光"],
    "ac": ["冷氣", "空調", "冷氣機", "恆溫器", "冷風機", "空調系統", "調溫器"], 
    "tv": ["電視", "電視機", "螢幕", "顯示器", "液晶螢幕", "智慧電視", "平板電視"],
    "vacuum": ["掃地機", "吸塵器", "機器人", "掃地機器人", "拖地機", "掃拖機", "打掃機器人", "清潔機器人"],
    "curtain": ["窗簾", "布簾", "百葉窗", "捲簾", "遮光簾", "紗簾", "羅馬簾", "遮陽簾"],
    "fan": ["風扇", "電風扇", "吊扇", "循環扇", "立扇", "桌扇", "排風扇"],
    "speaker": ["喇叭", "音響", "揚聲器", "音箱", "播放器", "智慧音箱"],
}

FILLERS_EN = ["uh", "um", "like", "you know", "actually", "er", "ah", "maybe", "please", "hmm", "well", "okay", "so", "basically", "I mean", "sort of", "kind of", "really", "just", "now", "hey", "alright"]
FILLERS_ZH = ["那個", "呃", "嗯", "就是", "那個...應該", "阿", "好像是", "麻煩", "欸", "我想", "然後", "喔", "那個什麼", "呃...", "對了", "就", "啊", "唉", "嘿", "好", "這個"]

# Noise dictionaries (Homophones)
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

def to_zh_count(n: int) -> str:
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
    if random.random() < weight_default:
        return "default"
    return random.choice([r for r in ROOMS if r != "default"])

def pick_room_word_and_target(base_target: str) -> Tuple[str, str, str]:
    if base_target == "default":
        if random.random() < 0.5:
            return random.choice(ROOM_ALIASES_ZH["default"]), "default", "zh"
        return random.choice(ROOM_ALIASES_EN["default"]), "default", "en"

    if base_target in ["bedroom", "study", "guest_room", "nursery"] and random.random() < 0.35:
        lang = "zh" if random.random() < 0.5 else "en"
        
        if base_target == "nursery":
            if lang == "zh":
                name = random.choice(["寶寶", "小寶", "弟弟", "妹妹", "兒童", "小孩"])
                suffix = random.choice(["房間", "房"])
            else:
                name = random.choice(["Baby", "Junior", "Tommy", "Kids", "Child's"]) 
                suffix = random.choice(["room", "bedroom"])
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
        else: 
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
    variants = DEVICE_VARIANTS_ZH if lang == "zh" else DEVICE_VARIANTS_EN
    adjectives = INTENSITY_ZH if lang == "zh" else INTENSITY_EN 
    
    base = random.choice(variants.get(dev_type, [dev_type]))
    
    if random.random() < 0.15:
        return f"smart {base}" if lang == "en" else f"智慧{base}"
    
    return base

def inject_asr_noise(text: str, lang: str, prob: float = 0.0) -> str:
    if random.random() > prob: return text

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
    if random.random() > 0.15: return text
    
    if lang == "zh":
        if random.random() < 0.5:
            time_expr = random.choice(TIME_EXPRESSIONS_ZH)
            return f"{time_expr}{text}" if random.random() < 0.5 else f"{text}{time_expr}"
    else:
        if random.random() < 0.5:
            time_expr = random.choice(TIME_EXPRESSIONS_EN)
            return f"{text} {time_expr}" if random.random() < 0.5 else f"{time_expr}, {text}"
    
    return text

def humanize_text(text: str, lang: str, noise_prob: float = 0.0, force_variation: bool = False) -> str:
    text = inject_asr_noise(text, lang, prob=noise_prob)
    
    if not force_variation and random.random() > 0.85: 
        return text

    words = text.split()
    if not words: return text
    
    fillers = FILLERS_ZH if lang == "zh" else FILLERS_EN
    prefixes = PREFIXES_ZH if lang == "zh" else PREFIXES_EN
    suffixes = SUFFIXES_ZH if lang == "zh" else SUFFIXES_EN
    
    ops = []
    
    if random.random() < 0.20 or force_variation:
        ops.append("prefix")
    
    if random.random() < 0.15:
        ops.append("suffix")
    
    for op in ops:
        if op == "prefix":
            words.insert(0, random.choice(prefixes))
        elif op == "suffix":
            words.append(random.choice(suffixes))

    result = " ".join(words)
    result = add_contextual_elements(result, lang)
    
    return result

def make_slots(**kwargs) -> Dict[str, Any]:
    return {
        "device": kwargs.get("device"),
        "value": str(kwargs.get("value")) if kwargs.get("value") is not None else None,
        "value_num": float(kwargs.get("value")) if isinstance(kwargs.get("value"), (int, float)) else None,
        "unit": kwargs.get("unit"),
        "mode": kwargs.get("mode"),
        "scene": kwargs.get("scene"),
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
    conf = max(0.0, min(1.0, base_conf + random.uniform(-0.12, 0.06)))
    return Example("command", domain, action, target, state, slots, text, round(conf, 2))

def emit_transcript(domain, action, target, state, slots, text, base_conf=0.88) -> Example:
    conf = max(0.0, min(1.0, base_conf + random.uniform(-0.12, 0.06)))
    return Example("transcript", domain, action, target, state, slots, text, round(conf, 2))

def gen_lights() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    
    explicit_device = (random.random() < 0.55)
    dev_word = get_granular_device("light", lang) if explicit_device else ("它" if lang == "zh" else "it")

    if random.random() < 0.25:
        situation = random.choice(["dark", "bright"])
        if situation == "dark":
            onoff = "on"
            action = "turn_on"
            phrases = (
                ["這裡太暗了", "我看不到路", "黑漆漆的", "有點暗", "甚麼都看不到", f"{room_word}太暗了", "開燈", "弄亮一點", "幫我照明"]
                if lang == "zh"
                else ["it's too dark in here", "I can't see anything", "it is pitch black", "it's a bit dim", f"the {room_word} is too dark", "lights please", "illuminate"]
            )
        else:
            onoff = "off"
            action = "turn_off"
            phrases = (
                ["這裡太亮了", "好刺眼", "太亮了", "閃到眼睛", f"{room_word}亮到不行", "關燈", "弄暗一點"]
                if lang == "zh"
                else ["it's too bright", "it's blinding", "turn it down", "too bright in here", f"the {room_word} is too bright", "kill the lights", "dim the room"]
            )

        phr = humanize_text(random.choice(phrases), lang)
        final_target = norm_target if room_word in phr else "default"
        slots = make_slots(device="light")
        return emit_command("lights", action, final_target, onoff, slots, phr, 0.92)

    # Standard Commands
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"
    slots = make_slots(device="light")

    if lang == "zh":
        verb = random.choice(["打開", "開", "啟動"]) if onoff == "on" else random.choice(["關掉", "關", "閉上", "切掉"])
        if explicit_device:
            structures = [
                f"{verb}{room_word}{dev_word}", f"把{dev_word}{verb}", 
                f"{room_word}{dev_word}幫我{verb}", f"去{verb}{room_word}{dev_word}"
            ]
        else:
            structures = [f"{verb}{room_word}", f"{verb}它", "燈光控制", f"幫我{verb}"]
    else:
        verb = random.choice(["turn on", "switch on", "activate"]) if onoff == "on" else random.choice(["turn off", "switch off", "deactivate", "kill"])
        if explicit_device:
            structures = [
                f"{verb} the {room_word} {dev_word}", f"{verb} the {dev_word}",
                f"{dev_word} {onoff}", f"set {dev_word} to {onoff}"
            ]
        else:
            structures = [f"{verb} the {room_word}", f"{verb} it", f"lights {onoff}", "hit the lights"]

    st = random.choice(structures)
    phr = humanize_text(st, lang)
    final_target = norm_target if room_word in phr else "default"
    return emit_command("lights", action, final_target, onoff, slots, phr, 0.95)


def gen_climate() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)

    explicit_device = (random.random() < 0.40)
    dev_word = get_granular_device("ac", lang) if explicit_device else ""

    mode = random.choice(["set_temp", "adjust", "onoff"])

    if mode == "set_temp":
        temp = random.randint(16, 30)
        slots = make_slots(value=temp, unit="celsius", mode="absolute", device="thermostat")
        
        if lang == "zh":
            t_str = str(temp)
            if explicit_device:
                st = random.choice([
                    f"{room_word}{dev_word}設定{t_str}度", f"把{dev_word}調到{t_str}度", f"{dev_word}{t_str}度"
                ])
            else:
                st = random.choice([
                    f"把{room_word}溫度設為{t_str}度", f"溫度{t_str}度", f"氣溫控制在{t_str}"
                ])
        else:
            if explicit_device:
                st = random.choice([
                    f"set the {room_word} {dev_word} to {temp} degrees", f"{dev_word} to {temp}", f"make the {dev_word} {temp}"
                ])
            else:
                st = random.choice([
                    f"set the temperature in {room_word} to {temp}", f"temp to {temp}", f"make it {temp} degrees"
                ])

        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in phr else "default"
        return emit_command("climate", "set_temperature", final_target, None, slots, phr, 0.95)

    if mode == "onoff":
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"
        slots = make_slots(device="thermostat")
        
        if lang == "zh":
            verb = random.choice(["打開", "啟動"]) if onoff == "on" else random.choice(["關掉", "停止"])
            st = f"{verb}{room_word}{get_granular_device('ac', 'zh')}"
        else:
            verb = random.choice(["turn on", "start"]) if onoff == "on" else random.choice(["turn off", "stop"])
            st = f"{verb} the {room_word} {get_granular_device('ac', 'en')}"

        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in phr else "default"
        return emit_command("climate", action, final_target, onoff, slots, phr, 0.95)
        
    # Adjust / Implicit Climate
    delta = random.choice([-1, 1, -2, 2])
    slots = make_slots(value=abs(delta), unit="celsius", mode="relative", device="thermostat")
    
    if lang == "zh":
        if delta > 0:
            st = random.choice([f"{room_word}溫度調高一點", "我覺得好冷", "暖氣開強一點", "升溫"])
        else:
            st = random.choice([f"{room_word}溫度調低一點", "我覺得好熱", "冷氣強一點", "降溫", "太熱了"])
    else:
        if delta > 0:
            st = random.choice([f"raise the temp in {room_word}", "I'm freezing", "warm it up", "it's too cold", "increase heat"])
        else:
            st = random.choice([f"lower the temp in {room_word}", "I'm boiling", "cool it down", "it's too hot", "more AC"])
    
    phr = humanize_text(st, lang)
    final_target = norm_target if room_word in phr else "default"
    return emit_command("climate", "adjust_temperature", final_target, None, slots, phr, 0.95)

def gen_vacuum() -> Example:
    base_room = pick_room(weight_default=0.0) 
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("vacuum", lang)
    
    if random.random() < 0.6:
        if lang == "zh":
            st = random.choice([
                f"{dev_word}去打掃{room_word}", f"{room_word}髒了", f"清理{room_word}", f"{dev_word}掃一下{room_word}"
            ])
        else:
            st = random.choice([
                f"{dev_word} clean the {room_word}", f"vacuum the {room_word}", f"clean up the {room_word}", f"the {room_word} is dirty"
            ])
        
        phr = humanize_text(st, lang)
        if room_word in phr:
            target = norm_target
            slots = make_slots(mode="room", value=norm_target, device="robot_vacuum")
        else:
            target = "default"
            slots = make_slots(mode="room", value=None, device="robot_vacuum")
            
        return emit_command("vacuum", "start", target, None, slots, phr, 0.90)

    slots = make_slots(device="robot_vacuum")
    if lang == "zh":
        st = random.choice([f"{dev_word}回家充電", "掃地機回去", "停止打掃", "回基座"])
    else:
        st = random.choice([f"{dev_word} return to base", "dock the vacuum", "go home", "stop cleaning"])
    
    phr = humanize_text(st, lang)
    return emit_command("vacuum", "dock", "default", None, slots, phr, 0.95)

def gen_curtain() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("curtain", lang)
    
    action = random.choice(["open", "close"])
    slots = make_slots(device="curtain")

    if lang == "zh":
        verb = random.choice(["打開", "拉開"]) if action == "open" else random.choice(["關上", "拉上", "閉合"])
        st = random.choice([f"{verb}{room_word}{dev_word}", f"把{dev_word}{verb}"])
    else:
        verb = random.choice(["open", "raise"]) if action == "open" else random.choice(["close", "shut", "lower"])
        st = random.choice([f"{verb} the {room_word} {dev_word}", f"{verb} the {dev_word}"])

    phr = humanize_text(st, lang)
    final_target = norm_target if room_word in phr else "default"
    return emit_command("curtain", action, final_target, action, slots, phr, 0.95)

def gen_fan() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("fan", lang)

    onoff = random.choice(["on", "off"])
    slots = make_slots(device="fan")
    
    if lang == "zh":
        if onoff == "on":
            st = random.choice([f"打開{room_word}{dev_word}", "通風一下", "空氣不流通", "開風扇"])
        else:
            st = random.choice([f"關掉{room_word}{dev_word}", "停止通風", "關風扇"])
    else:
        if onoff == "on":
            st = random.choice([f"turn on the {room_word} {dev_word}", "get some air moving", "it's stuffy", "start the fan"])
        else:
            st = random.choice([f"turn off the {room_word} {dev_word}", "stop the fan", "kill the fan"])

    phr = humanize_text(st, lang)
    final_target = norm_target if room_word in phr else "default"
    return emit_command("fan", "turn_on" if onoff == "on" else "turn_off", final_target, onoff, slots, phr, 0.95)

def gen_media() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)

    media_type = random.choice(["tv", "speaker"])
    dev_word = get_granular_device(media_type, lang)

    action_type = random.choice(["onoff", "volume", "next", "channel"])
    
    if action_type == "channel":
        media_type = "tv"
        dev_word = get_granular_device("tv", lang)
        ch = random.randint(1, 50)
        slots = make_slots(device="tv", value=ch, mode="channel")
        if lang == "zh":
            st = random.choice([f"{room_word}{dev_word}轉到{ch}台", f"切換到{ch}頻道", f"選{ch}台"])
        else:
            st = random.choice([f"change {room_word} {dev_word} to channel {ch}", f"channel {ch} please", f"put on channel {ch}"])
        
        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in phr else "default"
        return emit_command("media", "channel_change", final_target, None, slots, phr, 0.95)

    if action_type == "volume":
        slots = make_slots(device=media_type, mode="volume")
        if lang == "zh":
            st = random.choice([f"把{dev_word}聲音調大", "大聲一點", "聽不到", "音量調高"])
        else:
            st = random.choice([f"turn up the volume on the {dev_word}", "make it louder", "I can't hear it", "volume up"])
            
        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in phr else "default"
        return emit_command("media", "set_volume", final_target, None, slots, phr, 0.92)

    if action_type == "onoff":
        onoff = random.choice(["on", "off"])
        slots = make_slots(device=media_type)
        if lang == "zh":
            verb = random.choice(["打開", "開啟"]) if onoff == "on" else random.choice(["關掉", "關閉"])
            st = f"{verb}{room_word}{dev_word}"
        else:
            verb = random.choice(["turn on", "power up"]) if onoff == "on" else random.choice(["turn off", "shut down"])
            st = f"{verb} the {room_word} {dev_word}"
            
        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in phr else "default"
        return emit_command("media", "turn_on" if onoff == "on" else "turn_off", final_target, onoff, slots, phr, 0.95)

    slots = make_slots(device=media_type)
    if lang == "zh":
        st = random.choice([f"{dev_word}下一首", "切歌", "這首不喜歡"])
    else:
        st = random.choice([f"{dev_word} next track", "skip this song", "next song"])
    phr = humanize_text(st, lang)
    return emit_command("media", "next", "default", None, slots, phr, 0.95)

def gen_timer() -> Example:
    lang = "zh" if random.random() < 0.5 else "en"
    val = random.choice([5, 10, 15, 30])
    unit = "minutes"
    slots = make_slots(device="timer", value=val, unit=unit)

    if lang == "zh":
        st = random.choice([f"設定{val}分鐘計時器", f"{val}分鐘後叫我", f"提醒我{val}分鐘"])
    else:
        st = random.choice([f"set a {val} minute timer", f"remind me in {val} minutes", f"timer for {val} mins"])
    
    phr = humanize_text(st, lang)
    return emit_command("timer", "set_time", "default", None, slots, phr, 0.95)

TRANSCRIPT_CATEGORIES = {
    "news": {
        "en": [
            "Breaking news tonight", "The weather forecast for tomorrow is sunny", 
            "Stock markets closed higher today", "In sports news", "Traffic is heavy on the I-5",
            "The president announced a new policy", "Scientists discovered a new planet"
        ],
        "zh": [
            "晚間新聞報導", "明天天氣預報", "股市今日收盤上漲", "體育新聞方面",
            "高速公路目前塞車", "總統宣布了一項新政策", "科學家發現了新行星"
        ]
    },
    "conversation": {
        "en": [
            "Hey, did you see that movie?", "I'm going to the store later", "What do you want for dinner?",
            "I love this song", "That's a great idea", "No, I don't think so", "Happy birthday!",
            "Can you pass the salt?", "I'll be right back", "See you tomorrow"
        ],
        "zh": [
            "欸，你看過那部電影嗎？", "我晚點要去商店", "晚餐想吃什麼？", "我好愛這首歌",
            "真是個好主意", "我不這麼認為", "生日快樂！", "幫我拿一下鹽巴好嗎？",
            "我馬上回來", "明天見"
        ]
    },
    "questions_to_humans": {
        "en": [
            "Mom, where are my socks?", "Dad, can you help me?", "Honey, have you seen my keys?",
            "Who is calling?", "Why is the sky blue?", "When is dinner ready?"
        ],
        "zh": [
            "媽，我的襪子在哪？", "爸，可以幫我嗎？", "親愛的，有看到我的鑰匙嗎？",
            "誰打來的？", "為什麼天是藍的？", "晚餐什麼時候好？"
        ]
    },
    "broken_commands": {
        "en": [
            "Alexa, turn... actually nevermind", "Hey Google, set a... wait", "Turn on the... uh... forgot",
            "Computer, play... no stop", "Lights... actually it's fine"
        ],
        "zh": [
            "幫我開... 算了", "設定一個... 等等", "打開... 呃... 忘了",
            "播放... 不用了", "燈光... 其實不用"
        ]
    },
    "phone_calls": {
        "en": [
            "Yeah I'm on my way", "Okay bye", "I'll call you back later", "No I can't talk right now",
            "Hello? Can you hear me?"
        ],
        "zh": [
            "對，我在路上了", "好，拜拜", "我晚點回撥給你", "現在不方便講話", "喂？聽得到嗎？"
        ]
    }
}

def gen_transcript() -> Example:
    lang = "zh" if random.random() < 0.5 else "en"
    
    category = random.choice(list(TRANSCRIPT_CATEGORIES.keys()))
    text = random.choice(TRANSCRIPT_CATEGORIES[category][lang])
    
    phr = humanize_text(text, lang, noise_prob=0.0)
    
    return emit_transcript("unknown", "none", None, None, make_slots(), phr, 0.15)


def compute_text_hash(text: str) -> str:
    normalized = " ".join(text.strip().lower().split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()

def mutate_example(ex: Example, attempts: int) -> Example:
    lang = "zh" if any(ord(c) > 128 for c in ex.raw_text) else "en"
    ex.raw_text = humanize_text(ex.raw_text, lang, noise_prob=0.0, force_variation=True)
    return ex

GENERATORS = [
    (gen_lights, 0.10),
    (gen_climate, 0.10),
    (gen_vacuum, 0.10),
    (gen_timer, 0.10),
    (gen_curtain, 0.10),
    (gen_fan, 0.10),
    (gen_media, 0.10),
    (gen_transcript, 0.30), 
]

def generate(n: int, max_attempts: int = 15) -> List[Example]:
    out = []
    seen_hashes = set()
    failed_attempts = 0
    
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
            continue
        
        seen_hashes.add(text_hash)
        out.append(ex)
        
        if len(out) % 5000 == 0:
            print(f"Generated {len(out)}/{n} unique examples...")

    return out

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="smart_home_mega.jsonl")
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
    
    print(f"Done! Saved to {args.out}")

if __name__ == "__main__":
    main()