# ============================================================
#  AI TECHNICAL SUPPORT DASHBOARD
# ============================================================

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
    QScrollArea, QFrame, QSizePolicy, QLineEdit, QGridLayout, QPushButton
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QBrush, QPen,
    QLinearGradient
)
from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import SectionHeader, SidebarNavItem, GlowButton
from intent_platform.ui.pages.support.agent_dashboard import AgentDashboard


class SupportDashboard(QWidget):
    """AI Technical Support workspace with device diagnostics."""

    navigate_back = Signal()
    navigate_to_agent = Signal()  # Emitted to open AI Customer Support Agent

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left Nav ──
        left = QWidget()
        left.setFixedWidth(220)
        left.setStyleSheet(f"background-color: {Theme.SIDEBAR_BG}; border-right: 1px solid {Theme.BORDER_SUBTLE};")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 20, 0, 20)
        left_layout.setSpacing(4)

        back_btn = _SupportBackButton("← Back to Home")
        back_btn.clicked.connect(self.navigate_back.emit)
        left_layout.addWidget(back_btn)
        left_layout.addSpacing(16)

        title = QLabel("  🛠 Tech Support")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; padding: 8px 12px; background: transparent;")
        left_layout.addWidget(title)
        left_layout.addSpacing(8)

        self._nav_items = []
        for pid, icon, label in [
            ("sp_dash", "📊", "Dashboard"),
            ("sp_agent", "🤖", "AI Support Agent"),
            ("sp_health", "💊", "Device Health"),
            ("sp_diag", "🔍", "Diagnostics"),
            ("sp_software", "📦", "Software"),
            ("sp_updates", "🔄", "Updates"),
            ("sp_reports", "📄", "Reports"),
            ("sp_settings", "⚙", "Settings"),
        ]:
            item = SidebarNavItem(pid, icon, label)
            item.clicked.connect(self._on_nav)
            left_layout.addWidget(item)
            self._nav_items.append(item)

        left_layout.addStretch()
        layout.addWidget(left)

        # ── Content Stack ──
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        self._stack.addWidget(self._build_support_home())  # 0
        self.agent_dashboard = AgentDashboard()
        self.agent_dashboard.navigate_back.connect(lambda: self._on_nav("sp_dash"))
        self._stack.addWidget(self.agent_dashboard)  # 1 — AI Agent Dashboard
        self._stack.addWidget(self._build_device_health())  # 2
        self._stack.addWidget(self._build_placeholder("Diagnostics", "Run hardware and software diagnostics."))
        self._stack.addWidget(self._build_placeholder("Installed Software", "Manage installed applications."))
        self._stack.addWidget(self._build_placeholder("System Updates", "Check for system updates."))
        self._stack.addWidget(self._build_placeholder("Reports", "View support reports."))
        self._stack.addWidget(self._build_placeholder("Settings", "Configure support settings."))
        layout.addWidget(self._stack)

        self._on_nav("sp_dash")

    def _on_nav(self, pid):
        idx_map = {"sp_dash": 0, "sp_agent": 1, "sp_health": 2, "sp_diag": 3,
                   "sp_software": 4, "sp_updates": 5, "sp_reports": 6, "sp_settings": 7}
        self._stack.setCurrentIndex(idx_map.get(pid, 0))
        for item in self._nav_items:
            item.set_active(item._page_id == pid)

    def _build_support_home(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(32, 28, 32, 32)
        lay.setSpacing(20)

        lay.addWidget(SectionHeader("Technical Support", "AI-powered diagnostics and troubleshooting"))

        # ── AI Customer Support Agent Launch Hero Button ──
        agent_hero = QPushButton("🤖  Launch AI Customer Support Agent")
        agent_hero.setCursor(Qt.PointingHandCursor)
        agent_hero.setFixedHeight(54)
        agent_hero.setFont(QFont("Segoe UI", 15, QFont.Bold))
        agent_hero.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.GRADIENT_SUPPORT};
                color: white;
                border-radius: 14px;
                border: none;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #34d399,stop:1 #38bdf8);
            }}
        """)
        agent_hero.clicked.connect(lambda: self._on_nav("sp_agent"))
        lay.addWidget(agent_hero)
        lay.addSpacing(4)

        # Search bar
        search = QLineEdit()
        search.setPlaceholderText("🔍  What can I help you with?")
        search.setFixedHeight(52)
        search.setFont(QFont("Segoe UI", 14))
        search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 14px;
                padding: 0 20px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 14px;
            }}
            QLineEdit:focus {{ border-color: {Theme.ACCENT_GREEN}; }}
        """)
        lay.addWidget(search)

        # Example queries
        examples_row = QHBoxLayout()
        examples_row.setSpacing(10)
        for text in ["My laptop is slow", "Install Python", "Wi-Fi not working", "Help me use Excel"]:
            chip = _SuggestionChip(text)
            examples_row.addWidget(chip)
        examples_row.addStretch()
        lay.addLayout(examples_row)

        lay.addSpacing(8)

        # Quick device status
        lay.addWidget(SectionHeader("System Overview"))

        grid = QGridLayout()
        grid.setSpacing(14)
        devices = [
            ("CPU", "Intel Core i7", "🖥", "72%", Theme.ACCENT_BLUE),
            ("RAM", "16 GB DDR4", "💾", "58%", Theme.ACCENT_GREEN),
            ("Storage", "512 GB SSD", "💿", "45%", Theme.ACCENT_ORANGE),
            ("Battery", "Plugged In", "🔋", "100%", Theme.ACCENT_GREEN),
            ("Network", "Connected", "🌐", "Active", Theme.ACCENT_CYAN),
            ("Antivirus", "Protected", "🛡", "Active", Theme.ACCENT_GREEN),
        ]
        for i, (name, desc, icon, val, color) in enumerate(devices):
            card = _DeviceCard(name, desc, icon, val, color)
            grid.addWidget(card, i // 3, i % 3)
        lay.addLayout(grid)

        lay.addStretch()
        scroll.setWidget(content)

        p_layout = QVBoxLayout(page)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.addWidget(scroll)
        return page

    def _build_device_health(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(32, 28, 32, 32)
        lay.setSpacing(20)

        lay.addWidget(SectionHeader("Device Health", "Real-time system monitoring"))

        # Large device cards
        grid = QGridLayout()
        grid.setSpacing(16)
        metrics = [
            ("CPU Usage", "72%", "🖥", Theme.ACCENT_BLUE, "Intel Core i7-12700H @ 2.30GHz"),
            ("Memory", "9.2 / 16 GB", "💾", Theme.ACCENT_GREEN, "DDR4-3200 Dual Channel"),
            ("Disk C:", "234 / 512 GB", "💿", Theme.ACCENT_ORANGE, "NVMe SSD — 45% used"),
            ("Battery", "100%", "🔋", Theme.ACCENT_GREEN, "Plugged In — Full Charge"),
            ("GPU", "NVIDIA RTX 3060", "🎮", Theme.ACCENT_PURPLE, "6 GB VRAM — Temp: 42°C"),
            ("Network", "192.168.1.42", "🌐", Theme.ACCENT_CYAN, "Wi-Fi 6 — 867 Mbps"),
        ]
        for i, (name, val, icon, color, detail) in enumerate(metrics):
            card = _DetailedDeviceCard(name, val, icon, color, detail)
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid)

        lay.addStretch()
        scroll.setWidget(content)

        p_lay = QVBoxLayout(page)
        p_lay.setContentsMargins(0, 0, 0, 0)
        p_lay.addWidget(scroll)
        return page

    def _build_placeholder(self, title, msg):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 32)
        lay.addWidget(SectionHeader(title))

        lbl = QLabel(msg)
        lbl.setFont(QFont("Segoe UI", 13))
        lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)
        lay.addStretch()
        return page


# ── Support-specific Widgets ──

class _SupportBackButton(QWidget):
    clicked = Signal()

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)

    def enterEvent(self, e):
        self._hover = True; self.update()
    def leaveEvent(self, e):
        self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(Theme.ACCENT_GREEN) if self._hover else QColor(Theme.TEXT_SECONDARY)
        p.setPen(c)
        p.setFont(QFont("Segoe UI", 12))
        p.drawText(self.rect().adjusted(16, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, self._text)
        p.end()


class _SuggestionChip(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self.setMinimumWidth(len(text) * 8 + 28)

    def enterEvent(self, e):
        self._hover = True; self.update()
    def leaveEvent(self, e):
        self._hover = False; self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 17, 17)
        if self._hover:
            p.fillPath(path, QBrush(QColor(Theme.ACCENT_GREEN + "20")))
            p.setPen(QPen(QColor(Theme.ACCENT_GREEN + "60"), 1))
            p.drawRoundedRect(1, 1, w - 2, h - 2, 17, 17)
            p.setPen(QColor(Theme.ACCENT_GREEN))
        else:
            p.fillPath(path, QBrush(QColor(Theme.BG_CARD)))
            p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
            p.drawRoundedRect(1, 1, w - 2, h - 2, 17, 17)
            p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(self.rect(), Qt.AlignCenter, self._text)
        p.end()


class _DeviceCard(QWidget):
    def __init__(self, name, desc, icon, value, color, parent=None):
        super().__init__(parent)
        self._name = name
        self._desc = desc
        self._icon = icon
        self._value = value
        self._color = color
        self.setFixedHeight(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 12, 12)
        p.fillPath(path, QBrush(QColor(Theme.BG_CARD)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)

        # Icon
        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI Emoji", 22))
        p.drawText(16, 16, 40, 40, Qt.AlignCenter, self._icon)

        # Name + description
        p.setPen(QColor(Theme.TEXT_PRIMARY))
        p.setFont(QFont("Segoe UI", 14, QFont.DemiBold))
        p.drawText(64, 18, w - 80, 24, Qt.AlignLeft | Qt.AlignVCenter, self._name)

        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(64, 42, w - 80, 20, Qt.AlignLeft | Qt.AlignVCenter, self._desc)

        # Value badge
        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI", 13, QFont.Bold))
        p.drawText(64, 66, w - 80, 22, Qt.AlignLeft | Qt.AlignVCenter, self._value)
        p.end()


class _DetailedDeviceCard(QWidget):
    def __init__(self, name, value, icon, color, detail, parent=None):
        super().__init__(parent)
        self._name = name
        self._value = value
        self._icon = icon
        self._color = color
        self._detail = detail
        self.setFixedHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 12, 12)
        p.fillPath(path, QBrush(QColor(Theme.BG_CARD)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)

        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI Emoji", 24))
        p.drawText(20, 20, 44, 44, Qt.AlignCenter, self._icon)

        p.setPen(QColor(Theme.TEXT_PRIMARY))
        p.setFont(QFont("Segoe UI", 15, QFont.Bold))
        p.drawText(76, 20, w - 100, 26, Qt.AlignLeft | Qt.AlignVCenter, self._name)

        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI", 20, QFont.Bold))
        p.drawText(76, 48, w - 100, 30, Qt.AlignLeft | Qt.AlignVCenter, self._value)

        p.setPen(QColor(Theme.TEXT_MUTED))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(76, 82, w - 100, 22, Qt.AlignLeft | Qt.AlignVCenter, self._detail)
        p.end()
