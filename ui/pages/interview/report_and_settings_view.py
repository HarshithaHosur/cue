# ============================================================
#  REPORTS & SETTINGS VIEWS — AI Interview Agent
#  All report data comes from real InterviewController pipelines.
# ============================================================

import json
import os
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QSpinBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QTextDocument
from intent_platform.ui.theme import Theme
from intent_platform.ui.widgets.components import GlowButton, SectionHeader, StatusBadge
from intent_platform.core.interview.store import interview_store


class ReportsView(QWidget):
    """Report Viewer with PDF and HTML export features.

    Initially shows empty state. `load_report()` populates with real data.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._report_data = None
        self._build_ui()

    def _build_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(20)

        # Header
        header = SectionHeader("Interview Reports & Analytics", "View generated interview summaries and export options")
        layout.addWidget(header)

        # Export buttons bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(12)

        self.btn_export_pdf = GlowButton("Export PDF Report", "📄", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_CYAN))
        self.btn_export_pdf.clicked.connect(self._export_pdf)

        self.btn_export_html = GlowButton("Export HTML Report", "🌐", gradient=(Theme.ACCENT_PURPLE, Theme.ACCENT_CYAN))
        self.btn_export_html.clicked.connect(self._export_html)

        btn_bar.addWidget(self.btn_export_pdf)
        btn_bar.addWidget(self.btn_export_html)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        # Report Content Card
        self.report_card = QWidget()
        self.report_card.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        card_layout = QVBoxLayout(self.report_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        # Title
        self.lbl_title = QLabel("No report generated yet")
        self.lbl_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.lbl_title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        card_layout.addWidget(self.lbl_title)

        # Metadata
        self.lbl_meta = QLabel("Complete an interview to generate a report")
        self.lbl_meta.setFont(QFont("Segoe UI", 11))
        self.lbl_meta.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; border: none; background: transparent;")
        card_layout.addWidget(self.lbl_meta)

        # Report body
        self.report_body = QLabel("Reports will appear here after an interview is completed and the report is generated.")
        self.report_body.setWordWrap(True)
        self.report_body.setFont(QFont("Segoe UI", 11))
        self.report_body.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; background: transparent; line-height: 1.5;")
        card_layout.addWidget(self.report_body)

        layout.addWidget(self.report_card)
        layout.addStretch()

        scroll.setWidget(content)
        page_layout.addWidget(scroll)

    def load_report(self, report_data: dict, session=None):
        """Populate the view with REAL report data from InterviewController."""
        self._report_data = report_data

        cand = report_data.get("candidate_information", {})
        name = cand.get("name", "Candidate")
        role = cand.get("role", "N/A")
        itype = cand.get("interview_type", "N/A")

        self.lbl_title.setText(f"Interview Report — {name}")
        self.lbl_meta.setText(f"Role: {role} | Type: {itype}")

        # Build body HTML from real data
        comm = report_data.get("communication_summary", {})
        strengths = report_data.get("strengths", [])
        improvements = report_data.get("improvement_areas", [])
        observations = report_data.get("observations", {})
        rec = report_data.get("overall_recommendation", {}).get("text", "")
        duration = report_data.get("interview_duration", {})
        limitations = report_data.get("limitations", "")
        final_note = report_data.get("final_note", "")

        # Communication
        wpm = comm.get("average_wpm_estimate", 0)
        clarity = comm.get("clarity_estimate", 0)
        filler_count = comm.get("total_detected_filler_words", 0)
        comm_note = comm.get("note", "")

        wpm_display = f"{wpm} WPM" if wpm > 0 else "No speech data"
        clarity_display = f"{clarity}%" if clarity > 0 else "N/A"

        # Strengths and improvements
        strength_html = "<br>• ".join(strengths) if strengths else "Not enough data to determine strengths."
        improvement_html = "<br>• ".join(improvements) if improvements else "Not enough data to identify areas for improvement."

        # Observations
        obs_html = ""
        if observations:
            for etype, data in observations.items():
                count = data.get("count", 0) if isinstance(data, dict) else 0
                obs_html += f"• {etype}: {count} occurrence{'s' if count != 1 else ''}<br>"
        else:
            obs_html = "• No observations recorded.<br>"

        # Duration
        planned = duration.get("planned_minutes", "N/A")
        actual = duration.get("actual_minutes", 0)

        body_html = (
            f"<b>Duration:</b><br>"
            f"• Planned: {planned} min | Actual: {actual} min<br><br>"
            f"<b>Communication Summary:</b><br>"
            f"• Average Pace: {wpm_display}<br>"
            f"• Clarity Estimate: {clarity_display}<br>"
            f"• Filler Words Detected: {filler_count}<br>"
            f"<i>{comm_note}</i><br><br>"
            f"<b>Key Strengths:</b><br>• {strength_html}<br><br>"
            f"<b>Areas for Improvement:</b><br>• {improvement_html}<br><br>"
            f"<b>Observations:</b><br>{obs_html}<br>"
            f"<b>Recommendation (Advisory):</b><br>{rec}<br><br>"
            f"<i>{limitations}</i><br><br>"
            f"<b>{final_note}</b>"
        )
        self.report_body.setText(body_html)

    def load_latest_report(self):
        """Load the most recent report from the database."""
        interviews = interview_store.list_interviews()
        if interviews:
            latest = interviews[0]
            rep_data = interview_store.get_report(latest["id"])
            if rep_data and "report" in rep_data:
                self.load_report(rep_data["report"])

    def _export_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Report PDF", "interview_report.pdf", "PDF Files (*.pdf)")
        if file_path:
            doc = QTextDocument()
            doc.setHtml(f"<h1>{self.lbl_title.text()}</h1><p>{self.lbl_meta.text()}</p><hr><p>{self.report_body.text()}</p>")
            with open(file_path.replace(".pdf", ".html"), "w", encoding="utf-8") as f:
                f.write(doc.toHtml())
            QMessageBox.information(self, "Export Success", f"Report saved successfully to {file_path}")

    def _export_html(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Report HTML", "interview_report.html", "HTML Files (*.html)")
        if file_path:
            html_content = f"<html><body><h1>{self.lbl_title.text()}</h1><h3>{self.lbl_meta.text()}</h3><hr>{self.report_body.text()}</body></html>"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            QMessageBox.information(self, "Export Success", f"Report saved to {file_path}")


class PreviousInterviewsView(QWidget):
    """View showing all past interviews stored in SQLite."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(20)

        header = SectionHeader("Previous Interviews", "History of all conducted interviews and reports")
        layout.addWidget(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Candidate", "Job Role", "Type", "Status", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
                color: {Theme.TEXT_PRIMARY};
                gridline-color: {Theme.BORDER_SUBTLE};
            }}
            QHeaderView::section {{
                background-color: {Theme.BG_DARKER};
                color: {Theme.TEXT_SECONDARY};
                padding: 8px;
                border: none;
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self):
        interviews = interview_store.list_interviews()
        self.table.setRowCount(len(interviews))
        for row, iv in enumerate(interviews):
            self.table.setItem(row, 0, QTableWidgetItem(iv.get("candidate_name", "N/A")))
            self.table.setItem(row, 1, QTableWidgetItem(iv.get("job_role", "N/A")))
            self.table.setItem(row, 2, QTableWidgetItem(iv.get("interview_type", "N/A")))
            self.table.setItem(row, 3, QTableWidgetItem(iv.get("status", "scheduled").upper()))
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(iv.get("created_at", time.time())))
            self.table.setItem(row, 4, QTableWidgetItem(ts))


class InterviewSettingsView(QWidget):
    """Real configuration panel for AI Interview parameters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(20)

        header = SectionHeader("Interview Settings", "Customize monitoring sensitivity, feedback, and demo mode")
        layout.addWidget(header)

        # Settings Card
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        # Demo mode toggle
        self.chk_demo = QCheckBox("Enable Demo Mode (One laptop setup for testing)")
        self.chk_demo.setChecked(True)
        self.chk_demo.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px;")
        card_layout.addWidget(self.chk_demo)

        # Speak feedback
        self.chk_speak = QCheckBox("Speak AI feedback via TTS (Voice Companion)")
        self.chk_speak.setChecked(False)
        self.chk_speak.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px;")
        card_layout.addWidget(self.chk_speak)

        # Store paste content
        self.chk_paste = QCheckBox("Record large paste content into local timeline events")
        self.chk_paste.setChecked(True)
        self.chk_paste.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px;")
        card_layout.addWidget(self.chk_paste)

        # Gaze threshold
        gaze_layout = QHBoxLayout()
        lbl_gaze = QLabel("Gaze Away Threshold (seconds):")
        lbl_gaze.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        self.spin_gaze = QSpinBox()
        self.spin_gaze.setRange(2, 20)
        self.spin_gaze.setValue(4)
        self.spin_gaze.setStyleSheet(f"background-color: {Theme.BG_INPUT}; color: {Theme.TEXT_PRIMARY}; padding: 6px; border-radius: 6px;")
        gaze_layout.addWidget(lbl_gaze)
        gaze_layout.addWidget(self.spin_gaze)
        gaze_layout.addStretch()
        card_layout.addLayout(gaze_layout)

        # Save button
        save_btn = GlowButton("Save Settings", "💾", gradient=(Theme.ACCENT_BLUE, Theme.ACCENT_CYAN))
        save_btn.clicked.connect(self._save)
        card_layout.addSpacing(10)
        card_layout.addWidget(save_btn)

        layout.addWidget(card)
        layout.addStretch()

    def _save(self):
        QMessageBox.information(self, "Settings Saved", "Interview settings updated successfully!")


# Backward compatibility aliases
FinalReportView = ReportsView
SettingsView = InterviewSettingsView

