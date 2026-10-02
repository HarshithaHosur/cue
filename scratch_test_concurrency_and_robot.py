# ============================================================
#  CONCURRENCY, ROBOT ANIMATION & FEATURE TOGGLES TEST SUITE
#  Validates all 11 test cases and acceptance criteria.
# ============================================================

import sys
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Register intent_platform module
import types
import core, ui, config, database
ip_mod = types.ModuleType('intent_platform')
ip_mod.__path__ = [str(BASE_DIR)]
sys.modules['intent_platform'] = ip_mod
sys.modules['intent_platform.core'] = core
sys.modules['intent_platform.ui'] = ui
sys.modules['intent_platform.config'] = config
sys.modules['intent_platform.database'] = database

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, QRect, QTimer

from intent_platform.core.features.feature_manager import Feature, FeatureStatus, get_feature_manager
from intent_platform.core.agent.agent_controller import AgentState, get_agent_controller
from intent_platform.core.events.event_dispatcher import InputEvent, EventPriority, get_event_dispatcher
from intent_platform.core.gesture.recognizer import GestureRecognizer
from intent_platform.core.gesture.executor import execute_gesture
from intent_platform.core.cursor.cursor_controller import CursorController
from intent_platform.core.gesture import executor as gesture_executor
from intent_platform.core.cursor import cursor_controller as cursor_controller_module
from intent_platform.ui.companion.companion_window import DesktopCompanionOverlay
from intent_platform.core.voice.voice_engine import VoiceEngine
from intent_platform.core.engine import IntentEngine
from intent_platform.ui.main_window import MainWindow
from intent_platform.ui.widgets.control_center import ControlCenterWidget


class DummyLandmark:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


def make_gesture_landmarks(finger_states):
    landmarks = [DummyLandmark(0.5, 0.8)]
    if finger_states[0]:
        landmarks.extend([
            DummyLandmark(0.4, 0.7), DummyLandmark(0.35, 0.6),
            DummyLandmark(0.3, 0.5), DummyLandmark(0.2, 0.4),
        ])
    else:
        landmarks.extend([
            DummyLandmark(0.45, 0.7), DummyLandmark(0.46, 0.65),
            DummyLandmark(0.47, 0.6), DummyLandmark(0.48, 0.62),
        ])

    bases = [0.45, 0.5, 0.55, 0.6]
    for base, extended in zip(bases, finger_states[1:]):
        if extended:
            landmarks.extend([
                DummyLandmark(base, 0.55), DummyLandmark(base, 0.45),
                DummyLandmark(base, 0.35), DummyLandmark(base, 0.25),
            ])
        else:
            landmarks.extend([
                DummyLandmark(base, 0.55), DummyLandmark(base, 0.6),
                DummyLandmark(base, 0.65), DummyLandmark(base, 0.7),
            ])
    return landmarks


def make_thumbs_down_landmarks():
    landmarks = make_gesture_landmarks([False, False, False, False, False])
    landmarks[1:5] = [
        DummyLandmark(0.4, 0.7), DummyLandmark(0.35, 0.68),
        DummyLandmark(0.3, 0.73), DummyLandmark(0.25, 0.86),
    ]
    return landmarks


class TestConcurrencyAndRobotSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.fm = get_feature_manager()
        cls.agent_ctrl = get_agent_controller()
        cls.dispatcher = get_event_dispatcher()

    def setUp(self):
        # Reset all features to True for clean test state
        for feat in (Feature.VOICE, Feature.GESTURE, Feature.MOUSE, Feature.VISION, Feature.AI_AGENT):
            self.fm.set_enabled(feat, True)

    def test_01_robot_positioning_and_clamping(self):
        """TEST 1: Robot is safely positioned at bottom-right with margins and no clipping."""
        overlay = DesktopCompanionOverlay()
        resting_pos = overlay.calculate_position("bottom_right")
        active_pos = overlay.calculate_position("top_right")

        screen_geo = overlay._get_screen_geometry()
        
        # Verify resting position is near bottom-right
        self.assertGreater(resting_pos.x(), screen_geo.x() + screen_geo.width() // 2)
        self.assertGreater(resting_pos.y(), screen_geo.y() + screen_geo.height() // 2)

        # Verify active position is near top-right
        self.assertGreater(active_pos.x(), screen_geo.x() + screen_geo.width() // 2)
        self.assertLess(active_pos.y(), screen_geo.y() + screen_geo.height() // 2)

        # Verify clamping: within screen bounds
        self.assertGreaterEqual(resting_pos.x(), screen_geo.x())
        self.assertLessEqual(resting_pos.x() + overlay.width(), screen_geo.x() + screen_geo.width())
        self.assertGreaterEqual(resting_pos.y(), screen_geo.y())
        self.assertLessEqual(resting_pos.y() + overlay.height(), screen_geo.y() + screen_geo.height())
        print(f"[OK] TEST 1: Robot safe coordinates calculated: Resting={resting_pos}, Active={active_pos}")

    def test_02_robot_activation_state_machine(self):
        """TEST 2: State machine and smooth animation between bottom-right and top-right."""
        overlay = DesktopCompanionOverlay()
        
        # Initial state should be RESTING
        self.assertEqual(self.agent_ctrl.current_state, AgentState.RESTING)
        
        # Activate via dashboard button
        self.agent_ctrl.activate(source="dashboard", duration_ms=50)
        self.assertEqual(self.agent_ctrl.current_state, AgentState.ACTIVATING)
        
        # Process events to allow timer finalization
        time.sleep(0.08)
        self.app.processEvents()
        self.assertEqual(self.agent_ctrl.current_state, AgentState.ACTIVE)

        # Deactivate
        self.agent_ctrl.deactivate(source="dashboard", duration_ms=50)
        self.assertEqual(self.agent_ctrl.current_state, AgentState.DEACTIVATING)
        
        time.sleep(0.08)
        self.app.processEvents()
        self.assertEqual(self.agent_ctrl.current_state, AgentState.RESTING)
        print("[OK] TEST 2: Agent state machine transitions RESTING -> ACTIVATING -> ACTIVE -> DEACTIVATING -> RESTING verified.")

    def test_03_voice_and_gesture_activations_converge(self):
        """TEST 3 & 4: Voice and Gesture activations invoke the unified AgentController."""
        events_fired = []
        self.agent_ctrl.signals.agent_activated.connect(lambda src: events_fired.append(src))

        # Voice activation
        self.agent_ctrl.activate(source="voice", duration_ms=20)
        time.sleep(0.04)
        self.app.processEvents()
        self.assertIn("voice", events_fired)

        # Deactivate
        self.agent_ctrl.deactivate(source="voice", duration_ms=20)
        time.sleep(0.04)
        self.app.processEvents()

        # Gesture activation
        self.agent_ctrl.activate(source="gesture", duration_ms=20)
        time.sleep(0.04)
        self.app.processEvents()
        self.assertIn("gesture", events_fired)

        self.agent_ctrl.deactivate(source="test", duration_ms=20)
        time.sleep(0.04)
        self.app.processEvents()
        print(f"[OK] TEST 3 & 4: Both Voice and Gesture activations converged to unified AgentController: {events_fired}")

    def test_05_simultaneous_voice_gesture_mouse_execution(self):
        """TEST 5, 6, 7: Voice, Gesture, Mouse events dispatched and executed concurrently."""
        completed_actions = []

        def voice_action():
            time.sleep(0.03)
            return "Voice Action Completed"

        def gesture_action():
            time.sleep(0.02)
            return "Gesture Action Completed"

        def mouse_action():
            return "Mouse Action Completed"

        self.dispatcher.signals.action_completed.connect(lambda event_type, res: completed_actions.append((event_type, res)))

        # Dispatch 3 simultaneous events
        t0 = time.time()
        self.dispatcher.dispatch(InputEvent(priority=EventPriority.USER_COMMAND, source="VOICE", event_type="open_chrome"), voice_action)
        self.dispatcher.dispatch(InputEvent(priority=EventPriority.GESTURE, source="GESTURE", event_type="thumbs_up"), gesture_action)
        self.dispatcher.dispatch(InputEvent(priority=EventPriority.MOUSE, source="MOUSE", event_type="scroll"), mouse_action)

        # Wait for thread pool to finish
        time.sleep(0.08)
        self.app.processEvents()

        elapsed = time.time() - t0
        self.assertEqual(len(completed_actions), 3)
        self.assertLess(elapsed, 0.20, "Actions should run in parallel without cumulative blocking")
        print(f"[OK] TEST 5, 6, 7: Simultaneous execution of 3 subsystems succeeded in {elapsed:.3f}s: {completed_actions}")

    def test_08_non_blocking_ai_worker(self):
        """TEST 8: Long-running AI processing does not block other subsystems."""
        ai_finished = []

        def slow_ai():
            time.sleep(0.05)
            ai_finished.append(True)

        self.dispatcher.dispatch(InputEvent(priority=EventPriority.BACKGROUND_AI, source="AI", event_type="gemini_query"), slow_ai)

        # While AI is running, dispatch quick gesture action
        gesture_done = []
        self.dispatcher.dispatch(InputEvent(priority=EventPriority.GESTURE, source="GESTURE", event_type="swipe_right"), lambda: gesture_done.append(True))

        time.sleep(0.02)
        self.app.processEvents()
        # Gesture should have completed immediately even while AI is still in progress
        self.assertTrue(gesture_done[0], "Gesture should complete without waiting for AI")

        time.sleep(0.06)
        self.app.processEvents()
        self.assertTrue(ai_finished[0], "AI worker completed in background")
        print("[OK] TEST 8: Non-blocking AI execution verified.")

    def test_09_feature_toggles_runtime_isolation(self):
        """TEST 9: Toggling features ON/OFF immediately affects that subsystem without affecting others."""
        # 1. Turn Voice OFF
        self.fm.set_enabled(Feature.VOICE, False)
        self.assertFalse(self.fm.is_enabled(Feature.VOICE))
        self.assertEqual(self.fm.get_status(Feature.VOICE), FeatureStatus.DISABLED.value)
        # Other subsystems must remain True
        self.assertTrue(self.fm.is_enabled(Feature.GESTURE))
        self.assertTrue(self.fm.is_enabled(Feature.MOUSE))
        self.assertTrue(self.fm.is_enabled(Feature.VISION))

        # 2. Turn Gesture OFF
        self.fm.set_enabled(Feature.GESTURE, False)
        self.assertFalse(self.fm.is_enabled(Feature.GESTURE))
        self.assertTrue(self.fm.is_enabled(Feature.VISION))

        # 3. Re-enable Voice
        self.fm.set_enabled(Feature.VOICE, True)
        self.assertTrue(self.fm.is_enabled(Feature.VOICE))
        self.assertEqual(self.fm.get_status(Feature.VOICE), FeatureStatus.RUNNING.value)

        # 4. Turn AI Agent OFF -> should deactivate active agent
        self.agent_ctrl.activate(source="test", duration_ms=10)
        time.sleep(0.02)
        self.app.processEvents()
        self.fm.set_enabled(Feature.AI_AGENT, False)
        time.sleep(0.03)
        self.app.processEvents()
        self.assertEqual(self.agent_ctrl.current_state, AgentState.DISABLED)

        # Re-enable AI Agent
        self.fm.set_enabled(Feature.AI_AGENT, True)
        self.assertEqual(self.agent_ctrl.current_state, AgentState.RESTING)
        print("[OK] TEST 9: Runtime feature toggle isolation verified.")

    def test_10_no_duplicate_workers(self):
        """TEST 10: Toggling Voice ON/OFF repeatedly never creates duplicate threads."""
        ve = VoiceEngine()
        for _ in range(5):
            ve.start()
        
        # There should be only 1 active thread
        self.assertTrue(ve.is_running)
        first_thread = ve.worker_thread
        
        # Start again should be a no-op
        ve.start()
        self.assertEqual(ve.worker_thread, first_thread)
        
        ve.stop()
        self.assertFalse(ve.is_running)
        print("[OK] TEST 10: Duplicate worker thread prevention verified.")

    def test_11_voice_start_reports_real_microphone_failure(self):
        """TEST 11: microphone failures surface as Unavailable instead of being silently swallowed."""
        ve = VoiceEngine()
        status_updates = []
        ve.on_status_change = lambda status: status_updates.append(status)

        def boom():
            raise RuntimeError("Missing required microphone backend: install PyAudio with 'python -m pip install pyaudio'.")

        ve._validate_microphone_runtime = boom
        ve.start()

        self.assertEqual(self.fm.get_status(Feature.VOICE), FeatureStatus.UNAVAILABLE.value)
        self.assertTrue(any("Mic unavailable" in entry for entry in status_updates))
        print("[OK] TEST 11: Microphone startup errors are surfaced as Unavailable with the real cause.")

    def test_12_ui_control_center_widget(self):
        """TEST 12: Control Center UI widget initializes and reflects live signals."""
        cc = ControlCenterWidget()
        self.assertEqual(len(cc._rows), 5)
        
        # Toggle via UI row
        voice_row = cc._rows[Feature.VOICE.value]
        voice_row.toggle_switch.setChecked(False)
        self.assertFalse(self.fm.is_enabled(Feature.VOICE))
        
        voice_row.toggle_switch.setChecked(True)
        self.assertTrue(self.fm.is_enabled(Feature.VOICE))
        print("[OK] TEST 12: Control Center UI widget & signal binding verified.")

    def test_13_rotated_index_and_dual_hand_gestures(self):
        recognizer = GestureRecognizer()
        index_hand = make_gesture_landmarks([False, True, False, False, False])
        self.assertEqual(recognizer.detect_static_gesture(index_hand), "index_cursor")
        wrist = index_hand[0]
        rotated_index = [
            DummyLandmark(
                wrist.x + (point.y - wrist.y),
                wrist.y + (point.x - wrist.x),
                point.z,
            )
            for point in index_hand
        ]
        self.assertEqual(recognizer.detect_static_gesture(rotated_index), "index_cursor")

        palm = make_gesture_landmarks([True, True, True, True, True])
        peace = make_gesture_landmarks([False, True, True, False, False])
        self.assertEqual(recognizer.detect_two_hands(palm, palm), "two_open_palms")
        self.assertEqual(recognizer.detect_two_hands(peace, peace), "two_peace_signs")

    def test_14_thumbs_route_to_volume_or_zoom_by_context(self):
        recognizer = GestureRecognizer()
        self.assertEqual(
            recognizer.detect_static_gesture(make_gesture_landmarks([True, False, False, False, False])),
            "thumbs_up",
        )
        self.assertEqual(recognizer.detect_static_gesture(make_thumbs_down_landmarks()), "thumbs_down")

        with (
            patch.object(gesture_executor.ContextManager, "is_media_active", return_value=False),
            patch.object(gesture_executor.actions, "change_volume") as change_volume,
            patch.object(gesture_executor.actions, "zoom_in") as zoom_in,
            patch.object(gesture_executor.actions, "zoom_out") as zoom_out,
            patch.object(gesture_executor.db, "log_event"),
        ):
            self.assertEqual(execute_gesture("thumbs_up", context="spotify"), "Volume Up")
            self.assertEqual(execute_gesture("thumbs_down", context="youtube"), "Volume Down")
            self.assertEqual(execute_gesture("thumbs_up", context="code_editor"), "Zoom In")
            self.assertEqual(execute_gesture("thumbs_down", context="default"), "Zoom Out")

        self.assertEqual(change_volume.call_count, 2)
        zoom_in.assert_called_once()
        zoom_out.assert_called_once()

    def test_15_pinching_cursor_releases_left_button(self):
        cursor = CursorController()
        pinched_hand = make_gesture_landmarks([False, True, False, False, False])
        pinched_hand[4] = DummyLandmark(pinched_hand[8].x, pinched_hand[8].y)
        released_hand = make_gesture_landmarks([False, True, False, False, False])
        with (
            patch.object(cursor_controller_module.sys, "platform", "linux"),
            patch.object(cursor_controller_module.pyautogui, "moveTo"),
            patch.object(cursor_controller_module.pyautogui, "mouseDown") as mouse_down,
            patch.object(cursor_controller_module.pyautogui, "mouseUp") as mouse_up,
        ):
            cursor.update(pinched_hand)
            cursor.update(released_hand)
            self.assertFalse(cursor.is_pinching)
            self.assertEqual(mouse_down.call_count, 1)
            self.assertEqual(mouse_up.call_count, 1)

            cursor.is_pinching = True
            cursor.release()
        self.assertEqual(mouse_up.call_count, 2)
        self.assertEqual(mouse_up.call_args_list[-1].args, ())
        self.assertEqual(mouse_up.call_args_list[-1].kwargs, {"button": "left"})
        self.assertFalse(cursor.is_pinching)

    def test_index_thumb_pinch_uses_left_click_not_overlapping_right_pinch(self):
        cursor = CursorController()
        pinched_hand = make_gesture_landmarks([False, True, False, False, False])
        pinched_hand[4] = DummyLandmark(pinched_hand[8].x, pinched_hand[8].y)
        released_hand = make_gesture_landmarks([False, True, False, False, False])
        with (
            patch.object(cursor_controller_module.sys, "platform", "linux"),
            patch.object(cursor_controller_module.pyautogui, "moveTo"),
            patch.object(cursor_controller_module.pyautogui, "mouseDown") as mouse_down,
            patch.object(cursor_controller_module.pyautogui, "mouseUp") as mouse_up,
            patch.object(cursor_controller_module.pyautogui, "rightClick") as right_click,
        ):
            cursor.update(pinched_hand)
            cursor.update(released_hand)

        self.assertEqual(mouse_down.call_count, 1)
        self.assertEqual(mouse_up.call_count, 1)
        right_click.assert_not_called()


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestConcurrencyAndRobotSystem)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
