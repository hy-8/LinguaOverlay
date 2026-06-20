from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QMouseEvent, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src.config import Settings


class OverlayWindow(QWidget):
    stopping = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self._drag_position: QPoint | None = None
        self._locked = False
        self._build_ui()
        self._build_tray()

    def _build_ui(self) -> None:
        self.setWindowTitle("实时桌面字幕")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(720)
        self.resize(980, 180)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 14, 22, 18)
        root.setSpacing(8)

        controls = QHBoxLayout()
        self.status_label = QLabel("准备启动")
        self.status_label.setStyleSheet("color: #b8c0cc; font-size: 12px;")
        controls.addWidget(self.status_label)
        controls.addStretch()

        self.original_button = QPushButton("原文")
        self.original_button.setCheckable(True)
        self.original_button.setChecked(self.settings.show_original)
        self.original_button.clicked.connect(self._toggle_original)
        controls.addWidget(self.original_button)

        self.lock_button = QPushButton("锁定")
        self.lock_button.setCheckable(True)
        self.lock_button.clicked.connect(self.set_locked)
        controls.addWidget(self.lock_button)
        root.addLayout(controls)

        self.original_label = QLabel("等待音频…")
        self.original_label.setWordWrap(True)
        self.original_label.setFont(
            QFont("Microsoft YaHei UI", self.settings.font_size_original)
        )
        self.original_label.setStyleSheet("color: #d6dbe3;")
        self.original_label.setVisible(self.settings.show_original)
        root.addWidget(self.original_label)

        self.translation_label = QLabel("中文字幕将在这里显示")
        self.translation_label.setWordWrap(True)
        self.translation_label.setFont(
            QFont(
                "Microsoft YaHei UI",
                self.settings.font_size_translation,
                QFont.Weight.DemiBold,
            )
        )
        self.translation_label.setStyleSheet("color: white;")
        root.addWidget(self.translation_label)

        self.setStyleSheet(
            """
            QPushButton {
                color: #dce3ec;
                background: rgba(255, 255, 255, 25);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 5px;
                padding: 4px 10px;
            }
            QPushButton:checked { background: rgba(64, 140, 255, 100); }
            """
        )

        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2, screen.height() - 260)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("实时桌面字幕")
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaVolume))
        menu = QMenu()

        show_action = QAction("显示/隐藏字幕", self)
        show_action.triggered.connect(self._toggle_window)
        menu.addAction(show_action)

        self.tray_original_action = QAction("显示原文", self)
        self.tray_original_action.setCheckable(True)
        self.tray_original_action.setChecked(self.settings.show_original)
        self.tray_original_action.triggered.connect(self._set_original_visible)
        menu.addAction(self.tray_original_action)

        self.tray_lock_action = QAction("鼠标穿透", self)
        self.tray_lock_action.setCheckable(True)
        self.tray_lock_action.triggered.connect(self.set_locked)
        menu.addAction(self.tray_lock_action)

        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(10, 13, 18)
        color.setAlphaF(max(0.15, min(1.0, self.settings.background_opacity)))
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 14, 14)
        painter.drawPath(path)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_preview(self, text: str) -> None:
        if text:
            self.original_label.setText(text)

    def set_subtitle(self, original: str, translation: str) -> None:
        self.original_label.setText(original)
        self.translation_label.setText(translation)
        self.adjustSize()
        self.setMinimumWidth(720)
        self.resize(max(720, min(self.width(), 1100)), self.height())

    def _toggle_original(self) -> None:
        self._set_original_visible(self.original_button.isChecked())

    def _set_original_visible(self, visible: bool) -> None:
        self.original_label.setVisible(visible)
        self.original_button.setChecked(visible)
        self.tray_original_action.setChecked(visible)
        self.adjustSize()

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self.lock_button.setChecked(locked)
        self.tray_lock_action.setChecked(locked)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, locked)
        self.show()

    def _toggle_window(self) -> None:
        self.setVisible(not self.isVisible())

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_window()

    def _quit(self) -> None:
        self.stopping.emit()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._locked and event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            not self._locked
            and self._drag_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_position = None
        event.accept()
