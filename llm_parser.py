import json
from pathlib import Path
from llama_cpp import Llama

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "llm" / "smarthome-json-v2.7-bf16.gguf"

SYSTEM = """You are a smart home command extraction engine. Analyze the user's natural language input and return EXACTLY ONE JSON object.

OUTPUT RULES
- JSON only. No markdown, no conversational text. First char "{", last "}".
- If the input is NOT a smart home command (chat, greetings, questions), set "type": "transcript" and "domain": "unknown".
- Use "null" for missing values.
- Double quotes for strings.
- raw_text = original user sentence.

LOGIC & NORMALIZATION
- Room Normalization: Map all room mentions to ["bathroom", "kitchen", "bedroom", "living_room", "dining_room", "study", "balcony", "hallway", "entryway", "default"].
- Default Target: If NO room is mentioned, set "target": "default".
- Implicit Intent: Phrases like "too dark" or "too hot" should be interpreted as commands (lights/climate) with lower confidence.

SCHEMA DEFINITION
{
  "type": "command" | "transcript",
  "domain": "lights" | "switches" | "climate" | "media" | "covers" | "locks" | "vacuum" | "timer" | "scene" | "query",
  "action": "turn_on" | "turn_off" | "set" | "open" | "close" | "lock" | "unlock" | "start" | "stop" | "increase" | "decrease" | "query",
  "target": "string" | "default" | null,
  "state": "on" | "off" | null,
  "slots": {
    "device": "string",
    "value": "string",
    "value_num": number,
    "unit": "string",
    "mode": "string",
    "scene": "string",
    "duration_sec": number
  },
  "raw_text": "string",
  "confidence": number
}
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
