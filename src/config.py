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
    window_seconds: float = 10.0
    hop_seconds: float = 1.5
    finalize_delay_seconds: float = 1.2
    translation_hold_seconds: float = 1.8
    show_original: bool = True
    font_size_original: int = 20
    font_size_translation: int = 27
    background_opacity: float = 0.78
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

    payload["minimax_api_key"] = os.getenv("MINIMAX_API_KEY", "")
    payload["minimax_base_url"] = os.getenv(
        "MINIMAX_BASE_URL", payload.get("minimax_base_url", Settings.minimax_base_url)
    )
    payload["minimax_model"] = os.getenv(
        "MINIMAX_MODEL", payload.get("minimax_model", Settings.minimax_model)
    )
    return Settings(**payload)
