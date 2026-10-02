# ============================================================
#  AI CUSTOMER SUPPORT AGENT DASHBOARD — Multimodal Executive UI
#  Premium chat panel, collapsible reasoning panel, audit log,
#  context awareness bar, and permission-based confirmation controls.
# ============================================================

from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QLineEdit, QPushButton, QSplitter,
    QTextEdit
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QBrush, QPen,
    QLinearGradient, QTextCursor
)
from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import SectionHeader


class AgentDashboard(QWidget):
    """AI Customer Support Agent dashboard with chat, reasoning, and audit panels."""

    navigate_back = Signal()
    user_command_submitted = Signal(str)           # Emitted when user types a command
    user_confirmed_action = Signal()               # Emitted when user clicks Confirm
    user_cancelled_action = Signal()               # Emitted when user clicks Cancel

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Context Awareness Bar ──
        self.context_bar = self._build_context_bar()
        layout.addWidget(self.context_bar)

        # ── Main 3-Column Layout ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {Theme.BORDER_SUBTLE};
                width: 2px;
            }}
        """)

        # LEFT: Chat Panel
        chat_panel = self._build_chat_panel()
        splitter.addWidget(chat_panel)

        # RIGHT: Stacked Reasoning + Audit
        right_col = QWidget()
        right_col.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Reasoning Panel (top half)
        reasoning_panel = self._build_reasoning_panel()
        right_layout.addWidget(reasoning_panel, 1)

        # Audit Log Panel (bottom half)
        audit_panel = self._build_audit_panel()
        right_layout.addWidget(audit_panel, 1)

        splitter.addWidget(right_col)
        splitter.setSizes([600, 420])

        layout.addWidget(splitter, 1)

        # ── Confirmation Bar (hidden by default) ──
        self.confirm_bar = self._build_confirmation_bar()
        self.confirm_bar.setVisible(False)
        layout.addWidget(self.confirm_bar)

    # ────────────────────────────────────────────
    #  CONTEXT AWARENESS BAR
    # ────────────────────────────────────────────
    def _build_context_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(48)
        bar.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border-bottom: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(16)

        # Back button
        back_btn = QPushButton("← Back")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 600;
                border: none;
                padding: 4px 8px;
            }}
            QPushButton:hover {{ color: {Theme.ACCENT_GREEN}; }}
        """)
        back_btn.clicked.connect(self.navigate_back.emit)
        lay.addWidget(back_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {Theme.BORDER_SUBTLE};")
        lay.addWidget(sep)

        # AI Agent badge
        agent_badge = QLabel("🤖 AI Customer Support Agent")
        agent_badge.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        agent_badge.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; background: transparent;")
        lay.addWidget(agent_badge)

        lay.addStretch()

        # Live context indicators
        self.ctx_website = QLabel("🌐 —")
        self.ctx_website.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; font-size: 12px; font-weight: 600; background: {Theme.BG_ELEVATED}; padding: 4px 10px; border-radius: 10px;")

        self.ctx_page_type = QLabel("📄 —")
        self.ctx_page_type.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600; background: {Theme.BG_ELEVATED}; padding: 4px 10px; border-radius: 10px;")

        self.ctx_browser = QLabel("🖥️ —")
        self.ctx_browser.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; background: {Theme.BG_ELEVATED}; padding: 4px 10px; border-radius: 10px;")

        lay.addWidget(self.ctx_website)
        lay.addWidget(self.ctx_page_type)
        lay.addWidget(self.ctx_browser)

        return bar

    # ────────────────────────────────────────────
    #  CHAT PANEL (Left)
    # ────────────────────────────────────────────
    def _build_chat_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(42)
        header.setStyleSheet(f"background: {Theme.BG_CARD}; border-bottom: 1px solid {Theme.BORDER_SUBTLE};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)
        chat_title = QLabel("💬 Conversation")
        chat_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        chat_title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        h_lay.addWidget(chat_title)
        h_lay.addStretch()

        self.status_label = QLabel("● Ready")
        self.status_label.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; font-size: 11px; font-weight: 600; background: transparent;")
        h_lay.addWidget(self.status_label)
        layout.addWidget(header)

        # Chat Messages Scroll Area
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_scroll.setStyleSheet(f"background: {Theme.BG_DARKER}; border: none;")

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll, 1)

        # Input Area
        input_frame = QFrame()
        input_frame.setFixedHeight(56)
        input_frame.setStyleSheet(f"background: {Theme.BG_CARD}; border-top: 1px solid {Theme.BORDER_SUBTLE};")
        inp_lay = QHBoxLayout(input_frame)
        inp_lay.setContentsMargins(12, 8, 12, 8)
        inp_lay.setSpacing(8)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type a request or say 'System help me'...")
        self.chat_input.setFont(QFont("Segoe UI", 13))
        self.chat_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 12px;
                padding: 0 14px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {Theme.ACCENT_CYAN}; }}
        """)
        self.chat_input.returnPressed.connect(self._on_send)
        inp_lay.addWidget(self.chat_input, 1)

        send_btn = QPushButton("Send ➤")
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setFixedSize(80, 36)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT_GREEN};
                color: #0f1117;
                font-weight: 700;
                font-size: 12px;
                border-radius: 10px;
                border: none;
            }}
            QPushButton:hover {{ background: #34d399; }}
        """)
        send_btn.clicked.connect(self._on_send)
        inp_lay.addWidget(send_btn)

        layout.addWidget(input_frame)
        return panel

    # ────────────────────────────────────────────
    #  REASONING PANEL (Right Top — Collapsible)
    # ────────────────────────────────────────────
    def _build_reasoning_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(42)
        header.setStyleSheet(f"background: {Theme.BG_CARD}; border-bottom: 1px solid {Theme.BORDER_SUBTLE};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)
        r_title = QLabel("🧠 AI Reasoning")
        r_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        r_title.setStyleSheet(f"color: {Theme.ACCENT_PURPLE}; background: transparent;")
        h_lay.addWidget(r_title)
        h_lay.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Theme.TEXT_MUTED};
                font-size: 11px; border: none; padding: 2px 8px;
            }}
            QPushButton:hover {{ color: {Theme.TEXT_PRIMARY}; }}
        """)
        clear_btn.clicked.connect(self._clear_reasoning)
        h_lay.addWidget(clear_btn)
        layout.addWidget(header)

        self.reasoning_area = QTextEdit()
        self.reasoning_area.setReadOnly(True)
        self.reasoning_area.setFont(QFont("Segoe UI", 12))
        self.reasoning_area.setStyleSheet(f"""
            QTextEdit {{
                background: {Theme.BG_DARKEST};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px;
                line-height: 1.6;
            }}
        """)
        self.reasoning_area.setPlaceholderText("AI reasoning steps will appear here...")
        layout.addWidget(self.reasoning_area, 1)
        return panel

    # ────────────────────────────────────────────
    #  AUDIT LOG PANEL (Right Bottom)
    # ────────────────────────────────────────────
    def _build_audit_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(42)
        header.setStyleSheet(f"background: {Theme.BG_CARD}; border-bottom: 1px solid {Theme.BORDER_SUBTLE}; border-top: 1px solid {Theme.BORDER_SUBTLE};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)
        a_title = QLabel("📋 Audit Trail")
        a_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        a_title.setStyleSheet(f"color: {Theme.ACCENT_ORANGE}; background: transparent;")
        h_lay.addWidget(a_title)
        h_lay.addStretch()
        layout.addWidget(header)

        self.audit_area = QTextEdit()
        self.audit_area.setReadOnly(True)
        self.audit_area.setFont(QFont("Consolas", 11))
        self.audit_area.setStyleSheet(f"""
            QTextEdit {{
                background: {Theme.BG_DARKEST};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 10px;
            }}
        """)
        self.audit_area.setPlaceholderText("Action audit logs will appear here...")
        layout.addWidget(self.audit_area, 1)
        return panel

    # ────────────────────────────────────────────
    #  CONFIRMATION BAR (Bottom, hidden by default)
    # ────────────────────────────────────────────
    def _build_confirmation_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1e1b4b,stop:1 #0f172a);
                border-top: 2px solid {Theme.ACCENT_ORANGE};
            }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)

        self.confirm_label = QLabel("⚠️ Confirmation required before proceeding...")
        self.confirm_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self.confirm_label.setStyleSheet(f"color: {Theme.ACCENT_ORANGE}; background: transparent;")
        lay.addWidget(self.confirm_label, 1)

        cancel_btn = QPushButton("✖ Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedSize(100, 34)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.SURFACE1}; color: {Theme.ACCENT_RED};
                font-weight: 700; font-size: 12px; border-radius: 8px; border: 1px solid {Theme.ACCENT_RED};
            }}
            QPushButton:hover {{ background: {Theme.ACCENT_RED}; color: white; }}
        """)
        cancel_btn.clicked.connect(self._on_cancel_action)
        lay.addWidget(cancel_btn)

        confirm_btn = QPushButton("✔ Confirm")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setFixedSize(120, 34)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT_GREEN}; color: #0f1117;
                font-weight: 700; font-size: 12px; border-radius: 8px; border: none;
            }}
            QPushButton:hover {{ background: #34d399; }}
        """)
        confirm_btn.clicked.connect(self._on_confirm_action)
        lay.addWidget(confirm_btn)

        return bar

    # ────────────────────────────────────────────
    #  PUBLIC SLOTS
    # ────────────────────────────────────────────
    @Slot(str)
    def add_reasoning_step(self, step: str):
        """Appends a reasoning step to the AI Reasoning panel."""
        self.reasoning_area.append(step)
        cursor = self.reasoning_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.reasoning_area.setTextCursor(cursor)

    @Slot(str, str)
    def add_response(self, text_response: str, voice_response: str):
        """Adds AI assistant response as a chat bubble."""
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._add_chat_bubble(f"{stamp}  Assistant\n{text_response}", is_user=False)

    @Slot(dict)
    def show_confirmation(self, action_payload: dict):
        """Shows the confirmation bar for medium/high risk actions."""
        label = action_payload.get("target_label", "action")
        risk = action_payload.get("risk_level", "MEDIUM_RISK")
        prompt = action_payload.get("confirmation_prompt", f"Confirm action: {label}?")
        icon = "🔴" if risk == "HIGH_RISK" else "⚠️"
        self.confirm_label.setText(f"{icon} {prompt}")
        self.confirm_bar.setVisible(True)

    @Slot()
    def hide_confirmation(self):
        self.confirm_bar.setVisible(False)

    @Slot(str, str)
    def on_action_executed(self, action_name: str, result_msg: str):
        """Called when a confirmed or safe action completes."""
        self.hide_confirmation()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._add_chat_bubble(f"{stamp}  Action: {action_name}\nStatus: executed\n{result_msg}", is_user=False)

    @Slot(dict)
    def update_context(self, context: dict):
        """Updates the context awareness bar with live detection data."""
        icon = context.get("website_icon", "🌐")
        website = context.get("website", "—")
        page_type = context.get("page_type", "—")
        browser = context.get("browser", "—")

        self.ctx_website.setText(f"{icon} {website}")
        self.ctx_page_type.setText(f"📄 {page_type}")
        self.ctx_browser.setText(f"🖥️ {browser}")

    @Slot(str, str)
    def update_agent_state(self, state: str, message: str):
        """Updates the status indicator based on agent state."""
        state_map = {
            "listening": ("● Listening...", Theme.ACCENT_CYAN),
            "thinking": ("● Thinking...", Theme.ACCENT_PURPLE),
            "speaking": ("● Speaking", Theme.ACCENT_GREEN),
            "executing": ("● Executing...", Theme.ACCENT_ORANGE),
            "waiting": ("● Awaiting Confirmation", Theme.ACCENT_ORANGE),
            "completed": ("● Completed", Theme.ACCENT_GREEN),
            "idle": ("● Ready", Theme.ACCENT_GREEN),
            "error": ("● Error", Theme.ACCENT_RED),
        }
        text, color = state_map.get(state.lower(), ("● Ready", Theme.ACCENT_GREEN))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600; background: transparent;")

    @Slot(dict)
    def add_audit_entry(self, entry: dict):
        """Appends an audit log entry to the audit panel."""
        time_str = entry.get("short_time", "??:??")
        category = entry.get("category", "INFO")
        message = entry.get("message", "")
        risk = entry.get("risk_level", "INFO")

        color_map = {
            "CONTEXT": Theme.ACCENT_CYAN,
            "HIGHLIGHT": Theme.ACCENT_PURPLE,
            "EXECUTE": Theme.ACCENT_GREEN,
            "SAFETY": Theme.ACCENT_ORANGE,
            "SUPPORT_MODE": Theme.ACCENT_BLUE,
            "ACTION": Theme.ACCENT_GREEN,
        }
        c = color_map.get(category, Theme.TEXT_MUTED)
        html = f'<span style="color: {Theme.TEXT_MUTED}">{time_str}</span>  <span style="color: {c}; font-weight: bold">[{category}]</span>  {message}'
        self.audit_area.append(html)
        cursor = self.audit_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.audit_area.setTextCursor(cursor)

    def add_user_message(self, text: str):
        """Adds user message to the chat panel."""
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._add_chat_bubble(f"{stamp}  You\n{text}", is_user=True)

    def load_history(self, turns):
        """Restores recent persisted conversation turns into the existing chat panel."""
        for turn in turns:
            stamp = datetime.fromtimestamp(turn["timestamp"]).strftime("%Y-%m-%d %H:%M")
            self._add_chat_bubble(f"{stamp}  You\n{turn['user_message']}", is_user=True)
            response = f"{stamp}  Assistant\n{turn['assistant_response']}"
            if turn.get("action_taken"):
                response += f"\nAction: {turn['action_taken']}"
            response += f"\nStatus: {turn.get('status', 'responded')}"
            self._add_chat_bubble(response, is_user=False)

    # ────────────────────────────────────────────
    #  PRIVATE HELPERS
    # ────────────────────────────────────────────
    def _add_chat_bubble(self, text: str, is_user: bool = False):
        """Renders a styled chat bubble in the conversation panel."""
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Segoe UI", 12))
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if is_user:
            bubble.setStyleSheet(f"""
                QLabel {{
                    background: {Theme.ACCENT_BLUE};
                    color: white;
                    border-radius: 14px;
                    padding: 10px 16px;
                    margin-left: 60px;
                }}
            """)
            bubble.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            bubble.setStyleSheet(f"""
                QLabel {{
                    background: {Theme.BG_CARD};
                    color: {Theme.TEXT_PRIMARY};
                    border: 1px solid {Theme.BORDER_SUBTLE};
                    border-radius: 14px;
                    padding: 10px 16px;
                    margin-right: 60px;
                }}
            """)
            bubble.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Insert before the stretch at the end
        count = self.chat_layout.count()
        self.chat_layout.insertWidget(count - 1, bubble)

        # Auto-scroll to bottom
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    def _on_send(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_input.clear()
        self.add_user_message(text)
        self.user_command_submitted.emit(text)

    def _on_confirm_action(self):
        self.hide_confirmation()
        self.user_confirmed_action.emit()

    def _on_cancel_action(self):
        self.hide_confirmation()
        self.user_cancelled_action.emit()

    def _clear_reasoning(self):
        self.reasoning_area.clear()
