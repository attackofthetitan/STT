import json
import random
import argparse
from dataclasses import dataclass, asdict
from turtle import st
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
    "living_room": ["living room", "lounge", "family room", "sitting room", "parlor", "drawing room", "front room", "common room"],
    "dining_room": ["dining room", "dining area", "dinette", "eating area", "breakfast nook", "dining space"],
    "study": ["study", "office", "workspace", "home office", "desk area", "work room", "library", "den"], 
    "balcony": ["balcony", "terrace", "patio", "deck", "veranda", "lanai"],
    "hallway": ["hallway", "corridor", "hall", "passage", "passageway", "gallery", "walkway"],
    "entryway": ["entryway", "foyer", "entrance", "front door area", "lobby", "mudroom", "vestibule", "porch"],
    "garage": ["garage", "car port", "parking area", "vehicle bay"],
    "basement": ["basement", "cellar", "downstairs", "lower level", "sub level"],
    "attic": ["attic", "loft", "upper level", "roof space", "garret"],
    "laundry_room": ["laundry room", "utility room", "laundry area"],
    "closet": ["closet", "wardrobe", "storage room", "walk-in"],
    "guest_room": ["guest room", "spare room", "visitor room", "guest bedroom"],
    "nursery": ["nursery", "baby room", "kids room", "children's room"],
    "default": ["the house", "everywhere", "the whole place", "all rooms", "the entire home", "the whole house", "indoors", "all areas", "throughout"],
}

PERSON_NAMES_ZH = ["爸爸", "媽媽", "哥哥", "妹妹", "阿嬤", "爺爺", "小寶", "老王", "老婆", "老公", "弟弟", "姊姊", "寶貝", "親愛的", "小明", "小華", "阿姨", "叔叔", "奶奶", "外公", "外婆", "兒子", "女兒"]
PERSON_NAMES_EN = ["Mom", "Dad", "Alice", "Bob", "Grandma", "Grandpa", "Tommy", "Baby", "Honey", "Sweetie", "Sis", "Bro", "Junior", "Sarah", "Mike", "Emma", "Jack", "Lily", "Max", "Sophie"]

ADJECTIVES_ZH = ["主", "大", "小", "天花板", "地板", "智慧", "舊", "新", "紅色", "藍色", "黃色", "那個", "旁邊的", "上面的", "前面", "後面", "左邊", "右邊", "中間", "角落", "明亮", "昏暗", "暖色", "冷色", "牆壁"]
ADJECTIVES_EN = ["main", "big", "small", "ceiling", "floor", "smart", "old", "new", "red", "blue", "yellow", "overhead", "corner", "fancy", "front", "back", "left", "right", "center", "bright", "dim", "warm", "cool", "wall", "mounted", "standing"]

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

PREFIXES_EN = ["Could you", "Please", "Can you", "Hey,", "I need you to", "Would you mind to", "Just", "Quickly", "Go ahead and", "Time to", "Help me", "Kindly", "Yo", "Do me a favor and", "I want you to", "Make sure to", "Remember to", "Don't forget to"]
PREFIXES_ZH = ["麻煩", "請", "幫我", "可以幫我", "那個", "欸", "快速", "我想", "這時候", "去", "幫忙", "順便", "勞駕", "那個誰", "記得", "要", "趕快", "現在"]

SUFFIXES_EN = ["please", "thanks", "thank you", "now", "right now", "ASAP", "quickly", "immediately", "ok", "okay", "alright", "yeah"]
SUFFIXES_ZH = ["謝謝", "拜託", "快點", "馬上", "現在", "立刻", "好嗎", "可以嗎", "喔", "啦", "耶", "吧"]

TIME_EXPRESSIONS_EN = ["in a minute", "in 5 minutes", "later", "soon", "in a bit", "after dinner", "before bed", "in the morning", "tonight"]
TIME_EXPRESSIONS_ZH = ["等一下", "五分鐘後", "待會", "稍後", "晚點", "吃飯後", "睡前", "早上", "今晚", "現在"]

INTENSITY_EN = ["very", "really", "super", "a bit", "slightly", "completely", "totally", "fully", "partially", "somewhat"]
INTENSITY_ZH = ["很", "非常", "超級", "有點", "稍微", "完全", "全部", "整個", "部分", "稍稍"]

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
    
    if not force_variation and random.random() > 0.65:
        return text

    words = text.split()
    if not words: return text
    
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
    dev_word = get_granular_device("light", lang)
    
    is_implicit_device_word = False

    if random.random() < 0.50:
        dev_word = "它" if lang == "zh" else "it"
        is_implicit_device_word = True

    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"

    strong_verbs_zh = ["亮起來", "點亮", "弄亮", "照亮", "熄滅", "滅掉", "弄暗", "滅燈"]
    strong_verbs_en = ["illuminate", "brighten", "dim", "extinguish", "light up"]

    if lang == "zh":
        verbs_on = ["打開", "開", "開一下", "開啟", "啟動"] + ["亮起來", "點亮", "點開", "弄亮", "開燈", "讓...亮", "照亮"]
        verbs_off = ["關掉", "關", "關一下", "關閉", "停掉"] + ["熄滅", "滅掉", "暗掉", "關燈", "弄暗", "滅燈"]
        verb = random.choice(verbs_on if onoff == "on" else verbs_off)
        
        prefix = random.choice(PREFIXES_ZH) if random.random() < 0.35 else ""
        intensity = random.choice(INTENSITY_ZH) if random.random() < 0.1 else ""
        
        structures = [
            f"{prefix}{verb}{room_word}{dev_word}",
            f"{prefix}{room_word}{dev_word}{verb}",
            f"把{room_word}{dev_word}{verb}",
            f"{room_word}{dev_word}幫我{verb}",
            f"{verb}{room_word}的{dev_word}",
            f"{room_word}裡面的{dev_word}{verb}",
            f"請{verb}{room_word}{dev_word}",
            f"我要{verb}{room_word}{dev_word}",
            f"{intensity}{verb}{dev_word}",
            f"{room_word}需要{verb}{dev_word}",
            f"可以{verb}{room_word}{dev_word}嗎",
            f"{verb}一下{room_word}{dev_word}",
            f"把{dev_word}{verb}",
            f"想要{room_word}{dev_word}{verb}",
            f"{room_word}{dev_word}要{verb}了",
            f"幫忙{verb}{room_word}裡的{dev_word}",
            f"{verb}{room_word}裡所有的{dev_word}",
            f"把{room_word}所有{dev_word}都{verb}",
            f"{room_word}的{dev_word}可以{verb}嗎",
            f"麻煩{verb}{room_word}{dev_word}好嗎",
        ]
    else:
        verbs_on = ["turn on", "switch on", "activate", "power on", "hit", "enable", "fire up", "bring up"] + ["light up", "flip on", "illuminate", "brighten"]
        verbs_off = ["turn off", "switch off", "kill", "cut", "shut off", "disable", "power down", "shut down"] + ["extinguish", "flip off", "dim"]
        verb = random.choice(verbs_on if onoff == "on" else verbs_off)
        
        prefix = random.choice(PREFIXES_EN) if random.random() < 0.35 else ""
        intensity = random.choice(INTENSITY_EN) if random.random() < 0.1 else ""
        
        structures = [
            f"{prefix} {verb} the {room_word} {dev_word}",
            f"{prefix} {verb} the {dev_word} in the {room_word}",
            f"{room_word} {dev_word} {verb}",
            f"{prefix} make the {room_word} {dev_word} {onoff}",
            f"{verb} {dev_word} {room_word}",
            f"can I have the {room_word} {dev_word} {onoff}",
            f"{room_word} {dev_word} needs to be {onoff}",
            f"I want the {room_word} {dev_word} {onoff}",
            f"{intensity} {verb} the {dev_word}",
            f"let's {verb} the {room_word} {dev_word}",
            f"could you {verb} {room_word} {dev_word}",
            f"{verb} all {dev_word}s in {room_word}",
            f"make sure {room_word} {dev_word} is {onoff}",
            f"{room_word} {dev_word} should be {onoff}",
            f"I need {room_word} {dev_word} {onoff}",
            f"flip the {room_word} {dev_word} {onoff}",
            f"{verb} every {dev_word} in {room_word}",
            f"get the {room_word} {dev_word} {onoff}",
            f"{prefix} {onoff} {room_word} {dev_word}",
            f"we need {room_word} {dev_word} {onoff}",
        ]
    
    st = random.choice(structures)
    phr = humanize_text(st.strip(), lang)
    final_target = norm_target if room_word in st else "default"
    
    slots = make_slots(device="light")
    
    has_strong_verb = (verb in strong_verbs_zh) if lang == "zh" else (verb in strong_verbs_en)

    if "燈" in phr or "light" in phr.lower() or "lamp" in phr.lower():
        slots["device"] = "light"
    elif has_strong_verb:
        slots["device"] = "light" 
    elif is_implicit_device_word:
        slots["device"] = None
    
    return emit_command("lights", action, final_target, onoff, slots, phr, 0.92)

def gen_climate() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("ac", lang)

    mode = random.choice(["set_temp", "set_temp", "onoff", "adjust"])

    is_implicit_device_word = False
    if mode in ["set_temp", "adjust"] and random.random() < 0.35:
        dev_word = "它" if lang == "zh" else "it"
        is_implicit_device_word = True
    
    slots = make_slots(device="thermostat")

    def finalize_device_slot(phrase):
        if "ac" in phrase.lower() or "thermostat" in phrase.lower() or "冷氣" in phrase or "空調" in phrase:
            return "thermostat"
        if is_implicit_device_word and mode in ["set_temp", "adjust"]:
            return "thermostat"
        return None

    if mode == "set_temp":
        temp = random.randint(16, 30)
        if lang == "zh":
            t_str = to_zh_count(temp) if random.random() < 0.4 else str(temp)
            structures = [
                f"{room_word}{dev_word}調到{t_str}度", 
                f"溫度設為{t_str}",
                f"{dev_word}設定{t_str}度", 
                f"幫我把{room_word}氣溫定在{t_str}",
            ]
        else:
            structures = [
                f"set {room_word} {dev_word} to {temp} degrees",
                f"make it {temp} degrees in the {room_word}",
                f"set {dev_word} to {temp}",
                f"put the {room_word} at {temp}"
            ]
        
        st = random.choice(structures)
        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in st else "default"
        
        slots["value"] = str(temp)
        slots["unit"] = "celsius"
        slots["mode"] = "setpoint"
        slots["device"] = finalize_device_slot(phr)
        
        return emit_command("climate", "set_temperature", final_target, None, slots, phr, 0.95)
    
    elif mode == "adjust":
        delta = random.choice([-5, -3, -2, -1, 1, 2, 3, 5])
        if lang == "zh":
            d_str = to_zh_count(abs(delta)) if random.random() < 0.4 else str(abs(delta))
            direction = "調高" if delta > 0 else "調低"
            structures = [
                f"{room_word}{dev_word}{direction}{d_str}度", 
                f"{direction}{room_word}溫度{d_str}度"
            ]
        else:
            direction = "increase" if delta > 0 else "decrease"
            structures = [
                f"{direction} {room_word} temp by {abs(delta)} degrees",
                f"make {room_word} {abs(delta)} degrees {'warmer' if delta > 0 else 'cooler'}",
            ]
        st = random.choice(structures)
        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in st else "default"

        slots["value"] = str(delta)
        slots["unit"] = "celsius"
        slots["mode"] = "relative"
        slots["device"] = finalize_device_slot(phr)
        
        return emit_command("climate", "adjust_temperature", final_target, None, slots, phr, 0.95)
    
    else:
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"
        if lang == "zh":
            verb = random.choice(["打開", "開", "啟動"]) if onoff == "on" else random.choice(["關掉", "關", "停掉"])
            st = f"{verb}{room_word}{dev_word}"
        else:
            verb = random.choice(["turn on", "switch on"]) if onoff == "on" else random.choice(["turn off", "switch off"])
            st = f"{verb} {room_word} {dev_word}"
            
        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in st else "default"

        slots["device"] = "thermostat"
        
        return emit_command("climate", action, final_target, onoff, slots, phr, 0.95)
    
def gen_vacuum() -> Example:
    base_room = pick_room(weight_default=0.0) 
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("vacuum", lang)
    
    act_type = random.choice(["room", "generic", "dock"])
    state = None
    
    if act_type == "room":
        if lang == "zh":
            st = f"{dev_word}去打掃{room_word}"
        else:
            st = f"{dev_word} go clean the {room_word}"
        
        return emit_command("vacuum", "set", norm_target, state, make_slots(device="robot_vacuum", mode="room", value=norm_target), humanize_text(st, lang), 0.90)

    elif act_type == "dock":
        if lang == "zh":
            phrases = ["回家", "回去充電", "回基座", "充電"]
            st = f"{dev_word}{random.choice(phrases)}"
        else:
            phrases = ["go home", "return to base", "dock", "charge", "return home"]
            st = f"{dev_word} {random.choice(phrases)}"
            
        return emit_command("vacuum", "dock", "default", state, make_slots(device="robot_vacuum"), humanize_text(st, lang), 0.90)

    else:
        act = random.choice(["start", "stop", "pause"])
        if lang == "zh":
            v_map = {
                "start": ["開始掃地", "啟動"], "stop": ["停止", "停"], 
                "pause": ["暫停", "等一下"]
            }
        else:
            v_map = {
                "start": ["start cleaning", "start"], "stop": ["stop", "halt"],
                "pause": ["pause", "hold on"]
            }
            
        st = f"{dev_word} {random.choice(v_map[act])}" if lang == "en" else f"{dev_word}{random.choice(v_map[act])}"
        
        return emit_command("vacuum", act, "default", state, make_slots(device="robot_vacuum"), humanize_text(st, lang), 0.85)
    
def gen_timer() -> Example:
    lang = "zh" if random.random() < 0.5 else "en"
    
    if random.random() < 0.6:
        val = random.choice([1, 2, 3, 5, 10, 15, 20, 25, 30, 45, 60, 90])
        unit = "minutes"
    else:
        val = random.choice([1, 2, 3, 4, 5, 6, 12, 24])
        unit = "hours"
    
    if lang == "zh":
        u_str = "分鐘" if unit == "minutes" else "小時"
        val_str = to_zh_count(val) if random.random() < 0.4 else str(val)
        prefix = random.choice(PREFIXES_ZH) if random.random() < 0.4 else ""
        
        structures = [
            f"{prefix}幫我計時{val_str}{u_str}",
            f"倒數{val_str}{u_str}",
            f"設一個{val_str}{u_str}的計時器",
            f"計時{val_str}{u_str}",
            f"{val_str}{u_str}後提醒我",
            f"定時{val_str}{u_str}",
            f"開始倒數{val_str}{u_str}",
            f"設定{val_str}{u_str}計時",
            f"我需要{val_str}{u_str}計時器",
            f"{val_str}{u_str}鬧鐘",
        ]
    else:
        u_str = unit
        prefix = random.choice(PREFIXES_EN) if random.random() < 0.4 else ""
        
        structures = [
            f"{prefix} set a timer for {val} {u_str}",
            f"countdown {val} {u_str}",
            f"timer {val} {u_str} start",
            f"{val} {u_str} timer",
            f"start {val} {u_str} timer",
            f"set timer {val} {u_str}",
            f"I need a {val} {u_str} timer",
            f"remind me in {val} {u_str}",
            f"{val} {u_str} countdown",
            f"alarm for {val} {u_str}",
        ]
        
    return emit_command("timer", "set_time", "default", None, 
                       make_slots(device="timer", value=val, unit=unit), 
                       humanize_text(random.choice(structures), lang), 0.90)

def gen_curtain() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("curtain", lang)
    
    action_type = random.choice(["open", "close", "partial"])

    slots = make_slots(device="curtain")

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
        final_target = norm_target if room_word in st else "default"

        slots["value"] = str(percentage)
        slots["unit"] = "percent"
        slots["device"] = "curtain"

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
        final_target = norm_target if room_word in st else "default"
        
        return emit_command("curtain", action, final_target, action, slots, phr, 0.95)

def gen_fan() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    dev_word = get_granular_device("fan", lang)
    
    action_type = random.choice(["onoff", "speed"])
    
    if action_type == "speed":
        speed = random.choice([1, 2, 3, "low", "medium", "high", "max"])
        if lang == "zh":
            speed_map = {1:"一檔", 2:"二檔", 3:"三檔", "low":"低速", "medium":"中速", "high":"高速", "max":"最強"}
            s_str = speed_map.get(speed, str(speed))
            structures = [
                f"{room_word}{dev_word}調{s_str}",
                f"把{dev_word}轉到{s_str}",
                f"{dev_word}設定{s_str}",
            ]
        else:
            structures = [
                f"set {room_word} {dev_word} to {speed}",
                f"{room_word} {dev_word} {speed} speed",
                f"put {room_word} {dev_word} on {speed}",
            ]
        
        st = random.choice(structures)
        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in st else "default"

        slots = make_slots(device="fan", value=str(speed), mode="speed", unit=None)
            
        return emit_command("fan", "set_speed", final_target, None, slots, phr, 0.95)
    
    else:
        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"
        if lang == "zh":
            verb = random.choice(["打開", "開"]) if onoff == "on" else random.choice(["關掉", "關"])
            structures = [f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}"]
        else:
            verb = random.choice(["turn on", "switch on"]) if onoff == "on" else random.choice(["turn off", "switch off"])
            structures = [f"{verb} {room_word} {dev_word}", f"{room_word} {dev_word} {onoff}"]
        
        st = random.choice(structures)
        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in st else "default"
        
        slots = make_slots(device="fan")
            
        return emit_command("fan", action, final_target, onoff, slots, phr, 0.95)

def gen_media() -> Example:
    base_room = pick_room()
    room_word, norm_target, lang = pick_room_word_and_target(base_room)
    
    media_type = random.choice(["tv", "speaker"])
    dev_word = get_granular_device(media_type, lang)
    
    is_implicit_device_word = False
    if random.random() < 0.50:
        dev_word = "它" if lang == "zh" else "it"
        is_implicit_device_word = True
    
    action_type = random.choice(["onoff", "volume", "playback", "channel"])
    
    slots = make_slots(device=media_type) 
    
    def finalize_device_slot(phrase, original_dev_type):
        if is_implicit_device_word:
            return None
        if original_dev_type in phrase.lower(): return original_dev_type
        if dev_word in phrase: return original_dev_type 
        return None

    if action_type == "volume":
        vol = random.choice([10, 20, 30, 40, 50, 60, 70, 80, "up", "down"])
        if lang == "zh":
            if isinstance(vol, int):
                v_str = to_zh_count(vol) if random.random() < 0.3 else str(vol)
                structures = [
                    f"{dev_word}音量調到{v_str}", 
                    f"音量{v_str}",
                    f"把聲音調成{v_str}"
                ]
            else:
                v_str = "調大" if vol == "up" else "調小"
                structures = [
                    f"{dev_word}{v_str}聲音", 
                    f"音量{v_str}",
                    f"聲音{'大' if vol == 'up' else '小'}聲一點"
                ]
        else:
            if isinstance(vol, int):
                structures = [
                    f"set {dev_word} volume to {vol}", 
                    f"volume {vol}",
                    f"make {dev_word} volume {vol}"
                ]
            else:
                structures = [
                    f"turn {dev_word} volume {vol}", 
                    f"volume {vol}",
                    f"make it {'louder' if vol == 'up' else 'quieter'}"
                ]
        
        st = random.choice(structures)
        phr = humanize_text(st, lang)
        
        final_target = norm_target if room_word in phr else "default"
        
        slots["device"] = finalize_device_slot(phr, media_type)
             
        slots["value"] = str(vol)
        slots["mode"] = "volume"
        
        return emit_command("media", "set_volume", final_target, None, slots, phr, 0.85)

    elif action_type == "onoff":
        if is_implicit_device_word:
            action_type = "playback" 
        else:
            onoff = random.choice(["on", "off"])
            action = "turn_on" if onoff == "on" else "turn_off"
            if lang == "zh":
                verb = random.choice(["打開", "開"]) if onoff == "on" else random.choice(["關掉", "關"])
                st = f"{verb}{dev_word}"
            else:
                verb = random.choice(["turn on"]) if onoff == "on" else random.choice(["turn off"])
                st = f"{verb} {dev_word}"
            
            phr = humanize_text(st, lang)
            final_target = norm_target if room_word in phr else "default"
            slots["device"] = finalize_device_slot(phr, media_type)
            return emit_command("media", action, final_target, onoff, slots, phr, 0.88)
    
    elif action_type == "channel":
        if lang == "zh":
             structures = [f"換台", f"轉到{random.randint(1,100)}台", f"切換頻道", f"下一台"]
        else:
             structures = [f"change channel", f"channel {random.randint(1,100)}", f"next channel"]
             
        st = random.choice(structures)
        phr = humanize_text(st, lang)
        
        slots["device"] = "tv"
        final_target = norm_target if room_word in phr else "default"
        
        return emit_command("media", "channel_change", final_target, None, slots, phr, 0.84)

    if action_type == "playback":
        if lang == "zh":
            options = [
                (["播放", "繼續", "繼續播放"], "play"),
                (["暫停", "停", "先停一下"], "pause")
            ]
        else:
            options = [
                (["play", "resume", "continue music"], "play"),
                (["pause", "stop", "hold on"], "pause")
            ]
            
        phrases, action = random.choice(options)
        st = random.choice(phrases)
        if is_implicit_device_word:
            if lang == "en" and action == "play": st = "play it"
            if lang == "en" and action == "pause": st = "pause it"
            
        phr = humanize_text(st, lang)
        final_target = norm_target if room_word in phr else "default"
        slots["device"] = finalize_device_slot(phr, media_type)
        
        return emit_command("media", action, final_target, None, slots, phr, 0.84)

def compute_text_hash(text: str) -> str:
    normalized = text.lower().strip()
    for char in ".,!?;:":
        normalized = normalized.replace(char, "")
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()

def mutate_example(ex: Example, attempts: int) -> Example:
    lang = "zh" if any(ord(c) > 128 for c in ex.raw_text) else "en"
    
    ex.raw_text = humanize_text(ex.raw_text, lang, noise_prob=0.0, force_variation=True)
    
    if attempts >= 2:
        if lang == "zh":
            additions = ["拜託", "謝謝", "快點", "喔", "耶", "好嗎", "可以嗎", "幫忙", "立刻"]
            if random.random() < 0.5:
                ex.raw_text = f"{random.choice(additions)}{ex.raw_text}"
            else:
                ex.raw_text = f"{ex.raw_text}{random.choice(additions)}"
        else:
            additions = ["please", "thanks", "now", "okay", "alright", "quick", "ASAP", "right now"]
            if random.random() < 0.5:
                ex.raw_text = f"{random.choice(additions)}, {ex.raw_text}"
            else:
                ex.raw_text = f"{ex.raw_text} {random.choice(additions)}"
    
    if attempts >= 4:
        ex.raw_text = add_contextual_elements(ex.raw_text, lang)
    
    if attempts >= 6:
        intensity = INTENSITY_ZH if lang == "zh" else INTENSITY_EN
        modifier = random.choice(intensity)
        words = ex.raw_text.split()
        if len(words) > 2:
            insert_pos = random.randint(1, len(words)-1)
            words.insert(insert_pos, modifier)
            ex.raw_text = " ".join(words)
    
    return ex

def gen_transcript() -> Example:
    lang = "zh" if random.random() < 0.5 else "en"
    
    broken_cmds_en = [
        "turn on the", "switch off", "set the", "open the", "can you please",
        "make it", "adjust the", "change the", "volume", "lights in the", 
        "turn on", "please turn off"
    ]
    broken_cmds_zh = [
        "打開", "關掉", "設定", "幫我開", "把那個", "音量", "調整",
        "那個房間的", "可以幫我嗎", "去開", "那個...開"
    ]

    hard_negatives_zh = [
        "我想買一台新車", "股市今天跌了", "比特幣現在多少錢", "我要買車",
        "這輛車多少錢", "開車去上班", "公車來了嗎", 
        "叫計程車", "要叫計程車", "幫我叫計程車", "我想叫計程車" 
    ]
    hard_negatives_en = [
        "I want to buy a new car", "I don't agree with you", "That's impossible",
        "What time is it", "How tall is Mount Everest", "Who is the president",
        "I want to purchase a vehicle", "Buy a tesla", "Get me a car",
        "Call an uber", "Taxi please", "Call a taxi", "I want to call a taxi"
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
                "哈囉", "有人在嗎", "測試測試"
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
                "Testing testing", "Anyone there", "Can you hear me"
            ]
            text = random.choice(texts)

    phr = humanize_text(text, lang, noise_prob=0.0)
    
    return emit_transcript("unknown", "none", None, None, make_slots(), phr, 0.15)

GENERATORS = [
    (gen_lights, 0.15),
    (gen_climate, 0.15),
    (gen_vacuum, 0.10),
    (gen_timer, 0.10),
    (gen_curtain, 0.10),
    (gen_fan, 0.10),
    (gen_media, 0.10),
    (gen_transcript, 0.25),
]

def generate(n: int, max_attempts: int = 15) -> List[Example]:
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
                print(f"Warning: High collision rate ({failed_attempts} failures). Consider expanding templates.")
            continue
        
        seen_hashes.add(text_hash)
        out.append(ex)
        
        if len(out) % 10000 == 0:
            print(f"Generated {len(out)}/{n} unique examples... ({failed_attempts} collisions)")

    return out

def main():
    p = argparse.ArgumentParser(description="Generate diverse smart home voice command dataset (optimized for Whisper STT)")
    p.add_argument("--out", default="smart_home_mega.jsonl", help="Output file path")
    p.add_argument("--n", type=int, default=100000, help="Number of examples to generate")
    p.add_argument("--seed", type=int, default=42, help="Random seed")
    p.add_argument("--asr-noise", type=float, default=0.0, 
                   help="ASR noise probability (0.0 for Whisper - clean transcriptions, 0.1-0.3 for noisier models)")
    args = p.parse_args()

    random.seed(args.seed)
    
    global ASR_NOISE_PROB
    ASR_NOISE_PROB = args.asr_noise
    
    print(f"Generating {args.n:,} unique examples with seed {args.seed}...")
    if args.asr_noise > 0:
        print(f"ASR noise level: {args.asr_noise:.2%} (simulating lower-quality STT)")
    else:
        print("ASR noise: DISABLED (optimized for Whisper - clean transcriptions)")
    print("This may take a few minutes for large datasets...")
    
    data = generate(args.n)
    
    with open(args.out, "w", encoding="utf-8") as f:
        for ex in data:
            f.write(json.dumps(asdict(ex), ensure_ascii=False) + "\n")
    
    langs = {"zh": 0, "en": 0}
    domains = {}
    for ex in data:
        lang = "zh" if any(ord(c) > 128 for c in ex.raw_text) else "en"
        langs[lang] += 1
        domains[ex.domain] = domains.get(ex.domain, 0) + 1
    
    print(f"\n{'='*60}")
    print(f"Successfully generated {len(data):,} unique examples")
    print(f"Output: {args.out}")
    print(f"\nLanguage distribution:")
    print(f"  Chinese: {langs['zh']:,} ({100*langs['zh']/len(data):.1f}%)")
    print(f"  English: {langs['en']:,} ({100*langs['en']/len(data):.1f}%)")
    print(f"\nDomain distribution:")
    for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {domain}: {count:,} ({100*count/len(data):.1f}%)")

if __name__ == "__main__":
    main()