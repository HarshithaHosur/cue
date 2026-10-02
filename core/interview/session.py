# ============================================================
#  INTERVIEW MODULE — Session State Machine
# ============================================================

import time
import logging
from typing import Optional, Dict, Any

from PySide6.QtCore import QObject, Signal

from intent_platform.core.interview.models import InterviewState, InterviewSetup
from intent_platform.core.interview.store import interview_store

logger = logging.getLogger(__name__)


class InterviewSession(QObject):
    """Interview state machine supporting the full lifecycle:
    CREATED -> CONFIGURED -> PERMISSIONS_CHECKING -> PREFLIGHT -> LIVE -> ENDING -> COMPLETED
    """

    state_changed = Signal(str)                  # new state string
    event_logged = Signal(str, str, str, float)  # event_type, message, payload, timestamp
    question_changed = Signal(int, str)          # index, text
    timer_tick = Signal(int)                     # remaining seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = InterviewState.CREATED
        self._setup: Optional[InterviewSetup] = None
        self._interview_id: Optional[str] = None
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._current_question_index: int = -1
        self._face_encoding = None

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

    def initialize(self, setup: InterviewSetup) -> str:
        """Creates interview in DB and stores setup data."""
        self._setup = setup
        self._interview_id = interview_store.create_interview({
            "title": setup.title,
            "candidate_name": setup.candidate_name,
            "candidate_email": setup.candidate_email,
            "job_role": setup.job_role,
            "interview_type": setup.interview_type,
            "duration_minutes": setup.duration_minutes,
            "difficulty": setup.difficulty,
            "meeting_platform": getattr(setup, "meeting_platform", "Zoom"),
            "meeting_link": setup.meeting_link,
            "notes": setup.notes,
            "resume_path": setup.resume_path,
            "status": "scheduled",
            "created_at": setup.created_at,
        })
        setup.interview_id = self._interview_id
        logger.info(f"[InterviewSession] Session created: {self._interview_id}")
        return self._interview_id

    def transition_to(self, new_state: InterviewState) -> bool:
        """Attempt a state transition."""
        old = self._state
        self._state = new_state

        if new_state == InterviewState.LIVE:
            self._start_time = time.time()
            interview_store.update_interview_status(
                self._interview_id, "live", started_at=self._start_time
            )
        elif new_state in (InterviewState.COMPLETED, InterviewState.ENDED):
            self._end_time = time.time()
            duration = self._end_time - (self._start_time or self._end_time)
            interview_store.update_interview_status(
                self._interview_id, "completed",
                ended_at=self._end_time, actual_duration_s=duration
            )
        elif new_state == InterviewState.PREFLIGHT:
            interview_store.update_interview_status(self._interview_id, "preflight")

        self.emit_event("system", f"State: {old.value} → {new_state.value}")
        self.state_changed.emit(new_state.value)
        logger.info(f"[InterviewSession] {self._interview_id}: {old.value} → {new_state.value}")
        return True

    def emit_event(self, event_type: str, message: str, payload: str = "") -> str:
        """Write to store and emit signal."""
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
