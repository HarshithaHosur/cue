# ============================================================
#  GESTURE EXECUTOR — Context-Aware Gesture Dispatcher
#  Executes system automation based on identified hand gesture
#  and the currently active foreground application.
# ============================================================

from typing import Optional
import pyautogui

from intent_platform.core.automation import actions
from intent_platform.core.context.context_manager import ContextManager
from intent_platform.database.connection import db


def execute_gesture(gesture_name: str, context: Optional[str] = None) -> Optional[str]:
    """
    Dispatches mapped action for a recognized gesture in the current context.
    
    Gestures:
      - 'thumbs_up': Volume Up if media active; Zoom In if zoomable/other app.
      - 'thumbs_down': Volume Down if media active; Zoom Out if zoomable/other app.
      - 'fist': Take Screenshot.
      - 'swipe_right': Next browser tab.
      - 'swipe_left': Previous browser tab.
    """
    if gesture_name in ('palm', 'peace', 'index_cursor', 'two_open_palms', 'two_peace_signs'):
        return f"Mode trigger: {gesture_name}"

    is_media = ContextManager.is_media_active()
    detected_app = context or ContextManager.detect_context()
    label = None

    try:
        if gesture_name == 'thumbs_up':
            if is_media or detected_app in ('spotify', 'vlc', 'media', 'youtube'):
                actions.change_volume('up', 5)
                label = "Volume Up"
            else:
                # Zoom in inside VS Code, PowerPoint, Browser, PDF, Image Viewer, etc.
                actions.zoom_in()
                label = "Zoom In"

        elif gesture_name == 'thumbs_down':
            if is_media or detected_app in ('spotify', 'vlc', 'media', 'youtube'):
                actions.change_volume('down', 5)
                label = "Volume Down"
            else:
                # Zoom out inside supported applications
                actions.zoom_out()
                label = "Zoom Out"

        elif gesture_name == 'fist':
            # Closed Fist -> Take Screenshot
            res = actions.take_screenshot()
            label = "Screenshot Saved"

        elif gesture_name == 'swipe_right':
            # Open Palm moving Left -> Right: Next Browser Tab
            actions.switch_tab('next')
            label = "Next Tab"

        elif gesture_name == 'swipe_left':
            # Open Palm moving Right -> Left: Previous Browser Tab
            actions.switch_tab('previous')
            label = "Previous Tab"

        if label:
            db.log_event("gesture", gesture_name, f"Action: {label} (Context: {detected_app})")
            return label

    except Exception as e:
        db.log_event("gesture_error", gesture_name, str(e))
        return None

    return None
