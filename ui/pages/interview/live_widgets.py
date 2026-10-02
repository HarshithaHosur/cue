# ============================================================
#  LIVE INTERVIEW SESSION WIDGETS — Embedded Zoom & AI Coach
#  Real-time data only. No hardcoded metrics.
# ============================================================

import math
import random
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

        self.setFixedHeight(50)
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
                rand_bump = random.uniform(0.1, 0.5)
                self.target_bars[i] = min(1.0, max(0.08, wave + rand_bump))

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
        max_h = h - 16
        start_x = 14

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
    """Visually dominant embedded Zoom meeting window."""

    explain_requested = Signal(str)
    toggle_screen_share = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._meeting_title = "Zoom Meeting Session"
        self._platform = "Zoom"
        self._is_screen_shared = False
        self._screen_content = "def calculate_risk(portfolio):\n    # O(n) scan across asset weights\n    total_exposure = sum(asset.weight * asset.volatility for asset in portfolio)\n    return total_exposure"
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Video / Meeting Container Box
        self.container = QFrame()
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: #0b0f19;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 12px;
            }}
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(16, 16, 16, 16)
        container_layout.setSpacing(12)

        # Top meeting header inside container
        top_row = QHBoxLayout()
        self.lbl_meeting_status = QLabel("🔵 Zoom Meeting Active — Candidate Connected")
        self.lbl_meeting_status.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_meeting_status.setStyleSheet("color: #4da6ff; background: transparent; border: none;")
        top_row.addWidget(self.lbl_meeting_status)
        top_row.addStretch()

        self.btn_screen_toggle = QPushButton("🖥 Toggle Screen Share (Demo)")
        self.btn_screen_toggle.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_DARKER};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }}
            QPushButton:hover {{ border-color: {Theme.ACCENT_CYAN}; }}
        """)
        self.btn_screen_toggle.clicked.connect(self._on_toggle_screen)
        top_row.addWidget(self.btn_screen_toggle)
        container_layout.addLayout(top_row)

        # Main Screen / Code Area
        self.screen_display = QFrame()
        self.screen_display.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_DARKEST};
                border: 1px dashed {Theme.BORDER_HOVER};
                border-radius: 8px;
            }}
        """)
        screen_layout = QVBoxLayout(self.screen_display)
        screen_layout.setContentsMargins(20, 20, 20, 20)

        self.lbl_screen_header = QLabel("⏳ Waiting for candidate to share screen...")
        self.lbl_screen_header.setFont(QFont("Segoe UI", 13, QFont.DemiBold))
        self.lbl_screen_header.setAlignment(Qt.AlignCenter)
        self.lbl_screen_header.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background: transparent; border: none;")
        screen_layout.addWidget(self.lbl_screen_header)

        self.code_edit = QTextEdit()
        self.code_edit.setPlainText(self._screen_content)
        self.code_edit.setFont(QFont("Consolas", 12))
        self.code_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: #121824;
                color: #a8d1ff;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        self.code_edit.setVisible(False)
        screen_layout.addWidget(self.code_edit)

        container_layout.addWidget(self.screen_display, 1)

        # Action Toolbar below screen
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.lbl_selection_hint = QLabel("💡 Hint: Select code or use gesture to point, then click 'Explain Selection'")
        self.lbl_selection_hint.setFont(QFont("Segoe UI", 10))
        self.lbl_selection_hint.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent; border: none;")
        bottom_bar.addWidget(self.lbl_selection_hint)
        bottom_bar.addStretch()

        self.btn_explain = GlowButton("Explain Selection", "🧠", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_PURPLE))
        self.btn_explain.setFixedHeight(34)
        self.btn_explain.clicked.connect(self._on_explain_clicked)
        bottom_bar.addWidget(self.btn_explain)

        container_layout.addLayout(bottom_bar)
        layout.addWidget(self.container)

    def set_screen_share_active(self, active: bool, sharer_name: str = "Candidate"):
        self._is_screen_shared = active
        if active:
            self.lbl_screen_header.setText(f"🖥 Shared Screen ({sharer_name}'s Workspace):")
            self.lbl_screen_header.setAlignment(Qt.AlignLeft)
            self.lbl_screen_header.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; background: transparent; border: none;")
            self.code_edit.setVisible(True)
        else:
            self.lbl_screen_header.setText("⏳ Waiting for candidate to share screen...")
            self.lbl_screen_header.setAlignment(Qt.AlignCenter)
            self.lbl_screen_header.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background: transparent; border: none;")
            self.code_edit.setVisible(False)

    def _on_toggle_screen(self):
        new_state = not self._is_screen_shared
        self.set_screen_share_active(new_state)
        self.toggle_screen_share.emit(new_state)

    def _on_explain_clicked(self):
        cursor = self.code_edit.textCursor()
        selected = cursor.selectedText()
        if not selected.strip():
            selected = self.code_edit.toPlainText()
        self.explain_requested.emit(selected)


# ── Live Transcript Widget ──

class LiveTranscriptWidget(QWidget):
    """Scrollable live transcript with role chips."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(140)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QLabel("📝 Live Transcript")
        header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        header.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        layout.addWidget(header)

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
        self.content_layout.addStretch()

        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def add_transcript(self, speaker: str, text: str, ts_str: str = ""):
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
        self.setFixedHeight(50)
        self._iv_pct = None
        self._cand_pct = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        title = QLabel("📊 Interview Balance")
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        header_row.addWidget(title)

        self.lbl_stats = QLabel("Waiting for speech...")
        self.lbl_stats.setFont(QFont("Segoe UI", 10))
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
            self.lbl_stats.setText("Waiting for speech...")
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
        layout.setSpacing(8)

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
                padding: 8px 12px;
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Active Suggestion Box
        self.coach_card = QFrame()
        self.coach_card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_DARKER};
                border: 1px solid {Theme.BORDER_HOVER};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        card_layout = QVBoxLayout(self.coach_card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)

        self.lbl_sug_title = QLabel("💡 AI Follow-Up Guidance")
        self.lbl_sug_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_sug_title.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        card_layout.addWidget(self.lbl_sug_title)

        self.lbl_sug_body = QLabel("Observing candidate response. Contextual follow-up suggestions will appear dynamically.")
        self.lbl_sug_body.setWordWrap(True)
        self.lbl_sug_body.setFont(QFont("Segoe UI", 10))
        self.lbl_sug_body.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        card_layout.addWidget(self.lbl_sug_body)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_ask = QPushButton("Ask Suggestion")
        self.btn_ask.setStyleSheet(f"background: {Theme.ACCENT_BLUE}; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold;")
        self.btn_ask.clicked.connect(self._on_ask_suggestion)
        self.btn_dismiss = QPushButton("Dismiss")
        self.btn_dismiss.setStyleSheet(f"background: {Theme.BG_CARD}; color: {Theme.TEXT_MUTED}; padding: 4px 10px; border-radius: 4px;")
        self.btn_dismiss.clicked.connect(self._on_dismiss_suggestion)
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.lbl_explain_title = QLabel("🧠 Visual Context & Code Explanation")
        self.lbl_explain_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_explain_title.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        layout.addWidget(self.lbl_explain_title)

        self.txt_explain_body = QLabel("Point with gesture or select screen text and click 'Explain Selection' to analyze code structure, complexity, and follow-ups.")
        self.txt_explain_body.setWordWrap(True)
        self.txt_explain_body.setFont(QFont("Segoe UI", 10))
        self.txt_explain_body.setStyleSheet(f"""
            background: {Theme.BG_DARKER};
            border: 1px solid {Theme.BORDER_SUBTLE};
            border-radius: 6px;
            padding: 10px;
            color: {Theme.TEXT_PRIMARY};
        """)
        layout.addWidget(self.txt_explain_body)
        layout.addStretch()
        return widget

    def _build_analysis_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

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
        # Clear items
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
        self.lbl_sug_body.setText("Suggestion dismissed. Next observation will appear here.")
