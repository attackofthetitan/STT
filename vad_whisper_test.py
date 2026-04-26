import os
import time
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Vendor CUDA DLLs
CUDNN_DIR  = ROOT / "vendor" / "cudnn" / "bin"
CUDBLAS_DIR   = ROOT / "vendor" / "cublas" / "bin"
os.environ["PATH"] = f"{CUDNN_DIR};{CUDBLAS_DIR};" + os.environ.get("PATH", "")

import numpy as np
import sounddevice as sd
import onnxruntime as ort
from asr_engine import QwenASR

# VAD settings
SAMPLE_RATE = 16000
FRAME_MS = 32
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)

END_SILENCE_MS = 300
END_SILENCE_FRAMES = max(1, END_SILENCE_MS // FRAME_MS)
PREPAD_MS = 100
PREPAD_FRAMES = max(1, PREPAD_MS // FRAME_MS)

MAX_SPEECH_SEC = 12
MIN_SPEECH_MS = 200

# Silero VAD threshold
VAD_THRESHOLD = 0.3

# ASR settings
ASR_MODEL = os.getenv("STT_ASR_MODEL", str(ROOT / "models" / "asr" / "qwen3-asr-0.6b"))
ASR_LANGUAGE = os.getenv("STT_ASR_LANGUAGE", "Traditional Chinese")
ASR_MAX_NEW_TOKENS = int(os.getenv("STT_ASR_MAX_NEW_TOKENS", "128"))
ASR_MAX_MODEL_LEN = int(os.getenv("STT_ASR_MAX_MODEL_LEN", "1024"))
ASR_GPU_MEMORY_UTILIZATION = float(os.getenv("STT_ASR_GPU_MEMORY_UTILIZATION", "0.28"))
ASR_ENFORCE_EAGER = os.getenv("STT_ASR_ENFORCE_EAGER", "0") == "1"

def now_ms() -> float:
    return time.perf_counter() * 1000.0

SILERO_ONNX = ROOT / "models" / "silero" / "silero_vad.onnx"

def load_silero_onnx_session():
    if not SILERO_ONNX.exists():
        raise FileNotFoundError(f"Missing Silero ONNX at: {SILERO_ONNX}")
    return ort.InferenceSession(str(SILERO_ONNX), providers=["CPUExecutionProvider"])

def silero_prob(sess, audio_f32: np.ndarray, state: np.ndarray):
    # audio_f32: (FRAME_SAMPLES,) float32, 16kHz
    x = audio_f32.reshape(1, -1).astype(np.float32)
    sr = np.array([SAMPLE_RATE], dtype=np.int64)
    prob, state = sess.run(None, {"input": x, "sr": sr, "state": state})
    return float(np.squeeze(prob)), state

def main():
    # Load Silero VAD
    vad_sess = load_silero_onnx_session()
    state = np.zeros((2, 1, 128), dtype=np.float32)

    asr = QwenASR(
        model_name=ASR_MODEL,
        language=ASR_LANGUAGE,
        max_new_tokens=ASR_MAX_NEW_TOKENS,
        max_model_len=ASR_MAX_MODEL_LEN,
        gpu_memory_utilization=ASR_GPU_MEMORY_UTILIZATION,
        enforce_eager=ASR_ENFORCE_EAGER,
    )
    asr.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), SAMPLE_RATE)

    from llm_parser import parse_command_llm

    print("Streaming... speak normally. Ctrl+C to stop.")
    print(f"VAD: frame={FRAME_MS}ms, end_silence={END_SILENCE_MS}ms, prepad={PREPAD_MS}ms, thr={VAD_THRESHOLD}")
    print(
        f"ASR: model={ASR_MODEL}, backend=vLLM, "
        f"gpu_memory_utilization={ASR_GPU_MEMORY_UTILIZATION}, language={ASR_LANGUAGE or 'auto'}"
    )

    prepad = []
    speech = []
    recording = False
    silence_run = 0
    speech_start_t = None

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=FRAME_SAMPLES,
    ) as stream:
        while True:
            frame, _ = stream.read(FRAME_SAMPLES)
            x = frame[:, 0].copy()

            prepad.append(x)
            if len(prepad) > PREPAD_FRAMES:
                prepad.pop(0)

            prob, state = silero_prob(vad_sess, x, state)
            is_speech = prob >= VAD_THRESHOLD

            if not recording:
                if is_speech:
                    recording = True
                    speech_start_t = time.perf_counter()
                    silence_run = 0
                    speech = list(prepad)
                    prepad = []
            else:
                speech.append(x)
                silence_run = 0 if is_speech else (silence_run + 1)

                too_long = (time.perf_counter() - speech_start_t) > MAX_SPEECH_SEC
                ended = silence_run >= END_SILENCE_FRAMES

                if ended or too_long:
                    recording = False

                    audio_f32 = np.concatenate(speech) if speech else np.zeros(0, dtype=np.float32)
                    speech = []
                    prepad = []
                    silence_run = 0
                    speech_start_t = None

                    dur_ms = (audio_f32.size / SAMPLE_RATE) * 1000.0
                    if dur_ms < MIN_SPEECH_MS:
                        continue

                    # --- ASR transcription ---
                    t_asr = now_ms()
                    text, language = asr.transcribe(audio_f32, SAMPLE_RATE)
                    dt_asr = now_ms() - t_asr

                    # Skip empty transcripts — no point sending to LLM
                    if not text:
                        continue

                    print(f"> [{language or 'unknown'}] ({dt_asr:.0f}ms) {text}")

                    # --- LLM intent parsing ---
                    t_llm = now_ms()
                    event = parse_command_llm(text)
                    dt_llm = now_ms() - t_llm

                    event["raw_transcript"] = text
                    print(f"  LLM: {dt_llm:.0f}ms | {json.dumps(event, ensure_ascii=False)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
