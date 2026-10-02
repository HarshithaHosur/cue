# ============================================================
#  INTERVIEW RUBRIC ENGINE
#  Manages evaluation criteria, rubric templates, live coverage
#  tracking, and evidence-linked gap detection.
# ============================================================

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RubricCriterion:
    criterion_id: str
    category: str              # e.g., "Technical", "System Design", "Communication"
    name: str                  # e.g., "Data Structures", "Failure Recovery", "Clarity"
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    state: str = "NOT_STARTED" # NOT_STARTED, MENTIONED, PARTIALLY_COVERED, SUFFICIENTLY_COVERED
    evidence_count: int = 0
    evidence_snippets: List[Dict[str, Any]] = field(default_factory=list)


class RubricEngine:
    """Configures and tracks evaluation rubrics during interviews."""

    DEFAULT_TEMPLATES = {
        "Technical": [
            {"category": "DSA", "name": "Data Structures", "keywords": ["array", "tree", "graph", "hash", "linked list", "stack", "queue"]},
            {"category": "DSA", "name": "Algorithms & Complexity", "keywords": ["o(n)", "complexity", "binary search", "sort", "recursion", "dynamic programming"]},
            {"category": "Core Engineering", "name": "OOP & Clean Code", "keywords": ["class", "inheritance", "interface", "refactor", "solid", "design pattern"]},
            {"category": "Core Engineering", "name": "DBMS & Indexing", "keywords": ["sql", "database", "index", "query", "transaction", "acid", "postgres", "mysql"]},
            {"category": "Core Engineering", "name": "OS & Concurrency", "keywords": ["thread", "process", "lock", "async", "deadlock", "memory", "concurrency"]}
        ],
        "System Design": [
            {"category": "Architecture", "name": "System Architecture", "keywords": ["architecture", "microservice", "monolith", "client", "server", "gateway"]},
            {"category": "Scalability", "name": "Scalability & Load Balancing", "keywords": ["scale", "load balancer", "horizontal", "sharding", "partition"]},
            {"category": "Reliability", "name": "Reliability & Failure Recovery", "keywords": ["failure", "fault", "circuit breaker", "retry", "fallback", "backup"]},
            {"category": "Data & Caching", "name": "Database Design & Caching", "keywords": ["redis", "cache", "invalidation", "ttl", "nosql", "replica"]},
            {"category": "Messaging", "name": "Asynchronous Messaging", "keywords": ["kafka", "queue", "rabbitmq", "pubsub", "event", "consumer"]}
        ],
        "Communication": [
            {"category": "Communication", "name": "Clarity & Structure", "keywords": ["first", "second", "tradeoff", "because", "approach", "summary"]},
            {"category": "Communication", "name": "Technical Articulation", "keywords": ["specifically", "architectural", "rationale", "implementation", "design"]},
            {"category": "Communication", "name": "Active Listening", "keywords": ["clarify", "assumption", "question", "requirement"]}
        ]
    }

    def __init__(self, custom_criteria: Optional[List[Dict[str, Any]]] = None, interview_type: str = "Technical"):
        self.criteria: List[RubricCriterion] = []
        self._load_criteria(custom_criteria, interview_type)

    def _load_criteria(self, custom: Optional[List[Dict[str, Any]]], interview_type: str):
        if custom:
            for idx, c in enumerate(custom):
                self.criteria.append(RubricCriterion(
                    criterion_id=c.get("criterion_id", f"crit_{idx+1}"),
                    category=c.get("category", "General"),
                    name=c.get("name", "Criterion"),
                    description=c.get("description", ""),
                    keywords=[k.lower() for k in c.get("keywords", [])],
                    state=c.get("state", "NOT_STARTED")
                ))
        else:
            # Load from templates based on interview type
            templates_to_load = []
            if interview_type in self.DEFAULT_TEMPLATES:
                templates_to_load.append(self.DEFAULT_TEMPLATES[interview_type])
            else:
                templates_to_load.append(self.DEFAULT_TEMPLATES["Technical"])
            templates_to_load.append(self.DEFAULT_TEMPLATES["Communication"])

            crit_count = 1
            for group in templates_to_load:
                for item in group:
                    self.criteria.append(RubricCriterion(
                        criterion_id=f"crit_{crit_count}",
                        category=item["category"],
                        name=item["name"],
                        keywords=[k.lower() for k in item["keywords"]],
                        state="NOT_STARTED"
                    ))
                    crit_count += 1

    def evaluate_transcript(self, speaker: str, text: str, timestamp: float) -> List[RubricCriterion]:
        """Analyzes speech against rubric criteria keywords and updates coverage state."""
        updated = []
        text_lower = text.lower()

        for crit in self.criteria:
            matched_keywords = [kw for kw in crit.keywords if kw in text_lower]
            if matched_keywords:
                crit.evidence_count += 1
                snippet_info = {
                    "timestamp": timestamp,
                    "speaker": speaker,
                    "text": text[:120],
                    "matched_keywords": matched_keywords
                }
                crit.evidence_snippets.append(snippet_info)

                # Transition state based on evidence count
                old_state = crit.state
                if crit.evidence_count >= 3:
                    crit.state = "SUFFICIENTLY_COVERED"
                elif crit.evidence_count >= 1:
                    crit.state = "PARTIALLY_COVERED"
                else:
                    crit.state = "MENTIONED"

                if crit.state != old_state:
                    updated.append(crit)
                    logger.info(f"[RubricEngine] Criterion '{crit.name}' transitioned to {crit.state}")

        return updated

    def get_gaps(self) -> List[RubricCriterion]:
        """Returns rubric criteria that are NOT_STARTED or only MENTIONED."""
        return [c for c in self.criteria if c.state in ("NOT_STARTED", "MENTIONED")]

    def get_coverage_percentage(self) -> float:
        if not self.criteria:
            return 100.0
        points = {
            "NOT_STARTED": 0.0,
            "MENTIONED": 0.3,
            "PARTIALLY_COVERED": 0.7,
            "SUFFICIENTLY_COVERED": 1.0
        }
        total_score = sum(points.get(c.state, 0.0) for c in self.criteria)
        return (total_score / len(self.criteria)) * 100.0

    def get_summary(self) -> Dict[str, Any]:
        """Returns full rubric breakdown."""
        return {
            "coverage_pct": self.get_coverage_percentage(),
            "total_criteria": len(self.criteria),
            "sufficiently_covered": sum(1 for c in self.criteria if c.state == "SUFFICIENTLY_COVERED"),
            "partially_covered": sum(1 for c in self.criteria if c.state == "PARTIALLY_COVERED"),
            "uncovered": sum(1 for c in self.criteria if c.state == "NOT_STARTED"),
            "criteria": [
                {
                    "criterion_id": c.criterion_id,
                    "category": c.category,
                    "name": c.name,
                    "state": c.state,
                    "evidence_count": c.evidence_count,
                    "evidence_snippets": c.evidence_snippets
                }
                for c in self.criteria
            ]
        }
