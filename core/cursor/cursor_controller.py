# ============================================================
#  CURSOR CONTROLLER — Vision-Driven OS Mouse Engine
#  Translates hand landmarks into system mouse events with
#  sub-pixel velocity-adaptive smoothing, Win32 hardware calls,
#  hysteresis pinch-to-click, right-click, and drag-and-drop.
# ============================================================

import sys
import math
import time
from typing import Optional, Tuple, Any

import cv2
import pyautogui

if sys.platform == 'win32':
    import ctypes

from intent_platform.core.cursor.smoother import VelocityAdaptiveSmoother
from intent_platform.config.settings import (
    SMOOTHING_SLOW,
    SMOOTHING_FAST,
    PINCH_THRESHOLD_ENTER,
    PINCH_THRESHOLD_EXIT,
    CLICK_COOLDOWN,
    DRAG_ENTRY_TIME
)

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


class CursorController:
    """Controls OS mouse using MediaPipe hand landmarks with real hardware feel."""

    def __init__(self):
        self.screen_w, self.screen_h = pyautogui.size()
        self.smoother = VelocityAdaptiveSmoother(
            slow_alpha=SMOOTHING_SLOW,
            fast_alpha=SMOOTHING_FAST
        )

        # Comfortable mapping bounds (10% margins for easy corner reach)
        self.map_x_min = 0.10
        self.map_x_max = 0.90
        self.map_y_min = 0.10
        self.map_y_max = 0.90

        # State flags
        self.is_pinching = False
        self.is_right_pinching = False
        self.is_dragging = False

        # Timers
        self.pinch_start_time = 0.0
        self.last_action_time = 0.0
        self.prev_x = None
        self.prev_y = None

    def reset(self):
        """Reset state and release mouse buttons if held."""
        self.release()
        self.smoother.reset()
        self.is_pinching = False
        self.is_right_pinching = False
        self.is_dragging = False
        self.pinch_start_time = 0.0
        self.prev_x = None
        self.prev_y = None

    def release(self):
        """Safety release of all pressed mouse buttons."""
        if self.is_dragging or self.is_pinching:
            if sys.platform == 'win32':
                try:
                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
                except Exception:
                    pass
            else:
                try:
                    pyautogui.mouseUp(button='left')
                except Exception:
                    pass
            self.is_dragging = False

        self.is_pinching = False
        self.is_right_pinching = False
        self.pinch_start_time = 0.0

    def update(self, landmarks, frame_bgr=None) -> Optional[Tuple[int, int]]:
        """Processes current frame landmarks and updates OS mouse.
        
        Args:
            landmarks: MediaPipe normalized landmarks list.
            frame_bgr: Optional cv2 frame for drawing visual feedback.
            
        Returns:
            Tuple[int, int] of (screen_x, screen_y) or None.
        """
        if not landmarks or len(landmarks) < 21:
            return None

        current_time = time.time()

        # ── 1. Map Index Fingertip (Landmark 8) to Screen ──
        raw_cam_x = landmarks[8].x
        raw_cam_y = landmarks[8].y

        # Clamp to mapping region
        cx = max(self.map_x_min, min(raw_cam_x, self.map_x_max))
        cy = max(self.map_y_min, min(raw_cam_y, self.map_y_max))

        norm_x = (cx - self.map_x_min) / (self.map_x_max - self.map_x_min)
        norm_y = (cy - self.map_y_min) / (self.map_y_max - self.map_y_min)

        target_x = norm_x * (self.screen_w - 1)
        target_y = norm_y * (self.screen_h - 1)

        # Apply velocity-adaptive smoothing
        cursor_x, cursor_y = self.smoother.update(target_x, target_y)
        cursor_x = max(0, min(self.screen_w - 1, cursor_x))
        cursor_y = max(0, min(self.screen_h - 1, cursor_y))

        # Move mouse using native Win32 API for zero latency
        if sys.platform == 'win32':
            ctypes.windll.user32.SetCursorPos(cursor_x, cursor_y)
            if self.is_dragging:
                # Emit absolute mouse move event for robust text selection
                abs_x = int(cursor_x * 65535 / max(self.screen_w - 1, 1))
                abs_y = int(cursor_y * 65535 / max(self.screen_h - 1, 1))
                ctypes.windll.user32.mouse_event(0x0001 | 0x8000, abs_x, abs_y, 0, 0)
        else:
            pyautogui.moveTo(cursor_x, cursor_y)

        self.prev_x = cursor_x
        self.prev_y = cursor_y

        # ── 2. Pinch Distances ──
        thumb = landmarks[4]
        index = landmarks[8]
        middle = landmarks[12]

        left_pinch_dist = math.hypot(thumb.x - index.x, thumb.y - index.y)
        right_pinch_dist = math.hypot(thumb.x - middle.x, thumb.y - middle.y)

        # If both distances overlap, the requested thumb-index pinch is a left-click.
        left_is_pinched = (left_pinch_dist < PINCH_THRESHOLD_ENTER) if not self.is_pinching else (left_pinch_dist < PINCH_THRESHOLD_EXIT)

        # ── 3. Right Click Pinch Evaluation (Thumb + Middle) ──
        right_is_pinched = (
            not left_is_pinched
            and ((right_pinch_dist < PINCH_THRESHOLD_ENTER) if not self.is_right_pinching else (right_pinch_dist < PINCH_THRESHOLD_EXIT))
        )
        if right_is_pinched:
            if not self.is_right_pinching:
                self.is_right_pinching = True
                if (current_time - self.last_action_time) > CLICK_COOLDOWN:
                    if sys.platform == 'win32':
                        abs_x = int(cursor_x * 65535 / max(self.screen_w - 1, 1))
                        abs_y = int(cursor_y * 65535 / max(self.screen_h - 1, 1))
                        ctypes.windll.user32.mouse_event(0x0008 | 0x0010 | 0x8000, abs_x, abs_y, 0, 0)  # RIGHTDOWN + RIGHTUP
                    else:
                        pyautogui.rightClick()
                    self.last_action_time = current_time
        else:
            self.is_right_pinching = False

        # ── 4. Left Click & Drag State Machine (Thumb + Index) ──
        if left_is_pinched:
            if not self.is_pinching:
                # Pinch initiated: send LEFTDOWN immediately so drag & click start at exact position
                self.is_pinching = True
                self.pinch_start_time = current_time
                if sys.platform == 'win32':
                    abs_x = int(cursor_x * 65535 / max(self.screen_w - 1, 1))
                    abs_y = int(cursor_y * 65535 / max(self.screen_h - 1, 1))
                    ctypes.windll.user32.mouse_event(0x0002 | 0x8000, abs_x, abs_y, 0, 0)  # LEFTDOWN
                else:
                    pyautogui.mouseDown(button='left')
            else:
                # Pinch remains closed: automatic continuous drag mode
                self.is_dragging = True
        else:
            if self.is_pinching:
                # Release pinch: send LEFTUP (completing single click or releasing drag)
                if sys.platform == 'win32':
                    abs_x = int(cursor_x * 65535 / max(self.screen_w - 1, 1))
                    abs_y = int(cursor_y * 65535 / max(self.screen_h - 1, 1))
                    ctypes.windll.user32.mouse_event(0x0004 | 0x8000, abs_x, abs_y, 0, 0)  # LEFTUP
                else:
                    pyautogui.mouseUp(button='left')

                self.is_pinching = False
                self.is_dragging = False
                self.pinch_start_time = 0.0
                self.last_action_time = current_time

        # Visual feedback on camera frame
        if frame_bgr is not None:
            h, w = frame_bgr.shape[:2]
            ix = int(landmarks[8].x * w)
            iy = int(landmarks[8].y * h)
            color = (0, 0, 255) if self.is_dragging else ((0, 255, 255) if self.is_pinching else (0, 255, 0))
            cv2.circle(frame_bgr, (ix, iy), 8, color, -1)

        return (cursor_x, cursor_y)
