import json
import os
from pathlib import Path

os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")

from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

from smart_home_schema import SYSTEM_PROMPT


ROOT = Path(__file__).resolve().parent
MODEL_PATH = os.getenv(
    "STT_LLM_MODEL",
    str(ROOT / "private" / "finetune" / "artifacts" / "qwen35_08b_base_full_sft"),
)
MAX_MODEL_LEN = int(os.getenv("STT_LLM_MAX_MODEL_LEN", "512"))
MAX_NEW_TOKENS = int(os.getenv("STT_LLM_MAX_NEW_TOKENS", "128"))
GPU_MEMORY_UTILIZATION = float(os.getenv("STT_LLM_GPU_MEMORY_UTILIZATION", "0.28"))
MAX_NUM_SEQS = int(os.getenv("STT_LLM_MAX_NUM_SEQS", "1"))
MAX_NUM_BATCHED_TOKENS = int(os.getenv("STT_LLM_MAX_NUM_BATCHED_TOKENS", "512"))
DTYPE = os.getenv("STT_LLM_DTYPE", "auto")
ENFORCE_EAGER = os.getenv("STT_LLM_ENFORCE_EAGER", "0") == "1"

STOP_TOKENS = ["<|im_end|>"]


def build_prompt(user_text: str) -> str:
    return (
        "<|im_start|>system\n" + SYSTEM_PROMPT + "<|im_end|>\n"
        "<|im_start|>user\n" + user_text + "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def patch_qwen35_vllm(model: str) -> dict | None:
    model_path = Path(model)
    config_path = model_path / "config.json"
    model_config = json.loads(config_path.read_text()) if config_path.exists() else {}
    markers = [
        model,
        " ".join(model_config.get("architectures") or []),
        str(model_config.get("model_type") or ""),
        str((model_config.get("text_config") or {}).get("model_type") or ""),
    ]
    is_qwen35 = any(
        "qwen3.5" in marker.lower() or "qwen35" in marker.lower() or "qwen3_5" in marker.lower()
        for marker in markers
    )
    if not is_qwen35:
        return None

    from vllm.model_executor.models import qwen3_5
    from vllm.model_executor.models.registry import ModelRegistry

    def get_text_only_mrope_positions(self, input_tokens, mm_features):
        if mm_features:
            raise ValueError("Text-only Qwen3.5 parser does not support multimodal inputs.")
        import torch

        positions = torch.arange(len(input_tokens), dtype=torch.long)
        return positions.unsqueeze(0).expand(3, -1), 0

    for cls in (qwen3_5.Qwen3_5ForCausalLMBase, qwen3_5.Qwen3_5ForCausalLM):
        cls.is_hybrid = True
        cls.supports_mrope = True
        cls.get_mrope_input_positions = get_text_only_mrope_positions
        cls.get_mamba_state_dtype_from_config = classmethod(
            qwen3_5.Qwen3_5ForConditionalGeneration.get_mamba_state_dtype_from_config.__func__
        )
        cls.get_mamba_state_shape_from_config = classmethod(
            qwen3_5.Qwen3_5ForConditionalGeneration.get_mamba_state_shape_from_config.__func__
        )
        cls.get_mamba_state_copy_func = classmethod(
            qwen3_5.Qwen3_5ForConditionalGeneration.get_mamba_state_copy_func.__func__
        )

    original_load_weights = qwen3_5.Qwen3_5ForCausalLMBase.load_weights

    def load_weights_with_prefix_fix(self, weights):
        def remap_weights():
            for name, tensor in weights:
                if name.startswith("model.visual.") or name.startswith("visual."):
                    continue
                if name.startswith("model.language_model."):
                    name = "model." + name[len("model.language_model."):]
                yield name, tensor

        return original_load_weights(self, remap_weights())

    qwen3_5.Qwen3_5ForCausalLMBase.load_weights = load_weights_with_prefix_fix
    ModelRegistry.register_model("Qwen3_5ForCausalLM", qwen3_5.Qwen3_5ForCausalLM)
    ModelRegistry.register_model("Qwen3_5MoeForCausalLM", qwen3_5.Qwen3_5MoeForCausalLM)
    return {"architectures": ["Qwen3_5ForCausalLM"]}


_tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
_stop_token_ids = [token_id for token_id in (_tokenizer.convert_tokens_to_ids(token) for token in STOP_TOKENS) if token_id]
if _tokenizer.eos_token_id not in _stop_token_ids:
    _stop_token_ids.append(_tokenizer.eos_token_id)

_hf_overrides = patch_qwen35_vllm(MODEL_PATH)

_llm_kwargs = {
    "model": MODEL_PATH,
    "tokenizer": MODEL_PATH,
    "trust_remote_code": True,
    "dtype": DTYPE,
    "gpu_memory_utilization": GPU_MEMORY_UTILIZATION,
    "max_model_len": MAX_MODEL_LEN,
    "max_num_seqs": MAX_NUM_SEQS,
    "max_num_batched_tokens": MAX_NUM_BATCHED_TOKENS,
    "enforce_eager": ENFORCE_EAGER,
    "language_model_only": True,
    "skip_mm_profiling": True,
    "disable_log_stats": True,
    "enable_prefix_caching": True,
}
if _hf_overrides:
    _llm_kwargs["hf_overrides"] = _hf_overrides

_llm = LLM(**_llm_kwargs)
_sampling_params = SamplingParams(
    temperature=0.0,
    top_p=1.0,
    max_tokens=MAX_NEW_TOKENS,
    stop=STOP_TOKENS,
    stop_token_ids=_stop_token_ids,
)


def parse_command_llm(text: str) -> dict:
    output = _llm.generate([build_prompt(text)], _sampling_params, use_tqdm=False)[0]
    s = output.outputs[0].text
    for stop in STOP_TOKENS:
        s = s.split(stop)[0]
    obj = json.loads(s.strip())
    obj["raw_text"] = text
    return obj
