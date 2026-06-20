from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Windows 实时桌面字幕")
    parser.add_argument("--diagnose", action="store_true", help="检查运行环境")
    parser.add_argument("--list-devices", action="store_true", help="列出 WASAPI 回环设备")
    parser.add_argument("--mock", action="store_true", help="强制使用模拟翻译")
    parser.add_argument(
        "--smoke-seconds",
        type=float,
        default=0,
        help="启动完整应用并在指定秒数后自动退出",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.diagnose:
        from src.diagnostics import print_diagnostics

        return print_diagnostics()

    if args.list_devices:
        from src.audio_capture import print_loopback_devices

        print_loopback_devices()
        return 0

    from PySide6.QtCore import QObject, QTimer, Signal
    from PySide6.QtWidgets import QApplication

    from src.config import load_settings
    from src.overlay import OverlayWindow
    from src.pipeline import RealtimePipeline

    class UiBridge(QObject):
        status = Signal(str)
        preview = Signal(str)
        subtitle = Signal(str, str)

    settings = load_settings(PROJECT_DIR)
    app = QApplication(sys.argv)
    app.setApplicationName("实时桌面字幕")
    app.setQuitOnLastWindowClosed(False)

    bridge = UiBridge()
    overlay = OverlayWindow(settings)

    def report_status(text: str) -> None:
        if args.smoke_seconds:
            print(f"[status] {text}", flush=True)
        bridge.status.emit(text)

    def report_preview(text: str) -> None:
        if args.smoke_seconds and text:
            print(f"[preview] {text}", flush=True)
        bridge.preview.emit(text)

    def report_subtitle(original: str, translation: str) -> None:
        if args.smoke_seconds:
            print(f"[subtitle] {original} -> {translation}", flush=True)
        bridge.subtitle.emit(original, translation)

    pipeline = RealtimePipeline(
        settings=settings,
        project_dir=PROJECT_DIR,
        force_mock=args.mock,
        on_status=report_status,
        on_preview=report_preview,
        on_subtitle=report_subtitle,
    )

    bridge.status.connect(overlay.set_status)
    bridge.preview.connect(overlay.set_preview)
    bridge.subtitle.connect(overlay.set_subtitle)
    overlay.stopping.connect(pipeline.stop)
    overlay.show()

    QTimer.singleShot(100, pipeline.start)
    if args.smoke_seconds > 0:
        QTimer.singleShot(round(args.smoke_seconds * 1000), app.quit)
    exit_code = app.exec()
    pipeline.stop()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
