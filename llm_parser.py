import json
from pathlib import Path
from llama_cpp import Llama

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "llm" / "smarthome-json-v2-bf16.gguf"

SYSTEM = """You are a smart home command extraction engine. You receive user sentences and infer the intent.

Return EXACTLY ONE JSON object and NOTHING ELSE.
- No questions. No refusals. No extra text.
- Output must start with "{" and end with "}".
- Use only keys in the schema.
- Use null for missing values.
- raw_text MUST equal the original user sentence.
- confidence is a number 0.0–1.0.

SCHEMA (output keys and allowed enums)
{
  "type": "command" | "transcript",
  "domain": "lights" | "climate" | "media" | "covers" | "switches" | "locks" | "vacuum" | "timer" | "scene" | "query" | "unknown",
  "action": "set" | "turn_on" | "turn_off" | "open" | "close" | "lock" | "unlock" | "start" | "stop" | "pause" | "resume" | "increase" | "decrease" | "query" | "none",
  "target": "bathroom" | "kitchen" | "bedroom" | "living_room" | "default" | null,
  "state": "on" | "off" | null,
  "slots": {
    "device": null,
    "value": null,
    "value_num": null,
    "unit": null,
    "mode": null,
    "scene": null,
    "duration_sec": null
  },
  "raw_text": "",
  "confidence": 0.0
}

ROOM NORMALIZATION
- bathroom: 廁所/浴室/洗手間/restroom/bathroom
- kitchen: 廚房/kitchen
- bedroom: 房間/臥室/主臥/我的房間/bedroom
- living_room: 客廳/大廳/living room
- If no room mentioned: target="default" for commands; target=null for transcripts.

TRANSCRIPT RULE
If not a smart-home command:
- type="transcript", domain="unknown", action="none", target=null, state=null, slots all null, confidence ≤ 0.35

DOMAIN→ACTION
- lights: turn_on/turn_off + state on/off, slots.device="light"
- switches: turn_on/turn_off + state on/off, slots.device in {fan,humidifier,diffuser,plug,air_purifier}
- covers: open/close OR set with slots.mode="position", slots.value_num 0..100, unit="percent"
- locks: lock/unlock, slots.device="front_door", state=null
- climate:
  - power: turn_on/turn_off + state on/off, slots.device="ac"
  - set temp: set, slots.device="thermostat", mode="setpoint", value_num=<temp>, unit="c"
  - delta temp: increase/decrease, slots.device="thermostat", value_num=<delta>, unit="c"
  - set mode: set, slots.device="ac", mode in {cool,heat,dry,fan_only}
- media:
  - TV power: turn_on/turn_off + state, slots.device="tv"
  - playback: pause/resume/stop, slots.device="music"
  - volume: increase/decrease, slots.device="volume", value_num=<steps>, unit="step"
  - source: set, slots.device="tv", mode="source", value=<HDMI1/HDMI2/YouTube/Netflix/...>
- vacuum: start/stop/pause/resume OR set dock/room via slots.mode and slots.value
- timer: set minutes (unit="min", duration_sec=minutes*60) OR stop(cancel) OR query(remaining)
- scene: set, slots.device="scene", slots.scene=<scene name>
- query: action="query", slots.device indicates what is queried, slots.mode indicates query type

AMBIGUITY
- Choose the most likely interpretation; lower confidence (0.55–0.74).

"""

_llm = Llama(
    model_path=str(MODEL_PATH),
    n_ctx=2048,
    n_gpu_layers=-1,
    verbose=False,
)

def parse_command_llm(text: str) -> dict:
    prompt = (
        "<start_of_turn>system\n" + SYSTEM + "<end_of_turn>\n"
        "<start_of_turn>user\n" + text + "<end_of_turn>\n"
        "<start_of_turn>model\n"
    )

    out = _llm(
        prompt,
        max_tokens=256,
        temperature=0.0,
        stop=["\n\n", "\nUser:"],
    )
    s = out["choices"][0]["text"].strip()
    obj = json.loads(s)
    obj.setdefault("raw_text", text)
    if obj.get("type") not in ("command", "transcript"):
        raise ValueError("Bad JSON: type")
    return obj
