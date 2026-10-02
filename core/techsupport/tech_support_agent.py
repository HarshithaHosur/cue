# ============================================================
#  AI TECHNICAL SUPPORT EXECUTIVE — Multimodal Autonomous Agent
#  Extends CustomerSupportAgent into a complete IT Support Executive.
#  Incorporates 10 specialized modules:
#  1. Software Installation Assistant
#  2. Terminal Error Explanation
#  3. WiFi Troubleshooting
#  4. Battery Health Assistant
#  5. Voice Conversation
#  6. Permission System
#  7. Error Knowledge (Gemini Reasoning)
#  8. Screen Understanding (High Precision Vision & OCR)
#  9. Companion Narration
#  10. Audit Logging
# ============================================================

import os
import time
import threading
import subprocess
from typing import Dict, Any, Optional, List

from intent_platform.core.support.support_agent import (
    CustomerSupportAgent,
    CustomerSupportAgentSignals
)
from intent_platform.core.support.safety_manager import ActionRiskLevel
from intent_platform.core.support.highlighter import clear_highlight
from intent_platform.core.support.audit_logger import global_audit_logger

from intent_platform.core.techsupport.software_installer import SoftwareInstallationAssistant
from intent_platform.core.techsupport.terminal_diagnostics import TerminalErrorDiagnostics
from intent_platform.core.techsupport.wifi_troubleshooter import WiFiTroubleshooter
from intent_platform.core.techsupport.battery_health import BatteryHealthAssistant


class TechnicalSupportAgent(CustomerSupportAgent):
    """
    Complete AI Technical Support Executive.
    Inherits and builds upon the CustomerSupportAgent architecture,
    preserving full multimodal capabilities (Screen Understanding,
    Voice, Companion, Safety, and Audit) while expanding domain expertise
    to system diagnostics, software deployment, and programming triage.
    """

    def __init__(self, voice_engine=None, companion=None, parent=None):
        super().__init__(voice_engine=voice_engine, companion=companion, parent=parent)

        # Specialized Technical Subsystems
        self.software_installer = SoftwareInstallationAssistant()
        self.terminal_diagnostics = TerminalErrorDiagnostics()
        self.wifi_troubleshooter = WiFiTroubleshooter()
        self.battery_assistant = BatteryHealthAssistant()

        # Tech support pending action context
        self.active_tech_action: Optional[Dict[str, Any]] = None

    def _run_pipeline(self, command: str):
        """
        Extends the multimodal pipeline with IT Support domain routing.
        If user command matches software installation, terminal errors,
        Wi-Fi troubleshooting, or battery health, route to the specialized
        technical executive. Otherwise, seamlessly delegate to CustomerSupportAgent.
        """
        with self.processing_lock:
            cmd_lower = command.lower().strip()
            self.conversation_history.append({"role": "user", "content": command, "timestamp": time.time()})
            self.active_workflow = command
            self.task_state.update({
                "previous_goal": self.task_state.get("goal", ""),
                "goal": command,
                "current_request": command,
                "status": "observing",
            })

            # Check if user is confirming or cancelling an existing pending action
            if self.safety_manager.has_pending_action() or self.active_tech_action:
                if any(w in cmd_lower for w in ["continue", "yes", "confirm", "proceed", "go ahead", "do it", "ok"]):
                    self.confirm_pending_action()
                    return
                elif any(w in cmd_lower for w in ["stop", "no", "cancel", "abort", "don't", "wait"]):
                    self.cancel_pending_action()
                    return
                else:
                    if self.safety_manager.has_pending_action():
                        superseded = self.safety_manager.cancel_pending_action()
                        self._update_latest_action_status(
                            superseded.get("target_label", "action"), "superseded_by_new_request"
                        )
                    if self.active_tech_action:
                        self.active_tech_action = None

            # ── DOMAIN 1: Software Installation Assistant ──
            if self._is_software_install_request(cmd_lower):
                self._handle_software_installation(command)
                return

            # ── DOMAIN 2 & 7: Terminal Error Explanation ──
            if self._is_terminal_error_request(cmd_lower):
                self._run_standard_customer_support_pipeline(command)
                return

            # ── DOMAIN 3: WiFi Troubleshooting ──
            if self._is_wifi_request(cmd_lower):
                self._handle_wifi_troubleshooting(command)
                return

            # ── DOMAIN 4: Battery Health Assistant ──
            if self._is_battery_request(cmd_lower):
                self._handle_battery_health(command)
                return

            # ── DOMAIN 5+: Fallback to Core Customer Support Screen Pipeline ──
            # Reuses all existing implementations (Amazon, refund, policy, general website analysis)
            self._run_standard_customer_support_pipeline(command)

    # ────────────────────────────────────────────
    #  INTENT CLASSIFIERS
    # ────────────────────────────────────────────
    def _is_software_install_request(self, cmd: str) -> bool:
        keywords = ["install", "download", "setup", "get python", "get vscode", "get git", "get node", "get docker"]
        if any(kw in cmd for kw in keywords):
            # Check if software match is in catalog
            return self.software_installer.match_software(cmd) is not None
        return False

    def _is_terminal_error_request(self, cmd: str) -> bool:
        triggers = [
            "explain this error", "what is this error", "fix this error", "terminal error",
            "explain error", "code error", "why did this fail", "traceback",
            "syntax error", "modulenotfound", "compile error", "debug this"
        ]
        return any(trig in cmd for trig in triggers)

    def _is_wifi_request(self, cmd: str) -> bool:
        triggers = [
            "wifi", "wi-fi", "internet", "network", "offline", "connection lost",
            "no internet", "ping", "signal strength", "dns"
        ]
        return any(trig in cmd for trig in triggers)

    def _is_battery_request(self, cmd: str) -> bool:
        triggers = [
            "battery", "charge", "charging", "power saver", "battery saver",
            "battery health", "draining fast", "power consumption"
        ]
        return any(trig in cmd for trig in triggers)

    # ────────────────────────────────────────────
    #  MODULE 1: SOFTWARE INSTALLATION HANDLER
    # ────────────────────────────────────────────
    def _handle_software_installation(self, command: str):
        sw_info = self.software_installer.match_software(command)
        if not sw_info:
            self._respond_and_speak(
                "I couldn't identify the specific software package. Please specify the name, such as Python, VS Code, Git, or Node.js.",
                "I couldn't identify the requested software package. Could you please specify which application you would like to install?"
            )
            return

        name = sw_info["name"]

        # Module 9: Companion narration
        self.update_companion("thinking", f"Searching official sources for {name}...")
        self.signals.reasoning_step.emit(f"🔍 Locating official download source for {name}")
        time.sleep(0.4)

        plan = self.software_installer.prepare_installation_plan(sw_info)

        analysis = self._analyze_screen_with_runtime_context(
            command,
            {
                "software": {key: value for key, value in sw_info.items() if key != "official_url"} |
                    {"official_source": sw_info.get("official_url", "")},
                "installation_steps": [
                    value for key, value in plan.items()
                    if key not in {"explanation_text", "explanation_voice"}
                ],
            },
        )
        if not analysis:
            return

        self.update_companion("waiting", f"Waiting for confirmation to download {name}...")
        self.signals.reasoning_step.emit(f"📦 Found verified official installer: {sw_info['official_url']}")
        self.signals.reasoning_step.emit(f"🛡️ Permission check: Awaiting your confirmation to proceed")

        # Set safety action payload
        action_payload = self.safety_manager.prepare_action(
            action_name="download_installer",
            target_label=f"Download & Install {name}",
            details={"software_info": sw_info, "plan": plan}
        )
        self.active_tech_action = {
            "type": "software_install",
            "stage": "awaiting_download_permission",
            "payload": action_payload,
            "software_info": sw_info
        }

        self.signals.confirmation_required.emit(action_payload)
        self._respond_and_speak(analysis["explanation_text"], analysis["explanation_voice"])

    # ────────────────────────────────────────────
    #  MODULE 2 & 7: TERMINAL ERROR HANDLER
    # ────────────────────────────────────────────
    def _handle_terminal_error(self, command: str):
        # Module 9: Companion narration sequence
        self.update_companion("thinking", "Analyzing terminal...")
        self.signals.reasoning_step.emit("📸 Capturing active terminal window")
        time.sleep(0.3)

        self.update_companion("thinking", "Understanding the error...")
        self.signals.reasoning_step.emit("🔤 Extracting text via High-Precision OCR Engine")
        time.sleep(0.3)

        self.signals.reasoning_step.emit("🧠 Running Gemini reasoning on stack trace")
        self.update_companion("thinking", "Searching for the best solution...")

        report = self.terminal_diagnostics.diagnose_active_terminal(command_hint=command)

        self.signals.reasoning_step.emit(f"🎯 Error Identified: {report['error_type']} in {report['file_name']}")
        if report.get("recommended_command"):
            self.signals.reasoning_step.emit(f"💡 Recommended Command: {report['recommended_command']}")

        full_text = report["full_text"]
        voice_resp = report["voice_response"]

        # If a safe remediation command is proposed (e.g. pip install ...), ask permission to run it
        if report.get("has_remediation_command"):
            cmd_to_run = report["recommended_command"]
            action_payload = self.safety_manager.prepare_action(
                action_name="run_terminal_command",
                target_label=cmd_to_run,
                details={"command": cmd_to_run}
            )
            self.active_tech_action = {
                "type": "terminal_remediation",
                "stage": "awaiting_cmd_permission",
                "command": cmd_to_run
            }
            self.update_companion("waiting", f"Shall I execute: {cmd_to_run}?")
            self.signals.confirmation_required.emit(action_payload)
        else:
            self.update_companion("completed", "Diagnostic complete.")

        self._respond_and_speak(full_text, voice_resp)

    # ────────────────────────────────────────────
    #  MODULE 3: WIFI TROUBLESHOOTING HANDLER
    # ────────────────────────────────────────────
    def _handle_wifi_troubleshooting(self, command: str):
        report = self.wifi_troubleshooter.run_diagnostics()
        analysis = self._analyze_screen_with_runtime_context(command, {"wifi_diagnostics": report})
        if not analysis:
            return

        if report.get("requires_confirmation") and report.get("suggested_action") != "none":
            action_name = report["suggested_action"]
            action_label = report["action_label"]

            action_payload = self.safety_manager.prepare_action(
                action_name=action_name,
                target_label=action_label,
                details=report
            )
            self.active_tech_action = {
                "type": "wifi_fix",
                "action_name": action_name,
                "payload": action_payload
            }
            self.update_companion("waiting", report["confirmation_prompt"])
            self.signals.confirmation_required.emit(action_payload)
        else:
            self.update_companion("completed", "Wi-Fi check complete.")

        self._respond_and_speak(analysis["explanation_text"], analysis["explanation_voice"])

    # ────────────────────────────────────────────
    #  MODULE 4: BATTERY HEALTH HANDLER
    # ────────────────────────────────────────────
    def _handle_battery_health(self, command: str):
        report = self.battery_assistant.analyze_battery()
        analysis = self._analyze_screen_with_runtime_context(command, {"battery_diagnostics": report})
        if not analysis:
            return

        if report.get("requires_confirmation") and report.get("suggested_action") != "none":
            action_name = report["suggested_action"]
            action_payload = self.safety_manager.prepare_action(
                action_name=action_name,
                target_label="Enable Battery Saver",
                details=report
            )
            self.active_tech_action = {
                "type": "battery_fix",
                "action_name": action_name,
                "payload": action_payload
            }
            self.update_companion("waiting", report["confirmation_prompt"])
            self.signals.confirmation_required.emit(action_payload)
        else:
            self.update_companion("completed", "Battery check complete.")

        self._respond_and_speak(analysis["explanation_text"], analysis["explanation_voice"])

    def _analyze_screen_with_runtime_context(
        self, command: str, additional_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        self.update_companion("thinking", "Analyzing the active screen and current diagnostic data...")
        try:
            analysis = self.screen_intelligence.get_screen_understanding(
                command=command,
                conversation_history=self.conversation_history,
                force_refresh=True,
                additional_context=additional_context,
            )
        except Exception as error:
            message = "I couldn't complete screen-grounded reasoning, so I did not recommend or execute a change."
            self.audit_logger.log(
                f"Screen analysis failed ({type(error).__name__})",
                category="ANALYSIS_ERROR",
                risk_level="HIGH_RISK",
            )
            self.update_companion("error", message)
            self.signals.reasoning_step.emit(message)
            self.signals.response_ready.emit(message, message)
            self.speak(message)
            self._record_assistant_response(message, status="failed")
            return None

        self.signals.context_updated.emit(self.screen_intelligence.current_context)
        for step in analysis.get("reasoning_steps", []):
            self.signals.reasoning_step.emit(step)
        return analysis

    # ────────────────────────────────────────────
    #  CONFIRM & CANCEL HANDLERS (MODULE 6: PERMISSION)
    # ────────────────────────────────────────────
    def confirm_pending_action(self):
        """User approved pending action via voice 'Continue' or UI button."""
        if self.active_tech_action:
            action = self.active_tech_action
            self.active_tech_action = None
            self.safety_manager.pop_pending_action()
            action_type = action.get("type")

            if action_type == "software_install":
                self._execute_software_install_step(action)
                return
            elif action_type == "terminal_remediation":
                cmd = action.get("command", "")
                self._execute_terminal_remediation(cmd)
                return
            elif action_type == "wifi_fix":
                act_name = action.get("action_name", "")
                self._execute_wifi_fix(act_name)
                return
            elif action_type == "battery_fix":
                act_name = action.get("action_name", "")
                self._execute_battery_fix(act_name)
                return

        # Fallback to base UI click confirmation
        super().confirm_pending_action()

    def cancel_pending_action(self):
        """User cancelled pending action via voice 'Stop' or UI button."""
        self.active_tech_action = None
        super().cancel_pending_action()

    def _execute_software_install_step(self, action: Dict[str, Any]):
        sw_info = action.get("software_info", {})
        name = sw_info.get("name", "Software")
        stage = action.get("stage")

        if stage == "awaiting_download_permission":
            # Step 1: Download installer
            self.update_companion("executing", f"Downloading {name}...")
            self.signals.reasoning_step.emit(f"📥 Downloading verified {name} installer to disk...")

            def progress_cb(pct, msg):
                self.signals.reasoning_step.emit(f"📥 {msg}")

            download_res = self.software_installer.download_installer(progress_callback=progress_cb)

            if download_res.get("success"):
                if download_res.get("opened_browser"):
                    self.update_companion("completed", f"Opened official {name} download page.")
                    self._respond_and_speak(
                        f"I opened the official {name} website in your browser for secure download.",
                        f"I've opened the official {name} website for you. Let me know when you'd like me to assist with the next step."
                    )
                    return

                # Ask permission to run installer
                self.signals.reasoning_step.emit(f"✅ Installer downloaded: {download_res.get('installer_path')}")
                self.update_companion("waiting", f"Ready to run installer for {name}...")

                action_payload = self.safety_manager.prepare_action(
                    action_name="run_installer",
                    target_label=f"Run {name} Setup",
                    details={"software_info": sw_info}
                )
                self.active_tech_action = {
                    "type": "software_install",
                    "stage": "awaiting_run_permission",
                    "software_info": sw_info
                }
                self.signals.confirmation_required.emit(action_payload)
                self._respond_and_speak(
                    f"The installer for {name} has finished downloading.\n\nShall I launch the setup wizard now?",
                    f"The installer for {name} is downloaded and ready. Would you like me to launch it now?"
                )
            else:
                self.update_companion("idle", "Download interrupted.")
                self._respond_and_speak(
                    f"Unable to download installer directly ({download_res.get('error')}). Opening official source page instead.",
                    f"I couldn't download the file directly, so I am opening the official {name} website for you."
                )
                self.software_installer.open_official_website(sw_info)

        elif stage == "awaiting_run_permission":
            # Step 2: Execute installer
            self.update_companion("executing", f"Launching {name} setup...")
            self.signals.reasoning_step.emit(f"🚀 Executing {name} installer...")

            exec_res = self.software_installer.execute_installer()

            if exec_res.get("success"):
                self.update_companion("completed", f"{name} installation wizard launched.")
                self.signals.reasoning_step.emit(f"✨ {exec_res.get('message')}")
                self.signals.action_executed.emit("install_software", f"Launched installer for {name}")

                # Voice & Text confirmation
                text_msg = (
                    f"🎉 **{name} Installation Wizard Launched**\n\n"
                    f"{exec_res.get('message')}\n\n"
                    f"I will stay active to guide you through any setup prompts or verify the installation once finished."
                )
                voice_msg = f"I've launched the installer for {name}. Please proceed through the setup window, and let me know when you'd like me to verify the installation."
                self._respond_and_speak(text_msg, voice_msg)
            else:
                self.update_companion("idle", "Failed to launch installer.")
                self._respond_and_speak(
                    f"Could not launch installer: {exec_res.get('error')}",
                    f"There was an issue launching the installer. Please check your system permissions."
                )

    def _execute_terminal_remediation(self, command: str):
        self.update_companion("executing", f"Running: {command}...")
        self.signals.reasoning_step.emit(f"⚡ User Approved: Executing command `{command}`")

        try:
            # Run terminal command safely
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.audit_logger.log(
                f"Executed approved terminal command: {command}",
                category="TERMINAL_EXEC",
                risk_level="SAFE"
            )
            self.update_companion("completed", "Command initiated.")
            self.signals.action_executed.emit("terminal_command", f"Executed: {command}")
            msg = f"I've executed `{command}` in your terminal. Check the output window to see completion progress."
            self._respond_and_speak(msg, f"I've executed the command {command} for you.")
        except Exception as e:
            self._respond_and_speak(f"Error running command: {e}", "There was an error executing the command.")

    def _execute_wifi_fix(self, action_name: str):
        self.update_companion("executing", "Applying network remediation...")
        self.signals.reasoning_step.emit(f"⚡ Applying fix: {action_name}")

        res = self.wifi_troubleshooter.execute_fix(action_name)
        if res.get("success"):
            self.update_companion("completed", "Network remediation complete.")
            self.signals.action_executed.emit("wifi_remediation", res.get("message", "Done"))
            self._respond_and_speak(res.get("message", "Remediation applied."), res.get("message", "Network settings updated."))
        else:
            self._respond_and_speak(f"Failed to apply fix: {res.get('error')}", "Unable to update network settings.")

    def _execute_battery_fix(self, action_name: str):
        self.update_companion("executing", "Updating power settings...")
        self.signals.reasoning_step.emit(f"⚡ Updating power settings: {action_name}")

        res = self.battery_assistant.execute_power_action(action_name)
        if res.get("success"):
            self.update_companion("completed", "Power settings opened.")
            self.signals.action_executed.emit("power_settings", res.get("message", "Done"))
            self._respond_and_speak(res.get("message", "Settings opened."), "I've opened the battery saver settings for you.")
        else:
            self._respond_and_speak(f"Could not open settings: {res.get('error')}", "Unable to open battery settings.")

    def _respond_and_speak(self, text: str, voice: str):
        """Helper to send synchronized response to UI chat, companion, and audio TTS."""
        action = self.active_tech_action.get("type", "") if self.active_tech_action else ""
        status = "awaiting_confirmation" if self.active_tech_action else "responded"
        self._record_assistant_response(text, action, status)
        self.signals.response_ready.emit(text, voice)
        self.speak(voice)

    def _run_standard_customer_support_pipeline(self, command: str):
        """
        Executes the original CustomerSupportAgent screen reasoning pipeline
        for all general web, UI automation, and application questions.
        """
        # Call base implementation of screen analysis & actions
        # 1. Listen & Acknowledge
        self.update_companion("listening", "Listening to your request...")
        time.sleep(0.3)

        # 2. Screen Understanding via ScreenIntelligenceService
        self.update_companion("thinking", "Analyzing active window & screen structure...")
        self.signals.reasoning_step.emit("👀 Analyzing active window & screen structure")

        try:
            analysis = self.screen_intelligence.get_screen_understanding(
                command=command,
                conversation_history=self.conversation_history,
                additional_context={"task_state": dict(self.task_state)},
            )
        except Exception as error:
            print(f"[TechnicalSupportAgent] Screen analysis failed ({type(error).__name__}).")
            message = "I couldn't analyze the current screen, so I took no action. Check the AI connection or try again."
            self.update_companion("error", message)
            self.signals.reasoning_step.emit(message)
            self.audit_logger.log(
                f"Screen analysis failed ({type(error).__name__})",
                category="ANALYSIS_ERROR",
                risk_level="HIGH_RISK",
            )
            return

        context = self.screen_intelligence.current_context
        self.last_detected_website = context.get("website", "General Application")
        self.last_detected_page_type = context.get("page_type", "Standard Window")
        self.signals.context_updated.emit(context)

        if analysis.get("cache_hit"):
            self.signals.reasoning_step.emit("⚡ Reused cached screen analysis (instant response, zero API overhead)")

        self.audit_logger.log(
            f"Detected {context.get('website')} - {context.get('page_type')} ({context.get('browser')})",
            category="CONTEXT",
            risk_level="INFO"
        )

        # 3. Visual Confidence Check Guard
        if not analysis.get("confidence_verified", True):
            warning_msg = analysis.get("confidence_warning", self.screen_intelligence.LOW_CONFIDENCE_MESSAGE)
            self.update_companion("speaking", warning_msg)
            self.signals.reasoning_step.emit("⚠️ Visual confidence check failed: Safely pausing automation")
            self.signals.response_ready.emit(warning_msg, warning_msg)
            self.speak(warning_msg)
            return

        # Emit reasoning steps
        steps = analysis.get("reasoning_steps", [])
        for step in steps:
            self.signals.reasoning_step.emit(step)
            time.sleep(0.15)

        # 4. Target Element & Highlighting
        target = analysis.get("target_element", {})
        target_found = target.get("found", False)
        target_x = target.get("x", -1)
        target_y = target.get("y", -1)
        target_w = target.get("w", 160)
        target_h = target.get("h", 44)
        target_label = target.get("label", "Element")

        if target_found and target_x > 0 and target_y > 0:
            from intent_platform.core.support.highlighter import highlight_element
            self.signals.reasoning_step.emit(f"🎯 Highlighting '{target_label}'")
            highlight_element(target_x, target_y, target_w, target_h, target_label)

        # 5. Formulate Multimodal Responses
        explanation_text = analysis["explanation_text"]
        explanation_voice = analysis["explanation_voice"]

        self.signals.response_ready.emit(explanation_text, explanation_voice)

        # 6. Safety & Permission Assessment
        suggested_action = analysis.get("suggested_action", "highlight")
        action_payload = self.safety_manager.prepare_action(
            action_name=suggested_action,
            target_coords=(target_x, target_y) if target_found else None,
            target_label=target_label,
            details=analysis
        )
        self.task_state["screen"] = analysis.get("screen_context", {})
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
            self.update_companion("waiting", confirm_prompt or "Waiting for your confirmation...")
            self.signals.reasoning_step.emit(f"🖱️ Waiting for your confirmation to continue ({risk_level})")
            self.signals.confirmation_required.emit(action_payload)
            self.speak(full_voice)
        else:
            self.update_companion("speaking", explanation_voice)
            self.speak(explanation_voice)
            self._execute_action_direct(action_payload)
