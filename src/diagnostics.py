from __future__ import annotations

import importlib.metadata
import platform
import subprocess
import sys


PACKAGES = (
    "ctranslate2",
    "faster-whisper",
    "PyAudioWPatch",
    "PySide6",
    "httpx",
    "numpy",
)


def print_diagnostics() -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Executable: {sys.executable}")
    print(f"Platform: {platform.platform()}")
    print("")
    print("依赖：")
    for package in PACKAGES:
        try:
            version = importlib.metadata.version(package)
            print(f"  OK  {package} {version}")
        except importlib.metadata.PackageNotFoundError:
            print(f"  --  {package} 未安装")

    print("")
    print("NVIDIA：")
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,compute_cap",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"  {result.stdout.strip()}")
    except Exception as exc:
        print(f"  无法执行 nvidia-smi：{exc}")

    try:
        import ctranslate2

        print(f"  CUDA compute types: {ctranslate2.get_supported_compute_types('cuda')}")
    except Exception as exc:
        print(f"  CTranslate2 CUDA 检查失败：{exc}")

    print("")
    print("WASAPI 回环设备：")
    try:
        from src.audio_capture import list_loopback_devices

        devices = list_loopback_devices()
        for device in devices:
            print(
                f"  [{device['index']}] {device['name']} | "
                f"{int(device['defaultSampleRate'])} Hz | "
                f"{device['maxInputChannels']} ch"
            )
        if not devices:
            print("  未找到回环设备")
    except Exception as exc:
        print(f"  设备检查失败：{exc}")

    return 0
