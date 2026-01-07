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
from faster_whisper import WhisperModel
from llm_parser import parse_command_llm

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

# Whisper settings
MODEL_NAME = "medium"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"
LANGUAGE = None

CPU_THREADS = 4
NUM_WORKERS = 1

BEAM_SIZE = 5
BEST_OF = 1

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

def parse_command_llm_safe(text: str) -> dict:
    # Makes sure the LLM parsing does not raise exceptions
    for _ in range(2):
        try:
            return parse_command_llm(text)
        except Exception:
            pass
    return {
        "type": "transcript",
        "domain": "unknown",
        "action": "none",
        "target": None,
        "state": None,
        "slots": {
            "device": None,
            "value": None,
            "unit": None,
            "mode": None,
            "scene": None,
            "duration_sec": None
        },
        "raw_text": text,
        "confidence": 0.0,
    }


def main():
    # Load Silero VAD
    vad_sess = load_silero_onnx_session()
    state = np.zeros((2, 1, 128), dtype=np.float32)

    # Load Whisper
    whisper_dir = ROOT / "models" / "whisper" / MODEL_NAME
    if not whisper_dir.exists():
        raise FileNotFoundError(f"Missing Whisper model dir: {whisper_dir}")

    model = WhisperModel(
        str(whisper_dir),
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        cpu_threads=CPU_THREADS,
        num_workers=NUM_WORKERS,
    )

    # Warmup Whisper
    _ = list(model.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), vad_filter=False)[0])

    print("Streaming... speak normally. Ctrl+C to stop.")
    print(f"VAD: frame={FRAME_MS}ms, end_silence={END_SILENCE_MS}ms, prepad={PREPAD_MS}ms, thr={VAD_THRESHOLD}")
    print(f"Whisper: model={MODEL_NAME}, device={DEVICE}, compute={COMPUTE_TYPE}")

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

                    t0 = now_ms()
                    segments, info = model.transcribe(
                        audio_f32,
                        language=LANGUAGE,
                        vad_filter=True,
                        vad_parameters={"min_silence_duration_ms": END_SILENCE_MS, "speech_pad_ms": PREPAD_MS},
                        condition_on_previous_text=False,
                        beam_size=BEAM_SIZE,
                        best_of=BEST_OF,
                    )
                    dt = now_ms() - t0

                    text = " ".join(s.text.strip() for s in segments).strip()
                    if text:
                        print(f"> ({dt:.0f} ms) {text}  [{info.language} {info.language_probability:.2f}]")
                    
                    event = parse_command_llm_safe(text)
                    event["raw_transcript"] = text
                    print(json.dumps(event, ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")

