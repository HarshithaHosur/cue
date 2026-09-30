# ============================================================
#  PHASE 4: NOVELTY WIDGETS — AI Interview Agent
# ============================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton, QProgressBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import GlowButton


class EvidenceDialog(QDialog):
    """Dialog displaying evidence timestamp ref, transcript snippet, and notes."""

    def __init__(self, chip_label="▶ 10:14", snippet="Sample transcript text", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Evidence Snippet — {chip_label}")
        self.setFixedSize(450, 260)
        self.setStyleSheet(f"background-color: {Theme.BG_DARKER}; color: {Theme.TEXT_PRIMARY};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel(f"🔍 Evidence Reference ({chip_label})")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        layout.addWidget(title)

        snippet_box = QLabel(f'"{snippet}"')
        snippet_box.setWordWrap(True)
        snippet_box.setFont(QFont("Segoe UI", 11, QFont.StyleItalic))
        snippet_box.setStyleSheet(f"""
            background-color: {Theme.BG_CARD};
            border: 1px solid {Theme.BORDER_SUBTLE};
            border-radius: 8px;
            padding: 14px;
            color: {Theme.TEXT_PRIMARY};
        """)
        layout.addWidget(snippet_box)

        close_btn = GlowButton("Close", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_CYAN))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)


class CompetencyCoverageWidget(QWidget):
    """UI widget displaying live coverage map of interview rubric competencies."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.coverage_pct = 60.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        title_lbl = QLabel("🎯 Rubric Competency Coverage Map")
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        title_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")

        self.pct_lbl = QLabel("60% Covered")
        self.pct_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.pct_lbl.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")

        header_row.addWidget(title_lbl)
        header_row.addWidget(self.pct_lbl, alignment=Qt.AlignRight)
        layout.addLayout(header_row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(60)
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Theme.BG_DARKEST};
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT_CYAN};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.bar)

    def set_coverage(self, pct: float):
        self.coverage_pct = pct
        self.bar.setValue(int(pct))
        self.pct_lbl.setText(f"{int(pct)}% Covered")


class BaselineBadgeWidget(QWidget):
    """Glowing baseline calibration indicator widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.is_calibrated = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lbl = QLabel("● Calibrating Personal Baseline...")
        self.lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl.setStyleSheet(f"color: {Theme.ACCENT_ORANGE};")
        layout.addWidget(self.lbl)

    def mark_calibrated(self):
        self.is_calibrated = True
        self.lbl.setText("● Personal Baseline Calibrated")
        self.lbl.setStyleSheet(f"color: {Theme.ACCENT_GREEN};")
