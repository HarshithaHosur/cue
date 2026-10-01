# ============================================================
#  AI INTERVIEW DASHBOARD — Full interview workspace
# ============================================================

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
    QScrollArea, QFrame, QSizePolicy, QLineEdit, QComboBox,
    QSpinBox, QTextEdit, QRadioButton, QButtonGroup, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QBrush, QPen,
    QLinearGradient
)
from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import (
    GlowButton, SectionHeader, SidebarNavItem, StatusBadge
)
from intent_platform.ui.pages.interview.live_widgets import (
    AudioWaveformWidget, LiveVideoPanel, LiveMetricCard, LiveTranscriptWidget
)
from intent_platform.ui.pages.interview.report_and_settings_view import (
    PreviousInterviewsView, ReportsView, InterviewSettingsView
)
from intent_platform.core.interview.store import interview_store
from intent_platform.core.interview.session import InterviewSession
from intent_platform.core.interview.models import InterviewSetup, InterviewState
from intent_platform.core.interview.gesture_router import GestureRouter
from intent_platform.core.interview.observation_engine import ObservationEngine
from intent_platform.core.interview.voice_router import VoiceRouter


class InterviewDashboard(QWidget):
    """Complete AI Interview Agent workspace with sub-navigation."""

    navigate_back = Signal()

    def __init__(self, engine=None, user_profile=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.user_profile = user_profile
        self._build_ui()

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
            ("iv_live", "🔴", "Live Interviews"),
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
        self._stack.addWidget(self.previous_page)                # 3: Previous
        self._stack.addWidget(self.reports_page)                 # 4: Reports
        self._stack.addWidget(self.settings_page)                # 5: Settings

        layout.addWidget(self._stack)

        # Activate first
        self._on_nav_click("iv_dashboard")

    def _on_nav_click(self, page_id):
        idx_map = {
            "iv_dashboard": 0, "iv_create": 1, "iv_live": 2,
            "iv_previous": 3, "iv_reports": 4, "iv_settings": 5
        }
        idx = idx_map.get(page_id, 0)
        self._stack.setCurrentIndex(idx)
        for item in self._nav_items:
            item.set_active(item._page_id == page_id)

    def _on_start_interview(self):
        """Validate form, save via interview_store, create session, and transition to LIVE."""
        title = self.input_title.text().strip() or "Standard AI Interview"
        candidate = self.input_candidate.text().strip() or "Candidate"
        role = self.input_role.text().strip() or "Software Engineer"
        duration = self.spin_duration.value()
        difficulty = self.combo_difficulty.currentText()

        selected_rb = self.btn_group_type.checkedButton()
        itype = selected_rb.text() if selected_rb else "Technical"

        # 1. Save via interview_store
        setup_data = {
            "title": title,
            "candidate_name": candidate,
            "candidate_email": f"{candidate.lower().replace(' ', '.')}@example.com",
            "job_role": role,
            "interview_type": itype,
            "duration_minutes": duration,
            "difficulty": difficulty,
            "status": "scheduled",
        }
        self.interview_id = interview_store.create_interview(setup_data)

        # 2. Create InterviewSession
        self.session = InterviewSession()
        setup_obj = InterviewSetup(
            title=title,
            candidate_name=candidate,
            job_role=role,
            interview_type=itype,
            duration_minutes=duration,
            difficulty=difficulty,
        )
        self.session.initialize(setup_obj)
        self.session.transition_to(InterviewState.VERIFYING)

        # 3. Transition to LIVE
        self._enter_live_session()

    def _enter_live_session(self):
        """Transition session to LIVE, hook engine frame tap, gesture interceptor, voice router, and timeline event listener."""
        if hasattr(self, 'session') and self.session:
            self.session.transition_to(InterviewState.LIVE)
            # Step 4: Show timeline events from session.emit_event in live page
            self.session.event_logged.connect(self._on_event_logged)

        # Step 3: Wire routers & engine hooks
        self.gesture_router = GestureRouter()
        self.gesture_router.active = True
        self.gesture_router.on_next_question = lambda: self._on_nav_question(1)
        self.gesture_router.on_previous_question = lambda: self._on_nav_question(-1)

        self.voice_router = VoiceRouter()
        self.voice_router.on_next_question = lambda: self._on_nav_question(1)
        self.voice_router.on_previous_question = lambda: self._on_nav_question(-1)

        self.obs_engine = ObservationEngine()

        if self.engine:
            self.engine.add_frame_tap(self._on_frame_tap)
            self.engine.gesture_interceptor = self.gesture_router.intercept
            if hasattr(self.engine, 'voice_engine') and self.engine.voice_engine:
                self.engine.voice_engine.set_interview_hooks(self.voice_router, self._on_transcript_tap)
                self.engine.voice_engine.interview_mode = True

        self._on_nav_click("iv_live")

    def _exit_live_session(self):
        """Undo all engine hooks and routers on End Interview."""
        if self.engine:
            self.engine.remove_frame_tap(self._on_frame_tap)
            self.engine.gesture_interceptor = None
            if hasattr(self.engine, 'voice_engine') and self.engine.voice_engine:
                self.engine.voice_engine.set_interview_hooks(None, None)
                self.engine.voice_engine.interview_mode = False

        if hasattr(self, 'gesture_router') and self.gesture_router:
            self.gesture_router.active = False

        if hasattr(self, 'session') and self.session and self.session.state == InterviewState.LIVE:
            self.session.transition_to(InterviewState.ENDED)
            self.session.transition_to(InterviewState.REPORTED)

    def _on_frame_tap(self, frame):
        """Frame tap callback feeding live frame to ObservationEngine and video view."""
        if hasattr(self, 'obs_engine') and self.obs_engine:
            self.obs_engine.process_frame(frame)

    def _on_transcript_tap(self, entry):
        """Transcript tap callback feeding live transcript widget."""
        role = "Interviewer" if entry.get("has_wake") else "Candidate"
        text = entry.get("text", "")
        if hasattr(self, 'transcript_widget') and self.transcript_widget:
            self.transcript_widget.add_transcript(role, text)

    def _on_event_logged(self, event_type, message, payload, timestamp):
        """Step 4: Show timeline events from session.emit_event in live page."""
        if hasattr(self, 'transcript_widget') and self.transcript_widget:
            self.transcript_widget.add_transcript("Timeline", f"[{event_type.upper()}] {message}")

    def _on_nav_question(self, delta):
        pass

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

        header = SectionHeader("Interview Dashboard", "Manage and monitor AI-powered interviews")
        layout.addWidget(header)

        # Stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        for lbl, val, icon, color in [
            ("Total Interviews", "0", "📊", Theme.ACCENT_BLUE),
            ("Active Now", "0", "🔴", Theme.ACCENT_RED),
            ("Completed", "0", "✅", Theme.ACCENT_GREEN),
            ("Avg Score", "—", "⭐", Theme.ACCENT_ORANGE),
        ]:
            card = _MiniStatCard(lbl, val, icon, color)
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Empty state
        empty = _EmptyState(
            "No Interview Running",
            "Create a new interview session to get started with AI-powered candidate evaluation.",
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
        self.input_candidate.setPlaceholderText("e.g. John Doe")
        self.input_meeting = QLineEdit()
        self.input_meeting.setPlaceholderText("e.g. https://meet.google.com/...")

        fields = [
            ("Interview Title", self.input_title),
            ("Job Role", self.input_role),
            ("Candidate Name", self.input_candidate),
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

    def _build_live_interview(self):
        """Professional meeting-like interface for live interviews with real-time video, waveform, and AI analytics."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left: Video streams, Audio Waveform & Transcript ──
        left_area = QWidget()
        left_area.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_area)
        left_layout.setContentsMargins(18, 16, 12, 16)
        left_layout.setSpacing(10)

        # Top Stream row: Candidate camera & Screen share
        streams_row = QHBoxLayout()
        streams_row.setSpacing(10)

        self.cam_panel = LiveVideoPanel("Candidate Camera (HD)", "📹", is_screen_share=False)
        self.screen_panel = LiveVideoPanel("Screen Share / Workspace", "🖥", is_screen_share=True)

        streams_row.addWidget(self.cam_panel, 1)
        streams_row.addWidget(self.screen_panel, 1)
        left_layout.addLayout(streams_row, 3)

        # Audio Waveform Visualizer (Real-time voice spectrum)
        self.waveform_widget = AudioWaveformWidget(num_bars=32)
        left_layout.addWidget(self.waveform_widget)

        # Live Transcript Ticker
        self.transcript_widget = LiveTranscriptWidget()
        left_layout.addWidget(self.transcript_widget)

        layout.addWidget(left_area, 3)

        # ── Right: AI Intelligence & Live Analytics ──
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
        right_layout.setSpacing(10)

        # Title & Live Badge Header
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        ai_title = QLabel("🤖 AI Interview Agent")
        ai_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        ai_title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        header_row.addWidget(ai_title)

        live_badge = StatusBadge("LIVE", "active")
        header_row.addWidget(live_badge, alignment=Qt.AlignRight)
        right_layout.addLayout(header_row)

        status_lbl = QLabel("● Real-time Monitoring & AI Assistant Active")
        status_lbl.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        status_lbl.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; border: none; background: transparent;")
        right_layout.addWidget(status_lbl)

        # Live Metric Cards
        self.card_pace = LiveMetricCard("Communication Pace", "142 WPM", 88, "Optimal", Theme.ACCENT_GREEN)
        self.card_eye = LiveMetricCard("Eye Contact Ratio", "94%", 94, "Strong", Theme.ACCENT_CYAN)
        self.card_integrity = LiveMetricCard("Integrity Monitor", "Clean", 98, "Verified", Theme.ACCENT_GREEN)
        self.card_coding = LiveMetricCard("Coding Analytics", "Python", 85, "O(n) Time", Theme.ACCENT_PURPLE)

        right_layout.addWidget(self.card_pace)
        right_layout.addWidget(self.card_eye)
        right_layout.addWidget(self.card_integrity)
        right_layout.addWidget(self.card_coding)

        # Standard Analysis Sections for AI Assistant and Notes
        sections = [
            ("AI Assistant Prompt", "Ready for commands..."),
            ("Interview Notes", "Auto-generating summary...")
        ]
        for name, status in sections:
            section = _AnalysisSection(name)
            section._status = status
            right_layout.addWidget(section)

        # AI Companion Status Bubble
        companion_bubble = QLabel("💬 AI Companion: Listening to speech stream & tracking gesture shortcuts...")
        companion_bubble.setWordWrap(True)
        companion_bubble.setStyleSheet(f"""
            background-color: {Theme.BG_DARKER};
            color: {Theme.TEXT_PRIMARY};
            border-radius: 8px;
            padding: 10px;
            font-style: italic;
            font-size: 11px;
        """)
        right_layout.addWidget(companion_bubble)

        right_layout.addStretch()
        layout.addWidget(right_panel)

        return page

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


class _VideoPlaceholder(QWidget):
    def __init__(self, title, icon, message, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon = icon
        self._message = message
        self.setMinimumHeight(150)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 12, 12)
        p.fillPath(path, QBrush(QColor(Theme.BG_DARKEST)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)

        p.setPen(QColor(Theme.TEXT_MUTED))
        p.setFont(QFont("Segoe UI Emoji", 32))
        p.drawText(self.rect().adjusted(0, -20, 0, 0), Qt.AlignCenter, self._icon)

        p.setFont(QFont("Segoe UI", 11))
        p.drawText(self.rect().adjusted(0, 30, 0, 0), Qt.AlignCenter, self._message)

        # Title badge
        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p.drawText(12, 18, self._title)
        p.end()


class _AnalysisSection(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self._title = title
        self._status = "No data"
        self.setFixedHeight(48)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 8, 8)
        p.fillPath(path, QBrush(QColor(Theme.BG_DARKER)))

        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(12, 0, w // 2, h, Qt.AlignLeft | Qt.AlignVCenter, self._title)

        p.setPen(QColor(Theme.TEXT_MUTED))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(0, 0, w - 12, h, Qt.AlignRight | Qt.AlignVCenter, self._status)
        p.end()
