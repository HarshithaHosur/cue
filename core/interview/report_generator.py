# ============================================================
#  INTERVIEW MODULE — Report Generator
# ============================================================

import time
import json
import logging
from typing import Dict, List, Any, Optional

from intent_platform.core.interview.store import interview_store

logger = logging.getLogger(__name__)


LIMITATIONS_NOTE = (
    "All estimates (clarity, fluency, confidence, communication score, gaze analysis) "
    "are computed using heuristic methods and may not fully reflect actual candidate performance. "
    "Speech metrics depend on STT accuracy, which varies with accent, background noise, "
    "and network conditions."
)

FINAL_DECISION_NOTE = "Final decision rests with the interviewer."


class ReportGenerator:
    """Generates the interview report from session data.

    Deterministic fallback when AI narrative is unavailable.
    """

    def generate(
        self,
        interview_id: str,
        voice_metrics: Dict,
        observations: List[Dict],
        questions: List[Dict],
        notes: List[Dict],
        transcript: List[Dict],
        setup: Dict,
        actual_duration_s: float = 0,
    ) -> Dict[str, Any]:
        """Build and save the report. Returns the full report dict."""

        # Planned vs actual duration
        planned_min = setup.get("duration_minutes", 45)
        actual_min = round(actual_duration_s / 60, 1) if actual_duration_s > 0 else 0

        # Question summaries
        question_summaries = []
        for q in questions:
            q_notes = [n for n in notes if n.get("question_index") == q.get("idx", q.get("index", -1))]
            q_transcript = [t for t in transcript if t.get("question_index") == q.get("idx", q.get("index", -1))]
            q_summary = {
                "question": q.get("text", ""),
                "category": q.get("category", ""),
                "asked": q.get("asked_at") is not None,
                "response_word_count": sum(len(t.get("text", "").split()) for t in q_transcript),
                "notes_count": len(q_notes),
            }
            question_summaries.append(q_summary)

        # Group observations
        obs_grouped = {}
        for o in observations:
            et = o.get("event_type", "other")
            if et not in obs_grouped:
                obs_grouped[et] = {"count": 0, "messages": [], "reviewed": 0}
            obs_grouped[et]["count"] += 1
            obs_grouped[et]["messages"].append(o.get("message", ""))
            if o.get("reviewed"):
                obs_grouped[et]["reviewed"] += 1

        # Strengths and improvements from notes
        strengths = []
        improvements = []
        for n in notes:
            if n.get("note_type") == "auto" and n.get("auto_analysis"):
                try:
                    analysis = json.loads(n["auto_analysis"]) if isinstance(n["auto_analysis"], str) else n["auto_analysis"]
                    strengths.extend(analysis.get("strengths", []))
                    improvements.extend(analysis.get("improvements", []))
                except (json.JSONDecodeError, TypeError):
                    pass

        report = {
            "candidate_information": {
                "name": setup.get("candidate_name", ""),
                "email": setup.get("candidate_email", ""),
                "role": setup.get("job_role", ""),
                "interview_type": setup.get("interview_type", ""),
                "difficulty": setup.get("difficulty", ""),
            },
            "interview_duration": {
                "planned_minutes": planned_min,
                "actual_minutes": actual_min,
            },
            "questions_asked": question_summaries,
            "communication_summary": {
                "average_wpm_estimate": voice_metrics.get("avg_wpm", 0),
                "total_detected_filler_words": voice_metrics.get("total_filler_count", 0),
                "average_filler_rate_estimate": voice_metrics.get("avg_filler_rate", 0),
                "clarity_estimate": voice_metrics.get("avg_clarity", 0),
                "fluency_estimate": voice_metrics.get("avg_fluency", 0),
                "note": "All metrics are estimates based on heuristic analysis.",
            },
            "technical_performance": {
                "questions_attempted": sum(1 for q in question_summaries if q["asked"]),
                "total_questions": len(question_summaries),
                "note": "Generated without AI narrative" if not strengths else "Based on auto-generated notes",
            },
            "problem_solving": {
                "note": "Assessed from code-related observations and question responses.",
            },
            "confidence_estimate": {
                "value": voice_metrics.get("avg_confidence", 0),
                "label": "estimate",
                "note": "Heuristic estimate based on hedging phrases, filler rate, and pace stability.",
            },
            "observations": obs_grouped,
            "strengths": strengths[:10] if strengths else ["No auto-generated strengths available."],
            "improvement_areas": improvements[:10] if improvements else ["No auto-generated improvement areas available."],
            "overall_recommendation": {
                "text": "Suggested next step: review the detailed observations and question performance before making a decision.",
                "note": FINAL_DECISION_NOTE,
            },
            "limitations": LIMITATIONS_NOTE,
            "final_note": FINAL_DECISION_NOTE,
            "generated_at": time.time(),
            "generation_method": "deterministic_fallback",
        }

        # Save to store
        interview_store.save_report(interview_id, report)
        interview_store.update_interview_status(interview_id, "reported")

        return report
