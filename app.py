import base64
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from asr_engine import QwenASR


ROOT = Path(__file__).resolve().parent

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

CUDNN_DIR = ROOT / "vendor" / "cudnn" / "bin"
CUDBLAS_DIR = ROOT / "vendor" / "cublas" / "bin"
os.environ["PATH"] = f"{CUDNN_DIR};{CUDBLAS_DIR};" + os.environ.get("PATH", "")

ASR_MODEL = os.getenv("STT_ASR_MODEL", str(ROOT / "models" / "asr" / "qwen3-asr-0.6b"))
ASR_LANGUAGE = os.getenv("STT_ASR_LANGUAGE") or None
ASR_MAX_NEW_TOKENS = int(os.getenv("STT_ASR_MAX_NEW_TOKENS", "128"))
ASR_MAX_MODEL_LEN = int(os.getenv("STT_ASR_MAX_MODEL_LEN", "1536"))
ASR_GPU_MEMORY_UTILIZATION = float(os.getenv("STT_ASR_GPU_MEMORY_UTILIZATION", "0.28"))
ASR_ENFORCE_EAGER = os.getenv("STT_ASR_ENFORCE_EAGER", "0") == "1"

asr = None
parse_command_llm = None
load_lock = threading.Lock()


def now_ms() -> float:
    return time.perf_counter() * 1000.0


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
    let ctx, source, analyser, monitorGain, stream, rafId;
    let recording = false;
    let speaking = false;
    let sending = false;
    let recorder = null;
    let utteranceChunks = [];
    let silenceMs = 0;
    let speechMs = 0;
    let currentRms = 0;
    const speechThreshold = 0.012;
    const endSilenceMs = 400;
    const minSpeechMs = 350;

    function setStatus(text) { statusEl.textContent = text; }
    function setDebug(text) { debugEl.textContent = text; }

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
      currentRms = rms;
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

    function makeRecorder() {
      const type = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
      return type ? new MediaRecorder(stream, { mimeType: type }) : new MediaRecorder(stream);
    }

    function startContinuousRecorder() {
      if (rafId) cancelAnimationFrame(rafId);
      silenceMs = 0;
      speechMs = 0;
      speaking = false;
      updateLevel();
      detectSpeech();
    }

    function startUtterance() {
      utteranceChunks = [];
      recorder = makeRecorder();
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) utteranceChunks.push(event.data);
      };
      recorder.onstop = () => {
        const chunks = utteranceChunks;
        const blobType = recorder.mimeType;
        utteranceChunks = [];
        recorder = null;
        if (speechMs >= minSpeechMs) {
          sendBlob(new Blob(chunks, { type: blobType }));
        }
        speechMs = 0;
      };
      recorder.start();
      speaking = true;
      silenceMs = 0;
      speechMs = 0;
      setStatus("recording");
    }

    function finishUtterance() {
      speaking = false;
      silenceMs = 0;
      setStatus("listening");
      if (recorder && recorder.state !== "inactive") recorder.stop();
    }

    function detectSpeech() {
      if (!recording) return;
      const dt = 100;
      if (currentRms >= speechThreshold) {
        if (!speaking && !sending) startUtterance();
        if (speaking) {
          speechMs += dt;
          silenceMs = 0;
        }
      } else if (speaking) {
        silenceMs += dt;
        if (silenceMs >= endSilenceMs) finishUtterance();
      }
      setTimeout(detectSpeech, dt);
    }

    async function recordBlob(ms) {
      await ensureMic();
      return await new Promise((resolve) => {
        const chunks = [];
        const manualRecorder = makeRecorder();
        manualRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) chunks.push(event.data);
        };
        manualRecorder.onstop = () => resolve(new Blob(chunks, { type: manualRecorder.mimeType }));
        manualRecorder.start();
        setTimeout(() => manualRecorder.stop(), ms);
      });
    }

    async function sendBlob(blob) {
      if (sending || blob.size === 0) return;
      sending = true;
      setStatus("transcribing");
      const response = await fetch("/transcribe", { method: "POST", body: blob });
      const msg = await response.json();
      const row = document.createElement("tr");
      row.innerHTML = `<td></td><td></td><td></td><td><pre></pre></td>`;
      row.children[0].textContent = msg.language;
      row.children[1].textContent = msg.transcript;
      row.children[2].textContent = `${msg.asr_ms} / ${msg.llm_ms} ms`;
      row.querySelector("pre").textContent = JSON.stringify(msg.raw, null, 2);
      rows.prepend(row);
      sending = false;
      setStatus(recording ? "listening" : "stopped");
    }

    async function preloadModels() {
      setStatus("loading models");
      const response = await fetch("/preload", { method: "POST" });
      const msg = await response.json();
      setStatus(msg.status);
    }

    document.querySelector("#start").onclick = async () => {
      await ensureMic();
      recording = true;
      await preloadModels();
      startContinuousRecorder();
    };

    document.querySelector("#send4").onclick = async () => {
      setStatus("recording 4s");
      const blob = await recordBlob(4000);
      await sendBlob(blob);
    };

    document.querySelector("#stop").onclick = () => {
      recording = false;
      speaking = false;
      levelEl.style.width = "0%";
      if (recorder && recorder.state !== "inactive") recorder.stop();
      if (rafId) cancelAnimationFrame(rafId);
      if (source) source.disconnect();
      if (monitorGain) monitorGain.disconnect();
      if (stream) stream.getTracks().forEach(track => track.stop());
      ctx = null;
      source = null;
      analyser = null;
      monitorGain = null;
      stream = null;
      recorder = null;
      utteranceChunks = [];
      setStatus("stopped");
    };

    refreshDevices();
    navigator.mediaDevices.addEventListener("devicechange", refreshDevices);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        if self.path == "/preload":
            load_models()
            data = json.dumps({"status": "listening"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if self.path != "/transcribe":
            self.send_response(404)
            self.end_headers()
            return

        body = self.rfile.read(int(self.headers["Content-Length"]))
        print(
            f"received audio: {len(body)} bytes, content-type={self.headers.get('Content-Type')}",
            flush=True,
        )
        audio_url = "data:audio/wav;base64," + base64.b64encode(body).decode("ascii")

        load_models()
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
            parsed = {
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

        payload = {
            "language": language or "unknown",
            "transcript": text,
            "asr_ms": round(dt_asr),
            "llm_ms": round(dt_llm),
            "raw": parsed,
        }
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    host = os.getenv("STT_APP_HOST", "127.0.0.1")
    port = int(os.getenv("STT_APP_PORT", "7860"))
    print(f"STT app: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
