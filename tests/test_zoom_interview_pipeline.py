# ============================================================
#  TEST SUITE: AI INTERVIEWER COACH & EMBEDDED ZOOM PIPELINE
# ============================================================

import sys
import os
import time
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

# Initialize headless Qt App if none exists
app = QApplication.instance() or QApplication(sys.argv)

from intent_platform.core.interview.zoom.zoom_auth import ZoomAuthManager
from intent_platform.core.interview.zoom.zoom_meeting_adapter import ZoomMeetingAdapter, ZoomConnectionState
from intent_platform.core.interview.zoom.zoom_rtms_service import ZoomRTMSService, RTMSState
from intent_platform.core.interview.resume_parser import ResumeParser, ResumeClaimTracker
from intent_platform.core.interview.rubric_engine import RubricEngine
from intent_platform.core.interview.copilot_engine import InterviewCopilotEngine
from intent_platform.core.interview.controller import InterviewController
from intent_platform.core.interview.models import InterviewSetup, InterviewState
from intent_platform.core.interview.store import interview_store
from intent_platform.core.features.feature_manager import get_feature_manager, Feature
from intent_platform.core.agent.agent_controller import get_agent_controller


class TestZoomInterviewPipeline(unittest.TestCase):

    def setUp(self):
        self.auth = ZoomAuthManager()
        self.adapter = ZoomMeetingAdapter(auth_manager=self.auth)
        self.rtms = ZoomRTMSService(auth_manager=self.auth)

    def test_zoom_auth_status(self):
        status = self.auth.check_authorization_status()
        self.assertIn("sdk_configured", status)
        self.assertIn("rtms_configured", status)
        self.assertIn("missing_vars", status)

    def test_zoom_url_parser(self):
        # Valid Zoom URL with passcode
        valid_url = "https://us04web.zoom.us/j/7891234567?pwd=testpassword123"
        valid, msg, info = self.adapter.parse_meeting_link(valid_url)
        self.assertTrue(valid)
        self.assertEqual(info.get("meeting_id"), "7891234567")
        self.assertEqual(info.get("passcode"), "testpassword123")

        # Invalid URL
        invalid_url = "not_a_valid_link"
        valid, msg, _ = self.adapter.parse_meeting_link(invalid_url)
        self.assertFalse(valid)

    def test_zoom_rtms_lifecycle(self):
        session_id = "test_sess_001"
        self.rtms.initialize_session(session_id)
        self.rtms.start_stream()
        self.assertTrue(self.rtms.is_streaming)

        self.rtms.pause_stream()
        self.assertFalse(self.rtms.is_streaming)

        self.rtms.resume_stream()
        self.assertTrue(self.rtms.is_streaming)

        # Ingest transcript
        received = []
        self.rtms.transcript_segment.connect(lambda spk, txt, dur, ts: received.append((spk, txt)))
        self.rtms.inject_transcript_segment("candidate", "We used Kafka for streaming data.")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "candidate")

        self.rtms.stop_stream()
        self.assertFalse(self.rtms.is_streaming)

    def test_resume_parser_and_tracker(self):
        sample_resume_text = """
        John Doe
        john.doe@example.com
        Experience:
        - Built distributed payment microservices using Kafka and Redis.
        - Deployed scalable Docker containers on Kubernetes.
        Skills: Python, Go, PostgreSQL, AWS, Docker, Kubernetes.
        """
        parsed = ResumeParser.analyze_text(sample_resume_text, "resume.txt")
        self.assertTrue(parsed["success"])
        self.assertIn("Python", parsed["skills"])
        self.assertIn("Kafka", parsed["skills"])
        self.assertGreaterEqual(len(parsed["claims"]), 2)

        # Test live tracker
        tracker = ResumeClaimTracker(parsed["claims"])
        summary_init = tracker.get_summary()
        self.assertEqual(summary_init["discussed_count"], 0)

        # Candidate mentions Kafka
        tracker.evaluate_transcript_segment("candidate", "In my last role I used Kafka extensively.", time.time())
        summary_after = tracker.get_summary()
        self.assertGreaterEqual(summary_after["discussed_count"], 1)

    def test_rubric_engine(self):
        rubric = RubricEngine(interview_type="Technical")
        summary_init = rubric.get_summary()
        self.assertGreaterEqual(summary_init["total_criteria"], 3)
        self.assertEqual(summary_init["coverage_pct"], 0.0)

        # Candidate speaks about binary search and data structures
        rubric.evaluate_transcript("candidate", "We used binary search to optimize the array lookup time.", time.time())
        summary_after = rubric.get_summary()
        self.assertGreater(summary_after["coverage_pct"], 0.0)

        gaps = rubric.get_gaps()
        self.assertTrue(isinstance(gaps, list))

    def test_copilot_engine_risks_and_followups(self):
        copilot = InterviewCopilotEngine()

        # 1. Sensitive question check
        risk = copilot.analyze_interviewer_question("Are you married and do you have children?", time.time())
        self.assertIsNotNone(risk)
        self.assertEqual(risk["category"], "Marital / Family Status")

        # 2. Visual explanation
        received_explains = []
        copilot.visual_explain_ready.connect(lambda res: received_explains.append(res))
        copilot.explain_visual_selection("for i in range(n):\n    for j in range(n):\n        pass")
        for _ in range(10):
            time.sleep(0.05)
            QApplication.processEvents()
            if received_explains:
                break
        self.assertGreaterEqual(len(received_explains), 1)
        self.assertIn("O(n²)", received_explains[0]["complexity"])

    def test_full_interview_controller_lifecycle(self):
        ctrl = InterviewController()

        setup = InterviewSetup(
            title="Senior Backend Interview",
            candidate_name="Alex Rivera",
            candidate_email="alex@example.com",
            job_role="Backend Engineer",
            interview_type="Technical",
            duration_minutes=30,
            meeting_platform="Zoom",
            meeting_link="https://zoom.us/j/9988776655"
        )

        # 1. Preflight
        preflight = ctrl.run_preflight()
        self.assertTrue(preflight.can_start)

        # 2. Start Interview (Idempotency test)
        iid = ctrl.start_interview(setup)
        self.assertIsNotNone(iid)
        self.assertTrue(ctrl.is_live)

        # Verify only 1 session exists
        dup_iid = ctrl.start_interview(setup)
        self.assertEqual(iid, dup_iid)

        # 3. Simulate dialogue
        ctrl.record_transcript("interviewer", "Can you explain your messaging architecture?", 3.0)
        ctrl.record_transcript("candidate", "We deployed Kafka on Kubernetes for decoupling.", 5.0)

        # 4. Check talk time and transcript persistence
        trans = interview_store.get_transcript(iid)
        self.assertGreaterEqual(len(trans), 2)
        self.assertGreater(ctrl.metrics.total_talk_s, 0)

        # 5. End Interview & verify report
        report = ctrl.end_interview()
        self.assertFalse(ctrl.is_live)
        self.assertIsNotNone(report)
        self.assertEqual(report["interview_details"]["candidate_name"], "Alex Rivera")
        self.assertIn("conversation_analysis", report)
        self.assertIn("rubric_coverage", report)
        self.assertIn("resume_coverage", report)

    def test_concurrent_feature_isolation(self):
        fm = get_feature_manager()
        agent = get_agent_controller()

        # Ensure toggling one feature does not kill others
        fm.set_enabled(Feature.VOICE.value, True)
        fm.set_enabled(Feature.GESTURE.value, True)
        fm.set_enabled(Feature.MOUSE.value, False)

        self.assertTrue(fm.is_enabled(Feature.VOICE.value))
        self.assertTrue(fm.is_enabled(Feature.GESTURE.value))
        self.assertFalse(fm.is_enabled(Feature.MOUSE.value))

        # Re-enable mouse
        fm.set_enabled(Feature.MOUSE.value, True)
        self.assertTrue(fm.is_enabled(Feature.MOUSE.value))


if __name__ == "__main__":
    unittest.main()
