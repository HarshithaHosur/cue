# ============================================================
#  INTERVIEW MODULE — Session State Machine
# ============================================================

import time
import logging
import json
from typing import Optional, Dict, Any

from PySide6.QtCore import QObject, Signal

from intent_platform.core.interview.models import InterviewState, InterviewSetup
from intent_platform.core.interview.store import interview_store

logger = logging.getLogger(__name__)


class InterviewSession(QObject):
    """Thread-safe interview state machine: SETUP -> VERIFYING -> LIVE -> ENDED -> REPORTED.

    Emits Qt signals on every state transition and event.
    """

    # Signals
    state_changed = Signal(str)                  # new state string
    event_logged = Signal(str, str, str, float)  # event_type, message, payload, timestamp
    question_changed = Signal(int, str)          # index, text
    timer_tick = Signal(int)                     # remaining seconds

    VALID_TRANSITIONS = {
        InterviewState.SETUP: [InterviewState.VERIFYING],
        InterviewState.VERIFYING: [InterviewState.LIVE, InterviewState.SETUP],
        InterviewState.LIVE: [InterviewState.ENDED],
        InterviewState.ENDED: [InterviewState.REPORTED],
        InterviewState.REPORTED: [],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = InterviewState.SETUP
        self._setup: Optional[InterviewSetup] = None
        self._interview_id: Optional[str] = None
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._current_question_index: int = -1
        self._face_encoding = None  # Candidate face anchor

    @property
    def state(self) -> InterviewState:
        return self._state

    @property
    def interview_id(self) -> Optional[str]:
        return self._interview_id

    @property
    def setup(self) -> Optional[InterviewSetup]:
        return self._setup

    @property
    def start_time(self) -> Optional[float]:
        return self._start_time

    @property
    def current_question_index(self) -> int:
        return self._current_question_index

    @property
    def face_encoding(self):
        return self._face_encoding

    @face_encoding.setter
    def face_encoding(self, val):
        self._face_encoding = val

    def initialize(self, setup: InterviewSetup) -> str:
        """Create interview in DB and store setup data."""
        self._setup = setup
        self._interview_id = interview_store.create_interview({
            "title": setup.title,
            "candidate_name": setup.candidate_name,
            "candidate_email": setup.candidate_email,
            "job_role": setup.job_role,
            "interview_type": setup.interview_type,
            "duration_minutes": setup.duration_minutes,
            "difficulty": setup.difficulty,
            "meeting_link": setup.meeting_link,
            "notes": setup.notes,
            "resume_path": setup.resume_path,
            "status": "scheduled",
            "created_at": setup.created_at,
        })
        setup.interview_id = self._interview_id
        logger.info(f"Interview created: {self._interview_id}")
        return self._interview_id

    def transition_to(self, new_state: InterviewState) -> bool:
        """Attempt a state transition. Returns True on success."""
        if new_state not in self.VALID_TRANSITIONS.get(self._state, []):
            logger.warning(
                f"Invalid transition: {self._state.value} -> {new_state.value}"
            )
            return False

        old = self._state
        self._state = new_state

        if new_state == InterviewState.LIVE:
            self._start_time = time.time()
            interview_store.update_interview_status(
                self._interview_id, "live", started_at=self._start_time
            )
        elif new_state == InterviewState.ENDED:
            self._end_time = time.time()
            duration = self._end_time - (self._start_time or self._end_time)
            interview_store.update_interview_status(
                self._interview_id, "ended",
                ended_at=self._end_time, actual_duration_s=duration
            )
        elif new_state == InterviewState.REPORTED:
            interview_store.update_interview_status(self._interview_id, "reported")
        elif new_state == InterviewState.VERIFYING:
            interview_store.update_interview_status(self._interview_id, "verifying")

        self.emit_event("system", f"State: {old.value} → {new_state.value}")
        self.state_changed.emit(new_state.value)
        logger.info(f"Interview {self._interview_id}: {old.value} → {new_state.value}")
        return True

    def emit_event(self, event_type: str, message: str, payload: str = "") -> str:
        """Thread-safe: write to store and emit signal."""
        if not self._interview_id:
            return ""
        ts = time.time()
        eid = interview_store.add_event(
            self._interview_id, event_type, message, payload, ts
        )
        self.event_logged.emit(event_type, message, payload, ts)
        return eid

    def set_current_question(self, index: int, text: str = ""):
        self._current_question_index = index
        self.question_changed.emit(index, text)

    def get_remaining_seconds(self) -> int:
        if not self._start_time or not self._setup:
            return 0
        elapsed = time.time() - self._start_time
        total = self._setup.duration_minutes * 60
        return max(0, int(total - elapsed))

    def get_actual_duration(self) -> float:
        if self._start_time:
            end = self._end_time or time.time()
            return end - self._start_time
        return 0.0
