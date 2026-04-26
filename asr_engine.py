import base64
import io
import re
import wave

import numpy as np


class QwenASR:
    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-ASR-0.6B",
        language: str | None = None,
        max_new_tokens: int = 128,
        max_inference_batch_size: int = 1,
        gpu_memory_utilization: float = 0.7,
        max_model_len: int = 2048,
        enforce_eager: bool = True,
    ):
        from vllm import LLM, SamplingParams

        self.language = language or "Traditional Chinese"
        self.sampling_params = SamplingParams(temperature=0.01, max_tokens=max_new_tokens)
        self.model = LLM(
            model=model_name,
            max_num_seqs=max_inference_batch_size,
            gpu_memory_utilization=gpu_memory_utilization,
            max_model_len=max_model_len,
            enforce_eager=enforce_eager,
        )

    def transcribe(self, audio_f32, sample_rate: int) -> tuple[str, str | None]:
        audio_url = self._wav_data_url(audio_f32, sample_rate)
        return self.transcribe_audio_url(audio_url)

    def transcribe_audio_url(self, audio_url: str) -> tuple[str, str | None]:
        content = [{"type": "audio_url", "audio_url": {"url": audio_url}}]
        if self.language:
            content.append({"type": "text", "text": f"Transcribe the audio in {self.language}."})

        outputs = self.model.chat(
            [{"role": "user", "content": content}],
            sampling_params=self.sampling_params,
            use_tqdm=False,
        )
        return self._clean_output(outputs[0].outputs[0].text)

    @staticmethod
    def _clean_output(text: str) -> tuple[str, str | None]:
        text = text.strip()
        language = None

        match = re.match(r"language\s+([^<\s]+)\s*<asr_text>\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            language = match.group(1)
            text = match.group(2)
        else:
            text = text.replace("<asr_text>", "")

        return text.strip(), language

    @staticmethod
    def _wav_data_url(audio_f32, sample_rate: int) -> str:
        audio_i16 = np.clip(audio_f32, -1.0, 1.0)
        audio_i16 = (audio_i16 * 32767.0).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(audio_i16.tobytes())

        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:audio/wav;base64,{encoded}"
