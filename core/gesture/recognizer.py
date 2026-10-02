# ============================================================
#  GESTURE RECOGNITION ENGINE
#  Classifies static hand postures, directional horizontal swipes,
#  and dual-hand coordination (Two Palms / Two Peace Signs).
# ============================================================

import math
import time
from typing import Optional, List, Tuple, Any

from intent_platform.config.settings import GESTURE_COOLDOWN, SWIPE_COOLDOWN


class GestureRecognizer:
    """Detects static hand gestures, dynamic swipes, and dual-hand postures."""

    def __init__(self):
        self.wrist_history: List[Tuple[int, int, float]] = []
        self.last_gesture_time: float = 0.0
        self.last_swipe_time: float = 0.0

    @staticmethod
    def _distance(first, second) -> float:
        return math.sqrt(
            (first.x - second.x) ** 2
            + (first.y - second.y) ** 2
            + (getattr(first, "z", 0.0) - getattr(second, "z", 0.0)) ** 2
        )

    def _is_finger_extended(self, landmarks, tip_idx: int, pip_idx: int, mcp_idx: int) -> bool:
        wrist = landmarks[0]
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        mcp = landmarks[mcp_idx]
        tip_to_wrist = self._distance(tip, wrist)
        pip_to_wrist = self._distance(pip, wrist)
        mcp_to_wrist = self._distance(mcp, wrist)
        return tip_to_wrist > pip_to_wrist * 1.05 and pip_to_wrist > mcp_to_wrist * 0.9

    def get_finger_states(self, landmarks) -> List[bool]:
        """Returns boolean state [thumb, index, middle, ring, pinky] where True = extended."""
        tips = [4, 8, 12, 16, 20]
        pips = [2, 6, 10, 14, 18]
        mcps = [1, 5, 9, 13, 17]
        states = []

        # ── Thumb State ──
        # Thumb is extended if distance between tip (4) and pinky MCP (17) is greater than IP (3) to pinky MCP (17)
        # and tip is further from palm center than MCP (2)
        d_tip_pinky = math.hypot(landmarks[4].x - landmarks[17].x, landmarks[4].y - landmarks[17].y)
        d_ip_pinky = math.hypot(landmarks[3].x - landmarks[17].x, landmarks[3].y - landmarks[17].y)
        states.append(d_tip_pinky > d_ip_pinky * 1.05)

        # ── Index, Middle, Ring, Pinky States ──
        # Extension is measured relative to the palm so hand rotation does not matter.
        for i in range(1, 5):
            states.append(self._is_finger_extended(landmarks, tips[i], pips[i], mcps[i]))

        return states

    def is_index_pointing(self, landmarks) -> bool:
        """Determines if the index finger is extended exclusively for cursor mode."""
        # Index must be extended relative to the palm, regardless of hand rotation.
        if not self._is_finger_extended(landmarks, 8, 6, 5):
            return False

        # Middle, Ring, Pinky MUST be curled closed
        for tip_idx, pip_idx, mcp_idx in [(12, 10, 9), (16, 14, 13), (20, 18, 17)]:
            if self._is_finger_extended(landmarks, tip_idx, pip_idx, mcp_idx):
                return False

        return True

    def detect_static_gesture(self, landmarks) -> Optional[str]:
        """Identifies static hand postures."""
        if not landmarks or len(landmarks) < 21:
            return None

        # Give the exclusive index posture precedence over thumb direction.
        if self.is_index_pointing(landmarks):
            return 'index_cursor'

        fingers = self.get_finger_states(landmarks)
        thumb_ext = fingers[0]
        index_ext = fingers[1]
        middle_ext = fingers[2]
        ring_ext = fingers[3]
        pinky_ext = fingers[4]
        all_others_closed = not index_ext and not middle_ext and not ring_ext and not pinky_ext

        # 1. THUMBS UP & THUMBS DOWN: Highest priority to avoid any cursor confusion
        if all_others_closed:
            thumb_tip = landmarks[4]
            thumb_mcp = landmarks[2]
            wrist = landmarks[0]
            index_mcp = landmarks[5]

            # Thumbs Up: Thumb tip is higher than MCP and wrist
            if thumb_tip.y < thumb_mcp.y and thumb_tip.y < index_mcp.y:
                return 'thumbs_up'
            # Thumbs Down: Thumb tip is lower than MCP and wrist
            elif thumb_tip.y > thumb_mcp.y and thumb_tip.y > wrist.y:
                return 'thumbs_down'
            else:
                # Closed Fist: All fingers closed, thumb tucked
                return 'fist'

        # 2. PALM: All 4 fingers extended (or all 5)
        if index_ext and middle_ext and ring_ext and pinky_ext:
            return 'palm'

        # 3. PEACE: Index and Middle open, Ring and Pinky firmly closed
        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            return 'peace'

        # 5. FIST Fallback Check
        if not index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return 'fist'

        return None

    def detect_two_hands(self, hand1_landmarks, hand2_landmarks) -> Optional[str]:
        """Detects coordinated two-hand gestures: Two Open Palms or Two Peace Signs."""
        if not hand1_landmarks or not hand2_landmarks:
            return None

        g1 = self.detect_static_gesture(hand1_landmarks)
        g2 = self.detect_static_gesture(hand2_landmarks)

        if g1 == 'palm' and g2 == 'palm':
            return 'two_open_palms'
        if g1 == 'peace' and g2 == 'peace':
            return 'two_peace_signs'

        return None

    def detect_swipe(self, landmarks, frame_w: int = 1280, frame_h: int = 720) -> Optional[str]:
        """Detects high-velocity horizontal open-palm swipe gestures."""
        now = time.time()
        if now - self.last_swipe_time < SWIPE_COOLDOWN:
            self.wrist_history.clear()
            return None

        wrist = landmarks[0]
        wx = int(wrist.x * frame_w)
        wy = int(wrist.y * frame_h)
        self.wrist_history.append((wx, wy, now))

        # Keep recent 0.4s
        self.wrist_history = [p for p in self.wrist_history if now - p[2] < 0.4]
        if len(self.wrist_history) < 3:
            return None

        start_x, start_y, _ = self.wrist_history[0]
        end_x, end_y, _ = self.wrist_history[-1]
        dx = end_x - start_x
        dy = abs(end_y - start_y)

        # Swipe criteria: minimum 50px horizontal travel, under 140px vertical drift, open hand
        if abs(dx) > 50 and dy < 140:
            fingers = self.get_finger_states(landmarks)
            if sum(fingers[1:]) >= 3:
                self.wrist_history.clear()
                self.last_swipe_time = now
                # In mirrored camera view: moving hand to the right means dx > 0
                return 'swipe_right' if dx > 0 else 'swipe_left'

        return None

    def recognize(self, landmarks, frame_w: int = 1280, frame_h: int = 720) -> Optional[str]:
        """Top-level single hand evaluator."""
        now = time.time()

        # Check swipe first while updating history
        swipe = self.detect_swipe(landmarks, frame_w, frame_h)
        if swipe:
            self.last_gesture_time = now
            return swipe

        if now - self.last_gesture_time < GESTURE_COOLDOWN:
            return None

        static = self.detect_static_gesture(landmarks)
        if static:
            self.last_gesture_time = now
            self.wrist_history.clear()
            return static

        return None
