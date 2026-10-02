# ============================================================
#  INTERVIEW MODULE — Dynamic Evidence-Linked Report Generator
#  Builds real post-interview intelligence reports from session data.
#  NO fake scores, NO fake candidate names, NO fake hiring decisions.
# ============================================================

import time
import json
import logging
from typing import Dict, List, Any, Optional

from intent_platform.core.interview.store import interview_store

logger = logging.getLogger(__name__)

LIMITATIONS_NOTE = (
    "All conversational pacing, talk-time ratios, and observation timestamps are derived from "
    "runtime audio streams and transcript events. The AI serves as an objective co-pilot; "
    "final candidate evaluation and hiring decisions rest entirely with the human interviewer."
)

FINAL_DECISION_NOTE = "Human Interviewer Evaluation & Decision Only."


class ReportGenerator:
    """Generates traceable, evidence-linked interview reports."""

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
        resume_summary: Optional[Dict] = None,
        rubric_summary: Optional[Dict] = None,
        visual_selections: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Builds and saves the complete intelligence report."""

        planned_min = setup.get("duration_minutes", 45)
        actual_min = round(actual_duration_s / 60, 1) if actual_duration_s > 0 else 0

        # 1. Question summaries
        question_summaries = []
        for q in questions:
            q_notes = [n for n in notes if n.get("question_index") == q.get("idx", q.get("index", -1))]
            q_transcript = [t for t in transcript if t.get("question_index") == q.get("idx", q.get("index", -1))]
            question_summaries.append({
                "question": q.get("text", ""),
                "category": q.get("category", "General"),
                "asked": q.get("asked_at") is not None,
                "response_word_count": sum(len(t.get("text", "").split()) for t in q_transcript),
                "notes_count": len(q_notes),
            })

        # 2. Group observations with timestamps
        obs_grouped = {}
        for o in observations:
            et = o.get("event_type", "other")
            if et not in obs_grouped:
                obs_grouped[et] = {"count": 0, "messages": [], "timestamps": []}
            obs_grouped[et]["count"] += 1
            obs_grouped[et]["messages"].append(o.get("message", ""))
            obs_grouped[et]["timestamps"].append(o.get("timestamp", 0))

        # 3. Evidence Timeline items
        evidence_timeline = []
        for t in transcript[:50]:
            ts = t.get("timestamp", 0)
            mins = int((ts % 3600) // 60)
            secs = int(ts % 60)
            evidence_timeline.append({
                "chip_label": f"▶ {mins:02d}:{secs:02d}",
                "speaker": t.get("speaker", "unknown").capitalize(),
                "text": t.get("text", ""),
                "timestamp": ts
            })

        # 4. Talk-Time Metrics
        iv_talk_pct = voice_metrics.get("interviewer_talk_pct")
        cand_talk_pct = voice_metrics.get("candidate_talk_pct")
        interruptions = voice_metrics.get("interruptions", [])

        # 5. Coaching Observations
        coaching_notes = []
        if iv_talk_pct is not None and iv_talk_pct > 65:
            coaching_notes.append("High interviewer talk-time ratio observed. Consider allowing longer pauses for candidate technical depth.")
        elif iv_talk_pct is not None:
            coaching_notes.append("Balanced dialogue distribution between interviewer and candidate.")

        if interruptions:
            coaching_notes.append(f"{len(interruptions)} overlapping speech / interruption event(s) detected during discussion.")

        # Check for sensitive alerts
        sensitive_events = [o for o in observations if "sensitive" in o.get("event_type", "").lower() or "fairness" in o.get("event_type", "").lower()]
        if sensitive_events:
            coaching_notes.append(f"Noted {len(sensitive_events)} potentially sensitive topic query alert(s).")

        report = {
            "interview_details": {
                "candidate_name": setup.get("candidate_name", "Candidate"),
                "candidate_email": setup.get("candidate_email", ""),
                "job_role": setup.get("job_role", "Software Engineer"),
                "interview_type": setup.get("interview_type", "Technical"),
                "difficulty": setup.get("difficulty", "Medium"),
                "meeting_platform": setup.get("meeting_platform", "Zoom"),
                "meeting_link": setup.get("meeting_link", ""),
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(setup.get("created_at", time.time()))),
                "planned_minutes": planned_min,
                "actual_minutes": actual_min,
            },
            "conversation_analysis": {
                "interviewer_talk_pct": iv_talk_pct,
                "candidate_talk_pct": cand_talk_pct,
                "interviewer_talk_s": voice_metrics.get("interviewer_talk_s", 0),
                "candidate_talk_s": voice_metrics.get("candidate_talk_s", 0),
                "interviewer_words": voice_metrics.get("interviewer_words", 0),
                "candidate_words": voice_metrics.get("candidate_words", 0),
                "interruption_count": len(interruptions),
                "interruptions": interruptions,
                "average_wpm": voice_metrics.get("avg_wpm", 0),
                "total_filler_words": voice_metrics.get("total_filler_count", 0),
            },
            "question_analysis": {
                "questions_configured": len(question_summaries),
                "questions_asked": sum(1 for q in question_summaries if q["asked"]),
                "summaries": question_summaries,
            },
            "rubric_coverage": rubric_summary or {
                "coverage_pct": 0.0, "total_criteria": 0, "criteria": []
            },
            "resume_coverage": resume_summary or {
                "total_claims": 0, "discussed_count": 0, "unexplored_count": 0, "claims": []
            },
            "technical_screen_analysis": {
                "visual_selections_count": len(visual_selections or []),
                "selections": visual_selections or [],
                "status": "Available" if visual_selections else "No screen capture selections recorded"
            },
            "observations": obs_grouped,
            "interviewer_coaching_summary": coaching_notes,
            "evidence_timeline": evidence_timeline,
            "limitations_disclaimer": LIMITATIONS_NOTE,
            "final_evaluator_notice": FINAL_DECISION_NOTE,
            "generated_at": time.time(),
        }

        # Save report
        interview_store.save_report(interview_id, report)
        interview_store.update_interview_status(interview_id, "completed")

        return report
