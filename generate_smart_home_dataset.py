import json
import random
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
import hashlib

random.seed(42)

# Schema templates

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

# Room definitions

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

# lookup for detecting rooms in text
def build_room_detection_map() -> Dict[str, str]:
    """
    Build a map from all room aliases (lowercased) to their canonical room name.
    This is used to detect which room (if any) is mentioned in the final text.
    """
    detection_map = {}
    for room, aliases in ROOM_ALIASES_ZH.items():
        if room == "default":
            continue  # Don't detect default aliases as specific rooms
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
    """
    import re
    text_lower = text.lower()
    
    # Sort aliases by length (descending) to match longer phrases first
    sorted_aliases = sorted(ROOM_DETECTION_MAP.keys(), key=len, reverse=True)
    
    for alias in sorted_aliases:
        # For short English words will require word boundaries to prevent "floor" from matching "loo", "den" from matching "garden", etc.
        if len(alias) <= 4 and alias.isascii():
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_lower):
                return ROOM_DETECTION_MAP[alias]
        else:
            # For longer phrases or non-ASCII (Chinese) use simple substring match
            if alias in text_lower:
                return ROOM_DETECTION_MAP[alias]
    
    return None


# Other definitions

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
    "窗簾": ["窗連", "裝簾"],
    "風扇": ["封扇", "峰扇"],
    "計時器": ["記時器", "機時器"],
    "音量": ["音亮", "音兩"],
}

HOMOPHONES_EN = {
    "light": ["right", "lite"],
    "lights": ["rights", "lites"],
    "fan": ["van", "fin"],
    "off": ["of", "awf"],
    "on": ["an", "own"],
    "timer": ["tymer", "time her"],
    "volume": ["volumn", "valume"],
    "curtain": ["certain", "curtin"],
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

DEFAULT_COMMAND_NOISE_PROB = 0.12
DEFAULT_TRANSCRIPT_NOISE_PROB = 0.04
DEFAULT_NEGATIVE_NOISE_PROB = 0.06
DEFAULT_SEMANTIC_CONTEXT_PROB = 0.20
DEFAULT_DISCOURSE_VARIATION_PROB = 0.18
DEFAULT_REPHRASE_PROB = 0.10
DEFAULT_PUNCTUATION_VARIATION_PROB = 0.10

SEMANTIC_PREFIXES_EN = [
    "if possible, ", "when you get a moment, ", "for tonight, ",
    "before everyone arrives, ", "since guests are coming soon, ",
    "for my normal routine, ", "as soon as you can, ", "while I'm tied up, ",
    "before I forget, ", "for the next little while, ",
    "to keep things comfortable, ",
]
SEMANTIC_SUFFIXES_EN = [
    ", before everyone gets back", ", for my usual routine",
    ", so things stay comfortable", ", since I'm stepping out soon",
    ", because I'm multitasking right now", ", so it's sorted ahead of time",
    ", for the next little while", ", before I forget again",
    ", while I'm busy with something else",
]
SEMANTIC_QUESTION_PREFIXES_EN = [
    "quick check: ", "just checking: ", "small question: ", "one quick thing: ",
]
SEMANTIC_QUESTION_SUFFIXES_EN = [
    ", I'm trying to plan ahead", ", just making sure", ", so I can plan the next step",
]

SEMANTIC_PREFIXES_ZH = [
    "如果方便的話，", "有空的時候，", "先麻煩你，", "趁現在，", "我等等要出門，",
    "先幫我處理一下，", "待會會用到，", "順手幫我，", "先安排一下，",
]
SEMANTIC_SUFFIXES_ZH = [
    "，免得我忘記", "，先這樣就好", "，這樣比較方便", "，等一下會用到", "，先處理好",
    "，我正在忙別的事", "，我等等要出門", "，先幫我排好", "，先維持一下", "，這樣比較安心",
]
SEMANTIC_QUESTION_PREFIXES_ZH = [
    "順便問一下，", "我確認一下，", "我先問個問題，", "快速確認一下，",
]
SEMANTIC_QUESTION_SUFFIXES_ZH = [
    "，我只是先確認", "，我想先搞清楚", "，先確認一下",
]

DISCOURSE_REASON_EN = [
    "I'm handling something else", "I'm trying to keep things organized", "I need this sorted first",
    "I don't want to forget it", "I'm in the middle of another task", "I'm planning the next step",
]
DISCOURSE_CONTRAST_EN = [
    "I was going to leave it, but", "I thought I'd wait, but", "this can probably wait, but",
    "I wasn't going to ask, but", "I tried to ignore it, but",
]
DISCOURSE_SEQUENCE_EN = [
    "before I move on,", "as the next step,", "while we're at it,", "to keep the flow going,",
    "for this step,", "first thing,",
]

DISCOURSE_REASON_ZH = [
    "我正在忙別的事", "我想先把事情排好", "我怕我等等忘記",
    "我現在手上還有其他事", "我在安排接下來的步驟", "我想先處理這件事",
]
DISCOURSE_CONTRAST_ZH = [
    "本來想先放著，不過", "原本不急，但", "我剛剛想先等等，可是",
    "原本不打算現在做，但", "我本來想晚點再說，不過",
]
DISCOURSE_SEQUENCE_ZH = [
    "先處理這個，", "下一步先", "順便先", "趁現在先", "先把這件事做掉，", "先來",
]

EN_REPHRASE_PAIRS = [
    ("right now", "at the moment"),
    ("can you", "could you"),
    ("I need", "I would like"),
    ("set", "adjust"),
    ("turn off", "switch off"),
    ("turn on", "switch on"),
    ("for now", "for the moment"),
    ("quickly", "when you can"),
]

ZH_REPHRASE_PAIRS = [
    ("幫我", "麻煩你"),
    ("現在", "這會兒"),
    ("調到", "調成"),
    ("關掉", "關掉一下"),
    ("打開", "開一下"),
    ("先", "先幫我"),
    ("提醒我", "記得提醒我"),
]

# Helpers

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
    """Switching languages to replace a room name with its equivalent in the other language."""
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
    if random.random() > 0.30:
        return text
    corrections = CORRECTIONS_ZH if lang == "zh" else CORRECTIONS_EN
    fake_actions = ["關掉", "打開", "設定"] if lang == "zh" else ["Turn off", "Open", "Set"]
    fake = random.choice(fake_actions)
    correction = random.choice(corrections)
    return f"{fake}...{correction}，{text}" if lang == "zh" else f"{fake}... {correction}, {text}"

def inject_time_expression(text: str, lang: str, prob: float = 0.0) -> str:
    if random.random() > prob:
        return text

    time_expressions = TIME_EXPRESSIONS_ZH if lang == "zh" else TIME_EXPRESSIONS_EN
    time_expr = random.choice(time_expressions)
    if random.random() < 0.55:
        return f"{time_expr}{text}" if lang == "zh" else f"{time_expr} {text}"
    return f"{text}{time_expr}" if lang == "zh" else f"{text} {time_expr}"


def inject_token_drop(text: str, lang: str, prob: float = 0.0) -> str:
    if random.random() > prob:
        return text

    if lang == "en":
        words = text.split()
        if len(words) < 4:
            return text
        removable = [i for i, w in enumerate(words) if w.lower() not in {"not", "no", "don't", "cant", "can't"}]
        if not removable:
            return text
        del words[random.choice(removable)]
        return " ".join(words)

    removable_chunks = ["幫我", "可以", "麻煩", "一下", "一下子", "請", "我想", "幫忙"]
    present = [chunk for chunk in removable_chunks if chunk in text and len(text.replace(chunk, "", 1).strip()) >= 2]
    if not present:
        return text
    return text.replace(random.choice(present), "", 1)


def inject_restart(text: str, lang: str, prob: float = 0.0) -> str:
    if random.random() > prob:
        return text

    if lang == "en":
        words = text.split()
        if len(words) < 2:
            return text
        snippet = " ".join(words[: min(len(words), random.choice([1, 2]))])
        return f"{snippet} ... {text}"

    if len(text) < 2:
        return text
    snippet_len = 2 if len(text) > 4 else 1
    snippet = text[:snippet_len]
    return f"{snippet}...{text}"


def inject_semantic_context(text: str, lang: str, prob: float = DEFAULT_SEMANTIC_CONTEXT_PROB) -> str:
    """
    Add lightweight semantic context (intent-preserving) while keeping language to zh/en only.
    Avoids heavy edits on very short phrases to reduce label drift for ambiguous utterances.
    """
    if random.random() > prob:
        return text

    stripped = text.strip()
    if not stripped:
        return text

    if lang == "en":
        if len(stripped.split()) <= 2 and random.random() < 0.85:
            return text
    else:
        if len(stripped) <= 3 and random.random() < 0.85:
            return text

    is_question = stripped.endswith("?") or stripped.endswith("？")

    if lang == "zh":
        prefixes = SEMANTIC_QUESTION_PREFIXES_ZH if is_question else SEMANTIC_PREFIXES_ZH
        suffixes = SEMANTIC_QUESTION_SUFFIXES_ZH if is_question else SEMANTIC_SUFFIXES_ZH
    else:
        prefixes = SEMANTIC_QUESTION_PREFIXES_EN if is_question else SEMANTIC_PREFIXES_EN
        suffixes = SEMANTIC_QUESTION_SUFFIXES_EN if is_question else SEMANTIC_SUFFIXES_EN

    mode = random.choices(["prefix", "suffix", "both"], weights=[0.45, 0.35, 0.20], k=1)[0]
    if mode == "prefix":
        return f"{random.choice(prefixes)}{stripped}"
    if mode == "suffix":
        return f"{stripped}{random.choice(suffixes)}"
    return f"{random.choice(prefixes)}{stripped}{random.choice(suffixes)}"


def inject_discourse_variation(text: str, lang: str, prob: float = DEFAULT_DISCOURSE_VARIATION_PROB) -> str:
    """Inject discourse-level structure (reason/contrast/sequence) without changing intent semantics."""
    if random.random() > prob:
        return text

    stripped = text.strip()
    if not stripped:
        return text

    if lang == "en" and len(stripped.split()) <= 2 and random.random() < 0.80:
        return text
    if lang == "zh" and len(stripped) <= 3 and random.random() < 0.80:
        return text

    mode = random.choice(["reason_prefix", "reason_suffix", "contrast", "sequence"])

    if lang == "en":
        reason = random.choice(DISCOURSE_REASON_EN)
        if mode == "reason_prefix":
            return f"because {reason}, {stripped}"
        if mode == "reason_suffix":
            joiner = "" if stripped.endswith((".", "!", "?")) else ""
            return f"{stripped}{joiner}, because {reason}"
        if mode == "contrast":
            return f"{random.choice(DISCOURSE_CONTRAST_EN)} {stripped}"
        return f"{random.choice(DISCOURSE_SEQUENCE_EN)} {stripped}"

    reason = random.choice(DISCOURSE_REASON_ZH)
    if mode == "reason_prefix":
        return f"因為{reason}，{stripped}"
    if mode == "reason_suffix":
        return f"{stripped}，因為{reason}"
    if mode == "contrast":
        return f"{random.choice(DISCOURSE_CONTRAST_ZH)}{stripped}"
    return f"{random.choice(DISCOURSE_SEQUENCE_ZH)}{stripped}"


def inject_micro_rephrase(text: str, lang: str, prob: float = DEFAULT_REPHRASE_PROB) -> str:
    """Apply one lexical paraphrase to increase variety while preserving meaning."""
    if random.random() > prob:
        return text

    pairs = EN_REPHRASE_PAIRS if lang == "en" else ZH_REPHRASE_PAIRS
    random.shuffle(pairs)
    lowered = text.lower()

    for src, dst in pairs:
        if lang == "en":
            if src in lowered:
                idx = lowered.find(src)
                return text[:idx] + dst + text[idx + len(src):]
        else:
            if src in text:
                return text.replace(src, dst, 1)

    return text


def inject_punctuation_variation(text: str, lang: str, prob: float = DEFAULT_PUNCTUATION_VARIATION_PROB) -> str:
    """Add punctuation style variation to diversify surface forms."""
    if random.random() > prob:
        return text

    stripped = text.strip()
    if not stripped:
        return text

    if stripped.endswith((".", "!", "?", "。", "！", "？", "…")):
        return text

    if lang == "en":
        return stripped + random.choice([".", "!", "..."])
    return stripped + random.choice(["。", "！", "…"])


def humanize_text(
    text: str,
    lang: str,
    noise_prob: float = DEFAULT_COMMAND_NOISE_PROB,
    semantic_prob: float = DEFAULT_SEMANTIC_CONTEXT_PROB,
    discourse_prob: float = DEFAULT_DISCOURSE_VARIATION_PROB,
    rephrase_prob: float = DEFAULT_REPHRASE_PROB,
    punctuation_prob: float = DEFAULT_PUNCTUATION_VARIATION_PROB,
) -> str:
    """Add natural speech patterns such as fillers, prefixes, suffixes, code-switching."""
    text = apply_code_switching(text, lang)
    text = inject_discourse_variation(text, lang, prob=discourse_prob)
    text = inject_semantic_context(text, lang, prob=semantic_prob)
    text = inject_micro_rephrase(text, lang, prob=rephrase_prob)
    text = inject_hesitation_and_correction(text, lang)
    text = inject_time_expression(text, lang, prob=0.12)
    text = inject_asr_noise(text, lang, prob=noise_prob)
    text = inject_token_drop(text, lang, prob=noise_prob * 0.55)
    text = inject_restart(text, lang, prob=noise_prob * 0.35)
    text = inject_punctuation_variation(text, lang, prob=punctuation_prob)
    
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
        "unit": kwargs.get("unit"),
        "mode": kwargs.get("mode"),
        "scene": kwargs.get("scene"),
    }

# Data classes

@dataclass
class Example:
    type: str
    domain: str
    action: str
    target: Optional[str]
    state: Optional[str]
    slots: Dict[str, Any]
    raw_text: str  # input text

def emit_command(domain, action, target, state, slots, text) -> Example:
    return Example("command", domain, action, target, state, slots, text)

def emit_transcript(domain, action, target, state, slots, text) -> Example:
    return Example("transcript", domain, action, target, state, slots, text)


def finalize_target(text: str) -> str:
    """
    Determine the target based on what room aliases appear and ensures ground truth matches what model can see.
    """
    detected = detect_room_in_text(text)
    return detected if detected else "default"

# Domain generators

def gen_lights() -> Example:
    """Generate a lights domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"

    # Sometimes include room, sometimes not
    include_room_in_structure = (base_room != "default") and (random.random() < 0.75)
    room_word = pick_room_word(base_room, lang) if include_room_in_structure else ""

    explicit_device = random.random() < 0.70
    dev_word = get_granular_device("light", lang) if explicit_device else ("燈" if lang == "zh" else "light")

    # Brightness setting commands (15%)
    if random.random() < 0.15:
        brightness = random.choice([10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100])
        slots = make_slots(device="light", value=brightness, unit="percent")
        if lang == "zh":
            b_str = str(brightness)
            if include_room_in_structure:
                structures = [
                    f"{room_word}{dev_word}調到{b_str}%", f"把{room_word}{dev_word}亮度設{b_str}%",
                    f"{room_word}亮度{b_str}%", f"把{room_word}的{dev_word}調到{b_str}",
                ]
            else:
                structures = [
                    f"{dev_word}調到{b_str}%", f"亮度設{b_str}%", f"亮度{b_str}",
                    f"把{dev_word}調到{b_str}%", f"{dev_word}亮度{b_str}%",
                ]
        else:
            if include_room_in_structure:
                structures = [
                    f"set {room_word} {dev_word} to {brightness}%",
                    f"dim the {room_word} {dev_word} to {brightness} percent",
                    f"{room_word} {dev_word} brightness {brightness}",
                    f"set {room_word} brightness to {brightness}%",
                ]
            else:
                structures = [
                    f"set {dev_word} to {brightness}%", f"dim {dev_word} to {brightness} percent",
                    f"brightness {brightness}", f"set brightness to {brightness}%",
                    f"{dev_word} brightness {brightness}%", f"{dev_word} at {brightness} percent",
                ]
        st = random.choice(structures)
        raw_text = humanize_text(st, lang)
        final_target = finalize_target(raw_text)
        return emit_command("lights", "set", final_target, None, slots, raw_text)

    # Situational commands (25%)
    if random.random() < 0.25:
        situation = random.choice(["dark", "bright", "dark", "dark"])  # Bias toward dark (more common)
        if situation == "dark":
            onoff, action = "on", "turn_on"
            if lang == "zh":
                if include_room_in_structure:
                    phrases = [
                        f"{room_word}太暗了", f"{room_word}看不到", f"{room_word}黑黑的",
                        f"{room_word}好暗喔", f"{room_word}沒有光", f"{room_word}暗暗的",
                        f"{room_word}光線不夠", f"{room_word}伸手不見五指",
                    ]
                else:
                    phrases = [
                        "這裡太暗了", "看不到路", "有點暗", "好暗", "看不清楚", "黑漆漆的", "太暗了",
                        "需要亮一點", "看不見了", "光線太暗了", "暗死了", "我看不到東西",
                        "能不能亮一點", "這邊好暗", "視線很差",
                    ]
            else:
                if include_room_in_structure:
                    phrases = [
                        f"the {room_word} is too dark", f"it's dark in the {room_word}",
                        f"can't see in the {room_word}", f"the {room_word} is really dim",
                        f"there's no light in the {room_word}", f"the {room_word} needs light",
                        f"it's pitch black in the {room_word}",
                    ]
                else:
                    phrases = [
                        "it's too dark", "I can't see", "it's dim", "too dark", "can't see anything",
                        "it's pitch black", "I need some light", "it's really dark in here",
                        "can barely see", "where's the light", "I need light", "so dark",
                        "there's no light", "it's too dim", "could use some light in here",
                    ]
        else:
            onoff, action = "off", "turn_off"
            if lang == "zh":
                if include_room_in_structure:
                    phrases = [
                        f"{room_word}太亮了", f"{room_word}好刺眼",
                        f"{room_word}光線太強了", f"{room_word}亮到不行",
                    ]
                else:
                    phrases = [
                        "這裡太亮了", "好刺眼", "太亮了", "眼睛好痛", "亮到受不了",
                        "光線太強了", "刺眼死了", "亮得睜不開眼", "太刺眼了",
                    ]
            else:
                if include_room_in_structure:
                    phrases = [
                        f"the {room_word} is too bright", f"too bright in the {room_word}",
                        f"the {room_word} lights are blinding", f"it's way too bright in the {room_word}",
                    ]
                else:
                    phrases = [
                        "it's too bright", "it's blinding", "too bright", "my eyes hurt",
                        "way too bright", "the light is blinding me", "so bright",
                        "it's hurting my eyes", "turn down the brightness",
                    ]

        raw_text = humanize_text(random.choice(phrases), lang)
        final_target = finalize_target(raw_text)
        slots = make_slots(device="light")
        return emit_command("lights", action, final_target, onoff, slots, raw_text)

    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"
    slots = make_slots(device="light")

    if lang == "zh":
        verbs = ["打開", "開", "開啟"] if onoff == "on" else ["關掉", "關", "關閉", "熄"]
        verb = random.choice(verbs)
        if include_room_in_structure:
            structures = [
                f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}",
                f"把{room_word}{dev_word}{verb}", f"把{room_word}的{dev_word}{verb}",
                f"{room_word}的{dev_word}幫我{verb}", f"我要{verb}{room_word}{dev_word}",
                f"幫我{verb}{room_word}的{dev_word}",
            ]
        else:
            structures = [
                f"{verb}{dev_word}", f"把{dev_word}{verb}",
                f"幫我{verb}{dev_word}", f"我要{verb}{dev_word}",
                f"{dev_word}幫我{verb}", f"可以{verb}{dev_word}嗎",
            ]
    else:
        verbs_on = ["turn on", "switch on", "flip on", "put on"]
        verbs_off = ["turn off", "switch off", "flip off", "shut off", "kill"]
        verb = random.choice(verbs_on) if onoff == "on" else random.choice(verbs_off)
        if include_room_in_structure:
            structures = [
                f"{verb} the {room_word} {dev_word}", f"{verb} {room_word} {dev_word}",
                f"{verb} the {dev_word} in the {room_word}",
                f"I need the {room_word} {dev_word} {'on' if onoff == 'on' else 'off'}",
                f"can you {verb} the {room_word} {dev_word}",
                f"would you {verb} the {room_word} {dev_word}",
                f"the {room_word} {dev_word} needs to be {'on' if onoff == 'on' else 'off'}",
            ]
        else:
            structures = [
                f"{verb} the {dev_word}", f"{verb} {dev_word}",
                f"I want the {dev_word} {'on' if onoff == 'on' else 'off'}",
                f"{dev_word} {'on' if onoff == 'on' else 'off'}",
                f"can you {verb} the {dev_word}",
                f"hit the {dev_word}" if onoff == "on" else f"kill the {dev_word}",
                f"would you mind {'turning on' if onoff == 'on' else 'turning off'} the {dev_word}",
                f"get the {dev_word} {'on' if onoff == 'on' else 'off'}",
            ]

    st = random.choice(structures)
    raw_text = humanize_text(st, lang)
    final_target = finalize_target(raw_text)
    return emit_command("lights", action, final_target, onoff, slots, raw_text)


def gen_climate() -> Example:
    """Generate a climate domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"
    
    include_room_in_structure = (base_room != "default") and (random.random() < 0.70)
    room_word = pick_room_word(base_room, lang) if include_room_in_structure else ""

    explicit_device = random.random() < 0.55
    dev_word = get_granular_device("ac", lang) if explicit_device else ("冷氣" if lang == "zh" else "AC")

    # Feeling-based commands (25%)
    if random.random() < 0.25:
        feeling = random.choice(["hot", "cold", "hot", "hot"])
        if feeling == "hot":
            if lang == "zh":
                if include_room_in_structure:
                    phrases = [
                        f"{room_word}好悶", f"{room_word}好熱", f"{room_word}太熱了",
                        f"{room_word}悶到不行", f"{room_word}像烤箱一樣",
                        f"{room_word}熱得受不了", f"{room_word}快熱死了",
                    ]
                else:
                    phrases = [
                        "好熱", "太熱了", "熱死了", "好悶", "快中暑了", "流汗了", "受不了這個熱",
                        "悶死了", "好熱好熱", "快要融化了", "汗流浹背", "空氣好悶",
                        "熱得受不了", "像在蒸桑拿", "又熱又悶",
                    ]
            else:
                if include_room_in_structure:
                    phrases = [
                        f"the {room_word} is hot", f"it's too hot in the {room_word}",
                        f"the {room_word} is stuffy", f"the {room_word} feels like an oven",
                        f"it's boiling in the {room_word}", f"the {room_word} is sweltering",
                    ]
                else:
                    phrases = [
                        "it's too hot", "I'm burning up", "it's so hot", "I'm sweating",
                        "it's stuffy", "the heat is killing me", "I'm roasting",
                        "it's boiling in here", "so hot in here", "I'm dying of heat",
                        "it feels like a sauna", "need some cool air", "can't stand the heat",
                    ]
            action, state = "turn_on", "on"
        else:
            if lang == "zh":
                if include_room_in_structure:
                    phrases = [
                        f"{room_word}好冰", f"{room_word}好冷", f"{room_word}太冷了",
                        f"{room_word}冷到不行", f"{room_word}凍死了",
                    ]
                else:
                    phrases = [
                        "好冷", "太冷了", "冷死了", "發抖了", "冷到受不了",
                        "凍死了", "好冰", "手腳冰冷", "冷到發抖", "快凍僵了",
                    ]
            else:
                if include_room_in_structure:
                    phrases = [
                        f"the {room_word} is freezing", f"it's cold in the {room_word}",
                        f"the {room_word} is like a fridge", f"it's so cold in the {room_word}",
                    ]
                else:
                    phrases = [
                        "it's too cold", "I'm freezing", "it's freezing", "I'm shivering",
                        "way too cold", "it's like a freezer in here", "I'm so cold",
                        "brr it's cold", "need some heat", "I can see my breath",
                    ]
            action, state = "turn_off", "off"

        raw_text = humanize_text(random.choice(phrases), lang)
        final_target = finalize_target(raw_text)
        slots = make_slots(device="thermostat")
        return emit_command("climate", action, final_target, state, slots, raw_text)

    # Temperature setting (35%)
    if random.random() < 0.35:
        temp = random.choice([16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30])
        if lang == "zh":
            t_str = to_zh_count(temp) if random.random() < 0.3 else str(temp)
            if include_room_in_structure:
                structures = [
                    f"{room_word}{dev_word}設{t_str}度", f"把{room_word}溫度調到{t_str}度",
                    f"{room_word}溫度{t_str}度", f"把{room_word}{dev_word}調到{t_str}度",
                    f"{room_word}設定{t_str}度",
                ]
            else:
                structures = [
                    f"{dev_word}設{t_str}度", f"溫度調到{t_str}度",
                    f"溫度{t_str}度", f"調到{t_str}度",
                    f"設{t_str}度", f"{dev_word}調{t_str}度",
                    f"把溫度設成{t_str}度",
                ]
        else:
            if include_room_in_structure:
                structures = [
                    f"set {room_word} {dev_word} to {temp} degrees",
                    f"set the {room_word} temperature to {temp}",
                    f"make the {room_word} {temp} degrees",
                    f"{room_word} temperature {temp}",
                    f"I want the {room_word} at {temp} degrees",
                ]
            else:
                structures = [
                    f"set {dev_word} to {temp} degrees", f"set temperature to {temp}",
                    f"temperature {temp}", f"{dev_word} {temp} degrees",
                    f"make it {temp} degrees", f"I want {temp} degrees",
                    f"set it to {temp}", f"change temperature to {temp}",
                    f"{temp} degrees",
                ]

        st = random.choice(structures)
        raw_text = humanize_text(st, lang)
        final_target = finalize_target(raw_text)
        slots = make_slots(device="thermostat", value=temp, unit="celsius")
        return emit_command("climate", "set", final_target, None, slots, raw_text)

    # On/off
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"

    if lang == "zh":
        verbs_on = ["打開", "開", "啟動", "開啟"]
        verbs_off = ["關掉", "關", "關閉", "停掉"]
        verb = random.choice(verbs_on) if onoff == "on" else random.choice(verbs_off)
        if include_room_in_structure:
            structures = [
                f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}",
                f"把{room_word}{dev_word}{verb}", f"幫我{verb}{room_word}的{dev_word}",
                f"我要{verb}{room_word}{dev_word}",
            ]
        else:
            structures = [
                f"{verb}{dev_word}", f"把{dev_word}{verb}",
                f"幫我{verb}{dev_word}", f"我要{verb}{dev_word}",
                f"可以{verb}{dev_word}嗎",
            ]
    else:
        verb = random.choice(["turn on", "switch on", "fire up"]) if onoff == "on" else random.choice(["turn off", "switch off", "shut off"])
        if include_room_in_structure:
            structures = [
                f"{verb} the {room_word} {dev_word}", f"{verb} {dev_word} in the {room_word}",
                f"can you {verb} the {room_word} {dev_word}",
                f"I need the {room_word} {dev_word} {'on' if onoff == 'on' else 'off'}",
                f"the {room_word} {dev_word} needs to go {'on' if onoff == 'on' else 'off'}",
            ]
        else:
            structures = [
                f"{verb} the {dev_word}", f"{verb} {dev_word}",
                f"can you {verb} the {dev_word}",
                f"I want the {dev_word} {'on' if onoff == 'on' else 'off'}",
                f"{dev_word} {'on' if onoff == 'on' else 'off'}",
                f"get the {dev_word} {'going' if onoff == 'on' else 'off'}",
            ]

    st = random.choice(structures)
    raw_text = humanize_text(st, lang)
    final_target = finalize_target(raw_text)
    slots = make_slots(device="thermostat")
    return emit_command("climate", action, final_target, onoff, slots, raw_text)


def gen_vacuum() -> Example:
    """Generate a vacuum domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"

    dev_word = get_granular_device("vacuum", lang)

    # Situational / mess-based commands (10%)
    if random.random() < 0.10:
        if lang == "zh":
            phrases = [
                "地板好髒", "地上好多灰塵", "地板需要清一下", "好多毛髮在地上",
                "地上都是碎屑", "該掃地了", "好久沒掃地了", "地板髒死了",
            ]
        else:
            phrases = [
                "the floor is dirty", "there's dust everywhere", "the floor needs cleaning",
                "there's hair all over the floor", "crumbs on the floor", "time to vacuum",
                "the floor is a mess", "the floor hasn't been cleaned in a while",
            ]
        raw_text = humanize_text(random.choice(phrases), lang)
        slots = make_slots(device="robot_vacuum")
        return emit_command("vacuum", "start", "default", None, slots, raw_text)

    # Room-specific cleaning (25%)
    if random.random() < 0.25 and base_room != "default":
        room_word = pick_room_word(base_room, lang)

        if lang == "zh":
            structures = [
                f"{dev_word}去打掃{room_word}", f"打掃{room_word}", f"{room_word}要打掃",
                f"去{room_word}掃一下", f"幫我掃{room_word}", f"{dev_word}清潔{room_word}",
                f"{room_word}地板掃一下",
            ]
        else:
            structures = [
                f"{dev_word} go clean the {room_word}", f"clean the {room_word}",
                f"vacuum the {room_word}", f"sweep the {room_word}",
                f"send the {dev_word} to the {room_word}", f"have the {dev_word} do the {room_word}",
                f"can you clean the {room_word}",
            ]

        st = random.choice(structures)
        raw_text = humanize_text(st, lang)
        final_target = finalize_target(raw_text)

        if final_target != "default":
            slots = make_slots(device="robot_vacuum", mode="room", value=final_target)
        else:
            slots = make_slots(device="robot_vacuum")
        return emit_command("vacuum", "start", final_target, None, slots, raw_text)

    # Dock command (20%)
    if random.random() < 0.20:
        if lang == "zh":
            phrases = [
                f"{dev_word}回家", f"{dev_word}回去充電", f"{dev_word}回基座", f"{dev_word}充電",
                f"叫{dev_word}回去", f"{dev_word}回充電座", f"讓{dev_word}回家",
            ]
        else:
            phrases = [
                f"{dev_word} go home", f"{dev_word} return to base", f"{dev_word} dock",
                f"send the {dev_word} home", f"have the {dev_word} go charge",
                f"tell the {dev_word} to come back", f"{dev_word} go back to the dock",
            ]

        raw_text = humanize_text(random.choice(phrases), lang)
        slots = make_slots(device="robot_vacuum")
        return emit_command("vacuum", "dock", "default", None, slots, raw_text)

    # Generic start/stop/pause
    act = random.choice(["start", "stop", "pause"])
    if lang == "zh":
        v_map = {
            "start": ["開始掃地", "啟動", "開始打掃", "開始清潔", "去掃地", "出動"],
            "stop": ["停止", "停", "不要掃了", "停下來", "別掃了"],
            "pause": ["暫停", "等一下", "先停一下", "暫時停止"],
        }
        structures = [f"{dev_word}{random.choice(v_map[act])}", f"叫{dev_word}{random.choice(v_map[act])}"]
    else:
        v_map = {
            "start": ["start cleaning", "start", "begin cleaning", "go clean", "start vacuuming", "run"],
            "stop": ["stop", "halt", "stop cleaning", "quit", "stop vacuuming"],
            "pause": ["pause", "hold", "wait", "hold on", "pause cleaning"],
        }
        verb_phrase = random.choice(v_map[act])
        structures = [f"{dev_word} {verb_phrase}", f"have the {dev_word} {verb_phrase}", f"tell the {dev_word} to {verb_phrase}"]

    raw_text = humanize_text(random.choice(structures), lang)
    slots = make_slots(device="robot_vacuum")
    return emit_command("vacuum", act, "default", None, slots, raw_text)


def gen_timer() -> Example:
    """Generate a timer domain command."""
    lang = "zh" if random.random() < 0.5 else "en"

    # Add seconds as a unit option (15%)
    r = random.random()
    if r < 0.15:
        val = random.choice([10, 15, 20, 30, 45, 60, 90])
        unit = "seconds"
    elif r < 0.60:
        val = random.choice([1, 2, 3, 5, 10, 15, 20, 30, 45, 60])
        unit = "minutes"
    else:
        val = random.choice([1, 2, 3, 4, 5, 6, 8, 12])
        unit = "hours"

    slots = make_slots(device="timer", value=val, unit=unit)

    if lang == "zh":
        u_map = {"seconds": "秒", "minutes": "分鐘", "hours": "小時"}
        u_str = u_map[unit]
        val_str = to_zh_count(val) if random.random() < 0.4 else str(val)
        structures = [
            f"設一個{val_str}{u_str}計時器",
            f"{val_str}{u_str}後提醒我",
            f"倒數{val_str}{u_str}",
            f"計時{val_str}{u_str}",
            f"設定{val_str}{u_str}倒數計時",
            f"幫我計時{val_str}{u_str}",
            f"定時{val_str}{u_str}",
            f"鬧鐘{val_str}{u_str}",
            f"{val_str}{u_str}後叫我",
            f"設個{val_str}{u_str}的定時器",
            f"幫我倒數{val_str}{u_str}",
            f"再{val_str}{u_str}提醒我一下",
            f"過{val_str}{u_str}叫我一聲",
            f"給我一個{val_str}{u_str}倒數",
            f"{val_str}{u_str}後通知我",
            f"幫我設{val_str}{u_str}提醒",
        ]
    else:
        u_str = unit
        u_singular = unit.rstrip("s") if val == 1 else unit
        structures = [
            f"set a {val} {u_str} timer",
            f"remind me in {val} {u_str}",
            f"timer {val} {u_str}",
            f"alert me in {val} {u_str}",
            f"countdown {val} {u_str}",
            f"set timer for {val} {u_str}",
            f"start a {val} {u_singular} timer",
            f"{val} {u_singular} timer",
            f"wake me up in {val} {u_str}",
            f"notify me in {val} {u_str}",
            f"I need a {val} {u_singular} timer",
            f"can you set a {val} {u_singular} timer",
            f"give me a {val} {u_singular} countdown",
            f"ping me in {val} {u_str}",
            f"remind me after {val} {u_str}",
            f"set up a {val} {u_singular} countdown",
            f"in {val} {u_str} give me a heads up",
        ]

    raw_text = humanize_text(random.choice(structures), lang)
    return emit_command("timer", "set_time", "default", None, slots, raw_text)


def gen_curtain() -> Example:
    """Generate a curtain domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"

    include_room_in_structure = (base_room != "default") and (random.random() < 0.70)
    room_word = pick_room_word(base_room, lang) if include_room_in_structure else ""

    dev_word = get_granular_device("curtain", lang)

    action_type = random.choice(["open", "close", "partial"])
    slots = make_slots(device="curtain")

    # Situational commands (10%)
    if random.random() < 0.10:
        situation = random.choice(["sunny", "dark", "privacy"])
        if situation == "sunny":
            action = "close"
            if lang == "zh":
                phrases = [
                    "太陽好大", "陽光太刺眼", "太曬了", "光線太強了",
                    "被太陽照到了", "好刺眼", "陽光進來了",
                ]
            else:
                phrases = [
                    "the sun is too bright", "too much sunlight", "it's too sunny",
                    "the glare is terrible", "the sun is in my eyes", "too much light coming in",
                ]
        elif situation == "dark":
            action = "open"
            if lang == "zh":
                phrases = [
                    "讓陽光進來", "想要自然光", "太暗了開窗簾", "需要光線",
                    "讓光進來", "想看外面",
                ]
            else:
                phrases = [
                    "let some light in", "I want natural light", "it's too dark open the curtains",
                    "need some daylight", "let the light in", "I want to see outside",
                ]
        else:
            action = "close"
            if lang == "zh":
                phrases = ["需要隱私", "有人在看", "拉上窗簾比較好", "不想被看到"]
            else:
                phrases = ["I need some privacy", "someone might see in", "close the drapes", "I don't want people looking in"]

        raw_text = humanize_text(random.choice(phrases), lang)
        final_target = finalize_target(raw_text)
        return emit_command("curtain", action, final_target, None, slots, raw_text)

    if action_type == "partial":
        percentage = random.choice([10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90])
        if lang == "zh":
            p_str = str(percentage)
            if include_room_in_structure:
                structures = [
                    f"{room_word}{dev_word}開{p_str}%", f"把{room_word}{dev_word}開到{p_str}%",
                    f"{room_word}的{dev_word}調到{p_str}%", f"把{room_word}{dev_word}拉到{p_str}%",
                ]
            else:
                structures = [
                    f"{dev_word}開{p_str}%", f"把{dev_word}開到{p_str}%",
                    f"{dev_word}調到{p_str}%", f"{dev_word}{p_str}%",
                    f"把{dev_word}拉到{p_str}%",
                ]
        else:
            if include_room_in_structure:
                structures = [
                    f"open {room_word} {dev_word} {percentage}%",
                    f"set {room_word} {dev_word} to {percentage}%",
                    f"{room_word} {dev_word} at {percentage} percent",
                    f"put the {room_word} {dev_word} at {percentage}%",
                ]
            else:
                structures = [
                    f"open {dev_word} {percentage}%", f"set {dev_word} to {percentage}%",
                    f"{dev_word} at {percentage} percent", f"{dev_word} {percentage}%",
                    f"put the {dev_word} at {percentage}%",
                ]

        st = random.choice(structures)
        raw_text = humanize_text(st, lang)
        final_target = finalize_target(raw_text)
        slots["value"] = str(percentage)
        slots["unit"] = "percent"
        return emit_command("curtain", "set_position", final_target, None, slots, raw_text)

    action = "open" if action_type == "open" else "close"
    if lang == "zh":
        verbs = ["打開", "拉開", "開", "升起"] if action == "open" else ["關上", "拉上", "關", "拉下", "合上"]
        verb = random.choice(verbs)
        if include_room_in_structure:
            structures = [
                f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}",
                f"把{room_word}{dev_word}{verb}", f"把{room_word}的{dev_word}{verb}",
                f"幫我{verb}{room_word}的{dev_word}",
            ]
        else:
            structures = [
                f"{verb}{dev_word}", f"把{dev_word}{verb}",
                f"幫我{verb}{dev_word}", f"我要{verb}{dev_word}",
                f"可以{verb}{dev_word}嗎",
            ]
    else:
        verbs_open = ["open", "pull open", "raise", "draw open"]
        verbs_close = ["close", "shut", "draw", "pull shut", "lower"]
        verb = random.choice(verbs_open) if action == "open" else random.choice(verbs_close)
        if include_room_in_structure:
            structures = [
                f"{verb} the {room_word} {dev_word}", f"{verb} {room_word} {dev_word}",
                f"can you {verb} the {room_word} {dev_word}",
                f"I want the {room_word} {dev_word} {'open' if action == 'open' else 'closed'}",
                f"would you {verb} the {room_word} {dev_word}",
            ]
        else:
            structures = [
                f"{verb} the {dev_word}", f"{verb} {dev_word}",
                f"can you {verb} the {dev_word}",
                f"I want the {dev_word} {'open' if action == 'open' else 'closed'}",
                f"{dev_word} {'open' if action == 'open' else 'closed'}",
                f"would you mind {'opening' if action == 'open' else 'closing'} the {dev_word}",
            ]

    st = random.choice(structures)
    raw_text = humanize_text(st, lang)
    final_target = finalize_target(raw_text)
    return emit_command("curtain", action, final_target, None, slots, raw_text)


def gen_fan() -> Example:
    """Generate a fan domain command."""
    base_room = pick_room()
    lang = "zh" if random.random() < 0.5 else "en"

    include_room_in_structure = (base_room != "default") and (random.random() < 0.65)
    room_word = pick_room_word(base_room, lang) if include_room_in_structure else ""

    dev_word = get_granular_device("fan", lang)
    action_type = random.choice(["onoff", "onoff", "speed", "speed"])

    # Situational (8%)
    if random.random() < 0.08:
        if lang == "zh":
            phrases = [
                "好悶需要通風", "空氣不流通", "需要吹一下風", "有點悶",
                "想要涼快一點", "需要風",
            ]
        else:
            phrases = [
                "it's stuffy in here", "I need some air", "need some airflow",
                "it's not breezy enough", "could use a breeze", "the air is stale",
            ]
        raw_text = humanize_text(random.choice(phrases), lang)
        final_target = finalize_target(raw_text)
        slots = make_slots(device="fan")
        return emit_command("fan", "turn_on", final_target, "on", slots, raw_text)

    if action_type == "speed":
        direction = random.choice(["up", "down"])
        sign = 1 if direction == "up" else -1

        explicit_magnitude = random.random() < 0.30
        mag = random.choice([1, 2, 3]) if explicit_magnitude else None
        delta = (sign * mag) if mag else None

        slots = make_slots(device="fan", mode="relative")
        if delta:
            slots["value"] = str(delta)

        if lang == "zh":
            up_words = ["快", "大", "強", "高"]
            down_words = ["慢", "小", "弱", "低"]
            adj = random.choice(up_words) if sign > 0 else random.choice(down_words)
            if explicit_magnitude:
                mag_str = str(mag)
                if include_room_in_structure:
                    structures = [
                        f"{room_word}{dev_word}風速調{'高' if sign > 0 else '低'}{mag_str}檔",
                        f"把{room_word}{dev_word}{'加' if sign > 0 else '減'}{mag_str}檔",
                    ]
                else:
                    structures = [
                        f"{dev_word}風速調{'高' if sign > 0 else '低'}{mag_str}檔",
                        f"風速{'加' if sign > 0 else '減'}{mag_str}檔",
                        f"{dev_word}{'加' if sign > 0 else '減'}{mag_str}檔",
                    ]
            else:
                if include_room_in_structure:
                    structures = [
                        f"{room_word}{dev_word}{adj}一點",
                        f"把{room_word}{dev_word}調{adj}",
                        f"{room_word}{dev_word}再{adj}一些",
                    ]
                else:
                    structures = [
                        f"{dev_word}{adj}一點", f"風扇{adj}一點",
                        f"把{dev_word}調{adj}", f"{dev_word}再{adj}一些",
                        f"風{adj}一點",
                    ]
        else:
            if explicit_magnitude:
                if include_room_in_structure:
                    structures = [
                        f"turn the {room_word} {dev_word} {'up' if sign > 0 else 'down'} by {mag}",
                        f"increase the {room_word} {dev_word} speed by {mag}" if sign > 0 else f"decrease the {room_word} {dev_word} speed by {mag}",
                    ]
                else:
                    structures = [
                        f"turn {dev_word} {'up' if sign > 0 else 'down'} by {mag}",
                        f"fan speed {'up' if sign > 0 else 'down'} {mag}",
                        f"{'increase' if sign > 0 else 'decrease'} fan speed by {mag}",
                    ]
            else:
                if include_room_in_structure:
                    structures = [
                        f"turn the {room_word} {dev_word} {'up' if sign > 0 else 'down'}",
                        f"make the {room_word} {dev_word} {'faster' if sign > 0 else 'slower'}",
                        f"{room_word} {dev_word} {'higher' if sign > 0 else 'lower'}",
                    ]
                else:
                    structures = [
                        f"turn {dev_word} {'up' if sign > 0 else 'down'}",
                        f"fan {'faster' if sign > 0 else 'slower'}",
                        f"{'speed up' if sign > 0 else 'slow down'} the {dev_word}",
                        f"make the {dev_word} {'faster' if sign > 0 else 'slower'}",
                        f"{dev_word} {'higher' if sign > 0 else 'lower'}",
                        f"{'more' if sign > 0 else 'less'} fan",
                    ]

        st = random.choice(structures)
        raw_text = humanize_text(st, lang)
        final_target = finalize_target(raw_text)
        return emit_command("fan", "set_speed", final_target, None, slots, raw_text)

    # On/off
    onoff = random.choice(["on", "off"])
    action = "turn_on" if onoff == "on" else "turn_off"
    slots = make_slots(device="fan")

    if lang == "zh":
        verbs_on = ["打開", "開", "啟動", "開啟"]
        verbs_off = ["關掉", "關", "停掉", "關閉"]
        verb = random.choice(verbs_on) if onoff == "on" else random.choice(verbs_off)
        if include_room_in_structure:
            structures = [
                f"{verb}{room_word}{dev_word}", f"{room_word}{dev_word}{verb}",
                f"把{room_word}{dev_word}{verb}", f"幫我{verb}{room_word}的{dev_word}",
            ]
        else:
            structures = [
                f"{verb}{dev_word}", f"把{dev_word}{verb}",
                f"幫我{verb}{dev_word}", f"我要{verb}{dev_word}",
            ]
    else:
        verb = random.choice(["turn on", "switch on"]) if onoff == "on" else random.choice(["turn off", "switch off", "shut off"])
        if include_room_in_structure:
            structures = [
                f"{verb} the {room_word} {dev_word}", f"{verb} {room_word} {dev_word}",
                f"can you {verb} the {room_word} {dev_word}",
                f"I want the {room_word} {dev_word} {'on' if onoff == 'on' else 'off'}",
            ]
        else:
            structures = [
                f"{verb} the {dev_word}", f"{verb} {dev_word}",
                f"can you {verb} the {dev_word}",
                f"{dev_word} {'on' if onoff == 'on' else 'off'}",
                f"I want the {dev_word} {'on' if onoff == 'on' else 'off'}",
                f"get the {dev_word} {'going' if onoff == 'on' else 'off'}",
            ]

    st = random.choice(structures)
    raw_text = humanize_text(st, lang)
    final_target = finalize_target(raw_text)
    return emit_command("fan", action, final_target, onoff, slots, raw_text)


def gen_media() -> Example:
    """Generate a media domain command."""
    lang = "zh" if random.random() < 0.5 else "en"

    action_type = random.choice(["onoff", "volume_explicit", "volume_generic", "playback", "playback", "playback", "channel"])

    if action_type == "volume_generic":
        numeric = random.random() < 0.50
        vol = random.choice([5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100])
        direction = random.choice(["up", "down"])

        if numeric:
            if lang == "zh":
                structures = [
                    f"音量調到{vol}", f"音量{vol}", f"把音量設成{vol}",
                    f"音量調{vol}", f"聲音調到{vol}",
                ]
            else:
                structures = [
                    f"set volume to {vol}", f"volume {vol}", f"volume at {vol}",
                    f"make it volume {vol}", f"put the volume at {vol}",
                ]
            slots = make_slots(value=str(vol), mode="volume")
        else:
            if lang == "zh":
                structures = [
                    f"音量{'調大' if direction == 'up' else '調小'}",
                    f"{'大' if direction == 'up' else '小'}聲一點",
                    f"聲音{'大' if direction == 'up' else '小'}一點",
                    f"音量{'加大' if direction == 'up' else '降低'}",
                    f"{'太小聲了' if direction == 'up' else '太大聲了'}",
                ]
            else:
                structures = [
                    f"volume {'up' if direction == 'up' else 'down'}",
                    f"{'louder' if direction == 'up' else 'quieter'}",
                    f"{'turn it up' if direction == 'up' else 'turn it down'}",
                    "I can't hear" if direction == "up" else "it's too loud",
                    f"{'crank it up' if direction == 'up' else 'tone it down'}",
                    f"make it {'louder' if direction == 'up' else 'quieter'}",
                ]
            slots = make_slots(mode="volume")

        raw_text = humanize_text(random.choice(structures), lang)
        return emit_command("media", "set_volume", "default", None, slots, raw_text)

    if action_type == "volume_explicit":
        media_type = random.choice(["tv", "speaker"])
        dev_word = get_granular_device(media_type, lang)

        numeric = random.random() < 0.50
        vol = random.choice([5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100])

        if numeric:
            if lang == "zh":
                structures = [
                    f"{dev_word}音量調到{vol}", f"{dev_word}音量{vol}",
                    f"把{dev_word}音量設成{vol}", f"{dev_word}聲音調到{vol}",
                ]
            else:
                structures = [
                    f"set {dev_word} volume to {vol}", f"{dev_word} volume {vol}",
                    f"put the {dev_word} at volume {vol}", f"{dev_word} at {vol}",
                ]
            slots = make_slots(device=media_type, value=str(vol), mode="volume")
        else:
            direction = random.choice(["up", "down"])
            if lang == "zh":
                structures = [
                    f"{dev_word}{'大' if direction == 'up' else '小'}聲一點",
                    f"把{dev_word}{'調大' if direction == 'up' else '調小'}",
                    f"{dev_word}聲音{'太小了' if direction == 'up' else '太大了'}",
                ]
            else:
                structures = [
                    f"{dev_word} {'louder' if direction == 'up' else 'quieter'}",
                    f"turn the {dev_word} {'up' if direction == 'up' else 'down'}",
                    f"make the {dev_word} {'louder' if direction == 'up' else 'quieter'}",
                    f"the {dev_word} is too {'quiet' if direction == 'up' else 'loud'}",
                ]
            slots = make_slots(device=media_type, mode="volume")

        raw_text = humanize_text(random.choice(structures), lang)
        return emit_command("media", "set_volume", "default", None, slots, raw_text)

    if action_type == "channel":
        dev_word = get_granular_device("tv", lang)

        numeric = random.random() < 0.50
        ch = random.randint(1, 100)

        if numeric:
            if lang == "zh":
                structures = [
                    f"轉到{ch}台", f"{dev_word}切到{ch}台",
                    f"切{ch}台", f"轉{ch}台", f"換到{ch}台",
                ]
            else:
                structures = [
                    f"channel {ch}", f"switch to channel {ch}",
                    f"go to channel {ch}", f"put on channel {ch}",
                    f"change to channel {ch}",
                ]
            slots = make_slots(device="tv", value=str(ch), mode="channel")
        else:
            if lang == "zh":
                structures = ["換台", "下一台", "切換頻道", "轉台", "上一台"]
            else:
                structures = ["change channel", "next channel", "change the channel", "flip the channel", "switch channels"]
            slots = make_slots(device="tv", mode="channel")

        raw_text = humanize_text(random.choice(structures), lang)
        return emit_command("media", "channel_change", "default", None, slots, raw_text)

    if action_type == "onoff":
        media_type = random.choice(["tv", "speaker"])
        dev_word = get_granular_device(media_type, lang)

        onoff = random.choice(["on", "off"])
        action = "turn_on" if onoff == "on" else "turn_off"

        if lang == "zh":
            verbs_on = ["打開", "開", "開啟"]
            verbs_off = ["關掉", "關", "關閉"]
            verb = random.choice(verbs_on) if onoff == "on" else random.choice(verbs_off)
            structures = [
                f"{verb}{dev_word}", f"把{dev_word}{verb}",
                f"幫我{verb}{dev_word}", f"我要{verb}{dev_word}",
            ]
        else:
            verb = random.choice(["turn on", "switch on", "put on"]) if onoff == "on" else random.choice(["turn off", "switch off", "shut off"])
            structures = [
                f"{verb} {dev_word}", f"{verb} the {dev_word}",
                f"can you {verb} the {dev_word}", f"I want the {dev_word} {'on' if onoff == 'on' else 'off'}",
                f"{dev_word} {'on' if onoff == 'on' else 'off'}",
            ]

        raw_text = humanize_text(random.choice(structures), lang)
        slots = make_slots(device=media_type)
        return emit_command("media", action, "default", onoff, slots, raw_text)

    # Playback
    media_type = random.choice(["tv", "speaker"])
    dev_word = get_granular_device(media_type, lang)

    action = random.choice(["play", "play", "pause", "pause", "next", "previous", "stop", "next", "previous"])
    if lang == "zh":
        vmap_variants = {
            "play": ["播放", "放", "繼續播放", "繼續放", "開始播", "繼續播"],
            "pause": ["暫停", "停一下", "暫時停止", "先停一下"],
            "next": ["下一首", "下一個", "下一曲", "切下一首", "跳下一首"],
            "previous": ["上一首", "上一個", "上一曲", "切上一首", "回上一首"],
            "stop": ["停止", "停止播放", "不要放了", "先不要播了"],
        }
        verb_phrase = random.choice(vmap_variants[action])
        if action in ["next", "previous"]:
            structures = [
                f"{dev_word}{verb_phrase}", verb_phrase, f"切{verb_phrase}", f"幫我{verb_phrase}",
                f"{verb_phrase}一下", f"{dev_word}{verb_phrase}一下",
            ]
        else:
            structures = [
                f"{dev_word}{verb_phrase}", verb_phrase, f"幫我{verb_phrase}",
                f"{verb_phrase}一下", f"{dev_word}{verb_phrase}一下",
            ]
        st = random.choice(structures)
    else:
        vmap_variants = {
            "play": ["play", "resume", "continue playing", "start playing", "keep playing"],
            "pause": ["pause", "pause it", "hold on", "pause for a second"],
            "next": ["next track", "next song", "skip", "next", "skip this", "skip ahead"],
            "previous": ["previous track", "previous song", "go back", "last track", "previous", "go to the last song"],
            "stop": ["stop", "stop playing", "stop the music", "cut the audio"],
        }
        verb_phrase = random.choice(vmap_variants[action])
        structures = [
            f"{verb_phrase} on {dev_word}", f"{verb_phrase} on the {dev_word}",
            verb_phrase, f"{dev_word} {verb_phrase}",
            f"can you {verb_phrase}", f"{verb_phrase} for me",
        ]
        st = random.choice(structures)

    raw_text = humanize_text(st, lang)
    
    slots = make_slots(device=media_type)
    
    return emit_command("media", action, "default", None, slots, raw_text)


def gen_meta_command_negative() -> Example:
    """
    Generate command-like utterances that explicitly say not to execute.
    These are the hard boundary cases where quoted, canceled, or discussed
    commands should remain transcripts.
    """
    lang = "zh" if random.random() < 0.55 else "en"

    if lang == "zh":
        command_like = random.choice([
            "暫停電視", "把電視暫停", "停止電視", "把電視停掉",
            "開燈", "把燈打開", "關燈", "把燈關掉",
            "開窗簾", "把窗簾打開", "關窗簾", "把窗簾關上",
            "設兩秒計時器", "設定計時器", "調低電視音量",
        ])
        templates = [
            f"我說「{command_like}」只是在舉例，不是要你操作",
            f"{command_like}那句只是示範說法，別真的執行",
            f"剛才{command_like}那句取消，請忽略",
            f"我是在說{command_like}這件事，不是在下命令",
            f"{command_like}這句不要當真，不是控制命令",
            f"我只是念到「{command_like}」，不是叫你做",
            f"我剛剛講{command_like}是口誤，不要動設備",
            f"如果我說{command_like}，那也只是例子",
            f"不是要你{command_like}，我只是聊天",
            f"先別動，我還沒要你{command_like}",
        ]
    else:
        command_like = random.choice([
            "pause the TV", "stop the TV", "turn on the lights",
            "turn off the lights", "open the curtains", "close the curtains",
            "set a two second timer", "turn the TV volume down",
        ])
        templates = [
            f"I said \"{command_like}\" as an example, not as a command",
            f"The phrase \"{command_like}\" was just something I was quoting",
            f"Cancel the part where I said {command_like}; do not execute it",
            f"When I said {command_like}, I was explaining the wording",
            f"Do not treat {command_like} as a device instruction",
            f"I only read out \"{command_like}\" from the text",
            f"I mentioned {command_like}, but I am not asking for anything",
            f"If I say {command_like}, that is only an example",
            f"I am not asking you to {command_like}; I am just talking",
            f"Hold on, I am not telling you to {command_like}",
        ]

    raw_text = inject_punctuation_variation(
        random.choice(templates),
        lang,
        prob=0.35,
    )
    return emit_transcript("unknown", "none", None, None, make_slots(), raw_text)


def gen_contrastive_direct_command() -> Example:
    """Generate direct commands that are close to the meta-command negatives."""
    lang = "zh" if random.random() < 0.5 else "en"

    if lang == "zh":
        examples = [
            ("media", "pause", "default", None, make_slots(device="tv"), ["暫停電視", "把電視暫停", "電視先暫停"]),
            ("media", "stop", "default", None, make_slots(device="tv"), ["停止電視播放", "把電視停掉", "電視先不要播"]),
            ("media", "set_volume", "default", None, make_slots(device="tv", mode="volume"), ["把電視音量調小", "電視聲音小一點"]),
            ("lights", "turn_on", "default", "on", make_slots(device="light"), ["開燈", "把燈打開", "幫我開燈"]),
            ("lights", "turn_off", "default", "off", make_slots(device="light"), ["關燈", "把燈關掉", "幫我關燈"]),
            ("curtain", "open", "default", None, make_slots(device="curtain"), ["開窗簾", "把窗簾打開", "窗簾拉開"]),
            ("curtain", "close", "default", None, make_slots(device="curtain"), ["關窗簾", "把窗簾關上", "窗簾拉上"]),
            ("timer", "set_time", "default", None, make_slots(device="timer", value="2", unit="seconds"), ["設兩秒計時器", "設定兩秒倒數"]),
        ]
    else:
        examples = [
            ("media", "pause", "default", None, make_slots(device="tv"), ["pause the TV", "please pause the TV"]),
            ("media", "stop", "default", None, make_slots(device="tv"), ["stop the TV", "stop TV playback"]),
            ("media", "set_volume", "default", None, make_slots(device="tv", mode="volume"), ["turn the TV volume down", "make the TV quieter"]),
            ("lights", "turn_on", "default", "on", make_slots(device="light"), ["turn on the lights", "please turn the lights on"]),
            ("lights", "turn_off", "default", "off", make_slots(device="light"), ["turn off the lights", "please turn the lights off"]),
            ("curtain", "open", "default", None, make_slots(device="curtain"), ["open the curtains", "please open the curtains"]),
            ("curtain", "close", "default", None, make_slots(device="curtain"), ["close the curtains", "please close the curtains"]),
            ("timer", "set_time", "default", None, make_slots(device="timer", value="2", unit="seconds"), ["set a two second timer", "start a two second timer"]),
        ]

    domain, action, target, state, slots, texts = random.choice(examples)
    raw_text = inject_punctuation_variation(
        random.choice(texts),
        lang,
        prob=0.25,
    )
    return emit_command(domain, action, target, state, slots, raw_text)


def gen_hard_negative() -> Example:
    """Generate hard negatives that mentions devices but NOT commands."""
    lang = "zh" if random.random() < 0.5 else "en"
    
    dev_type = random.choice(["light", "ac", "tv", "vacuum", "fan", "curtain", "speaker"])
    dev_word = get_granular_device(dev_type, lang)
    room = random.choice(ROOMS)
    room_word = pick_room_word(room, lang)
    person_word = random.choice(PERSON_NAMES_ZH if lang == "zh" else PERSON_NAMES_EN)
    
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
            f"{person_word}說他忘記關{dev_word}了",
            f"{person_word}叫我去關{dev_word}",
            f"{person_word}說{dev_word}壞了",
            f"{person_word}把{dev_word}打開了",
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
            f"{person_word} forgot to turn off the {dev_word}",
            f"{person_word} told me to turn off the {dev_word}",
            f"{person_word} said the {dev_word} is broken",
            f"{person_word} turned on the {dev_word}",
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
        
    text = humanize_text(random.choice(templates), lang, noise_prob=DEFAULT_NEGATIVE_NOISE_PROB)
    
    return Example(
        type="transcript",
        domain="unknown",
        action="none",
        target=None,
        state=None,
        slots=make_slots(),
        raw_text=text,
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
        
        # Statements & Observations
        statements = [
            "今天天氣真好", "下雨了",
            "我等等要出門", "我回來了", "我出門了", "我在忙", "我在睡覺",
            "股市今天跌了", "塞車塞好久", "好累喔", "肚子好餓",
            "今天上班好忙", "作業好多", "考試考完了", "放假了",
        ]
        
        # Requests (non-smart home)
        requests = [
            "告訴我一個笑話", "幫我叫計程車", "幫我訂餐廳", "幫我查路線",
            "幫我翻譯這個", "幫我算一下", "幫我記住這個", "幫我整理重點",
            "幫我查股價", "幫我草擬一封信", "說個故事", "幫我摘要這篇文章",
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
            "Draft an email", "Summarize this article", "Help me write a message",
            "Tell me a story", "What's in the news", "Look up this recipe",
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
    raw_text = humanize_text(text, lang, noise_prob=DEFAULT_TRANSCRIPT_NOISE_PROB)
    return emit_transcript("unknown", "none", None, None, make_slots(), raw_text)


def gen_abandoned_correction() -> Example:
    """
    Generate examples where user starts a command but abandons/corrects to nothing.
    These should be labeled as 'transcript' not 'command'.
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
    )


def gen_ambiguous_short_phrase() -> Example:
    lang = "zh" if random.random() < 0.5 else "en"
    
    if lang == "zh":
        # Directional / Relative
        directional = [
            "下一個", "上一個", "前一個", "後一個",
            "左邊", "右邊", "上面", "下面", "這邊", "那邊",
        ]
        
        # Quantity / Intensity
        quantity = [
            "多一點", "少一點", "再多一點", "再少一點", "一半",
            "全部", "一點點", "很多", "太多", "太少", "剛好",
        ]
        
        # Speed / Volume / Brightness (without device)
        adjustments = [
            "快一點", "慢一點",
            "高一點", "低一點", "強一點", "弱一點",
            "大一點", "小一點", "長一點", "短一點",
        ]
        
        # Action words without context - AVOID playback command conflicts
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
        # Directional / Relative
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
        
        # Adjustments without device
        adjustments = [
            "Faster", "Slower",
            "Higher", "Lower", "Stronger", "Weaker", 
            "Bigger", "Smaller", "Longer", "Shorter",
        ]
        
        # Action words without context
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
    )

# Generate

def compute_text_hash(text: str) -> str:
    normalized = " ".join(text.strip().lower().split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()

def mutate_example(ex: Example, attempts: int) -> Example:
    lang = "zh" if any(ord(c) > 128 for c in ex.raw_text) else "en"

    if attempts >= 3:
        ex.raw_text = inject_discourse_variation(ex.raw_text, lang, prob=0.90)
        ex.raw_text = inject_semantic_context(ex.raw_text, lang, prob=0.90)
    if attempts >= 4:
        ex.raw_text = inject_micro_rephrase(ex.raw_text, lang, prob=0.95)
        ex.raw_text = inject_punctuation_variation(ex.raw_text, lang, prob=0.95)
    
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
    (gen_lights, 0.095),
    (gen_climate, 0.095),
    (gen_vacuum, 0.095),
    (gen_timer, 0.095),
    (gen_curtain, 0.095),
    (gen_fan, 0.095),
    (gen_media, 0.095),
    (gen_hard_negative, 0.10),
    (gen_transcript, 0.09),
    (gen_abandoned_correction, 0.04),
    (gen_ambiguous_short_phrase, 0.025),
    (gen_meta_command_negative, 0.06),
    (gen_contrastive_direct_command, 0.04),
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


def print_distribution(
    title: str,
    counts: Dict[str, int],
    total: int,
    top_n: Optional[int] = None,
) -> None:
    """Pretty-print a count distribution with percentages."""
    if not counts or total <= 0:
        return

    print(f"\n{title}:")
    items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    if top_n is not None:
        items = items[:top_n]

    for key, count in items:
        print(f"  {key}: {count} ({count / total:.1%})")


def summarize_dataset(data: List[Example]) -> None:
    """
    Report high-level dataset stats without conflating transcripts,
    global-only commands, and room-specific commands.
    """
    type_counts = Counter()
    domain_counts = Counter()
    overall_target_counts = Counter()
    command_target_counts = Counter()
    room_command_target_counts = Counter()
    command_domain_target_counts = defaultdict(Counter)

    for ex in data:
        type_counts[ex.type] += 1
        domain_counts[ex.domain] += 1

        overall_target = ex.target if ex.target is not None else "None"
        overall_target_counts[overall_target] += 1

        if ex.type == "command":
            command_target = ex.target if ex.target is not None else "None"
            command_target_counts[command_target] += 1
            command_domain_target_counts[ex.domain][command_target] += 1

            if command_target not in {"default", "None"}:
                room_command_target_counts[command_target] += 1

    total_examples = len(data)
    total_commands = type_counts.get("command", 0)

    print(f"\nType distribution: {dict(type_counts)}")
    print_distribution("Domain distribution", dict(domain_counts), total_examples)
    print_distribution("Overall target distribution (top 10)", dict(overall_target_counts), total_examples, top_n=10)

    if total_commands:
        print_distribution("Command target distribution", dict(command_target_counts), total_commands)

        if room_command_target_counts:
            print_distribution(
                "Room-specific command target distribution",
                dict(room_command_target_counts),
                sum(room_command_target_counts.values()),
            )

        print("\nCommand default share by domain:")
        for domain in sorted(command_domain_target_counts.keys()):
            domain_target_counts = command_domain_target_counts[domain]
            domain_total = sum(domain_target_counts.values())
            default_count = domain_target_counts.get("default", 0)
            print(f"  {domain}: {default_count}/{domain_total} ({default_count / domain_total:.1%})")


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

    print(f"\nDone! Saved to {args.out}")
    summarize_dataset(data)


if __name__ == "__main__":
    main()
