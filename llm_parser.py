import json
from pathlib import Path
from llama_cpp import Llama

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "llm" / "smarthome-json-mega-v4.1-bf16.gguf"

SYSTEM = """You are a smart home intent parser. Translate the user's input into a structured JSON command with no markdown, no explanations, and no explanations.

Rules:
1. If no specific room is mentioned, set "target" to "default".
2. If the device is not explicitly named, set "slots.device" to null.
3. If the input is NOT a direct command, set "type" to "transcript", "domain" to "unknown", and "action" to "none".
4. Always include all fields in the JSON, using null for any unspecified values.
5. "raw_text" should exactly match the user's input.
"""
_llm = Llama(
    model_path=str(MODEL_PATH),
    n_ctx=512,
    n_gpu_layers=-1,
    verbose=False,
    flash_attn=True,
    n_batch=2048,
    n_ubatch=2048,
    top_p=0.95,
    top_k=64,
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
