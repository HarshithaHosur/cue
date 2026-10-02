# ============================================================
#  AI INTERVIEW DASHBOARD — Full interview workspace
#  Uses InterviewController for all business logic.
#  No hardcoded metrics. Real data pipelines only.
# ============================================================

import time
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
    QScrollArea, QFrame, QSizePolicy, QLineEdit, QComboBox,
    QSpinBox, QTextEdit, QRadioButton, QButtonGroup, QGridLayout,
    QMessageBox, QPushButton
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QBrush, QPen,
    QLinearGradient
)
from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import (
    GlowButton, SectionHeader, SidebarNavItem, StatusBadge
)
from intent_platform.ui.pages.interview.live_widgets import (
    AudioWaveformWidget, LiveVideoPanel, LiveMetricCard,
    LiveTranscriptWidget, TalkTimeWidget, CoachingSuggestionWidget
)
from intent_platform.ui.pages.interview.report_and_settings_view import (
    PreviousInterviewsView, ReportsView, InterviewSettingsView
)
from intent_platform.core.interview.store import interview_store
from intent_platform.core.interview.models import InterviewSetup, InterviewState
from intent_platform.core.interview.controller import InterviewController, PreFlightResult

logger = logging.getLogger(__name__)


class InterviewDashboard(QWidget):
    """Complete AI Interview Agent workspace with sub-navigation.

    All business logic is delegated to InterviewController.
    """

    navigate_back = Signal()

    def __init__(self, engine=None, user_profile=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.user_profile = user_profile

        # Controller manages the full interview lifecycle
        self.controller = InterviewController()
        self._connect_controller()

        self._build_ui()

    def _connect_controller(self):
        """Connect controller signals to UI handlers."""
        self.controller.state_changed.connect(self._on_state_changed)
        self.controller.interview_started.connect(self._on_interview_started)
        self.controller.interview_ended.connect(self._on_interview_ended)
        self.controller.report_ready.connect(self._on_report_ready)
        self.controller.error_occurred.connect(self._on_error)

        # Metrics signals
        m = self.controller.metrics
        m.talk_time_updated.connect(self._on_talk_time_updated)
        m.transcript_entry.connect(self._on_transcript_entry)
        m.observation_fired.connect(self._on_observation)
        m.question_changed.connect(self._on_question_changed)
        m.fairness_alert.connect(self._on_fairness_alert)
        m.coaching_suggestion.connect(self._on_coaching_suggestion)
        m.paste_probes_generated.connect(self._on_paste_probes)

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left Panel (Sub-navigation) ──
        left_panel = QWidget()
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet(f"background-color: {Theme.SIDEBAR_BG}; border-right: 1px solid {Theme.BORDER_SUBTLE};")

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 20, 0, 20)
        left_layout.setSpacing(4)

        # Back button
        back_btn = _BackButton("← Back to Home")
        back_btn.clicked.connect(self.navigate_back.emit)
        left_layout.addWidget(back_btn)
        left_layout.addSpacing(16)

        # Title
        title_lbl = QLabel("  🎤 Interview")
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {Theme.ACCENT_BLUE}; padding: 8px 12px; background: transparent;")
        left_layout.addWidget(title_lbl)
        left_layout.addSpacing(8)

        # Nav items
        self._nav_items = []
        nav_data = [
            ("iv_dashboard", "📊", "Dashboard"),
            ("iv_create", "➕", "Create Interview"),
            ("iv_live", "🔴", "Live Interview"),
            ("iv_previous", "📋", "Previous"),
            ("iv_reports", "📄", "Reports"),
            ("iv_settings", "⚙", "Settings"),
        ]
        for page_id, icon, label in nav_data:
            item = SidebarNavItem(page_id, icon, label)
            item.clicked.connect(self._on_nav_click)
            left_layout.addWidget(item)
            self._nav_items.append(item)

        left_layout.addStretch()
        layout.addWidget(left_panel)

        # ── Content Area (Stacked) ──
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        # Sub-pages
        self.previous_page = PreviousInterviewsView()
        self.reports_page = ReportsView()
        self.settings_page = InterviewSettingsView()

        self._stack.addWidget(self._build_interview_home())      # 0: Dashboard
        self._stack.addWidget(self._build_create_interview())    # 1: Create
        self._stack.addWidget(self._build_live_interview())      # 2: Live
        self._stack.addWidget(self._build_preflight_page())      # 3: Pre-flight
        self._stack.addWidget(self.previous_page)                # 4: Previous
        self._stack.addWidget(self.reports_page)                 # 5: Reports
        self._stack.addWidget(self.settings_page)                # 6: Settings

        layout.addWidget(self._stack)

        # Activate first
        self._on_nav_click("iv_dashboard")

    def _on_nav_click(self, page_id):
        idx_map = {
            "iv_dashboard": 0, "iv_create": 1, "iv_live": 2,
            "iv_previous": 4, "iv_reports": 5, "iv_settings": 6
        }
        idx = idx_map.get(page_id, 0)
        self._stack.setCurrentIndex(idx)
        for item in self._nav_items:
            item.set_active(item._page_id == page_id)

    # ── Start Interview Flow ──

    def _on_start_interview(self):
        """Validate form and show pre-flight checks."""
        title = self.input_title.text().strip() or "Interview Session"
        candidate = self.input_candidate.text().strip()
        role = self.input_role.text().strip()
        duration = self.spin_duration.value()
        difficulty = self.combo_difficulty.currentText()

        selected_rb = self.btn_group_type.checkedButton()
        itype = selected_rb.text() if selected_rb else "Technical"

        setup = InterviewSetup(
            title=title,
            candidate_name=candidate,
            job_role=role,
            interview_type=itype,
            duration_minutes=duration,
            difficulty=difficulty,
        )

        # Validate
        errors = self.controller.validate_setup(setup)
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return

        # Store setup for after preflight
        self._pending_setup = setup

        # Show pre-flight page
        self._stack.setCurrentIndex(3)
        self._run_preflight()

    def _run_preflight(self):
        """Run pre-flight checks and update the UI."""
        # Reset check widgets
        for name, lbl in self._preflight_labels.items():
            lbl.setText(f"  ⏳ {name}: Checking...")
            lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 12px; padding: 4px 8px; background: transparent;")

        self._preflight_start_btn.setEnabled(False)
        self._preflight_start_btn.setText("Checking...")

        # Run checks
        QTimer.singleShot(300, self._execute_preflight)

    def _execute_preflight(self):
        result = self.controller.run_preflight(self.engine)

        for check in result.checks:
            lbl = self._preflight_labels.get(check.name)
            if lbl:
                if check.available:
                    lbl.setText(f"  ✓ {check.name}: {check.message}")
                    lbl.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; font-size: 12px; padding: 4px 8px; background: transparent;")
                elif check.degraded:
                    lbl.setText(f"  ⚠ {check.name}: {check.message}")
                    lbl.setStyleSheet(f"color: {Theme.ACCENT_ORANGE}; font-size: 12px; padding: 4px 8px; background: transparent;")
                else:
                    lbl.setText(f"  ✗ {check.name}: {check.message}")
                    lbl.setStyleSheet(f"color: {Theme.ACCENT_RED}; font-size: 12px; padding: 4px 8px; background: transparent;")

        if result.can_start:
            self._preflight_start_btn.setEnabled(True)
            self._preflight_start_btn.setText("🚀 Start Interview")
        else:
            self._preflight_start_btn.setEnabled(False)
            self._preflight_start_btn.setText("Cannot start — required services unavailable")

    def _on_preflight_start(self):
        """Pre-flight passed — start the interview."""
        if hasattr(self, '_pending_setup'):
            iid = self.controller.start_interview(self._pending_setup, self.engine)
            if iid:
                self._on_nav_click("iv_live")

    # ── Controller Signal Handlers ──

    def _on_state_changed(self, state_str):
        logger.info(f"Interview state: {state_str}")

    def _on_interview_started(self, interview_id):
        logger.info(f"Interview started: {interview_id}")
        # Update live page header
        if hasattr(self, '_live_title_lbl'):
            setup = self.controller.session.setup if self.controller.session else None
            if setup:
                self._live_title_lbl.setText(
                    f"📋 {setup.title} — {setup.candidate_name} ({setup.job_role})"
                )
        if hasattr(self, 'cam_panel'):
            if self.engine and hasattr(self.engine, 'is_running') and self.engine.is_running:
                self.cam_panel.set_camera_active(True)

    def _on_interview_ended(self):
        logger.info("Interview ended")
        if hasattr(self, 'waveform_widget'):
            self.waveform_widget.set_voice_activity(False)
        if hasattr(self, 'cam_panel'):
            self.cam_panel.set_camera_active(False)

    def _on_report_ready(self, report):
        logger.info("Report generated")
        self.reports_page.load_report(report, self.controller.session)
        self._on_nav_click("iv_reports")

    def _on_error(self, title, detail):
        QMessageBox.critical(self, title, detail)

    def _on_talk_time_updated(self):
        m = self.controller.metrics
        if hasattr(self, 'talk_time_widget') and m.interviewer_talk_pct is not None:
            self.talk_time_widget.set_talk_time(m.interviewer_talk_pct, m.candidate_talk_pct)

        # Update WPM card
        if hasattr(self, 'card_pace') and m.current_wpm is not None:
            wpm = int(m.current_wpm)
            if wpm > 0:
                if wpm < 100:
                    tag = "Slow"
                elif wpm < 160:
                    tag = "Normal"
                else:
                    tag = "Fast"
                self.card_pace.set_metric(f"{wpm} WPM", min(100, int(wpm / 1.6)), tag, Theme.ACCENT_GREEN)

        # Update waveform
        if hasattr(self, 'waveform_widget') and m.current_wpm:
            self.waveform_widget.set_voice_activity(True, m._last_speaker or "Speaker", m.current_wpm)

    def _on_transcript_entry(self, speaker, text, timestamp):
        ts_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
        role = "Interviewer" if speaker == "interviewer" else "Candidate"
        if hasattr(self, 'transcript_widget'):
            self.transcript_widget.add_transcript(role, text, ts_str)

    def _on_observation(self, obs):
        count = len(self.controller.metrics.observations)
        if hasattr(self, 'card_observations'):
            self.card_observations.set_metric(
                f"{count} observation{'s' if count != 1 else ''}",
                min(100, count * 15), "Active", Theme.ACCENT_ORANGE
            )
        # Add to transcript as timeline event
        if hasattr(self, 'transcript_widget'):
            self.transcript_widget.add_transcript(
                "System", f"[{obs.event_type.upper()}] {obs.message}"
            )

    def _on_question_changed(self, index, text):
        if hasattr(self, '_question_label'):
            self._question_label.setText(f"Q{index + 1}: {text}")

    def _on_fairness_alert(self, question, warning, ts):
        if hasattr(self, 'coaching_widget'):
            self.coaching_widget.set_suggestion(f"⚠ {warning}")
        if hasattr(self, 'transcript_widget'):
            self.transcript_widget.add_transcript(
                "Fairness", warning, time.strftime("%H:%M:%S", time.localtime(ts))
            )

    def _on_coaching_suggestion(self, suggestion):
        if hasattr(self, 'coaching_widget'):
            self.coaching_widget.set_suggestion(suggestion)

    def _on_paste_probes(self, probes):
        if hasattr(self, 'transcript_widget'):
            self.transcript_widget.add_transcript(
                "System", f"Generated {len(probes)} probe questions from pasted code"
            )

    # ── End Interview ──

    def _on_end_interview(self):
        """End the live interview."""
        if not self.controller.is_live:
            return
        reply = QMessageBox.question(
            self, "End Interview",
            "Are you sure you want to end this interview?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.controller.end_interview()

    # ── Question Navigation ──

    def _on_nav_question(self, delta):
        self.controller.navigate_question(delta)

    # ── Sub-page builders ──

    def _build_interview_home(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(24)

        header = SectionHeader("AI Interviewer Coach", "Real-time coaching to improve your interview quality")
        layout.addWidget(header)

        # Stats — from real database
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        total = interview_store.get_interview_count()
        completed = interview_store.get_interview_count("reported")
        live = interview_store.get_interview_count("live")
        for lbl, val, icon, color in [
            ("Total Interviews", str(total), "📊", Theme.ACCENT_BLUE),
            ("Active Now", str(live), "🔴", Theme.ACCENT_RED),
            ("Completed", str(completed), "✅", Theme.ACCENT_GREEN),
            ("Avg Score", "—", "⭐", Theme.ACCENT_ORANGE),
        ]:
            card = _MiniStatCard(lbl, val, icon, color)
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Empty state
        empty = _EmptyState(
            "No Interview Running",
            "Create a new interview session to get started with AI-powered interviewer coaching.",
            "Start New Interview"
        )
        empty.action_clicked.connect(lambda: self._on_nav_click("iv_create"))
        layout.addWidget(empty)

        layout.addStretch()
        scroll.setWidget(content)

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        return page

    def _build_create_interview(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(20)

        header = SectionHeader("Create New Interview", "Set up interview parameters before starting")
        layout.addWidget(header)

        # Form card
        form_card = QWidget()
        form_card.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(28, 24, 28, 28)
        form_layout.setSpacing(16)

        # Form fields
        self.input_title = QLineEdit()
        self.input_title.setPlaceholderText("e.g. Senior Python Developer Interview")
        self.input_role = QLineEdit()
        self.input_role.setPlaceholderText("e.g. Backend Engineer")
        self.input_candidate = QLineEdit()
        self.input_candidate.setPlaceholderText("Candidate name (required)")
        self.input_meeting = QLineEdit()
        self.input_meeting.setPlaceholderText("e.g. https://meet.google.com/...")

        fields = [
            ("Interview Title *", self.input_title),
            ("Job Role *", self.input_role),
            ("Candidate Name *", self.input_candidate),
            ("Meeting Link", self.input_meeting),
        ]
        for label_text, widget in fields:
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Segoe UI", 12))
            lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
            form_layout.addWidget(lbl)
            widget.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Theme.BG_INPUT};
                    border: 1px solid {Theme.BORDER_SUBTLE};
                    border-radius: 8px;
                    padding: 10px 14px;
                    color: {Theme.TEXT_PRIMARY};
                    font-size: 13px;
                }}
                QLineEdit:focus {{ border-color: {Theme.ACCENT_CYAN}; }}
            """)
            form_layout.addWidget(widget)

        # Duration + Difficulty row
        row = QHBoxLayout()
        row.setSpacing(16)

        dur_group = QVBoxLayout()
        dur_lbl = QLabel("Duration (minutes)")
        dur_lbl.setFont(QFont("Segoe UI", 12))
        dur_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        dur_group.addWidget(dur_lbl)
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(15, 180)
        self.spin_duration.setValue(45)
        self.spin_duration.setStyleSheet(f"""
            QSpinBox {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 10px 14px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)
        dur_group.addWidget(self.spin_duration)
        row.addLayout(dur_group)

        diff_group = QVBoxLayout()
        diff_lbl = QLabel("Difficulty Level")
        diff_lbl.setFont(QFont("Segoe UI", 12))
        diff_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        diff_group.addWidget(diff_lbl)
        self.combo_difficulty = QComboBox()
        self.combo_difficulty.addItems(["Easy", "Medium", "Hard", "Expert"])
        self.combo_difficulty.setCurrentIndex(1)
        self.combo_difficulty.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 10px 14px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)
        diff_group.addWidget(self.combo_difficulty)
        row.addLayout(diff_group)

        form_layout.addLayout(row)

        # Interview type
        type_lbl = QLabel("Interview Type")
        type_lbl.setFont(QFont("Segoe UI", 12))
        type_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        form_layout.addWidget(type_lbl)

        type_row = QHBoxLayout()
        type_row.setSpacing(16)
        radio_style = f"""
            QRadioButton {{
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
                spacing: 8px;
                border: none;
                background: transparent;
            }}
            QRadioButton::indicator {{
                width: 18px; height: 18px;
                border-radius: 9px;
                border: 2px solid {Theme.BORDER_HOVER};
                background: transparent;
            }}
            QRadioButton::indicator:checked {{
                border-color: {Theme.ACCENT_CYAN};
                background: {Theme.ACCENT_CYAN};
            }}
        """
        self.btn_group_type = QButtonGroup(self)
        for tname in ["Technical", "HR", "Coding", "Aptitude"]:
            rb = QRadioButton(tname)
            rb.setStyleSheet(radio_style)
            self.btn_group_type.addButton(rb)
            type_row.addWidget(rb)
            if tname == "Technical":
                rb.setChecked(True)

        type_row.addStretch()
        form_layout.addLayout(type_row)

        # Start button
        start_btn = GlowButton("Start Interview", "🚀",
                                gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_PURPLE))
        start_btn.setFixedHeight(48)
        start_btn.clicked.connect(self._on_start_interview)
        form_layout.addSpacing(8)
        form_layout.addWidget(start_btn)

        layout.addWidget(form_card)
        layout.addStretch()

        scroll.setWidget(content)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        return page

    def _build_preflight_page(self):
        """Pre-flight readiness check page."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(20)

        header = SectionHeader("Interview Readiness", "Checking all required services before starting")
        layout.addWidget(header)

        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 28)
        card_layout.setSpacing(8)

        # Create labels for each service check
        self._preflight_labels = {}
        services = [
            "Database", "Session", "Observation Engine",
            "Camera", "Microphone", "Speech Recognition",
            "AI / Gemini", "Screen Capture"
        ]
        for svc in services:
            lbl = QLabel(f"  ⏳ {svc}: Checking...")
            lbl.setFont(QFont("Segoe UI", 12))
            lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; padding: 4px 8px; background: transparent;")
            card_layout.addWidget(lbl)
            self._preflight_labels[svc] = lbl

        card_layout.addSpacing(16)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = GlowButton("Cancel", "❌", gradient=(Theme.BORDER_SUBTLE, Theme.BORDER_HOVER))
        cancel_btn.setFixedHeight(44)
        cancel_btn.clicked.connect(lambda: self._on_nav_click("iv_create"))
        btn_row.addWidget(cancel_btn)

        self._preflight_start_btn = GlowButton("Checking...", "🚀",
                                                 gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_PURPLE))
        self._preflight_start_btn.setFixedHeight(44)
        self._preflight_start_btn.setEnabled(False)
        self._preflight_start_btn.clicked.connect(self._on_preflight_start)
        btn_row.addWidget(self._preflight_start_btn)

        card_layout.addLayout(btn_row)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_live_interview(self):
        """Live interview page with real-time metrics from InterviewController."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── TOP BAR ──
        top_bar = QWidget()
        top_bar.setFixedHeight(48)
        top_bar.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-bottom: 1px solid {Theme.BORDER_SUBTLE};")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 0, 16, 0)

        self._live_title_lbl = QLabel("📋 Interview — Waiting to start")
        self._live_title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self._live_title_lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        top_layout.addWidget(self._live_title_lbl)

        top_layout.addStretch()

        self._live_timer_lbl = QLabel("⏱ 00:00")
        self._live_timer_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self._live_timer_lbl.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; background: transparent;")
        top_layout.addWidget(self._live_timer_lbl)

        live_badge = StatusBadge("LIVE", "active")
        top_layout.addWidget(live_badge)

        layout.addWidget(top_bar)

        # ── MAIN AREA ──
        main_area = QHBoxLayout()
        main_area.setContentsMargins(0, 0, 0, 0)
        main_area.setSpacing(0)

        # Left: Video + Audio + Transcript
        left_area = QWidget()
        left_area.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_area)
        left_layout.setContentsMargins(18, 16, 12, 16)
        left_layout.setSpacing(10)

        # Video streams
        streams_row = QHBoxLayout()
        streams_row.setSpacing(10)
        self.cam_panel = LiveVideoPanel("Candidate Camera", "📹", is_screen_share=False)
        self.screen_panel = LiveVideoPanel("Screen Share", "🖥", is_screen_share=True)
        streams_row.addWidget(self.cam_panel, 1)
        streams_row.addWidget(self.screen_panel, 1)
        left_layout.addLayout(streams_row, 3)

        # Audio Waveform
        self.waveform_widget = AudioWaveformWidget(num_bars=32)
        left_layout.addWidget(self.waveform_widget)

        # Live Transcript
        self.transcript_widget = LiveTranscriptWidget()
        left_layout.addWidget(self.transcript_widget)

        main_area.addWidget(left_area, 3)

        # ── Right Panel: AI Interviewer Coach ──
        right_panel = QWidget()
        right_panel.setFixedWidth(380)
        right_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border-left: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(8)

        # Header
        header_row = QHBoxLayout()
        ai_title = QLabel("🤖 AI Interviewer Coach")
        ai_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        ai_title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        header_row.addWidget(ai_title)
        header_row.addStretch()
        right_layout.addLayout(header_row)

        # Talk-Time Widget
        self.talk_time_widget = TalkTimeWidget()
        right_layout.addWidget(self.talk_time_widget)

        # Coaching Suggestion
        self.coaching_widget = CoachingSuggestionWidget()
        right_layout.addWidget(self.coaching_widget)

        # Live Metric Cards — all start with waiting/empty state
        self.card_pace = LiveMetricCard("Communication Pace", "—", 0, "Waiting...", Theme.TEXT_MUTED)
        self.card_observations = LiveMetricCard("Observations", "0", 0, "No observations", Theme.TEXT_MUTED)
        self.card_interruptions = LiveMetricCard("Interruptions", "0", 0, "None detected", Theme.TEXT_MUTED)

        right_layout.addWidget(self.card_pace)
        right_layout.addWidget(self.card_observations)
        right_layout.addWidget(self.card_interruptions)

        # Current Question
        self._question_label = QLabel("No questions loaded")
        self._question_label.setWordWrap(True)
        self._question_label.setFont(QFont("Segoe UI", 10))
        self._question_label.setStyleSheet(f"""
            color: {Theme.TEXT_PRIMARY}; background-color: {Theme.BG_DARKER};
            border-radius: 8px; padding: 10px; border: none;
        """)
        right_layout.addWidget(self._question_label)

        # Question nav buttons
        q_btn_row = QHBoxLayout()
        q_btn_row.setSpacing(8)
        prev_btn = QPushButton("← Prev")
        prev_btn.setStyleSheet(f"background: {Theme.BG_DARKER}; color: {Theme.TEXT_PRIMARY}; padding: 6px 12px; border-radius: 6px; border: 1px solid {Theme.BORDER_SUBTLE};")
        prev_btn.clicked.connect(lambda: self._on_nav_question(-1))
        next_btn = QPushButton("Next →")
        next_btn.setStyleSheet(f"background: {Theme.BG_DARKER}; color: {Theme.TEXT_PRIMARY}; padding: 6px 12px; border-radius: 6px; border: 1px solid {Theme.BORDER_SUBTLE};")
        next_btn.clicked.connect(lambda: self._on_nav_question(1))
        q_btn_row.addWidget(prev_btn)
        q_btn_row.addWidget(next_btn)
        q_btn_row.addStretch()
        right_layout.addLayout(q_btn_row)

        right_layout.addStretch()

        # End Interview button
        end_btn = GlowButton("End Interview", "⏹",
                              gradient=(Theme.ACCENT_RED, Theme.ACCENT_ORANGE))
        end_btn.setFixedHeight(40)
        end_btn.clicked.connect(self._on_end_interview)
        right_layout.addWidget(end_btn)

        main_area.addWidget(right_panel)

        layout.addLayout(main_area)

        # Connect timer
        if self.controller.session:
            self.controller.session.timer_tick.connect(self._on_timer_tick)

        return page

    def _on_timer_tick(self, remaining_seconds):
        mins = remaining_seconds // 60
        secs = remaining_seconds % 60
        if hasattr(self, '_live_timer_lbl'):
            self._live_timer_lbl.setText(f"⏱ {mins:02d}:{secs:02d}")

    # ── Helper Widgets ──

    def _build_placeholder(self, title, icon, message):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.addWidget(SectionHeader(title))
        layout.addSpacing(40)
        empty = _EmptyState(title, message)
        layout.addWidget(empty)
        layout.addStretch()
        return page


# ── Helper Widgets ──

class _BackButton(QWidget):
    clicked = Signal()

    def __init__(self, text="← Back", parent=None):
        super().__init__(parent)
        self._text = text
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor(Theme.ACCENT_CYAN) if self._hover else QColor(Theme.TEXT_SECONDARY)
        p.setPen(color)
        p.setFont(QFont("Segoe UI", 12))
        p.drawText(self.rect().adjusted(16, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, self._text)
        p.end()


class _MiniStatCard(QWidget):
    def __init__(self, label, value, icon, color, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = value
        self._icon = icon
        self._color = color
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 10, 10)
        p.fillPath(path, QBrush(QColor(Theme.BG_CARD)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)

        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI Emoji", 18))
        p.drawText(14, 12, 32, 32, Qt.AlignCenter, self._icon)

        p.setPen(QColor(Theme.TEXT_PRIMARY))
        p.setFont(QFont("Segoe UI", 18, QFont.Bold))
        p.drawText(52, 10, w - 60, 28, Qt.AlignLeft | Qt.AlignVCenter, self._value)

        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(52, 42, w - 60, 20, Qt.AlignLeft | Qt.AlignVCenter, self._label)
        p.end()


class _EmptyState(QWidget):
    action_clicked = Signal()

    def __init__(self, title="", message="", button_text="", parent=None):
        super().__init__(parent)
        self._title = title
        self._message = message
        self._button_text = button_text
        self.setMinimumHeight(200)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        icon_lbl = QLabel("📋")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 40))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.DemiBold))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(title_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setFont(QFont("Segoe UI", 12))
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        msg_lbl.setMaximumWidth(400)
        msg_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        layout.addWidget(msg_lbl)

        if button_text:
            btn = GlowButton(button_text, "🚀", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_PURPLE))
            btn.setFixedWidth(200)
            btn.clicked.connect(self.action_clicked.emit)
            layout.addWidget(btn, alignment=Qt.AlignCenter)
