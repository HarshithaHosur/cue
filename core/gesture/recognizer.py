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
        # Extended if tip is higher than PIP joint (y is lower) and further from wrist (0)
        wrist = landmarks[0]
        for i in range(1, 5):
            tip = landmarks[tips[i]]
            pip = landmarks[pips[i]]
            mcp = landmarks[mcps[i]]

            # Normal vertical check
            is_higher = tip.y < pip.y
            # Distance from wrist check
            d_tip_wrist = math.hypot(tip.x - wrist.x, tip.y - wrist.y)
            d_pip_wrist = math.hypot(pip.x - wrist.x, pip.y - wrist.y)
            d_mcp_wrist = math.hypot(mcp.x - wrist.x, mcp.y - wrist.y)

            is_extended = is_higher and (d_tip_wrist > d_pip_wrist > d_mcp_wrist * 0.9)
            states.append(is_extended)

        return states

    def is_index_pointing(self, landmarks) -> bool:
        """Determines if the index finger is extended exclusively for cursor mode."""
        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        thumb_mcp = landmarks[2]
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        index_mcp = landmarks[5]

        # Index MUST be clearly extended
        d_tip_wrist = math.hypot(index_tip.x - wrist.x, index_tip.y - wrist.y)
        d_pip_wrist = math.hypot(index_pip.x - wrist.x, index_pip.y - wrist.y)
        index_up = (index_tip.y < index_pip.y) and (d_tip_wrist > d_pip_wrist * 1.05)
        if not index_up:
            return False

        # Middle, Ring, Pinky MUST be curled closed
        for tip_idx, pip_idx in [(12, 10), (16, 14), (20, 18)]:
            tip = landmarks[tip_idx]
            pip = landmarks[pip_idx]
            if tip.y < pip.y and math.hypot(tip.x - wrist.x, tip.y - wrist.y) > math.hypot(pip.x - wrist.x, pip.y - wrist.y):
                return False

        # Thumb must NOT be pointing straight up (which would be thumbs up)
        if thumb_tip.y < thumb_mcp.y and math.hypot(thumb_tip.x - wrist.x, thumb_tip.y - wrist.y) > math.hypot(thumb_mcp.x - wrist.x, thumb_mcp.y - wrist.y) * 1.3:
            return False

        return True

    def detect_static_gesture(self, landmarks) -> Optional[str]:
        """Identifies static hand postures."""
        if not landmarks or len(landmarks) < 21:
            return None

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

        # 4. INDEX CURSOR: Only index extended (thumb can be near for pinch)
        if self.is_index_pointing(landmarks):
            return 'index_cursor'

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
