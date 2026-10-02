# ============================================================
#  INTERVIEW MODULE — Controller / Service Layer
#  Single orchestrator for the entire interview lifecycle.
#  The UI calls this instead of directly managing store/session.
# ============================================================

import time
import logging
import threading
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal, QTimer

from intent_platform.core.interview.config import InterviewConfig
from intent_platform.core.interview.models import (
    InterviewState, InterviewSetup, ObservationRecord
)
from intent_platform.core.interview.session import InterviewSession
from intent_platform.core.interview.store import interview_store
from intent_platform.core.interview.observation_engine import ObservationEngine
from intent_platform.core.interview.voice_analysis import VoiceAnalyzer
from intent_platform.core.interview.voice_router import VoiceRouter
from intent_platform.core.interview.gesture_router import GestureRouter
from intent_platform.core.interview.report_generator import ReportGenerator
from intent_platform.core.interview.novelty import (
    PersonalBaselineTracker, PasteProbeGenerator,
    CompetencyCoverageMap, QuestionFairnessLinter, EvidenceLinker
)

logger = logging.getLogger(__name__)


# ── Service Status ──

@dataclass
class ServiceCheck:
    """Result of a single pre-flight service check."""
    name: str
    available: bool
    message: str
    degraded: bool = False   # True = can continue without it


@dataclass
class PreFlightResult:
    """Aggregated pre-flight check results."""
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

    The UI subscribes to signals emitted here. No fake defaults.
    Every field starts as None (meaning: no data yet).
    """

    metrics_updated = Signal()               # general refresh
    talk_time_updated = Signal()
    transcript_entry = Signal(str, str, float)  # speaker, text, timestamp
    observation_fired = Signal(object)        # ObservationRecord
    question_changed = Signal(int, str)       # index, text
    fairness_alert = Signal(str, str, float)  # question, warning, timestamp
    coaching_suggestion = Signal(str)         # suggestion text
    service_status_changed = Signal(str, str) # service_name, status
    paste_probes_generated = Signal(list)     # list of probe dicts

    def __init__(self, parent=None):
        super().__init__(parent)

        # Speech / Talk-time (all None = "no data yet")
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

        # Rubric
        self.rubric_coverage: Optional[CompetencyCoverageMap] = None

        # Baseline
        self.baseline_status: str = "not_started"  # not_started, calibrating, established, insufficient

        # Service availability
        self.services: Dict[str, str] = {
            "camera": "unknown",
            "microphone": "unknown",
            "speech_recognition": "unknown",
            "screen_capture": "unknown",
            "ai_gemini": "unknown",
            "database": "unknown",
            "observation_engine": "unknown",
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
        """Record a speech segment and check for interruptions."""
        words = len(text.split())
        if speaker == "interviewer":
            self.interviewer_words += words
            self.interviewer_talk_s += duration
        else:
            self.candidate_words += words
            self.candidate_talk_s += duration

        self.total_talk_s = self.interviewer_talk_s + self.candidate_talk_s
        self.current_wpm = wpm

        # Interruption detection: if new speaker starts within 0.5s of previous speaker's end
        if (self._last_speaker is not None
                and self._last_speaker != speaker
                and self._last_speaker_end is not None
                and (ts - self._last_speaker_end) < 0.5):
            self.interruptions.append({
                "timestamp": ts,
                "interrupter": speaker,
                "interrupted": self._last_speaker,
                "transcript_snippet": text[:60],
            })

        self._last_speaker = speaker
        self._last_speaker_end = ts + duration

        self.talk_time_updated.emit()
        self.transcript_entry.emit(speaker, text, ts)

    def set_service_status(self, name: str, status: str):
        self.services[name] = status
        self.service_status_changed.emit(name, status)


# ── Interview Controller ──

class InterviewController(QObject):
    """Central service orchestrating the full interview lifecycle.

    UI calls:
        controller.validate_setup(setup) -> errors list
        controller.run_preflight(engine) -> PreFlightResult
        controller.start_interview(setup, engine) -> interview_id
        controller.navigate_question(delta)
        controller.add_note(content)
        controller.end_interview()
        controller.generate_report() -> report dict
    """

    # Signals for UI
    state_changed = Signal(str)              # new InterviewState value
    preflight_update = Signal(str, bool, str)  # check_name, passed, message
    preflight_complete = Signal(object)      # PreFlightResult
    interview_started = Signal(str)          # interview_id
    interview_ended = Signal()
    report_ready = Signal(dict)              # report dict
    error_occurred = Signal(str, str)        # title, detail

    def __init__(self, parent=None):
        super().__init__(parent)

        self.config = InterviewConfig(demo_mode=False)  # Real mode by default
        self.session: Optional[InterviewSession] = None
        self.metrics = InterviewMetricsState()

        # Services (initialized on start)
        self.obs_engine: Optional[ObservationEngine] = None
        self.voice_analyzer: Optional[VoiceAnalyzer] = None
        self.voice_router: Optional[VoiceRouter] = None
        self.gesture_router: Optional[GestureRouter] = None
        self.baseline_tracker: Optional[PersonalBaselineTracker] = None
        self.coverage_map: Optional[CompetencyCoverageMap] = None
        self.report_generator = ReportGenerator()

        # Engine reference
        self._engine = None
        self._interview_id: Optional[str] = None
        self._questions: List[Dict] = []
        self._current_q_idx: int = -1
        self._is_live: bool = False
        self._timer: Optional[QTimer] = None

    @property
    def interview_id(self) -> Optional[str]:
        return self._interview_id

    @property
    def state(self) -> InterviewState:
        return self.session.state if self.session else InterviewState.SETUP

    # ── 1. Validation ──

    def validate_setup(self, setup: Any) -> List[str]:
        """Returns list of validation error strings. Empty = valid."""
        if isinstance(setup, dict):
            setup = InterviewSetup(
                title=setup.get('title', ''),
                candidate_name=setup.get('candidate_name', setup.get('candidate', '')),
                candidate_email=setup.get('candidate_email', ''),
                job_role=setup.get('job_role', setup.get('target_role', setup.get('role', ''))),
                interview_type=setup.get('interview_type', setup.get('type', 'Technical')),
                duration_minutes=int(setup.get('duration_minutes', setup.get('duration', 45))),
                difficulty=setup.get('difficulty', 'Medium'),
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

    # ── 2. Pre-flight ──

    def run_preflight(self, engine=None) -> PreFlightResult:
        """Checks all services and returns aggregated result."""
        result = PreFlightResult()
        self._engine = engine

        # Database
        try:
            interview_store.get_interview_count()
            result.add("Database", True, "SQLite connected")
            self.metrics.set_service_status("database", "ready")
        except Exception as e:
            result.add("Database", False, f"Database error: {e}", degraded=False)
            self.metrics.set_service_status("database", "error")

        # Session
        result.add("Session", True, "Session manager ready")
        self.metrics.set_service_status("session", "ready")

        # Observation Engine
        result.add("Observation Engine", True, "Observation engine ready")
        self.metrics.set_service_status("observation_engine", "ready")

        # Camera (check via engine)
        if engine and hasattr(engine, 'is_running') and engine.is_running:
            result.add("Camera", True, "Camera feed active")
            self.metrics.set_service_status("camera", "ready")
        else:
            result.add("Camera", False, "Camera not active — visual features disabled", degraded=True)
            self.metrics.set_service_status("camera", "unavailable")

        # Microphone
        try:
            import speech_recognition as sr
            mic = sr.Microphone()
            with mic as source:
                pass  # Just test if it opens
            result.add("Microphone", True, "Microphone available")
            self.metrics.set_service_status("microphone", "ready")
        except Exception as e:
            result.add("Microphone", False, f"Microphone unavailable: {e}", degraded=True)
            self.metrics.set_service_status("microphone", "unavailable")

        # Speech Recognition
        if engine and hasattr(engine, 'voice_engine') and engine.voice_engine:
            result.add("Speech Recognition", True, "Voice engine ready")
            self.metrics.set_service_status("speech_recognition", "ready")
        else:
            result.add("Speech Recognition", False, "Voice engine not initialized", degraded=True)
            self.metrics.set_service_status("speech_recognition", "unavailable")

        # AI / Gemini
        try:
            from intent_platform.core.ai.gemini_service import GeminiAgent, GENAI_AVAILABLE
            from intent_platform.config.settings import GEMINI_API_KEY
            if GENAI_AVAILABLE and GEMINI_API_KEY:
                result.add("AI / Gemini", True, "Gemini API configured")
                self.metrics.set_service_status("ai_gemini", "ready")
            else:
                result.add("AI / Gemini", False, "Gemini not configured — using local fallback", degraded=True)
                self.metrics.set_service_status("ai_gemini", "fallback")
        except Exception:
            result.add("AI / Gemini", False, "AI service unavailable — using local fallback", degraded=True)
            self.metrics.set_service_status("ai_gemini", "unavailable")

        # Screen Capture
        result.add("Screen Capture", False, "Screen capture not active", degraded=True)
        self.metrics.set_service_status("screen_capture", "unavailable")

        self.preflight_complete.emit(result)
        return result

    # ── 3. Start Interview ──

    def start_interview(self, setup: Any, engine=None) -> Optional[str]:
        """Creates exactly ONE interview record, initializes all services, transitions to LIVE."""
        try:
            self._engine = engine

            if isinstance(setup, dict):
                setup = InterviewSetup(
                    title=setup.get('title', ''),
                    candidate_name=setup.get('candidate_name', setup.get('candidate', '')),
                    candidate_email=setup.get('candidate_email', ''),
                    job_role=setup.get('job_role', setup.get('target_role', setup.get('role', ''))),
                    interview_type=setup.get('interview_type', setup.get('type', 'Technical')),
                    duration_minutes=int(setup.get('duration_minutes', setup.get('duration', 45))),
                    difficulty=setup.get('difficulty', 'Medium'),
                    meeting_link=setup.get('meeting_link', ''),
                    notes=setup.get('notes', ''),
                    resume_path=setup.get('resume_path', '')
                )

            # Validate
            errors = self.validate_setup(setup)
            if errors:
                self.error_occurred.emit("Validation Error", "\n".join(errors))
                return None

            # Create session (which creates the SINGLE db record)
            self.session = InterviewSession()
            self._interview_id = self.session.initialize(setup)
            logger.info(f"Interview started: {self._interview_id}")

            # Initialize services
            self.obs_engine = ObservationEngine(self.config)
            self.obs_engine.on_observation = self._on_observation

            self.voice_analyzer = VoiceAnalyzer(self.config)

            self.voice_router = VoiceRouter()
            self._register_voice_commands()

            self.gesture_router = GestureRouter()
            self.gesture_router.active = True
            self.gesture_router.on_next_question = lambda: self.navigate_question(1)
            self.gesture_router.on_previous_question = lambda: self.navigate_question(-1)
            self.gesture_router.on_timeline_log = self._on_gesture_timeline

            self.baseline_tracker = PersonalBaselineTracker(
                calibration_duration_s=self.config.baseline_duration_s
            )
            self.metrics.baseline_status = "calibrating"

            self.coverage_map = CompetencyCoverageMap()
            self.metrics.rubric_coverage = self.coverage_map

            # Transition: SETUP -> VERIFYING -> LIVE
            self.session.transition_to(InterviewState.VERIFYING)
            self.state_changed.emit(InterviewState.VERIFYING.value)

            self.session.transition_to(InterviewState.LIVE)
            self._is_live = True
            self.state_changed.emit(InterviewState.LIVE.value)

            # Wire engine hooks
            self._connect_engine_hooks()

            # Connect session events to transcript widget
            self.session.event_logged.connect(self._on_session_event)

            # Start interview timer
            self._timer = QTimer()
            self._timer.setInterval(1000)
            self._timer.timeout.connect(self._on_timer_tick)
            self._timer.start()

            self.interview_started.emit(self._interview_id)
            self.session.emit_event("system", "Interview started — LIVE")

            return self._interview_id

        except Exception as e:
            logger.exception(f"Failed to start interview: {e}")
            self.error_occurred.emit("Start Interview Failed", str(e))
            self._cleanup_partial()
            return None

    # ── 4. Engine Hooks ──

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

    # ── 5. Runtime Callbacks ──

    def _on_frame_tap(self, frame):
        """Process each camera frame for observation engine."""
        # The observation engine tracks face count etc. via explicit calls,
        # not via raw frame processing. This hook is for future CV features.
        pass

    def record_transcript(self, speaker: str, text: str, duration: float = 0.0, ts: float = None):
        """Programmatically record a transcript entry."""
        if ts is None:
            ts = time.time()
        entry = {
            "text": text,
            "duration": duration,
            "ts": ts,
            "has_wake": (speaker == "interviewer")
        }
        self._on_transcript_tap(entry)

    def _on_transcript_tap(self, entry: dict):
        """Called by VoiceEngine for every transcript segment."""
        if not self._is_live or not self.session:
            return

        raw_text = entry.get("text", "")
        duration = entry.get("duration", 0.0)
        ts = entry.get("ts", time.time())
        has_wake = entry.get("has_wake", False)

        # Speaker attribution: wake word = interviewer, otherwise = candidate
        speaker = "interviewer" if has_wake else "candidate"

        # Analyze speech metrics
        if self.voice_analyzer and raw_text.strip():
            metrics = self.voice_analyzer.analyze_utterance(raw_text, max(duration, 0.1))
            wpm = metrics.get("wpm", 0)
        else:
            wpm = 0

        # Update live metrics state
        if raw_text.strip():
            self.metrics.add_speech(speaker, raw_text, duration, wpm, ts)

        # Persist transcript
        interview_store.add_transcript(
            self._interview_id, speaker, raw_text, duration,
            self._current_q_idx, ts
        )

        # Question fairness lint for interviewer questions
        if speaker == "interviewer" and raw_text.strip():
            warning = QuestionFairnessLinter.lint_question(raw_text)
            if warning:
                self.metrics.fairness_alert.emit(raw_text, warning, ts)
                self.session.emit_event("fairness", warning, raw_text)

        # Update baseline tracker
        if self.baseline_tracker:
            if self.baseline_tracker.is_calibrating:
                self.baseline_tracker.add_sample(0.5, wpm)
                elapsed = time.time() - self.baseline_tracker.start_time
                if not self.baseline_tracker.is_calibrating:
                    self.metrics.baseline_status = "established"
                    self.session.emit_event("system", "Personal baseline established")

        # Talk-time coaching
        self._check_talk_time_balance()

    def _on_observation(self, obs: ObservationRecord):
        """Called when ObservationEngine fires an observation."""
        self.metrics.observations.append(obs)
        self.metrics.observation_fired.emit(obs)

        if self.session:
            self.session.emit_event(
                "observation", obs.message,
                f'{{"event_type": "{obs.event_type}", "count": {obs.count}}}'
            )

    def _on_session_event(self, event_type, message, payload, timestamp):
        """Forward session events."""
        pass  # UI connects directly to session.event_logged

    def _on_gesture_timeline(self, gesture_name: str, action_label: str):
        if self.session:
            self.session.emit_event("gesture", f"{gesture_name}: {action_label}")

    def _on_timer_tick(self):
        """Update interview timer."""
        if self.session:
            remaining = self.session.get_remaining_seconds()
            self.session.timer_tick.emit(remaining)

    def _check_talk_time_balance(self):
        """Coach the interviewer on talk-time balance."""
        pct = self.metrics.interviewer_talk_pct
        if pct is not None and pct > 70 and self.metrics.total_talk_s > 120:
            self.metrics.coaching_suggestion.emit(
                "Interviewer has spoken for most of the session. "
                "Consider giving the candidate more response time."
            )

    # ── 6. Question Navigation ──

    def navigate_question(self, delta: int):
        """Move to next/previous question."""
        if not self._questions:
            return
        new_idx = max(0, min(len(self._questions) - 1, self._current_q_idx + delta))
        if new_idx != self._current_q_idx:
            self._current_q_idx = new_idx
            q = self._questions[self._current_q_idx]
            self.metrics.current_question_index = self._current_q_idx
            self.metrics.question_changed.emit(self._current_q_idx, q.get("text", ""))

            # Mark as asked
            if q.get("question_id"):
                interview_store.mark_question_asked(q["question_id"])

            # Update coverage map
            if self.coverage_map:
                self.coverage_map.tag_question(q.get("text", ""), q.get("category", ""))

            if self.session:
                self.session.set_current_question(self._current_q_idx, q.get("text", ""))

    def add_question(self, text: str, category: str = "", difficulty: str = "Medium"):
        """Add a question to the current interview."""
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
        # Auto-navigate to first question if none active
        if self._current_q_idx < 0:
            self.navigate_question(1)

    def add_note(self, content: str, note_type: str = "manual"):
        """Add a note to the current interview."""
        if not self._interview_id:
            return
        interview_store.add_note(
            self._interview_id, content,
            self._current_q_idx, note_type
        )
        if self.session:
            self.session.emit_event("note", content)

    # ── 7. Paste Detection ──

    def handle_paste_event(self, content: str):
        """Handle a paste event detected by the observation engine."""
        if not self._is_live:
            return

        if self.obs_engine:
            self.obs_engine.record_paste(content)

        # Generate probe questions from pasted code
        if len(content) > 50:
            probes = PasteProbeGenerator.generate_probes(content)
            self.metrics.paste_probes_generated.emit(probes)
            if self.session:
                self.session.emit_event(
                    "paste_probe",
                    f"Generated {len(probes)} probe questions from pasted code",
                    str(probes)
                )

    # ── 8. End Interview ──

    def end_interview(self):
        """Clean shutdown: disconnect hooks, stop services, transition state, generate report."""
        if not self._is_live:
            return

        logger.info(f"Ending interview: {self._interview_id}")
        self._is_live = False

        # Stop timer
        if self._timer:
            self._timer.stop()
            self._timer = None

        # Disconnect engine hooks
        self._disconnect_engine_hooks()

        # Deactivate gesture router
        if self.gesture_router:
            self.gesture_router.active = False

        # Transition state
        if self.session and self.session.state == InterviewState.LIVE:
            self.session.transition_to(InterviewState.ENDED)
            self.state_changed.emit(InterviewState.ENDED.value)

        self.session.emit_event("system", "Interview ended")
        self.interview_ended.emit()

        # Generate report in background
        self._generate_report_async()
        return self._build_report()

    finish_interview = end_interview

    def _generate_report_async(self):
        """Generate the report without blocking the UI."""
        def _gen():
            try:
                report = self._build_report()
                self.report_ready.emit(report)
                if self.session:
                    self.session.transition_to(InterviewState.REPORTED)
                    self.state_changed.emit(InterviewState.REPORTED.value)
            except Exception as e:
                logger.exception(f"Report generation failed: {e}")
                self.error_occurred.emit("Report Generation Failed", str(e))

        threading.Thread(target=_gen, daemon=True).start()

    def _build_report(self) -> Dict:
        """Build the report from actual session data."""
        voice_metrics = {}
        if self.voice_analyzer:
            voice_metrics = self.voice_analyzer.get_overall_metrics()

        # Add talk-time data
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
            }

        actual_duration = self.session.get_actual_duration() if self.session else 0.0

        report = self.report_generator.generate(
            interview_id=self._interview_id,
            voice_metrics=voice_metrics,
            observations=observations,
            questions=questions,
            notes=notes,
            transcript=transcript,
            setup=setup,
            actual_duration_s=actual_duration,
        )

        # Add coverage data
        if self.coverage_map:
            report["rubric_coverage"] = {
                "percentage": self.coverage_map.get_coverage_percentage(),
                "covered": {k: v for k, v in self.coverage_map.covered.items()},
                "uncovered": self.coverage_map.get_uncovered(),
            }

        return report

    # ── 9. Cleanup ──

    def _cleanup_partial(self):
        """Clean up after a failed start."""
        self._disconnect_engine_hooks()
        if self.gesture_router:
            self.gesture_router.active = False
        self._is_live = False

    def _register_voice_commands(self):
        """Register voice commands with the voice router."""
        if not self.voice_router:
            return

        self.voice_router.register_action(
            "next question", lambda: self.navigate_question(1) or "Next question"
        )
        self.voice_router.register_action(
            "previous question", lambda: self.navigate_question(-1) or "Previous question"
        )
        self.voice_router.register_action(
            "take notes", lambda: "Note mode activated"
        )
        self.voice_router.register_action(
            "end interview", lambda: self.end_interview() or "Ending interview"
        )
        self.voice_router.register_action(
            "generate summary", lambda: "Generating summary..."
        )
