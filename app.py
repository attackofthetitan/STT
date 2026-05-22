import base64
import io
import json
import os
import secrets
import threading
import time
import uuid
import wave
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request

import numpy as np
from asr_engine import QwenASR


ROOT = Path(__file__).resolve().parent

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

CUDNN_DIR = ROOT / "vendor" / "cudnn" / "bin"
CUDBLAS_DIR = ROOT / "vendor" / "cublas" / "bin"
os.environ["PATH"] = f"{CUDNN_DIR};{CUDBLAS_DIR};" + os.environ.get("PATH", "")

ASR_MODEL = os.getenv("STT_ASR_MODEL", str(ROOT / "models" / "asr" / "qwen3-asr-0.6b"))
ASR_LANGUAGE = os.getenv("STT_ASR_LANGUAGE", "Traditional Chinese")
ASR_MAX_NEW_TOKENS = int(os.getenv("STT_ASR_MAX_NEW_TOKENS", "128"))
ASR_MAX_MODEL_LEN = int(os.getenv("STT_ASR_MAX_MODEL_LEN", "1536"))
ASR_GPU_MEMORY_UTILIZATION = float(os.getenv("STT_ASR_GPU_MEMORY_UTILIZATION", "0.28"))
ASR_ENFORCE_EAGER = os.getenv("STT_ASR_ENFORCE_EAGER", "0") == "1"
HA_WEBHOOK_URL = os.getenv("STT_HA_WEBHOOK_URL")
AUTH_TOKEN = os.getenv("STT_API_TOKEN") or secrets.token_urlsafe(32)

SAMPLE_RATE = 16000
FRAME_MS = 32
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
END_SILENCE_MS = 400
END_SILENCE_FRAMES = max(1, END_SILENCE_MS // FRAME_MS)
PREPAD_MS = 100
PREPAD_FRAMES = max(1, PREPAD_MS // FRAME_MS)
MAX_SPEECH_SEC = 12
MIN_SPEECH_MS = 350
VAD_THRESHOLD = 0.3
SILERO_ONNX = ROOT / "models" / "silero" / "silero_vad.onnx"
MAX_AUDIO_SESSIONS = int(os.getenv("STT_MAX_AUDIO_SESSIONS", "4"))
MAX_CHUNK_BYTES = int(os.getenv("STT_MAX_CHUNK_BYTES", str(SAMPLE_RATE * 2)))
MAX_TRANSCRIBE_BYTES = int(os.getenv("STT_MAX_TRANSCRIBE_BYTES", str(SAMPLE_RATE * 2 * 30)))
MAX_STOP_BYTES = 4096

RATE_LIMITS = {
    "/preload": (5, 60.0),
    "/audio/start": (10, 60.0),
    "/audio/chunk": (80, 10.0),
    "/audio/stop": (20, 60.0),
    "/transcribe": (10, 60.0),
}
DEFAULT_RATE_LIMIT = (30, 60.0)

asr = None
parse_command_llm = None
load_lock = threading.Lock()
vad_session = None
vad_lock = threading.Lock()
audio_sessions = {}
audio_sessions_lock = threading.Lock()
rate_limit_events = {}
rate_limit_lock = threading.Lock()


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def allow_request(client: str, path: str, now: float | None = None) -> tuple[bool, float]:
    limit, window = RATE_LIMITS.get(path, DEFAULT_RATE_LIMIT)
    now = now if now is not None else time.monotonic()
    key = (client, path)
    with rate_limit_lock:
        events = rate_limit_events.setdefault(key, deque())
        cutoff = now - window
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= limit:
            retry_after = max(1.0, window - (now - events[0]))
            return False, retry_after
        events.append(now)
    return True, 0.0


def pcm16_wav_data_url(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:audio/wav;base64,{encoded}"


def empty_transcript_payload() -> dict:
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
        },
        "raw_text": "",
        "raw_transcript": "",
    }


def forward_to_home_assistant(parsed: dict) -> bool:
    if not HA_WEBHOOK_URL or parsed.get("type") != "command":
        return False
    data = json.dumps(parsed, ensure_ascii=False).encode()
    req = request.Request(
        HA_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=5):
            return True
    except Exception as exc:
        print(f"home assistant webhook failed: {exc}", flush=True)
        return False


def load_models():
    global asr, parse_command_llm
    with load_lock:
        if asr is None:
            print("loading asr", flush=True)
            asr = QwenASR(
                model_name=ASR_MODEL,
                language=ASR_LANGUAGE,
                max_new_tokens=ASR_MAX_NEW_TOKENS,
                max_model_len=ASR_MAX_MODEL_LEN,
                gpu_memory_utilization=ASR_GPU_MEMORY_UTILIZATION,
                enforce_eager=ASR_ENFORCE_EAGER,
            )
        if parse_command_llm is None:
            print("loading parser", flush=True)
            from llm_parser import parse_command_llm as parser

            parse_command_llm = parser
        print("models loaded", flush=True)


def load_vad_session():
    global vad_session
    with vad_lock:
        if vad_session is None:
            if not SILERO_ONNX.exists():
                raise FileNotFoundError(f"Missing Silero ONNX at: {SILERO_ONNX}")
            import onnxruntime as ort

            vad_session = ort.InferenceSession(str(SILERO_ONNX), providers=["CPUExecutionProvider"])
        return vad_session


def silero_prob(sess, audio_f32: np.ndarray, state: np.ndarray) -> tuple[float, np.ndarray]:
    x = audio_f32.reshape(1, -1).astype(np.float32)
    sr = np.array([SAMPLE_RATE], dtype=np.int64)
    prob, state = sess.run(None, {"input": x, "sr": sr, "state": state})
    return float(np.squeeze(prob)), state


def transcribe_pcm16(pcm_bytes: bytes) -> dict:
    load_models()
    audio_url = pcm16_wav_data_url(pcm_bytes)
    t_asr = now_ms()
    text, language = asr.transcribe_audio_url(audio_url)
    dt_asr = now_ms() - t_asr

    if text:
        t_llm = now_ms()
        parsed = parse_command_llm(text)
        dt_llm = now_ms() - t_llm
        parsed["raw_transcript"] = text
    else:
        dt_llm = 0
        parsed = empty_transcript_payload()

    ha_forwarded = forward_to_home_assistant(parsed)
    return {
        "language": language or "unknown",
        "transcript": text,
        "asr_ms": round(dt_asr),
        "llm_ms": round(dt_llm),
        "ha_forwarded": ha_forwarded,
        "raw": parsed,
    }


class AudioSession:
    def __init__(self, vad):
        self.vad = vad
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.prepad = []
        self.speech = []
        self.recording = False
        self.silence_run = 0
        self.voiced_frames = 0
        self.speech_start_t = None
        self.pending = bytearray()
        self.lock = threading.Lock()

    def push_pcm16(self, pcm_bytes: bytes) -> list[dict]:
        results = []
        with self.lock:
            self.pending.extend(pcm_bytes)
            frame_bytes = FRAME_SAMPLES * 2
            while len(self.pending) >= frame_bytes:
                raw_frame = bytes(self.pending[:frame_bytes])
                del self.pending[:frame_bytes]
                frame = np.frombuffer(raw_frame, dtype="<i2").astype(np.float32) / 32768.0
                utterance = self._push_frame(frame)
                if utterance is not None:
                    results.append(transcribe_pcm16(utterance))
        return results

    def close(self) -> list[dict]:
        with self.lock:
            if not self.recording:
                return []
            utterance = self._finish_utterance()
        return [transcribe_pcm16(utterance)] if utterance is not None else []

    def _push_frame(self, frame: np.ndarray) -> bytes | None:
        self.prepad.append(frame)
        if len(self.prepad) > PREPAD_FRAMES:
            self.prepad.pop(0)

        prob, self.state = silero_prob(self.vad, frame, self.state)
        is_speech = prob >= VAD_THRESHOLD

        if not self.recording:
            if is_speech:
                self.recording = True
                self.speech_start_t = time.perf_counter()
                self.silence_run = 0
                self.voiced_frames = 1
                self.speech = list(self.prepad)
                self.prepad = []
            return None

        self.speech.append(frame)
        if is_speech:
            self.voiced_frames += 1
        self.silence_run = 0 if is_speech else self.silence_run + 1
        too_long = (time.perf_counter() - self.speech_start_t) > MAX_SPEECH_SEC
        ended = self.silence_run >= END_SILENCE_FRAMES
        if ended or too_long:
            return self._finish_utterance()
        return None

    def _finish_utterance(self) -> bytes | None:
        audio_f32 = np.concatenate(self.speech) if self.speech else np.zeros(0, dtype=np.float32)
        self.recording = False
        self.prepad = []
        self.speech = []
        self.silence_run = 0
        self.speech_start_t = None

        dur_ms = self.voiced_frames * FRAME_MS
        self.voiced_frames = 0
        if dur_ms < MIN_SPEECH_MS:
            return None

        audio_i16 = np.clip(audio_f32, -1.0, 1.0)
        audio_i16 = (audio_i16 * 32767.0).astype("<i2")
        return audio_i16.tobytes()


HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>STT</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; }
    body { margin: 0; background: #101418; color: #eef2f5; }
    main { max-width: 1120px; margin: 0 auto; padding: 24px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
    h1 { font-size: 22px; line-height: 1.2; margin: 0; font-weight: 650; }
    .controls { display: flex; gap: 8px; align-items: center; }
    button { height: 36px; border: 1px solid #43515f; background: #18212a; color: #eef2f5; border-radius: 6px; padding: 0 14px; font: inherit; cursor: pointer; }
    select { height: 36px; max-width: 280px; border: 1px solid #43515f; background: #18212a; color: #eef2f5; border-radius: 6px; padding: 0 10px; font: inherit; }
    button:hover { background: #202c36; }
    #status { min-width: 180px; color: #9fb2c3; font-size: 14px; text-align: right; }
    #debug { color: #9fb2c3; font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; margin: -8px 0 12px; overflow-wrap: anywhere; }
    .meter { height: 8px; background: #18212a; border: 1px solid #26323d; margin-bottom: 16px; }
    #level { height: 100%; width: 0%; background: #38bdf8; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; background: #121a21; border: 1px solid #26323d; }
    th, td { border-bottom: 1px solid #26323d; padding: 10px; vertical-align: top; text-align: left; }
    th { color: #9fb2c3; font-size: 12px; text-transform: uppercase; letter-spacing: 0; font-weight: 650; }
    td { font-size: 14px; }
    th:nth-child(1), td:nth-child(1) { width: 72px; }
    th:nth-child(2), td:nth-child(2) { width: 34%; }
    th:nth-child(3), td:nth-child(3) { width: 92px; }
    pre { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: #d8e4ed; }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>STT Realtime</h1>
      <div class="controls">
        <select id="device"></select>
        <button id="start">Start</button>
        <button id="send4">Send 4s</button>
        <button id="stop">Stop</button>
        <div id="status">idle</div>
      </div>
    </header>
    <div id="debug">mic: not started</div>
    <div class="meter"><div id="level"></div></div>
    <table>
      <thead>
        <tr><th>Lang</th><th>Transcript</th><th>Latency</th><th>Raw</th></tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </main>
  <script>
    const statusEl = document.querySelector("#status");
    const levelEl = document.querySelector("#level");
    const debugEl = document.querySelector("#debug");
    const deviceEl = document.querySelector("#device");
    const rows = document.querySelector("#rows");
    let ctx, source, analyser, monitorGain, stream, rafId, processor;
    let recording = false;
    let sessionId = null;
    let sendQueue = Promise.resolve();
    let pcmBuffer = [];
    let pcmBufferLength = 0;
    const authToken = __AUTH_TOKEN__;
    const targetSampleRate = 16000;
    const frameSamples = 512;
    const chunkFrames = 5;
    const chunkSamples = frameSamples * chunkFrames;

    function setStatus(text) { statusEl.textContent = text; }
    function setDebug(text) { debugEl.textContent = text; }
    function authHeaders(extra = {}) {
      return { ...extra, "X-STT-Token": authToken };
    }

    async function refreshDevices() {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const inputs = devices.filter((device) => device.kind === "audioinput");
      deviceEl.innerHTML = "";
      for (const input of inputs) {
        const option = document.createElement("option");
        option.value = input.deviceId;
        option.textContent = input.label || `Microphone ${deviceEl.length + 1}`;
        deviceEl.append(option);
      }
      setDebug(`audio inputs: ${inputs.length}`);
    }

    function updateLevel() {
      if (!analyser) return;
      const data = new Uint8Array(analyser.fftSize);
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (const v of data) {
        const x = (v - 128) / 128;
        sum += x * x;
      }
      const rms = Math.sqrt(sum / data.length);
      levelEl.style.width = `${Math.min(100, rms * 700)}%`;
      const track = stream.getAudioTracks()[0];
      const settings = track ? track.getSettings() : {};
      setDebug(
        `mic: ${track ? track.label : "none"} | state=${track ? track.readyState : "none"} | muted=${track ? track.muted : "n/a"} | rms=${rms.toFixed(4)} | rate=${settings.sampleRate || "?"}`
      );
      rafId = requestAnimationFrame(updateLevel);
    }

    async function ensureMic() {
      if (stream) return;
      const deviceId = deviceEl.value;
      stream = await navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true
      });
      await refreshDevices();
      ctx = new AudioContext();
      await ctx.resume();
      source = ctx.createMediaStreamSource(stream);
      analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      monitorGain = ctx.createGain();
      monitorGain.gain.value = 0;
      source.connect(analyser);
      analyser.connect(monitorGain);
      monitorGain.connect(ctx.destination);
      updateLevel();
    }

    function renderResult(msg) {
      const row = document.createElement("tr");
      row.innerHTML = `<td></td><td></td><td></td><td><pre></pre></td>`;
      row.children[0].textContent = msg.language;
      row.children[1].textContent = msg.transcript;
      row.children[2].textContent = `${msg.asr_ms} / ${msg.llm_ms} ms`;
      row.querySelector("pre").textContent = JSON.stringify(msg.raw, null, 2);
      rows.prepend(row);
    }

    function resampleTo16k(input, inputRate) {
      if (inputRate === targetSampleRate) return input;
      const ratio = inputRate / targetSampleRate;
      const outputLength = Math.floor(input.length / ratio);
      const output = new Float32Array(outputLength);
      for (let i = 0; i < outputLength; i++) {
        output[i] = input[Math.floor(i * ratio)] || 0;
      }
      return output;
    }

    function floatsToPcm16(samples) {
      const pcm = new Int16Array(samples.length);
      for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        pcm[i] = s < 0 ? s * 32768 : s * 32767;
      }
      return pcm;
    }

    function queueSamples(samples) {
      if (!recording || !sessionId || samples.length === 0) return;
      pcmBuffer.push(samples);
      pcmBufferLength += samples.length;
      while (pcmBufferLength >= chunkSamples) {
        const chunk = new Float32Array(chunkSamples);
        let offset = 0;
        while (offset < chunkSamples) {
          const head = pcmBuffer[0];
          const take = Math.min(head.length, chunkSamples - offset);
          chunk.set(head.subarray(0, take), offset);
          offset += take;
          if (take === head.length) {
            pcmBuffer.shift();
          } else {
            pcmBuffer[0] = head.subarray(take);
          }
          pcmBufferLength -= take;
        }
        sendPcmChunk(floatsToPcm16(chunk));
      }
    }

    function sendPcmChunk(pcm) {
      const body = pcm.buffer.slice(pcm.byteOffset, pcm.byteOffset + pcm.byteLength);
      sendQueue = sendQueue.then(async () => {
        if (!recording || !sessionId) return;
        const response = await fetch("/audio/chunk", {
          method: "POST",
          headers: authHeaders({
            "Content-Type": "application/octet-stream",
            "X-Session-Id": sessionId
          }),
          body
        });
        const msg = await response.json();
        if (!response.ok) throw new Error(msg.error || "audio chunk failed");
        for (const result of msg.results || []) renderResult(result);
        setStatus(recording ? "listening" : "stopped");
      }).catch((err) => {
        setStatus("error");
        setDebug(String(err));
      });
    }

    async function sendManualPcm(seconds) {
      const samples = await capturePcm(seconds);
      setStatus("transcribing");
      const pcm = floatsToPcm16(samples);
      const body = pcm.buffer.slice(pcm.byteOffset, pcm.byteOffset + pcm.byteLength);
      const response = await fetch("/transcribe", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/octet-stream" }),
        body
      });
      const msg = await response.json();
      renderResult(msg);
      setStatus(recording ? "listening" : "stopped");
    }

    async function capturePcm(seconds) {
      await ensureMic();
      return await new Promise((resolve) => {
        const chunks = [];
        const node = ctx.createScriptProcessor(4096, 1, 1);
        node.onaudioprocess = (event) => {
          chunks.push(resampleTo16k(event.inputBuffer.getChannelData(0), ctx.sampleRate));
        };
        source.connect(node);
        node.connect(monitorGain);
        setTimeout(() => {
          node.disconnect();
          const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
          const out = new Float32Array(total);
          let offset = 0;
          for (const chunk of chunks) {
            out.set(chunk, offset);
            offset += chunk.length;
          }
          resolve(out);
        }, seconds * 1000);
      });
    }

    async function preloadModels() {
      setStatus("loading models");
      const response = await fetch("/preload", { method: "POST", headers: authHeaders() });
      const msg = await response.json();
      setStatus(msg.status);
    }

    async function startAudioSession() {
      const response = await fetch("/audio/start", { method: "POST", headers: authHeaders() });
      const msg = await response.json();
      if (!response.ok || !msg.session_id) {
        throw new Error(msg.error || "failed to start audio session");
      }
      sessionId = msg.session_id;
      pcmBuffer = [];
      pcmBufferLength = 0;
      processor = ctx.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (event) => {
        const samples = resampleTo16k(event.inputBuffer.getChannelData(0), ctx.sampleRate);
        queueSamples(samples);
      };
      source.connect(processor);
      processor.connect(monitorGain);
    }

    async function stopAudioSession() {
      const stoppedSession = sessionId;
      sessionId = null;
      if (processor) processor.disconnect();
      processor = null;
      await sendQueue;
      if (!stoppedSession) return;
      const response = await fetch("/audio/stop", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ session_id: stoppedSession })
      });
      const msg = await response.json();
      for (const result of msg.results || []) renderResult(result);
    }

    document.querySelector("#start").onclick = async () => {
      try {
        await ensureMic();
        await preloadModels();
        recording = true;
        await startAudioSession();
        setStatus("listening");
      } catch (err) {
        recording = false;
        setStatus("error");
        setDebug(String(err));
      }
    };

    document.querySelector("#send4").onclick = async () => {
      setStatus("recording 4s");
      await sendManualPcm(4);
    };

    document.querySelector("#stop").onclick = async () => {
      recording = false;
      levelEl.style.width = "0%";
      await stopAudioSession();
      if (rafId) cancelAnimationFrame(rafId);
      if (processor) processor.disconnect();
      if (source) source.disconnect();
      if (monitorGain) monitorGain.disconnect();
      if (stream) stream.getTracks().forEach(track => track.stop());
      ctx = null;
      source = null;
      analyser = null;
      monitorGain = null;
      stream = null;
      processor = null;
      pcmBuffer = [];
      pcmBufferLength = 0;
      setStatus("stopped");
    };

    refreshDevices();
    navigator.mediaDevices.addEventListener("devicechange", refreshDevices);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def authenticated(self) -> bool:
        token = self.headers.get("X-STT-Token", "")
        if secrets.compare_digest(token, AUTH_TOKEN):
            return True
        self.send_json({"error": "unauthorized"}, status=401)
        return False

    def rate_limit(self) -> bool:
        client = self.client_address[0] if self.client_address else "unknown"
        allowed, retry_after = allow_request(client, self.path)
        if allowed:
            return False
        self.send_json({"error": "rate limit exceeded"}, status=429, headers={"Retry-After": str(round(retry_after))})
        return True

    def send_json(self, payload: dict, status: int = 200, headers: dict | None = None):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def read_body(self, max_bytes: int) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"error": "invalid content length"}, status=400)
            return None
        if length < 0:
            self.send_json({"error": "invalid content length"}, status=400)
            return None
        if length > max_bytes:
            self.send_json({"error": "request body too large"}, status=413)
            return None
        return self.rfile.read(length)

    def do_GET(self):
        page = HTML.replace("__AUTH_TOKEN__", json.dumps(AUTH_TOKEN))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode())

    def do_POST(self):
        if self.rate_limit():
            return
        if not self.authenticated():
            return

        if self.path == "/preload":
            load_models()
            self.send_json({"status": "listening"})
            return

        if self.path == "/audio/start":
            try:
                vad = load_vad_session()
            except Exception as exc:
                print(f"vad startup failed: {exc}", flush=True)
                self.send_json({"error": "failed to start vad"}, status=500)
                return
            session_id = uuid.uuid4().hex
            with audio_sessions_lock:
                if len(audio_sessions) >= MAX_AUDIO_SESSIONS:
                    self.send_json({"error": "too many active audio sessions"}, status=429)
                    return
                audio_sessions[session_id] = AudioSession(vad)
            self.send_json({"session_id": session_id, "sample_rate": SAMPLE_RATE, "frame_samples": FRAME_SAMPLES})
            return

        if self.path == "/audio/chunk":
            session_id = self.headers.get("X-Session-Id")
            with audio_sessions_lock:
                session = audio_sessions.get(session_id)
            if session is None:
                self.send_json({"error": "unknown audio session"}, status=404)
                return
            body = self.read_body(MAX_CHUNK_BYTES)
            if body is None:
                return
            results = session.push_pcm16(body)
            self.send_json({"results": results})
            return

        if self.path == "/audio/stop":
            body = self.read_body(MAX_STOP_BYTES)
            if body is None:
                return
            try:
                msg = json.loads(body.decode() or "{}")
            except json.JSONDecodeError:
                self.send_json({"error": "invalid json"}, status=400)
                return
            session_id = msg.get("session_id")
            with audio_sessions_lock:
                session = audio_sessions.pop(session_id, None)
            if session is None:
                self.send_json({"results": []})
                return
            self.send_json({"results": session.close()})
            return

        if self.path != "/transcribe":
            self.send_response(404)
            self.end_headers()
            return

        body = self.read_body(MAX_TRANSCRIBE_BYTES)
        if body is None:
            return
        print(
            f"received pcm audio: {len(body)} bytes, content-type={self.headers.get('Content-Type')}",
            flush=True,
        )
        self.send_json(transcribe_pcm16(body))

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    host = os.getenv("STT_APP_HOST", "127.0.0.1")
    port = int(os.getenv("STT_APP_PORT", "7860"))
    print(f"STT app: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
