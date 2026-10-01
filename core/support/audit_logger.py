# ============================================================
#  SUPPORT AUDIT LOGGER — Action, Safety & Decision Traceability
#  Maintains an immutable timeline of screen detections,
#  AI reasoning steps, user confirmations, and UI automations.
# ============================================================

import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from PySide6.QtCore import QObject, Signal

from intent_platform.database.connection import db


class AuditLoggerSignals(QObject):
    entry_added = Signal(dict)


class SupportAuditLogger:
    """
    Thread-safe audit logging for customer support actions.
    Emits real-time Qt signals for UI panels and persists to database.
    """

    def __init__(self, max_history: int = 250):
        self.max_history = max_history
        self.entries: List[Dict[str, Any]] = []
        self.signals = AuditLoggerSignals()

    def log(
        self,
        message: str,
        category: str = "ACTION",
        risk_level: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Logs a timestamped audit entry.
        Example: 10:42 Detected Amazon Orders Page
        """
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        short_time = now.strftime("%H:%M")

        entry = {
            "id": len(self.entries) + 1,
            "timestamp": time_str,
            "short_time": short_time,
            "message": message,
            "category": category,
            "risk_level": risk_level,
            "metadata": metadata or {}
        }

        self.entries.append(entry)
        if len(self.entries) > self.max_history:
            self.entries.pop(0)

        # Print to console (safe against Windows console encoding)
        try:
            print(f"[AUDIT {short_time}] [{category}] [{risk_level}] {message}")
        except Exception:
            try:
                safe_msg = message.encode("ascii", "replace").decode("ascii")
                print(f"[AUDIT {short_time}] [{category}] [{risk_level}] {safe_msg}")
            except Exception:
                pass

        # Persist to database
        try:
            db.log_event("support_audit", f"{category}:{risk_level}", message)
        except Exception:
            pass

        # Emit signal to live UI dashboards
        self.signals.entry_added.emit(entry)
        return entry

    def get_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.entries[-limit:]

    def get_entries(self) -> List[Dict[str, Any]]:
        return self.entries

    def clear(self):
        self.entries.clear()


# Global Singleton for support audit logging
global_audit_logger = SupportAuditLogger()
