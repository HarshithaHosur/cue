# ============================================================
#  CONCURRENCY, ROBOT ANIMATION & FEATURE TOGGLES TEST SUITE
#  Validates all 11 test cases and acceptance criteria.
# ============================================================

import sys
import os
import time
import unittest
from pathlib import Path

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
from intent_platform.ui.companion.companion_window import DesktopCompanionOverlay
from intent_platform.core.voice.voice_engine import VoiceEngine
from intent_platform.core.engine import IntentEngine
from intent_platform.ui.main_window import MainWindow
from intent_platform.ui.widgets.control_center import ControlCenterWidget


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

    def test_11_ui_control_center_widget(self):
        """TEST 11: Control Center UI widget initializes and reflects live signals."""
        cc = ControlCenterWidget()
        self.assertEqual(len(cc._rows), 5)
        
        # Toggle via UI row
        voice_row = cc._rows[Feature.VOICE.value]
        voice_row.toggle_switch.setChecked(False)
        self.assertFalse(self.fm.is_enabled(Feature.VOICE))
        
        voice_row.toggle_switch.setChecked(True)
        self.assertTrue(self.fm.is_enabled(Feature.VOICE))
        print("[OK] TEST 11: Control Center UI widget & signal binding verified.")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestConcurrencyAndRobotSystem)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
