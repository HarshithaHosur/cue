# ============================================================
#  INTERVIEW MODULE — Voice Router (wake-word commands only)
# ============================================================

import re
import logging
from difflib import SequenceMatcher
from typing import Optional, Callable, Dict

logger = logging.getLogger(__name__)


class VoiceRouter:
    """Handles ONLY wake-word interview commands with fuzzy matching.

    Returns short feedback for the companion, or None if unrecognized.
    """

    def __init__(self):
        self._actions: Dict[str, Callable] = {}
        self._commands = {
            "next question": ["next question", "go to next question", "next"],
            "previous question": ["previous question", "go back", "go to previous question", "last question"],
            "open candidate resume": ["open candidate resume", "open resume", "show resume", "candidate resume"],
            "zoom into screen": ["zoom into screen", "zoom in", "zoom into", "zoom in screen"],
            "zoom out": ["zoom out", "zoom out screen", "zoom out of screen"],
            "take notes": ["take notes", "take a note", "note this", "write note"],
            "mark this answer": ["mark this answer", "mark answer", "star this answer", "bookmark"],
            "generate summary": ["generate summary", "summarize", "summary", "summarize interview", "show summary"],
            "show interview report": ["show interview report", "show report", "interview report", "report"],
            "switch to candidate camera": ["switch to candidate camera", "show camera", "candidate camera", "switch camera"],
            "switch to screen share": ["switch to screen share", "show screen", "screen share", "switch screen"],
            "end interview": ["end interview", "stop interview", "finish interview", "end the interview"],
            "confirm": ["confirm", "yes confirm", "yes"],
        }

    def register_action(self, command_key: str, callback: Callable):
        self._actions[command_key] = callback

    def handle(self, text: str) -> Optional[str]:
        """Try to match text to a command. Returns feedback string or None."""
        text_lower = text.strip().lower()
        if not text_lower:
            return None

        best_match = None
        best_score = 0.0

        for cmd_key, synonyms in self._commands.items():
            for syn in synonyms:
                score = SequenceMatcher(None, text_lower, syn).ratio()
                if score > best_score:
                    best_score = score
                    best_match = cmd_key

            # Also try if the text contains the synonym
            for syn in synonyms:
                if syn in text_lower:
                    if len(syn) > 3:  # avoid very short matches
                        best_match = cmd_key
                        best_score = max(best_score, 0.85)

        if best_score < 0.55:
            return None

        if best_match and best_match in self._actions:
            try:
                result = self._actions[best_match]()
                return result or f"Executed: {best_match}"
            except Exception as e:
                logger.error(f"Voice router action error ({best_match}): {e}")
                return f"Error: {best_match}"

        if best_match:
            return f"Command recognized: {best_match} (not connected)"

        return None
