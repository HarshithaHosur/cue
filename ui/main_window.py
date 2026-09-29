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


class MainWindow(QMainWindow):
    """Main desktop application window hosting sidebar and pages."""

    def __init__(self, user_profile: dict = None, engine = None, parent=None):
        super().__init__(parent)
        self.user_profile = user_profile or {"username": "Harshitha", "full_name": "Harshitha"}
        self.engine = engine

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Companion overlay — starts hidden until user clicks Robot button
        self.companion = DesktopCompanionOverlay()
        self.companion.move(1400, 600)

        self._init_ui()
        self._connect_engine()

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
        self.page_interview = InterviewDashboard()
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
        if not self.engine:
            return
        if self.engine.is_agent_active:
            self.engine.deactivate_agent()
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
        else:
            self.engine.activate_agent()
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

    def _toggle_companion(self):
        if self.companion.isVisible():
            self.companion.hide()
            # Deactivate agent when companion is hidden
            if self.engine and self.engine.is_agent_active:
                self.engine.deactivate_agent()
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
        else:
            self.companion.show()
            # Activate agent when companion is shown
            if self.engine and not self.engine.is_agent_active:
                self.engine.activate_agent()
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

    def _connect_engine(self):
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

    def closeEvent(self, event):
        if self.engine:
            self.engine.stop()
        if self.companion:
            self.companion.close()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()
        event.accept()
