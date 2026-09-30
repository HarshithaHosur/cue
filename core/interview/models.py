# ============================================================
#  INTERVIEW MODULE — Data Models (dataclasses)
# ============================================================

import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class InterviewState(Enum):
    SETUP = "setup"
    VERIFYING = "verifying"
    LIVE = "live"
    ENDED = "ended"
    REPORTED = "reported"


class InterviewType(Enum):
    TECHNICAL = "Technical"
    HR = "HR"
    CODING = "Coding"
    APTITUDE = "Aptitude"


class CheckStatus(Enum):
    PENDING = "Pending"
    CHECKING = "Checking"
    PASSED = "Passed"
    FAILED = "Failed"


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
    meeting_link: str = ""
    notes: str = ""
    resume_path: str = ""
    created_at: float = field(default_factory=time.time)
    status: str = "scheduled"


@dataclass
class InterviewEvent:
    event_id: str = ""
    interview_id: str = ""
    event_type: str = ""       # e.g. "observation", "question_asked", "note", "command", "system"
    message: str = ""
    payload: str = ""          # JSON string
    timestamp: float = field(default_factory=time.time)
    reviewed: bool = False


@dataclass
class TranscriptEntry:
    entry_id: str = ""
    interview_id: str = ""
    speaker: str = ""          # "candidate" or "interviewer"
    text: str = ""
    duration: float = 0.0
    question_index: int = -1
    timestamp: float = field(default_factory=time.time)


@dataclass
class InterviewQuestion:
    question_id: str = ""
    interview_id: str = ""
    index: int = 0
    text: str = ""
    category: str = ""         # e.g. "Technical", "HR", "Coding"
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
    """Per-utterance or per-answer voice analysis."""
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
    """A single integrity/behavioral observation."""
    observation_id: str = ""
    event_type: str = ""       # e.g. "multi_face", "gaze_away", "tab_switch", "paste_detected"
    message: str = ""
    count: int = 1
    level: str = "notice"      # "notice" or "info"
    timestamp: float = field(default_factory=time.time)
    reviewed: bool = False
    reviewed_note: str = ""
