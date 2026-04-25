class QwenASR:
    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-ASR-0.6B",
        language: str | None = None,
        max_new_tokens: int = 128,
        max_inference_batch_size: int = 1,
        gpu_memory_utilization: float = 0.7,
    ):
        from qwen_asr import Qwen3ASRModel

        self.language = language
        self.model = Qwen3ASRModel.LLM(
            model=model_name,
            max_new_tokens=max_new_tokens,
            max_inference_batch_size=max_inference_batch_size,
            gpu_memory_utilization=gpu_memory_utilization,
        )

    def transcribe(self, audio_f32, sample_rate: int) -> tuple[str, str | None]:
        results = self.model.transcribe(
            audio=(audio_f32, sample_rate),
            language=self.language,
        )
        result = results[0]
        return result.text.strip(), result.language
