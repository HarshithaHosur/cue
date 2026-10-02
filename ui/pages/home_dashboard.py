# ============================================================
#  HOME DASHBOARD — Main landing page after login
# ============================================================

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QScrollArea, QFrame, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush, QPen, QLinearGradient
from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import (
    DashboardCard, SectionHeader, StatCard, GlowButton, StatusBadge
)
from intent_platform.ui.widgets.control_center import ControlCenterWidget


class HomeDashboard(QWidget):
    """Main dashboard shown after successful authentication."""

    navigate_to = Signal(str)  # Emits page ID to navigate

    def __init__(self, username="User", parent=None):
        super().__init__(parent)
        self._username = username
        self.setObjectName("homeDashboard")
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(40, 32, 40, 40)
        main_layout.setSpacing(32)

        # ── Welcome Header ──
        welcome_section = QWidget()
        welcome_section.setStyleSheet("background: transparent;")
        welcome_layout = QVBoxLayout(welcome_section)
        welcome_layout.setContentsMargins(0, 0, 0, 0)
        welcome_layout.setSpacing(6)

        greeting = QLabel(f"Welcome Back, {self._username} 👋")
        greeting.setFont(QFont("Segoe UI", 28, QFont.Bold))
        greeting.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        welcome_layout.addWidget(greeting)

        subtitle = QLabel("Choose an AI Agent to get started")
        subtitle.setFont(QFont("Segoe UI", 15))
        subtitle.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        welcome_layout.addWidget(subtitle)

        main_layout.addWidget(welcome_section)

        # ── Stats Row ──
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        stats = [
            ("Active Sessions", "0", "🟢", Theme.ACCENT_GREEN),
            ("Interviews Today", "0", "🎤", Theme.ACCENT_BLUE),
            ("Support Tickets", "0", "🛠", Theme.ACCENT_ORANGE),
            ("System Health", "100%", "💚", Theme.ACCENT_GREEN),
        ]
        for label, value, icon, color in stats:
            card = StatCard(label=label, value=value, icon_text=icon, color=color)
            stats_layout.addWidget(card)

        main_layout.addLayout(stats_layout)

        # ── Control Center (Capabilities ON/OFF) ──
        self.control_center = ControlCenterWidget()
        main_layout.addWidget(self.control_center)

        # ── Agent Cards ──
        cards_header = SectionHeader(title="AI Agents", subtitle="Launch a specialized AI workspace")
        main_layout.addWidget(cards_header)

        cards_grid = QGridLayout()
        cards_grid.setSpacing(20)

        # Card 1: AI Interview
        interview_card = DashboardCard(
            title="AI Interview Agent",
            description="Conduct intelligent AI-powered interviews with real-time analysis and candidate evaluation.",
            icon_text="🎤",
            gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_PURPLE),
            button_text="Launch"
        )
        interview_card.clicked.connect(lambda: self.navigate_to.emit("interview"))
        cards_grid.addWidget(interview_card, 0, 0)

        # Card 2: AI Technical Support
        support_card = DashboardCard(
            title="AI Technical Support",
            description="Diagnose and resolve computer issues with AI-powered system diagnostics and guided repair.",
            icon_text="🛠",
            gradient=(Theme.ACCENT_GREEN, Theme.ACCENT_CYAN),
            button_text="Open Support"
        )
        support_card.clicked.connect(lambda: self.navigate_to.emit("support"))
        cards_grid.addWidget(support_card, 0, 1)

        # Card 3: Analytics
        analytics_card = DashboardCard(
            title="Analytics",
            description="View usage statistics, performance insights and system reports. Coming soon.",
            icon_text="📈",
            gradient=(Theme.ACCENT_ORANGE, Theme.ACCENT_RED),
            button_text="Coming Soon"
        )
        analytics_card.clicked.connect(lambda: self.navigate_to.emit("analytics"))
        cards_grid.addWidget(analytics_card, 1, 0)

        # Card 4: Profile
        profile_card = DashboardCard(
            title="Profile",
            description="Manage your account, update credentials, view activity log and authentication status.",
            icon_text="👤",
            gradient=(Theme.ACCENT_PINK, Theme.ACCENT_PURPLE),
            button_text="View Profile"
        )
        profile_card.clicked.connect(lambda: self.navigate_to.emit("profile"))
        cards_grid.addWidget(profile_card, 1, 1)

        main_layout.addLayout(cards_grid)

        # ── Quick Actions ──
        quick_header = SectionHeader(title="Quick Actions")
        main_layout.addWidget(quick_header)

        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(12)

        actions = [
            ("⚙", "Settings", "settings"),
            ("🎤", "Voice Test", "voice_test"),
            ("✋", "Gesture Test", "gesture_test"),
            ("🖱", "Cursor Calibrate", "cursor_cal"),
        ]
        for icon, label, action_id in actions:
            btn = _QuickActionButton(icon, label)
            btn.clicked.connect(lambda checked=False, aid=action_id: self.navigate_to.emit(aid))
            quick_layout.addWidget(btn)

        quick_layout.addStretch()
        main_layout.addLayout(quick_layout)

        main_layout.addStretch()

        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)


class _QuickActionButton(QWidget):
    """Compact action button with icon + label."""
    clicked = Signal()

    def __init__(self, icon_text, label, parent=None):
        super().__init__(parent)
        self._icon = icon_text
        self._label = label
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(140, 48)

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
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 10, 10)

        if self._hover:
            p.fillPath(path, QBrush(QColor(Theme.BG_ELEVATED)))
            p.setPen(QPen(QColor(Theme.ACCENT_CYAN + "40"), 1))
            p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)
        else:
            p.fillPath(path, QBrush(QColor(Theme.BG_CARD)))
            p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
            p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)

        p.setPen(QColor(Theme.TEXT_PRIMARY))
        p.setFont(QFont("Segoe UI Emoji", 16))
        p.drawText(QRect(12, 0, 32, h), Qt.AlignCenter, self._icon)

        p.setFont(QFont("Segoe UI", 12))
        p.drawText(QRect(46, 0, w - 56, h), Qt.AlignLeft | Qt.AlignVCenter, self._label)
        p.end()
