# ============================================================
#  INTENT PLATFORM — Global Configuration
# ============================================================

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
QML_DIR = BASE_DIR / "ui" / "companion" / "qml"

# ── Automatically Load .env (never hardcode secrets) ──
for env_candidate in [BASE_DIR / ".env", BASE_DIR.parent / ".env"]:
    if env_candidate.exists():
        load_dotenv(dotenv_path=env_candidate, override=False)
load_dotenv(override=False)


# ── Application ──
APP_NAME = "Intent AI Platform"
APP_VERSION = "2.0.0"
APP_ORG = "IntentAI"

# ── Window Dimensions ──
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 800

# ── Camera ──
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# ── Gesture Timing ──
ACTIVATION_TIME = 2.0
STABILITY_THRESHOLD = 80
INACTIVITY_TIMEOUT = 45
GESTURE_COOLDOWN = 0.5
SWIPE_COOLDOWN = 1.5

# ── Voice ──
VOICE_LISTEN_TIMEOUT = 3
VOICE_PHRASE_LIMIT = 6
TTS_RATE = 175
TTS_VOLUME = 0.9
WAKE_WORD = "system"

# ── Cursor ──
SMOOTHING_SLOW = 0.50
SMOOTHING_FAST = 0.95
PINCH_THRESHOLD_ENTER = 0.055
PINCH_THRESHOLD_EXIT = 0.075
CLICK_COOLDOWN = 0.20
DRAG_ENTRY_TIME = 0.28

# ── MongoDB ──
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "intent_platform")

# ── Gemini ──
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# ── Zoom Meeting SDK & RTMS ──
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID", "")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET", "")
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID", "")
ZOOM_SDK_KEY = os.getenv("ZOOM_SDK_KEY", ZOOM_CLIENT_ID)
ZOOM_SDK_SECRET = os.getenv("ZOOM_SDK_SECRET", ZOOM_CLIENT_SECRET)
ZOOM_RTMS_CLIENT_ID = os.getenv("ZOOM_RTMS_CLIENT_ID", ZOOM_CLIENT_ID)
ZOOM_RTMS_CLIENT_SECRET = os.getenv("ZOOM_RTMS_CLIENT_SECRET", ZOOM_CLIENT_SECRET)
