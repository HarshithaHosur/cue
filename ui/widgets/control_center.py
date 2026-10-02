# ============================================================
#  CONTROL CENTER WIDGET — Real-Time Capabilities Control Panel
#  Provides live toggles and real operational status monitoring
#  for Voice, Gesture, Mouse, Vision, and AI Agent subsystems.
# ============================================================

from typing import Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush, QPen

from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import SectionHeader, StatusBadge, ToggleSwitch
from intent_platform.core.features.feature_manager import Feature, FeatureStatus, get_feature_manager


class FeatureControlRow(QWidget):
    """A single capability row in the Control Center."""

    def __init__(self, feature_key: str, icon: str, title: str, description: str, parent=None):
        super().__init__(parent)
        self.feature_key = feature_key
        self._feature_manager = get_feature_manager()

        self.setFixedHeight(56)
        self.setStyleSheet(f"""
            QWidget {{
                background: {Theme.BG_DARKER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(16)

        # Icon
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 18))
        icon_lbl.setFixedWidth(32)
        icon_lbl.setStyleSheet("background: transparent;")
        layout.addWidget(icon_lbl)

        # Title & Description
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        self.title_lbl = QLabel(title)
        self.title_lbl.setFont(QFont("Segoe UI", 12, QFont.DemiBold))
        self.title_lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")

        desc_lbl = QLabel(description)
        desc_lbl.setFont(QFont("Segoe UI", 10))
        desc_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")

        info_layout.addWidget(self.title_lbl)
        info_layout.addWidget(desc_lbl)
        layout.addLayout(info_layout, stretch=1)

        # Status Badge
        initial_status = self._feature_manager.get_status(feature_key)
        self.status_badge = StatusBadge(text=initial_status, color=self._get_status_color(initial_status))
        layout.addWidget(self.status_badge)

        # Toggle Switch
        is_init_enabled = self._feature_manager.is_enabled(feature_key)
        self.toggle_switch = ToggleSwitch(checked=is_init_enabled)
        self.toggle_switch.toggled.connect(self._on_toggled)
        layout.addWidget(self.toggle_switch)

    def _get_status_color(self, status: str) -> str:
        s_lower = status.lower()
        if "run" in s_lower or "active" in s_lower:
            return Theme.ACCENT_GREEN
        elif "pause" in s_lower or "wait" in s_lower:
            return Theme.ACCENT_ORANGE
        elif "disab" in s_lower or "off" in s_lower:
            return Theme.TEXT_MUTED
        elif "unavail" in s_lower or "err" in s_lower:
            return Theme.ACCENT_RED
        return Theme.ACCENT_CYAN

    def _on_toggled(self, checked: bool):
        self._feature_manager.set_enabled(self.feature_key, checked)

    def update_status(self, status: str):
        color = self._get_status_color(status)
        self.status_badge._text = status
        self.status_badge._color = color
        self.status_badge.setFixedWidth(max(70, len(status) * 9 + 28))
        self.status_badge.update()

    def update_enabled(self, enabled: bool):
        self.toggle_switch.setChecked(enabled, emit_signal=False)


class ControlCenterWidget(QWidget):
    """
    Control Center Panel embedding live toggle switches and operational status
    for Voice, Gesture, Mouse, Vision, and AI Agent subsystems.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._feature_manager = get_feature_manager()
        self._rows: Dict[str, FeatureControlRow] = {}
        self._build_ui()

        # Connect signals for real-time status and state syncing
        self._feature_manager.signals.feature_status_changed.connect(self._on_status_changed)
        self._feature_manager.signals.feature_toggled.connect(self._on_toggled)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(14)

        # Header
        header = SectionHeader(
            title="Control Center",
            subtitle="Manage real-time capabilities and hardware sensor processing"
        )
        main_layout.addWidget(header)

        # Container Card
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(10)

        # 5 Capability Rows
        capabilities = [
            (Feature.VOICE.value, "🎤", "Voice Control", "Microphone listening & speech commands"),
            (Feature.GESTURE.value, "✋", "Gesture Control", "Camera hand gestures & posture tracking"),
            (Feature.MOUSE.value, "🖱", "Mouse Control", "Virtual air-cursor & smooth gesture scroll"),
            (Feature.VISION.value, "👁", "Vision", "Camera feed & continuous authentication"),
            (Feature.AI_AGENT.value, "🤖", "AI Agent", "Multimodal intelligence & animated companion"),
        ]

        for feat_key, icon, title, desc in capabilities:
            row = FeatureControlRow(feat_key, icon, title, desc)
            self._rows[feat_key] = row
            card_layout.addWidget(row)

        main_layout.addWidget(card)

    @Slot(str, str)
    def _on_status_changed(self, feature: str, status: str):
        if feature in self._rows:
            self._rows[feature].update_status(status)

    @Slot(str, bool)
    def _on_toggled(self, feature: str, enabled: bool):
        if feature in self._rows:
            self._rows[feature].update_enabled(enabled)
            status = self._feature_manager.get_status(feature)
            self._rows[feature].update_status(status)
