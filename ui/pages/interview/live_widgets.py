# ============================================================
#  LIVE INTERVIEW SESSION WIDGETS — Rich Visual Experience
# ============================================================

import math
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QBrush, QPen,
    QLinearGradient
)
from intent_platform.ui.theme import Theme


class AudioWaveformWidget(QWidget):
    """Real-time animated voice spectrum visualizer."""

    def __init__(self, num_bars=24, parent=None):
        super().__init__(parent)
        self.num_bars = num_bars
        self.bars = [0.2] * num_bars
        self.target_bars = [0.2] * num_bars
        self.is_active = True
        self.speaking_role = "Candidate"
        self.wpm = 142

        self.setFixedHeight(54)
        self.setMinimumWidth(200)

        # Smooth animation timer
        self._timer = QTimer(self)
        self._timer.setInterval(40)  # 25 FPS
        self._timer.timeout.connect(self._update_waveform)
        self._timer.start()

    def _update_waveform(self):
        if not self.is_active:
            self.target_bars = [0.1] * self.num_bars
        else:
            for i in range(self.num_bars):
                # Sine wave + random audio pulse
                t = time_factor = (QTimer.remainingTime(self._timer) + i * 15) % 360
                wave = (math.sin(t * 0.1) + 1.0) * 0.4
                rand_bump = random.uniform(0.1, 0.5)
                self.target_bars[i] = min(1.0, max(0.08, wave + rand_bump))

        # Smooth interpolation
        for i in range(self.num_bars):
            self.bars[i] += (self.target_bars[i] - self.bars[i]) * 0.35
        self.update()

    def set_voice_activity(self, active: bool, role: str = "Candidate", wpm: int = 142):
        self.is_active = active
        self.speaking_role = role
        self.wpm = wpm

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background card
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 10, 10)
        p.fillPath(path, QBrush(QColor(Theme.BG_DARKER)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)

        # Draw audio bars
        bar_gap = 4
        total_bar_width = w - 160  # Reserve space for right label
        bar_w = max(3, (total_bar_width - (self.num_bars - 1) * bar_gap) / self.num_bars)
        max_h = h - 20
        start_x = 16

        gradient = QLinearGradient(0, h, 0, 0)
        gradient.setColorAt(0.0, QColor(Theme.ACCENT_BLUE))
        gradient.setColorAt(0.6, QColor(Theme.ACCENT_CYAN))
        gradient.setColorAt(1.0, QColor(Theme.ACCENT_PURPLE))

        for i, val in enumerate(self.bars):
            bar_h = val * max_h
            bx = start_x + i * (bar_w + bar_gap)
            by = (h - bar_h) / 2

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(gradient))
            p.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), bar_w / 2, bar_w / 2)

        # Right status text & WPM pill
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(QColor(Theme.ACCENT_GREEN if self.is_active else Theme.TEXT_MUTED))
        dot = "🟢" if self.is_active else "⚪"
        status_text = f"{dot} {self.speaking_role} ({self.wpm} WPM)"
        p.drawText(w - 145, 0, 135, h, Qt.AlignRight | Qt.AlignVCenter, status_text)
        p.end()


class LiveVideoPanel(QWidget):
    """Enhanced Live Stream Panel with target reticle, stats overlay & camera status."""

    def __init__(self, title="Candidate Stream", icon="📹", is_screen_share=False, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon = icon
        self._is_screen_share = is_screen_share
        self.setMinimumHeight(220)

        # Animation for HUD reticle rotation/pulse
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def _on_tick(self):
        self._tick = (self._tick + 1) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Dark viewport container
        bg_path = QPainterPath()
        bg_path.addRoundedRect(0, 0, w, h, 12, 12)
        p.fillPath(bg_path, QBrush(QColor(Theme.BG_DARKEST)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)

        if not self._is_screen_share:
            # Candidate Camera HUD Graphics
            cx, cy = w // 2, h // 2 - 10
            reticle_r = 55 + math.sin(self._tick * 0.08) * 3

            # Face bounding box indicator (simulated MediaPipe reticle)
            p.setPen(QPen(QColor(Theme.ACCENT_CYAN), 1.5, Qt.DashLine))
            p.drawRoundedRect(cx - reticle_r, cy - reticle_r, reticle_r * 2, reticle_r * 2, 16, 16)

            # Animated HUD Corner Brackets
            p.setPen(QPen(QColor(Theme.ACCENT_CYAN), 2.5))
            bracket_len = 16
            bx1, by1 = cx - reticle_r - 6, cy - reticle_r - 6
            bx2, by2 = cx + reticle_r + 6, cy + reticle_r + 6

            # Top-Left
            p.drawLine(bx1, by1, bx1 + bracket_len, by1)
            p.drawLine(bx1, by1, bx1, by1 + bracket_len)
            # Top-Right
            p.drawLine(bx2, by1, bx2 - bracket_len, by1)
            p.drawLine(bx2, by1, bx2, by1 + bracket_len)
            # Bottom-Left
            p.drawLine(bx1, by2, bx1 + bracket_len, by2)
            p.drawLine(bx1, by2, bx1, by2 - bracket_len)
            # Bottom-Right
            p.drawLine(bx2, by2, bx2 - bracket_len, by2)
            p.drawLine(bx2, by2, bx2, by2 - bracket_len)

            # Icon in reticle center
            p.setPen(QColor(Theme.TEXT_PRIMARY))
            p.setFont(QFont("Segoe UI Emoji", 26))
            p.drawText(QRectF(cx - 30, cy - 30, 60, 60), Qt.AlignCenter, "👤")

            # HUD Live Overlay stats
            p.setPen(QColor(Theme.ACCENT_GREEN))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            p.drawText(16, h - 18, "● LIVE 1080p | 30 FPS")

            p.setPen(QColor(Theme.TEXT_SECONDARY))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(w - 190, h - 18, "Gaze: Screen | Eye Contact: 94%")
        else:
            # Screen Share Stream Graphics
            p.setPen(QPen(QColor(Theme.ACCENT_BLUE), 1, Qt.DotLine))
            p.drawRoundedRect(16, 36, w - 32, h - 64, 8, 8)

            p.setPen(QColor(Theme.ACCENT_PURPLE))
            p.setFont(QFont("Segoe UI Emoji", 28))
            p.drawText(QRectF(w // 2 - 30, h // 2 - 35, 60, 50), Qt.AlignCenter, "🖥")

            p.setPen(QColor(Theme.TEXT_PRIMARY))
            p.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
            p.drawText(QRectF(0, h // 2 + 15, w, 24), Qt.AlignCenter, "Screen Sharing: Active (VS Code)")

            p.setPen(QColor(Theme.ACCENT_CYAN))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            p.drawText(16, h - 18, "● DISPLAY #1 (1920x1080)")

        # Title Bar Top Badge
        p.setPen(QColor(Theme.TEXT_PRIMARY))
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.drawText(16, 24, f"{self._icon}  {self._title}")
        p.end()


class LiveMetricCard(QWidget):
    """Interactive visual metric card with animated progress bar."""

    def __init__(self, title, val_text, score_percent, status_tag, color, parent=None):
        super().__init__(parent)
        self._title = title
        self._val_text = val_text
        self._score = score_percent
        self._status_tag = status_tag
        self._color = QColor(color)
        self.setFixedHeight(62)

    def set_metric(self, val_text, score_percent, status_tag):
        self._val_text = val_text
        self._score = score_percent
        self._status_tag = status_tag
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background card
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 8, 8)
        p.fillPath(path, QBrush(QColor(Theme.BG_DARKER)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

        # Title
        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p.drawText(12, 10, w - 120, 18, Qt.AlignLeft | Qt.AlignVCenter, self._title)

        # Value & Status Pill
        p.setPen(self._color)
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(w - 140, 10, 128, 18, Qt.AlignRight | Qt.AlignVCenter, f"{self._val_text} [{self._status_tag}]")

        # Progress track background
        track_y = 38
        track_w = w - 24
        track_h = 6
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(Theme.BG_DARKEST)))
        p.drawRoundedRect(QRectF(12, track_y, track_w, track_h), 3, 3)

        # Filled progress bar
        fill_w = max(4, (self._score / 100.0) * track_w)
        p.setBrush(QBrush(self._color))
        p.drawRoundedRect(QRectF(12, track_y, fill_w, track_h), 3, 3)
        p.end()


class LiveTranscriptWidget(QWidget):
    """Streaming transcript ticker showing live utterances with speaker tags."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self.entries = [
            ("Interviewer", "10:14:02", "Can you explain how the concurrency model works in your approach?"),
            ("Candidate", "10:14:15", "Certainly. We utilize non-blocking async loops paired with worker threads...")
        ]

    def add_transcript(self, role: str, text: str, timestamp: str = "Live"):
        self.entries.append((role, timestamp, text))
        if len(self.entries) > 3:
            self.entries.pop(0)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Container box
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 10, 10)
        p.fillPath(path, QBrush(QColor(Theme.BG_DARKER)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)

        # Title
        p.setPen(QColor(Theme.ACCENT_CYAN))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(12, 8, w - 24, 18, Qt.AlignLeft, "💬 Live Speech Transcript Ticker")

        # Entries
        y = 30
        for role, ts, text in self.entries[-2:]:
            role_color = Theme.ACCENT_BLUE if role == "Interviewer" else Theme.ACCENT_PURPLE
            p.setPen(QColor(role_color))
            p.setFont(QFont("Segoe UI", 9, QFont.Bold))
            p.drawText(12, y, 90, 16, Qt.AlignLeft, f"[{role}]")

            p.setPen(QColor(Theme.TEXT_MUTED))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(105, y, 50, 16, Qt.AlignLeft, ts)

            p.setPen(QColor(Theme.TEXT_PRIMARY))
            p.setFont(QFont("Segoe UI", 9))
            truncated = text[:50] + "..." if len(text) > 50 else text
            p.drawText(160, y, w - 172, 16, Qt.AlignLeft, truncated)
            y += 24

        p.end()
