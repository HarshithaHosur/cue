# ============================================================
#  TEST: REAL ZOOM PARTICIPANT LIFECYCLE & LIVE WORKSPACE
#  Verifies:
#  1. Initial state has exactly 1 participant (interviewer) in standby
#  2. Remote participant joining updates count to 2 with real name
#  3. Candidate speech triggers real transcript & evidence-based AI coach
#  4. Remote participant leaving resets count to 1 and enters standby
# ============================================================

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from intent_platform.core.engine import IntentEngine
from intent_platform.core.interview.models import InterviewSetup
from intent_platform.ui.pages.interview.interview_dashboard import InterviewDashboard


class TestZoomRealParticipantLifecycle(unittest.TestCase):

    def setUp(self):
        self.engine = IntentEngine()
        self.dashboard = InterviewDashboard(engine=self.engine)

    def tearDown(self):
        if self.dashboard.controller and self.dashboard.controller.is_live:
            self.dashboard.controller.end_interview()
        self.dashboard.deleteLater()
        app.processEvents()

    def test_complete_zoom_participant_lifecycle(self):
        # 1. Setup an interview session
        setup = InterviewSetup(
            title="Backend Architect Interview",
            candidate_name="Jane Smith",
            job_role="Senior Backend Architect",
            interview_type="Technical",
            duration_minutes=45,
            meeting_platform="Zoom",
            meeting_link="https://zoom.us/j/9876543210?pwd=secretPasscode"
        )
        self.dashboard._pending_setup = setup
        self.dashboard._on_preflight_start()
        app.processEvents()

        ws = self.dashboard.zoom_workspace
        coach = self.dashboard.coach_tabs

        # 2. Verify Initial Live State (Interviewer alone)
        self.assertTrue(self.dashboard.controller.is_live)
        self.assertEqual(ws._participant_count, 1)
        self.assertEqual(ws.btn_participants.text(), "👥 Participants (1)")
        self.assertEqual(ws.lbl_int_name.text(), "🔵 You (Interviewer / Host)")
        self.assertIn("Waiting for another participant", ws.lbl_cand_name.text())
        self.assertEqual(ws.lbl_video_quality.text(), "Standby")
        self.assertIn("1 Participant", self.dashboard._live_title_lbl.text())
        self.assertIn("Waiting for candidate activity", coach.lbl_sug_body.text())

        # 3. Remote Participant Joins
        self.dashboard.controller.zoom_adapter.add_remote_participant("part_002", "Jane Smith")
        app.processEvents()

        # Verify state with 2 participants
        self.assertEqual(ws._participant_count, 2)
        self.assertEqual(ws.btn_participants.text(), "👥 Participants (2)")
        self.assertEqual(ws.lbl_cand_name.text(), "🟢 Jane Smith")
        self.assertEqual(ws.lbl_video_quality.text(), "● Connected")
        self.assertIn("Connected (Jane Smith)", self.dashboard._live_title_lbl.text())
        self.assertIn("Waiting for speech", coach.lbl_sug_body.text())

        # 4. Candidate Speaks (Real Speech Event)
        self.dashboard.controller.record_transcript(
            "candidate",
            "We used Kafka for asynchronous communication and high throughput messaging.",
            duration=3.5
        )
        app.processEvents()
        time.sleep(0.1)
        app.processEvents()

        # Verify transcript and metrics
        self.assertTrue(self.dashboard.transcript_widget._has_entries)
        self.assertGreater(self.dashboard.controller.metrics.candidate_talk_s, 0.0)

        # 5. Screen Share Active
        self.dashboard.controller.zoom_adapter.update_screen_share_state(True, "Jane Smith")
        app.processEvents()

        self.assertTrue(ws._is_screen_shared)
        self.assertTrue(ws.btn_explain.isEnabled())
        self.assertIn("Jane Smith's Workspace", ws.lbl_screen_header.text())

        # 6. Screen Share Ends
        self.dashboard.controller.zoom_adapter.update_screen_share_state(False)
        app.processEvents()

        self.assertFalse(ws._is_screen_shared)
        self.assertFalse(ws.btn_explain.isEnabled())
        self.assertIn("Standby", ws.lbl_screen_header.text())

        # 7. Remote Participant Leaves
        self.dashboard.controller.zoom_adapter.remove_remote_participant("part_002")
        app.processEvents()

        # Verify return to 1 participant
        self.assertEqual(ws._participant_count, 1)
        self.assertEqual(ws.btn_participants.text(), "👥 Participants (1)")
        self.assertIn("Waiting for another participant", ws.lbl_cand_name.text())
        self.assertEqual(ws.lbl_video_quality.text(), "Standby")
        self.assertIn("1 Participant", self.dashboard._live_title_lbl.text())
        self.assertIn("Waiting for candidate activity", coach.lbl_sug_body.text())

        # 8. Cleanly End Interview
        self.dashboard._on_end_interview_clicked(confirm=False)
        app.processEvents()

        self.assertFalse(self.dashboard.controller.is_live)


if __name__ == "__main__":
    unittest.main()
