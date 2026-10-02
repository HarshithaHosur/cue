"""Text-only web agent with Groq primary and Gemini fallback providers."""

import json
import logging
import os
from typing import Optional

from config.settings import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("intent_os.web.agent")

SYSTEM_INSTRUCTION = """You are the Intent OS web assistant. Give accurate, concise answers grounded in this project context:

Intent OS is a multimodal, intent-driven AI agent. Its core pipeline is UNDERSTAND → OBSERVE → DECIDE → EXECUTE → VERIFY: it understands a user's intent, observes relevant context, decides what to do, executes an appropriate action, and verifies the result. The project aims to bridge the gap between chat-based AI that only tells people what to do and an agent that can understand intent and assist with tasks.

Text, voice, gestures, vision, and mouse/keyboard interaction are modalities intended to feed the same intent-processing layer, rather than separate assistants. Project use cases include customer support, technical troubleshooting, e-commerce assistance, desktop automation, and AI interview assistance. The conversational interview architecture can ask technical questions, understand responses, maintain context, and continue naturally.

Intent OS has web and desktop interfaces for the same underlying concept. The web version is the publicly deployable, cloud-compatible interface and currently provides text conversation; it does not access local devices. The desktop version runs locally and can use system capabilities such as screen observation, camera, microphone, gesture recognition, mouse, keyboard, and system-level actions. Do not claim that the web version performs local device actions or that an action occurred unless it actually did.

Help with questions, planning, explanations, and web-safe workflows using text only. You cannot see the user's screen or control their computer, browser, microphone, camera, files, or applications. Never invent project features. When asked for desktop control, explain that full device interaction is available in the local Intent OS Desktop Agent."""


class CloudAgentError(Exception):
    """Safe-to-handle provider failure without provider details."""


class CloudAgent:
    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL") or GEMINI_MODEL or "gemini-2.5-flash"
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    @property
    def configured(self) -> bool:
        return self.gemini_configured or self.groq_configured

    @property
    def gemini_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    def reply(self, message: str, history: list[dict[str, str]]) -> str:
        if not self.configured:
            raise CloudAgentError(
                "AI chat is not configured. Add GEMINI_API_KEY or GROQ_API_KEY to the server environment."
            )

        groq_error: Optional[CloudAgentError] = None
        if self.groq_configured:
            try:
                return self._reply_with_groq(message, history)
            except CloudAgentError as error:
                groq_error = error
                if not self.gemini_configured:
                    raise
                logger.warning("Groq unavailable; trying Gemini web-chat fallback (%s)", str(error))

        if self.gemini_configured:
            try:
                return self._reply_with_gemini(message, history)
            except CloudAgentError as gemini_error:
                if groq_error:
                    if "quota" in str(groq_error).lower() and "quota" in str(gemini_error).lower():
                        raise CloudAgentError(
                            "Groq and Gemini quotas are currently exhausted. Check both provider limits and try again."
                        ) from None
                    raise CloudAgentError(
                        f"Groq could not complete the request ({groq_error}). Gemini could not complete it either ({gemini_error})."
                    ) from None
                raise

        if groq_error:
            raise groq_error
        raise CloudAgentError("The AI service could not complete that request. Please try again shortly.")

    def _reply_with_gemini(self, message: str, history: list[dict[str, str]]) -> str:
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
            model_names = dict.fromkeys((self.model_name, "gemini-2.5-flash", "gemini-flash-latest"))
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

    def _reply_with_groq(self, message: str, history: list[dict[str, str]]) -> str:
        from groq import Groq

        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        messages.extend(
            {"role": item["role"], "content": item["content"]}
            for item in history
        )
        messages.append({"role": "user", "content": message})

        try:
            client = Groq(api_key=self.groq_api_key, timeout=30, max_retries=0)
            response = client.chat.completions.create(
                model=self.groq_model,
                messages=messages,
                max_tokens=1200,
            )
            answer = response.choices[0].message.content
            if not isinstance(answer, str) or not answer.strip():
                raise CloudAgentError("The AI returned an empty response. Please try again.")
            return answer.strip()
        except CloudAgentError:
            raise
        except Exception as error:
            status_code = getattr(error, "status_code", None)
            response = getattr(error, "response", None)
            response_text = getattr(response, "text", "")
            if status_code == 429 or type(error).__name__ == "RateLimitError":
                logger.warning("Groq request was rate-limited")
                raise CloudAgentError(
                    "Groq is currently rate-limited or out of quota. Wait a moment or check the Groq project's limits, then try again."
                ) from None
            if status_code in (401, 403):
                cloudflare_block = "error_code" in response_text and "1010" in response_text
                if cloudflare_block:
                    logger.warning("Groq request was blocked by the upstream network edge")
                    raise CloudAgentError(
                        "The network is blocking this Groq request before it reaches the AI service. Try another network or contact your network administrator."
                    ) from None
                logger.warning("Groq rejected the website request with HTTP status %s", status_code)
                raise CloudAgentError(
                    "Groq denied the website request. Check that the server-side key is active and that its Groq project has API access."
                ) from None
            if status_code is not None:
                logger.warning("Groq request failed with HTTP status %s", status_code)
            else:
                logger.warning("Groq request failed (%s)", type(error).__name__)
            if type(error).__name__ == "APIConnectionError":
                raise CloudAgentError("Groq could not be reached from this server. Check network access and try again.") from None
            if isinstance(error, (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError)):
                raise CloudAgentError("Groq returned an invalid response. Please try again.") from None
            raise CloudAgentError("Groq could not complete that request. Please try again shortly.") from None


cloud_agent = CloudAgent()