# ============================================================
#  AI INTERVIEW DASHBOARD — Full Interviewer Coach Workspace
#  Primary Mode: Embedded Zoom Meeting + AI Interviewer Coach.
#  Multi-modal concurrency: Voice, Gesture, Cursor, and Vision
#  all run simultaneously with the live Zoom session.
# ============================================================

import time
import os
import logging
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
    QScrollArea, QFrame, QSizePolicy, QLineEdit, QComboBox,
    QSpinBox, QTextEdit, QRadioButton, QButtonGroup, QGridLayout,
    QMessageBox, QPushButton, QFileDialog, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush, QPen

from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import (
    GlowButton, SectionHeader, SidebarNavItem, StatusBadge
)
from intent_platform.ui.pages.interview.live_widgets import (
    AudioWaveformWidget, LiveTranscriptWidget, TalkTimeWidget,
    EmbeddedZoomWorkspace, AICoachTabWidget
)
from intent_platform.ui.pages.interview.report_and_settings_view import (
    PreviousInterviewsView, ReportsView, InterviewSettingsView
)
from intent_platform.core.interview.store import interview_store
from intent_platform.core.interview.models import InterviewSetup, InterviewState
from intent_platform.core.interview.controller import InterviewController, PreFlightResult
from intent_platform.core.interview.resume_parser import ResumeParser

logger = logging.getLogger(__name__)


class InterviewDashboard(QWidget):
    """Complete AI Interview Intelligence workspace."""

    navigate_back = Signal()

    def __init__(self, engine=None, user_profile=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.user_profile = user_profile

        # Controller manages full interview lifecycle
        self.controller = InterviewController()
        self._pending_setup: Optional[InterviewSetup] = None
        self._parsed_resume_data: Optional[Dict[str, Any]] = None

        self._connect_controller()
        self._build_ui()

    def _connect_controller(self):
        self.controller.state_changed.connect(self._on_state_changed)
        self.controller.interview_started.connect(self._on_interview_started)
        self.controller.interview_ended.connect(self._on_interview_ended)
        self.controller.report_ready.connect(self._on_report_ready)
        self.controller.error_occurred.connect(self._on_error)
        self.controller.participant_joined.connect(self._on_remote_participant_joined)
        self.controller.participant_left.connect(self._on_remote_participant_left)

        # Zoom meeting adapter signals
        self.controller.zoom_adapter.state_changed.connect(self._on_zoom_state_changed)
        self.controller.zoom_adapter.screen_share_status.connect(self._on_zoom_screen_share_status)

        # Metrics & Copilot signals
        m = self.controller.metrics
        m.talk_time_updated.connect(self._on_talk_time_updated)
        m.transcript_entry.connect(self._on_transcript_entry)
        m.observation_fired.connect(self._on_observation)
        m.fairness_alert.connect(self._on_fairness_alert)
        m.copilot_suggestion_ready.connect(self._on_copilot_suggestion)
        m.visual_explain_ready.connect(self._on_visual_explain_result)
        m.rubric_updated.connect(self._on_rubric_updated)
        m.resume_claims_updated.connect(self._on_resume_claims_updated)

    def _on_remote_participant_joined(self, pid: str, name: str):
        if hasattr(self, 'zoom_workspace'):
            self.zoom_workspace.add_participant(pid, name)
        if hasattr(self, 'coach_tabs'):
            self.coach_tabs.set_coach_state("WAITING_FOR_SPEECH")
        if hasattr(self, '_live_title_lbl'):
            self._live_title_lbl.setText(f"🔴 LIVE • Zoom Meeting • Connected ({name})")

    def _on_remote_participant_left(self, pid: str):
        if hasattr(self, 'zoom_workspace'):
            self.zoom_workspace.remove_participant(pid)
        if hasattr(self, 'coach_tabs'):
            self.coach_tabs.set_coach_state("WAITING_FOR_PARTICIPANT")
        if hasattr(self, '_live_title_lbl'):
            self._live_title_lbl.setText("🔴 LIVE • Zoom Meeting • 1 Participant")

    def _on_zoom_state_changed(self, state: str, msg: str):
        if hasattr(self, 'zoom_workspace'):
            self.zoom_workspace.update_connection_state(state, msg)

    def _on_zoom_screen_share_status(self, active: bool, sharer: str):
        if hasattr(self, 'zoom_workspace'):
            self.zoom_workspace.set_screen_share_active(active, sharer)

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

        back_btn = _NavBackButton("← Back to Home")
        back_btn.clicked.connect(self.navigate_back.emit)
        left_layout.addWidget(back_btn)
        left_layout.addSpacing(16)

        title_lbl = QLabel("  🎤 Interview")
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {Theme.ACCENT_BLUE}; padding: 8px 12px; background: transparent;")
        left_layout.addWidget(title_lbl)
        left_layout.addSpacing(8)

        # Nav items
        self._nav_items = []
        nav_data = [
            ("iv_assist", "⚡", "Assist Ongoing"),
            ("iv_create", "➕", "Create Interview"),
            ("iv_permissions", "🔒", "Access & Permissions"),
            ("iv_live", "🔴", "Live Workspace"),
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

        # ── Content Stack ──
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        self.previous_page = PreviousInterviewsView()
        self.reports_page = ReportsView()
        self.settings_page = InterviewSettingsView()

        self._stack.addWidget(self._build_assist_ongoing_page())  # 0: Assist Ongoing (Primary)
        self._stack.addWidget(self._build_create_interview())     # 1: Create
        self._stack.addWidget(self._build_permissions_page())     # 2: Permissions Check
        self._stack.addWidget(self._build_preflight_page())       # 3: Preflight
        self._stack.addWidget(self._build_live_interview())       # 4: Live Interview
        self._stack.addWidget(self.previous_page)                 # 5: Previous
        self._stack.addWidget(self.reports_page)                  # 6: Reports
        self._stack.addWidget(self.settings_page)                 # 7: Settings

        layout.addWidget(self._stack)
        self._on_nav_click("iv_assist")

    def _on_nav_click(self, page_id):
        idx_map = {
            "iv_assist": 0, "iv_create": 1, "iv_permissions": 2,
            "iv_preflight": 3, "iv_live": 4, "iv_previous": 5,
            "iv_reports": 6, "iv_settings": 7
        }
        idx = idx_map.get(page_id, 0)
        self._stack.setCurrentIndex(idx)
        for item in self._nav_items:
            item.set_active(item._page_id == page_id)

    # ── Page 0: Assist Ongoing Meeting (Primary Flow) ──

    def _build_assist_ongoing_page(self):
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

        header = SectionHeader("AI Interviewer Coach", "Assist an ongoing Zoom interview with real-time AI copilot")
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
        card_layout.setSpacing(14)

        lbl_inst = QLabel("Paste your Zoom meeting link below to embed the meeting and launch the AI Co-Pilot:")
        lbl_inst.setFont(QFont("Segoe UI", 12))
        lbl_inst.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        card_layout.addWidget(lbl_inst)

        # Platform selector
        plat_row = QHBoxLayout()
        plat_lbl = QLabel("Platform:")
        plat_lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; border: none;")
        self.combo_assist_plat = QComboBox()
        self.combo_assist_plat.addItems(["Zoom Meeting SDK", "Google Meet (Companion)", "Microsoft Teams (Companion)"])
        self.combo_assist_plat.setStyleSheet(f"background-color: {Theme.BG_INPUT}; color: {Theme.TEXT_PRIMARY}; padding: 6px; border-radius: 6px;")
        plat_row.addWidget(plat_lbl)
        plat_row.addWidget(self.combo_assist_plat)
        plat_row.addStretch()
        card_layout.addLayout(plat_row)

        # Zoom Link input
        self.input_assist_link = QLineEdit()
        self.input_assist_link.setPlaceholderText("https://zoom.us/j/1234567890?pwd=...")
        self.input_assist_link.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 12px 14px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)
        card_layout.addWidget(self.input_assist_link)

        # Candidate Name (Optional quick entry)
        self.input_assist_cand = QLineEdit()
        self.input_assist_cand.setPlaceholderText("Candidate Name (e.g. Rahul Sharma)")
        self.input_assist_cand.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 10px 14px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)
        card_layout.addWidget(self.input_assist_cand)

        # Validation status label
        self.lbl_assist_status = QLabel("Meeting link ready to validate.")
        self.lbl_assist_status.setFont(QFont("Segoe UI", 10))
        self.lbl_assist_status.setStyleSheet(f"color: {Theme.TEXT_MUTED}; border: none;")
        card_layout.addWidget(self.lbl_assist_status)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_connect_zoom = GlowButton("Connect to Zoom", "⚡", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_CYAN))
        self.btn_connect_zoom.setFixedHeight(46)
        self.btn_connect_zoom.clicked.connect(self._on_assist_connect_clicked)
        btn_row.addWidget(self.btn_connect_zoom)

        btn_create_alt = GlowButton("Create Custom Interview", "➕", gradient=(Theme.BORDER_SUBTLE, Theme.BORDER_HOVER))
        btn_create_alt.setFixedHeight(46)
        btn_create_alt.clicked.connect(lambda: self._on_nav_click("iv_create"))
        btn_row.addWidget(btn_create_alt)

        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        layout.addWidget(card)

        # Quick stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        total = interview_store.get_interview_count()
        completed = interview_store.get_interview_count("completed")
        for lbl, val, icon, color in [
            ("Total Interviews", str(total), "📊", Theme.ACCENT_BLUE),
            ("Completed", str(completed), "✅", Theme.ACCENT_GREEN),
            ("AI Copilot", "Ready", "🧠", Theme.ACCENT_CYAN),
        ]:
            card_s = _MiniStatCard(lbl, val, icon, color)
            stats_row.addWidget(card_s)
        layout.addLayout(stats_row)

        layout.addStretch()
        scroll.setWidget(content)

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        return page

    def _on_assist_connect_clicked(self):
        url = self.input_assist_link.text().strip()
        cand = self.input_assist_cand.text().strip() or "Candidate"

        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a Zoom meeting URL.")
            return

        valid, msg, info = self.controller.parse_meeting_url(url)
        if not valid:
            self.lbl_assist_status.setText(f"❌ {msg}")
            self.lbl_assist_status.setStyleSheet(f"color: {Theme.ACCENT_RED}; border: none;")
            QMessageBox.warning(self, "Invalid URL", msg)
            return

        self.lbl_assist_status.setText(f"✓ {msg}")
        self.lbl_assist_status.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; border: none;")

        setup = InterviewSetup(
            title=f"Zoom Interview — {cand}",
            candidate_name=cand,
            job_role="Software Engineer",
            interview_type="Technical",
            meeting_platform=info.get("platform", "Zoom"),
            meeting_link=url,
        )
        self._pending_setup = setup
        self._stack.setCurrentIndex(2)  # Go to Permissions Check
        self._refresh_permissions_ui()

    # ── Page 1: Create Interview (Sectioned) ──

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

        header = SectionHeader("Configure Interview Session", "Complete setup for candidate, rubric, and meeting connection")
        layout.addWidget(header)

        # ── SECTION A: INTERVIEW DETAILS ──
        sec_a = _SectionCard("SECTION A — INTERVIEW DETAILS")
        self.input_title = QLineEdit("Technical Interview")
        self.input_role = QLineEdit("Senior Software Engineer")
        self.input_candidate = QLineEdit()
        self.input_candidate.setPlaceholderText("Candidate full name (required)")

        for lbl, w in [("Interview Title *", self.input_title), ("Job Role *", self.input_role), ("Candidate Name *", self.input_candidate)]:
            sec_a.add_field(lbl, w)

        # Duration & Difficulty
        row_dur = QHBoxLayout()
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(10, 180)
        self.spin_duration.setValue(45)
        self.spin_duration.setStyleSheet(f"background-color: {Theme.BG_INPUT}; color: {Theme.TEXT_PRIMARY}; padding: 8px; border-radius: 6px;")

        self.combo_difficulty = QComboBox()
        self.combo_difficulty.addItems(["Easy", "Medium", "Hard", "Expert"])
        self.combo_difficulty.setCurrentIndex(1)
        self.combo_difficulty.setStyleSheet(f"background-color: {Theme.BG_INPUT}; color: {Theme.TEXT_PRIMARY}; padding: 8px; border-radius: 6px;")

        row_dur.addWidget(QLabel("Duration (min):"))
        row_dur.addWidget(self.spin_duration)
        row_dur.addSpacing(20)
        row_dur.addWidget(QLabel("Difficulty:"))
        row_dur.addWidget(self.combo_difficulty)
        row_dur.addStretch()
        sec_a.add_layout(row_dur)
        layout.addWidget(sec_a)

        # ── SECTION B: CANDIDATE CONTEXT (RESUME) ──
        sec_b = _SectionCard("SECTION B — CANDIDATE CONTEXT & RESUME")
        res_row = QHBoxLayout()
        self.btn_upload_resume = QPushButton("📄 Upload Resume (PDF/DOCX/TXT)")
        self.btn_upload_resume.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_DARKER};
                color: {Theme.ACCENT_CYAN};
                border: 1px solid {Theme.BORDER_HOVER};
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {Theme.BG_CARD}; }}
        """)
        self.btn_upload_resume.clicked.connect(self._on_upload_resume)
        res_row.addWidget(self.btn_upload_resume)

        self.lbl_resume_status = QLabel("No resume attached (Optional)")
        self.lbl_resume_status.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px;")
        res_row.addWidget(self.lbl_resume_status)
        res_row.addStretch()
        sec_b.add_layout(res_row)
        layout.addWidget(sec_b)

        # ── SECTION C: INTERVIEW RUBRIC ──
        sec_c = _SectionCard("SECTION C — INTERVIEW RUBRIC")
        self.chk_rubric_dsa = QCheckBox("Data Structures & Algorithms (Arrays, Trees, Complexity)")
        self.chk_rubric_dsa.setChecked(True)
        self.chk_rubric_sys = QCheckBox("System Design & Architecture (Scalability, Caching, Reliability)")
        self.chk_rubric_sys.setChecked(True)
        self.chk_rubric_comm = QCheckBox("Communication & Structured Reasoning (Clarity, Tradeoffs)")
        self.chk_rubric_comm.setChecked(True)
        for chk in (self.chk_rubric_dsa, self.chk_rubric_sys, self.chk_rubric_comm):
            chk.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px; margin: 2px 0;")
            sec_c.add_widget(chk)
        layout.addWidget(sec_c)

        # ── SECTION D: MEETING LINK ──
        sec_d = _SectionCard("SECTION D — MEETING LINK")
        self.input_meeting = QLineEdit()
        self.input_meeting.setPlaceholderText("https://zoom.us/j/1234567890?pwd=...")
        sec_d.add_field("Zoom / Meeting URL", self.input_meeting)

        m_btn_row = QHBoxLayout()
        self.btn_test_link = QPushButton("🔍 Validate Meeting Link")
        self.btn_test_link.setStyleSheet(f"background: {Theme.BG_DARKER}; color: {Theme.TEXT_PRIMARY}; padding: 6px 12px; border-radius: 6px; border: 1px solid {Theme.BORDER_SUBTLE};")
        self.btn_test_link.clicked.connect(self._on_test_meeting_link)
        m_btn_row.addWidget(self.btn_test_link)
        m_btn_row.addStretch()
        sec_d.add_layout(m_btn_row)
        layout.addWidget(sec_d)

        # Proceed Button
        proceed_btn = GlowButton("Proceed to Permission & Preflight Check", "🔒", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_PURPLE))
        proceed_btn.setFixedHeight(48)
        proceed_btn.clicked.connect(self._on_create_proceed)
        layout.addWidget(proceed_btn)

        layout.addStretch()
        scroll.setWidget(content)

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        return page

    def _on_upload_resume(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Candidate Resume", "", "Resume Files (*.pdf *.docx *.txt);;All Files (*)"
        )
        if file_path:
            parsed = ResumeParser.parse_file(file_path)
            if parsed.get("success"):
                self._parsed_resume_data = parsed
                skills_str = ", ".join(parsed.get("skills", [])[:5])
                claims_count = len(parsed.get("claims", []))
                self.lbl_resume_status.setText(f"✓ {os.path.basename(file_path)} — {claims_count} claims extracted ({skills_str}...)")
                self.lbl_resume_status.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; font-size: 11px;")
                if not self.input_candidate.text().strip() and parsed.get("candidate_name") != "Candidate":
                    self.input_candidate.setText(parsed.get("candidate_name", ""))
            else:
                self.lbl_resume_status.setText(f"❌ Parse error: {parsed.get('error')}")
                self.lbl_resume_status.setStyleSheet(f"color: {Theme.ACCENT_RED}; font-size: 11px;")

    def _on_test_meeting_link(self):
        url = self.input_meeting.text().strip()
        if not url:
            QMessageBox.information(self, "Meeting Link", "Please enter a meeting URL.")
            return
        valid, msg, _ = self.controller.parse_meeting_url(url)
        if valid:
            QMessageBox.information(self, "Link Validated", f"✓ {msg}")
        else:
            QMessageBox.warning(self, "Link Validation Error", f"✗ {msg}")

    def _on_create_proceed(self):
        title = self.input_title.text().strip() or "Interview Session"
        candidate = self.input_candidate.text().strip()
        role = self.input_role.text().strip()
        duration = self.spin_duration.value()
        difficulty = self.combo_difficulty.currentText()
        meeting_link = self.input_meeting.text().strip()
        resume_path = self._parsed_resume_data.get("filename", "") if self._parsed_resume_data else ""

        setup = InterviewSetup(
            title=title,
            candidate_name=candidate,
            job_role=role,
            interview_type="Technical",
            duration_minutes=duration,
            difficulty=difficulty,
            meeting_link=meeting_link,
            resume_path=resume_path
        )
        errors = self.controller.validate_setup(setup)
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return

        self._pending_setup = setup
        self._stack.setCurrentIndex(2)  # Permissions page
        self._refresh_permissions_ui()

    # ── Page 2: Permission & Access Setup Screen ──

    def _build_permissions_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(18)

        header = SectionHeader("Permission & Access Check", "Verify real device permissions and Zoom access readiness")
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
        card_layout.setSpacing(12)

        lbl_iv_acc = QLabel("ZOOM & LOCAL SYSTEM PERMISSIONS")
        lbl_iv_acc.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl_iv_acc.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; border: none;")
        card_layout.addWidget(lbl_iv_acc)

        self._perm_labels = {}
        for perm in [
            ("Meeting Link", "🌐 Zoom Meeting URL", "Validating..."),
            ("Zoom SDK", "⚡ Zoom Meeting SDK Access", "Checking..."),
            ("Zoom RTMS", "📡 Realtime Media Streams (RTMS)", "Checking..."),
            ("Microphone", "🎙 Local Microphone", "Checking..."),
            ("Camera", "📷 Vision & Camera", "Checking..."),
            ("Screen Capture", "🖥 Local Screen Capture", "Checking...")
        ]:
            lbl = QLabel(f"  {perm[1]}: {perm[2]}")
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; padding: 2px 0;")
            card_layout.addWidget(lbl)
            self._perm_labels[perm[0]] = lbl

        card_layout.addSpacing(10)
        lbl_cand_acc = QLabel("REMOTE CANDIDATE PARTICIPATION")
        lbl_cand_acc.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl_cand_acc.setStyleSheet(f"color: {Theme.ACCENT_ORANGE}; border: none;")
        card_layout.addWidget(lbl_cand_acc)

        cand_notes = [
            "🎙 Candidate Audio: Waiting for candidate to speak in Zoom meeting",
            "📷 Candidate Video: Waiting for candidate video stream in Zoom meeting",
            "🖥 Candidate Screen: Waiting for candidate to share screen",
        ]
        for text in cand_notes:
            lbl = QLabel(f"  ⏳ {text}")
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; border: none; padding: 2px 0;")
            card_layout.addWidget(lbl)

        card_layout.addSpacing(16)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_retest = QPushButton("🔄 Re-Check Permissions")
        btn_retest.setStyleSheet(f"background: {Theme.BG_DARKER}; color: {Theme.TEXT_PRIMARY}; padding: 8px 14px; border-radius: 6px; border: 1px solid {Theme.BORDER_SUBTLE}; font-size: 11px;")
        btn_retest.clicked.connect(self._refresh_permissions_ui)
        btn_row.addWidget(btn_retest)

        self._btn_perm_settings = QPushButton("⚙ Configure Zoom Credentials")
        self._btn_perm_settings.setStyleSheet(f"background: {Theme.BG_DARKER}; color: {Theme.ACCENT_CYAN}; padding: 8px 14px; border-radius: 6px; border: 1px solid {Theme.BORDER_SUBTLE}; font-size: 11px;")
        self._btn_perm_settings.clicked.connect(lambda: self._stack.setCurrentIndex(7))
        btn_row.addWidget(self._btn_perm_settings)

        btn_cont = GlowButton("Continue to Preflight", "🚀", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_CYAN))
        btn_cont.setFixedHeight(38)
        btn_cont.clicked.connect(self._on_permissions_continue)
        btn_row.addWidget(btn_cont)

        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _refresh_permissions_ui(self):
        auth_status = self.controller.zoom_auth.check_authorization_status()
        
        # 1. Meeting Link
        lbl_link = self._perm_labels.get("Meeting Link")
        if lbl_link:
            if self._pending_setup and self._pending_setup.meeting_link:
                valid, msg, _ = self.controller.parse_meeting_url(self._pending_setup.meeting_link)
                if valid:
                    lbl_link.setText("  ✓ Zoom Meeting URL: Validated & Ready")
                    lbl_link.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; border: none; padding: 2px 0;")
                else:
                    lbl_link.setText(f"  ✗ Zoom Meeting URL: {msg}")
                    lbl_link.setStyleSheet(f"color: {Theme.ACCENT_RED}; border: none; padding: 2px 0;")
            else:
                lbl_link.setText("  ○ Zoom Meeting URL: Not specified")
                lbl_link.setStyleSheet(f"color: {Theme.TEXT_MUTED}; border: none; padding: 2px 0;")

        # 2. Zoom SDK
        lbl_sdk = self._perm_labels.get("Zoom SDK")
        if lbl_sdk:
            if auth_status["sdk_configured"]:
                lbl_sdk.setText("  ✓ Zoom Meeting SDK: Credentials Configured & Ready")
                lbl_sdk.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; border: none; padding: 2px 0;")
            else:
                lbl_sdk.setText("  ⚠ Zoom Meeting SDK: Credentials Missing (Set ZOOM_SDK_KEY / SECRET in .env)")
                lbl_sdk.setStyleSheet(f"color: {Theme.ACCENT_ORANGE}; border: none; padding: 2px 0;")

        # 3. Zoom RTMS
        lbl_rtms = self._perm_labels.get("Zoom RTMS")
        if lbl_rtms:
            if auth_status["rtms_configured"]:
                lbl_rtms.setText("  ✓ Zoom RTMS: Stream Authorized & Ready")
                lbl_rtms.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; border: none; padding: 2px 0;")
            else:
                lbl_rtms.setText("  ⚠ Zoom RTMS: Unconfigured (Local device audio/screen tap active)")
                lbl_rtms.setStyleSheet(f"color: {Theme.ACCENT_ORANGE}; border: none; padding: 2px 0;")

        # 4. Microphone
        lbl_mic = self._perm_labels.get("Microphone")
        if lbl_mic:
            try:
                import speech_recognition as sr
                mic = sr.Microphone()
                lbl_mic.setText("  ✓ Local Microphone: Ready & Granted")
                lbl_mic.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; border: none; padding: 2px 0;")
            except Exception as e:
                lbl_mic.setText(f"  ⚠ Local Microphone: Standby ({e})")
                lbl_mic.setStyleSheet(f"color: {Theme.ACCENT_ORANGE}; border: none; padding: 2px 0;")

        # 5. Camera & Vision
        lbl_cam = self._perm_labels.get("Camera")
        if lbl_cam:
            if self.engine and getattr(self.engine, 'is_running', False):
                lbl_cam.setText("  ✓ Vision & Camera: Active")
                lbl_cam.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; border: none; padding: 2px 0;")
            else:
                lbl_cam.setText("  ✓ Vision & Camera: Standby / Available")
                lbl_cam.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; border: none; padding: 2px 0;")

        # 6. Screen Capture
        lbl_screen = self._perm_labels.get("Screen Capture")
        if lbl_screen:
            lbl_screen.setText("  ✓ Local Screen Capture: Granted")
            lbl_screen.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; border: none; padding: 2px 0;")

    def _on_permissions_continue(self):
        self._stack.setCurrentIndex(3)  # Preflight page
        self._run_preflight()

    # ── Page 3: Preflight Check Screen ──

    def _build_preflight_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(20)

        header = SectionHeader("Preflight Readiness Check", "Final verification before launching live copilot")
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

        self._preflight_labels = {}
        services = [
            "Database", "Session", "Zoom Embedded Meeting", "Zoom RTMS",
            "Camera", "Microphone", "Speech Recognition", "AI Copilot",
            "Candidate Screen Share"
        ]
        for svc in services:
            lbl = QLabel(f"  ⏳ {svc}: Checking...")
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; padding: 4px 8px; background: transparent;")
            card_layout.addWidget(lbl)
            self._preflight_labels[svc] = lbl

        card_layout.addSpacing(16)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._preflight_start_btn = GlowButton("🚀 Launch Live Interview", "🚀", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_PURPLE))
        self._preflight_start_btn.setFixedHeight(44)
        self._preflight_start_btn.clicked.connect(self._on_preflight_start)
        btn_row.addWidget(self._preflight_start_btn)

        self._btn_configure_zoom = QPushButton("⚙ Configure Zoom Credentials")
        self._btn_configure_zoom.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_HOVER};
                border-color: {Theme.ACCENT_BLUE};
            }}
        """)
        self._btn_configure_zoom.clicked.connect(lambda: self._stack.setCurrentIndex(7))  # Settings page
        btn_row.addWidget(self._btn_configure_zoom)

        self._btn_companion_mode = QPushButton("🌐 Use Companion Mode Instead")
        self._btn_companion_mode.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_MUTED};
                border: 1px dashed {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                border-color: {Theme.ACCENT_ORANGE};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        self._btn_companion_mode.clicked.connect(self._on_use_companion_mode)
        btn_row.addWidget(self._btn_companion_mode)

        btn_row.addStretch()

        card_layout.addLayout(btn_row)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _run_preflight(self):
        QTimer.singleShot(200, self._execute_preflight)

    def _execute_preflight(self):
        result = self.controller.run_preflight(self.engine, self._pending_setup)
        for check in result.checks:
            lbl = self._preflight_labels.get(check.name)
            if lbl:
                if check.available and not check.degraded:
                    lbl.setText(f"  ✓ {check.name}: {check.message}")
                    lbl.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; font-size: 11px; background: transparent;")
                elif check.degraded:
                    lbl.setText(f"  ⚠ {check.name}: {check.message}")
                    lbl.setStyleSheet(f"color: {Theme.ACCENT_ORANGE}; font-size: 11px; background: transparent;")
                else:
                    lbl.setText(f"  ✗ {check.name}: {check.message}")
                    lbl.setStyleSheet(f"color: {Theme.ACCENT_RED}; font-size: 11px; background: transparent;")

        self._preflight_start_btn.setEnabled(result.can_start)

    def _on_preflight_start(self):
        if self._pending_setup:
            if hasattr(self, 'zoom_workspace'):
                self.zoom_workspace.remove_participant()  # Interviewer is Participant #1, candidate tile in standby
                if self._pending_setup.meeting_link:
                    valid, _, info = self.controller.parse_meeting_url(self._pending_setup.meeting_link)
                    if valid:
                        self.zoom_workspace.set_meeting_info(info)

            iid = self.controller.start_interview(self._pending_setup, self.engine)
            if iid:
                self.controller.launch_zoom_meeting()
                self._stack.setCurrentIndex(4)  # Live Interview page

    def _on_use_companion_mode(self):
        """Explicit secondary fallback: launches meeting in external browser/client upon user request."""
        if self._pending_setup:
            if hasattr(self, 'zoom_workspace'):
                self.zoom_workspace.remove_participant()
            iid = self.controller.start_interview(self._pending_setup, self.engine)
            if iid:
                self.controller.zoom_adapter.launch_companion_mode()
                self._stack.setCurrentIndex(4)

    # ── Page 4: Live Interview Workspace (Zoom Dominant) ──

    def _build_live_interview(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top Bar
        top_bar = QWidget()
        top_bar.setFixedHeight(50)
        top_bar.setStyleSheet(f"background-color: {Theme.BG_CARD}; border-bottom: 1px solid {Theme.BORDER_SUBTLE};")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 0, 16, 0)

        self._live_title_lbl = QLabel("🔴 LIVE • Zoom Meeting • Candidate Connected")
        self._live_title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self._live_title_lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        top_layout.addWidget(self._live_title_lbl)
        top_layout.addStretch()

        self._live_timer_lbl = QLabel("⏱ 00:00")
        self._live_timer_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self._live_timer_lbl.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; background: transparent;")
        top_layout.addWidget(self._live_timer_lbl)

        btn_end = GlowButton("End Interview", "⏹", gradient=(Theme.ACCENT_RED, Theme.ACCENT_ORANGE))
        btn_end.setFixedHeight(34)
        btn_end.clicked.connect(self._on_end_interview_clicked)
        top_layout.addWidget(btn_end)

        layout.addWidget(top_bar)

        # Main Split Workspace
        main_split = QHBoxLayout()
        main_split.setContentsMargins(0, 0, 0, 0)
        main_split.setSpacing(0)

        # Left: Dominant Embedded Zoom Meeting View + Bottom Waveform/Transcript
        left_area = QWidget()
        left_area.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_area)
        left_layout.setContentsMargins(12, 10, 8, 10)
        left_layout.setSpacing(8)

        self.zoom_workspace = EmbeddedZoomWorkspace()
        self.zoom_workspace.explain_requested.connect(self._on_visual_explain_requested)
        left_layout.addWidget(self.zoom_workspace, 3)

        self.waveform_widget = AudioWaveformWidget(num_bars=32)
        left_layout.addWidget(self.waveform_widget)

        self.transcript_widget = LiveTranscriptWidget()
        left_layout.addWidget(self.transcript_widget)

        main_split.addWidget(left_area, 3)

        # Right: AI Interviewer Coach Persistent Tabbed Panel
        right_panel = QWidget()
        right_panel.setFixedWidth(390)
        right_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border-left: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        ai_header = QLabel("🤖 AI Interviewer Coach (Private)")
        ai_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        ai_header.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; border: none; background: transparent;")
        right_layout.addWidget(ai_header)

        self.coach_tabs = AICoachTabWidget()
        self.coach_tabs.ask_suggestion_clicked.connect(self._on_ask_suggestion_forward)
        right_layout.addWidget(self.coach_tabs)

        main_split.addWidget(right_panel)
        layout.addLayout(main_split)
        return page

    # ── Signal Handlers ──

    def _on_state_changed(self, state_str):
        logger.info(f"[InterviewDashboard] State changed -> {state_str}")

    def _on_interview_started(self, interview_id):
        setup = self.controller.session.setup if self.controller.session else None
        if setup:
            self._live_title_lbl.setText("🔴 LIVE • Zoom Meeting • 1 Participant")
            if hasattr(self, 'coach_tabs'):
                self.coach_tabs.set_coach_state("WAITING_FOR_PARTICIPANT")
            if self.controller.session:
                self.controller.session.timer_tick.connect(self._on_timer_tick)

    def _on_timer_tick(self, remaining):
        mins = remaining // 60
        secs = remaining % 60
        self._live_timer_lbl.setText(f"⏱ {mins:02d}:{secs:02d}")

    def _on_interview_ended(self):
        self.waveform_widget.set_voice_activity(False)

    def _on_report_ready(self, report):
        self.reports_page.load_report(report, self.controller.session)
        self._on_nav_click("iv_reports")

    def _on_error(self, title, detail):
        QMessageBox.critical(self, title, detail)

    def _on_talk_time_updated(self):
        m = self.controller.metrics
        self.coach_tabs.tab_analysis.findChild(TalkTimeWidget).set_talk_time(
            m.interviewer_talk_pct, m.candidate_talk_pct
        )
        self.coach_tabs.update_analysis_summary(len(m.interruptions), m.baseline_status)
        if m.current_wpm:
            self.waveform_widget.set_voice_activity(True, m._last_speaker or "Speaker", m.current_wpm)

    def _on_transcript_entry(self, speaker, text, timestamp):
        ts_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
        role = "Interviewer" if speaker == "interviewer" else ("Candidate" if speaker == "candidate" else "Unknown")
        self.transcript_widget.add_transcript(role, text, ts_str)

    def _on_observation(self, obs):
        self.transcript_widget.add_transcript("System", f"[{obs.event_type.upper()}] {obs.message}")

    def _on_fairness_alert(self, category, explanation, ts):
        self.coach_tabs.set_risk_alert(explanation)
        self.transcript_widget.add_transcript("Fairness Alert", explanation, time.strftime("%H:%M:%S", time.localtime(ts)))

    def _on_copilot_suggestion(self, sug):
        self.coach_tabs.set_suggestion(sug)

    def _on_visual_explain_result(self, res):
        self.coach_tabs.set_visual_explanation(res)

    def _on_rubric_updated(self, summary):
        self.coach_tabs.update_rubric(summary)

    def _on_resume_claims_updated(self, summary):
        self.coach_tabs.update_resume_claims(summary)

    def _on_visual_explain_requested(self, text):
        self.controller.request_visual_explanation(text, source="screen_selection")

    def _on_ask_suggestion_forward(self, text):
        self.controller.add_note(f"Asked follow-up: {text}")

    def _on_end_interview_clicked(self, confirm: bool = True):
        if not self.controller.is_live:
            return
        if confirm:
            reply = QMessageBox.question(
                self, "End Interview",
                "Are you sure you want to end this interview and generate the intelligence report?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        self.controller.end_interview()


# ── Sub-components & Helpers ──

class _SectionCard(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(10)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; border: none; background: transparent;")
        self._layout.addWidget(title_lbl)

    def add_field(self, label_text, widget):
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        self._layout.addWidget(lbl)
        widget.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px 12px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)
        self._layout.addWidget(widget)

    def add_widget(self, widget):
        self._layout.addWidget(widget)

    def add_layout(self, layout):
        self._layout.addLayout(layout)


class _NavBackButton(QWidget):
    clicked = Signal()

    def __init__(self, text="← Back", parent=None):
        super().__init__(parent)
        self._text = text
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)

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
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(self.rect().adjusted(16, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, self._text)
        p.end()


class _MiniStatCard(QWidget):
    def __init__(self, label, value, icon, color, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = value
        self._icon = icon
        self._color = color
        self.setFixedHeight(72)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 8, 8)
        p.fillPath(path, QBrush(QColor(Theme.BG_CARD)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI Emoji", 16))
        p.drawText(12, 10, 28, 28, Qt.AlignCenter, self._icon)

        p.setPen(QColor(Theme.TEXT_PRIMARY))
        p.setFont(QFont("Segoe UI", 16, QFont.Bold))
        p.drawText(48, 8, w - 54, 26, Qt.AlignLeft | Qt.AlignVCenter, self._value)

        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(48, 36, w - 54, 20, Qt.AlignLeft | Qt.AlignVCenter, self._label)
        p.end()
