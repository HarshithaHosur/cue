# ============================================================
#  INTERVIEW MODULE — Data Models (dataclasses)
# ============================================================

import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class InterviewState(Enum):
    CREATED = "CREATED"
    CONFIGURED = "CONFIGURED"
    PERMISSIONS_CHECKING = "PERMISSIONS_CHECKING"
    PREFLIGHT = "PREFLIGHT"
    READY = "READY"
    MEETING_OPENING = "MEETING_OPENING"
    WAITING_FOR_PARTICIPANTS = "WAITING_FOR_PARTICIPANTS"
    LIVE = "LIVE"
    ENDING = "ENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    # Backward compatibility aliases
    SETUP = "CREATED"
    VERIFYING = "PREFLIGHT"
    ENDED = "COMPLETED"
    REPORTED = "COMPLETED"


class InterviewType(Enum):
    TECHNICAL = "Technical"
    CODING = "Coding"
    SYSTEM_DESIGN = "System Design"
    BEHAVIORAL = "Behavioral"
    HR = "HR"
    MIXED = "Mixed"
    APTITUDE = "Aptitude"


class CheckStatus(Enum):
    PENDING = "Pending"
    CHECKING = "Checking"
    PASSED = "Passed"
    FAILED = "Failed"
    DEGRADED = "Degraded"
    UNAVAILABLE = "Unavailable"


@dataclass
class InterviewSetup:
    interview_id: str = ""
    title: str = ""
    candidate_name: str = ""
    candidate_email: str = ""
    job_role: str = ""
    interview_type: str = "Technical"
    duration_minutes: int = 45
    difficulty: str = "Medium"
    meeting_platform: str = "Zoom"
    meeting_link: str = ""
    notes: str = ""
    resume_path: str = ""
    rubric_config: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "scheduled"


@dataclass
class InterviewEvent:
    event_id: str = ""
    interview_id: str = ""
    event_type: str = ""       # "observation", "question_asked", "note", "risk_detected", "rubric_gap", "resume_claim"
    message: str = ""
    payload: str = ""          # JSON string
    timestamp: float = field(default_factory=time.time)
    reviewed: bool = False


@dataclass
class TranscriptEntry:
    entry_id: str = ""
    interview_id: str = ""
    speaker: str = ""          # "candidate", "interviewer", or "unknown"
    text: str = ""
    duration: float = 0.0
    question_index: int = -1
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class InterviewQuestion:
    question_id: str = ""
    interview_id: str = ""
    index: int = 0
    text: str = ""
    category: str = ""         # "DSA", "System Design", "Behavioral", etc.
    difficulty: str = "Medium"
    asked_at: Optional[float] = None
    is_custom: bool = False


@dataclass
class InterviewNote:
    note_id: str = ""
    interview_id: str = ""
    question_index: int = -1
    content: str = ""
    note_type: str = "manual"  # "auto" or "manual"
    auto_analysis: str = ""    # JSON for AI-generated analysis
    timestamp: float = field(default_factory=time.time)


@dataclass
class VoiceMetrics:
    """Per-utterance or overall voice analysis."""
    wpm: float = 0.0
    filler_count: int = 0
    filler_rate: float = 0.0   # fillers per minute
    response_duration: float = 0.0
    clarity_estimate: float = 0.0   # 0-100
    fluency_estimate: float = 0.0   # 0-100
    confidence_estimate: float = 0.0  # 0-100
    communication_score: float = 0.0  # 0-100


@dataclass
class ObservationRecord:
    """A single integrity, behavior, or conversational observation."""
    observation_id: str = ""
    event_type: str = ""       # "overlapping_speech", "sensitive_question", "rubric_gap", "resume_claim", "paste_detected"
    message: str = ""
    count: int = 1
    level: str = "notice"      # "notice", "info", "warning"
    timestamp: float = field(default_factory=time.time)
    reviewed: bool = False
    reviewed_note: str = ""
    evidence_snippet: str = ""
