import json
import time
import statistics
import argparse
import random
import math
import requests
from tqdm import tqdm
from pathlib import Path
from types import SimpleNamespace
from generate_smart_home_dataset import generate

SYSTEM_PROMPT = """You are a smart home intent parser. Translate the user's input into a structured JSON command with no markdown and no explanations.

Rules:
1. If no specific room is mentioned, set "target" to "default".
2. Infer "slots.device" when the intent implies one (for example: channel -> tv, temperature/cooling/heating -> thermostat). Use null only when genuinely ambiguous.
3. If the input is NOT a direct command, set "type" to "transcript", "domain" to "unknown", and "action" to "none".
4. Always include all fields in the JSON, using null for any unspecified values.
"""

def build_prompt(user_text: str) -> str:
    return (
        "<|im_start|>system\n" + SYSTEM_PROMPT + "<|im_end|>\n"
        "<|im_start|>user\n" + user_text + "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )

STOP_TOKENS = ["<|im_end|>"]

try:
    from llama_cpp import Llama, LlamaGrammar
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


MODEL_PATH = "models/llm/smarthome-json-mega-v4.1-bf16.gguf"
TEST_SAMPLES = 500
OOD_HARDCODED_DATASET = Path(__file__).with_name("ood_hardcoded_100.jsonl")

SLOTS_TEMPLATE = {
    "device": None,
    "value": None,
    "unit": None,
    "mode": None,
    "scene": None,
}

ALLOWED_SLOT_KEYS = tuple(SLOTS_TEMPLATE.keys())


def normalize_slots(slots: dict) -> dict:
    """Normalize slots to canonical keys and drop legacy or extra keys."""
    slots = slots or {}
    return {k: slots.get(k, default) for k, default in SLOTS_TEMPLATE.items()}

def row_to_target_json(row: dict) -> dict:
    norm_slots = normalize_slots(row.get("slots"))

    obj = {
        "type": row.get("type"),
        "domain": row.get("domain"),
        "action": row.get("action"),
        "target": row.get("target"),
        "state": row.get("state"),
        "slots": norm_slots,
    }

    return obj


def row_from_item(item) -> dict:
    if isinstance(item, dict):
        return item
    if hasattr(item, "__dict__"):
        return item.__dict__
    raise TypeError(f"Unsupported sample type: {type(item)}")


def load_examples_from_jsonl(path: Path, sample_count: int, allow_repeat: bool = True) -> list:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    if not rows:
        raise ValueError(f"Dataset is empty: {path}")

    if sample_count <= len(rows):
        picked = random.sample(rows, sample_count)
    else:
        if allow_repeat:
            picked = rows.copy()
            while len(picked) < sample_count:
                picked.append(random.choice(rows))
        else:
            print(f"⚠️  Requested {sample_count} samples but dataset has only {len(rows)} unique rows. Using all rows.")
            picked = rows.copy()

    return [SimpleNamespace(**row) for row in picked]

STRICT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["command", "transcript"]
        },
        "domain": {
            "type": "string",
            "enum": [
                "lights", "climate", "vacuum", "timer", 
                "curtain", "fan", "media", "unknown"
            ]
        },
        "action": {
            "type": "string",
            "enum": [
                "turn_on", "turn_off", "set", "open", "close", 
                "start", "stop", "pause", "dock", "set_speed", 
                "set_volume", "set_time", "set_position",
                "channel_change", "play", "next", "previous", "none"
            ]
        },
        "target": {
            "type": ["string", "null"],
            "enum": [
                "bathroom", "kitchen", "bedroom", "living_room", 
                "dining_room", "study", "balcony", "hallway", 
                "entryway", "garage", "basement", "attic", 
                "laundry_room", "closet", "guest_room", "nursery", 
                "default", None
            ]
        },
        "state": {
            "type": ["string", "null"]
        },
        "slots": {
            "type": "object",
            "properties": {
                "device": {"type": ["string", "null"]},
                "value": {"type": ["string", "null"]},
                "unit": {
                    "type": ["string", "null"],
                    "enum": ["celsius", "percent", "seconds", "minutes", "hours", None]
                },
                "mode": {"type": ["string", "null"]},
                "scene": {"type": ["string", "null"]}
            },
            "required": list(ALLOWED_SLOT_KEYS),
            "additionalProperties": False,
        }
    },
    "required": ["type", "domain", "action", "target", "slots"],
    "additionalProperties": False,
}


# =============================================================================
# INFERENCE BACKENDS
# =============================================================================

class LocalLlamaBackend:
    """Local llama-cpp-python backend."""
    
    def __init__(self, model_path: str, use_grammar: bool = False, max_new_tokens: int = 256):
        if not LLAMA_CPP_AVAILABLE:
            raise RuntimeError("llama-cpp-python not installed. Use --server instead.")
        self.max_new_tokens = max_new_tokens
        
        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=1024,
            n_gpu_layers=-1,
            verbose=False,
            flash_attn=True,
            n_batch=2048,
            n_ubatch=2048,
        )
        
        self.grammar = None
        if use_grammar:
            self.grammar = LlamaGrammar.from_json_schema(json.dumps(STRICT_SCHEMA))
    
    def generate(self, prompt: str) -> tuple[str, int]:
        """Generate response. Returns (text, completion_tokens)."""
        output = self.llm(
            prompt,
            max_tokens=self.max_new_tokens,
            temperature=0.0,
            stop=STOP_TOKENS,
            grammar=self.grammar,
            echo=False,
            top_k=64,
            top_p=0.95,
        )
        
        text = output["choices"][0]["text"].strip()
        tokens = output["usage"]["completion_tokens"]
        return text, tokens


class LlamaServerBackend:
    """Remote llama.cpp server backend."""
    
    def __init__(self, server_url: str, use_grammar: bool = False, max_new_tokens: int = 256):
        self.server_url = server_url.rstrip("/")
        self.use_grammar = use_grammar
        self.max_new_tokens = max_new_tokens
        
        # Test connection
        try:
            resp = requests.get(f"{self.server_url}/health", timeout=5)
            if resp.status_code != 200:
                print(f"⚠️  Server health check returned {resp.status_code}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Cannot connect to server at {server_url}: {e}")
    
    def generate(self, prompt: str) -> tuple[str, int]:
        """Generate response. Returns (text, completion_tokens)."""
        payload = {
            "prompt": prompt,
            "n_predict": self.max_new_tokens,
            "temperature": 0.0,
            "stop": STOP_TOKENS,
        }
        
        if self.use_grammar:
            payload["json_schema"] = STRICT_SCHEMA
        
        try:
            resp = requests.post(
                f"{self.server_url}/completion",
                json=payload,
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            
            text = data.get("content", "").strip()
            tokens = data.get("tokens_predicted", len(text) // 4)
            return text, tokens
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Server request failed: {e}")


class OpenAICompatibleBackend:
    """OpenAI-compatible API backend (works with llama.cpp server --api-key)."""
    
    def __init__(self, server_url: str, api_key: str = None, use_grammar: bool = False, max_new_tokens: int = 256):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.use_grammar = use_grammar
        self.max_new_tokens = max_new_tokens
        
    def generate(self, prompt: str) -> tuple[str, int]:
        """Generate response using OpenAI-compatible /v1/completions endpoint."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "prompt": prompt,
            "max_tokens": self.max_new_tokens,
            "temperature": 0.0,
            "stop": STOP_TOKENS,
        }
        
        if self.use_grammar:
            payload["json_schema"] = STRICT_SCHEMA
        
        try:
            resp = requests.post(
                f"{self.server_url}/v1/completions",
                json=payload,
                headers=headers,
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            
            text = data["choices"][0]["text"].strip()
            tokens = data.get("usage", {}).get("completion_tokens", len(text) // 4)
            return text, tokens
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API request failed: {e}")


class HuggingFaceBackend:
    """Hugging Face Transformers backend."""
    
    def __init__(self, model_path: str, max_new_tokens: int = 128, compile_model: bool = False):
        if not TRANSFORMERS_AVAILABLE:
            raise RuntimeError("transformers or torch not installed. Please pip install torch transformers")

        self.max_new_tokens = max_new_tokens

        if torch.cuda.is_available():
            torch.set_float32_matmul_precision("high")
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.tokenizer.padding_side = "left"

        if self.tokenizer.pad_token_id is None and self.tokenizer.eos_token is not None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            torch_dtype="auto",
            trust_remote_code=True
        )
        self.model.eval()

        if compile_model and hasattr(torch, "compile"):
            try:
                self.model = torch.compile(self.model, mode="reduce-overhead", fullgraph=False)
                print("🔹 HF torch.compile: ENABLED")
            except Exception as e:
                print(f"⚠️  HF torch.compile unavailable ({e}); continuing without compile")

        self.stop_token_ids = []
        unk = self.tokenizer.unk_token_id
        for stop in STOP_TOKENS:
            stop_id = self.tokenizer.convert_tokens_to_ids(stop)
            if isinstance(stop_id, int) and stop_id >= 0 and stop_id != unk:
                self.stop_token_ids.append(stop_id)

        if self.tokenizer.eos_token_id is not None:
            self.stop_token_ids.append(self.tokenizer.eos_token_id)

        self.stop_token_ids = sorted(set(self.stop_token_ids))

    def _generate_outputs(self, inputs):
        eos_token_id = self.stop_token_ids if self.stop_token_ids else self.tokenizer.eos_token_id

        generate_kwargs = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": False,
            "use_cache": True,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": eos_token_id,
        }

        # Static KV cache can improve iterative decode throughput on many models.
        generate_kwargs["cache_implementation"] = "static"

        with torch.inference_mode():
            try:
                return self.model.generate(**inputs, **generate_kwargs)
            except Exception as e:
                # Some models/transformers versions do not support static cache with custom attention.
                if "cache_implementation" not in generate_kwargs:
                    raise

                generate_kwargs.pop("cache_implementation", None)
                try:
                    return self.model.generate(**inputs, **generate_kwargs)
                except Exception:
                    # Re-raise the original exception context for easier debugging.
                    raise e

    def generate_batch(self, prompts) -> list[tuple[str, int]]:
        """Generate responses for a prompt batch. Returns [(text, completion_tokens), ...]."""
        if not prompts:
            return []

        inputs = self.tokenizer(
            prompts,
            return_tensors="pt",
            add_special_tokens=False,
            padding=True,
            truncation=True,
        ).to(self.model.device)

        prompt_len = int(inputs["input_ids"].shape[1])
        outputs = self._generate_outputs(inputs)
        gen_tokens = outputs[:, prompt_len:]

        out = []
        for row in gen_tokens:
            if self.tokenizer.pad_token_id is not None:
                row = row[row != self.tokenizer.pad_token_id]

            text = self.tokenizer.decode(row, skip_special_tokens=False)
            for stop in STOP_TOKENS:
                if stop in text:
                    text = text.split(stop)[0]

            out.append((text.strip(), int(row.shape[0])))

        return out

    def generate(self, prompt: str) -> tuple[str, int]:
        """Generate response."""
        return self.generate_batch([prompt])[0]


# =============================================================================
# MAIN BENCHMARK
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Smart Home Intent Parser Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local model (default)
  python benchmark.py

        # Out-of-domain benchmark set (fixed 100 hardcoded cases)
    python benchmark.py --eval-set ood

    # Benchmark from prebuilt JSONL dataset
    python benchmark.py --dataset smart_home_ood_test.jsonl --samples 500
  
  # Local model with grammar
  python benchmark.py --grammar
  
  # Remote llama.cpp server
  python benchmark.py --server http://localhost:8080
  
  # Remote server with grammar
  python benchmark.py --server http://localhost:8080 --grammar
  
  # OpenAI-compatible API
  python benchmark.py --server http://localhost:8080 --openai-compat
  
  # Custom model path and samples
  python benchmark.py --model ./my-model.gguf --samples 1000
  
  # HuggingFace Backend
  python benchmark.py --hf --model ./qwen35_08b_base_full_sft
        """
    )
    
    parser.add_argument("--model", default=MODEL_PATH, help="Path to GGUF model or HF directory (for local mode)")
    parser.add_argument("--server", help="llama.cpp server URL (e.g., http://localhost:8080)")
    parser.add_argument("--api-key", help="API key for server authentication")
    parser.add_argument("--openai-compat", action="store_true", help="Use OpenAI-compatible /v1/completions endpoint")
    parser.add_argument("--grammar", action="store_true", help="Enable grammar constraints")
    parser.add_argument("--hf", action="store_true", help="Use local HuggingFace Transformers backend")
    parser.add_argument("--hf-compile", action="store_true", help="Enable torch.compile for HF backend (may increase startup time)")
    parser.add_argument("--hf-batch-size", type=int, default=1, help="HF batch size for throughput tuning (>=1)")
    parser.add_argument("--max-new-tokens", type=int, default=128, help="Maximum generated tokens per sample")
    parser.add_argument("--samples", type=int, default=TEST_SAMPLES, help="Number of test samples")
    parser.add_argument("--eval-set", choices=["in_domain", "ood"], default="in_domain", help="Sample source when --dataset is not provided")
    parser.add_argument("--dataset", help="Path to JSONL eval dataset (overrides --eval-set)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument("--output", default="failures.json", help="Output file for failures")
    
    args = parser.parse_args()

    if args.hf_batch_size < 1:
        parser.error("--hf-batch-size must be >= 1")
    
    # Initialize backend
    if args.server:
        if args.openai_compat:
            print(f"🔹 Using OpenAI-compatible API: {args.server}")
            backend = OpenAICompatibleBackend(args.server, args.api_key, args.grammar, args.max_new_tokens)
        else:
            print(f"🔹 Using llama.cpp server: {args.server}")
            backend = LlamaServerBackend(args.server, args.grammar, args.max_new_tokens)
    elif args.hf:
        print(f"🔹 Loading HuggingFace Model: {args.model}")
        backend = HuggingFaceBackend(args.model, max_new_tokens=args.max_new_tokens, compile_model=args.hf_compile)
    else:
        print(f"🔹 Loading Local llama.cpp Model: {args.model}")
        backend = LocalLlamaBackend(args.model, args.grammar, args.max_new_tokens)
    
    if args.grammar:
        print("🔹 Grammar constraints: ENABLED ✓")
    else:
        print("🔹 Grammar constraints: DISABLED")

    random.seed(args.seed)

    if args.dataset:
        dataset_path = Path(args.dataset)
        print(f"🔹 Loading {args.samples} test samples from dataset: {dataset_path}")
        raw_data = load_examples_from_jsonl(dataset_path, args.samples)
    elif args.eval_set == "ood":
        print(f"🔹 Loading out-of-domain samples from fixed hardcoded set: {OOD_HARDCODED_DATASET}")
        raw_data = load_examples_from_jsonl(OOD_HARDCODED_DATASET, args.samples, allow_repeat=False)
    else:
        print(f"🔹 Generating {args.samples} in-domain test samples...")
        raw_data = generate(args.samples)
    
    metrics = {
        "total": 0,
        "valid_json": 0,
        "intent_match": 0,
        "slot_match": 0,
    }
    
    # Throughput tracking
    latencies_ms = []
    total_completion_tokens = 0
    
    failures = []

    def process_prediction(user_text: str, gt: dict, pred_str: str, tokens: int, elapsed_ms: float) -> None:
        nonlocal total_completion_tokens
        latencies_ms.append(elapsed_ms)
        total_completion_tokens += tokens

        pred = json.loads(pred_str)
        metrics["valid_json"] += 1

        def clean(obj):
            c = obj.copy()
            # Strip any extra fields the model might output
            for k in ("confidence", "raw_text"):
                c.pop(k, None)
            c["slots"] = normalize_slots(c.get("slots"))
            return c

        pred_clean = clean(pred)
        gt_clean = clean(gt)

        intent_ok = (
            pred.get("type") == gt.get("type") and
            pred.get("domain") == gt.get("domain") and
            pred.get("action") == gt.get("action") and
            pred.get("target") == gt.get("target")
        )

        if intent_ok:
            metrics["intent_match"] += 1

            if json.dumps(pred_clean, sort_keys=True) == json.dumps(gt_clean, sort_keys=True):
                metrics["slot_match"] += 1
            else:
                failures.append({
                    "type": "slot_mismatch",
                    "input": user_text,
                    "expected": gt_clean,
                    "got": pred_clean
                })
        else:
            failures.append({
                "type": "intent_mismatch",
                "input": user_text,
                "expected": gt_clean,
                "got": pred_clean
            })

    print("🔹 Starting Inference Loop...")
    start_total = time.perf_counter()

    if args.hf and args.hf_batch_size > 1 and hasattr(backend, "generate_batch"):
        batch_size = args.hf_batch_size
        total_batches = math.ceil(len(raw_data) / batch_size)
        progress = tqdm(total=len(raw_data), desc=f"HF batched ({total_batches} batches)")

        for i in range(0, len(raw_data), batch_size):
            chunk = raw_data[i:i + batch_size]
            rows = [row_from_item(item) for item in chunk]
            user_texts = [row.get("raw_text", "") for row in rows]
            gts = [row_to_target_json(row) for row in rows]
            prompts = [build_prompt(text) for text in user_texts]

            try:
                start_req = time.perf_counter()
                batch_out = backend.generate_batch(prompts)
                elapsed_ms = (time.perf_counter() - start_req) * 1000
                per_item_ms = elapsed_ms / len(chunk)

                for user_text, gt, out in zip(user_texts, gts, batch_out):
                    pred_str, tokens = out
                    try:
                        process_prediction(user_text, gt, pred_str, tokens, per_item_ms)
                    except json.JSONDecodeError:
                        failures.append({"type": "invalid_json", "input": user_text, "got": pred_str})
                    except Exception as e:
                        print(f"Error processing '{user_text}': {e}")
                        latencies_ms.append(0)

                    metrics["total"] += 1
            except Exception as e:
                # If batch path fails, fall back to per-item processing for this chunk.
                print(f"Batch error (fallback to single): {e}")
                for user_text, gt, prompt in zip(user_texts, gts, prompts):
                    try:
                        start_req = time.perf_counter()
                        pred_str, tokens = backend.generate(prompt)
                        elapsed_ms = (time.perf_counter() - start_req) * 1000
                        process_prediction(user_text, gt, pred_str, tokens, elapsed_ms)
                    except json.JSONDecodeError:
                        failures.append({"type": "invalid_json", "input": user_text, "got": pred_str})
                    except Exception as item_e:
                        print(f"Error processing '{user_text}': {item_e}")
                        latencies_ms.append(0)

                    metrics["total"] += 1

            progress.update(len(chunk))

        progress.close()
    else:
        for item in tqdm(raw_data):
            row = row_from_item(item)
            user_text = row.get("raw_text", "")

            gt = row_to_target_json(row)
            prompt = build_prompt(user_text)

            try:
                # Time individual request
                start_req = time.perf_counter()
                pred_str, tokens = backend.generate(prompt)
                elapsed_ms = (time.perf_counter() - start_req) * 1000
                process_prediction(user_text, gt, pred_str, tokens, elapsed_ms)
            except json.JSONDecodeError:
                failures.append({"type": "invalid_json", "input": user_text, "got": pred_str})
            except Exception as e:
                print(f"Error processing '{user_text}': {e}")
                latencies_ms.append(0)  # Record failed request

            metrics["total"] += 1

    # Calculate total time
    total_time_sec = time.perf_counter() - start_total

    total = metrics["total"]
    if total == 0: total = 1

    # Calculate throughput metrics
    requests_per_sec = total / total_time_sec if total_time_sec > 0 else 0
    tokens_per_sec = total_completion_tokens / total_time_sec if total_time_sec > 0 else 0
    
    # Calculate latency percentiles (filter out zeros from errors)
    valid_latencies = [l for l in latencies_ms if l > 0]
    avg_latency = statistics.mean(valid_latencies) if valid_latencies else 0
    p50_latency = statistics.median(valid_latencies) if valid_latencies else 0
    
    sorted_latencies = sorted(valid_latencies)
    p95_idx = int(len(sorted_latencies) * 0.95)
    p99_idx = int(len(sorted_latencies) * 0.99)
    p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)] if sorted_latencies else 0
    p99_latency = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)] if sorted_latencies else 0

    print("\n" + "="*50)
    print("📊 BENCHMARK RESULTS")
    print("="*50)
    
    print(f"\n{'── ACCURACY ──':-^50}")
    print(f"  Total Samples:   {total}")
    print(f"  Valid JSON:      {metrics['valid_json']} ({metrics['valid_json']/total:.1%})")
    print(f"  Intent Accuracy: {metrics['intent_match']} ({metrics['intent_match']/total:.1%})")
    print(f"  Slot Accuracy:   {metrics['slot_match']} ({metrics['slot_match']/total:.1%})")
    
    print(f"\n{'── THROUGHPUT ──':-^50}")
    print(f"  Total Time:      {total_time_sec:.2f}s")
    print(f"  Requests/sec:    {requests_per_sec:.2f}")
    print(f"  Tokens/sec:      {tokens_per_sec:.1f}")
    print(f"  Total Tokens:    {total_completion_tokens}")
    
    print(f"\n{'── LATENCY ──':-^50}")
    print(f"  Average:         {avg_latency:.1f} ms")
    print(f"  P50 (median):    {p50_latency:.1f} ms")
    print(f"  P95:             {p95_latency:.1f} ms")
    print(f"  P99:             {p99_latency:.1f} ms")
    
    print("="*50)

    # Save failures
    if failures:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2, ensure_ascii=False)
        print(f"\n⚠️  {len(failures)} failures saved to '{args.output}'")
        
        # Count by type
        failure_types = {}
        for fail in failures:
            t = fail.get("type", "unknown")
            failure_types[t] = failure_types.get(t, 0) + 1
        print("   Breakdown:")
        for t, count in sorted(failure_types.items(), key=lambda x: -x[1]):
            print(f"     - {t}: {count}")
        
        # Print first 3 failures
        print("\n   Top 3 Failures:")
        for fail in failures[:3]:
            print(f"   [{fail['type']}] Input: {fail.get('input')}")
            if 'expected' in fail:
                print(f"     Exp: {json.dumps(fail['expected'], ensure_ascii=False)}")
                print(f"     Got: {json.dumps(fail['got'], ensure_ascii=False)}")
            else:
                print(f"     Got: {fail.get('got')}")
            print()

if __name__ == "__main__":
    main()
