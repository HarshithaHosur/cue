# ============================================================
#  INTERVIEW MODULE — Configuration (all thresholds in ONE place)
# ============================================================

from dataclasses import dataclass, field


@dataclass
class InterviewConfig:
    """All configurable thresholds for the interview module.
    Persisted overrides via db.get_setting / db.set_setting.
    """

    # Identity Monitor
    multi_face_duration_s: float = 2.0
    no_face_duration_s: float = 5.0
    face_recheck_interval_s: float = 10.0
    face_mismatch_threshold: int = 3
    face_similarity_threshold: float = 0.6

    # Gaze & Head
    gaze_away_threshold_s: float = 4.0
    head_movement_window_s: float = 60.0
    head_movement_max_per_min: int = 20

    # App / Tab Switching
    app_switch_window_s: float = 120.0
    app_switch_max_count: int = 8
    tab_switch_window_s: float = 120.0
    tab_switch_max_count: int = 10

    # Screen & Camera
    camera_interrupt_s: float = 3.0
    screen_inactivity_s: float = 90.0
    screen_interrupt_s: float = 3.0

    # Paste
    paste_char_threshold: int = 300
    paste_line_threshold: int = 8
    store_paste_content: bool = True

    # Voice Analysis
    filler_words: list = field(default_factory=lambda: [
        "like", "you know", "basically", "actually", "sort of",
        "kind of", "i mean", "um", "uh", "right", "so"
    ])

    # Observation Cooldowns (seconds)
    observation_cooldown_s: float = 10.0

    # Communication Score Weights
    pace_weight: float = 0.25
    clarity_weight: float = 0.25
    fluency_weight: float = 0.25
    confidence_weight: float = 0.25

    # Demo Mode
    demo_mode: bool = True
    speak_feedback: bool = False

    # Answer silence threshold
    answer_silence_s: float = 6.0

    # Baseline calibration
    baseline_duration_s: float = 60.0
