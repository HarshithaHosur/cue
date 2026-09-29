# ============================================================
#  GESTURE & VOICE CONTROL CENTER
#  Interactive configuration, mapping editor, and command testing
# ============================================================

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QScrollArea, QFrame, QMessageBox
)

from intent_platform.database.connection import db


class GestureVoiceSettingsView(QWidget):
    """Control center to configure, customize, and inspect gestures & voice commands."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        # Header
        header_box = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Gestures & Voice Command Matrix")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #CAD3F5;")
        subtitle = QLabel("Configure real-time spatial gestures, wake words, and speech actions")
        subtitle.setStyleSheet("color: #8087A2; font-size: 13px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_box.addLayout(title_box)
        header_box.addStretch()

        layout.addLayout(header_box)

        # Tabs: Gestures, Voice Commands, Live Logs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #363A4F;
                border-radius: 12px;
                background: #181926;
                padding: 16px;
            }
            QTabBar::tab {
                background: #24273A;
                color: #A5ADCB;
                font-weight: 600;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #8AADF4;
                color: #181926;
                font-weight: 700;
            }
        """)

        tabs.addTab(self._build_gestures_tab(), "Spatial Gestures")
        tabs.addTab(self._build_voice_tab(), "Voice Commands & Wake Word")
        tabs.addTab(self._build_logs_tab(), "Live Audit Logs")

        layout.addWidget(tabs)

    def _build_gestures_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)

        desc = QLabel("Registered Hand Gestures and Context Trigger Mappings:")
        desc.setStyleSheet("color: #CAD3F5; font-size: 13px; font-weight: 600;")
        layout.addWidget(desc)

        self.gesture_table = QTableWidget()
        self.gesture_table.setColumnCount(4)
        self.gesture_table.setHorizontalHeaderLabels(["Gesture Name", "Type", "Assigned Action", "Description"])
        self.gesture_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.gesture_table.setStyleSheet("""
            QTableWidget {
                background: #1E2030;
                color: #CAD3F5;
                gridline-color: #363A4F;
                border: none;
                border-radius: 8px;
            }
            QHeaderView::section {
                background: #24273A;
                color: #8AADF4;
                font-weight: 700;
                padding: 8px;
                border: none;
            }
        """)

        self._refresh_gestures_table()
        layout.addWidget(self.gesture_table)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Table")
        refresh_btn.setStyleSheet("background: #363A4F; color: #CAD3F5; padding: 8px 16px; border-radius: 6px;")
        refresh_btn.clicked.connect(self._refresh_gestures_table)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return w

    def _refresh_gestures_table(self):
        gestures = db.get_gestures()
        self.gesture_table.setRowCount(len(gestures))
        for row, g in enumerate(gestures):
            self.gesture_table.setItem(row, 0, QTableWidgetItem(g.get("name", "")))
            self.gesture_table.setItem(row, 1, QTableWidgetItem(g.get("type", "")))
            self.gesture_table.setItem(row, 2, QTableWidgetItem(g.get("action", "")))
            self.gesture_table.setItem(row, 3, QTableWidgetItem(g.get("description", "")))

    def _build_voice_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)

        # Wake Word Config
        ww_box = QHBoxLayout()
        ww_lbl = QLabel("Active Wake Word:")
        ww_lbl.setStyleSheet("color: #CAD3F5; font-weight: 600;")
        self.ww_input = QLineEdit()
        self.ww_input.setText(str(db.get_setting("wake_word", "system")))
        self.ww_input.setStyleSheet("background: #1E2030; border: 1px solid #363A4F; border-radius: 6px; padding: 6px 12px; color: #CAD3F5; max-width: 180px;")

        save_ww_btn = QPushButton("Save Wake Word")
        save_ww_btn.setStyleSheet("background: #8AADF4; color: #181926; font-weight: 700; padding: 6px 14px; border-radius: 6px;")
        save_ww_btn.clicked.connect(self._save_wake_word)

        ww_box.addWidget(ww_lbl)
        ww_box.addWidget(self.ww_input)
        ww_box.addWidget(save_ww_btn)
        ww_box.addStretch()
        layout.addLayout(ww_box)

        # Voice commands list
        self.voice_table = QTableWidget()
        self.voice_table.setColumnCount(3)
        self.voice_table.setHorizontalHeaderLabels(["Spoken Phrase", "Action Executed", "Tips"])
        self.voice_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.voice_table.setStyleSheet("""
            QTableWidget {
                background: #1E2030;
                color: #CAD3F5;
                gridline-color: #363A4F;
                border: none;
                border-radius: 8px;
            }
            QHeaderView::section {
                background: #24273A;
                color: #8AADF4;
                font-weight: 700;
                padding: 8px;
                border: none;
            }
        """)
        self._refresh_voice_table()
        layout.addWidget(self.voice_table)

        return w

    def _save_wake_word(self):
        new_ww = self.ww_input.text().strip().lower()
        if new_ww:
            db.set_setting("wake_word", new_ww)
            QMessageBox.information(self, "Updated", f"Wake word changed to '{new_ww}'")

    def _refresh_voice_table(self):
        cmds = db.get_voice_commands()
        self.voice_table.setRowCount(len(cmds))
        for row, c in enumerate(cmds):
            self.voice_table.setItem(row, 0, QTableWidgetItem(c.get("command", "")))
            self.voice_table.setItem(row, 1, QTableWidgetItem(c.get("action", "")))
            tips = c.get("tips", [])
            tips_str = ", ".join(tips) if isinstance(tips, list) else str(tips)
            self.voice_table.setItem(row, 2, QTableWidgetItem(tips_str))

    def _build_logs_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)

        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(4)
        self.logs_table.setHorizontalHeaderLabels(["Timestamp", "Type", "Action", "Details"])
        self.logs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.logs_table.setStyleSheet("""
            QTableWidget {
                background: #1E2030;
                color: #CAD3F5;
                gridline-color: #363A4F;
                border: none;
                border-radius: 8px;
            }
            QHeaderView::section {
                background: #24273A;
                color: #8AADF4;
                font-weight: 700;
                padding: 8px;
                border: none;
            }
        """)

        self._refresh_logs_table()
        layout.addWidget(self.logs_table)

        btn = QPushButton("Refresh Logs")
        btn.setStyleSheet("background: #363A4F; color: #CAD3F5; padding: 8px 16px; border-radius: 6px; max-width: 140px;")
        btn.clicked.connect(self._refresh_logs_table)
        layout.addWidget(btn)

        return w

    def _refresh_logs_table(self):
        logs = db.get_recent_logs(30)
        self.logs_table.setRowCount(len(logs))
        for row, l in enumerate(logs):
            self.logs_table.setItem(row, 0, QTableWidgetItem(l.get("timestamp", "")[:19]))
            self.logs_table.setItem(row, 1, QTableWidgetItem(l.get("event_type", "")))
            self.logs_table.setItem(row, 2, QTableWidgetItem(l.get("action", "")))
            self.logs_table.setItem(row, 3, QTableWidgetItem(l.get("details", "")))
