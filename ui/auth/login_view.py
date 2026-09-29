# ============================================================
#  AUTH VIEW — Glassmorphic Login & Biometric Enrollment
# ============================================================

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QFrame
)

from intent_platform.core.auth.face_auth import FaceAuthManager
from intent_platform.database.connection import db


class AuthDialog(QWidget):
    """Modern authentication and biometric enrollment screen."""

    authenticated = Signal(dict)  # Emits user profile dict upon successful auth

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Intent OS — Identity & Access")
        self.resize(780, 520)
        self.setStyleSheet("""
            QWidget {
                background: #11121D;
                color: #CAD3F5;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLineEdit {
                background: #181926;
                border: 1px solid #363A4F;
                border-radius: 8px;
                padding: 10px 14px;
                color: #CAD3F5;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #8AADF4;
                background: #1E2030;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8AADF4, stop:1 #B7BDF8);
                color: #11121D;
                font-weight: 700;
                font-size: 13px;
                border-radius: 8px;
                padding: 10px 16px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #91B4FA, stop:1 #C6CBFF);
            }
            QPushButton#secondaryBtn {
                background: #24273A;
                color: #CAD3F5;
                border: 1px solid #363A4F;
            }
            QPushButton#secondaryBtn:hover {
                background: #363A4F;
            }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(30)

        # Left Column: Brand & Info
        left_panel = QFrame()
        left_panel.setStyleSheet("background: #181926; border-radius: 16px; padding: 24px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(16)

        brand_lbl = QLabel("INTENT OS")
        brand_lbl.setStyleSheet("font-size: 24px; font-weight: 800; color: #8AADF4; letter-spacing: 2px;")
        tagline = QLabel("Next-Generation Multi-Modal AI Workspace & Biometric Desktop Assistant")
        tagline.setWordWrap(True)
        tagline.setStyleSheet("color: #A5ADCB; font-size: 13px; line-height: 1.4;")

        feature_box = QLabel("• 3-Layer Vision Security\n• Sub-pixel Velocity Cursor\n• Real-time Speech Intent\n• 60 FPS QML Companion")
        feature_box.setStyleSheet("color: #8087A2; font-size: 12px; margin-top: 20px; line-height: 1.8;")

        left_layout.addWidget(brand_lbl)
        left_layout.addWidget(tagline)
        left_layout.addWidget(feature_box)
        left_layout.addStretch()

        main_layout.addWidget(left_panel, 1)

        # Right Column: Stacked Login / Signup
        self.stack = QStackedWidget()

        self.login_page = self._build_login_page()
        self.signup_page = self._build_signup_page()

        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.signup_page)

        main_layout.addWidget(self.stack, 1)

    def _build_login_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)

        title = QLabel("Sign In")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #FFFFFF;")

        self.login_user = QLineEdit()
        self.login_user.setPlaceholderText("Username")
        self.login_user.returnPressed.connect(lambda: self.login_pass.setFocus())

        self.login_pass = QLineEdit()
        self.login_pass.setPlaceholderText("Password")
        self.login_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_pass.returnPressed.connect(self._handle_login)

        self.login_error = QLabel("")
        self.login_error.setStyleSheet("color: #ED8796; font-size: 12px;")
        self.login_error.setWordWrap(True)

        submit_btn = QPushButton("Sign In")
        submit_btn.clicked.connect(self._handle_login)

        switch_btn = QPushButton("Create Account")
        switch_btn.setObjectName("secondaryBtn")
        switch_btn.clicked.connect(self._switch_to_signup)

        # Quick Guest login for seamless demo
        guest_btn = QPushButton("Continue as Guest / Operator")
        guest_btn.setObjectName("secondaryBtn")
        guest_btn.clicked.connect(self._handle_guest_login)

        layout.addWidget(title)
        layout.addWidget(self.login_user)
        layout.addWidget(self.login_pass)
        layout.addWidget(self.login_error)
        layout.addWidget(submit_btn)
        layout.addWidget(switch_btn)
        layout.addWidget(guest_btn)
        layout.addStretch()
        return w

    def _build_signup_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)

        title = QLabel("Enroll Biometric Profile")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #FFFFFF;")

        self.signup_user = QLineEdit()
        self.signup_user.setPlaceholderText("Username")
        self.signup_user.returnPressed.connect(lambda: self.signup_name.setFocus())

        self.signup_name = QLineEdit()
        self.signup_name.setPlaceholderText("Full Name")
        self.signup_name.returnPressed.connect(lambda: self.signup_pass.setFocus())

        self.signup_pass = QLineEdit()
        self.signup_pass.setPlaceholderText("Password")
        self.signup_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.signup_pass.returnPressed.connect(self._handle_signup)

        self.signup_error = QLabel("")
        self.signup_error.setStyleSheet("color: #ED8796; font-size: 12px;")
        self.signup_error.setWordWrap(True)

        submit_btn = QPushButton("Complete Enrollment")
        submit_btn.clicked.connect(self._handle_signup)

        back_btn = QPushButton("Back to Sign In")
        back_btn.setObjectName("secondaryBtn")
        back_btn.clicked.connect(self._switch_to_login)

        layout.addWidget(title)
        layout.addWidget(self.signup_user)
        layout.addWidget(self.signup_name)
        layout.addWidget(self.signup_pass)
        layout.addWidget(self.signup_error)
        layout.addWidget(submit_btn)
        layout.addWidget(back_btn)
        layout.addStretch()
        return w

    def _switch_to_signup(self):
        self.signup_error.setText("")
        self.login_error.setText("")
        self.stack.setCurrentIndex(1)
        self.signup_user.setFocus()

    def _switch_to_login(self):
        self.signup_error.setText("")
        self.login_error.setText("")
        self.stack.setCurrentIndex(0)
        self.login_user.setFocus()

    def _handle_login(self):
        user = self.login_user.text().strip()
        pwd = self.login_pass.text().strip()
        if not user or not pwd:
            self.login_error.setStyleSheet("color: #ED8796; font-size: 12px;")
            self.login_error.setText("Please enter username and password")
            return

        # Show progress feedback
        self.login_error.setStyleSheet("color: #8AADF4; font-size: 12px;")
        self.login_error.setText("Verifying credentials & face biometric...")
        self.repaint()  # Force UI update before camera call

        ok, profile = FaceAuthManager.authenticate_credentials(user, pwd)
        if ok and profile:
            self._is_authenticated = True
            self.login_error.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 600;")
            self.login_error.setText("✓ Authenticated! Opening workspace...")
            self.repaint()
            self.authenticated.emit(profile)
            self.hide()  # Hide dialog to keep Qt event loop alive for MainWindow
        else:
            err = getattr(FaceAuthManager, 'last_error', None) or "Invalid credentials or face authentication failed"
            # If face does not match, user requested: direct to sign up!
            if "does not match" in err.lower() or "face authentication failed" in err.lower():
                self._switch_to_signup()
                self.signup_user.setText(user)
                self.signup_name.setText(user.title())
                self.signup_error.setStyleSheet("color: #ED8796; font-size: 12px; font-weight: 600;")
                self.signup_error.setText("⚠️ Face Mismatch: Camera face does not match enrolled profile. Please enroll your face or create account.")
            else:
                self.login_error.setStyleSheet("color: #ED8796; font-size: 12px;")
                self.login_error.setText(err)

    def _handle_signup(self):
        user = self.signup_user.text().strip()
        name = self.signup_name.text().strip()
        pwd = self.signup_pass.text().strip()
        if not user or not name or not pwd:
            self.signup_error.setStyleSheet("color: #ED8796; font-size: 12px;")
            self.signup_error.setText("All fields are required")
            return

        # Check if user already exists
        existing = db.get_user(user)
        if existing:
            self.signup_error.setStyleSheet("color: #ED8796; font-size: 12px;")
            self.signup_error.setText(f"Username '{user}' already exists. Please choose another or sign in.")
            return

        self.signup_error.setStyleSheet("color: #8AADF4; font-size: 12px;")
        self.signup_error.setText("Capturing facial biometric from camera... please look directly at camera")
        self.repaint()

        pwd_hash = FaceAuthManager.hash_password(pwd)
        frame_rgb = FaceAuthManager.capture_camera_frame()
        face_enc = FaceAuthManager.extract_face_encoding(frame_rgb) if frame_rgb is not None else None

        ok = db.register_user(user, pwd_hash, name, face_encoding=face_enc)
        if ok:
            # Clear enrollment password
            self.signup_pass.clear()
            self.signup_error.setText("")

            # Pre-fill login credentials and switch to Login page
            self.login_user.setText(user)
            self.login_pass.clear()
            self.login_error.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 600;")
            face_status = "✓ Enrolled with biometric face!" if face_enc is not None else "✓ Enrolled (Face will be verified at login)!"
            self.login_error.setText(f"{face_status} Please sign in with your credentials.")
            self.stack.setCurrentIndex(0)
            self.login_pass.setFocus()
        else:
            self.signup_error.setStyleSheet("color: #ED8796; font-size: 12px;")
            self.signup_error.setText("Registration error. Please try again.")

    def _handle_guest_login(self):
        self._is_authenticated = True
        frame_rgb = FaceAuthManager.capture_camera_frame()
        face_enc = FaceAuthManager.extract_face_encoding(frame_rgb) if frame_rgb is not None else None
        self.authenticated.emit({
            "username": "guest",
            "full_name": "Guest Operator",
            "face_encoding": face_enc
        })
        self.hide()

    def closeEvent(self, event):
        """Ensure closing the login window exits the application without hanging the terminal."""
        if not getattr(self, '_is_authenticated', False):
            from PySide6.QtWidgets import QApplication
            QApplication.quit()
        event.accept()
