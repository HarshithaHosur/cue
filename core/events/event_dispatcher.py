# ============================================================
#  EVENT DISPATCHER — Concurrent Non-Blocking Action Layer
#  Guarantees Voice, Gestures, Mouse, Vision, and AI execution
#  operate simultaneously without thread-lock starvation.
# ============================================================

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Optional, Dict

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("EventDispatcher")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class EventPriority(IntEnum):
    SAFETY = 100
    USER_COMMAND = 80
    GESTURE = 60
    MOUSE = 40
    BACKGROUND_AI = 20


@dataclass(order=True)
class InputEvent:
    priority: int = EventPriority.USER_COMMAND
    source: str = field(compare=False, default="SYSTEM")      # VOICE, GESTURE, MOUSE, VISION, AI, SYSTEM
    event_type: str = field(compare=False, default="")        # e.g. "open_chrome", "thumbs_up", "cursor_move"
    payload: Any = field(compare=False, default=None)
    timestamp: float = field(compare=False, default_factory=time.time)


class DispatcherSignals(QObject):
    event_received = Signal(dict)
    event_dispatched = Signal(dict)
    action_completed = Signal(str, str)


class EventDispatcher:
    """
    Coordinates asynchronous non-blocking execution of HCI automation actions.
    Uses dedicated thread pools so automation tasks never block recognition loops.
    """

    _instance: Optional["EventDispatcher"] = None
    _lock = threading.RLock()

    def __init__(self, max_workers: int = 6):
        self.signals = DispatcherSignals()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ActionWorker")

    @classmethod
    def get_instance(cls) -> "EventDispatcher":
        with cls._lock:
            if cls._instance is None:
                cls._instance = EventDispatcher()
            return cls._instance

    def dispatch(self, event: InputEvent, action_fn: Optional[Callable[[], Any]] = None):
        """Dispatches an action asynchronously with priority logging."""
        logger.info(f"[{event.source.upper()}] event detected: {event.event_type} (priority: {event.priority})")
        
        event_dict = {
            "source": event.source,
            "event_type": event.event_type,
            "priority": int(event.priority),
            "timestamp": event.timestamp,
        }
        self.signals.event_received.emit(event_dict)

        if action_fn:
            def _execute():
                try:
                    logger.info(f"[DISPATCH] Executing action for [{event.source}] -> {event.event_type}")
                    result = action_fn()
                    res_str = str(result) if result is not None else "OK"
                    logger.info(f"[DISPATCH] Completed action for [{event.source}] -> {res_str}")
                    self.signals.action_completed.emit(event.event_type, res_str)
                except Exception as e:
                    logger.error(f"[DISPATCH] Error executing action for [{event.source}]: {e}")
                    self.signals.action_completed.emit(event.event_type, f"Error: {e}")

            self._executor.submit(_execute)
        
        self.signals.event_dispatched.emit(event_dict)


def get_event_dispatcher() -> EventDispatcher:
    return EventDispatcher.get_instance()
