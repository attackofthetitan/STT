import json


SYSTEM_PROMPT = """You are a smart home intent parser. Translate the user's input into a structured JSON command with no markdown and no explanations.

Rules:
1. If no specific room is mentioned, set "target" to "default".
2. Infer "slots.device" when the intent implies one (for example: channel -> tv, temperature/cooling/heating -> thermostat). Use null only when genuinely ambiguous.
3. If the input is NOT a direct command, set "type" to "transcript", "domain" to "unknown", and "action" to "none".
4. Always include all fields in the JSON, using null for any unspecified values.
"""

SLOTS_TEMPLATE = {
    "device": None,
    "value": None,
    "unit": None,
    "mode": None,
    "scene": None,
}

CHAT_EOS_TOKEN = "<|im_end|>"

CHAT_TEMPLATE = (
    "{% for message in messages %}"
    "{{'<|im_start|>' + message['role'] + '\\n'}}"
    "{% if message['role'] == 'assistant' %}"
    "{% generation %}{{ message['content'] + '<|im_end|>\\n' }}{% endgeneration %}"
    "{% else %}"
    "{{ message['content'] + '<|im_end|>\\n' }}"
    "{% endif %}"
    "{% endfor %}"
    "{% if add_generation_prompt %}"
    "{{ '<|im_start|>assistant\\n' }}"
    "{% endif %}"
)


def normalize_slots(slots: dict | None) -> dict:
    slots = slots or {}
    return {key: slots.get(key, default) for key, default in SLOTS_TEMPLATE.items()}


def command_payload(row: dict) -> dict:
    return {
        "type": row.get("type"),
        "domain": row.get("domain"),
        "action": row.get("action"),
        "target": row.get("target"),
        "state": row.get("state"),
        "slots": normalize_slots(row.get("slots")),
    }


def format_training_example(row: dict) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": row["raw_text"]},
            {
                "role": "assistant",
                "content": json.dumps(
                    command_payload(row),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
    }
