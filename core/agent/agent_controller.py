# ============================================================
#  UNIFIED AGENT CONTROLLER — State Machine & Event Convergence
#  Single source of truth for AI Agent / Robot lifecycle,
#  position state, animations, and multi-input activations.
# ============================================================

import logging
import threading
import time
from enum import Enum
from typing import Optional

from PySide6.QtCore import QObject, Signal, QTimer

from intent_platform.core.features.feature_manager import Feature, get_feature_manager

logger = logging.getLogger("AgentController")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class AgentState(str, Enum):
    RESTING = "RESTING"
    ACTIVATING = "ACTIVATING"
    ACTIVE = "ACTIVE"
    DEACTIVATING = "DEACTIVATING"
    PROCESSING = "PROCESSING"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class AgentControllerSignals(QObject):
    """Qt Signals emitted on agent lifecycle and positioning changes."""
    state_changed = Signal(str, str)             # current_state, message
    position_requested = Signal(str, int)        # target_position ("bottom_right" / "top_right"), duration_ms
    companion_mood = Signal(str, str)           # qml_state, speech_bubble
    agent_activated = Signal(str)               # activation_source
    agent_deactivated = Signal(str)             # deactivation_source


class AgentController(QObject):
    """
    Central orchestrator for AI Agent activation, robot animation states,
    and unified event dispatching across Voice, Gestures, and Dashboard buttons.
    """

    _instance: Optional["AgentController"] = None
    _lock = threading.RLock()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = AgentControllerSignals()
        self._state_lock = threading.RLock()
        self._current_state: AgentState = AgentState.RESTING
        self._active_source: str = "init"
        self._feature_manager = get_feature_manager()

        # Connect feature state listener
        self._feature_manager.signals.feature_toggled.connect(self._on_feature_toggled)

    @classmethod
    def get_instance(cls) -> "AgentController":
        with cls._lock:
            if cls._instance is None:
                cls._instance = AgentController()
            return cls._instance

    @property
    def current_state(self) -> AgentState:
        with self._state_lock:
            return self._current_state

    @property
    def is_active(self) -> bool:
        with self._state_lock:
            return self._current_state in (AgentState.ACTIVATING, AgentState.ACTIVE, AgentState.PROCESSING)

    def _on_feature_toggled(self, feature: str, enabled: bool):
        """If the AI Agent feature itself is toggled OFF, deactivate agent."""
        if feature == Feature.AI_AGENT.value:
            if not enabled:
                with self._state_lock:
                    self._current_state = AgentState.DISABLED
                logger.info("[AGENT] Feature AI_AGENT disabled -> deactivating to bottom-right")
                self.signals.position_requested.emit("bottom_right", 350)
                self.signals.state_changed.emit(AgentState.DISABLED.value, "AI Agent Disabled")
                self.signals.companion_mood.emit("idle", "Agent Disabled")
            elif enabled and self._current_state == AgentState.DISABLED:
                with self._state_lock:
                    self._current_state = AgentState.RESTING
                self.signals.state_changed.emit(AgentState.RESTING.value, "Ready")
                self.signals.companion_mood.emit("idle", "Ready")

    def activate(self, source: str = "dashboard", duration_ms: int = 650) -> bool:
        """
        Unified activation endpoint:
        Transitions: RESTING -> ACTIVATING -> (smooth animation to TOP-RIGHT) -> ACTIVE.
        """
        with self._state_lock:
            if not self._feature_manager.is_enabled(Feature.AI_AGENT):
                logger.warning(f"[AGENT] Activation from '{source}' rejected: AI_AGENT feature is DISABLED.")
                return False

            if self._current_state in (AgentState.ACTIVATING, AgentState.ACTIVE, AgentState.PROCESSING):
                logger.info(f"[AGENT] Already active or activating (current: {self._current_state.value}).")
                return True

            logger.info(f"[AGENT] activated via {source}")
            self._current_state = AgentState.ACTIVATING
            self._active_source = source

        # Emit state and trigger UI animation to TOP-RIGHT
        self.signals.state_changed.emit(AgentState.ACTIVATING.value, f"Activating via {source}...")
        self.signals.position_requested.emit("top_right", duration_ms)
        self.signals.companion_mood.emit("thinking", "Waking up...")

        # Schedule transition to ACTIVE upon animation completion
        QTimer.singleShot(duration_ms, self._finalize_activation)
        return True

    def _finalize_activation(self):
        with self._state_lock:
            if self._current_state == AgentState.ACTIVATING:
                self._current_state = AgentState.ACTIVE
                logger.info(f"[AGENT] Transitioned to ACTIVE state (source: {self._active_source})")
        self.signals.state_changed.emit(AgentState.ACTIVE.value, "AI Agent Active")
        self.signals.companion_mood.emit("idle", "Ready to assist!")
        self.signals.agent_activated.emit(self._active_source)

    def deactivate(self, source: str = "dashboard", duration_ms: int = 650) -> bool:
        """
        Unified deactivation endpoint:
        Transitions: ACTIVE/PROCESSING -> DEACTIVATING -> (smooth animation to BOTTOM-RIGHT) -> RESTING.
        """
        with self._state_lock:
            if self._current_state in (AgentState.RESTING, AgentState.DEACTIVATING, AgentState.DISABLED):
                logger.info(f"[AGENT] Already resting or deactivating (current: {self._current_state.value}).")
                return True

            logger.info(f"[AGENT] deactivated via {source}")
            self._current_state = AgentState.DEACTIVATING
            self._active_source = source

        # Emit state and trigger UI animation to BOTTOM-RIGHT
        self.signals.state_changed.emit(AgentState.DEACTIVATING.value, f"Deactivating via {source}...")
        self.signals.position_requested.emit("bottom_right", duration_ms)
        self.signals.companion_mood.emit("idle", "Resting...")

        # Schedule transition to RESTING upon animation completion
        QTimer.singleShot(duration_ms, self._finalize_deactivation)
        return True

    def _finalize_deactivation(self):
        with self._state_lock:
            if self._current_state == AgentState.DEACTIVATING:
                if not self._feature_manager.is_enabled(Feature.AI_AGENT):
                    self._current_state = AgentState.DISABLED
                else:
                    self._current_state = AgentState.RESTING
                logger.info(f"[AGENT] Transitioned to {self._current_state.value} state (source: {self._active_source})")
        msg = "Resting" if self._current_state == AgentState.RESTING else "AI Agent Disabled"
        mood_msg = "Zzz..." if self._current_state == AgentState.RESTING else "Agent Disabled"
        self.signals.state_changed.emit(self._current_state.value, msg)
        self.signals.companion_mood.emit("idle", mood_msg)
        self.signals.agent_deactivated.emit(self._active_source)

    def toggle(self, source: str = "dashboard") -> bool:
        """Toggles between Active and Resting states."""
        if self.is_active:
            return self.deactivate(source=source)
        else:
            return self.activate(source=source)

    def set_processing(self, message: str = "Thinking..."):
        """Sets the agent into PROCESSING mode (while active)."""
        with self._state_lock:
            if self.is_active:
                self._current_state = AgentState.PROCESSING
                logger.info(f"[AGENT] Processing: {message}")
        self.signals.state_changed.emit(AgentState.PROCESSING.value, message)
        self.signals.companion_mood.emit("thinking", message)

    def set_idle(self, message: str = "Ready"):
        """Returns agent to normal ACTIVE state."""
        with self._state_lock:
            if self._current_state == AgentState.PROCESSING:
                self._current_state = AgentState.ACTIVE
        self.signals.state_changed.emit(self._current_state.value, message)
        self.signals.companion_mood.emit("idle", message)

    def set_error(self, message: str):
        """Notifies UI of an error without stopping unrelated operations."""
        logger.warning(f"[AGENT] Error: {message}")
        self.signals.companion_mood.emit("error", message)


def get_agent_controller() -> AgentController:
    return AgentController.get_instance()
