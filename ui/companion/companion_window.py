# ============================================================
#  DESKTOP COMPANION WINDOW — QML Bridge & Transparent Overlay
# ============================================================

from pathlib import Path
from PySide6.QtCore import Qt, QPoint, QUrl, Slot, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMenu
from PySide6.QtQuickWidgets import QQuickWidget

from intent_platform.config.settings import QML_DIR


class DesktopCompanionOverlay(QWidget):
    """Always-on-top, draggable, frameless overlay embedding the animated Robot Companion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_position = QPoint()

        # Frameless, transparent, stays on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(320, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Embedded QML Widget
        self.quick_widget = QQuickWidget(self)
        self.quick_widget.setClearColor(Qt.GlobalColor.transparent)
        self.quick_widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)

        qml_path = QML_DIR / "RobotCompanion.qml"
        self.quick_widget.setSource(QUrl.fromLocalFile(str(qml_path)))
        layout.addWidget(self.quick_widget)

    @Slot(str, str)
    def update_companion_state(self, state: str, message: str = ""):
        """Updates companion state (idle, listening, thinking, executing, success, error) and bubble."""
        root = self.quick_widget.rootObject()
        if not root:
            return

        # Normalize state key for QML state transitions
        state_lower = state.lower()
        qml_state = "idle"
        if "listen" in state_lower:
            qml_state = "listening"
        elif "think" in state_lower or "cursor" in state_lower:
            qml_state = "thinking"
        elif "execut" in state_lower:
            qml_state = "executing"
        elif "success" in state_lower or "scroll" in state_lower or "saved" in state_lower or "activated" in state_lower or "completed" in state_lower:
            qml_state = "success"
        elif "error" in state_lower or "lost" in state_lower or "paused" in state_lower or "blocked" in state_lower:
            qml_state = "error"

        # Apply to QML properties
        root.setProperty("state", qml_state)
        root.setProperty("companionState", qml_state)

        bubble_msg = message if message else state
        root.setProperty("bubbleText", bubble_msg)
        root.setProperty("speechText", bubble_msg)
        root.setProperty("speechBubbleVisible", True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #181926;
                color: #CAD3F5;
                border: 1px solid #363A4F;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item:selected {
                background: #8AADF4;
                color: #181926;
                border-radius: 4px;
            }
        """)
        action_hide = menu.addAction("Hide Companion")
        action_reset = menu.addAction("Reset to Idle")
        action_quit = menu.addAction("Close")

        chosen = menu.exec(global_pos)
        if chosen == action_hide:
            self.hide()
        elif chosen == action_reset:
            self.update_companion_state("idle", "Ready!")
        elif chosen == action_quit:
            self.close()
