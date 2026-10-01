# ============================================================
#  SCREEN OVERLAY HIGHLIGHTER — Visual UI Element Targeting
#  Renders a neon pulsating overlay box and badge directly over
#  detected buttons, cards, and support options before action.
# ============================================================

import sys
import time
import math
from typing import Optional, Tuple
from PySide6.QtCore import Qt, QTimer, QRect, QPoint, Signal, QObject, Slot
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QWidget, QApplication


class HighlighterSignals(QObject):
    show_highlight = Signal(int, int, int, int, str, float)
    hide_highlight = Signal()


class VisualHighlightOverlay(QWidget):
    """
    Transparent, click-through, topmost desktop overlay that renders a glowing
    neon targeting box and title badge over any UI element on screen.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.target_rect: Optional[QRect] = None
        self.target_label: str = ""
        self.pulse_phase: float = 0.0

        # Animation timer for pulsating glow
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_pulse)
        self.anim_timer.setInterval(30)

        # Auto-dismiss timer
        self.auto_dismiss_timer = QTimer(self)
        self.auto_dismiss_timer.setSingleShot(True)
        self.auto_dismiss_timer.timeout.connect(self.hide_highlight)

        # Full primary screen coverage
        try:
            screen = QApplication.primaryScreen()
            if screen:
                geom = screen.geometry()
                self.setGeometry(geom)
        except Exception:
            self.setGeometry(0, 0, 1920, 1080)

    @Slot(int, int, int, int, str, float)
    def show_target(self, x: int, y: int, w: int = 160, h: int = 44, label: str = "", duration: float = 0.0):
        """
        Highlights target centered at (x, y) with dimensions (w, h).
        duration=0 means stay visible until hide_target() is called.
        """
        if x < 0 or y < 0:
            return

        # Center rect around (x, y) if w, h provided
        left = max(0, x - w // 2)
        top = max(0, y - h // 2)
        self.target_rect = QRect(left, top, max(w, 80), max(h, 36))
        self.target_label = label
        self.pulse_phase = 0.0

        # Match screen size
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

        self.show()
        self.raise_()
        self.anim_timer.start()

        if duration > 0:
            self.auto_dismiss_timer.start(int(duration * 1000))
        else:
            self.auto_dismiss_timer.stop()

        self.update()

    @Slot()
    def hide_highlight(self):
        """Hides the highlight overlay."""
        self.anim_timer.stop()
        self.auto_dismiss_timer.stop()
        self.target_rect = None
        self.target_label = ""
        self.hide()
        self.update()

    def _on_pulse(self):
        self.pulse_phase += 0.12
        if self.pulse_phase > 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
        self.update()

    def paintEvent(self, event):
        if not self.target_rect:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self.target_rect
        pulse = 0.5 + 0.5 * math.sin(self.pulse_phase)

        # 1. Outer Neon Glow
        outer_pad = int(6 + pulse * 6)
        glow_rect = r.adjusted(-outer_pad, -outer_pad, outer_pad, outer_pad)
        glow_color = QColor(14, 165, 233, int(45 + pulse * 45))  # Cyan/Sky pulse
        glow_pen = QPen(glow_color, 4)
        p.setPen(glow_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(glow_rect, 14, 14)

        # 2. Sharp Target Border
        border_color = QColor(56, 189, 248)  # Bright Cyan
        p.setPen(QPen(border_color, 3))
        p.setBrush(QColor(14, 165, 233, 25))  # Subtle translucent fill
        p.drawRoundedRect(r, 8, 8)

        # 3. Corner Accent Markers
        corner_len = 12
        corner_pen = QPen(QColor(255, 255, 255), 3)
        p.setPen(corner_pen)
        # Top-Left
        p.drawLine(r.left(), r.top(), r.left() + corner_len, r.top())
        p.drawLine(r.left(), r.top(), r.left(), r.top() + corner_len)
        # Top-Right
        p.drawLine(r.right(), r.top(), r.right() - corner_len, r.top())
        p.drawLine(r.right(), r.top(), r.right(), r.top() + corner_len)
        # Bottom-Left
        p.drawLine(r.left(), r.bottom(), r.left() + corner_len, r.bottom())
        p.drawLine(r.left(), r.bottom(), r.left(), r.bottom() - corner_len)
        # Bottom-Right
        p.drawLine(r.right(), r.bottom(), r.right() - corner_len, r.bottom())
        p.drawLine(r.right(), r.bottom(), r.right(), r.bottom() - corner_len)

        # 4. Floating Badge with AI Label
        if self.target_label:
            badge_text = f"🎯 AI Highlight: {self.target_label}"
            font = QFont("Segoe UI", 11, QFont.Weight.Bold)
            p.setFont(font)
            metrics = p.fontMetrics()
            text_w = metrics.horizontalAdvance(badge_text) + 24
            badge_h = 28

            # Position badge above target if room, else below
            badge_y = r.top() - badge_h - 8
            if badge_y < 10:
                badge_y = r.bottom() + 8
            badge_x = max(10, r.center().x() - text_w // 2)

            badge_rect = QRect(badge_x, badge_y, text_w, badge_h)
            path = QPainterPath()
            path.addRoundedRect(badge_rect, 14, 14)
            p.fillPath(path, QBrush(QColor(15, 23, 42, 230)))  # Dark slate background
            p.setPen(QPen(QColor(56, 189, 248), 1.5))
            p.drawPath(path)

            p.setPen(QColor(248, 250, 252))
            p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        p.end()


# Global Singleton Controller for cross-thread access
_global_highlighter: Optional[VisualHighlightOverlay] = None
_signals = HighlighterSignals()


def initialize_highlighter(app: Optional[QApplication] = None) -> VisualHighlightOverlay:
    global _global_highlighter
    if _global_highlighter is None:
        _global_highlighter = VisualHighlightOverlay()
        _signals.show_highlight.connect(_global_highlighter.show_target)
        _signals.hide_highlight.connect(_global_highlighter.hide_highlight)
    return _global_highlighter


def highlight_element(x: int, y: int, w: int = 160, h: int = 44, label: str = "", duration: float = 0.0):
    """Safely triggers highlight across Qt or background threads."""
    _signals.show_highlight.emit(x, y, w, h, label, duration)


def clear_highlight():
    """Hides active highlight overlay."""
    _signals.hide_highlight.emit()
