import json
from pathlib import Path
from llama_cpp import Llama, LlamaGrammar

SYSTEM_PROMPT = """You are a smart home intent parser. Translate the user's input into a structured JSON command with no markdown and no explanations.

Rules:
1. If no specific room is mentioned, set "target" to "default".
2. Infer "slots.device" when the intent implies one (for example: channel -> tv, temperature/cooling/heating -> thermostat). Use null only when genuinely ambiguous.
3. If the input is NOT a direct command, set "type" to "transcript", "domain" to "unknown", and "action" to "none".
4. Always include all fields in the JSON, using null for any unspecified values.
"""

def build_prompt(user_text: str) -> str:
    return (
        "<start_of_turn>system\n" + SYSTEM_PROMPT + "<end_of_turn>\n"
        "<start_of_turn>user\n" + user_text + "<end_of_turn>\n"
        "<start_of_turn>model\n"
    )

STOP_TOKENS = ["\n\n", "\nUser:"]

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "llm" / "smarthome-json-mega-v4.1-bf16.gguf"
GRAMMAR_PATH = ROOT / "smart_home_grammar.gbnf"

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

_grammar = None
if GRAMMAR_PATH.exists():
    _grammar = LlamaGrammar.from_file(str(GRAMMAR_PATH))

def parse_command_llm(text: str) -> dict:
    prompt = build_prompt(text)

    out = _llm(
        prompt,
        max_tokens=192,
        temperature=0.0,
        stop=STOP_TOKENS,
        grammar=_grammar,
    )
    s = out["choices"][0]["text"].strip()
    obj = json.loads(s)
    obj["raw_text"] = text  # attach input text to output for convenience
    if obj.get("type") not in ("command", "transcript"):
        raise ValueError("Bad JSON: type")
    return obj
