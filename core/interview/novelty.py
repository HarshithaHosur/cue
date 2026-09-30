# ============================================================
#  PHASE 4: NOVELTY FEATURES — AI Interview Agent
# ============================================================

import time
import re
import math
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


# ── A. Evidence Linking ──

class EvidenceLinker:
    """Links report claims and timeline events to timestamped transcript snippets."""

    @staticmethod
    def create_evidence_ref(event_id: str, timestamp_s: float, snippet: str) -> Dict[str, Any]:
        mins = int(timestamp_s // 60)
        secs = int(timestamp_s % 60)
        chip_label = f"▶ {mins:02d}:{secs:02d}"
        return {
            "event_id": event_id,
            "timestamp": timestamp_s,
            "chip_label": chip_label,
            "snippet": snippet,
        }


# ── B. Personal Baseline Tracker ──

class PersonalBaselineTracker:
    """Learns candidate's normal gaze, head movement, and speaking pace during initial 60s."""

    def __init__(self, calibration_duration_s: float = 60.0):
        self.calibration_duration_s = calibration_duration_s
        self.start_time = time.time()
        self.is_calibrating = True

        self._gaze_samples: List[float] = []
        self._wpm_samples: List[float] = []

        self.mean_gaze = 0.90
        self.std_gaze = 0.05
        self.mean_wpm = 135.0
        self.std_wpm = 15.0

    def add_sample(self, gaze_score: float, wpm: float):
        now = time.time()
        if self.is_calibrating:
            self._gaze_samples.append(gaze_score)
            if wpm > 0:
                self._wpm_samples.append(wpm)

            if now - self.start_time >= self.calibration_duration_s:
                self._finalize_calibration()

    def _finalize_calibration(self):
        self.is_calibrating = False
        if self._gaze_samples:
            self.mean_gaze = sum(self._gaze_samples) / len(self._gaze_samples)
            var_gaze = sum((x - self.mean_gaze) ** 2 for x in self._gaze_samples) / len(self._gaze_samples)
            self.std_gaze = max(0.02, math.sqrt(var_gaze))

        if self._wpm_samples:
            self.mean_wpm = sum(self._wpm_samples) / len(self._wpm_samples)
            var_wpm = sum((x - self.mean_wpm) ** 2 for x in self._wpm_samples) / len(self._wpm_samples)
            self.std_wpm = max(5.0, math.sqrt(var_wpm))

        logger.info(f"Baseline Calibrated: Mean Gaze={self.mean_gaze:.2f}, Mean WPM={self.mean_wpm:.1f}")

    def evaluate_gaze_anomaly(self, gaze_score: float, k: float = 2.0) -> Optional[str]:
        if self.is_calibrating:
            return None
        threshold = self.mean_gaze - k * self.std_gaze
        if gaze_score < threshold:
            return f"Extended gaze away relative to candidate's baseline (Gaze={gaze_score:.2f}, Baseline={self.mean_gaze:.2f})"
        return None


# ── C. Paste -> Probe Generator ──

class PasteProbeGenerator:
    """Generates 3 'explain your code' probe questions on large paste events."""

    @staticmethod
    def generate_probes(pasted_code: str) -> List[Dict[str, str]]:
        lines = pasted_code.strip().split("\n")
        line_count = len(lines)
        first_line = lines[0][:40] if lines else "code snippet"

        return [
            {
                "question": f"Can you walk me through the logic starting at `{first_line}`?",
                "category": "Code Explanation",
                "difficulty": "Medium"
            },
            {
                "question": "What is the time and space complexity of this pasted algorithm?",
                "category": "Algorithmic Complexity",
                "difficulty": "Medium"
            },
            {
                "question": "How would you handle edge cases or exceptions in this code segment?",
                "category": "Edge Cases & Reliability",
                "difficulty": "Hard"
            }
        ]


# ── D. Coverage Map & Competency Rubric ──

class CompetencyCoverageMap:
    """Tracks rubric competencies (DSA, System Design, Communication, etc.) across asked questions."""

    DEFAULT_COMPETENCIES = [
        "DSA", "System Design", "Problem Solving", "Communication", "Domain Knowledge"
    ]

    def __init__(self, rubric_list: Optional[List[str]] = None):
        self.rubric = rubric_list if rubric_list else self.DEFAULT_COMPETENCIES
        self.covered: Dict[str, bool] = {comp: False for comp in self.rubric}

    def tag_question(self, question_text: str, category: str):
        text_upper = (question_text + " " + category).upper()
        for comp in self.rubric:
            if comp.upper() in text_upper or (comp == "DSA" and "ALGORITHM" in text_upper):
                self.covered[comp] = True

    def get_coverage_percentage(self) -> float:
        if not self.rubric:
            return 100.0
        count = sum(1 for v in self.covered.values() if v)
        return (count / len(self.rubric)) * 100.0

    def get_uncovered(self) -> List[str]:
        return [comp for comp, is_cov in self.covered.items() if not is_cov]


# ── E. Question Fairness Linter ──

class QuestionFairnessLinter:
    """Lints questions for protected-attribute topics (age, family status, religion, nationality, disability)."""

    PROTECTED_TERMS = {
        "age": [r"\bage\b", r"\bhow old\b", r"\bborn in\b", r"\bretirement\b"],
        "marital/family status": [r"\bmarried\b", r"\bchildren\b", r"\bkids\b", r"\bspouse\b", r"\bpregnant\b"],
        "religion": [r"\breligion\b", r"\bchurch\b", r"\bmosque\b", r"\btemple\b", r"\bpray\b"],
        "nationality/origin": [r"\bcitizen\b", r"\borigin\b", r"\bvisa status\b", r"\bnative language\b"],
        "disability/health": [r"\bdisability\b", r"\bmedical condition\b", r"\bsick leave\b", r"\bhealth issues\b"]
    }

    @classmethod
    def lint_question(cls, question_text: str) -> Optional[str]:
        text_lower = question_text.lower()
        for category, patterns in cls.PROTECTED_TERMS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return f"Fairness Notice: Question references sensitive topic ({category})"
        return None


# ── F. Candidate Transparency Receipt Exporter ──

class TransparencyReceiptExporter:
    """Exports a plain-language summary receipt of recorded categories and consent time."""

    @staticmethod
    def generate_receipt(candidate_name: str, consent_timestamp: float, observations: List[Dict]) -> Dict[str, Any]:
        counts = {}
        for obs in observations:
            et = obs.get("event_type", "monitoring_event")
            counts[et] = counts.get(et, 0) + 1

        consent_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(consent_timestamp)) if consent_timestamp > 0 else "Granted"

        return {
            "title": "Candidate Data & Monitoring Transparency Receipt",
            "candidate_name": candidate_name,
            "consent_timestamp": consent_str,
            "monitored_categories": [
                "Camera Presence & Gaze Alignment",
                "Speech Pace & Audio Waveform Activity",
                "Application Window & Tab Switch Counts",
                "Clipboard Paste Operations"
            ],
            "recorded_event_counts": counts,
            "privacy_disclaimer": "All metrics are processed locally for evaluation purposes only. No secret recording occurs.",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }
