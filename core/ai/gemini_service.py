# ============================================================
#  GEMINI AI SERVICE — Multi-Modal Agent & Tool Calling
# ============================================================

import os
from typing import Optional, Dict, Any, List

from intent_platform.config.settings import GEMINI_API_KEY, GEMINI_MODEL
from intent_platform.core.automation import actions
from intent_platform.core.context.context_manager import ContextManager

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def _tool_open_app(app_name: str) -> str:
    """Opens or focuses an application, document or file by name."""
    return actions.open_item(app_name)

def _tool_close_window() -> str:
    """Closes the currently active window."""
    return actions.close_active_window()

def _tool_volume(direction: str, steps: int = 5) -> str:
    """Adjusts system volume up or down."""
    return actions.change_volume(direction, steps)

def _tool_screenshot() -> str:
    """Takes a full screen capture."""
    return actions.take_screenshot()

def _tool_new_tab() -> str:
    """Opens a new browser tab."""
    return actions.open_new_tab()

def _tool_close_tab() -> str:
    """Closes current browser tab."""
    return actions.close_tab()


class GeminiAgent:
    """Interface for Gemini multimodal queries and function calling."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.client_ready = False
        self.model = None

        if self.api_key and GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                tools = [
                    _tool_open_app,
                    _tool_close_window,
                    _tool_volume,
                    _tool_screenshot,
                    _tool_new_tab,
                    _tool_close_tab
                ]
                self.model = genai.GenerativeModel(
                    model_name=GEMINI_MODEL,
                    tools=tools
                )
                self.client_ready = True
            except Exception:
                self.client_ready = False

    def ask(self, prompt: str) -> str:
        """Sends user prompt to Gemini agent or returns intelligent local fallback."""
        if not self.client_ready or not self.model:
            p_lower = prompt.lower()
            if "chrome" in p_lower or "browser" in p_lower:
                actions.open_item("chrome")
                return "Offline Assistant: Opened Chrome."
            elif "notepad" in p_lower:
                actions.open_item("notepad")
                return "Offline Assistant: Opened Notepad."
            elif "screenshot" in p_lower:
                path = actions.take_screenshot()
                return f"Offline Assistant: {path}."
            elif "volume up" in p_lower:
                actions.change_volume("up", 5)
                return "Offline Assistant: Increased volume."
            elif "volume down" in p_lower:
                actions.change_volume("down", 5)
                return "Offline Assistant: Decreased volume."
            elif "new tab" in p_lower:
                actions.open_new_tab()
                return "Offline Assistant: Opened new tab."
            elif "close tab" in p_lower:
                actions.close_tab()
                return "Offline Assistant: Closed tab."
            else:
                context = ContextManager.get_current_context()
                return (
                    f"Gemini API key not configured or offline. "
                    f"Active App: {context.get('detected_app')}."
                )

        try:
            chat = self.model.start_chat(enable_automatic_function_calling=True)
            context = ContextManager.get_current_context()
            sys_prompt = f"[System Context: Current foreground app is '{context.get('detected_app')}', window title '{context.get('active_window_title')}']\nUser: {prompt}"
            response = chat.send_message(sys_prompt)
            return response.text
        except Exception as e:
            return f"Gemini Error: {str(e)}"

    def query(self, prompt: str) -> str:
        """Alias for ask."""
        return self.ask(prompt)
