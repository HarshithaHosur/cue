# ============================================================
#  INTERVIEW MODULE — Controller / Service Layer
#  Single orchestrator for the entire interview lifecycle:
#  Zoom Meeting SDK, RTMS, AI Copilot, Resume & Rubric Intelligence.
# ============================================================

import time
import logging
import threading
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal, QTimer

from intent_platform.core.interview.config import InterviewConfig
from intent_platform.core.interview.models import (
    InterviewState, InterviewSetup, ObservationRecord, TranscriptEntry
)
from intent_platform.core.interview.session import InterviewSession
from intent_platform.core.interview.store import interview_store
from intent_platform.core.interview.observation_engine import ObservationEngine
from intent_platform.core.interview.voice_analysis import VoiceAnalyzer
from intent_platform.core.interview.voice_router import VoiceRouter
from intent_platform.core.interview.gesture_router import GestureRouter
from intent_platform.core.interview.report_generator import ReportGenerator
from intent_platform.core.interview.novelty import (
    PersonalBaselineTracker, PasteProbeGenerator, EvidenceLinker
)
from intent_platform.core.interview.zoom.zoom_auth import ZoomAuthManager
from intent_platform.core.interview.zoom.zoom_meeting_adapter import (
    ZoomMeetingAdapter, ZoomConnectionState
)
from intent_platform.core.interview.zoom.zoom_rtms_service import ZoomRTMSService, RTMSState
from intent_platform.core.interview.resume_parser import ResumeParser, ResumeClaimTracker
from intent_platform.core.interview.rubric_engine import RubricEngine
from intent_platform.core.interview.copilot_engine import InterviewCopilotEngine, CopilotSuggestion

logger = logging.getLogger(__name__)


# ── Pre-flight Results ──

@dataclass
class ServiceCheck:
    name: str
    available: bool
    message: str
    degraded: bool = False   # True = can continue without it


@dataclass
class PreFlightResult:
    checks: List[ServiceCheck] = field(default_factory=list)
    can_start: bool = True

    @property
    def all_passed(self) -> bool:
        return all(c.available for c in self.checks)

    def add(self, name: str, available: bool, message: str, degraded: bool = True):
        self.checks.append(ServiceCheck(name, available, message, degraded))
        if not available and not degraded:
            self.can_start = False


# ── Live Metrics State ──

class InterviewMetricsState(QObject):
    """Observable runtime state for all live interview metrics.
    No fake defaults. Every field starts with genuine initial state.
    """

    metrics_updated = Signal()
    talk_time_updated = Signal()
    transcript_entry = Signal(str, str, float)  # speaker, text, timestamp
    observation_fired = Signal(object)        # ObservationRecord
    question_changed = Signal(int, str)       # index, text
    fairness_alert = Signal(str, str, float)  # question, warning, timestamp
    coaching_suggestion = Signal(str)         # suggestion text
    service_status_changed = Signal(str, str) # service_name, status
    paste_probes_generated = Signal(list)     # list of probe dicts
    copilot_suggestion_ready = Signal(object) # CopilotSuggestion
    visual_explain_ready = Signal(dict)       # dict
    rubric_updated = Signal(dict)             # rubric summary dict
    resume_claims_updated = Signal(dict)      # resume claims summary dict

    def __init__(self, parent=None):
        super().__init__(parent)

        # Talk-time tracking
        self.interviewer_words: int = 0
        self.candidate_words: int = 0
        self.interviewer_talk_s: float = 0.0
        self.candidate_talk_s: float = 0.0
        self.total_talk_s: float = 0.0
        self.current_wpm: Optional[float] = None
        self.average_wpm: Optional[float] = None
        self.filler_count: int = 0

        # Interruptions
        self.interruptions: List[Dict] = []
        self._last_speaker: Optional[str] = None
        self._last_speaker_end: Optional[float] = None

        # Observations
        self.observations: List[ObservationRecord] = []

        # Questions
        self.current_question_index: int = -1
        self.questions: List[Dict] = []

        # Rubric & Resume state summaries
        self.rubric_summary: Dict[str, Any] = {}
        self.resume_summary: Dict[str, Any] = {}

        # Baseline
        self.baseline_status: str = "not_started"

        # Service statuses
        self.services: Dict[str, str] = {
            "zoom_adapter": "unknown",
            "zoom_rtms": "unknown",
            "camera": "unknown",
            "microphone": "unknown",
            "speech_recognition": "unknown",
            "screen_capture": "unknown",
            "ai_copilot": "unknown",
            "database": "unknown",
            "session": "unknown",
        }

    @property
    def interviewer_talk_pct(self) -> Optional[float]:
        if self.total_talk_s <= 0:
            return None
        return (self.interviewer_talk_s / self.total_talk_s) * 100.0

    @property
    def candidate_talk_pct(self) -> Optional[float]:
        if self.total_talk_s <= 0:
            return None
        return (self.candidate_talk_s / self.total_talk_s) * 100.0

    def add_speech(self, speaker: str, text: str, duration: float, wpm: float, ts: float):
        """Record speech segment, measure talk-time, and detect interruptions."""
        words = len(text.split())
        if speaker == "interviewer":
            self.interviewer_words += words
            self.interviewer_talk_s += duration
        elif speaker == "candidate":
            self.candidate_words += words
            self.candidate_talk_s += duration

        self.total_talk_s = self.interviewer_talk_s + self.candidate_talk_s
        self.current_wpm = wpm if wpm > 0 else self.current_wpm

        # Interruption detection: speaker overlap within 0.5s of previous speaker
        if (self._last_speaker is not None
                and self._last_speaker != speaker
                and self._last_speaker_end is not None
                and (ts - self._last_speaker_end) < 0.5):
            self.interruptions.append({
                "timestamp": ts,
                "interrupter": speaker,
                "interrupted": self._last_speaker,
                "transcript_snippet": text[:80],
            })

        self._last_speaker = speaker
        self._last_speaker_end = ts + max(duration, 0.5)

        self.talk_time_updated.emit()
        self.transcript_entry.emit(speaker, text, ts)

    def set_service_status(self, name: str, status: str):
        self.services[name] = status
        self.service_status_changed.emit(name, status)


# ── Interview Controller ──

class InterviewController(QObject):
    """Central orchestrator for AI Interviewer Coach lifecycle."""

    state_changed = Signal(str)
    preflight_complete = Signal(object)
    interview_started = Signal(str)
    interview_ended = Signal()
    report_ready = Signal(dict)
    error_occurred = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.config = InterviewConfig(demo_mode=False)
        self.session: Optional[InterviewSession] = None
        self.metrics = InterviewMetricsState()

        # Zoom Adapters
        self.zoom_auth = ZoomAuthManager()
        self.zoom_adapter = ZoomMeetingAdapter(auth_manager=self.zoom_auth)
        self.zoom_rtms = ZoomRTMSService(auth_manager=self.zoom_auth)

        # Intelligence Engines
        self.resume_tracker: Optional[ResumeClaimTracker] = None
        self.rubric_engine: Optional[RubricEngine] = None
        self.copilot_engine = InterviewCopilotEngine()
        self.report_generator = ReportGenerator()

        # Other services
        self.obs_engine: Optional[ObservationEngine] = None
        self.voice_analyzer: Optional[VoiceAnalyzer] = None
        self.voice_router: Optional[VoiceRouter] = None
        self.gesture_router: Optional[GestureRouter] = None
        self.baseline_tracker: Optional[PersonalBaselineTracker] = None

        # State
        self._engine = None
        self._interview_id: Optional[str] = None
        self._questions: List[Dict] = []
        self._current_q_idx: int = -1
        self._is_live: bool = False
        self._timer: Optional[QTimer] = None
        self._visual_selections: List[Dict[str, Any]] = []

        # Wire Copilot and RTMS signals
        self._wire_copilot_signals()

    def _wire_copilot_signals(self):
        self.copilot_engine.suggestion_ready.connect(self._on_copilot_suggestion)
        self.copilot_engine.risk_alert_ready.connect(self._on_risk_alert)
        self.copilot_engine.visual_explain_ready.connect(self._on_visual_explain_result)
        self.zoom_rtms.transcript_segment.connect(self._on_rtms_transcript_segment)

    @property
    def interview_id(self) -> Optional[str]:
        return self._interview_id

    @property
    def state(self) -> InterviewState:
        return self.session.state if self.session else InterviewState.SETUP

    @property
    def is_live(self) -> bool:
        return self._is_live

    # ── 1. Validation & Meeting URL Parsing ──

    def validate_setup(self, setup: Any) -> List[str]:
        """Validates interview setup parameters."""
        if isinstance(setup, dict):
            setup = InterviewSetup(
                title=setup.get('title', ''),
                candidate_name=setup.get('candidate_name', setup.get('candidate', '')),
                candidate_email=setup.get('candidate_email', ''),
                job_role=setup.get('job_role', setup.get('target_role', setup.get('role', ''))),
                interview_type=setup.get('interview_type', setup.get('type', 'Technical')),
                duration_minutes=int(setup.get('duration_minutes', setup.get('duration', 45))),
                difficulty=setup.get('difficulty', 'Medium'),
                meeting_platform=setup.get('meeting_platform', 'Zoom'),
                meeting_link=setup.get('meeting_link', ''),
                notes=setup.get('notes', ''),
                resume_path=setup.get('resume_path', '')
            )
        errors = []
        if not getattr(setup, 'title', '').strip():
            errors.append("Interview title is required.")
        if not getattr(setup, 'candidate_name', '').strip():
            errors.append("Candidate name is required.")
        if not getattr(setup, 'job_role', '').strip():
            errors.append("Job role is required.")
        if getattr(setup, 'duration_minutes', 0) < 5:
            errors.append("Duration must be at least 5 minutes.")
        return errors

    def parse_meeting_url(self, url: str):
        """Parses and validates a Zoom meeting link format."""
        return self.zoom_adapter.parse_meeting_link(url)

    # ── 2. Pre-flight Checks ──

    def run_preflight(self, engine=None, setup: Optional[InterviewSetup] = None) -> PreFlightResult:
        """Executes real preflight verification across local devices, Zoom, and AI services."""
        result = PreFlightResult()
        self._engine = engine

        # Database
        try:
            interview_store.get_interview_count()
            result.add("Database", True, "SQLite database storage ready")
            self.metrics.set_service_status("database", "ready")
        except Exception as e:
            result.add("Database", False, f"Database error: {e}", degraded=False)
            self.metrics.set_service_status("database", "error")

        # Session
        result.add("Session", True, "Interview session manager ready")
        self.metrics.set_service_status("session", "ready")

        # Zoom Meeting SDK & Auth
        auth_status = self.zoom_auth.check_authorization_status()
        if auth_status["sdk_configured"]:
            result.add("Zoom Meeting SDK", True, "Zoom SDK credentials verified")
            self.metrics.set_service_status("zoom_adapter", "ready")
        else:
            result.add("Zoom Meeting SDK", True, "SDK credentials not set in .env — Companion launch mode ready", degraded=True)
            self.metrics.set_service_status("zoom_adapter", "companion_mode")

        # Zoom RTMS
        if auth_status["rtms_configured"]:
            result.add("Zoom RTMS", True, "Zoom RTMS real-time stream ready")
            self.metrics.set_service_status("zoom_rtms", "ready")
        else:
            result.add("Zoom RTMS", True, "RTMS credentials not set — Local audio/transcript tap active", degraded=True)
            self.metrics.set_service_status("zoom_rtms", "companion_mode")

        # Camera
        if engine and hasattr(engine, 'is_running') and engine.is_running:
            result.add("Camera", True, "Camera active")
            self.metrics.set_service_status("camera", "ready")
        else:
            result.add("Camera", True, "Camera feed standby", degraded=True)
            self.metrics.set_service_status("camera", "standby")

        # Microphone
        try:
            import speech_recognition as sr
            mic = sr.Microphone()
            result.add("Microphone", True, "Local microphone available")
            self.metrics.set_service_status("microphone", "ready")
        except Exception as e:
            result.add("Microphone", True, f"Microphone standby: {e}", degraded=True)
            self.metrics.set_service_status("microphone", "standby")

        # Speech Recognition
        if engine and hasattr(engine, 'voice_engine') and engine.voice_engine:
            result.add("Speech Recognition", True, "Voice engine active")
            self.metrics.set_service_status("speech_recognition", "ready")
        else:
            result.add("Speech Recognition", True, "Voice engine standby", degraded=True)
            self.metrics.set_service_status("speech_recognition", "standby")

        # AI Copilot (Gemini / Local Heuristics)
        try:
            from intent_platform.core.ai.gemini_service import GENAI_AVAILABLE
            from intent_platform.config.settings import GEMINI_API_KEY
            if GENAI_AVAILABLE and GEMINI_API_KEY:
                result.add("AI Copilot", True, "Gemini AI Engine active")
                self.metrics.set_service_status("ai_copilot", "ready")
            else:
                result.add("AI Copilot", True, "Contextual rule engine active (Gemini optional)", degraded=True)
                self.metrics.set_service_status("ai_copilot", "heuristic_fallback")
        except Exception:
            result.add("AI Copilot", True, "Contextual rule engine active", degraded=True)
            self.metrics.set_service_status("ai_copilot", "fallback")

        # Candidate / Screen Share (Truthful waiting state)
        result.add("Candidate Screen Share", True, "Standby — waiting for candidate to share screen", degraded=True)
        self.metrics.set_service_status("screen_capture", "waiting_for_candidate")

        self.preflight_complete.emit(result)
        return result

    # ── 3. Start Interview (Single Session Guaranteed) ──

    def start_interview(self, setup: Any, engine=None) -> Optional[str]:
        """Creates exactly ONE interview record, initializes all engines, and starts live assistance."""
        try:
            # Idempotency guard: do not create duplicate session if already live
            if self._is_live and self._interview_id:
                logger.warning(f"Interview {self._interview_id} is already live.")
                return self._interview_id

            self._engine = engine

            if isinstance(setup, dict):
                setup = InterviewSetup(
                    title=setup.get('title', 'Interview Session'),
                    candidate_name=setup.get('candidate_name', setup.get('candidate', 'Candidate')),
                    candidate_email=setup.get('candidate_email', ''),
                    job_role=setup.get('job_role', setup.get('target_role', setup.get('role', 'Software Engineer'))),
                    interview_type=setup.get('interview_type', setup.get('type', 'Technical')),
                    duration_minutes=int(setup.get('duration_minutes', setup.get('duration', 45))),
                    difficulty=setup.get('difficulty', 'Medium'),
                    meeting_platform=setup.get('meeting_platform', 'Zoom'),
                    meeting_link=setup.get('meeting_link', ''),
                    notes=setup.get('notes', ''),
                    resume_path=setup.get('resume_path', ''),
                    rubric_config=setup.get('rubric_config', [])
                )

            # Validate
            errors = self.validate_setup(setup)
            if errors:
                self.error_occurred.emit("Validation Error", "\n".join(errors))
                return None

            # Create session and persist single record
            self.session = InterviewSession()
            self._interview_id = self.session.initialize(setup)
            logger.info(f"[InterviewController] Interview started: ID={self._interview_id}")

            # 1. Initialize Resume Tracker
            if setup.resume_path:
                parsed_res = ResumeParser.parse_file(setup.resume_path)
                if parsed_res.get("success"):
                    self.resume_tracker = ResumeClaimTracker(parsed_res.get("claims", []))
                    interview_store.save_resume_claims(self._interview_id, parsed_res.get("claims", []))
                    self.metrics.resume_summary = self.resume_tracker.get_summary()
                    self.metrics.resume_claims_updated.emit(self.metrics.resume_summary)
            if not self.resume_tracker:
                self.resume_tracker = ResumeClaimTracker()
                self.metrics.resume_summary = self.resume_tracker.get_summary()

            # 2. Initialize Rubric Engine
            self.rubric_engine = RubricEngine(
                custom_criteria=setup.rubric_config if setup.rubric_config else None,
                interview_type=setup.interview_type
            )
            self.metrics.rubric_summary = self.rubric_engine.get_summary()
            self.metrics.rubric_updated.emit(self.metrics.rubric_summary)

            # 3. Initialize Observation & Voice Analyzers
            self.obs_engine = ObservationEngine(self.config)
            self.obs_engine.on_observation = self._on_observation
            self.voice_analyzer = VoiceAnalyzer(self.config)

            # 4. Initialize Routers & Baselines
            self.voice_router = VoiceRouter()
            self._register_voice_commands()

            self.gesture_router = GestureRouter()
            self.gesture_router.active = True
            self.gesture_router.on_next_question = lambda: self.navigate_question(1)
            self.gesture_router.on_previous_question = lambda: self.navigate_question(-1)

            self.baseline_tracker = PersonalBaselineTracker(
                calibration_duration_s=self.config.baseline_duration_s
            )
            self.metrics.baseline_status = "calibrating"

            # 5. Initialize Zoom Meeting & RTMS
            if setup.meeting_link:
                self.zoom_adapter.prepare_meeting(setup.meeting_link)
            self.zoom_rtms.initialize_session(self._interview_id)
            self.zoom_rtms.start_stream()

            # 6. Lifecycle transition to LIVE
            self.session.transition_to(InterviewState.LIVE)
            self._is_live = True
            self.state_changed.emit(InterviewState.LIVE.value)

            # 7. Connect Engine Hooks
            self._connect_engine_hooks()

            # 8. Start timer
            self._timer = QTimer()
            self._timer.setInterval(1000)
            self._timer.timeout.connect(self._on_timer_tick)
            self._timer.start()

            self.interview_started.emit(self._interview_id)
            self.session.emit_event("system", "Interview session active and live.")

            return self._interview_id

        except Exception as e:
            logger.exception(f"[InterviewController] Failed to start interview: {e}")
            self.error_occurred.emit("Start Failed", str(e))
            self._cleanup_partial()
            return None

    # ── 4. Zoom Meeting Launching ──

    def launch_zoom_meeting(self) -> bool:
        """Launches Zoom meeting either embedded or via companion browser."""
        candidate_name = self.session.setup.candidate_name if self.session and self.session.setup else "Candidate"
        return self.zoom_adapter.launch_or_embed_meeting(display_name=f"Interviewer (with {candidate_name})")

    # ── 5. Engine Hooks & Concurrency ──

    def _connect_engine_hooks(self):
        if not self._engine:
            return
        self._engine.add_frame_tap(self._on_frame_tap)
        self._engine.gesture_interceptor = self.gesture_router.intercept
        if hasattr(self._engine, 'voice_engine') and self._engine.voice_engine:
            self._engine.voice_engine.set_interview_hooks(
                self.voice_router, self._on_transcript_tap
            )
            self._engine.voice_engine.interview_mode = True

    def _disconnect_engine_hooks(self):
        if not self._engine:
            return
        try:
            self._engine.remove_frame_tap(self._on_frame_tap)
        except (ValueError, AttributeError):
            pass
        self._engine.gesture_interceptor = None
        if hasattr(self._engine, 'voice_engine') and self._engine.voice_engine:
            self._engine.voice_engine.set_interview_hooks(None, None)
            self._engine.voice_engine.interview_mode = False

    def _on_frame_tap(self, frame):
        pass

    # ── 6. Transcript & Intelligence Processing ──

    def record_transcript(self, speaker: str, text: str, duration: float = 0.0, ts: Optional[float] = None):
        """Programmatic entry point for transcript segments."""
        if ts is None:
            ts = time.time()
        self.zoom_rtms.inject_transcript_segment(speaker, text, duration, ts)

    def _on_rtms_transcript_segment(self, speaker: str, text: str, duration: float, ts: float):
        """Handles normalized transcript segments from Zoom RTMS or local audio tap."""
        if not self._is_live or not self.session:
            return

        text = text.strip()
        if not text:
            return

        # 1. Voice metrics & WPM
        wpm = 0
        if self.voice_analyzer and text:
            metrics = self.voice_analyzer.analyze_utterance(text, max(duration, 0.1))
            wpm = metrics.get("wpm", 0)

        # 2. Update Live Metrics
        self.metrics.add_speech(speaker, text, duration, wpm, ts)

        # 3. Persist Transcript
        interview_store.add_transcript(
            self._interview_id, speaker, text, duration,
            self._current_q_idx, 1.0, ts
        )

        # 4. Intelligence Processing based on speaker
        if speaker == "interviewer":
            # Check for sensitive/risky questions
            self.copilot_engine.analyze_interviewer_question(text, ts)
        elif speaker == "candidate":
            # Check resume claims coverage
            if self.resume_tracker:
                updated_claims = self.resume_tracker.evaluate_transcript_segment(speaker, text, ts)
                if updated_claims:
                    self.metrics.resume_summary = self.resume_tracker.get_summary()
                    self.metrics.resume_claims_updated.emit(self.metrics.resume_summary)

            # Check rubric coverage
            if self.rubric_engine:
                updated_rubric = self.rubric_engine.evaluate_transcript(speaker, text, ts)
                if updated_rubric:
                    self.metrics.rubric_summary = self.rubric_engine.get_summary()
                    self.metrics.rubric_updated.emit(self.metrics.rubric_summary)

            # Generate contextual follow-up questions
            recent_trans = interview_store.get_transcript(self._interview_id) if self._interview_id else []
            job_role = self.session.setup.job_role if self.session and self.session.setup else "Software Engineer"
            self.copilot_engine.process_candidate_answer(
                text, recent_trans, self.resume_tracker, self.rubric_engine, job_role, ts
            )

        # 5. Baseline calibration update
        if self.baseline_tracker and self.baseline_tracker.is_calibrating:
            self.baseline_tracker.add_sample(0.9, wpm)
            if not self.baseline_tracker.is_calibrating:
                self.metrics.baseline_status = "established"
                self.session.emit_event("system", "Personal baseline calibrated from candidate speech.")

    def _on_transcript_tap(self, entry: dict):
        """Called by local VoiceEngine when in companion mode."""
        raw_text = entry.get("text", "")
        duration = entry.get("duration", 0.0)
        ts = entry.get("ts", time.time())
        has_wake = entry.get("has_wake", False)
        speaker = "interviewer" if has_wake else "candidate"
        self._on_rtms_transcript_segment(speaker, raw_text, duration, ts)

    def _on_copilot_suggestion(self, sug: CopilotSuggestion):
        self.metrics.copilot_suggestion_ready.emit(sug)
        if self.session:
            self.session.emit_event("copilot", f"[{sug.suggestion_type}] {sug.title}: {sug.content}")

    def _on_risk_alert(self, category: str, explanation: str, ts: float):
        self.metrics.fairness_alert.emit(category, explanation, ts)
        if self.session:
            self.session.emit_event("fairness", explanation)

    def _on_visual_explain_result(self, res: dict):
        self._visual_selections.append(res)
        if self._interview_id:
            interview_store.add_visual_selection(
                self._interview_id,
                res.get("selected_text", ""),
                res.get("explanation", ""),
                res.get("complexity", ""),
                res.get("follow_up", ""),
                res.get("timestamp")
            )
        self.metrics.visual_explain_ready.emit(res)
        if self.session:
            self.session.emit_event("visual_explain", res.get("explanation", ""))

    def request_visual_explanation(self, context_text: str = "", source: str = "screen_selection"):
        """Interviewer triggered 'Explain This' via Voice, Gesture, or Button."""
        self.copilot_engine.explain_visual_selection(context_text, source=source)

    def _on_observation(self, obs: ObservationRecord):
        self.metrics.observations.append(obs)
        self.metrics.observation_fired.emit(obs)
        if self.session:
            self.session.emit_event(
                "observation", obs.message,
                f'{{"event_type": "{obs.event_type}", "count": {obs.count}}}'
            )

    def _on_timer_tick(self):
        if self.session:
            remaining = self.session.get_remaining_seconds()
            self.session.timer_tick.emit(remaining)

    # ── 7. Question Navigation & Notes ──

    def navigate_question(self, delta: int):
        if not self._questions:
            return
        new_idx = max(0, min(len(self._questions) - 1, self._current_q_idx + delta))
        if new_idx != self._current_q_idx:
            self._current_q_idx = new_idx
            q = self._questions[self._current_q_idx]
            self.metrics.current_question_index = self._current_q_idx
            self.metrics.question_changed.emit(self._current_q_idx, q.get("text", ""))

            if q.get("question_id"):
                interview_store.mark_question_asked(q["question_id"])
            if self.session:
                self.session.set_current_question(self._current_q_idx, q.get("text", ""))

    def add_question(self, text: str, category: str = "Technical", difficulty: str = "Medium"):
        if not self._interview_id:
            return
        idx = len(self._questions)
        qid = interview_store.add_question(
            self._interview_id, idx, text, category, difficulty
        )
        self._questions.append({
            "question_id": qid, "text": text, "category": category,
            "difficulty": difficulty, "idx": idx, "asked_at": None,
        })
        if self._current_q_idx < 0:
            self.navigate_question(1)

    def add_note(self, content: str, note_type: str = "manual"):
        if not self._interview_id:
            return
        interview_store.add_note(
            self._interview_id, content,
            self._current_q_idx, note_type
        )
        if self.session:
            self.session.emit_event("note", content)

    # ── 8. End Interview ──

    def end_interview(self):
        """Clean shutdown: stops RTMS, disconnects meeting, flushes events, generates report."""
        if not self._is_live:
            return

        logger.info(f"[InterviewController] Ending interview: {self._interview_id}")
        self._is_live = False

        if self._timer:
            self._timer.stop()
            self._timer = None

        # Stop streams and disconnect
        self.zoom_rtms.stop_stream()
        self.zoom_adapter.disconnect_meeting()
        self._disconnect_engine_hooks()

        if self.gesture_router:
            self.gesture_router.active = False

        if self.session:
            self.session.transition_to(InterviewState.COMPLETED)
            self.state_changed.emit(InterviewState.COMPLETED.value)
            self.session.emit_event("system", "Interview completed.")

        self.interview_ended.emit()
        self._generate_report_async()
        return self._build_report()

    finish_interview = end_interview

    def _generate_report_async(self):
        def _gen():
            try:
                report = self._build_report()
                self.report_ready.emit(report)
            except Exception as e:
                logger.exception(f"[InterviewController] Report generation failed: {e}")
                self.error_occurred.emit("Report Failed", str(e))

        threading.Thread(target=_gen, daemon=True).start()

    def _build_report(self) -> Dict[str, Any]:
        """Builds evidence-linked report."""
        voice_metrics = {}
        if self.voice_analyzer:
            voice_metrics = self.voice_analyzer.get_overall_metrics()

        voice_metrics["interviewer_words"] = self.metrics.interviewer_words
        voice_metrics["candidate_words"] = self.metrics.candidate_words
        voice_metrics["interviewer_talk_s"] = round(self.metrics.interviewer_talk_s, 1)
        voice_metrics["candidate_talk_s"] = round(self.metrics.candidate_talk_s, 1)
        voice_metrics["interviewer_talk_pct"] = round(self.metrics.interviewer_talk_pct or 0, 1)
        voice_metrics["candidate_talk_pct"] = round(self.metrics.candidate_talk_pct or 0, 1)
        voice_metrics["interruptions"] = self.metrics.interruptions

        observations = [
            {"event_type": o.event_type, "message": o.message,
             "timestamp": o.timestamp, "reviewed": o.reviewed}
            for o in self.metrics.observations
        ]

        questions = interview_store.get_questions(self._interview_id) if self._interview_id else []
        notes = interview_store.get_notes(self._interview_id) if self._interview_id else []
        transcript = interview_store.get_transcript(self._interview_id) if self._interview_id else []

        setup = {}
        if self.session and self.session.setup:
            s = self.session.setup
            setup = {
                "candidate_name": s.candidate_name,
                "candidate_email": s.candidate_email,
                "job_role": s.job_role,
                "interview_type": s.interview_type,
                "difficulty": s.difficulty,
                "duration_minutes": s.duration_minutes,
                "meeting_platform": s.meeting_platform,
                "meeting_link": s.meeting_link,
                "created_at": s.created_at
            }

        actual_duration = self.session.get_actual_duration() if self.session else 0.0

        resume_summary = self.resume_tracker.get_summary() if self.resume_tracker else {}
        rubric_summary = self.rubric_engine.get_summary() if self.rubric_engine else {}

        report = self.report_generator.generate(
            interview_id=self._interview_id or "session_report",
            voice_metrics=voice_metrics,
            observations=observations,
            questions=questions,
            notes=notes,
            transcript=transcript,
            setup=setup,
            actual_duration_s=actual_duration,
            resume_summary=resume_summary,
            rubric_summary=rubric_summary,
            visual_selections=self._visual_selections
        )
        return report

    def _cleanup_partial(self):
        self._disconnect_engine_hooks()
        if self.gesture_router:
            self.gesture_router.active = False
        self._is_live = False

    def _register_voice_commands(self):
        if not self.voice_router:
            return
        self.voice_router.register_action(
            "explain this", lambda: self.request_visual_explanation(source="voice_command") or "Explaining selection"
        )
        self.voice_router.register_action(
            "next question", lambda: self.navigate_question(1) or "Next question"
        )
        self.voice_router.register_action(
            "previous question", lambda: self.navigate_question(-1) or "Previous question"
        )
        self.voice_router.register_action(
            "end interview", lambda: self.end_interview() or "Ending interview"
        )
