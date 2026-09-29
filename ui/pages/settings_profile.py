# ============================================================
#  SETTINGS PAGE — Theme, notifications, companion, privacy
# ============================================================

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush, QPen, QLinearGradient
from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import SectionHeader


class SettingsPage(QWidget):
    """Application settings page."""
    navigate_back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(24)

        layout.addWidget(SectionHeader("Settings", "Customize your platform experience"))

        # ── Settings Groups ──
        settings_groups = [
            ("Appearance", [
                ("Theme", "toggle", ["Dark Mode", "Light Mode"], 0),
                ("Accent Color", "combo", ["Cyan", "Purple", "Blue", "Green"], 0),
                ("Font Size", "combo", ["Small", "Medium", "Large"], 1),
            ]),
            ("Notifications", [
                ("Desktop Notifications", "toggle", ["Enabled", "Disabled"], 0),
                ("Sound Alerts", "toggle", ["Enabled", "Disabled"], 0),
                ("Email Notifications", "toggle", ["Enabled", "Disabled"], 1),
            ]),
            ("AI Companion", [
                ("Robot Companion", "toggle", ["ON", "OFF"], 0),
                ("Companion Position", "combo", ["Bottom Right", "Bottom Left", "Top Right"], 0),
                ("Idle Animations", "toggle", ["Enabled", "Disabled"], 0),
                ("Speech Bubbles", "toggle", ["Enabled", "Disabled"], 0),
            ]),
            ("Voice & Input", [
                ("Microphone", "combo", ["Default Device", "USB Microphone", "Headset"], 0),
                ("Language", "combo", ["English (US)", "English (UK)", "English (India)"], 0),
                ("Wake Word", "combo", ["System", "Hey Assistant", "Computer"], 0),
            ]),
            ("Camera", [
                ("Camera Device", "combo", ["Default Camera", "External Webcam"], 0),
                ("Resolution", "combo", ["720p", "1080p", "480p"], 0),
            ]),
            ("Privacy & Security", [
                ("Face Auth Required", "toggle", ["Enabled", "Disabled"], 0),
                ("Multi-Face Lockout", "toggle", ["Enabled", "Disabled"], 0),
                ("Session Timeout", "combo", ["15 min", "30 min", "1 hour", "Never"], 1),
            ]),
        ]

        for group_title, items in settings_groups:
            group = _SettingsGroup(group_title, items)
            layout.addWidget(group)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)


class _SettingsGroup(QWidget):
    """A group of settings with a title."""

    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        layout.addWidget(title_lbl)
        layout.addSpacing(12)

        for i, (label, widget_type, options, default_idx) in enumerate(items):
            row = _SettingsRow(label, widget_type, options, default_idx)
            layout.addWidget(row)
            if i < len(items) - 1:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background-color: {Theme.BORDER_SUBTLE}; border: none;")
                layout.addWidget(sep)


class _SettingsRow(QWidget):
    """Single settings row with label and control."""

    def __init__(self, label, widget_type, options, default_idx, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet("border: none; background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)

        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 13))
        lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(lbl)
        layout.addStretch()

        if widget_type == "toggle":
            toggle = _ToggleSwitch(options, default_idx)
            layout.addWidget(toggle)
        elif widget_type == "combo":
            combo = QComboBox()
            combo.addItems(options)
            combo.setCurrentIndex(default_idx)
            combo.setFixedWidth(180)
            combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: {Theme.BG_INPUT};
                    border: 1px solid {Theme.BORDER_SUBTLE};
                    border-radius: 8px;
                    padding: 6px 12px;
                    color: {Theme.TEXT_PRIMARY};
                    font-size: 12px;
                }}
                QComboBox:hover {{ border-color: {Theme.BORDER_HOVER}; }}
                QComboBox::drop-down {{ border: none; width: 24px; }}
                QComboBox QAbstractItemView {{
                    background-color: {Theme.BG_CARD};
                    border: 1px solid {Theme.BORDER_SUBTLE};
                    color: {Theme.TEXT_PRIMARY};
                    selection-background-color: {Theme.BG_ELEVATED};
                }}
            """)
            layout.addWidget(combo)


class _ToggleSwitch(QWidget):
    """Custom toggle switch widget."""

    def __init__(self, options, default_idx=0, parent=None):
        super().__init__(parent)
        self._options = options
        self._active = default_idx == 0
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(56, 28)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._active = not self._active
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Track
        track = QPainterPath()
        track.addRoundedRect(0, 0, 56, 28, 14, 14)

        if self._active:
            p.fillPath(track, QBrush(QColor(Theme.ACCENT_CYAN)))
            # Knob
            p.setBrush(QBrush(QColor("white")))
            p.setPen(Qt.NoPen)
            p.drawEllipse(32, 4, 20, 20)
        else:
            p.fillPath(track, QBrush(QColor(Theme.BG_ELEVATED)))
            p.setBrush(QBrush(QColor(Theme.TEXT_MUTED)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(4, 4, 20, 20)

        p.end()


# ============================================================
#  PROFILE PAGE
# ============================================================

class ProfilePage(QWidget):
    """User profile management page."""
    navigate_back = Signal()

    def __init__(self, username="User", email="user@example.com", parent=None):
        super().__init__(parent)
        self._username = username
        self._email = email
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(24)

        layout.addWidget(SectionHeader("Profile", "Manage your account"))

        # Profile card
        card = QWidget()
        card.setFixedHeight(200)
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(24)

        # Avatar
        avatar = _AvatarWidget(self._username[0].upper() if self._username else "U")
        card_layout.addWidget(avatar)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)

        name_lbl = QLabel(self._username)
        name_lbl.setFont(QFont("Segoe UI", 22, QFont.Bold))
        name_lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        info_layout.addWidget(name_lbl)

        email_lbl = QLabel(self._email)
        email_lbl.setFont(QFont("Segoe UI", 13))
        email_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        info_layout.addWidget(email_lbl)

        info_layout.addSpacing(8)

        # Status badges row
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        from intent_platform.ui.widgets.components import StatusBadge
        badges_row.addWidget(StatusBadge("Authenticated", Theme.ACCENT_GREEN))
        badges_row.addWidget(StatusBadge("Face Verified", Theme.ACCENT_CYAN))
        badges_row.addStretch()
        info_layout.addLayout(badges_row)

        info_layout.addStretch()
        card_layout.addLayout(info_layout)
        card_layout.addStretch()

        layout.addWidget(card)

        # Account details
        details_card = QWidget()
        details_card.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(24, 20, 24, 20)
        details_layout.setSpacing(0)

        title = QLabel("Account Details")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        details_layout.addWidget(title)
        details_layout.addSpacing(12)

        for label, value in [
            ("Username", self._username),
            ("Email", self._email),
            ("Last Login", "Just now"),
            ("Auth Method", "Password + Face Recognition"),
            ("Account Status", "Active"),
            ("Member Since", "September 2026"),
        ]:
            row = QWidget()
            row.setFixedHeight(44)
            row.setStyleSheet("border: none; background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 8, 0, 8)

            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 13))
            lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
            row_layout.addWidget(lbl)
            row_layout.addStretch()

            val_lbl = QLabel(value)
            val_lbl.setFont(QFont("Segoe UI", 13, QFont.DemiBold))
            val_lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
            row_layout.addWidget(val_lbl)

            details_layout.addWidget(row)

        layout.addWidget(details_card)
        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)


class _AvatarWidget(QWidget):
    """Circular avatar with gradient background."""

    def __init__(self, letter="U", parent=None):
        super().__init__(parent)
        self._letter = letter
        self.setFixedSize(100, 100)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        grad = QLinearGradient(0, 0, 100, 100)
        grad.setColorAt(0, QColor(Theme.ACCENT_CYAN))
        grad.setColorAt(1, QColor(Theme.ACCENT_PURPLE))

        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, 100, 100)

        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI", 36, QFont.Bold))
        p.drawText(self.rect(), Qt.AlignCenter, self._letter)
        p.end()


# ============================================================
#  ANALYTICS PAGE (Coming Soon)
# ============================================================

class AnalyticsPage(QWidget):
    """Analytics placeholder page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        icon = QLabel("📈")
        icon.setFont(QFont("Segoe UI Emoji", 48))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background: transparent;")
        layout.addWidget(icon)

        title = QLabel("Analytics")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(title)

        sub = QLabel("Coming Soon")
        sub.setFont(QFont("Segoe UI", 14))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color: {Theme.TEXT_MUTED}; background: transparent;")
        layout.addWidget(sub)

        desc = QLabel("Usage statistics, performance insights, and comprehensive\nreporting will be available in a future update.")
        desc.setFont(QFont("Segoe UI", 12))
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        layout.addWidget(desc)
