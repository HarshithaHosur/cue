# ============================================================
#  UNIFIED INTENT ENGINE — Vision, Voice, Cursor & Security
#  Central coordinator running MediaPipe vision, continuous
#  face authentication, gesture tracking, virtual cursor,
#  voice listening, scroll mode, and companion synchronization.
# ============================================================

import logging
import sys
import time
import math
import cv2
import numpy as np
from typing import Optional, Dict, Any

from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtGui import QImage

try:
    import mediapipe as mp
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False

import pyautogui

from intent_platform.config.settings import (
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_FPS,
    ACTIVATION_TIME,
    INACTIVITY_TIMEOUT
)
from intent_platform.core.cursor.cursor_controller import CursorController
from intent_platform.core.gesture.recognizer import GestureRecognizer
from intent_platform.core.gesture.executor import execute_gesture
from intent_platform.core.auth.ownership_verifier import HandOwnershipVerifier
from intent_platform.core.voice.voice_engine import VoiceEngine
from intent_platform.core.context.context_manager import ContextManager
from intent_platform.core.features.feature_manager import Feature, FeatureStatus, get_feature_manager
from intent_platform.core.agent.agent_controller import AgentState, get_agent_controller
from intent_platform.core.events.event_dispatcher import InputEvent, EventPriority, get_event_dispatcher
from intent_platform.database.connection import db

logger = logging.getLogger("IntentEngine")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class IntentEngineSignals(QObject):
    """Qt Signals emitted by the background engine threads to the UI."""
    frame_ready = Signal(QImage)
    gesture_detected = Signal(str, str)             # gesture, action
    voice_detected = Signal(str, str)               # transcript, action
    companion_state = Signal(str, str)              # state, message
    system_status = Signal(dict)                    # telemetry dict
    mode_changed = Signal(str)                      # "idle", "active", "cursor", "scroll"


class IntentEngine(QThread):
    """Main processing thread managing camera loop, security, and HCI subsystems."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = IntentEngineSignals()

        # Global singletons
        self._feature_manager = get_feature_manager()
        self._agent_controller = get_agent_controller()
        self._event_dispatcher = get_event_dispatcher()

        # Subsystems
        self.cursor_controller = CursorController()
        self.gesture_recognizer = GestureRecognizer()
        self.security_verifier = HandOwnershipVerifier()

        # Interview Hooks
        self.frame_taps = []
        self.gesture_interceptor = None

        # Engine & Agent State
        self.is_running = False
        self.current_mode = "idle"                  # "idle", "active", "cursor", "scroll"
        self.last_interaction_time = time.time()
        self.activation_start_time = 0.0
        self.is_activating = False

        # Two-Hand Scroll Mode State
        self.scroll_start_time = 0.0
        self.is_holding_two_palms = False
        self.last_scroll_y: Optional[float] = None

        # Continuous Authentication State
        self.user_profile: Optional[Dict[str, Any]] = None
        self.auth_lost_active = False

        # Voice Subsystem
        self.voice_engine = VoiceEngine(
            on_status_change=self._on_voice_status,
            on_command_detected=self._on_voice_command
        )

        # Connect Agent Controller lifecycle signals
        self._agent_controller.signals.agent_activated.connect(self._on_agent_activated)
        self._agent_controller.signals.agent_deactivated.connect(self._on_agent_deactivated)
        self._feature_manager.signals.feature_toggled.connect(self._on_feature_toggled)

        # MediaPipe setup
        self.holistic = None
        if MP_AVAILABLE:
            try:
                self.mp_holistic = mp.solutions.holistic
                self.holistic = self.mp_holistic.Holistic(
                    static_image_mode=False,
                    model_complexity=1,
                    min_detection_confidence=0.6,
                    min_tracking_confidence=0.5,
                    smooth_landmarks=True
                )
            except Exception as e:
                logger.warning(f"[VISION] MediaPipe Holistic init failed: {e}")
                self.holistic = None

    @property
    def is_agent_active(self) -> bool:
        return self._agent_controller.is_active

    def _on_feature_toggled(self, feature: str, enabled: bool):
        if feature == Feature.MOUSE.value and not enabled:
            self.cursor_controller.release()
            if self.current_mode == "cursor":
                self._switch_mode("idle")

    def _on_agent_activated(self, source: str):
        logger.info(f"[ENGINE] AI Agent activated via '{source}'")
        self.current_mode = "idle"
        self.voice_engine.set_paused(False)
        self.signals.companion_state.emit("idle", "AI Agent Activated")

    def _on_agent_deactivated(self, source: str):
        logger.info(f"[ENGINE] AI Agent deactivated via '{source}'")
        self.cursor_controller.release()
        self.voice_engine.set_paused(True)
        self._switch_mode("idle")
        self.signals.companion_state.emit("idle", "AI Agent Deactivated")

    def set_authenticated_user(self, profile: dict):
        """Receives authenticated user profile and initializes continuous biometric verification."""
        self.user_profile = profile
        if profile and profile.get("face_encoding"):
            self.security_verifier.set_authenticated_encoding(profile.get("face_encoding"))

    def activate_agent(self):
        """Initializes all modules through unified AgentController."""
        self._agent_controller.activate(source="button")
        self.voice_engine.set_paused(False)
        self.voice_engine.speak("AI Agent Activated")

    def deactivate_agent(self):
        """Safely deactivates through unified AgentController."""
        self._agent_controller.deactivate(source="button")
        self.voice_engine.set_paused(True)
        self.voice_engine.speak("AI Agent Deactivated")

    def _on_voice_status(self, status: str):
        if self.is_agent_active and not self.auth_lost_active:
            if status == "Listening":
                self.signals.companion_state.emit("listening", "Listening...")

    def _on_voice_command(self, transcript: str, action: str):
        if self.auth_lost_active:
            return
        self.last_interaction_time = time.time()
        self.signals.voice_detected.emit(transcript, action)
        self.signals.companion_state.emit("success", f"Completed: {action}")

    def run(self):
        """Main vision, security verification, and tracking loop."""
        self.is_running = True
        logger.info("[ENGINE] Vision & tracking loop started.")
        self.voice_engine.start()

        cap = None
        if self._feature_manager.is_enabled(Feature.VISION):
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)

            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                self._feature_manager.set_status(Feature.VISION, FeatureStatus.RUNNING.value)
            else:
                logger.warning("[VISION] Camera unavailable.")
                self._feature_manager.set_status(Feature.VISION, FeatureStatus.UNAVAILABLE.value)
                cap = None

        prev_time = time.time()

        while self.is_running:
            # If Vision feature is disabled or camera unavailable
            if not self._feature_manager.is_enabled(Feature.VISION) or cap is None:
                if cap is not None:
                    cap.release()
                    cap = None
                    self._feature_manager.set_status(Feature.VISION, FeatureStatus.DISABLED.value)
                time.sleep(0.05)
                # Attempt camera re-acquisition if re-enabled
                if self._feature_manager.is_enabled(Feature.VISION) and cap is None:
                    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        cap = cv2.VideoCapture(0)
                    if cap.isOpened():
                        self._feature_manager.set_status(Feature.VISION, FeatureStatus.RUNNING.value)
                    else:
                        cap = None
                continue

            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.03)
                continue

            now = time.time()
            dt = now - prev_time
            prev_time = now
            fps = 1.0 / dt if dt > 0 else 30.0

            # Flip for selfie-view
            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            for tap in self.frame_taps:
                try:
                    tap(frame)
                except Exception as e:
                    logger.error(f"Frame tap error: {e}")

            right_hand_landmarks = None
            left_hand_landmarks = None
            pose_landmarks = None

            if self.holistic is not None and self._feature_manager.is_enabled(Feature.GESTURE):
                results = self.holistic.process(frame_rgb)
                pose_landmarks = results.pose_landmarks
                right_hand_landmarks = results.right_hand_landmarks
                left_hand_landmarks = results.left_hand_landmarks

            # Primary hand for single-hand gestures (prefer right hand, fallback to left)
            primary_hand = right_hand_landmarks or left_hand_landmarks

            # ── CONTINUOUS AUTHENTICATION VERIFICATION ──
            security_res = self.security_verifier.verify(
                frame_rgb,
                primary_hand.landmark if primary_hand else None,
                pose_landmarks
            )

            context_app = ContextManager.detect_context()

            # ── REQUIREMENT: Immediate Pause on Authentication Loss ──
            if security_res.auth_lost:
                if not self.auth_lost_active:
                    self.auth_lost_active = True
                    self.voice_engine.set_paused(True)
                    self.cursor_controller.release()
                    self._switch_mode("idle")
                    self.signals.companion_state.emit("error", "Authentication Lost - Agent Paused")

                telemetry = {
                    "fps": int(fps),
                    "mode": "paused",
                    "context": context_app,
                    "security": "Authentication Lost - Agent Paused",
                    "face_ok": False,
                    "hand_visible": primary_hand is not None
                }
                self.signals.system_status.emit(telemetry)
                self._emit_frame(frame)
                time.sleep(0.03)
                continue

            # Auth is valid: recover from auth lost state
            if self.auth_lost_active:
                self.auth_lost_active = False
                self.voice_engine.set_paused(False)
                self.signals.companion_state.emit("idle", "User Verified - Resuming")

            # Check inactivity timeout
            if self.current_mode != "idle" and (now - self.last_interaction_time) > INACTIVITY_TIMEOUT:
                self._switch_mode("idle")
                self.signals.companion_state.emit("idle", "Idle mode activated")

            # ── GESTURE & TRACKING DISPATCH ──
            if self._feature_manager.is_enabled(Feature.GESTURE):
                # 1. Dual-hand coordination (Two Open Palms / Two Peace Signs)
                both_hands_present = (right_hand_landmarks is not None and left_hand_landmarks is not None)
                if both_hands_present:
                    self._process_two_hands(right_hand_landmarks.landmark, left_hand_landmarks.landmark)

                # 2. In Scroll Mode: track hand vertical movement
                if self.current_mode == "scroll":
                    if primary_hand:
                        self._process_scroll(primary_hand.landmark)
                # 3. Single-hand gestures & cursor
                elif primary_hand and security_res.gesture_ready:
                    self._process_single_hand(primary_hand.landmark, frame, context_app)
                elif self.is_activating:
                    self.is_activating = False
                    self.activation_start_time = 0.0

            # Telemetry status
            telemetry = {
                "fps": int(fps),
                "mode": self.current_mode,
                "context": context_app,
                "security": security_res.reason,
                "face_ok": True,
                "hand_visible": primary_hand is not None
            }
            self.signals.system_status.emit(telemetry)

            # Render frame
            self._emit_frame(frame)
            time.sleep(0.01)

        if cap is not None:
            cap.release()
        self.cursor_controller.release()
        self.voice_engine.stop()
        logger.info("[ENGINE] Vision & tracking loop stopped.")

    def _emit_frame(self, frame: np.ndarray):
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_BGR888).copy()
        self.signals.frame_ready.emit(q_img)

    def _switch_mode(self, new_mode: str):
        if self.current_mode != new_mode:
            self.current_mode = new_mode
            if new_mode != "cursor":
                self.cursor_controller.reset()
            if new_mode != "scroll":
                self.last_scroll_y = None
                self.is_holding_two_palms = False
            self.signals.mode_changed.emit(new_mode)

    def _process_two_hands(self, hand1_landmarks, hand2_landmarks):
        """Evaluates Two Open Palms (hold ~1.8s -> Scroll Mode) and Two Peace Signs (deactivate scroll)."""
        now = time.time()
        two_hands_gesture = self.gesture_recognizer.detect_two_hands(hand1_landmarks, hand2_landmarks)

        # Two Peace Signs -> Deactivate Scroll Mode
        if two_hands_gesture == 'two_peace_signs' and self.current_mode == "scroll":
            self._switch_mode("active")
            self.signals.companion_state.emit("idle", "Scroll Mode Disabled")
            self.voice_engine.speak("Scroll Mode Deactivated")
            self.last_interaction_time = now
            return

        # Two Open Palms held steadily -> Activate Scroll Mode
        if two_hands_gesture == 'two_open_palms':
            if not self.is_holding_two_palms:
                self.is_holding_two_palms = True
                self.scroll_start_time = now
            elif (now - self.scroll_start_time) >= 1.8 and self.current_mode != "scroll":
                self._switch_mode("scroll")
                self.is_holding_two_palms = False
                self.last_interaction_time = now
                self.signals.companion_state.emit("success", "Scroll Mode Enabled")
                self.voice_engine.speak("Scroll Mode Enabled")
        else:
            self.is_holding_two_palms = False

    def _process_scroll(self, landmarks):
        """Translates hand vertical movement into smooth continuous scrolling."""
        if not self._feature_manager.is_enabled(Feature.MOUSE):
            return

        current_y = (landmarks[0].y + landmarks[9].y) / 2.0
        now = time.time()
        self.last_interaction_time = now

        if self.last_scroll_y is not None:
            dy = self.last_scroll_y - current_y
            abs_dy = abs(dy)
            if abs_dy > 0.004:
                sign = 1 if dy > 0 else -1
                sensitivity = 1400.0
                step = abs_dy * sensitivity + (abs_dy ** 1.6) * sensitivity * 2.5
                clicks = int(sign * step)
                if clicks != 0:
                    def _scroll():
                        if sys.platform == 'win32':
                            import ctypes
                            wheel_delta = clicks * 15
                            ctypes.windll.user32.mouse_event(0x0800, 0, 0, wheel_delta, 0)
                        else:
                            pyautogui.scroll(clicks * 5)
                    self._event_dispatcher.dispatch(
                        InputEvent(priority=EventPriority.MOUSE, source="GESTURE_SCROLL", event_type="scroll"),
                        _scroll
                    )

        self.last_scroll_y = current_y

    def _process_single_hand(self, landmarks, frame_bgr, context_app: str):
        now = time.time()
        static_gesture = self.gesture_recognizer.detect_static_gesture(landmarks)

        # ── Gesture-driven AI Agent Activation / Deactivation ──
        if static_gesture == 'palm' and self.current_mode == "idle":
            if not self.is_activating:
                self.is_activating = True
                self.activation_start_time = now
            elif (now - self.activation_start_time) >= ACTIVATION_TIME:
                self.is_activating = False
                self._switch_mode("active")
                self.last_interaction_time = now
                self._agent_controller.activate(source="gesture")
                self.voice_engine.speak("System ready")
                return

        # ── Cursor Mode Activation (ONLY Index Finger) ──
        if static_gesture == 'index_cursor' and self.current_mode != "cursor":
            if self._feature_manager.is_enabled(Feature.MOUSE):
                self._switch_mode("cursor")
                self.cursor_controller.reset()
                self.signals.companion_state.emit("thinking", "Cursor Enabled")
                self.last_interaction_time = now
                return

        # ── Cursor Mode Deactivation (One Peace Sign) ──
        if static_gesture == 'peace' and self.current_mode == "cursor":
            self._switch_mode("active")
            self.cursor_controller.reset()
            self.signals.companion_state.emit("idle", "Cursor Deactivated")
            self.last_interaction_time = now
            return

        # ── Active Cursor Tracking ──
        if self.current_mode == "cursor" and self._feature_manager.is_enabled(Feature.MOUSE):
            self.cursor_controller.update(landmarks, frame_bgr)
            self.last_interaction_time = now
            return

        # ── Context-Aware Gesture Execution (Thumbs Up/Down, Fist, Swipes) ──
        recognized = self.gesture_recognizer.recognize(landmarks)
        if recognized and recognized not in ('palm', 'peace', 'index_cursor'):
            current_context = ContextManager.detect_context()
            
            action_label = None
            if self.gesture_interceptor:
                try:
                    action_label = self.gesture_interceptor(recognized, current_context)
                except Exception as e:
                    logger.error(f"Gesture interceptor error: {e}")
            
            if action_label is None:
                # Dispatch execution asynchronously via EventDispatcher so gesture loop is never blocked!
                def _do_gesture():
                    return execute_gesture(recognized, current_context)
                
                event = InputEvent(
                    priority=EventPriority.GESTURE,
                    source="GESTURE",
                    event_type=recognized,
                    payload={"context": current_context}
                )

                def _on_gesture_done(label_res):
                    if label_res:
                        self.signals.gesture_detected.emit(recognized, label_res)
                        if recognized == 'fist':
                            self.signals.companion_state.emit("success", "Screenshot Saved")
                        elif 'swipe' in recognized:
                            self.signals.companion_state.emit("success", f"Gesture: {label_res}")
                        else:
                            self.signals.companion_state.emit("success", f"{label_res}")

                self._event_dispatcher.dispatch(event, lambda: _on_gesture_done(_do_gesture()))

    def stop(self):
        """Clean shutdown of engine."""
        self.is_running = False
        self.wait(1500)
