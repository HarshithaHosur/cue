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


class InterviewDashboard(QWidget):
    """Complete AI Interview Agent workspace with sub-navigation."""

    navigate_back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
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
        self._stack.addWidget(self._build_interview_home())      # 0: Dashboard
        self._stack.addWidget(self._build_create_interview())    # 1: Create
        self._stack.addWidget(self._build_live_interview())      # 2: Live
        self._stack.addWidget(self._build_placeholder("Previous Interviews", "📋", "No previous interviews found."))
        self._stack.addWidget(self._build_placeholder("Reports", "📄", "No reports generated yet."))
        self._stack.addWidget(self._build_placeholder("Interview Settings", "⚙", "Configure interview parameters."))

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
        fields = [
            ("Interview Title", QLineEdit, {"placeholderText": "e.g. Senior Python Developer Interview"}),
            ("Job Role", QLineEdit, {"placeholderText": "e.g. Backend Engineer"}),
            ("Candidate Name", QLineEdit, {"placeholderText": "e.g. John Doe"}),
            ("Meeting Link", QLineEdit, {"placeholderText": "e.g. https://meet.google.com/..."}),
        ]
        for label_text, widget_cls, props in fields:
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Segoe UI", 12))
            lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
            form_layout.addWidget(lbl)
            widget = widget_cls()
            if "placeholderText" in props:
                widget.setPlaceholderText(props["placeholderText"])
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
        dur_spin = QSpinBox()
        dur_spin.setRange(15, 180)
        dur_spin.setValue(45)
        dur_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 10px 14px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)
        dur_group.addWidget(dur_spin)
        row.addLayout(dur_group)

        diff_group = QVBoxLayout()
        diff_lbl = QLabel("Difficulty Level")
        diff_lbl.setFont(QFont("Segoe UI", 12))
        diff_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        diff_group.addWidget(diff_lbl)
        diff_combo = QComboBox()
        diff_combo.addItems(["Easy", "Medium", "Hard", "Expert"])
        diff_combo.setCurrentIndex(1)
        diff_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 10px 14px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)
        diff_group.addWidget(diff_combo)
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
        btn_group = QButtonGroup(self)
        for tname in ["Technical", "HR", "Coding", "Aptitude"]:
            rb = QRadioButton(tname)
            rb.setStyleSheet(radio_style)
            btn_group.addButton(rb)
            type_row.addWidget(rb)
            if tname == "Technical":
                rb.setChecked(True)

        type_row.addStretch()
        form_layout.addLayout(type_row)

        # Start button
        start_btn = GlowButton("Start Interview", "🚀",
                                gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_PURPLE))
        start_btn.setFixedHeight(48)
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
        """Professional meeting-like interface for live interviews."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left: Video area ──
        video_area = QWidget()
        video_area.setStyleSheet("background: transparent;")
        video_layout = QVBoxLayout(video_area)
        video_layout.setContentsMargins(20, 20, 10, 20)
        video_layout.setSpacing(12)

        # Candidate camera
        cam_placeholder = _VideoPlaceholder("Candidate Camera", "📹", "No candidate connected")
        video_layout.addWidget(cam_placeholder, 2)

        # Screen share
        screen_placeholder = _VideoPlaceholder("Screen Share", "🖥", "No screen shared")
        video_layout.addWidget(screen_placeholder, 3)

        layout.addWidget(video_area, 3)

        # ── Right: AI Panel ──
        right_panel = QWidget()
        right_panel.setFixedWidth(320)
        right_panel.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border-left: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 20, 16, 16)
        right_layout.setSpacing(12)

        ai_title = QLabel("🤖 AI Assistant")
        ai_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        ai_title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        right_layout.addWidget(ai_title)

        waiting_lbl = QLabel("Waiting for Interview...")
        waiting_lbl.setFont(QFont("Segoe UI", 12))
        waiting_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; border: none; background: transparent;")
        waiting_lbl.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(waiting_lbl)

        # Analysis sections (placeholder)
        for section_name in ["Communication Analysis", "Body Language", "Eye Contact",
                             "Confidence", "Coding Behaviour", "Integrity Monitor",
                             "Interview Notes"]:
            section = _AnalysisSection(section_name)
            right_layout.addWidget(section)

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
        p.drawText(0, 0, w - 12, h, Qt.AlignRight | Qt.AlignVCenter, "No data")
        p.end()
