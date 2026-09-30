# ============================================================
#  INTERVIEW MODULE — Observation Engine
#  Records neutral observations with hysteresis and cooldowns.
# ============================================================

import time
import logging
from typing import Dict, Optional

from intent_platform.core.interview.config import InterviewConfig
from intent_platform.core.interview.models import ObservationRecord

logger = logging.getLogger(__name__)


class ObservationEngine:
    """Tracks behavioral observations with cooldowns and hysteresis.

    All messages use neutral wording; banned words are never used.
    """

    def __init__(self, config: InterviewConfig):
        self.config = config
        self._observations: list = []
        self._cooldowns: Dict[str, float] = {}   # event_type -> last_fire_time
        self._counters: Dict[str, int] = {}

        # Hysteresis state
        self._gaze_away_start: Optional[float] = None
        self._no_face_start: Optional[float] = None
        self._multi_face_start: Optional[float] = None
        self._camera_lost_start: Optional[float] = None
        self._screen_lost_start: Optional[float] = None
        self._screen_inactive_start: Optional[float] = None

        # Rolling windows
        self._app_switches: list = []   # list of timestamps
        self._tab_switches: list = []
        self._head_movements: list = []

        # Callback
        self.on_observation = None   # callable(ObservationRecord)

    @property
    def observations(self) -> list:
        return list(self._observations)

    def _check_cooldown(self, event_type: str) -> bool:
        last = self._cooldowns.get(event_type, 0)
        if time.time() - last < self.config.observation_cooldown_s:
            return False
        return True

    def _fire(self, event_type: str, message: str, level: str = "notice") -> ObservationRecord:
        self._cooldowns[event_type] = time.time()
        self._counters[event_type] = self._counters.get(event_type, 0) + 1
        obs = ObservationRecord(
            event_type=event_type,
            message=message,
            count=self._counters[event_type],
            level=level,
            timestamp=time.time()
        )
        self._observations.append(obs)
        if self.on_observation:
            try:
                self.on_observation(obs)
            except Exception as e:
                logger.error(f"Observation callback error: {e}")
        return obs

    # ── Face / Identity ──

    def update_face_count(self, count: int):
        now = time.time()

        # Multiple faces
        if count >= 2:
            if self._multi_face_start is None:
                self._multi_face_start = now
            elif (now - self._multi_face_start) >= self.config.multi_face_duration_s:
                if self._check_cooldown("multi_face"):
                    self._fire("multi_face", "Multiple faces detected")
                    self._multi_face_start = now  # reset for next hysteresis
        else:
            self._multi_face_start = None

        # No face
        if count == 0:
            if self._no_face_start is None:
                self._no_face_start = now
            elif (now - self._no_face_start) >= self.config.no_face_duration_s:
                if self._check_cooldown("no_face"):
                    self._fire("no_face", "Candidate not in frame")
                    self._no_face_start = now
        else:
            if self._no_face_start is not None:
                if self._check_cooldown("face_returned"):
                    self._fire("face_returned", "Candidate returned", level="info")
            self._no_face_start = None

    def face_mismatch(self, similarity: float):
        if self._check_cooldown("face_mismatch"):
            self._fire(
                "face_mismatch",
                f"Face did not match the enrolled reference (similarity {similarity:.2f})"
            )

    # ── Gaze ──

    def update_gaze(self, is_looking: bool):
        now = time.time()
        if not is_looking:
            if self._gaze_away_start is None:
                self._gaze_away_start = now
            elif (now - self._gaze_away_start) >= self.config.gaze_away_threshold_s:
                duration = now - self._gaze_away_start
                if self._check_cooldown("gaze_away"):
                    self._fire(
                        "gaze_away",
                        f"Extended gaze away from screen ({duration:.0f} s)"
                    )
                    self._gaze_away_start = now
        else:
            self._gaze_away_start = None

    # ── Head Movement ──

    def record_head_movement(self):
        now = time.time()
        self._head_movements.append(now)
        cutoff = now - self.config.head_movement_window_s
        self._head_movements = [t for t in self._head_movements if t >= cutoff]
        if len(self._head_movements) >= self.config.head_movement_max_per_min:
            if self._check_cooldown("head_movement"):
                self._fire("head_movement", "Frequent head movement observed")

    # ── Camera ──

    def update_camera_status(self, frames_arriving: bool):
        now = time.time()
        if not frames_arriving:
            if self._camera_lost_start is None:
                self._camera_lost_start = now
            elif (now - self._camera_lost_start) >= self.config.camera_interrupt_s:
                if self._check_cooldown("camera_interrupt"):
                    self._fire("camera_interrupt", "Camera feed interrupted")
        else:
            if self._camera_lost_start is not None:
                if self._check_cooldown("camera_resumed"):
                    self._fire("camera_resumed", "Camera feed resumed", level="info")
            self._camera_lost_start = None

    # ── App Switching ──

    def record_app_switch(self, app_category: str):
        now = time.time()
        self._app_switches.append(now)
        cutoff = now - self.config.app_switch_window_s
        self._app_switches = [t for t in self._app_switches if t >= cutoff]
        if len(self._app_switches) >= self.config.app_switch_max_count:
            if self._check_cooldown("app_switch"):
                n = len(self._app_switches)
                self._fire(
                    "app_switch",
                    f"Frequent application switching observed ({n} in 2 min)"
                )

    # ── Tab Switching ──

    def record_tab_switch(self):
        now = time.time()
        self._tab_switches.append(now)
        cutoff = now - self.config.tab_switch_window_s
        self._tab_switches = [t for t in self._tab_switches if t >= cutoff]
        if len(self._tab_switches) >= self.config.tab_switch_max_count:
            if self._check_cooldown("tab_switch"):
                self._fire("tab_switch", "Frequent tab switching observed")

    # ── Screen ──

    def update_screen_status(self, is_active: bool):
        now = time.time()
        if not is_active:
            if self._screen_lost_start is None:
                self._screen_lost_start = now
            elif (now - self._screen_lost_start) >= self.config.screen_interrupt_s:
                if self._check_cooldown("screen_interrupt"):
                    self._fire("screen_interrupt", "Screen share interrupted")
        else:
            if self._screen_lost_start is not None:
                if self._check_cooldown("screen_resumed"):
                    self._fire("screen_resumed", "Screen share resumed", level="info")
            self._screen_lost_start = None

    def update_screen_activity(self, has_changed: bool, speech_active: bool = False):
        now = time.time()
        if not has_changed:
            if self._screen_inactive_start is None:
                self._screen_inactive_start = now
            elif (now - self._screen_inactive_start) >= self.config.screen_inactivity_s:
                if self._check_cooldown("screen_inactivity"):
                    speech = "yes" if speech_active else "no"
                    self._fire(
                        "screen_inactivity",
                        f"Extended screen inactivity (speech activity: {speech})"
                    )
                    self._screen_inactive_start = now
        else:
            self._screen_inactive_start = None

    # ── Paste ──

    def record_paste(self, content: str):
        lines = content.count('\n') + 1
        chars = len(content)
        if chars >= self.config.paste_char_threshold or lines >= self.config.paste_line_threshold:
            if self._check_cooldown("paste"):
                self._fire(
                    "paste",
                    f"Large pasted content detected ({lines} lines)"
                )

    # ── Mic ──

    def mic_interrupted(self):
        if self._check_cooldown("mic_interrupt"):
            self._fire("mic_interrupt", "Microphone interruption observed")

    def mic_resumed(self):
        if self._check_cooldown("mic_resumed"):
            self._fire("mic_resumed", "Microphone resumed", level="info")

    # ── Summary ──

    def get_summary(self) -> Dict[str, int]:
        """Return grouped observation counts."""
        summary = {}
        for obs in self._observations:
            summary[obs.event_type] = summary.get(obs.event_type, 0) + 1
        return summary
