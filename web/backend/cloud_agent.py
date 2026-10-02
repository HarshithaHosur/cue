"""Text-only Gemini agent. Intentionally has no desktop automation tools."""

import logging
import os
from typing import Optional

from config.settings import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("intent_os.web.agent")

SYSTEM_INSTRUCTION = """You are the Intent OS web assistant. Help with questions, planning, explanations, and web-safe workflows using text only. You cannot see the user's screen or control their computer, browser, microphone, camera, files, or applications. Never claim to have performed an action on the user's device. When asked for desktop control, explain that the full action is available in the local Intent OS Desktop Agent. Be clear, concise, and practical."""


class CloudAgentError(Exception):
    """Safe-to-handle provider failure without provider details."""


class CloudAgent:
    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", GEMINI_MODEL or "gemini-2.5-flash")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def reply(self, message: str, history: list[dict[str, str]]) -> str:
        if not self.api_key:
            raise CloudAgentError("AI chat is not configured. Add GEMINI_API_KEY to the server environment.")

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            chat_history = [
                {
                    "role": "model" if item["role"] == "assistant" else "user",
                    "parts": [item["content"]],
                }
                for item in history
            ]
            model_names = dict.fromkeys((self.model_name, "gemini-flash-latest", "gemini-3.8-flash"))
            for model_name in model_names:
                try:
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=SYSTEM_INSTRUCTION,
                    )
                    chat = model.start_chat(history=chat_history)
                    response = chat.send_message(message)
                    answer = getattr(response, "text", "")
                    if not isinstance(answer, str) or not answer.strip():
                        raise CloudAgentError("The AI returned an empty response. Please try again.")
                    return answer.strip()
                except CloudAgentError:
                    raise
                except Exception as error:
                    logger.warning("Gemini request failed for configured model (%s)", type(error).__name__)
                    if type(error).__name__ == "ResourceExhausted":
                        raise CloudAgentError(
                            "Gemini quota is currently exhausted. Check the API project's plan and limits, then try again."
                        ) from None
                    if type(error).__name__ != "NotFound":
                        raise CloudAgentError(
                            "The AI service could not complete that request. Please try again shortly."
                        ) from None

            raise CloudAgentError(
                "The configured Gemini model is unavailable. Set GEMINI_MODEL to a supported model and try again."
            )
        except CloudAgentError:
            raise
        except Exception as error:
            logger.warning("Gemini request failed (%s)", type(error).__name__)
            raise CloudAgentError("The AI service could not complete that request. Please try again shortly.") from None


cloud_agent = CloudAgent()