# ============================================================
#  MODULE 2 & 7: TERMINAL ERROR EXPLANATION & ERROR KNOWLEDGE
#  Deep diagnostics for Python, Java, Node, Git, C++, PowerShell,
#  Command Prompt, and VS Code terminal errors.
#  Combines screen capture + OCR + Gemini reasoning to explain:
#  - What caused the error
#  - Which file caused it
#  - Which line caused it
#  - Beginner-friendly explanation
#  - Professional explanation
#  - Safe solution & recommended command
# ============================================================

import os
import re
import json
import time
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image

from intent_platform.config.settings import GEMINI_API_KEY, GEMINI_MODEL
from intent_platform.core.support.screen_capture import EventDrivenScreenCapture
from intent_platform.core.support.ocr_engine import HighPrecisionOCREngine
from intent_platform.core.support.audit_logger import global_audit_logger

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class TerminalErrorDiagnostics:
    """
    Module 2 & 7: Terminal & Code Diagnostics Executive.
    Captures the foreground terminal or code window, uses OCR to locate errors,
    reasons with Gemini Flash to diagnose the root cause, and formulates
    both beginner-friendly and professional remediation steps.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY")
        self.capture_engine = EventDrivenScreenCapture()
        self.ocr_engine = HighPrecisionOCREngine()
        self.audit_logger = global_audit_logger
        self.client_ready = False

        if self.api_key and GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                self.client_ready = True
            except Exception as e:
                print(f"[TerminalDiagnostics] Gemini init error: {e}")
                self.client_ready = False

    def diagnose_active_terminal(self, command_hint: str = "") -> Dict[str, Any]:
        """
        Main pipeline:
        1. Capture active terminal/code editor window.
        2. Run OCR to extract terminal text and detected errors.
        3. Send to Gemini for dynamic reasoning.
        4. Return structured explanation (beginner, professional, solution, file, line).
        """
        start_time = time.time()
        self.audit_logger.log(
            "Terminal error diagnosis requested. Capturing active window...",
            category="TERMINAL_DIAG",
            risk_level="INFO"
        )

        # 1. Capture active window
        cap_result = self.capture_engine.capture_active_window()
        image_bytes = cap_result.get("image_bytes")
        window_title = cap_result.get("title", "Terminal")
        window_rect = cap_result.get("rect", [0, 0, 1920, 1080])

        # 2. Extract text via OCR
        ocr_result = self.ocr_engine.extract_text(image_bytes)
        full_text = ocr_result.get("full_text", "")
        detected_errors = ocr_result.get("detected_errors", [])

        # 3. Dynamic Gemini or Heuristic Reasoning
        analysis = self._reason_about_error(
            extracted_text=full_text,
            detected_errors=detected_errors,
            window_title=window_title,
            command_hint=command_hint
        )

        elapsed = round(time.time() - start_time, 2)
        analysis["elapsed_seconds"] = elapsed
        analysis["window_title"] = window_title

        self.audit_logger.log(
            f"Terminal error analyzed ({analysis.get('error_type', 'Error')}) in {elapsed}s",
            category="TERMINAL_DIAG",
            risk_level="INFO"
        )

        return analysis

    def _reason_about_error(
        self,
        extracted_text: str,
        detected_errors: List[Dict[str, Any]],
        window_title: str,
        command_hint: str
    ) -> Dict[str, Any]:
        """
        Uses Gemini 2.5 Flash to reason over the extracted terminal error.
        If offline, uses high-fidelity heuristic error understanding.
        """
        if self.client_ready and self.api_key and extracted_text.strip():
            try:
                model = genai.GenerativeModel("gemini-2.5-flash")
                prompt = f"""You are a Senior IT Technical Support Engineer and Software Diagnostician.
The user's active window is '{window_title}'.
The user asked: '{command_hint or "System explain this error."}'

Visible text extracted from the terminal or code window via high-precision OCR:
\"\"\"
{extracted_text[-2500:]}
\"\"\"

Detected error snippets:
{json.dumps(detected_errors, indent=2)}

Please thoroughly analyze this technical issue and return a STRICT JSON object with these EXACT keys:
{{
  "error_type": "<Short error name, e.g. ModuleNotFoundError, NullPointerException, SyntaxError, MergeConflict, ConnectionRefused>",
  "cause": "<Concise explanation of what caused the error>",
  "file_name": "<Name or path of the file that triggered the error, or 'Unknown/Terminal' if not applicable>",
  "line_number": "<Line number integer or string, or 'N/A' if not applicable>",
  "beginner_explanation": "<Simple, clear explanation in plain English for non-technical users>",
  "professional_explanation": "<In-depth technical breakdown of root cause, environment stack, and scope>",
  "safe_solution": "<Step-by-step resolution steps>",
  "recommended_command": "<Safe terminal command to fix it, e.g. 'pip install opencv-python', 'npm install', 'git status', or empty string>",
  "spoken_response": "<Natural conversational response for TTS audio. Friendly, empathetic, direct. 2-3 sentences.>"
}}
Do NOT wrap your output in markdown codeblocks. Return valid JSON only.
"""
                response = model.generate_content(prompt)
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]

                parsed = json.loads(raw_text.strip())
                return self._format_diagnostic_result(parsed)

            except Exception as e:
                print(f"[TerminalDiagnostics] Gemini analysis fallback: {e}")

        # Intelligent Fallback Diagnostician
        return self._heuristic_diagnostic(extracted_text, detected_errors, window_title)

    def _heuristic_diagnostic(
        self,
        extracted_text: str,
        detected_errors: List[Dict[str, Any]],
        window_title: str
    ) -> Dict[str, Any]:
        """
        High-fidelity heuristic engine covering Python, Node, Git, Java, C++, and Windows CLI errors.
        """
        text_lower = extracted_text.lower()

        # 1. Python ModuleNotFoundError / ImportError
        mod_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", extracted_text, re.IGNORECASE)
        if mod_match or "modulenotfounderror" in text_lower or "importerror" in text_lower:
            module_name = mod_match.group(1) if mod_match else "required_package"
            # Package alias mappings
            pkg_name = module_name
            if module_name == "cv2":
                pkg_name = "opencv-python"
            elif module_name == "PIL" or module_name == "pil":
                pkg_name = "pillow"
            elif module_name == "bs4":
                pkg_name = "beautifulsoup4"
            elif module_name == "sklearn":
                pkg_name = "scikit-learn"

            file_match = re.search(r'File "([^"]+)", line (\d+)', extracted_text)
            file_name = file_match.group(1) if file_match else "script.py"
            line_num = file_match.group(2) if file_match else "1"

            return self._format_diagnostic_result({
                "error_type": "ModuleNotFoundError",
                "cause": f"The Python package '{module_name}' is not installed in the active environment.",
                "file_name": file_name,
                "line_number": line_num,
                "beginner_explanation": f"Your program tried to use a library called '{module_name}', but your computer doesn't have it installed yet.",
                "professional_explanation": f"Python interpreter encountered an unresolvable import statement for module '{module_name}'. The package is missing from sys.path and the current virtual environment site-packages.",
                "safe_solution": f"Install the library by running: pip install {pkg_name}",
                "recommended_command": f"pip install {pkg_name}",
                "spoken_response": f"I analyzed your terminal. You have a ModuleNotFoundError because '{pkg_name}' is not installed. Would you like me to open the terminal and help you run 'pip install {pkg_name}'?"
            })

        # 2. Python SyntaxError
        if "syntaxerror" in text_lower:
            file_match = re.search(r'File "([^"]+)", line (\d+)', extracted_text)
            file_name = file_match.group(1) if file_match else "script.py"
            line_num = file_match.group(2) if file_match else "N/A"
            return self._format_diagnostic_result({
                "error_type": "SyntaxError",
                "cause": "Invalid Python syntax or missing delimiter (like a colon, bracket, or quotation mark).",
                "file_name": file_name,
                "line_number": line_num,
                "beginner_explanation": f"There is a typo or missing punctuation on line {line_num} of {file_name}.",
                "professional_explanation": "Python tokenizer/parser failed to parse source code token stream. Likely unclosed string literal, mismatched bracket, or missing statement colon.",
                "safe_solution": f"Check line {line_num} in {file_name} for unclosed parentheses, quotes, or missing colon after an if/for/def statement.",
                "recommended_command": "",
                "spoken_response": f"I detected a SyntaxError on line {line_num} in {file_name}. There is likely a missing colon, parenthesis, or quote that needs to be closed."
            })

        # 3. Node.js Cannot find module
        if "cannot find module" in text_lower or "err_module_not_found" in text_lower:
            node_mod = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", extracted_text, re.IGNORECASE)
            pkg = node_mod.group(1) if node_mod else "dependency"
            return self._format_diagnostic_result({
                "error_type": "MODULE_NOT_FOUND (Node.js)",
                "cause": f"Node.js package '{pkg}' is missing from node_modules.",
                "file_name": "package.json / entry script",
                "line_number": "N/A",
                "beginner_explanation": f"Your Node.js project is missing the '{pkg}' package.",
                "professional_explanation": f"Node.js module resolution algorithm failed to resolve '{pkg}' in local node_modules directory or global cache.",
                "safe_solution": f"Run npm install {pkg} or npm install to restore all project dependencies.",
                "recommended_command": f"npm install {pkg}",
                "spoken_response": f"I found a missing Node module '{pkg}'. You can install it using npm install {pkg}. Shall I help you run this in the terminal?"
            })

        # 4. Git Merge Conflict or Not a Git Repo
        if "fatal: not a git repository" in text_lower:
            return self._format_diagnostic_result({
                "error_type": "GitNotRepositoryError",
                "cause": "The current working directory does not contain a .git version control repository.",
                "file_name": "Terminal",
                "line_number": "N/A",
                "beginner_explanation": "You ran a Git command in a folder that isn't tracked by Git.",
                "professional_explanation": "Git command invoked without a valid git work-tree or git-dir in the current directory traversal.",
                "safe_solution": "Initialize a new repository using 'git init' or navigate to the project directory that contains .git.",
                "recommended_command": "git init",
                "spoken_response": "I detected a Git error. This folder is not a Git repository. Would you like me to help you initialize it or navigate to the correct folder?"
            })

        # 5. Generic Terminal Error Catch
        return self._format_diagnostic_result({
            "error_type": "TerminalExecutionError",
            "cause": "Command or script execution failed in the active terminal.",
            "file_name": window_title,
            "line_number": "N/A",
            "beginner_explanation": "The command encountered an error while executing in your terminal window.",
            "professional_explanation": f"Execution halted in '{window_title}' due to non-zero exit code or uncaught exception.",
            "safe_solution": "Inspect terminal output above, verify command arguments, and ensure all prerequisites are configured.",
            "recommended_command": "",
            "spoken_response": "I analyzed your terminal output and identified where the execution was halted. I've prepared the full breakdown on your screen."
        })

    def _format_diagnostic_result(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes and prepares full text and speech output."""
        err_type = raw.get("error_type", "Error")
        cause = raw.get("cause", "Execution failed")
        file_name = raw.get("file_name", "Unknown")
        line_num = str(raw.get("line_number", "N/A"))
        beginner = raw.get("beginner_explanation", cause)
        pro = raw.get("professional_explanation", cause)
        sol = raw.get("safe_solution", "Review script")
        cmd = raw.get("recommended_command", "")
        voice = raw.get("spoken_response") or f"I analyzed the terminal error. The issue is {err_type}: {cause}."

        full_text = (
            f"🔍 **Terminal Diagnostic Report**\n\n"
            f"• **Error Type:** `{err_type}`\n"
            f"• **Location:** File `{file_name}`, Line `{line_num}`\n"
            f"• **Root Cause:** {cause}\n\n"
            f"💡 **Beginner-Friendly Explanation:**\n{beginner}\n\n"
            f"🛠 **Professional Analysis:**\n{pro}\n\n"
            f"✅ **Safe Solution:**\n{sol}"
        )
        if cmd:
            full_text += f"\n\n⌨️ **Recommended Command:**\n`{cmd}`"

        return {
            "error_type": err_type,
            "cause": cause,
            "file_name": file_name,
            "line_number": line_num,
            "beginner_explanation": beginner,
            "professional_explanation": pro,
            "safe_solution": sol,
            "recommended_command": cmd,
            "full_text": full_text,
            "voice_response": voice,
            "has_remediation_command": bool(cmd)
        }
