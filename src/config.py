from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    audio_device_index: int | None = None
    target_sample_rate: int = 16000
    whisper_model: str = "large-v3-turbo"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    source_language: str = "auto"
    window_seconds: float = 5.0
    hop_seconds: float = 0.45
    minimum_audio_seconds: float = 0.65
    finalize_delay_seconds: float = 0.15
    translation_hold_seconds: float = 0.35
    translation_max_buffer_seconds: float = 0.9
    translation_max_chars: int = 48
    translation_queue_size: int = 6
    translation_workers: int = 3
    translation_stream: bool = True
    translation_context_items: int = 2
    subtitle_history_items: int = 2
    show_original: bool = True
    font_size_original: int = 20
    font_size_translation: int = 27
    background_opacity: float = 0.78
    translation_provider: str = "auto"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-mt-lite"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.io/v1"
    minimax_model: str = "MiniMax-M2.7-highspeed"
    translation_timeout_seconds: float = 30.0


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def load_settings(project_dir: Path) -> Settings:
    config_path = project_dir / "config" / "settings.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    _load_dotenv(project_dir / ".env")

    payload["translation_provider"] = os.getenv(
        "TRANSLATION_PROVIDER",
        payload.get("translation_provider", Settings.translation_provider),
    )
    payload["qwen_api_key"] = os.getenv("QWEN_API_KEY", "")
    payload["qwen_base_url"] = os.getenv(
        "QWEN_BASE_URL", payload.get("qwen_base_url", Settings.qwen_base_url)
    )
    payload["qwen_model"] = os.getenv(
        "QWEN_MODEL", payload.get("qwen_model", Settings.qwen_model)
    )
    payload["minimax_api_key"] = os.getenv("MINIMAX_API_KEY", "")
    payload["minimax_base_url"] = os.getenv(
        "MINIMAX_BASE_URL", payload.get("minimax_base_url", Settings.minimax_base_url)
    )
    payload["minimax_model"] = os.getenv(
        "MINIMAX_MODEL", payload.get("minimax_model", Settings.minimax_model)
    )
    return Settings(**payload)
