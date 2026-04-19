import json
import time
import statistics
import argparse
import requests
from tqdm import tqdm
from pathlib import Path
from generate_smart_home_dataset import generate

SYSTEM_PROMPT = """You are a smart home intent parser. Translate the user's input into a structured JSON command with no markdown and no explanations.

Rules:
1. If no specific room is mentioned, set "target" to "default".
2. If the device is not explicitly named, set "slots.device" to null.
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

try:
    from llama_cpp import Llama, LlamaGrammar
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False


MODEL_PATH = "models/llm/smarthome-json-mega-v4.1-bf16.gguf"
TEST_SAMPLES = 500

SLOTS_TEMPLATE = {
    "device": None,
    "value": None,
    "value_num": None,
    "unit": None,
    "mode": None,
    "scene": None,
}

def row_to_target_json(row: dict) -> dict:
    slots = row.get("slots") or {}
    norm_slots = {**SLOTS_TEMPLATE, **slots}

    obj = {
        "type": row.get("type"),
        "domain": row.get("domain"),
        "action": row.get("action"),
        "target": row.get("target"),
        "state": row.get("state"),
        "slots": norm_slots,
    }

    return obj

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
                "value_num": {"type": ["number", "null"]},
                "unit": {
                    "type": ["string", "null"],
                    "enum": ["celsius", "percent", "seconds", "minutes", "hours", None]
                },
                "mode": {"type": ["string", "null"]},
                "scene": {"type": ["string", "null"]}
            }
        }
    },
    "required": ["type", "domain", "action", "target", "slots"]
}


# =============================================================================
# INFERENCE BACKENDS
# =============================================================================

class LocalLlamaBackend:
    """Local llama-cpp-python backend."""
    
    def __init__(self, model_path: str, use_grammar: bool = False):
        if not LLAMA_CPP_AVAILABLE:
            raise RuntimeError("llama-cpp-python not installed. Use --server instead.")
        
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
            max_tokens=256,
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
    
    def __init__(self, server_url: str, use_grammar: bool = False):
        self.server_url = server_url.rstrip("/")
        self.use_grammar = use_grammar
        
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
            "n_predict": 256,
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
    
    def __init__(self, server_url: str, api_key: str = None, use_grammar: bool = False):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.use_grammar = use_grammar
        
    def generate(self, prompt: str) -> tuple[str, int]:
        """Generate response using OpenAI-compatible /v1/completions endpoint."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "prompt": prompt,
            "max_tokens": 256,
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
        """
    )
    
    parser.add_argument("--model", default=MODEL_PATH, help="Path to GGUF model (for local mode)")
    parser.add_argument("--server", help="llama.cpp server URL (e.g., http://localhost:8080)")
    parser.add_argument("--api-key", help="API key for server authentication")
    parser.add_argument("--openai-compat", action="store_true", help="Use OpenAI-compatible /v1/completions endpoint")
    parser.add_argument("--grammar", action="store_true", help="Enable grammar constraints")
    parser.add_argument("--samples", type=int, default=TEST_SAMPLES, help="Number of test samples")
    parser.add_argument("--output", default="failures.json", help="Output file for failures")
    
    args = parser.parse_args()
    
    # Initialize backend
    if args.server:
        if args.openai_compat:
            print(f"🔹 Using OpenAI-compatible API: {args.server}")
            backend = OpenAICompatibleBackend(args.server, args.api_key, args.grammar)
        else:
            print(f"🔹 Using llama.cpp server: {args.server}")
            backend = LlamaServerBackend(args.server, args.grammar)
    else:
        print(f"🔹 Loading Local Model: {args.model}")
        backend = LocalLlamaBackend(args.model, args.grammar)
    
    if args.grammar:
        print("🔹 Grammar constraints: ENABLED ✓")
    else:
        print("🔹 Grammar constraints: DISABLED")

    print(f"🔹 Generating {args.samples} test samples...")
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

    print("🔹 Starting Inference Loop...")
    start_total = time.perf_counter()
    
    for item in tqdm(raw_data):
        user_text = item.raw_text
        
        gt = row_to_target_json(item.__dict__)
        
        prompt = build_prompt(user_text)

        try:
            # Time individual request
            start_req = time.perf_counter()
            
            pred_str, tokens = backend.generate(prompt)
            
            # Record latency
            elapsed_ms = (time.perf_counter() - start_req) * 1000
            latencies_ms.append(elapsed_ms)
            total_completion_tokens += tokens
            
            pred = json.loads(pred_str)
            metrics["valid_json"] += 1
            
            def clean(obj):
                c = obj.copy()
                # Strip any extra fields the model might output
                for k in ("confidence", "raw_text"):
                    c.pop(k, None)
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
