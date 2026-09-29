# ============================================================
#  APPLICATION ENTRY POINT — Intent AI Platform
# ============================================================

import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from intent_platform.core.engine import IntentEngine
from intent_platform.ui.main_window import MainWindow
from intent_platform.ui.auth.login_view import AuthDialog


def main():
    # Enable high DPI display
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Intent AI Platform")
    app.setOrganizationName("IntentAI")

    # Enable immediate Ctrl+C termination from terminal
    import signal
    signal.signal(signal.SIGINT, lambda *args: app.quit())
    sig_timer = QTimer()
    sig_timer.timeout.connect(lambda: None)  # Gives Python interpreter control every 500ms to handle SIGINT
    sig_timer.start(500)

    # DO NOT start the engine yet — it grabs the camera and blocks the login
    engine = IntentEngine()

    main_win = None
    auth_dialog = AuthDialog()

    # Keep app alive even when auth dialog closes
    app.setQuitOnLastWindowClosed(False)

    def on_authenticated(profile: dict):
        nonlocal main_win
        try:
            # 1. Set user profile on the engine (face encoding for continuous auth)
            engine.set_authenticated_user(profile)

            # 2. Create and show the dashboard FIRST (so window is visible)
            main_win = MainWindow(user_profile=profile, engine=engine)
            main_win.show()

            # 3. NOW start the vision engine (camera loop) after dashboard is visible
            engine.start()

            # 4. Enable quit-on-close so closing dashboard exits the app
            app.setQuitOnLastWindowClosed(True)

        except Exception as e:
            import traceback
            traceback.print_exc()
            # If dashboard fails, quit the app
            app.quit()

    # Connect auth signal — when login succeeds, open dashboard
    auth_dialog.authenticated.connect(on_authenticated)
    auth_dialog.show()

    exit_code = app.exec()
    engine.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
