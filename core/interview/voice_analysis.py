# ============================================================
#  INTERVIEW MODULE — Voice Analysis
#  Per-utterance and per-answer metrics (all labeled "estimate").
# ============================================================

import re
import logging
from typing import List, Dict, Optional

from intent_platform.core.interview.config import InterviewConfig

logger = logging.getLogger(__name__)


class VoiceAnalyzer:
    """Analyzes speech metrics from transcript utterances."""

    def __init__(self, config: InterviewConfig):
        self.config = config
        self._utterances: List[Dict] = []
        self._current_answer_utterances: List[Dict] = []

    def analyze_utterance(self, text: str, duration: float) -> Dict:
        """Analyze a single utterance. Returns metrics dict."""
        words = text.split()
        word_count = len(words)

        # Words per minute
        wpm = (word_count / duration * 60.0) if duration > 0 else 0.0

        # Filler word detection
        text_lower = text.lower()
        filler_count = 0
        for filler in self.config.filler_words:
            # Count occurrences as whole phrases
            filler_count += len(re.findall(r'\b' + re.escape(filler) + r'\b', text_lower))

        filler_rate = (filler_count / duration * 60.0) if duration > 0 else 0.0

        # Clarity estimate (heuristic: penalize very low word count relative to duration)
        clarity = min(100.0, max(0.0, 100.0 - abs(wpm - 130) * 0.5))  # ~130 wpm is ideal

        # Fluency estimate (penalize fillers and very short utterances)
        fluency = max(0.0, 100.0 - filler_rate * 5.0)
        if word_count < 3 and duration > 2:
            fluency = max(0.0, fluency - 20.0)

        # Confidence estimate (penalize hedging phrases and high filler rate)
        hedging_phrases = ["i think maybe", "not sure", "i guess", "probably",
                           "i don't know", "sort of", "kind of"]
        hedge_count = sum(1 for h in hedging_phrases if h in text_lower)
        confidence = max(0.0, 100.0 - hedge_count * 15.0 - filler_rate * 3.0)

        # Communication score (weighted combination)
        comm_score = (
            clarity * self.config.clarity_weight +
            fluency * self.config.fluency_weight +
            confidence * self.config.confidence_weight +
            min(100.0, wpm / 1.5) * self.config.pace_weight  # normalize pace
        )

        metrics = {
            "wpm": round(wpm, 1),
            "word_count": word_count,
            "filler_count": filler_count,
            "filler_rate": round(filler_rate, 1),
            "duration": round(duration, 1),
            "clarity_estimate": round(clarity, 1),
            "fluency_estimate": round(fluency, 1),
            "confidence_estimate": round(confidence, 1),
            "communication_score": round(comm_score, 1),
        }

        self._utterances.append(metrics)
        self._current_answer_utterances.append(metrics)
        return metrics

    def start_new_answer(self):
        """Mark the start of a new answer segment."""
        self._current_answer_utterances = []

    def get_current_answer_metrics(self) -> Dict:
        """Aggregate metrics for the current answer."""
        return self._aggregate(self._current_answer_utterances)

    def get_overall_metrics(self) -> Dict:
        """Aggregate metrics for the entire interview."""
        return self._aggregate(self._utterances)

    def _aggregate(self, utterances: List[Dict]) -> Dict:
        if not utterances:
            return {
                "avg_wpm": 0, "total_filler_count": 0,
                "avg_filler_rate": 0, "total_duration": 0,
                "avg_clarity": 0, "avg_fluency": 0,
                "avg_confidence": 0, "avg_communication": 0,
                "utterance_count": 0,
            }
        n = len(utterances)
        return {
            "avg_wpm": round(sum(u["wpm"] for u in utterances) / n, 1),
            "total_filler_count": sum(u["filler_count"] for u in utterances),
            "avg_filler_rate": round(sum(u["filler_rate"] for u in utterances) / n, 1),
            "total_duration": round(sum(u["duration"] for u in utterances), 1),
            "avg_clarity": round(sum(u["clarity_estimate"] for u in utterances) / n, 1),
            "avg_fluency": round(sum(u["fluency_estimate"] for u in utterances) / n, 1),
            "avg_confidence": round(sum(u["confidence_estimate"] for u in utterances) / n, 1),
            "avg_communication": round(sum(u["communication_score"] for u in utterances) / n, 1),
            "utterance_count": n,
        }
