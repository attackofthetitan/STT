import argparse
import json
import os
import random
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path


os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")

from safetensors import safe_open
from tqdm import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

from generate_smart_home_dataset import generate
from smart_home_schema import SYSTEM_PROMPT, command_payload, normalize_slots

STOP_TOKENS = ["<|im_end|>"]
DEFAULT_MODEL = str(
    Path(__file__).parent
    / "private"
    / "finetune"
    / "artifacts"
    / "qwen35_08b_base_full_sft"
)
DEFAULT_SAMPLES_PER_SOURCE = 1000
DEFAULT_MAX_MODEL_LEN = 320
DEFAULT_MAX_NEW_TOKENS = 64
DEFAULT_BATCH_SIZE = 128
DEFAULT_MAX_NUM_SEQS = 128
DEFAULT_MAX_NUM_BATCHED_TOKENS = 8192
DEFAULT_GPU_MEMORY_UTILIZATION = 0.85
OOD_HARDCODED_DATASET = Path(__file__).with_name("ood_bench.jsonl")
SOURCE_KEY = "_eval_source"


def sample_jsonl(path: Path, sample_count: int) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return random.sample(rows, sample_count)


def has_language_model_weight_prefix(model_path: Path) -> bool:
    for path in sorted(model_path.glob("*.safetensors")):
        with safe_open(path, framework="pt", device="cpu") as f:
            return any(name.startswith("model.language_model.") for name in f.keys())
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smart home intent parser benchmark using vLLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: 1000 generated + 1000 OOD samples
  python benchmark.py

  # Benchmark only the hardcoded OOD set
  python benchmark.py --eval-set ood

  # Benchmark a LoRA adapter
  python benchmark.py --model Qwen/Qwen3.5-2B-Base --lora private/finetune/artifacts/qwen35_2b_base_lora_sft

  # Benchmark a prebuilt JSONL dataset
  python benchmark.py --dataset smart_home_ood_test.jsonl --samples 500
        """,
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="HF model ID or local model directory")
    parser.add_argument("--lora", help="Path to a LoRA adapter to apply with vLLM")
    parser.add_argument("--max-lora-rank", type=int, default=64, help="Maximum LoRA rank for vLLM")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Number of prompts to submit per vLLM call")
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES_PER_SOURCE, help="Number of samples per eval source")
    parser.add_argument(
        "--eval-set",
        choices=["generated", "in_domain", "ood", "both"],
        default="both",
        help="'both' uses --samples generated and --samples OOD",
    )
    parser.add_argument("--dataset", help="Path to JSONL eval dataset; overrides --eval-set")
    parser.add_argument("--output", default="failures.json", help="Output file for failures")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS, help="Maximum generated tokens per sample")
    parser.add_argument("--max-model-len", type=int, default=DEFAULT_MAX_MODEL_LEN, help="vLLM max model length")
    parser.add_argument("--max-num-seqs", type=int, default=DEFAULT_MAX_NUM_SEQS, help="vLLM max number of concurrent sequences")
    parser.add_argument(
        "--max-num-batched-tokens",
        type=int,
        default=DEFAULT_MAX_NUM_BATCHED_TOKENS,
        help="vLLM scheduler token budget per batch",
    )
    parser.add_argument("--tensor-parallel-size", type=int, default=1, help="vLLM tensor parallel size")
    parser.add_argument(
        "--gpu-memory-utilization",
        type=float,
        default=DEFAULT_GPU_MEMORY_UTILIZATION,
        help="vLLM GPU memory utilization",
    )
    parser.add_argument("--dtype", default="auto", help="vLLM dtype, e.g. auto, bfloat16, float16")
    parser.add_argument("--quantization", help="vLLM weight quantization method, e.g. fp8")
    parser.add_argument("--kv-cache-dtype", help="vLLM KV cache dtype, e.g. auto, fp8, turboquant_3bit_nc")
    parser.add_argument("--enforce-eager", action="store_true", help="Disable vLLM CUDA graphs")
    parser.add_argument(
        "--speculative-config-json",
        help="JSON object passed through to vLLM speculative_config, e.g. '{\"method\":\"ngram\",\"num_speculative_tokens\":4,\"prompt_lookup_max\":4}'",
    )
    args = parser.parse_args()

    speculative_config = None
    if args.speculative_config_json:
        try:
            speculative_config = json.loads(args.speculative_config_json)
        except json.JSONDecodeError as exc:
            parser.error(f"--speculative-config-json must be valid JSON: {exc}")
        if not isinstance(speculative_config, dict):
            parser.error("--speculative-config-json must decode to a JSON object")

    random.seed(args.seed)

    rows = []
    if args.dataset:
        print(f"INFO: Loading {args.samples} test samples from dataset: {args.dataset}")
        for row in sample_jsonl(Path(args.dataset), args.samples):
            row[SOURCE_KEY] = "dataset"
            rows.append(row)
    elif args.eval_set == "ood":
        print(f"INFO: Loading {args.samples} OOD samples from fixed set: {OOD_HARDCODED_DATASET}")
        for row in sample_jsonl(OOD_HARDCODED_DATASET, args.samples):
            row[SOURCE_KEY] = "ood"
            rows.append(row)
    elif args.eval_set == "both":
        print(f"INFO: Generating {args.samples} in-domain test samples...")
        for item in generate(args.samples):
            row = item.copy() if isinstance(item, dict) else vars(item).copy()
            row[SOURCE_KEY] = "generated"
            rows.append(row)

        print(f"INFO: Loading {args.samples} OOD samples from fixed set: {OOD_HARDCODED_DATASET}")
        ood_rows = sample_jsonl(OOD_HARDCODED_DATASET, args.samples)
        for row in ood_rows:
            row[SOURCE_KEY] = "ood"
            rows.append(row)

        print(f"INFO: Combined eval set: {args.samples} generated + {len(ood_rows)} OOD = {len(rows)} total")
    else:
        print(f"INFO: Generating {args.samples} in-domain test samples...")
        for item in generate(args.samples):
            row = item.copy() if isinstance(item, dict) else vars(item).copy()
            row[SOURCE_KEY] = "generated"
            rows.append(row)

    tokenizer_source = args.lora or args.model
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, trust_remote_code=True)
    stop_token_ids = [tokenizer.convert_tokens_to_ids(token) for token in STOP_TOKENS]
    if tokenizer.eos_token_id not in stop_token_ids:
        stop_token_ids.append(tokenizer.eos_token_id)
    print(f"INFO: vLLM stop token ids: {stop_token_ids}")

    model_path = Path(args.model)
    model_config = json.loads((model_path / "config.json").read_text()) if (model_path / "config.json").exists() else {}
    model_markers = [
        str(args.model),
        " ".join(model_config.get("architectures") or []),
        str(model_config.get("model_type") or ""),
        str((model_config.get("text_config") or {}).get("model_type") or ""),
    ]
    is_qwen35 = any(
        "qwen3.5" in marker.lower() or "qwen35" in marker.lower() or "qwen3_5" in marker.lower()
        for marker in model_markers
    )
    if is_qwen35:
        from vllm.model_executor.models import qwen3_5
        from vllm.model_executor.models.registry import ModelRegistry

        def get_text_only_mrope_positions(self, input_tokens, mm_features):
            if mm_features:
                raise ValueError("Text-only Qwen3.5 benchmark does not support multimodal inputs.")
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

        if model_path.is_dir() and has_language_model_weight_prefix(model_path):
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
            print("INFO: Patched vLLM weight loading for multimodal-prefixed Qwen3.5 weights")
        ModelRegistry.register_model("Qwen3_5ForCausalLM", qwen3_5.Qwen3_5ForCausalLM)
        ModelRegistry.register_model("Qwen3_5MoeForCausalLM", qwen3_5.Qwen3_5MoeForCausalLM)
        print("INFO: Patched vLLM registry for Qwen3.5 text-only checkpoints")

    sampling_params = SamplingParams(
        temperature=0.0,
        top_p=1.0,
        max_tokens=args.max_new_tokens,
        stop=STOP_TOKENS,
        stop_token_ids=stop_token_ids,
    )

    llm_kwargs = {
        "model": args.model,
        "tokenizer": tokenizer_source,
        "trust_remote_code": True,
        "dtype": args.dtype,
        "quantization": args.quantization,
        "tensor_parallel_size": args.tensor_parallel_size,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "enforce_eager": args.enforce_eager,
        "language_model_only": True,
        "skip_mm_profiling": True,
        "disable_log_stats": False,
        "enable_prefix_caching": True,
        "max_num_seqs": args.max_num_seqs,
        "max_num_batched_tokens": args.max_num_batched_tokens,
    }
    if args.kv_cache_dtype:
        llm_kwargs["kv_cache_dtype"] = args.kv_cache_dtype
    if speculative_config:
        llm_kwargs["speculative_config"] = speculative_config
    if args.max_model_len:
        llm_kwargs["max_model_len"] = args.max_model_len
    if is_qwen35:
        llm_kwargs["hf_overrides"] = {"architectures": ["Qwen3_5ForCausalLM"]}

    lora_request = None
    if args.lora:
        llm_kwargs["enable_lora"] = True
        llm_kwargs["max_lora_rank"] = args.max_lora_rank
        lora_request = LoRARequest("benchmark_adapter", 1, args.lora)

    print(f"INFO: Loading vLLM model: {args.model}")
    print("INFO: vLLM V1 multiprocessing: DISABLED")
    llm = LLM(**llm_kwargs)

    prompt_texts = [
        (
            "<|im_start|>system\n" + SYSTEM_PROMPT + "<|im_end|>\n"
            "<|im_start|>user\n" + row.get("raw_text", "") + "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        for row in rows
    ]
    print(f"INFO: Pre-tokenizing {len(prompt_texts)} prompts...")
    prompts = [
        {"prompt_token_ids": token_ids}
        for token_ids in tokenizer(prompt_texts, add_special_tokens=False)["input_ids"]
    ]

    metrics = Counter()
    source_metrics = defaultdict(Counter)
    failures = []
    latencies_ms = []
    total_completion_tokens = 0

    print("INFO: Starting inference...")
    start_total = time.perf_counter()
    progress = tqdm(total=len(rows), desc="Benchmark")

    for start in range(0, len(rows), args.batch_size):
        batch_rows = rows[start:start + args.batch_size]
        batch_prompts = prompts[start:start + args.batch_size]
        generate_kwargs = {"lora_request": lora_request} if lora_request else {}
        outputs = llm.generate(batch_prompts, sampling_params, use_tqdm=False, **generate_kwargs)

        for row, request_output in zip(batch_rows, outputs, strict=True):
            completion = request_output.outputs[0]
            pred_str = completion.text
            for stop in STOP_TOKENS:
                pred_str = pred_str.split(stop)[0]
            pred_str = pred_str.strip()

            source = row[SOURCE_KEY]
            metrics["total"] += 1
            source_metrics[source]["total"] += 1

            total_completion_tokens += len(completion.token_ids)
            request_metrics = request_output.metrics
            assert request_metrics is not None, "vLLM metrics are missing; disable_log_stats must be False."
            latencies_ms.append(
                (
                    request_metrics.first_token_latency
                    + request_metrics.last_token_ts
                    - request_metrics.first_token_ts
                ) * 1000.0
            )

            expected = command_payload(row)

            try:
                pred = json.loads(pred_str)
            except json.JSONDecodeError:
                failures.append({
                    "type": "invalid_json",
                    "source": source,
                    "input": row.get("raw_text", ""),
                    "got": pred_str,
                })
                progress.update(1)
                continue

            if not isinstance(pred, dict):
                pred = {}

            metrics["valid_json"] += 1
            source_metrics[source]["valid_json"] += 1

            pred_for_comparison = pred.copy()
            pred_for_comparison["slots"] = normalize_slots(pred.get("slots"))

            intent_ok = (
                pred.get("type") == expected["type"]
                and pred.get("domain") == expected["domain"]
                and pred.get("action") == expected["action"]
                and pred.get("target") == expected["target"]
            )

            if not intent_ok:
                failures.append({
                    "type": "intent_mismatch",
                    "source": source,
                    "input": row.get("raw_text", ""),
                    "expected": expected,
                    "got": pred_for_comparison,
                })
            else:
                metrics["intent_match"] += 1
                source_metrics[source]["intent_match"] += 1
                if pred_for_comparison == expected:
                    metrics["slot_match"] += 1
                    source_metrics[source]["slot_match"] += 1
                else:
                    failures.append({
                        "type": "slot_mismatch",
                        "source": source,
                        "input": row.get("raw_text", ""),
                        "expected": expected,
                        "got": pred_for_comparison,
                    })

            progress.update(1)

    progress.close()
    total_time_sec = time.perf_counter() - start_total
    total = metrics["total"]
    sorted_latencies = sorted(latencies_ms)
    p95_index = min(int(len(sorted_latencies) * 0.95), len(sorted_latencies) - 1)
    p99_index = min(int(len(sorted_latencies) * 0.99), len(sorted_latencies) - 1)

    print("\n" + "=" * 50)
    print("BENCHMARK RESULTS")
    print("=" * 50)

    print(f"\n{' ACCURACY ':-^50}")
    print(f"  Total Samples:   {total}")
    print(f"  Valid JSON:      {metrics['valid_json']} ({metrics['valid_json'] / total:.1%})")
    print(f"  Intent Accuracy: {metrics['intent_match']} ({metrics['intent_match'] / total:.1%})")
    print(f"  Slot Accuracy:   {metrics['slot_match']} ({metrics['slot_match'] / total:.1%})")

    print(f"\n{' BY SOURCE ':-^50}")
    for source, counts in sorted(source_metrics.items()):
        source_total = counts["total"]
        print(
            f"  {source:<12} "
            f"total={source_total:<5} "
            f"valid_json={counts['valid_json'] / source_total:>6.1%} "
            f"intent={counts['intent_match'] / source_total:>6.1%} "
            f"slot={counts['slot_match'] / source_total:>6.1%}"
        )

    print(f"\n{' THROUGHPUT ':-^50}")
    print(f"  Total Time:      {total_time_sec:.2f}s")
    print(f"  Requests/sec:    {total / total_time_sec:.2f}")
    print(f"  Tokens/sec:      {total_completion_tokens / total_time_sec:.1f}")
    print(f"  Total Tokens:    {total_completion_tokens}")

    print(f"\n{' LATENCY ':-^50}")
    print(f"  Average:         {statistics.mean(sorted_latencies):.1f} ms")
    print(f"  P50 (median):    {statistics.median(sorted_latencies):.1f} ms")
    print(f"  P95:             {sorted_latencies[p95_index]:.1f} ms")
    print(f"  P99:             {sorted_latencies[p99_index]:.1f} ms")
    print("=" * 50)

    if failures:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2, ensure_ascii=False)
        print(f"\nWARNING: {len(failures)} failures saved to '{args.output}'")

        print("   Breakdown:")
        for failure_type, count in Counter(failure["type"] for failure in failures).most_common():
            print(f"     - {failure_type}: {count}")

        print("   Breakdown by source:")
        for source, count in Counter(failure["source"] for failure in failures).most_common():
            print(f"     - {source}: {count}")

        print("\n   Top 3 Failures:")
        for failure in failures[:3]:
            print(f"   [{failure['type']}] Source: {failure['source']} | Input: {failure.get('input')}")
            if "expected" in failure:
                print(f"     Exp: {json.dumps(failure['expected'], ensure_ascii=False)}")
                print(f"     Got: {json.dumps(failure['got'], ensure_ascii=False)}")
            else:
                print(f"     Got: {failure.get('got')}")
            print()


if __name__ == "__main__":
    main()
