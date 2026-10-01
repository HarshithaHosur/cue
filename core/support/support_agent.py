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
    Operates across ANY website without custom hardcoded APIs.
    """

    def __init__(self, voice_engine=None, companion=None, parent=None):
        super().__init__(parent)
        self.signals = CustomerSupportAgentSignals()
        self.voice_engine = voice_engine
        self.companion = companion

        # Subsystems
        self.capture_engine = EventDrivenScreenCapture()
        self.page_analyzer = SupportPageAnalyzer()
        self.safety_manager = SafetyManager()
        self.audit_logger = global_audit_logger

        # State tracking
        self.is_active = True
        self.conversation_history: List[Dict[str, str]] = []
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
            self.conversation_history.append({"role": "user", "content": command})

            # Check if user is confirming or cancelling an existing pending action
            if self.safety_manager.has_pending_action():
                if any(w in cmd_lower for w in ["continue", "yes", "confirm", "proceed", "go ahead", "do it", "ok"]):
                    self.confirm_pending_action()
                    return
                elif any(w in cmd_lower for w in ["stop", "no", "cancel", "abort", "don't", "wait"]):
                    self.cancel_pending_action()
                    return

            # Quick handling for direct safe commands
            if "scroll down" in cmd_lower:
                self._execute_scroll("down")
                return
            elif "scroll up" in cmd_lower:
                self._execute_scroll("up")
                return

            # ── 1. Listen & Acknowledge ──
            self.update_companion("listening", "Listening to your request...")
            time.sleep(0.3)

            # ── 2. Reading Screen & Context Detection ──
            self.update_companion("thinking", "Reading your screen...")
            self.signals.reasoning_step.emit("👀 Capturing visible webpage context")
            img_bytes, w, h = self.capture_engine.capture(reason=f"request: {command}")

            context = SupportContextDetector.detect_context()
            self.last_detected_website = context["website"]
            self.last_detected_page_type = context["page_type"]
            self.signals.context_updated.emit(context)

            self.audit_logger.log(
                f"Detected {context['website']} - {context['page_type']} ({context['browser']})",
                category="CONTEXT",
                risk_level="INFO"
            )

            # ── 3. Vision Understanding & Reasoning ──
            self.update_companion("thinking", "Understanding the page & planning...")
            analysis = self.page_analyzer.analyze(
                command=command,
                image_bytes=img_bytes,
                context=context,
                res_w=w,
                res_h=h,
                conversation_history=self.conversation_history
            )

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
            explanation_text = analysis.get("explanation_text", "I've analyzed the page.")
            explanation_voice = analysis.get("explanation_voice", explanation_text)

            self.conversation_history.append({"role": "assistant", "content": explanation_text})
            self.signals.response_ready.emit(explanation_text, explanation_voice)

            # ── 6. Safety & Permission Assessment ──
            suggested_action = analysis.get("suggested_action", "highlight")
            action_payload = self.safety_manager.prepare_action(
                action_name=suggested_action,
                target_coords=(target_x, target_y) if target_found else None,
                target_label=target_label,
                details=analysis
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

        self.update_companion("executing", f"Executing: {target_label}...")
        self.signals.reasoning_step.emit(f"⚡ User Confirmed: Executing {action_name} on '{target_label}'")

        time.sleep(0.3)
        if target_coords and target_coords[0] > 0 and target_coords[1] > 0:
            x, y = target_coords
            try:
                pyautogui.click(x, y)
                clear_highlight()
            except Exception as e:
                print(f"[CustomerSupportAgent] Click error: {e}")

        # Advance workflow
        self.workflow_step += 1
        msg = f"Completed action: '{target_label}'."
        self.audit_logger.log(f"Executed {action_name} on '{target_label}'", category="EXECUTE", risk_level="SAFE")
        self.signals.action_executed.emit(action_name, msg)

        # Explain what happened
        self.update_companion("completed", "Task completed.")
        feedback_voice = f"I've selected {target_label} for you. Let me know if you need anything else."
        self.signals.response_ready.emit(msg, feedback_voice)
        self.speak(feedback_voice)

    def cancel_pending_action(self):
        """User cancelled pending action via voice 'System stop' or UI click."""
        action = self.safety_manager.cancel_pending_action()
        clear_highlight()
        target_label = action.get("target_label", "action") if action else "action"
        self.update_companion("idle", "Action cancelled.")
        msg = f"Cancelled {target_label}. No changes were made."
        self.audit_logger.log(f"User cancelled action: {target_label}", category="SAFETY", risk_level="INFO")
        self.signals.action_executed.emit("cancel", msg)
        self.speak("Action cancelled. Let me know how else I can help.")

    def _execute_action_direct(self, action: Dict[str, Any]):
        """Executes safe actions (highlight, explain, scroll)."""
        action_name = action.get("action_name")
        target_label = action.get("target_label", "")

        if action_name == "scroll":
            pyautogui.scroll(-600)
            self.audit_logger.log("Scrolled page down", category="ACTION", risk_level="SAFE")
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
        global_support_agent = CustomerSupportAgent(voice_engine=voice_engine, companion=companion)
    return global_support_agent
