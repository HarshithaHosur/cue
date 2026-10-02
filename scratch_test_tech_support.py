# ============================================================
#  TEST SUITE: AI TECHNICAL SUPPORT EXECUTIVE (MODULES 1 - 10)
# ============================================================

import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, r"d:\Ai_Build")

def run_all_tests():
    print("[TEST SUITE] Starting AI Technical Support Executive validation...")
    passed = 0
    total = 0

    # ────────────────────────────────────────────────────────────
    #  TEST 1: Module 1 — Software Installation Assistant
    # ────────────────────────────────────────────────────────────
    total += 1
    print("\n--- TEST 1: Module 1 Software Installation Assistant ---")
    try:
        from intent_platform.core.techsupport.software_installer import (
            SoftwareInstallationAssistant,
            SOFTWARE_CATALOG
        )
        assistant = SoftwareInstallationAssistant()

        # Match Python
        match_py = assistant.match_software("System please install Python")
        assert match_py is not None, "Failed to match Python request"
        assert match_py["name"] == "Python 3.11", f"Unexpected match: {match_py['name']}"
        assert "python.org" in match_py["official_url"], "Official URL mismatch"

        # Match VS Code
        match_code = assistant.match_software("I need vs code for development")
        assert match_code is not None, "Failed to match VS Code"
        assert "Microsoft.VisualStudioCode" == match_code["winget_id"], "Winget ID mismatch"

        # Prepare installation plan & permission check
        plan = assistant.prepare_installation_plan(match_py)
        assert plan["status"] == "ready_for_confirmation", "Plan not awaiting confirmation"
        assert "permission" in plan["explanation_text"].lower() or "permission" in plan["explanation_voice"].lower() or "confirm" in plan["confirmation_prompt"].lower(), "Missing permission gate"
        assert plan["risk_level"] == "MEDIUM_RISK", f"Incorrect risk level: {plan['risk_level']}"

        # Verify installation method check
        v_res = assistant.verify_installation(match_py)
        assert "installed" in v_res, "Verification result missing 'installed' key"
        print(f"[OK] Module 1 Verified: Python matched, official source '{match_py['official_url']}', permission prompt generated, verify check functional.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 1 failed: {e}")
        import traceback
        traceback.print_exc()

    # ────────────────────────────────────────────────────────────
    #  TEST 2: Module 2 & 7 — Terminal Error Diagnostics & Error Knowledge
    # ────────────────────────────────────────────────────────────
    total += 1
    print("\n--- TEST 2: Module 2 & 7 Terminal Error Diagnostics & Error Knowledge ---")
    try:
        from intent_platform.core.techsupport.terminal_diagnostics import TerminalErrorDiagnostics
        diag = TerminalErrorDiagnostics()

        sample_traceback = """
Traceback (most recent call last):
  File "C:/Users/Harshitha/app.py", line 42, in <module>
    import cv2
ModuleNotFoundError: No module named 'cv2'
"""
        # Test heuristic / reasoning engine directly
        result = diag._heuristic_diagnostic(
            extracted_text=sample_traceback,
            detected_errors=[{"error_type": "ModuleNotFoundError", "line": "ModuleNotFoundError: No module named 'cv2'"}],
            window_title="PowerShell - C:/Users/Harshitha/app.py"
        )

        assert result["error_type"] == "ModuleNotFoundError", f"Expected ModuleNotFoundError, got {result['error_type']}"
        assert "opencv-python" in result["recommended_command"], f"Expected pip install opencv-python, got {result['recommended_command']}"
        assert result["file_name"] == "C:/Users/Harshitha/app.py", f"File mismatch: {result['file_name']}"
        assert result["line_number"] == "42", f"Line mismatch: {result['line_number']}"
        assert len(result["beginner_explanation"]) > 10, "Beginner explanation too short"
        assert len(result["professional_explanation"]) > 10, "Professional explanation too short"
        assert len(result["safe_solution"]) > 10, "Safe solution too short"
        assert len(result["voice_response"]) > 10, "Voice response too short"

        print(f"[OK] Module 2 & 7 Verified: Extracted {result['error_type']} at line {result['line_number']} in {result['file_name']}. Recommended: '{result['recommended_command']}'.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 2 failed: {e}")
        import traceback
        traceback.print_exc()

    # ────────────────────────────────────────────────────────────
    #  TEST 3: Module 3 — WiFi Troubleshooting
    # ────────────────────────────────────────────────────────────
    total += 1
    print("\n--- TEST 3: Module 3 WiFi Troubleshooting ---")
    try:
        from intent_platform.core.techsupport.wifi_troubleshooter import WiFiTroubleshooter
        troubleshooter = WiFiTroubleshooter()

        report = troubleshooter.run_diagnostics()
        assert "status" in report, "Missing status key in Wi-Fi report"
        assert "wifi_enabled" in report, "Missing wifi_enabled key in Wi-Fi report"
        assert "internet_connected" in report, "Missing internet_connected key in Wi-Fi report"
        assert "explanation_text" in report, "Missing explanation_text"
        assert "explanation_voice" in report, "Missing explanation_voice"

        print(f"[OK] Module 3 Verified: Wi-Fi Status={report['status']}, Adapter='{report.get('ssid')}', Signal={report.get('signal')}, Online={report.get('internet_connected')}, Latency={report.get('latency_ms')}ms.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 3 failed: {e}")
        import traceback
        traceback.print_exc()

    # ────────────────────────────────────────────────────────────
    #  TEST 4: Module 4 — Battery Health Assistant
    # ────────────────────────────────────────────────────────────
    total += 1
    print("\n--- TEST 4: Module 4 Battery Health Assistant ---")
    try:
        from intent_platform.core.techsupport.battery_health import BatteryHealthAssistant
        batt_assistant = BatteryHealthAssistant()

        report = batt_assistant.analyze_battery()
        assert "percent" in report, "Missing battery percent"
        assert "power_plugged" in report, "Missing power_plugged state"
        assert "top_apps" in report, "Missing top_apps list"
        assert "explanation_text" in report, "Missing explanation_text"
        assert "explanation_voice" in report, "Missing explanation_voice"

        print(f"[OK] Module 4 Verified: Battery={report['percent']}%, Plugged={report['power_plugged']}, Runtime='{report.get('time_remaining_str')}', Top Drain App: {report['top_apps'][0]['name'] if report['top_apps'] else 'None'}.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 4 failed: {e}")
        import traceback
        traceback.print_exc()

    # ────────────────────────────────────────────────────────────
    #  TEST 5: Modules 5, 6, 8, 9, 10 — Technical Support Agent Orchestration
    # ────────────────────────────────────────────────────────────
    total += 1
    print("\n--- TEST 5: Orchestration (Voice, Permission, Screen, Companion, Audit) ---")
    try:
        from intent_platform.core.techsupport.tech_support_agent import TechnicalSupportAgent
        from intent_platform.core.support.audit_logger import global_audit_logger

        initial_audit_count = len(global_audit_logger.get_entries())

        agent = TechnicalSupportAgent()

        # Test intent routing for Software Install
        assert agent._is_software_install_request("system install python") is True, "Failed to classify install intent"
        assert agent._is_terminal_error_request("explain this error") is True, "Failed to classify terminal error intent"
        assert agent._is_wifi_request("my wifi is not working") is True, "Failed to classify wifi intent"
        assert agent._is_battery_request("check my battery") is True, "Failed to classify battery intent"

        # Mock Voice Engine
        spoken_phrases = []
        class MockVoiceEngine:
            def speak(self, text):
                spoken_phrases.append(text)

        # Mock Companion
        companion_states = []
        class MockCompanion:
            def update_companion_state(self, state, message):
                companion_states.append((state, message))

        agent.set_voice_engine(MockVoiceEngine())
        agent.set_companion(MockCompanion())

        # Test pipeline for Wi-Fi check
        agent._handle_wifi_troubleshooting("System check my wifi")

        assert len(spoken_phrases) > 0, "No voice output produced"
        assert len(companion_states) > 0, "No companion state updates produced"

        # Verify Audit Log entry was recorded (Module 10)
        final_audit_count = len(global_audit_logger.get_entries())
        assert final_audit_count > initial_audit_count, "No audit log entries recorded"

        recent_entry = global_audit_logger.get_recent_entries(1)[0]
        assert "short_time" in recent_entry, "Audit missing timestamp"
        assert "category" in recent_entry, "Audit missing category"

        print(f"[OK] Test 5 Verified: Companion received {len(companion_states)} updates, Voice spoke {len(spoken_phrases)} phrases, Audit logged {final_audit_count - initial_audit_count} events with timestamps.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 5 failed: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n====================================================")
    print(f"RESULTS: {passed}/{total} Tests Passed Successfully!")
    print(f"====================================================")
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
