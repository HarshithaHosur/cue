# ============================================================
#  CUSTOMER SUPPORT AGENT — Multimodal Autonomous Executive
#  Sees visible screen, listens to user voice, reasons with
#  Gemini 2.5 Flash Vision, highlights UI, enforces permission-
#  based safe automation, and speaks natural voice responses.
# ============================================================

import time
import threading
import re
from typing import Dict, Any, Optional, List
from PySide6.QtCore import QObject, Signal, Slot
import pyautogui
pyautogui.FAILSAFE = False

from intent_platform.core.support.screen_capture import EventDrivenScreenCapture
from intent_platform.core.support.context_detector import SupportContextDetector
from intent_platform.core.support.safety_manager import SafetyManager, ActionRiskLevel
from intent_platform.core.support.highlighter import highlight_element, clear_highlight
from intent_platform.core.support.audit_logger import global_audit_logger
from intent_platform.core.support.page_analyzer import SupportPageAnalyzer
from intent_platform.core.support.screen_intelligence_service import ScreenIntelligenceService
from intent_platform.core.support.conversation_store import ConversationStore
from intent_platform.core.automation import actions


class CustomerSupportAgentSignals(QObject):
    """Qt Signals emitted by Customer Support Agent to Dashboard & Companion."""
    state_changed = Signal(str, str)             # state ('thinking', 'waiting', 'speaking', 'completed'), message
    reasoning_step = Signal(str)                 # emoji step e.g. '👀 Detected Amazon Orders page'
    response_ready = Signal(str, str)            # text_response, voice_response
    confirmation_required = Signal(dict)        # pending action payload requiring user approval
    action_executed = Signal(str, str)           # action_name, result_message
    context_updated = Signal(dict)               # current app, website, page_type
    workflow_updated = Signal(str, str)          # workflow_name, stage_desc


class CustomerSupportAgent(QObject):
    """
    Multimodal AI Customer Support Executive.
    Operates across ANY website and desktop application without custom hardcoded APIs.
    Backed by continuous ScreenIntelligenceService.
    """

    def __init__(self, voice_engine=None, companion=None, parent=None):
        super().__init__(parent)
        self.signals = CustomerSupportAgentSignals()
        self.voice_engine = voice_engine
        self.companion = companion

        # Subsystems
        self.page_analyzer = SupportPageAnalyzer()
        self.screen_intelligence = ScreenIntelligenceService(page_analyzer=self.page_analyzer, parent=self)
        self.screen_intelligence.start()
        self.capture_engine = self.screen_intelligence.capture_engine
        self.safety_manager = SafetyManager()
        self.audit_logger = global_audit_logger
        self.conversation_store = ConversationStore()

        # State tracking
        self.is_active = True
        self.conversation_history: List[Dict[str, Any]] = []
        for turn in self.conversation_store.recent_turns():
            self.conversation_history.extend((
                {"role": "user", "content": turn["user_message"], "timestamp": turn["timestamp"]},
                {
                    "role": "assistant",
                    "content": turn["assistant_response"],
                    "timestamp": turn["timestamp"],
                    "action_taken": turn["action_taken"],
                },
            ))
        self.last_detected_website = ""
        self.last_detected_page_type = ""
        self.last_proactive_notice_time = 0.0
        self.active_workflow: Optional[str] = None
        self.workflow_step: int = 0
        self.task_state: Dict[str, Any] = {
            "goal": "",
            "current_request": "",
            "status": "idle",
            "last_action": None,
            "selected_item": "",
            "screen": {},
            "workflow_steps": [],
        }
        self.processing_lock = threading.Lock()

    def set_voice_engine(self, voice_engine):
        self.voice_engine = voice_engine

    def set_companion(self, companion):
        self.companion = companion

    def speak(self, text: str):
        """Speaks message via voice engine."""
        if self.voice_engine and hasattr(self.voice_engine, "speak"):
            self.voice_engine.speak(text)

    def update_companion(self, state: str, message: str):
        """Updates companion animation state, text bubble, and mouth expression."""
        self.signals.state_changed.emit(state, message)
        if self.companion and hasattr(self.companion, "update_companion_state"):
            self.companion.update_companion_state(state, message)

    @staticmethod
    def _is_customer_support_request(command: str) -> bool:
        text = " ".join(command.casefold().split())
        return any(term in text for term in (
            "customer support", "customer care", "customer service", "contact support",
            "raise a complaint", "raise complaint", "file a complaint", "file complaint",
            "complain about", "complaint", "return this", "return my", "refund",
            "track this", "track my order", "cancel this", "cancel my order", "my order",
            "help me with this order",
        ))

    @staticmethod
    def _is_open_support_request(command: str) -> bool:
        text = " ".join(command.casefold().split())
        asks_to_open = any(phrase in text for phrase in (
            "open ", "go to ", "navigate to ", "take me to ", "i need ", "i want ",
        ))
        names_support = any(phrase in text for phrase in (
            "customer support", "customer care", "customer service",
        ))
        return asks_to_open and names_support

    def _verify_observed_action(self, analysis: Dict[str, Any], context: Dict[str, Any]):
        action = self.task_state.get("last_action") or {}
        if action.get("status") != "executed":
            return True, ""

        target = str(action.get("target", ""))
        observed = self._screen_text(analysis)
        if self._is_open_support_request(str(self.task_state.get("goal", ""))):
            support_visible = bool(context.get("is_support_page")) or any(term in observed for term in (
                "customer support", "customer service", "customer care", "help center",
                "help centre", "contact us", "how can we help",
            ))
            if not support_visible:
                return False, "I performed the navigation click, but the fresh screen does not show Customer Support or Help. I can't report it as opened. Please tell me which shop is open or what you see now."

        if action.get("action") == "fill":
            details = action.get("details", {})
            value = str(details.get("field_value", "")).strip()
            if value and value.casefold() not in observed:
                return False, "I attempted to enter the information, but I can't verify it in the fresh screen observation. I haven't marked that field as completed. Please check the field before continuing."

        target_lower = target.casefold()
        details = action.get("details", {})
        is_submit_target = (
            details.get("action_stage") == "final_submit"
            or "submit" in target_lower
            or "send complaint" in target_lower
        )
        if action.get("action") == "click" and is_submit_target:
            submitted_markers = (
                "complaint submitted", "complaint raised", "request submitted", "ticket created",
                "case created", "case id", "ticket number", "successfully submitted",
            )
            if not any(marker in observed for marker in submitted_markers):
                return False, "I clicked the complaint submission control, but the fresh screen doesn't show a submission confirmation. I can't report the complaint as submitted. Please check the page for an error or confirmation."

        return True, ""

    def _ensure_browser_for_support_request(self, command: str) -> bool:
        if not self._is_customer_support_request(command):
            return True

        current = SupportContextDetector.detect_context()
        support_url = actions.resolve_support_url(command)

        if support_url and current.get("is_browser"):
            # If the user explicitly asked for a known support page, navigate there instead of leaving the browser on an unrelated page.
            self.update_companion("thinking", "Opening the official customer-care page for this website...")
            self.signals.reasoning_step.emit("🌐 Navigating to the official support page for this shop")
            launch_result = actions.open_item(command)
            if not launch_result.lower().startswith("opened"):
                message = "I couldn't open the support page, so I haven't taken any support action. Please open the browser and try again."
                self.task_state["status"] = "blocked"
                self.update_companion("error", message)
                self.signals.response_ready.emit(message, message)
                self._record_assistant_response(message, status="failed")
                self.audit_logger.log("Support page open request failed", category="LAUNCH_ERROR", risk_level="HIGH_RISK")
                return False
            return True

        if current.get("is_browser") or current.get("website") not in (None, "", "General Website"):
            return True

        if support_url:
            self.update_companion("thinking", "Opening the official support page for your shop before I inspect it...")
            self.signals.reasoning_step.emit("🌐 Opening the shop's official customer support page")
            launch_result = actions.open_item(command)
        else:
            self.update_companion("thinking", "Opening your default browser before inspecting the support page...")
            self.signals.reasoning_step.emit("🌐 No browser is active; opening the default browser for the support request")
            launch_result = actions.open_item("browser")

        if not launch_result.lower().startswith("opened"):
            message = "I couldn't open a browser, so I haven't taken any support action. Open a browser and tell me which shop to use."
            self.task_state["status"] = "blocked"
            self.update_companion("error", message)
            self.signals.response_ready.emit(message, message)
            self._record_assistant_response(message, status="failed")
            self.audit_logger.log("Default browser launch failed", category="LAUNCH_ERROR", risk_level="HIGH_RISK")
            return False

        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            if SupportContextDetector.get_active_window_info().get("is_browser"):
                self.signals.reasoning_step.emit("✅ Browser is active; observing the support page")
                return True
            time.sleep(0.25)

        message = "The browser launch was requested, but I couldn't verify that a browser window became active. I haven't clicked anything. Please open the shop and try again."
        self.task_state["status"] = "browser_not_ready"
        self.update_companion("error", message)
        self.signals.response_ready.emit(message, message)
        self._record_assistant_response(message, status="failed")
        self.audit_logger.log("Browser window did not become active after launch", category="LAUNCH_ERROR", risk_level="HIGH_RISK")
        return False

    @staticmethod
    def _user_provided_value(value: str, history: List[Dict[str, Any]]) -> bool:
        value = value.strip()
        if not value:
            return False
        return any(
            item.get("role") == "user"
            and re.search(re.escape(value), str(item.get("content", "")), re.IGNORECASE)
            for item in history
        )

    @staticmethod
    def _screen_text(analysis: Dict[str, Any]) -> str:
        screen = analysis.get("screen_context", {})
        return " ".join([
            str(screen.get("current_page", "")),
            str(screen.get("full_text", "")),
            " ".join(str(line) for line in screen.get("ocr_lines", [])),
        ]).casefold()

    def handle_user_request(self, command: str):
        """
        Main 10-step Customer Support Executive reasoning & action pipeline:
        1. Listen & acknowledge
        2. Capture screen (event-driven)
        3. Detect context (website, browser, page)
        4. Analyze screen with Gemini Vision
        5. Reason and formulate steps
        6. Explain findings (Text & Voice)
        7. Highlight UI element
        8. Check safety & request confirmation if required
        9. Perform action upon confirmation or immediately if safe
        10. Log to audit trail and confirm result
        """
        threading.Thread(target=self._run_pipeline, args=(command,), daemon=True).start()

    def _run_pipeline(self, command: str):
        with self.processing_lock:
            cmd_lower = command.lower().strip()
            self.conversation_history.append({"role": "user", "content": command, "timestamp": time.time()})

            # Check if user is confirming or cancelling an existing pending action
            if self.safety_manager.has_pending_action():
                if any(w in cmd_lower for w in ["continue", "yes", "confirm", "proceed", "go ahead", "do it", "ok"]):
                    self.confirm_pending_action()
                    return
                elif any(w in cmd_lower for w in ["stop", "no", "cancel", "abort", "don't", "wait"]):
                    self.cancel_pending_action()
                    return
                else:
                    superseded = self.safety_manager.cancel_pending_action()
                    if superseded:
                        self._update_latest_action_status(
                            superseded.get("target_label", "action"), "superseded_by_new_request"
                        )
                        clear_highlight()

            self.active_workflow = command
            self.task_state.update({
                "previous_goal": self.task_state.get("goal", ""),
                "goal": command,
                "current_request": command,
                "status": "observing",
            })

            if not self._ensure_browser_for_support_request(command):
                return

            # ── 1. Listen & Acknowledge ──
            self.update_companion("listening", "Listening to your request...")
            time.sleep(0.3)

            # ── 2. Screen Understanding via ScreenIntelligenceService ──
            self.update_companion("thinking", "Analyzing active window & screen structure...")
            self.signals.reasoning_step.emit("👀 Analyzing active window & screen structure")

            try:
                analysis = self.screen_intelligence.get_screen_understanding(
                    command=command,
                    conversation_history=self.conversation_history,
                    additional_context={"task_state": dict(self.task_state)},
                )
            except Exception as error:
                print(f"[CustomerSupportAgent] Screen analysis failed ({type(error).__name__}).")
                message = "I couldn't analyze the current screen, so I took no action. Check the AI connection or try again."
                self.task_state["status"] = "blocked"
                self.update_companion("error", message)
                self.signals.reasoning_step.emit(message)
                self.signals.response_ready.emit(message, message)
                self._record_assistant_response(message, status="failed")
                self.speak(message)
                self.audit_logger.log(
                    f"Screen analysis failed ({type(error).__name__})",
                    category="ANALYSIS_ERROR",
                    risk_level="HIGH_RISK",
                )
                return

            context = self.screen_intelligence.current_context
            self.last_detected_website = context.get("website", "General Website")
            self.last_detected_page_type = context.get("page_type", "Standard Webpage")
            self.task_state["screen"] = analysis.get("screen_context", {})
            self.task_state["selected_item"] = analysis.get("selected_item", self.task_state.get("selected_item", ""))
            self.signals.context_updated.emit(context)

            if analysis.get("cache_hit"):
                self.signals.reasoning_step.emit("⚡ Reused cached screen analysis (instant response, zero API overhead)")
                print(f"[CustomerSupportAgent] [CACHE HIT] Sub-50ms response for '{command}'")

            self.audit_logger.log(
                f"Detected {context.get('website')} - {context.get('page_type')} ({context.get('browser')})",
                category="CONTEXT",
                risk_level="INFO"
            )

            # ── 3. Visual Confidence Check Guard ──
            if not analysis.get("confidence_verified", True):
                warning_msg = analysis.get("confidence_warning", self.screen_intelligence.LOW_CONFIDENCE_MESSAGE)
                self.update_companion("speaking", warning_msg)
                self.signals.reasoning_step.emit("⚠️ Visual confidence check failed: Safely pausing automation")
                self.signals.response_ready.emit(warning_msg, warning_msg)
                self.task_state["status"] = "needs_clearer_screen"
                self.speak(warning_msg)
                self.audit_logger.log(
                    f"Visual Confidence Check Failed: {warning_msg}",
                    category="SAFETY",
                    risk_level="HIGH_RISK"
                )
                return

            # Emit reasoning steps sequentially to Reasoning Panel
            steps = analysis.get("reasoning_steps", [])
            for step in steps:
                self.signals.reasoning_step.emit(step)
                time.sleep(0.18)

            # ── 4. Target Element & Highlighting ──
            target = analysis.get("target_element", {})
            target_found = target.get("found", False)
            target_x = target.get("x", -1)
            target_y = target.get("y", -1)
            target_w = target.get("w", 160)
            target_h = target.get("h", 44)
            target_label = target.get("label", "Element")

            if target_found and target_x > 0 and target_y > 0:
                self.signals.reasoning_step.emit(f"🎯 Highlighting '{target_label}'")
                highlight_element(target_x, target_y, target_w, target_h, target_label)
                self.audit_logger.log(
                    f"Highlighted '{target_label}' at ({target_x}, {target_y})",
                    category="HIGHLIGHT",
                    risk_level="SAFE"
                )

            # ── 5. Plan the action before reporting its outcome ──
            explanation_text = analysis["explanation_text"]
            explanation_voice = analysis["explanation_voice"]

            # ── 6. Safety & Permission Assessment ──
            suggested_action = analysis.get("suggested_action", "highlight")
            action_payload = self.safety_manager.prepare_action(
                action_name=suggested_action,
                target_coords=(target_x, target_y) if target_found else None,
                target_label=target_label,
                details=analysis
            )
            auto_open_support = (
                suggested_action == "click"
                and self._is_open_support_request(command)
                and target_found
                and action_payload["requires_confirmation"]
            )
            if auto_open_support:
                action_payload["requires_confirmation"] = False
                action_payload["confirmation_prompt"] = ""
                action_payload["user_confirmed"] = True
            self.task_state["last_action"] = {
                "action": suggested_action,
                "target": target_label if target_found else "",
                "status": "awaiting_confirmation" if action_payload["requires_confirmation"] else "planned",
            }
            self.task_state["workflow_steps"].append(dict(self.task_state["last_action"]))
            self.task_state["status"] = self.task_state["last_action"]["status"]
            self._record_assistant_response(
                explanation_text,
                suggested_action,
                "awaiting_confirmation" if action_payload["requires_confirmation"] else "responded",
            )

            requires_confirm = action_payload["requires_confirmation"]
            risk_level = action_payload["risk_level"]

            if requires_confirm:
                confirm_prompt = action_payload["confirmation_prompt"]
                full_voice = f"{explanation_voice} {confirm_prompt}".strip()
                full_text = f"{explanation_text}\n\n⚠️ Confirmation: {confirm_prompt}"

                self.signals.response_ready.emit(full_text, full_voice)
                self.update_companion("waiting", confirm_prompt or "Waiting for your confirmation...")
                self.signals.reasoning_step.emit(f"🖱️ Waiting for your confirmation to continue ({risk_level})")
                self.signals.confirmation_required.emit(action_payload)
                self.audit_logger.log(
                    f"Awaiting User Confirmation for {suggested_action} ('{target_label}')",
                    category="SAFETY",
                    risk_level=risk_level
                )
                self.speak(full_voice)
            elif auto_open_support:
                self.update_companion("thinking", "Opening the verified Customer Support option...")
                self.confirm_pending_action(action_payload)
            else:
                # Safe action: execute immediately
                self.signals.response_ready.emit(explanation_text, explanation_voice)
                self.update_companion("speaking", explanation_voice)
                self.speak(explanation_voice)
                self.task_state["status"] = (
                    "completed" if analysis.get("workflow_completed") else "awaiting_user"
                )
                if analysis.get("workflow_completed"):
                    self.active_workflow = None
                self._execute_action_direct(
                    action_payload,
                    observe_after=suggested_action in {"scroll", "click"},
                    automatic_steps=1 if suggested_action == "scroll" else 0,
                )

    def confirm_pending_action(self, approved_action: Optional[Dict[str, Any]] = None):
        """User confirmed pending action via voice 'System continue' or UI click."""
        action = approved_action or self.safety_manager.pop_pending_action()
        if not action:
            self.update_companion("idle", "No action pending.")
            return

        target_label = action.get("target_label", "element")
        action_name = action.get("action_name", "click")

        if action_name in {"click", "fill", "select"} and not self._revalidate_pending_target(action):
            message = "The screen changed or the target is no longer visible, so I did not click. I’m rechecking the current screen."
            clear_highlight()
            self.update_companion("thinking", message)
            self._update_latest_action_status(target_label, "cancelled_screen_changed")
            self.task_state["last_action"] = {"action": action_name, "target": target_label, "status": "stale_target"}
            self.task_state["workflow_steps"].append(dict(self.task_state["last_action"]))
            self.task_state["status"] = "observing"
            self._observe_after_action()
            return

        target_coords = action.get("target_coords")
        if action_name in {"click", "fill", "select"} and not (
            isinstance(target_coords, (list, tuple))
            and len(target_coords) == 2
            and all(isinstance(value, (int, float)) and value >= 0 for value in target_coords)
        ):
            message = f"I couldn't verify a visible target for '{target_label}', so I did not interact with it. Please adjust the page or tell me what you see."
            self.task_state["status"] = "blocked_unverified_target"
            self.update_companion("error", message)
            self.signals.response_ready.emit(message, message)
            self.speak(message)
            return

        self.update_companion("executing", f"Executing: {target_label}...")
        self.signals.reasoning_step.emit(f"⚡ User Confirmed: Executing {action_name} on '{target_label}'")

        time.sleep(0.3)
        if action_name in {"click", "fill", "select"} and target_coords and target_coords[0] >= 0 and target_coords[1] >= 0:
            x, y = target_coords
            try:
                if action_name == "fill":
                    field_value = str(action.get("details", {}).get("field_value", "")).strip()
                    if not self._user_provided_value(field_value, self.conversation_history):
                        message = "I won't enter that value because I can't match it to information you provided. Please tell me the exact text to use."
                        self.task_state["status"] = "awaiting_user"
                        self.update_companion("waiting", message)
                        self.signals.response_ready.emit(message, message)
                        self.speak(message)
                        return
                    pyautogui.click(x, y)
                    pyautogui.hotkey("ctrl", "a")
                    pyautogui.write(field_value, interval=0.01)
                elif action_name == "select":
                    field_value = str(action.get("details", {}).get("field_value", "")).strip()
                    if not self._user_provided_value(field_value, self.conversation_history):
                        message = "I won't select an option until you provide the exact value to use."
                        self.task_state["status"] = "awaiting_user"
                        self.update_companion("waiting", message)
                        self.signals.response_ready.emit(message, message)
                        self.speak(message)
                        return
                    pyautogui.click(x, y)
                    pyautogui.write(field_value, interval=0.01)
                    pyautogui.press("enter")
                else:
                    pyautogui.click(x, y)
                clear_highlight()
            except Exception as e:
                message = f"I couldn't interact with '{target_label}' because the desktop action failed. No completion was recorded."
                self._update_latest_action_status(target_label, "failed")
                self.audit_logger.log(
                    f"Click failed ({type(e).__name__})",
                    category="ACTION_ERROR",
                    risk_level="HIGH_RISK",
                )
                self.signals.response_ready.emit(message, message)
                self.speak(message)
                self.update_companion("error", message)
                return

        # Advance workflow
        self.workflow_step += 1
        if action_name == "fill":
            msg = f"Entered the information you provided into '{target_label}'. Checking the updated screen."
        elif action_name == "select":
            msg = f"Selected '{target_label}'. Checking the updated screen."
        else:
            msg = f"Clicked '{target_label}'. Checking the updated screen."
        self.audit_logger.log(f"Executed {action_name} on '{target_label}'", category="EXECUTE", risk_level="SAFE")
        # Explain what happened
        self.update_companion("thinking", "Checking the updated screen...")
        self._update_latest_action_status(target_label, "action_performed_pending_verification")
        self.task_state["last_action"] = {"action": action_name, "target": target_label, "status": "executed"}
        self.task_state["last_action"]["details"] = dict(action.get("details", {}))
        self.task_state["last_action"]["verification_pending"] = True
        self.task_state["workflow_steps"].append(dict(self.task_state["last_action"]))
        self.task_state["status"] = "observing"
        self._observe_after_action()

    def cancel_pending_action(self):
        """User cancelled pending action via voice 'System stop' or UI click."""
        action = self.safety_manager.cancel_pending_action()
        clear_highlight()
        target_label = action.get("target_label", "action") if action else "action"
        self.update_companion("idle", "Action cancelled.")
        msg = f"Cancelled {target_label}. No changes were made."
        self.audit_logger.log(f"User cancelled action: {target_label}", category="SAFETY", risk_level="INFO")
        self.signals.action_executed.emit("cancel", msg)
        self._update_latest_action_status(target_label, "cancelled")
        self.speak("Action cancelled. Let me know how else I can help.")

    def _execute_action_direct(
        self,
        action: Dict[str, Any],
        observe_after: bool = True,
        automatic_steps: int = 0,
    ):
        """Executes safe actions (highlight, explain, scroll)."""
        action_name = action.get("action_name")
        target_label = action.get("target_label", "")

        if action_name == "scroll":
            direction = action.get("details", {}).get("scroll_direction", "down")
            amount = 600 if direction == "up" else -600
            pyautogui.scroll(amount)
            self.audit_logger.log(f"Scrolled page {direction}", category="ACTION", risk_level="SAFE")
            self.task_state["last_action"] = {"action": "scroll", "target": direction, "status": "executed"}
            self.task_state["status"] = "observing"
            if observe_after:
                time.sleep(0.35)
                self._observe_after_action(automatic_steps)
                return
        elif action_name == "highlight":
            self.audit_logger.log(f"Highlighted {target_label}", category="ACTION", risk_level="SAFE")

        if observe_after:
            time.sleep(0.35)
            self._observe_after_action()
            return

        if self.task_state.get("status") == "completed":
            self.update_companion("completed", "Task completed.")

    def _execute_scroll(self, direction: str = "down"):
        clicks = -650 if direction == "down" else 650
        pyautogui.scroll(clicks)
        self.update_companion("completed", f"Scrolled {direction}")
        self.audit_logger.log(f"Scrolled {direction}", category="ACTION", risk_level="SAFE")
        self.speak(f"Scrolled {direction}")

    def _revalidate_pending_target(self, action: Dict[str, Any]) -> bool:
        details = action.get("details", {})
        original_title = details.get("window_title", "")
        target = details.get("target_element", {})
        label = action.get("target_label", "")
        try:
            image, _, _, current_window = self.capture_engine.capture_active_window(
                reason="confirm_action_revalidation", force=True, prefer_active_window=True
            )
            if original_title and current_window.get("title") != original_title:
                return False
            ocr = self.screen_intelligence.ocr_engine.extract_text(image)
            target["image_x"] = target.get("image_x", target.get("x", -1))
            target["image_y"] = target.get("image_y", target.get("y", -1))
            matched_block = self.screen_intelligence._find_ocr_target(target, ocr.get("blocks", []))
            if not matched_block:
                return False
            bbox = matched_block.get("bbox", [0, 0, 0, 0])
            target["image_x"] = (bbox[0] + bbox[2]) // 2
            target["image_y"] = (bbox[1] + bbox[3]) // 2
            origin = current_window.get("capture_origin", current_window.get("bounds", {}))
            action["target_coords"] = (
                int(target["image_x"] + origin.get("left", 0)),
                int(target["image_y"] + origin.get("top", 0)),
            )
            return bool(label)
        except Exception as error:
            print(f"[CustomerSupportAgent] Target revalidation failed ({type(error).__name__}).")
            return False

    def _observe_after_action(self, automatic_steps: int = 0):
        command = self.active_workflow or self.task_state.get("goal") or "Help with the current task"
        if automatic_steps > 3:
            message = "I paused after several automatic navigation steps. Please tell me what you see or which option you want next."
            self.task_state["status"] = "awaiting_user"
            self.signals.response_ready.emit(message, message)
            self.speak(message)
            self.update_companion("waiting", message)
            return
        try:
            analysis = self.screen_intelligence.get_screen_understanding(
                command=command,
                conversation_history=self.conversation_history,
                force_refresh=True,
                additional_context={"task_state": dict(self.task_state)},
            )
            context = self.screen_intelligence.current_context
            self.task_state["screen"] = analysis.get("screen_context", {})
            self.task_state["selected_item"] = analysis.get(
                "selected_item", self.task_state.get("selected_item", "")
            )
            self.signals.context_updated.emit(context)
            if not analysis.get("confidence_verified", True):
                warning = analysis.get(
                    "confidence_warning", self.screen_intelligence.LOW_CONFIDENCE_MESSAGE
                )
                self.signals.response_ready.emit(warning, warning)
                self.task_state["status"] = "needs_clearer_screen"
                self.speak(warning)
                self.update_companion("waiting", warning)
                return

            verified, verification_message = self._verify_observed_action(analysis, context)
            if not verified:
                self.task_state["status"] = "action_unverified"
                self._update_latest_action_status(
                    self.task_state.get("last_action", {}).get("target", "action"),
                    "unverified",
                )
                self.signals.reasoning_step.emit("⚠️ The fresh screen did not verify the action; no success was recorded")
                self.signals.response_ready.emit(verification_message, verification_message)
                self.speak(verification_message)
                self.update_companion("waiting", verification_message)
                return

            completed_action = self.task_state.get("last_action") or {}
            if completed_action.get("status") == "executed":
                completed_action["verification_pending"] = False
                completed_action["verified"] = True
                self._update_latest_action_status(
                    completed_action.get("target", "action"), "executed"
                )
                self.signals.action_executed.emit(
                    str(completed_action.get("action", "action")),
                    f"Observed the screen after {completed_action.get('action', 'action')} on '{completed_action.get('target', 'target')}'.",
                )

            target = analysis.get("target_element", {})
            if target.get("found"):
                highlight_element(
                    target["x"], target["y"], target.get("w", 160),
                    target.get("h", 44), target.get("label", ""),
                )
            text = analysis["explanation_text"]
            voice = analysis["explanation_voice"]
            next_action = self.safety_manager.prepare_action(
                action_name=analysis.get("suggested_action", "explain"),
                target_coords=(target.get("x"), target.get("y")) if target.get("found") else None,
                target_label=target.get("label", "Element"),
                details=analysis,
            )
            if next_action["requires_confirmation"]:
                text = f"{text}\n\n{next_action['confirmation_prompt']}"
                voice = f"{voice} {next_action['confirmation_prompt']}".strip()
                self.signals.confirmation_required.emit(next_action)
                self.task_state["last_action"] = {
                    "action": next_action["action_name"],
                    "target": next_action["target_label"],
                    "status": "awaiting_confirmation",
                }
                self.task_state["workflow_steps"].append(dict(self.task_state["last_action"]))
                self.task_state["status"] = "awaiting_confirmation"
                self.update_companion("waiting", next_action["confirmation_prompt"])
            self.signals.response_ready.emit(text, voice)
            self._record_assistant_response(
                text,
                next_action["action_name"],
                "awaiting_confirmation" if next_action["requires_confirmation"] else "observed",
            )
            self.speak(voice)
            if not next_action["requires_confirmation"]:
                action_name = next_action["action_name"]
                if action_name == "scroll":
                    self._execute_action_direct(next_action, observe_after=False)
                    self._observe_after_action(automatic_steps + 1)
                else:
                    workflow_goal = str(self.task_state.get("goal", "")).casefold()
                    active_multistep_support = any(term in workflow_goal for term in (
                        "customer support", "customer care", "customer service", "complaint",
                        "complain", "order", "return", "refund", "track", "cancel",
                    ))
                    self.task_state["status"] = (
                        "completed" if analysis.get("workflow_completed") else "awaiting_user"
                    )
                    if analysis.get("workflow_completed") and not active_multistep_support:
                        self.active_workflow = None
                    self.update_companion("speaking", voice)
        except Exception as error:
            message = "The action was attempted, but I couldn't analyze the updated screen. Please check the active window and try again."
            self.task_state["status"] = "post_action_analysis_failed"
            self.audit_logger.log(
                f"Post-action analysis failed ({type(error).__name__})",
                category="POST_ACTION_ANALYSIS_ERROR",
                risk_level="HIGH_RISK",
            )
            self.signals.response_ready.emit(message, message)
            self.speak(message)
            self.update_companion("error", message)

    def _record_assistant_response(self, text: str, action_taken: str = "", status: str = "responded"):
        timestamp = time.time()
        user_turn = next(
            (item for item in reversed(self.conversation_history) if item.get("role") == "user"),
            {},
        )
        user_message = user_turn.get("content", "")
        self.conversation_history.append({
            "role": "assistant",
            "content": text,
            "timestamp": timestamp,
            "action_taken": action_taken,
            "status": status,
        })
        if user_message:
            self.conversation_store.save_turn(
                user_message,
                text,
                action_taken,
                status,
                user_turn.get("timestamp"),
            )

    def _update_latest_action_status(self, action_taken: str, status: str):
        self.conversation_store.update_latest_action(action_taken, status)
        for turn in reversed(self.conversation_history):
            if turn.get("role") == "assistant":
                turn["action_taken"] = action_taken
                turn["status"] = status
                break

    def check_support_page_proactive(self):
        """
        Support Detection Mode:
        Automatically inspects foreground window; if on a Support/Help/Returns/Refunds page,
        alerts the user proactively.
        """
        now = time.time()
        # Limit proactive checks to once every 12 seconds
        if now - self.last_proactive_notice_time < 12.0:
            return

        context = SupportContextDetector.detect_context()
        if context.get("is_support_page"):
            self.last_proactive_notice_time = now
            p_text = context["proactive_text"]
            p_voice = context["proactive_voice"]

            self.audit_logger.log(
                f"Support Detection Mode triggered on {context['website']}",
                category="SUPPORT_MODE",
                risk_level="INFO"
            )
            self.update_companion("speaking", p_text)
            self.signals.response_ready.emit(p_text, p_voice)
            self.speak(p_voice)


# Global Singleton for Agent
global_support_agent: Optional[CustomerSupportAgent] = None


def get_support_agent(voice_engine=None, companion=None) -> CustomerSupportAgent:
    global global_support_agent
    if global_support_agent is None:
        try:
            from intent_platform.core.techsupport.tech_support_agent import TechnicalSupportAgent
            global_support_agent = TechnicalSupportAgent(voice_engine=voice_engine, companion=companion)
        except Exception as e:
            print(f"[SupportAgent] TechnicalSupportAgent fallback to base: {e}")
            global_support_agent = CustomerSupportAgent(voice_engine=voice_engine, companion=companion)
    return global_support_agent

