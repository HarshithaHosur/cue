# ============================================================
#  CUSTOMER SUPPORT AGENT — Multimodal Autonomous Executive
#  Sees visible screen, listens to user voice, reasons with
#  Gemini 2.5 Flash Vision, highlights UI, enforces permission-
#  based safe automation, and speaks natural voice responses.
# ============================================================

import time
import threading
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

                    self.active_workflow = command

            # ── 1. Listen & Acknowledge ──
            self.update_companion("listening", "Listening to your request...")
            time.sleep(0.3)

            # ── 2. Screen Understanding via ScreenIntelligenceService ──
            self.update_companion("thinking", "Analyzing active window & screen structure...")
            self.signals.reasoning_step.emit("👀 Analyzing active window & screen structure")

            try:
                analysis = self.screen_intelligence.get_screen_understanding(
                    command=command,
                    conversation_history=self.conversation_history
                )
            except Exception as error:
                print(f"[CustomerSupportAgent] Screen analysis failed: {error}")
                message = "Screen analysis is unavailable. Check Gemini configuration and network access; no action was taken."
                self.update_companion("error", message)
                self.signals.reasoning_step.emit(message)
                self.signals.response_ready.emit(message, message)
                self._record_assistant_response(message, status="failed")
                self.speak(message)
                self.audit_logger.log(str(error), category="ANALYSIS_ERROR", risk_level="HIGH_RISK")
                return

            context = self.screen_intelligence.current_context
            self.last_detected_website = context.get("website", "General Website")
            self.last_detected_page_type = context.get("page_type", "Standard Webpage")
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

            # ── 5. Formulate Multimodal Responses ──
            explanation_text = analysis["explanation_text"]
            explanation_voice = analysis["explanation_voice"]

            self.signals.response_ready.emit(explanation_text, explanation_voice)

            # ── 6. Safety & Permission Assessment ──
            suggested_action = analysis.get("suggested_action", "highlight")
            action_payload = self.safety_manager.prepare_action(
                action_name=suggested_action,
                target_coords=(target_x, target_y) if target_found else None,
                target_label=target_label,
                details=analysis
            )
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

                self.update_companion("waiting", confirm_prompt or "Waiting for your confirmation...")
                self.signals.reasoning_step.emit(f"🖱️ Waiting for your confirmation to continue ({risk_level})")
                self.signals.confirmation_required.emit(action_payload)
                self.audit_logger.log(
                    f"Awaiting User Confirmation for {suggested_action} ('{target_label}')",
                    category="SAFETY",
                    risk_level=risk_level
                )
                self.speak(full_voice)
            else:
                # Safe action: execute immediately
                self.update_companion("speaking", explanation_voice)
                self.speak(explanation_voice)
                self._execute_action_direct(action_payload)

    def confirm_pending_action(self):
        """User confirmed pending action via voice 'System continue' or UI click."""
        action = self.safety_manager.pop_pending_action()
        if not action:
            self.update_companion("idle", "No action pending.")
            return

        target_coords = action.get("target_coords")
        target_label = action.get("target_label", "element")
        action_name = action.get("action_name", "click")

        if action_name == "click" and not self._revalidate_pending_target(action):
            message = "The screen changed or the target is no longer visible, so I did not click. I’m rechecking the current screen."
            clear_highlight()
            self.update_companion("thinking", message)
            self._update_latest_action_status(target_label, "cancelled_screen_changed")
            self._observe_after_action()
            return

        self.update_companion("executing", f"Executing: {target_label}...")
        self.signals.reasoning_step.emit(f"⚡ User Confirmed: Executing {action_name} on '{target_label}'")

        time.sleep(0.3)
        if action_name == "click" and target_coords and target_coords[0] >= 0 and target_coords[1] >= 0:
            x, y = target_coords
            try:
                pyautogui.click(x, y)
                clear_highlight()
            except Exception as e:
                message = f"I couldn't click '{target_label}': {e}. No completion was recorded."
                self._update_latest_action_status(target_label, "failed")
                self.audit_logger.log(str(e), category="ACTION_ERROR", risk_level="HIGH_RISK")
                self.signals.response_ready.emit(message, message)
                self.speak(message)
                self.update_companion("error", message)
                return

        # Advance workflow
        self.workflow_step += 1
        msg = f"Clicked '{target_label}'. Checking the updated screen."
        self.audit_logger.log(f"Executed {action_name} on '{target_label}'", category="EXECUTE", risk_level="SAFE")
        self.signals.action_executed.emit(action_name, msg)

        # Explain what happened
        self.update_companion("thinking", "Checking the updated screen...")
        self._update_latest_action_status(target_label, "executed")
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

    def _execute_action_direct(self, action: Dict[str, Any]):
        """Executes safe actions (highlight, explain, scroll)."""
        action_name = action.get("action_name")
        target_label = action.get("target_label", "")

        if action_name == "scroll":
            direction = action.get("details", {}).get("scroll_direction", "down")
            amount = 600 if direction == "up" else -600
            pyautogui.scroll(amount)
            self.audit_logger.log(f"Scrolled page {direction}", category="ACTION", risk_level="SAFE")
        elif action_name == "highlight":
            self.audit_logger.log(f"Highlighted {target_label}", category="ACTION", risk_level="SAFE")

        time.sleep(1.0)
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
            print(f"[CustomerSupportAgent] Target revalidation failed: {error}")
            return False

    def _observe_after_action(self):
        command = self.active_workflow or "Continue helping with the current task"
        try:
            analysis = self.screen_intelligence.get_screen_understanding(
                command=f"The user approved the previous step for: {command}. Analyze the updated screen and explain the next safe step.",
                conversation_history=self.conversation_history,
                force_refresh=True,
            )
            context = self.screen_intelligence.current_context
            self.signals.context_updated.emit(context)
            if not analysis.get("confidence_verified", True):
                warning = analysis.get(
                    "confidence_warning", self.screen_intelligence.LOW_CONFIDENCE_MESSAGE
                )
                self.signals.response_ready.emit(warning, warning)
                self.speak(warning)
                self.update_companion("waiting", warning)
                return

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
                self.update_companion("waiting", next_action["confirmation_prompt"])
            self.signals.response_ready.emit(text, voice)
            self._record_assistant_response(
                text,
                next_action["action_name"],
                "awaiting_confirmation" if next_action["requires_confirmation"] else "observed",
            )
            self.speak(voice)
            if not next_action["requires_confirmation"]:
                self.update_companion("speaking", voice)
                self._execute_action_direct(next_action)
        except Exception as error:
            message = "The action was attempted, but I could not analyze the updated screen. Please check the active window."
            self.audit_logger.log(str(error), category="POST_ACTION_ANALYSIS_ERROR", risk_level="HIGH_RISK")
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

