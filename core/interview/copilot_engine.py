# ============================================================
#  AI INTERVIEW COPILOT ENGINE
#  Real-time private intelligence co-pilot for the interviewer:
#  - Context-aware follow-up question generation
#  - Sensitive / risky question detection (non-accusatory)
#  - Code & screen region visual explanation
#  - Rubric gap & resume claim exploration suggestions
# ============================================================

import time
import re
import logging
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from PySide6.QtCore import QObject, Signal

from intent_platform.core.ai.gemini_service import GeminiAgent, GENAI_AVAILABLE
from intent_platform.config.settings import GEMINI_API_KEY
from intent_platform.core.interview.resume_parser import ResumeClaimTracker, ResumeClaim
from intent_platform.core.interview.rubric_engine import RubricEngine, RubricCriterion

logger = logging.getLogger(__name__)


@dataclass
class CopilotSuggestion:
    suggestion_id: str
    suggestion_type: str       # "FOLLOW_UP", "RESUME_PROBE", "RUBRIC_GAP", "RISK_ALERT", "CODE_PROBE", "COACHING"
    title: str
    content: str               # Suggested question or coaching advice
    reason: str
    evidence_text: str = ""
    evidence_timestamp: float = field(default_factory=time.time)
    priority: str = "medium"   # "high", "medium", "low"
    dismissed: bool = False
    asked: bool = False


class InterviewCopilotEngine(QObject):
    """Asynchronous AI Co-Pilot generating private real-time guidance for interviewers."""

    suggestion_ready = Signal(object)          # CopilotSuggestion
    risk_alert_ready = Signal(str, str, float) # (category, explanation, timestamp)
    visual_explain_ready = Signal(dict)        # {selected_text, explanation, complexity, follow_up}

    # Sensitive / protected attribute regex definitions
    SENSITIVE_PATTERNS = {
        "Age / Date of Birth": [
            r"\bhow old are you\b", r"\byour age\b", r"\bwhen were you born\b",
            r"\bwhat year did you graduate\b", r"\bhow close to retirement\b"
        ],
        "Marital / Family Status": [
            r"\bare you married\b", r"\bdo you have children\b", r"\bdo you have kids\b",
            r"\bplan on having children\b", r"\bpregnant\b", r"\bmarital status\b",
            r"\bwhat does your spouse do\b", r"\bwho takes care of your kids\b"
        ],
        "Religion / Beliefs": [
            r"\bwhat religion\b", r"\bwhat church\b", r"\bdo you attend\b",
            r"\breligious holidays\b", r"\bdo you pray\b"
        ],
        "Nationality / Origin / Citizenship": [
            r"\bwhere are you originally from\b", r"\bwhat is your native language\b",
            r"\bare you a citizen\b", r"\bwhere were you born\b", r"\bwhat is your race\b"
        ],
        "Health / Disability": [
            r"\bdo you have a disability\b", r"\bmedical condition\b", r"\bhealth issues\b",
            r"\btake sick leave often\b", r"\bpast illnesses\b", r"\bmental health\b"
        ]
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gemini: Optional[GeminiAgent] = None
        self._init_ai()
        self._suggestions: List[CopilotSuggestion] = []
        self._recent_topics: List[str] = []
        self._dismissed_ids: set = set()
        self._lock = threading.Lock()

    def _init_ai(self):
        if GENAI_AVAILABLE and GEMINI_API_KEY:
            try:
                self._gemini = GeminiAgent()
                logger.info("[CopilotEngine] Gemini AI Agent initialized successfully.")
            except Exception as e:
                logger.warning(f"[CopilotEngine] Could not initialize Gemini Agent: {e}")
                self._gemini = None
        else:
            self._gemini = None

    def analyze_interviewer_question(self, question_text: str, timestamp: float) -> Optional[Dict[str, Any]]:
        """Checks for potentially sensitive topics and produces non-accusatory guidance."""
        text_lower = question_text.lower()

        for category, patterns in self.SENSITIVE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text_lower):
                    explanation = (
                        f"Potentially sensitive topic detected ({category}). "
                        "Consider redirecting toward job-relevant technical or behavioral criteria."
                    )
                    self.risk_alert_ready.emit(category, explanation, timestamp)

                    sug = CopilotSuggestion(
                        suggestion_id=f"risk_{int(timestamp)}",
                        suggestion_type="RISK_ALERT",
                        title=f"⚠️ Sensitive Topic: {category}",
                        content="Consider redirecting: 'Could you share how your previous project experience applies to this role?'",
                        reason=explanation,
                        evidence_text=question_text,
                        evidence_timestamp=timestamp,
                        priority="high"
                    )
                    self._add_suggestion(sug)
                    return {"category": category, "explanation": explanation}

        return None

    def process_candidate_answer(
        self,
        candidate_text: str,
        recent_transcript: List[Dict[str, Any]],
        resume_tracker: Optional[ResumeClaimTracker] = None,
        rubric_engine: Optional[RubricEngine] = None,
        job_role: str = "Software Engineer",
        timestamp: Optional[float] = None
    ):
        """Asynchronously generates context-rich follow-up suggestions from candidate speech."""
        if timestamp is None:
            timestamp = time.time()

        if len(candidate_text.strip()) < 15:
            return

        def _worker():
            try:
                # 1. Check for unexplored rubric gaps
                rubric_gaps = rubric_engine.get_gaps() if rubric_engine else []
                rubric_focus = rubric_gaps[0].name if rubric_gaps else None

                # 2. Check for mentioned tech / claims
                matched_claims = []
                if resume_tracker:
                    for claim in resume_tracker.claims:
                        if any(kw in candidate_text.lower() for kw in claim.keywords):
                            matched_claims.append(claim)

                # 3. Generate targeted follow-up using AI or smart rule heuristics
                follow_up = self._generate_contextual_follow_up(
                    candidate_text, recent_transcript, matched_claims, rubric_focus, job_role
                )

                if follow_up:
                    sug = CopilotSuggestion(
                        suggestion_id=f"sug_{int(time.time()*1000)}",
                        suggestion_type="FOLLOW_UP",
                        title=follow_up.get("title", "💡 Suggested Follow-Up"),
                        content=follow_up.get("question", ""),
                        reason=follow_up.get("reason", ""),
                        evidence_text=candidate_text[:120],
                        evidence_timestamp=timestamp,
                        priority="medium"
                    )
                    self._add_suggestion(sug)

            except Exception as e:
                logger.exception(f"[CopilotEngine] Error processing candidate answer: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _generate_contextual_follow_up(
        self,
        candidate_text: str,
        recent_transcript: List[Dict[str, Any]],
        matched_claims: List[ResumeClaim],
        rubric_focus: Optional[str],
        job_role: str
    ) -> Optional[Dict[str, str]]:
        """Generates targeted question using Gemini AI or structured deterministic rules."""
        text_lower = candidate_text.lower()

        # Deterministic targeted probe generation for common tech stacks
        tech_probes = {
            "kafka": {
                "title": "💡 Follow-up: Kafka Architecture",
                "question": "You mentioned using Kafka. How did you handle message ordering guarantees and failure recovery if a consumer crashed?",
                "reason": "Candidate mentioned Kafka messaging but did not detail failure handling."
            },
            "redis": {
                "title": "💡 Follow-up: Caching Strategy",
                "question": "When using Redis, what cache invalidation strategy (e.g. Cache-Aside, Write-Through) did you implement?",
                "reason": "Candidate referenced Redis caching; explore consistency & invalidation tradeoffs."
            },
            "kubernetes": {
                "title": "💡 Follow-up: Container Orchestration",
                "question": "How did you configure pod autoscaling and handle zero-downtime rolling deployments in Kubernetes?",
                "reason": "Candidate mentioned Kubernetes; probe production deployment experience."
            },
            "docker": {
                "title": "💡 Follow-up: Containerization",
                "question": "What techniques did you use to optimize Docker image sizes and maintain security scanning in your build pipeline?",
                "reason": "Candidate noted Docker containerization."
            },
            "postgresql": {
                "title": "💡 Follow-up: Database Optimization",
                "question": "How did you analyze slow queries and design indexes in PostgreSQL for high-traffic tables?",
                "reason": "Candidate mentioned relational database experience; probe performance tuning."
            },
            "microservice": {
                "title": "💡 Follow-up: Microservices Tradeoffs",
                "question": "How did you manage distributed transactions and service-to-service communication latency in your microservices setup?",
                "reason": "Candidate referenced microservices architecture."
            }
        }

        for tech, probe in tech_probes.items():
            if tech in text_lower and tech not in self._recent_topics:
                self._recent_topics.append(tech)
                if len(self._recent_topics) > 10:
                    self._recent_topics.pop(0)
                return probe

        # Rubric gap probe fallback
        if rubric_focus and rubric_focus not in self._recent_topics:
            self._recent_topics.append(rubric_focus)
            return {
                "title": f"🎯 Rubric Exploration: {rubric_focus}",
                "question": f"Could you walk through how you approached {rubric_focus} in a complex project you worked on?",
                "reason": f"Rubric area '{rubric_focus}' has not been explored yet."
            }

        # Fallback AI-based prompt if Gemini available
        if self._gemini:
            prompt = (
                f"You are an expert interview coach for a {job_role} interview. "
                f"Candidate recently said: '{candidate_text[:300]}'. "
                "Generate one concise, direct technical follow-up question to probe their depth. "
                "Format: Return ONLY the question string, under 25 words."
            )
            try:
                res = self._gemini.generate_response(prompt)
                if res and len(res.strip()) > 10:
                    return {
                        "title": "💡 AI Follow-Up Suggestion",
                        "question": res.strip().strip('"'),
                        "reason": "Generated based on candidate's technical explanation."
                    }
            except Exception:
                pass

        return None

    def explain_visual_selection(self, selected_text_or_context: str, source: str = "screen_selection"):
        """Explains visible code or visual region selected by the interviewer."""
        def _worker():
            try:
                explanation = ""
                complexity = "O(n)"
                follow_up = "How would this behave under peak memory load?"

                if not selected_text_or_context.strip():
                    selected_text_or_context_safe = "Selected Screen Region"
                else:
                    selected_text_or_context_safe = selected_text_or_context

                # Check algorithmic patterns
                ctx_lower = selected_text_or_context_safe.lower()
                if "for " in ctx_lower and "for " in ctx_lower[ctx_lower.find("for ")+4:]:
                    complexity = "O(n²) Time Complexity (Nested Iteration)"
                    explanation = "Nested iteration loops through data quadratically. Consider using a hash map or two-pointer approach to optimize to O(n)."
                    follow_up = "Can you explain if this nested loop can be optimized to linear time using auxiliary memory?"
                elif "while " in ctx_lower or "for " in ctx_lower:
                    complexity = "O(n) Time Complexity, O(1) Space"
                    explanation = "Linear scan iterating across the collection. Standard traversal logic."
                    follow_up = "What are the boundary conditions and edge cases (e.g. empty input or negative values) for this loop?"
                elif "class " in ctx_lower or "def " in ctx_lower:
                    complexity = "Modular Component Definition"
                    explanation = "Defines class/method interface with encapsulated state and helper functions."
                    follow_up = "How does this implementation adhere to single-responsibility and error handling principles?"
                else:
                    explanation = f"Analyzed visible visual context from {source}. Content reflects active technical workspace."
                    complexity = "Context Analyzed"
                    follow_up = "Could you walk me through the design tradeoffs of this implementation?"

                result = {
                    "selected_text": selected_text_or_context_safe[:200],
                    "explanation": explanation,
                    "complexity": complexity,
                    "follow_up": follow_up,
                    "timestamp": time.time(),
                    "source": source
                }
                self.visual_explain_ready.emit(result)

            except Exception as e:
                logger.exception(f"[CopilotEngine] Error explaining visual selection: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _add_suggestion(self, sug: CopilotSuggestion):
        with self._lock:
            self._suggestions.append(sug)
            logger.info(f"[CopilotEngine] Dispatched suggestion: [{sug.suggestion_type}] {sug.title}")
        self.suggestion_ready.emit(sug)

    def dismiss_suggestion(self, suggestion_id: str):
        with self._lock:
            self._dismissed_ids.add(suggestion_id)
            for s in self._suggestions:
                if s.suggestion_id == suggestion_id:
                    s.dismissed = True
                    break

    def mark_suggestion_asked(self, suggestion_id: str):
        with self._lock:
            for s in self._suggestions:
                if s.suggestion_id == suggestion_id:
                    s.asked = True
                    break

    def get_active_suggestions(self) -> List[CopilotSuggestion]:
        with self._lock:
            return [s for s in self._suggestions if not s.dismissed and not s.asked]
