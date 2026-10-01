# ============================================================
#  AI INTERVIEW AGENT — ACCEPTANCE TEST SUITE
#  Run: venv\Scripts\python.exe scratch_test_interview.py
# ============================================================

import sys
import os
import time
import glob
import re
import json

# Ensure project root is on path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure intent_platform package maps to BASE_DIR
try:
    import intent_platform
except ModuleNotFoundError:
    import types
    import core, ui, config, database
    ip_mod = types.ModuleType('intent_platform')
    ip_mod.__path__ = [BASE_DIR]
    sys.modules['intent_platform'] = ip_mod
    sys.modules['intent_platform.core'] = core
    sys.modules['intent_platform.ui'] = ui
    sys.modules['intent_platform.config'] = config
    sys.modules['intent_platform.database'] = database

print("=" * 60)
print("  AI INTERVIEW AGENT ACCEPTANCE TEST SUITE")
print("=" * 60)

PASS_COUNT = 0
FAIL_COUNT = 0

def check(name, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  ✓ {name}")
    else:
        FAIL_COUNT += 1
        msg = f"  ✗ {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)

# ── 1. py_compile all new files ──
print("\n[1] Compile-checking all new and edited files...")
new_files = (
    glob.glob("core/interview/*.py", recursive=True)
)
compile_ok = True
for f in new_files:
    try:
        import py_compile
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"  COMPILE ERROR: {f} — {e}")
        compile_ok = False
check("All new files compile", compile_ok)

# ── 2. Store CRUD and idempotent table creation ──
print("\n[2] Testing InterviewStore CRUD...")
from intent_platform.core.interview.store import InterviewStore

# Create a fresh store (idempotent tables)
store = InterviewStore()

# Create interview
iid = store.create_interview({
    "title": "Test Interview",
    "candidate_name": "Jane Doe",
    "candidate_email": "jane@example.com",
    "job_role": "Backend Engineer",
    "interview_type": "Technical",
    "duration_minutes": 30,
    "difficulty": "Medium",
    "status": "scheduled",
})
check("Create interview", iid is not None and len(iid) > 0)

# Read interview
iv = store.get_interview(iid)
check("Read interview", iv is not None and iv["title"] == "Test Interview")

# Update status
store.update_interview_status(iid, "verifying")
iv2 = store.get_interview(iid)
check("Update interview status", iv2["status"] == "verifying")

# Add event
eid = store.add_event(iid, "system", "Test event", '{"key": "value"}')
check("Add event", eid is not None)

events = store.get_events(iid)
check("Get events", len(events) >= 1 and events[0]["message"] == "Test event")

# Add transcript
tid = store.add_transcript(iid, "candidate", "Hello, my name is Jane", 2.5, 0)
check("Add transcript", tid is not None)

transcript = store.get_transcript(iid)
check("Get transcript", len(transcript) >= 1)

# Add question
qid = store.add_question(iid, 0, "Tell me about yourself", "HR", "Easy")
check("Add question", qid is not None)

questions = store.get_questions(iid)
check("Get questions", len(questions) >= 1)

# Add note
nid = store.add_note(iid, "Candidate was articulate", 0, "manual")
check("Add note", nid is not None)

notes = store.get_notes(iid)
check("Get notes", len(notes) >= 1)

# Save report
rid = store.save_report(iid, {"test": "report"})
check("Save report", rid is not None)

report = store.get_report(iid)
check("Get report", report is not None and report["report"]["test"] == "report")

# List
all_interviews = store.list_interviews()
check("List interviews", len(all_interviews) >= 1)

count = store.get_interview_count()
check("Count interviews", count >= 1)

# Idempotent: calling _ensure_tables again should not fail
store._ensure_tables()
check("Idempotent table creation", True)

# ── 3. Session state-machine transitions ──
print("\n[3] Testing InterviewSession state machine...")
from intent_platform.core.interview.session import InterviewSession
from intent_platform.core.interview.models import InterviewState, InterviewSetup

session = InterviewSession()
setup = InterviewSetup(
    title="Session Test",
    candidate_name="Bob",
    job_role="Engineer",
)
sid = session.initialize(setup)
check("Session initialize", sid is not None)
check("Session state is SETUP", session.state == InterviewState.SETUP)

ok = session.transition_to(InterviewState.VERIFYING)
check("SETUP -> VERIFYING", ok and session.state == InterviewState.VERIFYING)

# Invalid: VERIFYING -> ENDED (should fail)
bad = session.transition_to(InterviewState.ENDED)
check("VERIFYING -> ENDED (invalid)", not bad)

ok = session.transition_to(InterviewState.LIVE)
check("VERIFYING -> LIVE", ok and session.state == InterviewState.LIVE)

ok = session.transition_to(InterviewState.ENDED)
check("LIVE -> ENDED", ok and session.state == InterviewState.ENDED)

ok = session.transition_to(InterviewState.REPORTED)
check("ENDED -> REPORTED", ok and session.state == InterviewState.REPORTED)

# ── 4. Observation engine with synthetic inputs ──
print("\n[4] Testing ObservationEngine with synthetic inputs...")
from intent_platform.core.interview.observation_engine import ObservationEngine
from intent_platform.core.interview.config import InterviewConfig

cfg = InterviewConfig(
    multi_face_duration_s=0.1,
    no_face_duration_s=0.1,
    gaze_away_threshold_s=0.1,
    observation_cooldown_s=0.05,
    app_switch_window_s=120,
    app_switch_max_count=3,
    tab_switch_window_s=120,
    tab_switch_max_count=3,
    paste_char_threshold=10,
    paste_line_threshold=2,
)
obs_engine = ObservationEngine(cfg)
fired_events = []
obs_engine.on_observation = lambda o: fired_events.append(o.event_type)

# Multiple faces
obs_engine.update_face_count(2)
time.sleep(0.15)
obs_engine.update_face_count(2)
check("Multi-face observation fires", "multi_face" in fired_events, f"fired: {fired_events}")

# No face
fired_events.clear()
obs_engine.update_face_count(0)
time.sleep(0.15)
obs_engine.update_face_count(0)
check("No-face observation fires", "no_face" in fired_events)

# Face returned
fired_events.clear()
time.sleep(0.1)
obs_engine.update_face_count(1)
check("Face returned observation fires", "face_returned" in fired_events)

# Gaze away
fired_events.clear()
obs_engine.update_gaze(False)
time.sleep(0.15)
obs_engine.update_gaze(False)
check("Gaze away observation fires", "gaze_away" in fired_events)

# App switching
fired_events.clear()
time.sleep(0.1)
for i in range(4):
    obs_engine.record_app_switch("editor")
check("App switching observation fires", "app_switch" in fired_events)

# Tab switching
fired_events.clear()
time.sleep(0.1)
for i in range(4):
    obs_engine.record_tab_switch()
check("Tab switching observation fires", "tab_switch" in fired_events)

# Paste detection
fired_events.clear()
time.sleep(0.1)
obs_engine.record_paste("x" * 50 + "\n" * 5)
check("Paste observation fires", "paste" in fired_events)

# Neutral language check on observations
all_obs_msgs = [o.message for o in obs_engine.observations]
banned_words = ["cheat", "cheating", "cheater", "fraud", "dishonest",
                "malpractice", "suspicious", "caught", "violation", "guilty"]
banned_found_in_obs = any(
    any(bw in msg.lower() for bw in banned_words)
    for msg in all_obs_msgs
)
check("Observation messages use neutral language", not banned_found_in_obs)

# ── 5. Voice analysis on canned utterances ──
print("\n[5] Testing VoiceAnalyzer...")
from intent_platform.core.interview.voice_analysis import VoiceAnalyzer

va = VoiceAnalyzer(InterviewConfig())

# Normal speech: 20 words in 10 seconds = 120 wpm
metrics = va.analyze_utterance(
    "I have experience in Python development and I have worked on several large-scale distributed systems using microservices architecture and cloud platforms",
    10.0
)
check("WPM calculation", 100 <= metrics["wpm"] <= 200, f"wpm={metrics['wpm']}")
check("Filler count is 0 for clean speech", metrics["filler_count"] == 0)

# Speech with fillers
metrics2 = va.analyze_utterance(
    "um basically like I think maybe sort of I mean you know it was kind of like a project",
    5.0
)
check("Filler detection", metrics2["filler_count"] >= 5, f"fillers={metrics2['filler_count']}")
check("Filler rate > 0", metrics2["filler_rate"] > 0)

# Overall metrics
overall = va.get_overall_metrics()
check("Overall metrics computed", overall["utterance_count"] == 2)

# ── 6. Voice router ──
print("\n[6] Testing VoiceRouter...")
from intent_platform.core.interview.voice_router import VoiceRouter

router = VoiceRouter()
action_log = []

def log_action(cmd):
    def _handler():
        action_log.append(cmd)
        return f"Done: {cmd}"
    return _handler

commands = [
    "next question", "previous question", "open candidate resume",
    "zoom into screen", "zoom out", "take notes", "mark this answer",
    "generate summary", "show interview report",
    "switch to candidate camera", "switch to screen share",
    "end interview", "confirm"
]
for cmd in commands:
    router.register_action(cmd, log_action(cmd))

# Test all 13 commands
test_phrases = [
    ("next question", "next question"),
    ("go to previous question", "previous question"),
    ("open resume", "open candidate resume"),
    ("zoom in", "zoom into screen"),
    ("zoom out", "zoom out"),
    ("take a note", "take notes"),
    ("mark answer", "mark this answer"),
    ("summarize", "generate summary"),
    ("show report", "show interview report"),
    ("show camera", "switch to candidate camera"),
    ("screen share", "switch to screen share"),
    ("end interview", "end interview"),
    ("confirm", "confirm"),
]

router_pass = True
for phrase, expected in test_phrases:
    result = router.handle(phrase)
    if result is None or expected not in action_log:
        router_pass = False
        print(f"    FAIL: '{phrase}' → expected '{expected}', got '{result}', log={action_log[-3:]}")
    action_log.clear()

check("All 13 voice commands resolve correctly", router_pass)

# Non-wake utterances (random speech) should return None
result = router.handle("the weather is nice today")
check("Non-command speech returns None", result is None)

# ── 7. Banned-word scan of source files ──
print("\n[7] Scanning new source files for banned words...")
scan_files = glob.glob("core/interview/*.py")
banned_in_source = False
for f in scan_files:
    if "scratch_test" in f:
        continue
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read().lower()
        for bw in banned_words:
            if bw in content:
                print(f"    BANNED: '{bw}' in {f}")
                banned_in_source = True
check("No banned words in new source files", not banned_in_source)

# ── 8. Report fallback produces all sections ──
print("\n[8] Testing ReportGenerator fallback...")
from intent_platform.core.interview.report_generator import ReportGenerator

rg = ReportGenerator()
report = rg.generate(
    interview_id=iid,
    voice_metrics=overall,
    observations=[{"event_type": "gaze_away", "message": "Extended gaze away from screen (5 s)", "reviewed": False}],
    questions=[{"text": "Tell me about yourself", "category": "HR", "idx": 0, "asked_at": time.time()}],
    notes=[{"question_index": 0, "content": "Good answer", "note_type": "manual", "auto_analysis": ""}],
    transcript=[{"question_index": 0, "text": "I am a developer", "speaker": "candidate"}],
    setup={"candidate_name": "Jane", "candidate_email": "jane@test.com", "job_role": "Engineer",
           "interview_type": "Technical", "difficulty": "Medium", "duration_minutes": 30},
    actual_duration_s=1800.0,
)

required_sections = [
    "candidate_information", "interview_duration", "questions_asked",
    "communication_summary", "technical_performance", "problem_solving",
    "confidence_estimate", "observations", "strengths", "improvement_areas",
    "overall_recommendation", "limitations", "final_note",
]
missing = [s for s in required_sections if s not in report]
check("Report has all required sections", len(missing) == 0, f"missing: {missing}")

check("Report final_note says 'Final decision rests with the interviewer'",
      "Final decision rests with the interviewer" in report.get("final_note", ""))

# Check report for banned words
report_str = json.dumps(report).lower()
report_banned = any(bw in report_str for bw in banned_words)
check("Report contains no banned words", not report_banned)

# ── 9. Engine hooks regression ──
print("\n[9] Testing engine hooks regression...")
from intent_platform.core.engine import IntentEngine

engine = IntentEngine()
check("Engine has frame_taps (empty list)", isinstance(engine.frame_taps, list) and len(engine.frame_taps) == 0)
check("Engine has gesture_interceptor (None)", engine.gesture_interceptor is None)

# ── 10. Voice engine interview mode regression ──
print("\n[10] Testing VoiceEngine interview mode regression...")
from intent_platform.core.voice.voice_engine import VoiceEngine

ve = VoiceEngine()
check("VoiceEngine.interview_mode default False", ve.interview_mode is False)
check("VoiceEngine has set_interview_hooks", hasattr(ve, 'set_interview_hooks'))

# Test that _process_transcript still works in non-interview mode
# (We can't fully test without a mic, but we can check the method exists and doesn't crash with a mock)
try:
    # This will try to classify and may fail gracefully, but should not crash
    ve._process_transcript("test utterance", meta={"duration": 1.0})
    check("VoiceEngine._process_transcript backward compatible", True)
except Exception as e:
    check("VoiceEngine._process_transcript backward compatible", False, str(e))

# ── 11. Gesture router ──
print("\n[11] Testing GestureRouter...")
from intent_platform.core.interview.gesture_router import GestureRouter

gr = GestureRouter()
gr.active = True
action_results = []
gr.on_next_question = lambda: action_results.append("next")
gr.on_previous_question = lambda: action_results.append("prev")
gr.on_zoom_in = lambda: action_results.append("zin")
gr.on_zoom_out = lambda: action_results.append("zout")
gr.on_timeline_log = lambda g, a: None

r = gr.intercept("swipe_right", "default")
check("Swipe right -> Next Question", r == "Next Question" and "next" in action_results)

action_results.clear()
r = gr.intercept("swipe_left", "default")
check("Swipe left -> Previous Question", r == "Previous Question" and "prev" in action_results)

r = gr.intercept("fist", "default")
check("Fist -> None (pass through for screenshot)", r is None)

# Inactive router
gr.active = False
r = gr.intercept("swipe_right", "default")
check("Inactive router returns None", r is None)


# ── 12. Phase 4 Novelty Features ──
print("\n[12] Testing Phase 4 Novelty features...")
from intent_platform.core.interview.novelty import (
    EvidenceLinker, PersonalBaselineTracker, PasteProbeGenerator,
    CompetencyCoverageMap, QuestionFairnessLinter, TransparencyReceiptExporter
)

# EvidenceLinker
eref = EvidenceLinker.create_evidence_ref("evt_1", 135.0, "Candidate explained threading model")
check("EvidenceLinker creates timestamp chip", eref["chip_label"] == "▶ 02:15")

# PersonalBaselineTracker
pbt = PersonalBaselineTracker(calibration_duration_s=0.1)
time.sleep(0.15)
pbt.add_sample(0.95, 140.0)
check("PersonalBaselineTracker calibrates", pbt.is_calibrating is False)

# PasteProbeGenerator
probes = PasteProbeGenerator.generate_probes("def solution():\n    return 42")
check("PasteProbeGenerator produces 3 probe questions", len(probes) == 3)

# CompetencyCoverageMap
ccm = CompetencyCoverageMap()
ccm.tag_question("Explain binary search tree algorithms", "Technical")
check("CompetencyCoverageMap tags DSA", ccm.get_coverage_percentage() > 0)

# QuestionFairnessLinter
fairness_warn = QuestionFairnessLinter.lint_question("How old are you and what is your family status?")
check("QuestionFairnessLinter flags protected attributes", fairness_warn is not None and "Fairness Notice" in fairness_warn)

# TransparencyReceiptExporter
receipt = TransparencyReceiptExporter.generate_receipt("Alice", time.time(), [{"event_type": "gaze_away"}])
check("TransparencyReceiptExporter creates summary receipt", receipt["candidate_name"] == "Alice")


# ── SUMMARY ──
print("\n" + "=" * 60)
total = PASS_COUNT + FAIL_COUNT
if FAIL_COUNT == 0:
    print(f"  ALL {total} TESTS PASSED! ✓")
else:
    print(f"  {PASS_COUNT}/{total} PASSED, {FAIL_COUNT} FAILED")
print("=" * 60)
