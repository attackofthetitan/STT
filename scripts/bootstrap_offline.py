from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

FW_REPO_BY_NAME = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
}

DEFAULT_SILERO_REPO = "onnx-community/silero-vad"
DEFAULT_SILERO_FILE = "onnx/model.onnx"

DEFAULT_MODELS = ["base"]


def download_silero_onnx(models_dir: Path, repo_id: str, filename: str) -> dict:
    silero_dir = models_dir / "silero"
    silero_dir.mkdir(parents=True, exist_ok=True)
    out_path = silero_dir / "silero_vad.onnx"

    print(f"[silero] Downloading from HF repo '{repo_id}' file '{filename}'")
    downloaded = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(silero_dir / "_hf"),
    )

    shutil.copy2(downloaded, out_path)
    print(f"[silero] Saved -> {out_path}")

    return {
        "repo_id": repo_id,
        "filename": filename,
        "path": str(out_path),
    }


def download_faster_whisper_models(models_dir: Path, model_names: list[str]) -> list[dict]:
    whisper_root = models_dir / "whisper"
    whisper_root.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []

    for name in model_names:
        repo_id = FW_REPO_BY_NAME.get(name, name)  # allow full repo ids
        target_dir = whisper_root / name

        print(f"[whisper] Downloading '{repo_id}' -> {target_dir}")

        # Grab the full snapshot
        snapshot_path = snapshot_download(
            repo_id=repo_id,
            local_dir=str(target_dir),
        )

        results.append(
            {
                "name": name,
                "repo_id": repo_id,
                "path": snapshot_path,
            }
        )

    return results


def write_manifest(models_dir: Path, silero: dict, whisper_models: list[dict]) -> None:
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "silero": silero,
        "whisper_models": whisper_models,
        "offline_env_vars": {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        },
        "load_paths": {
            "silero_onnx": "models/silero/silero_vad.onnx",
            "whisper_model_dirs": {m["name"]: f"models/whisper/{m['name']}" for m in whisper_models},
        },
    }
    out = models_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[ok] Wrote manifest -> {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        nargs="*",
        default=DEFAULT_MODELS,
        help="Whisper models to download: tiny base small medium large-v3 (default: base).",
    )
    parser.add_argument(
        "--silero-repo",
        default=DEFAULT_SILERO_REPO,
        help="Hugging Face repo for Silero VAD ONNX (default: onnx-community/silero-vad).",
    )
    parser.add_argument(
        "--silero-file",
        default=DEFAULT_SILERO_FILE,
        help="Path to ONNX file inside the Silero HF repo (default: onnx/model.onnx).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    models_dir = repo_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    print(f"[root] {repo_root}")
    print(f"[plan] Whisper models: {args.models}")
    print(f"[plan] Silero source: {args.silero_repo} :: {args.silero_file}")

    silero_info = download_silero_onnx(models_dir=models_dir, repo_id=args.silero_repo, filename=args.silero_file)
    whisper_info = download_faster_whisper_models(models_dir=models_dir, model_names=args.models)

    write_manifest(models_dir=models_dir, silero=silero_info, whisper_models=whisper_info)

    print("[done] All models downloaded and manifest created.")


if __name__ == "__main__":
    main()