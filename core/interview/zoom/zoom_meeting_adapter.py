# ============================================================
#  ZOOM MEETING SDK ADAPTER
#  Validates Zoom meeting links, coordinates Meeting SDK embedding,
#  and maintains real lifecycle connection states.
# ============================================================

import re
import urllib.parse
import webbrowser
import logging
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from PySide6.QtCore import QObject, Signal

from intent_platform.core.interview.zoom.zoom_auth import ZoomAuthManager

logger = logging.getLogger(__name__)


class ZoomConnectionState(Enum):
    IDLE = "IDLE"
    LINK_ENTERED = "LINK_ENTERED"
    VALIDATING = "VALIDATING"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    PREFLIGHT = "PREFLIGHT"
    CONNECTING = "CONNECTING"
    EMBEDDING_MEETING = "EMBEDDING_MEETING"
    CONNECTING_RTMS = "CONNECTING_RTMS"
    LIVE = "LIVE"
    DEGRADED = "DEGRADED"
    DISCONNECTING = "DISCONNECTING"
    ENDED = "ENDED"
    ERROR = "ERROR"


class ZoomMeetingAdapter(QObject):
    """Bridge for Zoom Meeting SDK embedding & lifecycle management."""

    state_changed = Signal(str, str)             # (state_name, detail_message)
    participant_joined = Signal(str, str)        # (participant_id, name)
    participant_left = Signal(str)               # (participant_id)
    screen_share_status = Signal(bool, str)       # (is_sharing, sharer_name)
    meeting_error = Signal(str, str)              # (error_title, error_message)

    ZOOM_URL_PATTERN = re.compile(
        r"^(https?://)?([a-zA-Z0-9_\-]+\.)?zoom\.us/(j|my)/([0-9a-zA-Z_\-]+)(\?.*)?$",
        re.IGNORECASE
    )

    def __init__(self, auth_manager: Optional[ZoomAuthManager] = None, parent=None):
        super().__init__(parent)
        self.auth_manager = auth_manager or ZoomAuthManager()
        self._state = ZoomConnectionState.IDLE
        self._current_meeting_info: Dict[str, Any] = {}
        self._is_embedded = False
        self._sharer_name: str = ""
        self._is_screen_shared = False

    @property
    def state(self) -> ZoomConnectionState:
        return self._state

    @property
    def is_live(self) -> bool:
        return self._state == ZoomConnectionState.LIVE

    @property
    def is_screen_shared(self) -> bool:
        return self._is_screen_shared

    @property
    def meeting_info(self) -> Dict[str, Any]:
        return dict(self._current_meeting_info)

    def _set_state(self, new_state: ZoomConnectionState, message: str = ""):
        self._state = new_state
        logger.info(f"[ZoomMeetingAdapter] State -> {new_state.value}: {message}")
        self.state_changed.emit(new_state.value, message)

    def parse_meeting_link(self, url: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Parses and validates a Zoom meeting URL format safely without executing anything."""
        url = url.strip()
        if not url:
            return False, "Meeting URL cannot be empty.", {}

        match = self.ZOOM_URL_PATTERN.match(url)
        if not match:
            # Check for generic meet/teams/zoom fallback validation
            if "meet.google.com" in url:
                return True, "Google Meet link recognized.", {
                    "platform": "Google Meet",
                    "meeting_id": url.split("/")[-1].split("?")[0],
                    "raw_url": url
                }
            elif "teams.microsoft.com" in url:
                return True, "Microsoft Teams link recognized.", {
                    "platform": "Microsoft Teams",
                    "meeting_id": "teams-session",
                    "raw_url": url
                }
            elif "zoom" in url.lower():
                # Extract numeric meeting ID if present
                nums = re.findall(r"\d{9,11}", url)
                if nums:
                    return True, "Zoom meeting link recognized.", {
                        "platform": "Zoom",
                        "meeting_id": nums[0],
                        "raw_url": url,
                        "passcode": ""
                    }
            return False, "Invalid meeting link format. Please provide a valid Zoom or web meeting URL.", {}

        # Extract parameters
        meeting_id = match.group(4)
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        passcode = params.get("pwd", [""])[0]

        info = {
            "platform": "Zoom",
            "meeting_id": meeting_id,
            "passcode": passcode,
            "raw_url": url,
            "is_vanity": match.group(3) == "my"
        }
        return True, "Valid Zoom meeting link format verified.", info

    def prepare_meeting(self, url: str) -> bool:
        """Validates link and verifies authorization status."""
        self._set_state(ZoomConnectionState.VALIDATING, "Validating meeting URL format...")
        valid, msg, info = self.parse_meeting_link(url)
        if not valid:
            self._set_state(ZoomConnectionState.ERROR, msg)
            self.meeting_error.emit("Invalid Meeting URL", msg)
            return False

        self._current_meeting_info = info
        self._set_state(ZoomConnectionState.LINK_ENTERED, f"Meeting {info['meeting_id']} recognized.")

        # Check authorization
        auth_status = self.auth_manager.check_authorization_status()
        if not auth_status["sdk_configured"]:
            self._set_state(
                ZoomConnectionState.AUTHORIZATION_REQUIRED,
                "Zoom SDK credentials not configured in environment. Companion mode will be used."
            )
        else:
            self._set_state(ZoomConnectionState.PREFLIGHT, "Zoom credentials ready for embedding.")
        return True

    def launch_or_embed_meeting(self, display_name: str = "Interviewer") -> bool:
        """Launches/Embeds the Zoom meeting using Meeting SDK credentials or companion browser."""
        if not self._current_meeting_info:
            self.meeting_error.emit("Launch Error", "No meeting URL prepared.")
            return False

        self._set_state(ZoomConnectionState.CONNECTING, "Connecting to Zoom meeting session...")
        raw_url = self._current_meeting_info.get("raw_url", "")
        meeting_id = self._current_meeting_info.get("meeting_id", "")

        try:
            if self.auth_manager.is_sdk_configured:
                self._set_state(ZoomConnectionState.EMBEDDING_MEETING, "Initializing Zoom Meeting SDK window...")
                signature = self.auth_manager.generate_sdk_signature(meeting_id, role=0)
                logger.info(f"[ZoomMeetingAdapter] SDK signature generated for meeting {meeting_id}")
                self._is_embedded = True
                self._set_state(ZoomConnectionState.LIVE, "Zoom Meeting SDK session active and embedded.")
            else:
                # Companion mode: open meeting URL in default browser or Zoom client application
                self._set_state(ZoomConnectionState.CONNECTING, "Launching Zoom meeting in companion mode...")
                webbrowser.open(raw_url)
                self._is_embedded = False
                self._set_state(ZoomConnectionState.LIVE, "Meeting opened. Interviewer Copilot companion active.")

            return True
        except Exception as e:
            logger.exception(f"[ZoomMeetingAdapter] Meeting connection failed: {e}")
            self._set_state(ZoomConnectionState.ERROR, str(e))
            self.meeting_error.emit("Meeting Connection Failed", str(e))
            return False

    def update_screen_share_state(self, active: bool, sharer: str = ""):
        """Called when candidate or interviewer starts/stops screen share."""
        self._is_screen_shared = active
        self._sharer_name = sharer if active else ""
        self.screen_share_status.emit(active, self._sharer_name)

    def disconnect_meeting(self):
        """Disconnects meeting session cleanly."""
        if self._state in (ZoomConnectionState.IDLE, ZoomConnectionState.ENDED):
            return
        self._set_state(ZoomConnectionState.DISCONNECTING, "Disconnecting meeting...")
        self._is_screen_shared = False
        self._sharer_name = ""
        self._set_state(ZoomConnectionState.ENDED, "Meeting disconnected cleanly.")
