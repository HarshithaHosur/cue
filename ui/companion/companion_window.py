# ============================================================
#  DESKTOP COMPANION WINDOW — Animated AI Robot Overlay
#  Always-on-top, responsive, fluidly animated companion
#  synchronized with central AgentController state machine.
# ============================================================

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    Qt, QPoint, QUrl, Slot, Signal, QPropertyAnimation,
    QEasingCurve, QRect, QTimer
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMenu
from PySide6.QtQuickWidgets import QQuickWidget

from intent_platform.config.settings import QML_DIR
from intent_platform.core.agent.agent_controller import get_agent_controller, AgentState

logger = logging.getLogger("DesktopCompanionOverlay")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class DesktopCompanionOverlay(QWidget):
    """
    Always-on-top, non-blocking, frameless overlay embedding the Kawaii AI Robot Companion.
    Provides smooth animated transitions between Resting (Bottom-Right) and Active (Top-Right) positions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_position = QPoint()
        self._current_position_tag = "bottom_right"
        self._pos_animation: Optional[QPropertyAnimation] = None

        # Frameless, transparent, stays on top, tool window (no taskbar clutter)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(260, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Embedded QML Widget
        self.quick_widget = QQuickWidget(self)
        self.quick_widget.setClearColor(Qt.GlobalColor.transparent)
        self.quick_widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)

        qml_path = QML_DIR / "RobotCompanion.qml"
        self.quick_widget.setSource(QUrl.fromLocalFile(str(qml_path)))
        layout.addWidget(self.quick_widget)

        # Position at initial Resting (Bottom-Right) location safely
        self.snap_to_resting_position()

        # Connect with central AgentController
        self._agent_controller = get_agent_controller()
        self._agent_controller.signals.position_requested.connect(self.animate_to_position)
        self._agent_controller.signals.companion_mood.connect(self.update_companion_state)

        # Hook screen resolution change if screen changes
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen.geometryChanged.connect(self._on_screen_geometry_changed)

    def _get_screen_geometry(self) -> QRect:
        """Returns the available geometry of the primary screen, excluding taskbars."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            return screen.availableGeometry()
        return QRect(0, 0, 1920, 1080)

    def calculate_position(self, position_tag: str) -> QPoint:
        """
        Calculates safe (x, y) coordinates for target position:
        - 'bottom_right': Resting position, 25px margin from right & bottom.
        - 'top_right': Active position, 25px margin from right, 90px from top (below title bar).
        Guarantees widget is 100% inside screen bounds with zero clipping.
        """
        screen_geo = self._get_screen_geometry()
        w = self.width()
        h = self.height()

        margin_right = 25
        margin_bottom = 25
        margin_top = 90

        x = screen_geo.x() + screen_geo.width() - w - margin_right

        if position_tag == "top_right":
            y = screen_geo.y() + margin_top
        else:  # bottom_right (resting)
            y = screen_geo.y() + screen_geo.height() - h - margin_bottom

        # Clamp strictly inside visible screen bounds
        min_x = screen_geo.x()
        max_x = screen_geo.x() + screen_geo.width() - w
        min_y = screen_geo.y()
        max_y = screen_geo.y() + screen_geo.height() - h

        clamped_x = max(min_x, min(x, max_x))
        clamped_y = max(min_y, min(y, max_y))

        return QPoint(clamped_x, clamped_y)

    def snap_to_resting_position(self):
        """Immediately places the companion at the resting bottom-right coordinates."""
        target = self.calculate_position("bottom_right")
        self.move(target)
        self._current_position_tag = "bottom_right"

    @Slot(str, int)
    def animate_to_position(self, position_tag: str, duration_ms: int = 650):
        """
        Smoothly animates the companion between Bottom-Right and Top-Right.
        Uses QEasingCurve.OutCubic for responsive natural deceleration.
        """
        if self._pos_animation and self._pos_animation.state() == QPropertyAnimation.State.Running:
            self._pos_animation.stop()

        target_pos = self.calculate_position(position_tag)
        current_pos = self.pos()

        if current_pos == target_pos:
            self._current_position_tag = position_tag
            return

        logger.info(f"[ROBOT] animation started: moving {self._current_position_tag} -> {position_tag} (duration: {duration_ms}ms)")

        self._pos_animation = QPropertyAnimation(self, b"pos", self)
        self._pos_animation.setDuration(duration_ms)
        self._pos_animation.setStartValue(current_pos)
        self._pos_animation.setEndValue(target_pos)
        self._pos_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _on_finished():
            self._current_position_tag = position_tag
            logger.info(f"[ROBOT] animation completed: positioned at {position_tag}")

        self._pos_animation.finished.connect(_on_finished)
        self._pos_animation.start()

    def _on_screen_geometry_changed(self, new_geo: QRect):
        """Recalculates safe placement if display resolution changes."""
        logger.info(f"[ROBOT] Screen resolution changed to {new_geo.width()}x{new_geo.height()}, updating position")
        target = self.calculate_position(self._current_position_tag)
        self.move(target)

    @Slot(str, str)
    def update_companion_state(self, state: str, message: str = ""):
        """Updates companion state (idle, listening, thinking, executing, success, error) and bubble."""
        root = self.quick_widget.rootObject()
        if not root:
            return

        state_lower = state.lower()
        qml_state = "idle"
        if "listen" in state_lower:
            qml_state = "listening"
        elif any(k in state_lower for k in ("think", "cursor", "read", "understand", "plan", "process")):
            qml_state = "thinking"
        elif "execut" in state_lower:
            qml_state = "executing"
        elif any(k in state_lower for k in ("wait", "confirm")):
            qml_state = "listening"
        elif "speak" in state_lower:
            qml_state = "success"
        elif any(k in state_lower for k in ("success", "scroll", "saved", "activated", "completed")):
            qml_state = "success"
        elif any(k in state_lower for k in ("error", "lost", "paused", "blocked", "disabled")):
            qml_state = "error"

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
            new_pos = event.globalPosition().toPoint() - self.drag_position
            # Screen clamp while dragging
            screen_geo = self._get_screen_geometry()
            clamped_x = max(screen_geo.x(), min(new_pos.x(), screen_geo.x() + screen_geo.width() - self.width()))
            clamped_y = max(screen_geo.y(), min(new_pos.y(), screen_geo.y() + screen_geo.height() - self.height()))
            self.move(clamped_x, clamped_y)
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
        
        is_active = self._agent_controller.is_active
        action_toggle = menu.addAction("Deactivate AI Agent" if is_active else "Activate AI Agent")
        action_reset_pos = menu.addAction("Snap to Resting Position")
        action_hide = menu.addAction("Hide Companion")
        action_quit = menu.addAction("Close")

        chosen = menu.exec(global_pos)
        if chosen == action_toggle:
            self._agent_controller.toggle(source="context_menu")
        elif chosen == action_reset_pos:
            self.snap_to_resting_position()
        elif chosen == action_hide:
            self.hide()
        elif chosen == action_quit:
            self.close()
