# ============================================================
#  MAIN WINDOW — Glassmorphic Application Shell & Navigation
# ============================================================

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QStatusBar
)

from intent_platform.config.settings import (
    APP_NAME, APP_VERSION, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT
)
from intent_platform.ui.theme import Theme
from intent_platform.ui.pages.home_dashboard import HomeDashboard
from intent_platform.ui.pages.interview.interview_dashboard import InterviewDashboard
from intent_platform.ui.pages.support.support_dashboard import SupportDashboard
from intent_platform.ui.pages.gesture_voice_settings import GestureVoiceSettingsView
from intent_platform.ui.pages.settings_profile import SettingsPage, ProfilePage, AnalyticsPage
from intent_platform.ui.companion.companion_window import DesktopCompanionOverlay
from intent_platform.core.support.support_agent import get_support_agent
from intent_platform.core.support.highlighter import initialize_highlighter
from intent_platform.core.support.audit_logger import global_audit_logger
from intent_platform.core.agent.agent_controller import get_agent_controller, AgentState
from intent_platform.core.features.feature_manager import get_feature_manager, Feature


class MainWindow(QMainWindow):
    """Main desktop application window hosting sidebar and pages."""

    def __init__(self, user_profile: dict = None, engine = None, parent=None):
        super().__init__(parent)
        self.user_profile = user_profile or {"username": "Harshitha", "full_name": "Harshitha"}
        self.engine = engine

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Unified singletons
        self.agent_controller = get_agent_controller()
        self.feature_manager = get_feature_manager()

        # Companion overlay — positioned dynamically at resting bottom-right
        self.companion = DesktopCompanionOverlay()
        self.companion.snap_to_resting_position()
        self.companion.show()

        # Initialize screen highlighter overlay (must exist before agent starts)
        self.screen_highlighter = initialize_highlighter()

        # Initialize AI Customer Support Agent
        self.support_agent = get_support_agent()
        self.support_agent.set_companion(self.companion)

        self._init_ui()
        self._connect_engine()
        self._connect_support_agent()

    def _init_ui(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {Theme.BASE};
            }}
            QWidget {{
                color: {Theme.TEXT};
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 1. Glassmorphic Sidebar ──
        sidebar = self._build_sidebar()
        main_layout.addWidget(sidebar)

        # ── 2. Content Area (Top Bar + Stacked Pages) ──
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top Bar
        top_bar = self._build_top_bar()
        content_layout.addWidget(top_bar)

        # Page Stack
        self.stack = QStackedWidget()
        user_name = self.user_profile.get("full_name") or self.user_profile.get("username", "Operator")
        user_handle = self.user_profile.get("username", "user")

        self.page_home = HomeDashboard(username=user_name)
        self.page_interview = InterviewDashboard(engine=self.engine, user_profile=self.user_profile)
        self.page_support = SupportDashboard()
        self.page_gestures = GestureVoiceSettingsView()
        self.page_analytics = AnalyticsPage()
        self.page_settings = SettingsPage()
        self.page_profile = ProfilePage(username=user_name, email=f"{user_handle}@intent.os")

        self.stack.addWidget(self.page_home)         # 0
        self.stack.addWidget(self.page_interview)    # 1
        self.stack.addWidget(self.page_support)      # 2
        self.stack.addWidget(self.page_gestures)     # 3
        self.stack.addWidget(self.page_analytics)    # 4
        self.stack.addWidget(self.page_settings)     # 5
        self.stack.addWidget(self.page_profile)      # 6

        # Wire navigation connections
        self.page_home.navigate_to.connect(self._handle_home_navigate)
        if hasattr(self.page_interview, 'navigate_back'):
            self.page_interview.navigate_back.connect(lambda: self._switch_page(0))
        if hasattr(self.page_support, 'navigate_back'):
            self.page_support.navigate_back.connect(lambda: self._switch_page(0))
        if hasattr(self.page_settings, 'navigate_back'):
            self.page_settings.navigate_back.connect(lambda: self._switch_page(0))
        if hasattr(self.page_profile, 'navigate_back'):
            self.page_profile.navigate_back.connect(lambda: self._switch_page(0))

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_container, 1)

    def _build_sidebar(self) -> QWidget:
        w = QFrame()
        w.setFixedWidth(240)
        w.setStyleSheet(f"""
            QFrame {{
                background: {Theme.MANTLE};
                border-right: 1px solid {Theme.SURFACE0};
            }}
        """)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(8)

        # Brand
        brand = QLabel("INTENT OS")
        brand.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {Theme.BLUE}; letter-spacing: 2px; padding-left: 8px; margin-bottom: 16px;")
        layout.addWidget(brand)

        # Nav Buttons
        self.nav_btns = []
        nav_items = [
            ("🏠  Overview", 0),
            ("💼  AI Interview", 1),
            ("🛠️  Tech Support", 2),
            ("✋  Gestures & Voice", 3),
            ("📊  Analytics", 4),
            ("⚙️  Settings", 5),
            ("👤  Profile", 6),
        ]

        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Theme.SUBTEXT0};
                    font-size: 13px;
                    font-weight: 600;
                    text-align: left;
                    padding: 12px 16px;
                    border-radius: 8px;
                    border: none;
                }}
                QPushButton:hover {{
                    background: {Theme.SURFACE0};
                    color: {Theme.TEXT};
                }}
                QPushButton:checked {{
                    background: {Theme.SURFACE1};
                    color: {Theme.BLUE};
                    font-weight: 700;
                    border-left: 3px solid {Theme.BLUE};
                }}
            """)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            layout.addWidget(btn)
            self.nav_btns.append(btn)

        self.nav_btns[0].setChecked(True)
        layout.addStretch()

        # Version tag
        v_tag = QLabel(f"Platform v{APP_VERSION}")
        v_tag.setStyleSheet(f"color: {Theme.OVERLAY0}; font-size: 11px; padding-left: 8px;")
        layout.addWidget(v_tag)

        return w

    def _build_top_bar(self) -> QWidget:
        w = QFrame()
        w.setFixedHeight(64)
        w.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BASE};
                border-bottom: 1px solid {Theme.SURFACE0};
            }}
        """)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(16)

        self.page_title = QLabel("System Overview")
        self.page_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {Theme.TEXT};")
        layout.addWidget(self.page_title)

        layout.addStretch()

        # Telemetry badges
        self.badge_vision = QLabel("● Vision: Idle (0 fps)")
        self.badge_vision.setStyleSheet(f"background: {Theme.SURFACE0}; color: {Theme.TEAL}; padding: 6px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;")

        self.badge_voice = QLabel("● Voice: Ready")
        self.badge_voice.setStyleSheet(f"background: {Theme.SURFACE0}; color: {Theme.BLUE}; padding: 6px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;")

        self.badge_sec = QLabel("● Security: 3-Layer Ok")
        self.badge_sec.setStyleSheet(f"background: {Theme.SURFACE0}; color: {Theme.GREEN}; padding: 6px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;")

        layout.addWidget(self.badge_vision)
        layout.addWidget(self.badge_voice)
        layout.addWidget(self.badge_sec)

        # AI Agent Activation Toggle — starts deactivated
        self.btn_agent = QPushButton("⚡ Activate AI Agent")
        self.btn_agent.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.SURFACE1};
                color: {Theme.TEXT};
                padding: 6px 14px;
                border-radius: 8px;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid {Theme.BLUE};
            }}
            QPushButton:hover {{
                background: {Theme.SURFACE2};
            }}
        """)
        self.btn_agent.clicked.connect(self._toggle_agent)
        layout.addWidget(self.btn_agent)

        # Companion Toggle
        toggle_comp_btn = QPushButton("🤖 Robot")
        toggle_comp_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.SURFACE1};
                color: {Theme.TEXT};
                padding: 6px 14px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid {Theme.SURFACE2};
            }}
            QPushButton:hover {{
                background: {Theme.SURFACE2};
            }}
        """)
        toggle_comp_btn.clicked.connect(self._toggle_companion)
        layout.addWidget(toggle_comp_btn)

        # User avatar badge
        user_lbl = QLabel(f"👤 {self.user_profile.get('full_name', 'Operator')}")
        user_lbl.setStyleSheet(f"background: {Theme.SURFACE0}; color: {Theme.LAVENDER}; font-weight: 700; padding: 6px 14px; border-radius: 8px; font-size: 12px;")
        layout.addWidget(user_lbl)

        return w

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        titles = [
            "System Overview",
            "AI Interview Intelligence",
            "AI Technical Support & Hardware Health",
            "Gestures & Voice Command Matrix",
            "System Analytics & Telemetry",
            "Platform Settings",
            "User Profile & Biometrics"
        ]
        if index < len(titles):
            self.page_title.setText(titles[index])
        if 0 <= index < len(self.nav_btns):
            self.nav_btns[index].setChecked(True)

    def _handle_home_navigate(self, page_id: str):
        mapping = {
            "overview": 0,
            "interview": 1,
            "support": 2,
            "gestures": 3,
            "gesture_test": 3,
            "voice_test": 3,
            "cursor_cal": 3,
            "analytics": 4,
            "settings": 5,
            "profile": 6,
        }
        target_idx = mapping.get(page_id, 0)
        self._switch_page(target_idx)

    def _toggle_agent(self):
        """Unified dashboard button toggle via central AgentController."""
        self.agent_controller.toggle(source="dashboard_button")

    def _toggle_companion(self):
        """Toggles companion visibility while preserving agent state."""
        if self.companion.isVisible():
            self.companion.hide()
            if self.agent_controller.is_active:
                self.agent_controller.deactivate(source="companion_hide")
        else:
            self.companion.show()
            self.companion.snap_to_resting_position()

    @Slot(str, str)
    def _on_agent_state_changed(self, state_str: str, message: str):
        """Synchronizes main window button state with AgentController."""
        if state_str in (AgentState.ACTIVATING.value, AgentState.ACTIVE.value, AgentState.PROCESSING.value):
            self.btn_agent.setText("⏹️ Deactivate AI Agent")
            self.btn_agent.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.BLUE};
                    color: {Theme.BASE};
                    padding: 6px 14px;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 12px;
                    border: none;
                }}
                QPushButton:hover {{
                    background: {Theme.SAPPHIRE};
                }}
            """)
            if not self.companion.isVisible():
                self.companion.show()
        else:
            self.btn_agent.setText("⚡ Activate AI Agent")
            self.btn_agent.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.SURFACE1};
                    color: {Theme.TEXT};
                    padding: 6px 14px;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 12px;
                    border: 1px solid {Theme.BLUE};
                }}
                QPushButton:hover {{
                    background: {Theme.SURFACE2};
                }}
            """)

    def _connect_engine(self):
        # Connect AgentController lifecycle state
        self.agent_controller.signals.state_changed.connect(self._on_agent_state_changed)

        if not self.engine:
            return

        self.engine.signals.system_status.connect(self._on_system_status)
        self.engine.signals.companion_state.connect(self.companion.update_companion_state)
        self.engine.signals.gesture_detected.connect(self._on_gesture)
        self.engine.signals.voice_detected.connect(self._on_voice)

    @Slot(dict)
    def _on_system_status(self, data: dict):
        fps = data.get("fps", 0)
        mode = data.get("mode", "idle").title()
        self.badge_vision.setText(f"● Vision: {mode} ({fps} fps)")

        if data.get("face_ok"):
            self.badge_sec.setText("● Security: Verified")
            self.badge_sec.setStyleSheet(f"background: {Theme.SURFACE0}; color: {Theme.GREEN}; padding: 6px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;")
        else:
            self.badge_sec.setText("● Security: Blocked")
            self.badge_sec.setStyleSheet(f"background: {Theme.SURFACE0}; color: {Theme.RED}; padding: 6px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;")

    @Slot(str, str)
    def _on_gesture(self, gesture: str, action: str):
        self.companion.update_companion_state("success", f"{gesture}: {action}")

    @Slot(str, str)
    def _on_voice(self, transcript: str, action: str):
        self.companion.update_companion_state("speaking", f"Heard: '{transcript}'")
        # Route support-related commands to the AI Customer Support Agent
        self._route_to_support_agent(transcript)

    def _route_to_support_agent(self, command: str):
        """Checks if the voice command is a support-related request and routes it."""
        cmd_lower = command.lower().strip()
        support_triggers = [
            'help me', 'replace', 'return', 'refund', 'explain this', 'explain page',
            'customer support', 'customer care', 'customer service', 'support', 'order',
            'complaint', 'complain', 'contact',
            'amazon', 'meesho', 'cart', 'returns', 'help',
            'download statement', 'statement', 'scroll down', 'scroll up',
            'highlight', 'fill this form', 'summarize', 'policy',
            'continue', 'confirm', 'proceed', 'stop', 'cancel', 'abort', 'no',
            'cold', 'delayed', 'wrong', 'damaged',
            # Technical Support Executive Voice Triggers
            'install', 'installer', 'python', 'vscode', 'vs code', 'node', 'git', 'docker',
            'error', 'traceback', 'syntaxerror', 'modulenotfound', 'terminal',
            'wifi', 'wi-fi', 'network', 'internet', 'battery', 'charge', 'power saver'
        ]
        import re
        confirmation_text = re.sub(r"[^\w\s]", "", cmd_lower).strip()
        confirmation_phrases = {"yes", "yes please", "sure", "go ahead", "go ahead please", "do it"}
        has_pending_action = (
            self.support_agent.safety_manager.has_pending_action()
            or bool(getattr(self.support_agent, "active_tech_action", None))
        )
        if any(kw in cmd_lower for kw in support_triggers) or (
            confirmation_text in confirmation_phrases and has_pending_action
        ):
            # Route to agent dashboard and display there
            agent_dash = self.page_support.agent_dashboard
            agent_dash.add_user_message(command)
            self.support_agent.handle_user_request(command)

    def closeEvent(self, event):
        if self.engine:
            self.engine.stop()
        if self.companion:
            self.companion.close()
        if self.screen_highlighter:
            self.screen_highlighter.close()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()
        event.accept()

    def _connect_support_agent(self):
        """Wires the AI Customer Support Agent signals to the Agent Dashboard UI."""
        agent = self.support_agent
        agent_dash = self.page_support.agent_dashboard
        agent_dash.load_history(agent.conversation_store.recent_turns())

        # Reasoning steps -> Reasoning Panel
        agent.signals.reasoning_step.connect(agent_dash.add_reasoning_step)
        # AI text+voice responses -> Chat Panel
        agent.signals.response_ready.connect(agent_dash.add_response)
        # Context updates -> Context Bar
        agent.signals.context_updated.connect(agent_dash.update_context)
        # Agent state -> Status label & Companion animation
        agent.signals.state_changed.connect(agent_dash.update_agent_state)
        # Confirmation requests -> Confirmation Bar
        agent.signals.confirmation_required.connect(agent_dash.show_confirmation)
        # Action execution -> Chat Panel confirmation
        agent.signals.action_executed.connect(agent_dash.on_action_executed)

        # Audit trail entries -> Audit Panel
        global_audit_logger.signals.entry_added.connect(agent_dash.add_audit_entry)

        # Dashboard UI -> Agent: typed commands
        agent_dash.user_command_submitted.connect(self._on_agent_dashboard_command)
        # Dashboard UI -> Agent: confirm/cancel buttons
        agent_dash.user_confirmed_action.connect(agent.confirm_pending_action)
        agent_dash.user_cancelled_action.connect(agent.cancel_pending_action)

        # Wire voice engine to support agent so it can speak
        if self.engine and hasattr(self.engine, 'voice_engine'):
            agent.set_voice_engine(self.engine.voice_engine)

    def _on_agent_dashboard_command(self, command: str):
        """Handles typed commands from the Agent Dashboard chat input."""
        self.support_agent.handle_user_request(command)
