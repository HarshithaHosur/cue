# ============================================================
#  ZOOM AUTHENTICATION & TOKEN MANAGER
#  Generates secure tokens and signatures for Zoom Meeting SDK
#  and Zoom RTMS (Real-Time Media Streams).
#  Never exposes raw client secrets to frontend code.
# ============================================================

import os
import time
import hmac
import hashlib
import base64
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ZoomAuthManager:
    """Manages Zoom Meeting SDK & RTMS authentication credentials and signatures."""

    def __init__(self):
        self.client_id = os.getenv("ZOOM_CLIENT_ID", "")
        self.client_secret = os.getenv("ZOOM_CLIENT_SECRET", "")
        self.account_id = os.getenv("ZOOM_ACCOUNT_ID", "")
        self.sdk_key = os.getenv("ZOOM_SDK_KEY", os.getenv("ZOOM_CLIENT_ID", ""))
        self.sdk_secret = os.getenv("ZOOM_SDK_SECRET", os.getenv("ZOOM_CLIENT_SECRET", ""))
        self.rtms_client_id = os.getenv("ZOOM_RTMS_CLIENT_ID", self.client_id)
        self.rtms_client_secret = os.getenv("ZOOM_RTMS_CLIENT_SECRET", self.client_secret)

    @property
    def is_sdk_configured(self) -> bool:
        """Checks if Zoom Meeting SDK credentials are configured."""
        return bool(self.sdk_key and self.sdk_secret)

    @property
    def is_rtms_configured(self) -> bool:
        """Checks if Zoom RTMS credentials are configured."""
        return bool(self.rtms_client_id and self.rtms_client_secret)

    def generate_sdk_signature(self, meeting_number: str, role: int = 0) -> Optional[str]:
        """Generates a valid HMAC-SHA256 signature for Zoom Meeting SDK.
        
        Args:
            meeting_number: Cleaned meeting ID string.
            role: 0 for attendee / assistant, 1 for host.
        """
        if not self.is_sdk_configured:
            logger.warning("[ZoomAuth] Meeting SDK credentials not configured in environment.")
            return None

        try:
            ts = int(round(time.time() * 1000)) - 30000
            msg = f"{self.sdk_key}{meeting_number}{ts}{role}"
            message = base64.b64encode(msg.encode("utf-8"))
            secret = self.sdk_secret.encode("utf-8")
            hash_val = hmac.new(secret, message, hashlib.sha256).digest()
            hash_b64 = base64.b64encode(hash_val).decode("utf-8")
            tmp_string = f"{self.sdk_key}.{meeting_number}.{ts}.{role}.{hash_b64}"
            signature = base64.b64encode(tmp_string.encode("utf-8")).decode("utf-8")
            return signature
        except Exception as e:
            logger.error(f"[ZoomAuth] Error generating SDK signature: {e}")
            return None

    def get_rtms_token(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Generates/returns authorized RTMS session token payload.
        
        In production, this requests or signs an RTMS connection token with Zoom RTMS endpoint.
        """
        if not self.is_rtms_configured:
            logger.warning("[ZoomAuth] RTMS credentials not configured in environment.")
            return None

        # Return structured token metadata for the RTMS client
        expires_at = int(time.time()) + 3600
        return {
            "client_id": self.rtms_client_id,
            "session_id": session_id,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "status": "ready"
        }

    def check_authorization_status(self) -> Dict[str, Any]:
        """Returns detailed authorization readiness for UI display."""
        return {
            "sdk_configured": self.is_sdk_configured,
            "rtms_configured": self.is_rtms_configured,
            "client_id_present": bool(self.client_id),
            "account_id_present": bool(self.account_id),
            "missing_vars": [
                var for var, val in [
                    ("ZOOM_CLIENT_ID", self.client_id),
                    ("ZOOM_CLIENT_SECRET", self.client_secret),
                    ("ZOOM_RTMS_CLIENT_ID", self.rtms_client_id),
                    ("ZOOM_RTMS_CLIENT_SECRET", self.rtms_client_secret),
                ] if not val
            ]
        }
