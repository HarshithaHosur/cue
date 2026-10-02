# ============================================================
#  TEST: PREFLIGHT TO LIVE INTERVIEW LAUNCH & LIFECYCLE
# ============================================================

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from intent_platform.core.engine import IntentEngine
from intent_platform.core.interview.controller import InterviewController
from intent_platform.core.interview.models import InterviewSetup, InterviewState
from intent_platform.ui.pages.interview.interview_dashboard import InterviewDashboard


class TestPreflightLiveLaunchFlow(unittest.TestCase):

    def setUp(self):
        self.engine = IntentEngine()
        self.page = InterviewDashboard(engine=self.engine)

    def tearDown(self):
        if self.page.controller and self.page.controller.is_live:
            self.page.controller.end_interview()
        self.page.deleteLater()
        app.processEvents()

    def test_preflight_launch_flow(self):
        # 1. Simulate user selecting ongoing interview setup
        setup = InterviewSetup(
            title="Senior AI Engineer Interview",
            candidate_name="Alex Chen",
            candidate_email="alex.chen@example.com",
            job_role="Senior AI Engineer",
            interview_type="Technical",
            duration_minutes=45,
            meeting_platform="Zoom",
            meeting_link="https://zoom.us/j/1234567890?pwd=testPasscode"
        )
        self.page._pending_setup = setup

        # 2. Trigger Preflight Check
        self.page._stack.setCurrentIndex(3)
        self.page._execute_preflight()
        app.processEvents()

        # Check that launch button is enabled
        self.assertTrue(self.page._preflight_start_btn.isEnabled())

        # 3. Simulate user clicking 'Launch Live Interview'
        initial_frame_taps_count = len(self.engine.frame_taps)
        self.page._on_preflight_start()
        app.processEvents()

        # 4. Verify Live Interview State & Workspace
        self.assertTrue(self.page.controller.is_live)
        self.assertEqual(self.page._stack.currentIndex(), 4)  # Live Workspace page index
        self.assertEqual(len(self.engine.frame_taps), initial_frame_taps_count + 1)
        self.assertIsNotNone(self.engine.gesture_interceptor)
        self.assertTrue(self.engine.voice_engine.interview_mode)

        # 5. End Interview
        self.page._on_end_interview_clicked(confirm=False)
        app.processEvents()

        self.assertFalse(self.page.controller.is_live)
        self.assertEqual(len(self.engine.frame_taps), initial_frame_taps_count)
        self.assertIsNone(self.engine.gesture_interceptor)
        self.assertFalse(self.engine.voice_engine.interview_mode)

        # 6. Test Repeat Launch (Launch -> End -> Launch again)
        self.page._pending_setup = setup
        self.page._execute_preflight()
        app.processEvents()

        self.page._on_preflight_start()
        app.processEvents()

        self.assertTrue(self.page.controller.is_live)
        self.assertEqual(self.page._stack.currentIndex(), 4)
        self.assertEqual(len(self.engine.frame_taps), initial_frame_taps_count + 1)

        self.page._on_end_interview_clicked(confirm=False)
        app.processEvents()
        self.assertFalse(self.page.controller.is_live)


if __name__ == "__main__":
    unittest.main()
