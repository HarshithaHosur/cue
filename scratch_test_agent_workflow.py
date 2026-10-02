"""Synthetic integration tests for iterative support-agent screen workflows."""

import os
import sys
import types
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import core
import ui
import config
import database

intent_package = types.ModuleType("intent_platform")
intent_package.__path__ = [BASE_DIR]
sys.modules["intent_platform"] = intent_package
sys.modules["intent_platform.core"] = core
sys.modules["intent_platform.ui"] = ui
sys.modules["intent_platform.config"] = config
sys.modules["intent_platform.database"] = database
intent_package.core = core
intent_package.ui = ui
intent_package.config = config
intent_package.database = database

from PySide6.QtCore import QCoreApplication

from intent_platform.core.support.page_analyzer import SupportPageAnalyzer
from intent_platform.core.support.support_agent import CustomerSupportAgent
from intent_platform.core.techsupport.tech_support_agent import TechnicalSupportAgent
from intent_platform.core.support.safety_manager import SafetyManager
from intent_platform.core.techsupport.software_installer import SoftwareInstallationAssistant
import intent_platform.core.support.page_analyzer as page_analyzer_module
import intent_platform.core.support.support_agent as support_agent_module


class SyntheticConversationStore:
    def __init__(self):
        self.turns = []

    def save_turn(self, user_message, assistant_response, action_taken="", status="responded", timestamp=None):
        self.turns.append({
            "user_message": user_message,
            "assistant_response": assistant_response,
            "action_taken": action_taken,
            "status": status,
            "timestamp": timestamp,
        })

    def update_latest_action(self, action_taken, status):
        if self.turns:
            self.turns[-1]["action_taken"] = action_taken
            self.turns[-1]["status"] = status


class SyntheticScreenIntelligence:
    LOW_CONFIDENCE_MESSAGE = "Please adjust the window so I can inspect it again."

    def __init__(self):
        self.ui_state = "home"
        self.calls = []
        self.current_context = self._context()
        self.capture_engine = Mock()
        self.ocr_engine = Mock()

    def _context(self):
        return {
            "website": "Amazon",
            "page_type": {
                "home": "Home",
                "support": "Customer Support",
                "return_reason": "Returns",
                "reason_selected": "Returns",
            }[self.ui_state],
            "application": "Synthetic Browser",
            "browser": "Synthetic Browser",
        }

    def _visible_target(self):
        return {
            "home": "Customer Support",
            "support": "Return item",
            "return_reason": "Wrong item received",
            "reason_selected": "",
        }[self.ui_state]

    def _analysis(self, command):
        label = self._visible_target()
        if self.ui_state == "support" and "return" not in command.casefold():
            label = ""
        if label:
            action = "click"
            found = True
            complete = False
            text = f"On {self.current_context['page_type']}, I found {label} for your request: {command}."
        else:
            action = "explain"
            found = False
            complete = True
            text = "The requested return reason is selected on the current page."
        return {
            "website": "Amazon",
            "page_type": self.current_context["page_type"],
            "user_intent": command,
            "reasoning_steps": [f"Observed synthetic {self.current_context['page_type']} screen"],
            "target_element": {
                "found": found,
                "label": label,
                "type": "button",
                "x": 80,
                "y": 60,
                "w": 120,
                "h": 30,
                "confidence": 0.99,
            },
            "explanation_text": text,
            "explanation_voice": text,
            "suggested_action": action,
            "risk_level": "MEDIUM_RISK" if action == "click" else "SAFE",
            "requires_confirmation": action == "click",
            "confirmation_prompt": f"Should I click {label}?" if label else "",
            "workflow_completed": complete,
            "selected_item": "Wireless Headphones" if self.ui_state != "home" else "",
            "confidence_verified": True,
            "ocr_confidence": 0.99,
            "screen_context": {"current_page": self.current_context["page_type"]},
            "window_title": "Synthetic Amazon",
        }

    def get_screen_understanding(self, command, conversation_history=None, force_refresh=False, additional_context=None):
        self.current_context = self._context()
        self.calls.append({
            "command": command,
            "state": self.ui_state,
            "history": list(conversation_history or []),
            "task_state": dict((additional_context or {}).get("task_state", {})),
            "force_refresh": force_refresh,
        })
        return self._analysis(command)

    @staticmethod
    def _find_ocr_target(target, blocks):
        label = target.get("label")
        return next((block for block in blocks if block.get("text") == label), None)


class AgentWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.agent = CustomerSupportAgent()
        self.browser_guard = patch.object(self.agent, "_ensure_browser_for_support_request", return_value=True)
        self.browser_guard.start()
        self.addCleanup(self.browser_guard.stop)
        self.real_screen_intelligence = self.agent.screen_intelligence
        self.real_screen_intelligence.stop()
        self.screen = SyntheticScreenIntelligence()
        self.agent.screen_intelligence = self.screen
        self.agent.capture_engine = self.screen.capture_engine
        self.agent.conversation_store = SyntheticConversationStore()
        self.responses = []
        self.confirmations = []
        self.executed_actions = []
        self.agent.signals.response_ready.connect(lambda text, voice: self.responses.append(text))
        self.agent.signals.confirmation_required.connect(self.confirmations.append)
        self.agent.signals.action_executed.connect(
            lambda action, message: self.executed_actions.append((action, message))
        )

    def tearDown(self):
        self.real_screen_intelligence.stop()

    def _mock_capture_and_ocr(self):
        def capture(**_kwargs):
            return b"synthetic-current-screen", 640, 480, {
                "title": "Synthetic Amazon",
                "hwnd": 0,
                "capture_origin": {"left": 0, "top": 0},
                "bounds": {"left": 0, "top": 0, "width": 640, "height": 480},
            }

        def ocr(_image):
            label = self.screen._visible_target()
            blocks = []
            if label:
                blocks.append({
                    "text": label,
                    "bbox": [20, 45, 140, 75],
                    "confidence": 0.99,
                })
            return {"blocks": blocks, "full_text": " ".join(b["text"] for b in blocks)}

        self.screen.capture_engine.capture_active_window.side_effect = capture
        self.screen.ocr_engine.extract_text.side_effect = ocr

    def _click_changes_screen(self, x, y):
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.screen.ui_state = {
            "home": "support",
            "support": "return_reason",
            "return_reason": "reason_selected",
        }[self.screen.ui_state]

    def test_support_to_return_uses_new_screen_and_context(self):
        self._mock_capture_and_ocr()
        self.agent.active_workflow = None
        with (
            patch.object(support_agent_module.time, "sleep", return_value=None),
            patch.object(support_agent_module.pyautogui, "click", side_effect=self._click_changes_screen),
        ):
            self.agent._run_pipeline("Open customer support")
            self.assertEqual(self.screen.calls[0]["state"], "home")
            self.assertEqual(self.screen.calls[-1]["state"], "support")
            self.assertEqual(self.confirmations, [])
            self.assertEqual(self.executed_actions[0][0], "click")
            self.assertIn("Customer Support", self.executed_actions[0][1])
            self.assertEqual(self.screen.calls[-1]["state"], "support")
            self.assertEqual(self.screen.calls[-1]["command"], "Open customer support")

            self.agent._run_pipeline("I want to return this product")
            return_call = self.screen.calls[-1]
            self.assertEqual(return_call["state"], "support")
            self.assertEqual(return_call["command"], "I want to return this product")
            self.assertTrue(any(
                entry.get("role") == "assistant"
                and entry.get("action_taken") == "Customer Support"
                and entry.get("status") == "executed"
                for entry in return_call["history"]
            ))
            self.assertEqual(self.confirmations[-1]["target_label"], "Return item")

            self.agent.confirm_pending_action()
            self.assertEqual(self.screen.calls[-1]["state"], "return_reason")
            self.assertEqual(self.confirmations[-1]["target_label"], "Wrong item received")

            self.agent.confirm_pending_action()
            self.assertEqual(self.screen.calls[-1]["state"], "reason_selected")
            self.assertEqual(self.agent.task_state["status"], "completed")

        self.assertEqual(len(self.confirmations), 2)
        self.assertTrue(any("return" in response.lower() for response in self.responses))

    def test_analysis_failure_is_safe_and_does_not_log_provider_details(self):
        self.screen.get_screen_understanding = Mock(side_effect=TimeoutError("private provider detail"))
        with patch("intent_platform.core.support.support_agent.time.sleep", return_value=None):
            self.agent._run_pipeline("Explain this screen")
        self.assertEqual(self.agent.task_state["status"], "blocked")
        self.assertIn("I couldn't analyze the current screen", self.responses[-1])
        self.assertNotIn("private provider detail", self.responses[-1])
        self.assertEqual(self.agent.conversation_store.turns[-1]["status"], "failed")

    def test_capture_failure_fails_safely_without_stale_click(self):
        self.screen.get_screen_understanding = Mock(side_effect=OSError("synthetic capture failure"))
        with patch.object(support_agent_module.time, "sleep", return_value=None):
            self.agent._run_pipeline("Open customer support")
        self.assertEqual(self.agent.task_state["status"], "blocked")
        self.assertIn("I couldn't analyze the current screen", self.responses[-1])
        self.assertFalse(self.agent.safety_manager.has_pending_action())
        self.assertNotIn("synthetic capture failure", self.responses[-1])

    def test_default_browser_launch_waits_for_browser_or_reports_failure(self):
        with (
            patch.object(support_agent_module.SupportContextDetector, "detect_context", return_value={
                "is_browser": False, "website": "General Website",
            }),
            patch.object(support_agent_module.SupportContextDetector, "get_active_window_info", side_effect=[
                {"is_browser": False}, {"is_browser": True},
            ]),
            patch.object(support_agent_module.actions, "open_item", return_value="Opened browser") as launch,
            patch.object(support_agent_module.time, "sleep", return_value=None),
        ):
            self.assertTrue(CustomerSupportAgent._ensure_browser_for_support_request(
                self.agent, "Open customer support"
            ))
        launch.assert_called_once_with("browser")

        with (
            patch.object(support_agent_module.SupportContextDetector, "detect_context", return_value={
                "is_browser": False, "website": "General Website",
            }),
            patch.object(support_agent_module.actions, "open_item", return_value="Could not find or open 'browser'"),
        ):
            self.assertFalse(CustomerSupportAgent._ensure_browser_for_support_request(
                self.agent, "Open customer care"
            ))
        self.assertEqual(self.agent.task_state["status"], "blocked")
        self.assertIn("couldn't open a browser", self.responses[-1].lower())

    def test_technical_support_analysis_failure_is_visible_in_chat(self):
        agent = TechnicalSupportAgent()
        self.addCleanup(agent.screen_intelligence.stop)
        agent.screen_intelligence.stop()
        agent._ensure_browser_for_support_request = lambda _command: True
        agent.screen_intelligence = Mock()
        agent.screen_intelligence.current_context = {"website": "Shop", "page_type": "Home"}
        agent.screen_intelligence.get_screen_understanding.side_effect = TimeoutError("private provider detail")
        responses = []
        agent.signals.response_ready.connect(lambda text, voice: responses.append((text, voice)))

        with patch("intent_platform.core.techsupport.tech_support_agent.time.sleep", return_value=None):
            agent._run_standard_customer_support_pipeline("Open customer support")

        self.assertEqual(agent.task_state["status"], "blocked")
        self.assertTrue(responses)
        self.assertIn("I couldn't analyze the current screen", responses[-1][0])
        self.assertNotIn("private provider detail", responses[-1][0])

    def test_support_open_executes_and_new_return_request_requires_confirmation(self):
        self._mock_capture_and_ocr()
        with (
            patch.object(support_agent_module.time, "sleep", return_value=None),
            patch.object(support_agent_module.pyautogui, "click", side_effect=self._click_changes_screen),
        ):
            self.agent._run_pipeline("Open customer support")
            self.assertFalse(self.agent.safety_manager.has_pending_action())
            self.assertEqual(self.screen.ui_state, "support")
            self.screen.ui_state = "support"
            self.agent._run_pipeline("I want to return this product")
        self.assertEqual(self.screen.calls[-1]["command"], "I want to return this product")
        self.assertEqual(self.screen.calls[-1]["state"], "support")
        self.assertEqual(self.confirmations[-1]["target_label"], "Return item")
        self.assertTrue(self.agent.safety_manager.has_pending_action())
        self.assertEqual(self.agent.task_state["goal"], "I want to return this product")

    def test_confirmation_click_uses_fresh_ocr_coordinates(self):
        self._mock_capture_and_ocr()
        self.agent.safety_manager.prepare_action(
            "click",
            target_coords=(70, 60),
            target_label="Customer Support",
            details={
                "window_title": "Synthetic Amazon",
                "target_element": {
                    "found": True,
                    "label": "Customer Support",
                    "image_x": 70,
                    "image_y": 60,
                    "x": 70,
                    "y": 60,
                },
            },
        )
        clicked = []
        self.screen.ocr_engine.extract_text.side_effect = lambda _image: {
            "blocks": [{"text": "Customer Support", "bbox": [300, 200, 440, 230], "confidence": 0.99}],
            "full_text": "Customer Support",
        }
        with (
            patch.object(support_agent_module.time, "sleep", return_value=None),
            patch.object(support_agent_module.pyautogui, "click", side_effect=lambda x, y: clicked.append((x, y))),
            patch.object(self.agent, "_observe_after_action"),
        ):
            self.agent.confirm_pending_action()
        self.assertEqual(clicked, [(370, 215)])

    def test_changed_ui_removes_target_and_prevents_click(self):
        self._mock_capture_and_ocr()
        self.agent.safety_manager.prepare_action(
            "click",
            target_coords=(80, 60),
            target_label="Customer Support",
            details={
                "window_title": "Synthetic Amazon",
                "target_element": {
                    "found": True,
                    "label": "Customer Support",
                    "image_x": 80,
                    "image_y": 60,
                    "x": 80,
                    "y": 60,
                },
            },
        )
        self.screen.ocr_engine.extract_text.side_effect = None
        self.screen.ocr_engine.extract_text.return_value = {"blocks": [], "full_text": "A different page"}
        clicked = Mock()
        self.agent._observe_after_action = Mock()
        with patch.object(support_agent_module.pyautogui, "click", clicked):
            self.agent.confirm_pending_action()
        clicked.assert_not_called()
        self.agent._observe_after_action.assert_called_once()
        self.assertEqual(self.agent.task_state["last_action"]["status"], "stale_target")

    def test_click_failure_is_reported_without_claiming_success(self):
        self._mock_capture_and_ocr()
        self.agent.safety_manager.prepare_action(
            "click",
            target_coords=(80, 60),
            target_label="Customer Support",
            details={
                "window_title": "Synthetic Amazon",
                "target_element": {
                    "found": True,
                    "label": "Customer Support",
                    "image_x": 80,
                    "image_y": 60,
                    "x": 80,
                    "y": 60,
                },
            },
        )
        with (
            patch.object(support_agent_module.time, "sleep", return_value=None),
            patch.object(support_agent_module.pyautogui, "click", side_effect=OSError("synthetic private OS detail")),
        ):
            self.agent.confirm_pending_action()
        self.assertIn("desktop action failed", self.responses[-1])
        self.assertNotIn("synthetic private OS detail", self.responses[-1])
        self.assertNotIn("Clicked 'Customer Support'", self.responses)

    def test_support_and_complaint_outcomes_require_fresh_screen_evidence(self):
        self.agent.task_state["goal"] = "Open customer support"
        self.agent.task_state["last_action"] = {
            "action": "click", "target": "Customer Support", "status": "executed",
        }
        not_open, _ = self.agent._verify_observed_action(
            {"screen_context": {"current_page": "Home", "full_text": "Shop home"}},
            {"is_support_page": False},
        )
        opened, _ = self.agent._verify_observed_action(
            {"screen_context": {"current_page": "Customer Support", "full_text": "How can we help?"}},
            {"is_support_page": True},
        )
        self.assertFalse(not_open)
        self.assertTrue(opened)

        self.agent.task_state["goal"] = "Submit complaint"
        self.agent.task_state["last_action"] = {
            "action": "click", "target": "Submit complaint", "status": "executed",
        }
        submitted, _ = self.agent._verify_observed_action(
            {"screen_context": {"current_page": "Complaint form", "full_text": "Please wait"}}, {},
        )
        verified, _ = self.agent._verify_observed_action(
            {"screen_context": {"current_page": "Complaint result", "full_text": "Complaint submitted. Ticket number 12345"}}, {},
        )
        self.assertFalse(submitted)
        self.assertTrue(verified)

    def test_final_submit_requires_explicit_stage_and_visible_ticket_result(self):
        self.agent.task_state["goal"] = "Raise a complaint"
        self.agent.task_state["last_action"] = {
            "action": "click",
            "target": "Raise complaint",
            "status": "executed",
            "details": {"action_stage": "form"},
        }
        form_open, _ = self.agent._verify_observed_action(
            {"screen_context": {"full_text": "Complaint details"}}, {},
        )
        self.agent.task_state["last_action"]["details"]["action_stage"] = "final_submit"
        pending, _ = self.agent._verify_observed_action(
            {"screen_context": {"full_text": "Submitting complaint"}}, {},
        )
        result, _ = self.agent._verify_observed_action(
            {"screen_context": {"full_text": "Complaint submitted. Ticket number ABC123"}}, {},
        )
        self.assertTrue(form_open)
        self.assertFalse(pending)
        self.assertTrue(result)

    def test_open_support_executes_and_verifies_for_base_and_technical_agents(self):
        for agent_type in (CustomerSupportAgent, TechnicalSupportAgent):
            with self.subTest(agent_type=agent_type.__name__):
                agent = agent_type()
                self.addCleanup(agent.screen_intelligence.stop)
                agent.screen_intelligence.stop()
                agent._ensure_browser_for_support_request = lambda _command: True
                observed_pages = iter(("Home", "Customer Support"))
                agent.screen_intelligence.current_context = {"website": "Shop", "page_type": "Home"}

                def understand(command, **_kwargs):
                    page = next(observed_pages)
                    agent.screen_intelligence.current_context = {
                        "website": "Shop",
                        "page_type": page,
                        "is_support_page": page == "Customer Support",
                    }
                    if page == "Home":
                        target = {"found": True, "label": "Customer Support", "type": "button", "x": 80, "y": 60, "w": 120, "h": 30, "confidence": 0.99}
                        suggestion = "click"
                        explanation = "I found Customer Support. Opening it now."
                    else:
                        target = {"found": False}
                        suggestion = "explain"
                        explanation = "Customer Support is open. What do you need help with?"
                    return {
                        "screen_context": {"current_page": page, "full_text": "Customer Support" if page == "Customer Support" else "Shop home"},
                        "target_element": target,
                        "explanation_text": explanation,
                        "explanation_voice": explanation,
                        "suggested_action": suggestion,
                        "workflow_completed": False,
                        "confidence_verified": True,
                        "window_title": "Synthetic Shop",
                    }

                agent.screen_intelligence.get_screen_understanding = Mock(side_effect=understand)
                agent._revalidate_pending_target = Mock(return_value=True)
                responses = []
                executed = []
                agent.signals.response_ready.connect(lambda text, _voice: responses.append(text))
                agent.signals.action_executed.connect(lambda name, result: executed.append((name, result)))
                with (
                    patch.object(support_agent_module.time, "sleep", return_value=None),
                    patch.object(support_agent_module.pyautogui, "click") as click,
                ):
                    agent._run_pipeline("Open customer support") if agent_type is CustomerSupportAgent else agent._run_standard_customer_support_pipeline("Open customer support")

                click.assert_called_once_with(80, 60)
                self.assertEqual(agent.screen_intelligence.get_screen_understanding.call_count, 2)
                self.assertTrue(any("Customer Support is open" in response for response in responses))
                self.assertTrue(executed)
                self.assertFalse(agent.safety_manager.has_pending_action())

    def test_form_fill_requires_value_from_user_history(self):
        self.agent.conversation_history[:] = [{"role": "user", "content": "My order number is 12345"}]
        self.assertTrue(self.agent._user_provided_value("12345", self.agent.conversation_history))
        self.assertFalse(self.agent._user_provided_value("99999", self.agent.conversation_history))

    def test_software_installation_plan_and_mocked_results(self):
        with tempfile.TemporaryDirectory(prefix="intent-install-test-") as directory:
            installer = SoftwareInstallationAssistant(download_dir=directory)
            python = installer.match_software("Please install Python")
            self.assertEqual(python["name"], "Python 3.11")
            plan = installer.prepare_installation_plan(python)
            self.assertEqual(plan["status"], "ready_for_confirmation")
            self.assertEqual(plan["risk_level"], "MEDIUM_RISK")

            with patch(
                "intent_platform.core.techsupport.software_installer.urllib.request.urlopen",
                side_effect=OSError("synthetic network denial"),
            ):
                failed_download = installer.download_installer()
            self.assertFalse(failed_download["success"])
            self.assertNotIn("synthetic network denial", failed_download["error"])
            self.assertEqual(failed_download["fallback_url"], python["official_url"])

            with (
                patch("intent_platform.core.techsupport.software_installer.os.path.exists", return_value=True),
                patch("intent_platform.core.techsupport.software_installer.subprocess.Popen") as launch,
            ):
                launch_result = installer.execute_installer()
            self.assertTrue(launch_result["success"])
            launch.assert_called_once()

            with (
                patch("intent_platform.core.techsupport.software_installer.os.path.exists", return_value=True),
                patch("intent_platform.core.techsupport.software_installer.subprocess.Popen", side_effect=PermissionError("synthetic permission denial")),
            ):
                failed_launch = installer.execute_installer()
            self.assertFalse(failed_launch["success"])
            self.assertNotIn("synthetic permission denial", failed_launch["error"])

            with patch("intent_platform.core.techsupport.software_installer.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="Python 3.11", stderr="")):
                verified = installer.verify_installation(python)
            self.assertTrue(verified["installed"])
            with patch("intent_platform.core.techsupport.software_installer.subprocess.run", side_effect=FileNotFoundError("synthetic missing command")):
                not_verified = installer.verify_installation(python)
            self.assertFalse(not_verified["installed"])
            self.assertNotIn("synthetic missing command", not_verified["error"])

    def test_context_prompt_includes_prior_action_and_current_goal(self):
        analyzer = SupportPageAnalyzer(api_key=None)
        analyzer.client_ready = True
        analyzer.api_key = ""
        analyzer._init_gemini = Mock()
        captured = {}

        class FakeResponse:
            text = '{"explanation_text":"I see the return option.","explanation_voice":"I see the return option.","suggested_action":"explain","target_element":{"found":false},"workflow_completed":false}'

        class FakeModel:
            def __init__(self, **kwargs):
                captured["system_instruction"] = kwargs["system_instruction"]

            def generate_content(self, parts):
                captured["parts"] = parts
                return FakeResponse()

        history = [
            {"role": "user", "content": "Open customer support"},
            {"role": "assistant", "content": "Opened support", "action_taken": "click Customer Support", "status": "executed"},
        ]
        task_state = {"goal": "Open customer support", "current_request": "Return it", "last_action": {"target": "Customer Support", "status": "executed"}}
        with patch.object(page_analyzer_module.genai, "GenerativeModel", FakeModel):
            response = analyzer.analyze(
                command="I want to return this product",
                image_bytes=b"synthetic image",
                context={},
                res_w=640,
                res_h=480,
                conversation_history=history,
                additional_context={"task_state": task_state},
            )
        prompt = captured["system_instruction"]
        self.assertIn("Open customer support", prompt)
        self.assertIn("click Customer Support", prompt)
        self.assertIn("I want to return this product", prompt)
        self.assertIn("current_request", prompt)
        self.assertEqual(response["suggested_action"], "explain")

    def test_safe_scroll_reobserves_and_bounds_automatic_steps(self):
        self._mock_capture_and_ocr()
        self.screen.ui_state = "support"
        self.agent.active_workflow = "Find the return option"
        self.agent.task_state.update({"goal": "Find the return option", "status": "observing"})
        scroll_analysis = self.screen._analysis("Find the return option")
        scroll_analysis.update({
            "target_element": {"found": False},
            "suggested_action": "scroll",
            "scroll_direction": "down",
            "workflow_completed": False,
        })
        calls = []

        def next_analysis(command, **kwargs):
            calls.append(command)
            return dict(scroll_analysis)

        self.screen.get_screen_understanding = Mock(side_effect=next_analysis)
        with (
            patch.object(support_agent_module.time, "sleep", return_value=None),
            patch.object(support_agent_module.pyautogui, "scroll") as scroll,
        ):
            self.agent._execute_action_direct(
                {
                    "action_name": "scroll",
                    "target_label": "page",
                    "details": {"scroll_direction": "down"},
                },
                automatic_steps=1,
            )
        self.assertEqual(scroll.call_count, 4)
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.agent.task_state["status"], "awaiting_user")
        self.assertIn("paused after several automatic navigation steps", self.responses[-1])


if __name__ == "__main__":
    unittest.main(verbosity=2)