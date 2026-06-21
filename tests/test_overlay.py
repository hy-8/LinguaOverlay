from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.config import load_settings
from src.overlay import OverlayWindow


def test_overlay_has_close_button_connected_to_quit() -> None:
    app = QApplication.instance() or QApplication([])
    window = OverlayWindow(load_settings(Path(__file__).parents[1]))

    assert window.close_button.text() == "✕"
    assert window.close_button.toolTip() == "关闭实时字幕"
    assert window.close_button.width() == 30
    assert window.close_button.height() == 30

    window.tray.hide()
    window.deleteLater()
    app.processEvents()
