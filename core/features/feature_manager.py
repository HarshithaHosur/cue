# ============================================================
#  CENTRAL RUNTIME FEATURE MANAGER — Real-Time Capabilities Control
#  Controls active runtime state for Voice, Gesture, Mouse,
#  Vision, and AI Agent subsystems with persistent settings.
# ============================================================

import json
import logging
import os
import threading
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("FeatureManager")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class Feature(str, Enum):
    VOICE = "voice"
    GESTURE = "gesture"
    MOUSE = "mouse"
    VISION = "vision"
    AI_AGENT = "ai_agent"


class FeatureStatus(str, Enum):
    RUNNING = "Running"
    PAUSED = "Paused"
    DISABLED = "Disabled"
    UNAVAILABLE = "Unavailable"
    ERROR = "Error"


class FeatureSignals(QObject):
    """Qt Signals emitted on feature state modifications."""
    feature_toggled = Signal(str, bool)               # feature_id, is_enabled
    feature_status_changed = Signal(str, str)         # feature_id, status_str
    all_features_updated = Signal(dict)               # summary dict of all features


class FeatureManager:
    """Central singleton managing feature switches, real status, and persistence."""

    _instance: Optional["FeatureManager"] = None
    _lock = threading.RLock()

    def __init__(self):
        self.signals = FeatureSignals()
        self._state_lock = threading.RLock()
        self._config_file = Path(__file__).resolve().parent.parent.parent / "config" / "features_config.json"

        # Default features configuration
        self._enabled: Dict[str, bool] = {
            Feature.VOICE.value: True,
            Feature.GESTURE.value: True,
            Feature.MOUSE.value: True,
            Feature.VISION.value: True,
            Feature.AI_AGENT.value: True,
        }

        # Real-time runtime status
        self._status: Dict[str, str] = {
            Feature.VOICE.value: FeatureStatus.RUNNING.value,
            Feature.GESTURE.value: FeatureStatus.RUNNING.value,
            Feature.MOUSE.value: FeatureStatus.RUNNING.value,
            Feature.VISION.value: FeatureStatus.RUNNING.value,
            Feature.AI_AGENT.value: FeatureStatus.RUNNING.value,
        }

        self._load_persisted_state()

    @classmethod
    def get_instance(cls) -> "FeatureManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = FeatureManager()
            return cls._instance

    def _load_persisted_state(self):
        """Loads persistent feature toggles from disk if available."""
        try:
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if k in self._enabled:
                            self._enabled[k] = bool(v)
                            if not v:
                                self._status[k] = FeatureStatus.DISABLED.value
                logger.info(f"[FEATURE_INIT] Loaded persisted state: {self._enabled}")
        except Exception as e:
            logger.warning(f"[FEATURE_INIT] Could not load persisted feature state: {e}")

    def _save_persisted_state(self):
        """Saves current feature configuration to disk."""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._enabled, f, indent=2)
        except Exception as e:
            logger.warning(f"[FEATURE_SAVE] Could not save feature state: {e}")

    def is_enabled(self, feature: str) -> bool:
        """Returns True if the feature is enabled by the user."""
        feat_key = feature.value if isinstance(feature, Feature) else str(feature).lower()
        with self._state_lock:
            return self._enabled.get(feat_key, True)

    def get_status(self, feature: str) -> str:
        """Returns the current real runtime status of the feature."""
        feat_key = feature.value if isinstance(feature, Feature) else str(feature).lower()
        with self._state_lock:
            return self._status.get(feat_key, FeatureStatus.UNAVAILABLE.value)

    def set_enabled(self, feature: str, enabled: bool):
        """
        Enables or disables a feature at runtime.
        Updates status, logs event, emits signal, and persists preference.
        """
        feat_key = feature.value if isinstance(feature, Feature) else str(feature).lower()
        with self._state_lock:
            old_val = self._enabled.get(feat_key)
            if old_val == enabled:
                return

            self._enabled[feat_key] = enabled
            if not enabled:
                self._status[feat_key] = FeatureStatus.DISABLED.value
            else:
                self._status[feat_key] = FeatureStatus.RUNNING.value

            logger.info(f"[FEATURE] {feat_key.upper()} {'ENABLED' if enabled else 'DISABLED'}")
            self._save_persisted_state()

        # Emit signals
        self.signals.feature_toggled.emit(feat_key, enabled)
        self.signals.feature_status_changed.emit(feat_key, self._status[feat_key])
        self.signals.all_features_updated.emit(self.get_all_states())

    def set_status(self, feature: str, status: str):
        """Updates the operational status of a feature (e.g. Unavailable, Error, Running)."""
        feat_key = feature.value if isinstance(feature, Feature) else str(feature).lower()
        status_val = status.value if isinstance(status, FeatureStatus) else str(status)
        with self._state_lock:
            # If user explicitly disabled the feature, keep it as DISABLED unless being enabled
            if not self._enabled.get(feat_key, True) and status_val != FeatureStatus.DISABLED.value:
                return

            if self._status.get(feat_key) == status_val:
                return

            self._status[feat_key] = status_val
            logger.info(f"[FEATURE_STATUS] {feat_key.upper()} status changed to: {status_val}")

        self.signals.feature_status_changed.emit(feat_key, status_val)
        self.signals.all_features_updated.emit(self.get_all_states())

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Returns complete snapshot of all features and their statuses."""
        with self._state_lock:
            return {
                feat: {
                    "enabled": self._enabled.get(feat, True),
                    "status": self._status.get(feat, FeatureStatus.UNAVAILABLE.value)
                }
                for feat in self._enabled
            }


def get_feature_manager() -> FeatureManager:
    return FeatureManager.get_instance()
