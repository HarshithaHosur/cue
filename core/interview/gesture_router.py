# ============================================================
#  INTERVIEW MODULE — Gesture Router
#  Installed as engine.gesture_interceptor ONLY while live.
# ============================================================

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GestureRouter:
    """Intercepts gestures during live interviews.

    Returns an action label string to consume the gesture, or None to
    let the default execute_gesture run.
    """

    def __init__(self):
        self.active = False
        self.on_next_question = None       # callable
        self.on_previous_question = None   # callable
        self.on_zoom_in = None             # callable
        self.on_zoom_out = None            # callable
        self.on_timeline_log = None        # callable(gesture_name, action_label)

    def intercept(self, gesture: str, context: str) -> Optional[str]:
        """Called by engine.gesture_interceptor.

        Returns action label to consume, or None for default behavior.
        """
        if not self.active:
            return None

        action = None

        if gesture == "swipe_right":
            action = "Next Question"
            if self.on_next_question:
                try:
                    self.on_next_question()
                except Exception as e:
                    logger.error(f"Gesture next question error: {e}")

        elif gesture == "swipe_left":
            action = "Previous Question"
            if self.on_previous_question:
                try:
                    self.on_previous_question()
                except Exception as e:
                    logger.error(f"Gesture previous question error: {e}")

        elif gesture == "thumbs_up":
            action = "Zoom In (Interview)"
            if self.on_zoom_in:
                try:
                    self.on_zoom_in()
                except Exception as e:
                    logger.error(f"Gesture zoom in error: {e}")

        elif gesture == "thumbs_down":
            action = "Zoom Out (Interview)"
            if self.on_zoom_out:
                try:
                    self.on_zoom_out()
                except Exception as e:
                    logger.error(f"Gesture zoom out error: {e}")

        elif gesture == "fist":
            # Observe only: log on timeline, return None so default screenshot runs
            if self.on_timeline_log:
                self.on_timeline_log("fist", "Screenshot captured")
            return None

        if action and self.on_timeline_log:
            try:
                self.on_timeline_log(gesture, action)
            except Exception as e:
                logger.error(f"Gesture timeline log error: {e}")

        return action
