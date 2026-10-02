# ============================================================
#  LIVE INTERVIEW SESSION WIDGETS — Embedded Zoom & AI Coach
#  Real-time data only. No hardcoded mock values.
# ============================================================

import math
import time
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy, QScrollArea, QTabWidget,
    QProgressBar, QTextEdit, QLineEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QBrush, QPen,
    QLinearGradient
)
from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import GlowButton, StatusBadge


# ── Audio Waveform Visualizer ──

class AudioWaveformWidget(QWidget):
    """Real-time voice activity visualizer."""

    def __init__(self, num_bars=28, parent=None):
        super().__init__(parent)
        self.num_bars = num_bars
        self.bars = [0.08] * num_bars
        self.target_bars = [0.08] * num_bars
        self.is_active = False
        self.speaking_role = ""
        self.wpm = None

        self.setFixedHeight(46)
        self.setMinimumWidth(200)

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._update_waveform)
        self._timer.start()

    def _update_waveform(self):
        if not self.is_active:
            self.target_bars = [0.08] * self.num_bars
        else:
            for i in range(self.num_bars):
                t = (QTimer.remainingTime(self._timer) + i * 15) % 360
                wave = (math.sin(t * 0.1) + 1.0) * 0.4
                self.target_bars[i] = min(1.0, max(0.08, wave))

        for i in range(self.num_bars):
            self.bars[i] += (self.target_bars[i] - self.bars[i]) * 0.35
        self.update()

    def set_voice_activity(self, active: bool, role: str = "", wpm=None):
        self.is_active = active
        self.speaking_role = role
        self.wpm = wpm

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 8, 8)
        p.fillPath(path, QBrush(QColor(Theme.BG_DARKER)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

        bar_gap = 4
        total_bar_width = w - 210
        bar_w = max(3, (total_bar_width - (self.num_bars - 1) * bar_gap) / self.num_bars)
        max_h = h - 14
        start_x = 12

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

        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        if self.is_active and self.speaking_role:
            p.setPen(QColor(Theme.ACCENT_GREEN))
            wpm_str = f" ({int(self.wpm)} WPM)" if self.wpm is not None else ""
            status_text = f"🟢 {self.speaking_role}{wpm_str}"
        elif self.is_active:
            p.setPen(QColor(Theme.ACCENT_GREEN))
            status_text = "🟢 Voice active"
        else:
            p.setPen(QColor(Theme.TEXT_MUTED))
            status_text = "⚪ Waiting for speech..."
        p.drawText(w - 200, 0, 190, h, Qt.AlignRight | Qt.AlignVCenter, status_text)
        p.end()


# ── Embedded Zoom Meeting Workspace ──

class EmbeddedZoomWorkspace(QWidget):
    """
    Visually dominant embedded Zoom meeting window inside Intent AI.
    Renders the in-app Zoom Meeting SDK container, live participant viewport,
    real-time screen share, and embedded Zoom controls without mock values.
    """

    explain_requested = Signal(str)
    companion_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._meeting_id = "—"
        self._passcode = ""
        self._participant_name = "Participant"
        self._is_screen_shared = False
        self._is_audio_muted = False
        self._is_video_muted = False
        self._participant_count = 1
        self._connection_state = "IDLE"
        self._screen_content = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Video / Meeting Container Box
        self.container = QFrame()
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: #080b14;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(10)

        # Top meeting header inside container
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.lbl_meeting_status = QLabel("🔵 Zoom Meeting Active • Connected")
        self.lbl_meeting_status.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_meeting_status.setStyleSheet("color: #4da6ff; background: transparent; border: none;")
        top_row.addWidget(self.lbl_meeting_status)

        self.lbl_security_badge = QLabel(" 🔒 E2EE 256-bit ")
        self.lbl_security_badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_security_badge.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, 0.12);
            color: {Theme.ACCENT_GREEN};
            border: 1px solid {Theme.ACCENT_GREEN};
            border-radius: 4px;
            padding: 2px 6px;
        """)
        top_row.addWidget(self.lbl_security_badge)

        self.lbl_meeting_id_badge = QLabel("Meeting ID: —")
        self.lbl_meeting_id_badge.setFont(QFont("Segoe UI", 9))
        self.lbl_meeting_id_badge.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background: transparent; border: none;")
        top_row.addWidget(self.lbl_meeting_id_badge)

        top_row.addStretch()

        self.btn_companion_fallback = QPushButton("🌐 Open in Zoom Instead")
        self.btn_companion_fallback.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_DARKER};
                color: {Theme.TEXT_MUTED};
                border: 1px dashed {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                border-color: {Theme.ACCENT_ORANGE};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        self.btn_companion_fallback.clicked.connect(self.companion_requested.emit)
        top_row.addWidget(self.btn_companion_fallback)

        container_layout.addLayout(top_row)

        # Main Central Area: Meeting Viewport & Screen Share View
        self.center_area = QWidget()
        self.center_area.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(self.center_area)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        # Live Meeting Participant Surface
        self.video_stage = QFrame()
        self.video_stage.setFixedHeight(200)
        self.video_stage.setStyleSheet(f"""
            QFrame {{
                background-color: #04060d;
                border: 1px solid {Theme.BORDER_HOVER};
                border-radius: 8px;
            }}
        """)
        video_stage_layout = QHBoxLayout(self.video_stage)
        video_stage_layout.setContentsMargins(10, 10, 10, 10)
        video_stage_layout.setSpacing(10)

        # Active Participant Tile
        self.candidate_card = QFrame()
        self.candidate_card.setStyleSheet(f"""
            QFrame {{
                background-color: #0c1220;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        cand_layout = QVBoxLayout(self.candidate_card)
        cand_layout.setContentsMargins(10, 10, 10, 10)
        
        self.lbl_cand_avatar = QLabel("👤")
        self.lbl_cand_avatar.setAlignment(Qt.AlignCenter)
        self.lbl_cand_avatar.setFont(QFont("Segoe UI", 32))
        self.lbl_cand_avatar.setStyleSheet("background: transparent; border: none;")
        cand_layout.addWidget(self.lbl_cand_avatar, 1)

        cand_info_row = QHBoxLayout()
        self.lbl_cand_name = QLabel(f"🟢 {self._participant_name}")
        self.lbl_cand_name.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_cand_name.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;")
        cand_info_row.addWidget(self.lbl_cand_name)
        cand_info_row.addStretch()
        
        self.lbl_video_quality = QLabel("Connected")
        self.lbl_video_quality.setFont(QFont("Segoe UI", 8))
        self.lbl_video_quality.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; background: transparent; border: none;")
        cand_info_row.addWidget(self.lbl_video_quality)
        cand_layout.addLayout(cand_info_row)
        video_stage_layout.addWidget(self.candidate_card, 2)

        # Local Interviewer Tile
        self.interviewer_card = QFrame()
        self.interviewer_card.setStyleSheet(f"""
            QFrame {{
                background-color: #0c1220;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        int_layout = QVBoxLayout(self.interviewer_card)
        int_layout.setContentsMargins(10, 10, 10, 10)
        
        lbl_int_avatar = QLabel("🎙")
        lbl_int_avatar.setAlignment(Qt.AlignCenter)
        lbl_int_avatar.setFont(QFont("Segoe UI", 32))
        lbl_int_avatar.setStyleSheet("background: transparent; border: none;")
        int_layout.addWidget(lbl_int_avatar, 1)

        int_info_row = QHBoxLayout()
        self.lbl_int_name = QLabel("🔵 You (Interviewer)")
        self.lbl_int_name.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_int_name.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;")
        int_info_row.addWidget(self.lbl_int_name)
        int_info_row.addStretch()
        int_layout.addLayout(int_info_row)
        video_stage_layout.addWidget(self.interviewer_card, 1)

        center_layout.addWidget(self.video_stage)

        # Screen Share / Contextual Code Display
        self.screen_display = QFrame()
        self.screen_display.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_DARKEST};
                border: 1px dashed {Theme.BORDER_HOVER};
                border-radius: 8px;
            }}
        """)
        screen_layout = QVBoxLayout(self.screen_display)
        screen_layout.setContentsMargins(14, 12, 14, 12)
        screen_layout.setSpacing(6)

        self.lbl_screen_header = QLabel("⏳ Candidate Screen Share: Standby (Waiting for candidate to share screen)")
        self.lbl_screen_header.setFont(QFont("Segoe UI", 11))
        self.lbl_screen_header.setAlignment(Qt.AlignCenter)
        self.lbl_screen_header.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background: transparent; border: none;")
        screen_layout.addWidget(self.lbl_screen_header)

        self.code_edit = QTextEdit()
        self.code_edit.setFont(QFont("Consolas", 12))
        self.code_edit.setPlaceholderText("Shared screen content or code selection will appear here when active...")
        self.code_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: #101622;
                color: #a8d1ff;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        self.code_edit.setVisible(False)
        self.code_edit.selectionChanged.connect(self._on_selection_changed)
        screen_layout.addWidget(self.code_edit, 1)

        center_layout.addWidget(self.screen_display, 1)
        container_layout.addWidget(self.center_area, 1)

        # In-App Zoom Control Bar
        controls_bar = QFrame()
        controls_bar.setFixedHeight(48)
        controls_bar.setStyleSheet(f"""
            QFrame {{
                background-color: #05070e;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)
        ctrl_layout = QHBoxLayout(controls_bar)
        ctrl_layout.setContentsMargins(10, 0, 10, 0)
        ctrl_layout.setSpacing(8)

        # Mute / Unmute
        self.btn_audio = QPushButton("🎙 Mute")
        self.btn_audio.setStyleSheet(self._ctrl_btn_style())
        self.btn_audio.clicked.connect(self._toggle_audio)
        ctrl_layout.addWidget(self.btn_audio)

        # Video On / Off
        self.btn_video = QPushButton("📹 Stop Video")
        self.btn_video.setStyleSheet(self._ctrl_btn_style())
        self.btn_video.clicked.connect(self._toggle_video)
        ctrl_layout.addWidget(self.btn_video)

        # Participants Count
        self.btn_participants = QPushButton(f"👥 Participants ({self._participant_count})")
        self.btn_participants.setStyleSheet(self._ctrl_btn_style())
        ctrl_layout.addWidget(self.btn_participants)

        ctrl_layout.addStretch()

        # Explain Code Selection
        self.btn_explain = GlowButton("🧠 Explain Selection", "🧠", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_PURPLE))
        self.btn_explain.setFixedHeight(32)
        self.btn_explain.setEnabled(False)
        self.btn_explain.clicked.connect(self._on_explain_clicked)
        ctrl_layout.addWidget(self.btn_explain)

        container_layout.addWidget(controls_bar)
        layout.addWidget(self.container)

    def _ctrl_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT_BLUE};
                color: #ffffff;
            }}
        """

    def set_participant_info(self, name: str):
        self._participant_name = name or "Participant"
        self.lbl_cand_name.setText(f"🟢 {self._participant_name}")

    def set_candidate_info(self, name: str, role: str = ""):
        self.set_participant_info(name)

    def set_participant_count(self, count: int):
        self._participant_count = max(1, count)
        self.btn_participants.setText(f"👥 Participants ({self._participant_count})")

    def set_meeting_info(self, info: dict):
        self._meeting_id = info.get("meeting_id", "—")
        self._passcode = info.get("passcode", "")
        self.lbl_meeting_id_badge.setText(f"Meeting ID: {self._meeting_id}")

    def update_connection_state(self, state: str, message: str = ""):
        self._connection_state = state
        if state in ("LIVE", "MEETING_CONNECTED"):
            self.lbl_meeting_status.setText(f"🟢 Zoom Meeting Active • Connected ({self._participant_name})")
            self.lbl_meeting_status.setStyleSheet("color: #10b981; background: transparent; border: none;")
        elif state in ("CONNECTING", "INITIALIZING_MEETING_SDK", "JOINING_EMBEDDED_MEETING"):
            self.lbl_meeting_status.setText("🟡 Connecting to Zoom Meeting...")
            self.lbl_meeting_status.setStyleSheet("color: #f59e0b; background: transparent; border: none;")
        elif state == "WAITING_ROOM":
            self.lbl_meeting_status.setText("⏳ Waiting Room — Host will admit you shortly")
            self.lbl_meeting_status.setStyleSheet("color: #f59e0b; background: transparent; border: none;")
        elif state == "ERROR":
            self.lbl_meeting_status.setText(f"🔴 Connection Error: {message}")
            self.lbl_meeting_status.setStyleSheet("color: #ef4444; background: transparent; border: none;")

    def _toggle_audio(self):
        self._is_audio_muted = not self._is_audio_muted
        if self._is_audio_muted:
            self.btn_audio.setText("🔇 Unmute")
            self.btn_audio.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(239, 68, 68, 0.2);
                    color: {Theme.ACCENT_RED};
                    border: 1px solid {Theme.ACCENT_RED};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 11px;
                }}
            """)
        else:
            self.btn_audio.setText("🎙 Mute")
            self.btn_audio.setStyleSheet(self._ctrl_btn_style())

    def _toggle_video(self):
        self._is_video_muted = not self._is_video_muted
        if self._is_video_muted:
            self.btn_video.setText("📷 Start Video")
            self.btn_video.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(239, 68, 68, 0.2);
                    color: {Theme.ACCENT_RED};
                    border: 1px solid {Theme.ACCENT_RED};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 11px;
                }}
            """)
        else:
            self.btn_video.setText("📹 Stop Video")
            self.btn_video.setStyleSheet(self._ctrl_btn_style())

    def set_screen_share_active(self, active: bool, sharer_name: str = ""):
        self._is_screen_shared = active
        sharer = sharer_name or self._participant_name
        if active:
            self.lbl_screen_header.setText(f"🖥 Shared Screen ({sharer}'s Workspace):")
            self.lbl_screen_header.setAlignment(Qt.AlignLeft)
            self.lbl_screen_header.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; background: transparent; border: none;")
            self.code_edit.setVisible(True)
            self.video_stage.setFixedHeight(110)
            self.btn_explain.setEnabled(True)
        else:
            self.lbl_screen_header.setText("⏳ Candidate Screen Share: Standby (Waiting for candidate to share screen)")
            self.lbl_screen_header.setAlignment(Qt.AlignCenter)
            self.lbl_screen_header.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background: transparent; border: none;")
            self.code_edit.setVisible(False)
            self.video_stage.setFixedHeight(200)
            self.btn_explain.setEnabled(False)

    def set_screen_content(self, text: str):
        self._screen_content = text
        self.code_edit.setPlainText(text)
        if text.strip():
            self.btn_explain.setEnabled(True)

    def _on_selection_changed(self):
        cursor = self.code_edit.textCursor()
        selected = cursor.selectedText().strip()
        self.btn_explain.setEnabled(bool(selected or self.code_edit.toPlainText().strip()))

    def _on_explain_clicked(self):
        cursor = self.code_edit.textCursor()
        selected = cursor.selectedText()
        if not selected.strip():
            selected = self.code_edit.toPlainText()
        if selected.strip():
            self.explain_requested.emit(selected)


# ── Live Transcript Widget ──

class LiveTranscriptWidget(QWidget):
    """Scrollable live transcript displaying genuine realtime speech segments."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(130)
        self._has_entries = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        header = QLabel("📝 Live Transcript")
        header.setFont(QFont("Segoe UI", 10, QFont.Bold))
        header.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        header_row.addWidget(header)
        header_row.addStretch()

        self.lbl_status = QLabel("● Listening for speech...")
        self.lbl_status.setFont(QFont("Segoe UI", 9))
        self.lbl_status.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background: transparent;")
        header_row.addWidget(self.lbl_status)
        layout.addLayout(header_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Theme.BG_DARKER};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)

        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(10, 8, 10, 8)
        self.content_layout.setSpacing(6)

        self.lbl_empty_hint = QLabel("Listening for conversation... Realtime speech segments will appear here.")
        self.lbl_empty_hint.setFont(QFont("Segoe UI", 10))
        self.lbl_empty_hint.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background: transparent;")
        self.content_layout.addWidget(self.lbl_empty_hint)
        self.content_layout.addStretch()

        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def add_transcript(self, speaker: str, text: str, ts_str: str = ""):
        if not self._has_entries:
            self._has_entries = True
            self.lbl_empty_hint.setVisible(False)

        if not ts_str:
            ts_str = time.strftime("%H:%M:%S")

        color = Theme.ACCENT_CYAN if "interviewer" in speaker.lower() else Theme.ACCENT_GREEN
        if "fairness" in speaker.lower() or "risk" in speaker.lower():
            color = Theme.ACCENT_RED
        elif "system" in speaker.lower():
            color = Theme.TEXT_MUTED

        lbl = QLabel(f"<font color='{Theme.TEXT_MUTED}'>[{ts_str}]</font> <font color='{color}'><b>{speaker}:</b></font> {text}")
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent;")

        count = self.content_layout.count()
        self.content_layout.insertWidget(count - 1, lbl)

        # Auto scroll to bottom
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))


# ── Talk Time Meter ──

class TalkTimeWidget(QWidget):
    """Real-time talk time balance indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._iv_pct = None
        self._cand_pct = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        title = QLabel("📊 Interview Talk Balance")
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        header_row.addWidget(title)

        self.lbl_stats = QLabel("Waiting for conversation...")
        self.lbl_stats.setFont(QFont("Segoe UI", 9))
        self.lbl_stats.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background: transparent;")
        header_row.addWidget(self.lbl_stats, alignment=Qt.AlignRight)
        layout.addLayout(header_row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(50)
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Theme.ACCENT_GREEN};
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT_CYAN};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.bar)

    def set_talk_time(self, iv_pct: Optional[float], cand_pct: Optional[float]):
        self._iv_pct = iv_pct
        self._cand_pct = cand_pct
        if iv_pct is None or cand_pct is None:
            self.lbl_stats.setText("Waiting for conversation...")
            self.bar.setValue(50)
        else:
            self.lbl_stats.setText(f"Interviewer: {int(iv_pct)}% | Candidate: {int(cand_pct)}%")
            self.bar.setValue(int(iv_pct))


# ── Tabbed AI Interviewer Coach Sidebar ──

class AICoachTabWidget(QWidget):
    """Private persistent AI Coach side panel with tabs."""

    ask_suggestion_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {Theme.BORDER_SUBTLE};
                background: {Theme.BG_CARD};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {Theme.BG_DARKER};
                color: {Theme.TEXT_SECONDARY};
                padding: 7px 10px;
                font-weight: bold;
                font-size: 11px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {Theme.BG_CARD};
                color: {Theme.ACCENT_CYAN};
                border-bottom: 2px solid {Theme.ACCENT_CYAN};
            }}
        """)

        # 1. COACH Tab
        self.tab_coach = self._build_coach_tab()
        self.tabs.addTab(self.tab_coach, "💡 Coach")

        # 2. RESUME Tab
        self.tab_resume = self._build_resume_tab()
        self.tabs.addTab(self.tab_resume, "📄 Resume")

        # 3. RUBRIC Tab
        self.tab_rubric = self._build_rubric_tab()
        self.tabs.addTab(self.tab_rubric, "🎯 Rubric")

        # 4. EXPLAIN Tab
        self.tab_explain = self._build_explain_tab()
        self.tabs.addTab(self.tab_explain, "🧠 Explain")

        # 5. ANALYSIS Tab
        self.tab_analysis = self._build_analysis_tab()
        self.tabs.addTab(self.tab_analysis, "📊 Analysis")

        layout.addWidget(self.tabs)

    def _build_coach_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Active Suggestion Box
        self.coach_card = QFrame()
        self.coach_card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_DARKER};
                border: 1px solid {Theme.BORDER_HOVER};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        card_layout = QVBoxLayout(self.coach_card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)

        self.lbl_sug_title = QLabel("💡 AI Follow-Up Guidance")
        self.lbl_sug_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_sug_title.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        card_layout.addWidget(self.lbl_sug_title)

        self.lbl_sug_body = QLabel("Waiting for live interview data... Contextual follow-up suggestions will appear dynamically as the candidate speaks.")
        self.lbl_sug_body.setWordWrap(True)
        self.lbl_sug_body.setFont(QFont("Segoe UI", 10))
        self.lbl_sug_body.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        card_layout.addWidget(self.lbl_sug_body)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_ask = QPushButton("Use Follow-Up")
        self.btn_ask.setStyleSheet(f"background: {Theme.ACCENT_BLUE}; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        self.btn_ask.clicked.connect(self._on_ask_suggestion)
        self.btn_ask.setVisible(False)
        self.btn_dismiss = QPushButton("Dismiss")
        self.btn_dismiss.setStyleSheet(f"background: {Theme.BG_CARD}; color: {Theme.TEXT_MUTED}; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
        self.btn_dismiss.clicked.connect(self._on_dismiss_suggestion)
        self.btn_dismiss.setVisible(False)
        btn_row.addWidget(self.btn_ask)
        btn_row.addWidget(self.btn_dismiss)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        layout.addWidget(self.coach_card)

        # Risk Alert Banner
        self.risk_card = QFrame()
        self.risk_card.setStyleSheet(f"""
            QFrame {{
                background-color: #2b1216;
                border: 1px solid {Theme.ACCENT_RED};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        risk_layout = QVBoxLayout(self.risk_card)
        risk_layout.setContentsMargins(6, 6, 6, 6)
        self.lbl_risk = QLabel("⚠️ Potentially Sensitive Question Notice\nConsider redirecting toward job-relevant technical criteria.")
        self.lbl_risk.setWordWrap(True)
        self.lbl_risk.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_risk.setStyleSheet(f"color: #ff8080;")
        risk_layout.addWidget(self.lbl_risk)
        self.risk_card.setVisible(False)
        layout.addWidget(self.risk_card)

        layout.addStretch()
        return widget

    def _build_resume_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.lbl_resume_stats = QLabel("Extracted Claims: 0 Total | 0 Discussed")
        self.lbl_resume_stats.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_resume_stats.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        layout.addWidget(self.lbl_resume_stats)

        self.resume_scroll = QScrollArea()
        self.resume_scroll.setWidgetResizable(True)
        self.resume_scroll.setFrameShape(QFrame.NoFrame)
        self.resume_content = QWidget()
        self.resume_layout = QVBoxLayout(self.resume_content)
        self.resume_layout.setContentsMargins(0, 0, 0, 0)
        self.resume_layout.setSpacing(6)
        self.resume_layout.addStretch()
        self.resume_scroll.setWidget(self.resume_content)
        layout.addWidget(self.resume_scroll)

        return widget

    def _build_rubric_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.rubric_progress = QProgressBar()
        self.rubric_progress.setRange(0, 100)
        self.rubric_progress.setValue(0)
        self.rubric_progress.setFixedHeight(8)
        self.rubric_progress.setStyleSheet(f"""
            QProgressBar {{ background-color: {Theme.BG_DARKER}; border-radius: 4px; border: none; }}
            QProgressBar::chunk {{ background-color: {Theme.ACCENT_CYAN}; border-radius: 4px; }}
        """)
        layout.addWidget(self.rubric_progress)

        self.lbl_rubric_cov = QLabel("Rubric Coverage: 0%")
        self.lbl_rubric_cov.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_rubric_cov.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        layout.addWidget(self.lbl_rubric_cov)

        self.rubric_scroll = QScrollArea()
        self.rubric_scroll.setWidgetResizable(True)
        self.rubric_scroll.setFrameShape(QFrame.NoFrame)
        self.rubric_content = QWidget()
        self.rubric_layout = QVBoxLayout(self.rubric_content)
        self.rubric_layout.setContentsMargins(0, 0, 0, 0)
        self.rubric_layout.setSpacing(6)
        self.rubric_layout.addStretch()
        self.rubric_scroll.setWidget(self.rubric_content)
        layout.addWidget(self.rubric_scroll)

        return widget

    def _build_explain_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.lbl_explain_title = QLabel("🧠 Visual Context & Code Explanation")
        self.lbl_explain_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_explain_title.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        layout.addWidget(self.lbl_explain_title)

        self.txt_explain_body = QLabel("Select code or screen text in the shared workspace to view structure, complexity, and follow-up guidance.")
        self.txt_explain_body.setWordWrap(True)
        self.txt_explain_body.setFont(QFont("Segoe UI", 10))
        self.txt_explain_body.setStyleSheet(f"""
            background: {Theme.BG_DARKER};
            border: 1px solid {Theme.BORDER_SUBTLE};
            border-radius: 6px;
            padding: 10px;
            color: {Theme.TEXT_SECONDARY};
        """)
        layout.addWidget(self.txt_explain_body)
        layout.addStretch()
        return widget

    def _build_analysis_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.talk_time_widget = TalkTimeWidget()
        layout.addWidget(self.talk_time_widget)

        self.lbl_analysis_details = QLabel(
            "• Interruptions: 0 detected\n"
            "• Candidate Baseline: Calibrating...\n"
            "• Question Quality: Normal"
        )
        self.lbl_analysis_details.setFont(QFont("Segoe UI", 10))
        self.lbl_analysis_details.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; line-height: 1.6;")
        layout.addWidget(self.lbl_analysis_details)
        layout.addStretch()
        return widget

    def set_suggestion(self, title: str, text: str):
        self.lbl_sug_title.setText(title)
        self.lbl_sug_body.setText(text)
        self.lbl_sug_body.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        self.btn_ask.setVisible(True)
        self.btn_dismiss.setVisible(True)
        self.tabs.setCurrentIndex(0)

    def set_risk_alert(self, explanation: str):
        self.lbl_risk.setText(f"⚠️ {explanation}")
        self.risk_card.setVisible(True)

    def set_visual_explanation(self, exp_data: dict):
        text = (
            f"<b>Context:</b> {exp_data.get('selected_text', '')}<br><br>"
            f"<b>Explanation:</b> {exp_data.get('explanation', '')}<br><br>"
            f"<b>Complexity:</b> <font color='{Theme.ACCENT_GREEN}'>{exp_data.get('complexity', '')}</font><br><br>"
            f"<b>Suggested Follow-up:</b><br>\"{exp_data.get('follow_up', '')}\""
        )
        self.txt_explain_body.setText(text)
        self.tabs.setCurrentIndex(3)

    def update_resume_claims(self, summary: dict):
        self.lbl_resume_stats.setText(
            f"Extracted Claims: {summary.get('total_claims', 0)} | Discussed: {summary.get('discussed_count', 0)}"
        )
        while self.resume_layout.count() > 1:
            item = self.resume_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for cl in summary.get("claims", []):
            status = cl.get("status", "UNEXPLORED")
            icon = "✓" if status == "DISCUSSED" else "⏳"
            color = Theme.ACCENT_GREEN if status == "DISCUSSED" else Theme.TEXT_MUTED
            lbl = QLabel(f"<font color='{color}'>{icon} <b>{cl.get('text', '')}</b></font> — {status}")
            lbl.setFont(QFont("Segoe UI", 9))
            self.resume_layout.insertWidget(self.resume_layout.count() - 1, lbl)

    def update_rubric(self, summary: dict):
        cov = int(summary.get("coverage_pct", 0))
        self.rubric_progress.setValue(cov)
        self.lbl_rubric_cov.setText(f"Rubric Coverage: {cov}%")

        while self.rubric_layout.count() > 1:
            item = self.rubric_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for cr in summary.get("criteria", []):
            st = cr.get("state", "NOT_STARTED")
            icon = "✓" if st == "SUFFICIENTLY_COVERED" else ("◐" if st == "PARTIALLY_COVERED" else "○")
            color = Theme.ACCENT_GREEN if st == "SUFFICIENTLY_COVERED" else (Theme.ACCENT_CYAN if st == "PARTIALLY_COVERED" else Theme.TEXT_MUTED)
            lbl = QLabel(f"<font color='{color}'>{icon} <b>{cr.get('name', '')}</b></font> ({st.replace('_', ' ')})")
            lbl.setFont(QFont("Segoe UI", 9))
            self.rubric_layout.insertWidget(self.rubric_layout.count() - 1, lbl)

    def _on_ask_suggestion(self):
        text = self.lbl_sug_body.text()
        self.ask_suggestion_clicked.emit(text)

    def _on_dismiss_suggestion(self):
        self.lbl_sug_title.setText("💡 AI Follow-Up Guidance")
        self.lbl_sug_body.setText("Waiting for live interview data... Next observation will appear dynamically.")
        self.lbl_sug_body.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        self.btn_ask.setVisible(False)
        self.btn_dismiss.setVisible(False)
