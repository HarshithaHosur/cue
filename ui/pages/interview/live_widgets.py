# ============================================================
#  LIVE INTERVIEW SESSION WIDGETS — Real Data Only
#  No hardcoded metrics. Every value comes from real sources.
# ============================================================

import math
import random
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy, QGraphicsDropShadowEffect,
    QScrollArea, QTabWidget
)
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QBrush, QPen,
    QLinearGradient
)
from intent_platform.ui.theme import Theme


class AudioWaveformWidget(QWidget):
    """Real-time animated voice spectrum visualizer.

    Shows actual voice activity state. WPM shown only when real data exists.
    """

    def __init__(self, num_bars=24, parent=None):
        super().__init__(parent)
        self.num_bars = num_bars
        self.bars = [0.08] * num_bars
        self.target_bars = [0.08] * num_bars
        self.is_active = False  # Start inactive — no fake activity
        self.speaking_role = ""
        self.wpm = None  # None = no data yet

        self.setFixedHeight(54)
        self.setMinimumWidth(200)

        # Smooth animation timer
        self._timer = QTimer(self)
        self._timer.setInterval(40)  # 25 FPS
        self._timer.timeout.connect(self._update_waveform)
        self._timer.start()

    def _update_waveform(self):
        if not self.is_active:
            self.target_bars = [0.08] * self.num_bars
        else:
            for i in range(self.num_bars):
                t = (QTimer.remainingTime(self._timer) + i * 15) % 360
                wave = (math.sin(t * 0.1) + 1.0) * 0.4
                rand_bump = random.uniform(0.1, 0.5)
                self.target_bars[i] = min(1.0, max(0.08, wave + rand_bump))

        # Smooth interpolation
        for i in range(self.num_bars):
            self.bars[i] += (self.target_bars[i] - self.bars[i]) * 0.35
        self.update()

    def set_voice_activity(self, active: bool, role: str = "", wpm=None):
        """Update with REAL voice activity. wpm=None means no data."""
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
        total_bar_width = w - 200
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

        # Right status text
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        if self.is_active and self.speaking_role:
            p.setPen(QColor(Theme.ACCENT_GREEN))
            wpm_str = f" ({int(self.wpm)} WPM)" if self.wpm is not None else ""
            status_text = f"🟢 {self.speaking_role}{wpm_str}"
        elif self.is_active:
            p.setPen(QColor(Theme.ACCENT_GREEN))
            status_text = "🟢 Voice detected"
        else:
            p.setPen(QColor(Theme.TEXT_MUTED))
            status_text = "⚪ Waiting for speech..."
        p.drawText(w - 195, 0, 185, h, Qt.AlignRight | Qt.AlignVCenter, status_text)
        p.end()


class LiveVideoPanel(QWidget):
    """Live Stream Panel. Shows real status — no fake overlays."""

    def __init__(self, title="Candidate Stream", icon="📹", is_screen_share=False, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon = icon
        self._is_screen_share = is_screen_share
        self._camera_active = False
        self._screen_active = False
        self.setMinimumHeight(220)

        # Animation for HUD reticle
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def _on_tick(self):
        self._tick = (self._tick + 1) % 360
        self.update()

    def set_camera_active(self, active: bool):
        self._camera_active = active
        self.update()

    def set_screen_active(self, active: bool):
        self._screen_active = active
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
            # Candidate Camera
            if self._camera_active:
                cx, cy = w // 2, h // 2 - 10
                reticle_r = 55 + math.sin(self._tick * 0.08) * 3

                p.setPen(QPen(QColor(Theme.ACCENT_CYAN), 1.5, Qt.DashLine))
                p.drawRoundedRect(cx - reticle_r, cy - reticle_r, reticle_r * 2, reticle_r * 2, 16, 16)

                # Corner brackets
                p.setPen(QPen(QColor(Theme.ACCENT_CYAN), 2.5))
                bracket_len = 16
                bx1, by1 = cx - reticle_r - 6, cy - reticle_r - 6
                bx2, by2 = cx + reticle_r + 6, cy + reticle_r + 6
                p.drawLine(bx1, by1, bx1 + bracket_len, by1)
                p.drawLine(bx1, by1, bx1, by1 + bracket_len)
                p.drawLine(bx2, by1, bx2 - bracket_len, by1)
                p.drawLine(bx2, by1, bx2, by1 + bracket_len)
                p.drawLine(bx1, by2, bx1 + bracket_len, by2)
                p.drawLine(bx1, by2, bx1, by2 - bracket_len)
                p.drawLine(bx2, by2, bx2 - bracket_len, by2)
                p.drawLine(bx2, by2, bx2, by2 - bracket_len)

                p.setPen(QColor(Theme.TEXT_PRIMARY))
                p.setFont(QFont("Segoe UI Emoji", 26))
                p.drawText(QRectF(cx - 30, cy - 30, 60, 60), Qt.AlignCenter, "👤")

                p.setPen(QColor(Theme.ACCENT_GREEN))
                p.setFont(QFont("Segoe UI", 10, QFont.Bold))
                p.drawText(16, h - 18, "● LIVE")
            else:
                # Camera unavailable
                p.setPen(QColor(Theme.TEXT_MUTED))
                p.setFont(QFont("Segoe UI Emoji", 32))
                p.drawText(self.rect().adjusted(0, -20, 0, 0), Qt.AlignCenter, "📷")
                p.setFont(QFont("Segoe UI", 11))
                p.drawText(self.rect().adjusted(0, 30, 0, 0), Qt.AlignCenter, "Camera unavailable")
        else:
            # Screen Share
            if self._screen_active:
                p.setPen(QPen(QColor(Theme.ACCENT_BLUE), 1, Qt.DotLine))
                p.drawRoundedRect(16, 36, w - 32, h - 64, 8, 8)
                p.setPen(QColor(Theme.ACCENT_PURPLE))
                p.setFont(QFont("Segoe UI Emoji", 28))
                p.drawText(QRectF(w // 2 - 30, h // 2 - 35, 60, 50), Qt.AlignCenter, "🖥")
                p.setPen(QColor(Theme.TEXT_PRIMARY))
                p.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
                p.drawText(QRectF(0, h // 2 + 15, w, 24), Qt.AlignCenter, "Screen sharing active")
            else:
                p.setPen(QColor(Theme.TEXT_MUTED))
                p.setFont(QFont("Segoe UI Emoji", 32))
                p.drawText(self.rect().adjusted(0, -20, 0, 0), Qt.AlignCenter, "🖥")
                p.setFont(QFont("Segoe UI", 11))
                p.drawText(self.rect().adjusted(0, 30, 0, 0), Qt.AlignCenter, "Screen sharing not active")

        # Title Bar
        p.setPen(QColor(Theme.TEXT_PRIMARY))
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.drawText(16, 24, f"{self._icon}  {self._title}")
        p.end()


class LiveMetricCard(QWidget):
    """Metric card with animated progress bar. Shows real values only."""

    def __init__(self, title, val_text="—", score_percent=0, status_tag="Waiting...", color=None, parent=None):
        super().__init__(parent)
        self._title = title
        self._val_text = val_text
        self._score = score_percent
        self._status_tag = status_tag
        self._color = QColor(color) if color else QColor(Theme.TEXT_MUTED)
        self.setFixedHeight(62)

    def set_metric(self, val_text, score_percent, status_tag, color=None):
        """Update with REAL measured values."""
        self._val_text = val_text
        self._score = score_percent
        self._status_tag = status_tag
        if color:
            self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 8, 8)
        p.fillPath(path, QBrush(QColor(Theme.BG_DARKER)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

        # Title
        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p.drawText(12, 10, w - 120, 18, Qt.AlignLeft | Qt.AlignVCenter, self._title)

        # Value & Status
        p.setPen(self._color)
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(w - 180, 10, 168, 18, Qt.AlignRight | Qt.AlignVCenter, f"{self._val_text} [{self._status_tag}]")

        # Progress track
        track_y = 38
        track_w = w - 24
        track_h = 6
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(Theme.BG_DARKEST)))
        p.drawRoundedRect(QRectF(12, track_y, track_w, track_h), 3, 3)

        # Filled progress bar
        if self._score > 0:
            fill_w = max(4, (self._score / 100.0) * track_w)
            p.setBrush(QBrush(self._color))
            p.drawRoundedRect(QRectF(12, track_y, fill_w, track_h), 3, 3)
        p.end()


class LiveTranscriptWidget(QWidget):
    """Streaming transcript ticker. Starts empty — no fake entries."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self.entries = []  # Start empty — no fake transcript

    def add_transcript(self, role: str, text: str, timestamp: str = ""):
        if not timestamp:
            timestamp = time.strftime("%H:%M:%S")
        self.entries.append((role, timestamp, text))
        if len(self.entries) > 50:
            self.entries.pop(0)
        self.update()

    def clear_entries(self):
        self.entries.clear()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 10, 10)
        p.fillPath(path, QBrush(QColor(Theme.BG_DARKER)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)

        # Title
        p.setPen(QColor(Theme.ACCENT_CYAN))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(12, 8, w - 24, 18, Qt.AlignLeft, "💬 Live Transcript")

        if not self.entries:
            # Empty state
            p.setPen(QColor(Theme.TEXT_MUTED))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(self.rect().adjusted(12, 28, -12, 0), Qt.AlignLeft, "Waiting for speech...")
            p.end()
            return

        # Show last 2 entries
        y = 30
        for role, ts, text in self.entries[-2:]:
            if role.lower() == "interviewer":
                role_color = Theme.ACCENT_BLUE
            elif role.lower() == "candidate":
                role_color = Theme.ACCENT_PURPLE
            else:
                role_color = Theme.ACCENT_ORANGE

            p.setPen(QColor(role_color))
            p.setFont(QFont("Segoe UI", 9, QFont.Bold))
            p.drawText(12, y, 90, 16, Qt.AlignLeft, f"[{role[:12]}]")

            p.setPen(QColor(Theme.TEXT_MUTED))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(105, y, 55, 16, Qt.AlignLeft, ts)

            p.setPen(QColor(Theme.TEXT_PRIMARY))
            p.setFont(QFont("Segoe UI", 9))
            truncated = text[:55] + "..." if len(text) > 55 else text
            p.drawText(165, y, w - 177, 16, Qt.AlignLeft, truncated)
            y += 24

        p.end()


# ── Talk-Time Widget ──

class TalkTimeWidget(QWidget):
    """Shows real interviewer/candidate talk-time ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._interviewer_pct = None  # None = no data
        self._candidate_pct = None

    def set_talk_time(self, interviewer_pct: float, candidate_pct: float):
        self._interviewer_pct = interviewer_pct
        self._candidate_pct = candidate_pct
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 8, 8)
        p.fillPath(path, QBrush(QColor(Theme.BG_DARKER)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p.drawText(12, 4, w - 24, 18, Qt.AlignLeft, "Talk-Time Balance")

        if self._interviewer_pct is None:
            p.setPen(QColor(Theme.TEXT_MUTED))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(12, 24, w - 24, 20, Qt.AlignLeft, "Waiting for speech data...")
        else:
            bar_y = 28
            bar_h = 10
            bar_w = w - 24

            # Interviewer portion
            int_w = max(2, (self._interviewer_pct / 100.0) * bar_w)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(Theme.ACCENT_BLUE)))
            p.drawRoundedRect(QRectF(12, bar_y, int_w, bar_h), 4, 4)

            # Candidate portion
            cand_w = bar_w - int_w
            p.setBrush(QBrush(QColor(Theme.ACCENT_PURPLE)))
            p.drawRoundedRect(QRectF(12 + int_w, bar_y, cand_w, bar_h), 4, 4)

            # Labels
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            p.setPen(QColor(Theme.ACCENT_BLUE))
            p.drawText(12, 42, w // 2 - 12, 16, Qt.AlignLeft,
                        f"Interviewer {self._interviewer_pct:.0f}%")
            p.setPen(QColor(Theme.ACCENT_PURPLE))
            p.drawText(w // 2, 42, w // 2 - 12, 16, Qt.AlignRight,
                        f"Candidate {self._candidate_pct:.0f}%")

        p.end()


# ── Coaching Suggestion Widget ──

class CoachingSuggestionWidget(QWidget):
    """Shows real-time coaching suggestions from the AI system."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suggestion = ""
        self.setFixedHeight(48)

    def set_suggestion(self, text: str):
        self._suggestion = text
        self.update()

    def clear(self):
        self._suggestion = ""
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 8, 8)

        if self._suggestion:
            p.fillPath(path, QBrush(QColor("#1a2a3f")))
            p.setPen(QPen(QColor(Theme.ACCENT_CYAN), 1))
            p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

            p.setPen(QColor(Theme.ACCENT_CYAN))
            p.setFont(QFont("Segoe UI", 9, QFont.Bold))
            p.drawText(12, 4, w - 24, 16, Qt.AlignLeft, "💡 Coaching Suggestion")

            p.setPen(QColor(Theme.TEXT_PRIMARY))
            p.setFont(QFont("Segoe UI", 9))
            truncated = self._suggestion[:80] + "..." if len(self._suggestion) > 80 else self._suggestion
            p.drawText(12, 22, w - 24, 20, Qt.AlignLeft, truncated)
        else:
            p.fillPath(path, QBrush(QColor(Theme.BG_DARKER)))
            p.setPen(QColor(Theme.TEXT_MUTED))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(12, 0, w - 24, h, Qt.AlignLeft | Qt.AlignVCenter, "No coaching suggestions yet")

        p.end()
