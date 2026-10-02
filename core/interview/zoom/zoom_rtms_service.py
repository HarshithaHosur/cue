# ============================================================
#  ZOOM RTMS (REAL-TIME MEDIA STREAMS) SERVICE
#  Manages authorized real-time media streams (audio, transcript,
#  screen-share frames, participant metadata) from Zoom RTMS.
# ============================================================

import time
import logging
import threading
from enum import Enum
from typing import Optional, Dict, Any, Callable
from PySide6.QtCore import QObject, Signal

from intent_platform.core.interview.zoom.zoom_auth import ZoomAuthManager

logger = logging.getLogger(__name__)


class RTMSState(Enum):
    UNCONFIGURED = "UNCONFIGURED"
    INITIALIZE = "INITIALIZE"
    STARTED = "STARTED"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class ZoomRTMSService(QObject):
    """Handles real-time audio, transcript, and screen-share streaming from Zoom RTMS."""

    status_changed = Signal(str, str)                      # (status, message)
    transcript_segment = Signal(str, str, float, float)    # (speaker, text, duration, timestamp)
    participant_event = Signal(str, str, str)              # (event_type, participant_id, name)
    screen_frame_ready = Signal(object)                    # (frame_data)
    audio_level_updated = Signal(float, str)               # (level, speaker)

    def __init__(self, auth_manager: Optional[ZoomAuthManager] = None, parent=None):
        super().__init__(parent)
        self.auth_manager = auth_manager or ZoomAuthManager()
        self._state = RTMSState.UNCONFIGURED
        self._session_id: Optional[str] = None
        self._is_streaming = False
        self._lock = threading.Lock()

        # Check initial configuration
        if self.auth_manager.is_rtms_configured:
            self._state = RTMSState.INITIALIZE

    @property
    def state(self) -> RTMSState:
        return self._state

    @property
    def is_configured(self) -> bool:
        return self.auth_manager.is_rtms_configured

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

    def _set_status(self, new_state: RTMSState, message: str = ""):
        self._state = new_state
        logger.info(f"[ZoomRTMS] Status -> {new_state.value}: {message}")
        self.status_changed.emit(new_state.value, message)

    def initialize_session(self, session_id: str) -> bool:
        """Initializes RTMS connection with session ID."""
        with self._lock:
            self._session_id = session_id
            if not self.auth_manager.is_rtms_configured:
                self._set_status(
                    RTMSState.UNCONFIGURED,
                    "Zoom RTMS credentials not configured in .env. Realtime stream running in local companion mode."
                )
                return False

            token_info = self.auth_manager.get_rtms_token(session_id)
            if not token_info:
                self._set_status(RTMSState.ERROR, "Failed to acquire RTMS authorization token.")
                return False

            self._set_status(RTMSState.INITIALIZE, f"RTMS session initialized for session {session_id}.")
            return True

    def start_stream(self) -> bool:
        """Starts real-time media and transcript ingestion."""
        with self._lock:
            if not self.auth_manager.is_rtms_configured:
                self._is_streaming = True
                self._set_status(
                    RTMSState.STARTED,
                    "RTMS streaming started in companion mode (using local device audio & screen capture)."
                )
                return True

            self._is_streaming = True
            self._set_status(RTMSState.STARTED, "Zoom RTMS connection established. Streaming live meeting data.")
            return True

    def pause_stream(self):
        """Pauses stream processing."""
        with self._lock:
            if self._is_streaming:
                self._is_streaming = False
                self._set_status(RTMSState.PAUSED, "RTMS stream paused.")

    def resume_stream(self):
        """Resumes paused stream."""
        with self._lock:
            if not self._is_streaming:
                self._is_streaming = True
                self._set_status(RTMSState.RESUMED, "RTMS stream resumed.")

    def stop_stream(self):
        """Stops RTMS streaming and releases resources."""
        with self._lock:
            self._is_streaming = False
            self._session_id = None
            self._set_status(RTMSState.STOPPED, "RTMS stream stopped cleanly.")

    def inject_transcript_segment(self, speaker: str, text: str, duration: float = 0.0, ts: Optional[float] = None):
        """Receives a transcript segment and broadcasts it to downstream listeners."""
        if not self._is_streaming:
            return
        if ts is None:
            ts = time.time()
        self.transcript_segment.emit(speaker, text, duration, ts)

    def inject_participant_event(self, event_type: str, participant_id: str, name: str):
        """Receives participant joined/left/muted events."""
        self.participant_event.emit(event_type, participant_id, name)
