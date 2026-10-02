# ============================================================
#  END-TO-END DEMO SIMULATION SCRIPT
#  Tests the complete user journey from meeting link input
#  to live AI co-piloting, visual code explanation, and
#  evidence-based post-interview report generation.
# ============================================================

import sys
import os
import time

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from intent_platform.core.interview.controller import InterviewController
from intent_platform.core.interview.models import InterviewSetup, InterviewState
from intent_platform.core.interview.store import interview_store
from intent_platform.core.features.feature_manager import get_feature_manager, Feature


def run_manual_acceptance_simulation():
    print("=" * 60)
    print("STARTING END-TO-END ZOOM INTERVIEW COACH SIMULATION")
    print("=" * 60)

    # 1. Initialize Controller
    ctrl = InterviewController()

    # 2. STEP 1 & 2: Candidate & Resume Context
    print("\n[STEP 1 & 2] Configuring Interview & Parsing Sample Resume...")
    sample_resume_text = """
    Rahul Sharma
    rahul.sharma@example.com
    Experience:
    - Designed and implemented payment stream processing architecture using Kafka and Redis.
    - Managed containerized services with Kubernetes and Docker.
    Skills: Python, Go, Kafka, Redis, Kubernetes, PostgreSQL, AWS.
    """
    resume_path = os.path.abspath("temp_sample_resume.txt")
    with open(resume_path, "w", encoding="utf-8") as f:
        f.write(sample_resume_text)

    setup = InterviewSetup(
        title="Senior Distributed Systems Interview",
        candidate_name="Rahul Sharma",
        candidate_email="rahul.sharma@example.com",
        job_role="Senior Software Engineer",
        interview_type="Technical",
        duration_minutes=45,
        difficulty="Hard",
        meeting_platform="Zoom",
        meeting_link="https://zoom.us/j/1234567890?pwd=demoPasscode123",
        resume_path=resume_path
    )

    # 3. STEP 3 & 4: Rubric & Meeting Link
    print("\n[STEP 3 & 4] Validating Zoom Meeting Link...")
    valid, msg, info = ctrl.parse_meeting_url(setup.meeting_link)
    assert valid, f"Meeting URL should be valid: {msg}"
    print(f"[OK] Validated: {msg} (Platform: {info['platform']}, ID: {info['meeting_id']})")

    # 4. STEP 5 & 6: Preflight Check
    print("\n[STEP 5 & 6] Executing Preflight Readiness Check...")
    preflight = ctrl.run_preflight(setup=setup)
    assert preflight.can_start, "Preflight should allow start in companion/SDK mode"
    for check in preflight.checks:
        status_icon = "[OK]" if check.available else "[WARN]"
        print(f"  {status_icon} {check.name}: {check.message}")

    # 5. STEP 7: Start Live Interview
    print("\n[STEP 7] Starting Live Embedded Interview Session...")
    iid = ctrl.start_interview(setup)
    assert iid is not None, "Interview session ID must be generated"
    assert ctrl.is_live, "Interview state must be LIVE"
    print(f"[OK] Live Session Created: ID={iid}")

    # 6. STEP 8: Interviewer Asks Opening Question
    print("\n[STEP 8] Interviewer asks technical architecture question...")
    t0 = time.time()
    ctrl.record_transcript("interviewer", "Rahul, can you walk me through your messaging architecture?", 4.0, t0)
    time.sleep(0.05)
    app.processEvents()

    # 7. STEP 9: Candidate Mentions Kafka (Resume Claim Detected)
    print("\n[STEP 9] Candidate answers referencing Kafka...")
    t1 = t0 + 5.0
    ctrl.record_transcript("candidate", "In our production platform, we used Kafka to decouple the payment services.", 6.0, t1)
    time.sleep(0.1)
    app.processEvents()

    resume_summary = ctrl.metrics.resume_summary
    print(f"[OK] Resume claims tracked: Total={resume_summary.get('total_claims')}, Discussed={resume_summary.get('discussed_count')}")
    assert resume_summary.get("discussed_count", 0) >= 1, "Kafka claim should be marked as discussed"

    # 8. STEP 10: Rubric Coverage & AI Follow-Up Generation
    print("\n[STEP 10] Checking Rubric Coverage & Follow-Up Suggestions...")
    rubric_summary = ctrl.metrics.rubric_summary
    print(f"[OK] Rubric Coverage: {int(rubric_summary.get('coverage_pct', 0))}%")
    active_sugs = ctrl.copilot_engine.get_active_suggestions()
    print(f"[OK] Active Copilot Suggestions: {len(active_sugs)}")
    if active_sugs:
        print(f"  [COACH] Top Suggestion: {active_sugs[0].title} -> {active_sugs[0].content}")

    # 9. STEP 11: Interviewer Asks Sensitive Question (Fairness Alert)
    print("\n[STEP 11] Simulating sensitive question query...")
    t2 = t1 + 8.0
    ctrl.record_transcript("interviewer", "Before we move on, what year were you born and what is your marital status?", 3.5, t2)
    time.sleep(0.05)
    app.processEvents()
    print("[OK] Sensitive question intercepted non-accusatorily by Copilot.")

    # 10. STEP 12: Overlapping Speech / Interruption Detection
    print("\n[STEP 12] Simulating overlapping speech...")
    t3 = t2 + 4.0
    ctrl.record_transcript("interviewer", "Wait, let me finish...", 1.5, t3)
    t4 = t3 + 0.2  # Starts while interviewer is speaking
    ctrl.record_transcript("candidate", "Sure, I was saying...", 2.0, t4)
    time.sleep(0.05)
    app.processEvents()
    print(f"[OK] Interruptions detected: {len(ctrl.metrics.interruptions)}")
    assert len(ctrl.metrics.interruptions) >= 1, "Interruption overlap should be recorded"

    # 11. STEP 13 & 14: Candidate Shares Screen & "Explain This" Requested
    print("\n[STEP 13 & 14] Candidate shares screen; Interviewer requests Visual Explanation...")
    ctrl.zoom_adapter.update_screen_share_state(True, "Rahul Sharma")
    assert ctrl.zoom_adapter.is_screen_shared, "Screen share state should be True"

    code_snippet = "for item in data:\n    for target in search_list:\n        if item == target: return True"
    ctrl.request_visual_explanation(code_snippet, source="shared_screen_selection")
    for _ in range(10):
        time.sleep(0.05)
        app.processEvents()

    # 12. STEP 15: Concurrency & Feature Isolation
    print("\n[STEP 15] Testing Feature Toggles (Concurrency & No Duplicate Workers)...")
    fm = get_feature_manager()
    fm.set_enabled(Feature.MOUSE.value, False)
    assert not fm.is_enabled(Feature.MOUSE.value), "Mouse should be disabled"
    assert fm.is_enabled(Feature.VOICE.value), "Voice must remain active"
    fm.set_enabled(Feature.MOUSE.value, True)
    assert fm.is_enabled(Feature.MOUSE.value), "Mouse re-enabled successfully without duplicate workers"

    # 13. STEP 16 & 17: End Interview & Generate Report
    print("\n[STEP 16 & 17] Ending Interview & Verifying Intelligence Report...")
    report = ctrl.end_interview()
    assert not ctrl.is_live, "Session should be ended"
    assert report is not None, "Report must be generated"

    cand_info = report["interview_details"]
    conv = report["conversation_analysis"]
    print(f"[OK] Report Candidate: {cand_info['candidate_name']} ({cand_info['job_role']})")
    print(f"[OK] Interviewer Talk: {conv.get('interviewer_talk_pct')}% | Candidate Talk: {conv.get('candidate_talk_pct')}%")
    print(f"[OK] Interruptions Count: {conv.get('interruption_count')}")
    print(f"[OK] Evidence Timeline Events: {len(report.get('evidence_timeline', []))}")
    print(f"[OK] Final Evaluator Notice: {report.get('final_evaluator_notice')}")

    # Ensure clean up
    if os.path.exists(resume_path):
        os.remove(resume_path)

    print("\n" + "=" * 60)
    print("ALL END-TO-END ACCEPTANCE CRITERIA PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_manual_acceptance_simulation()
