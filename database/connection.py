# ============================================================
#  DATABASE LAYER — Unified MongoDB & Local SQLite Fallback
# ============================================================

import os
import json
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

from intent_platform.config.settings import MONGO_URI, MONGO_DB, BASE_DIR

LOCAL_DB_PATH = BASE_DIR / "database" / "local_store.db"

INITIAL_GESTURES = [
    {
        'id': 'swipe_right',
        'name': 'Swipe Right',
        'type': 'System Trigger',
        'action': 'Next Slide / Next Tab',
        'description': 'Transition between active tabs or slides. Swipe horizontally right.',
        'icon': 'swipe_right',
        'enabled': True
    },
    {
        'id': 'swipe_left',
        'name': 'Swipe Left',
        'type': 'System Trigger',
        'action': 'Previous Slide / Prev Tab',
        'description': 'Transition between active tabs or slides. Swipe horizontally left.',
        'icon': 'swipe_left',
        'enabled': True
    },
    {
        'id': 'pinch',
        'name': 'Two Finger Pinch',
        'type': 'Cursor Trigger',
        'action': 'Select / Click',
        'description': 'Micro-scale adjustment or selection. Bring index finger and thumb together.',
        'icon': 'pinch',
        'enabled': True
    },
    {
        'id': 'fist',
        'name': 'Impact Fist',
        'type': 'System Trigger',
        'action': 'Play / Pause / Confirm',
        'description': 'High-priority confirm or media toggle. Close all fingers tight.',
        'icon': 'fist',
        'enabled': True
    },
    {
        'id': 'palm',
        'name': 'System Wave',
        'type': 'System Trigger',
        'action': 'Clear All / Wake HUD',
        'description': 'Macro command for waking UI or clearing overlays. Hold open palm steady.',
        'icon': 'palm',
        'enabled': True
    },
    {
        'id': 'peace',
        'name': 'Peace Sign',
        'type': 'System Trigger',
        'action': 'Deactivate Cursor Mode',
        'description': 'Disengages active cursor tracking. Extend index and middle finger.',
        'icon': 'peace',
        'enabled': True
    },
    {
        'id': 'thumbs_up',
        'name': 'Thumbs Up',
        'type': 'System Trigger',
        'action': 'Volume Up / Zoom In',
        'description': 'Increase system volume or zoom. Point thumb upwards with closed fist.',
        'icon': 'thumbs_up',
        'enabled': True
    },
    {
        'id': 'thumbs_down',
        'name': 'Thumbs Down',
        'type': 'System Trigger',
        'action': 'Volume Down / Zoom Out',
        'description': 'Decrease system volume or zoom. Point thumb downwards with closed fist.',
        'icon': 'thumbs_down',
        'enabled': True
    },
    {
        'id': 'index_cursor',
        'name': 'Index Point',
        'type': 'Cursor Mode',
        'action': 'Cursor Tracking',
        'description': 'Activate fine cursor control. Point index finger forward.',
        'icon': 'index_cursor',
        'enabled': True
    }
]

INITIAL_VOICE_COMMANDS = [
    {'id': 'open_chrome', 'command': 'open chrome', 'action': 'Launch Chrome', 'tips': ['Speak clearly', 'Use wake word']},
    {'id': 'open_browser', 'command': 'open browser', 'action': 'Launch Chrome', 'tips': ['Speak clearly']},
    {'id': 'open_notepad', 'command': 'open notepad', 'action': 'Launch Notepad', 'tips': ['Speak clearly']},
    {'id': 'open_calculator', 'command': 'open calculator', 'action': 'Launch Calculator', 'tips': ['Speak clearly']},
    {'id': 'open_file_explorer', 'command': 'open file explorer', 'action': 'Launch File Explorer', 'tips': ['Speak clearly']},
    {'id': 'open_settings', 'command': 'open settings', 'action': 'Launch Settings', 'tips': ['Speak clearly']},
    {'id': 'open_spotify', 'command': 'open spotify', 'action': 'Launch Spotify', 'tips': ['Speak clearly']},
    {'id': 'open_whatsapp', 'command': 'open whatsapp', 'action': 'Launch WhatsApp', 'tips': ['Speak clearly']},
    {'id': 'open_vscode', 'command': 'open vs code', 'action': 'Launch VS Code', 'tips': ['Speak clearly']},
    {'id': 'open_terminal', 'command': 'open terminal', 'action': 'Launch Terminal', 'tips': ['Speak clearly']},
    {'id': 'close_window', 'command': 'close window', 'action': 'Close Window', 'tips': ['Speak clearly']},
    {'id': 'minimize_window', 'command': 'minimize window', 'action': 'Minimize Window', 'tips': ['Speak clearly']},
    {'id': 'maximize_window', 'command': 'maximize window', 'action': 'Maximize Window', 'tips': ['Speak clearly']},
    {'id': 'play_pause', 'command': 'play pause', 'action': 'Play/Pause Media', 'tips': ['Speak clearly']},
    {'id': 'next_song', 'command': 'next song', 'action': 'Next Track', 'tips': ['Speak clearly']},
    {'id': 'previous_song', 'command': 'previous song', 'action': 'Previous Track', 'tips': ['Speak clearly']},
    {'id': 'volume_up', 'command': 'volume up', 'action': 'Increase Volume', 'tips': ['Speak clearly']},
    {'id': 'volume_down', 'command': 'volume down', 'action': 'Decrease Volume', 'tips': ['Speak clearly']},
    {'id': 'mute', 'command': 'mute', 'action': 'Mute Audio', 'tips': ['Speak clearly']},
    {'id': 'take_screenshot', 'command': 'take screenshot', 'action': 'Take Screenshot', 'tips': ['Speak clearly']},
    {'id': 'start_presentation', 'command': 'start presentation', 'action': 'Start Slideshow', 'tips': ['PowerPoint']},
    {'id': 'next_slide', 'command': 'next slide', 'action': 'Next Slide', 'tips': ['PowerPoint']},
    {'id': 'previous_slide', 'command': 'previous slide', 'action': 'Previous Slide', 'tips': ['PowerPoint']}
]


class DatabaseManager:
    """Manages database storage with transparent Mongo and SQLite fallback."""

    def __init__(self):
        self.is_mongo = False
        self.mongo_client = None
        self.mongo_db = None
        self._init_backend()

    def _init_backend(self):
        if PYMONGO_AVAILABLE:
            try:
                self.mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1000)
                self.mongo_client.server_info()  # Force connection check
                self.mongo_db = self.mongo_client[MONGO_DB]
                self.is_mongo = True
                self._seed_mongo()
                return
            except Exception:
                self.is_mongo = False
                self.mongo_client = None

        # Fallback to SQLite
        self._init_sqlite()

    def _init_sqlite(self):
        LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS kv_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS gestures (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    action TEXT,
                    description TEXT,
                    icon TEXT,
                    enabled INTEGER
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS voice_commands (
                    id TEXT PRIMARY KEY,
                    command TEXT,
                    action TEXT,
                    tips TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    action TEXT,
                    details TEXT,
                    timestamp TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT,
                    full_name TEXT,
                    face_encoding TEXT,
                    created_at TEXT
                )
            ''')
            conn.commit()

            # Seed if empty
            c.execute("SELECT count(*) FROM gestures")
            if c.fetchone()[0] == 0:
                for g in INITIAL_GESTURES:
                    c.execute(
                        "INSERT INTO gestures VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (g['id'], g['name'], g['type'], g['action'], g['description'], g['icon'], 1 if g['enabled'] else 0)
                    )
            c.execute("SELECT count(*) FROM voice_commands")
            if c.fetchone()[0] == 0:
                for v in INITIAL_VOICE_COMMANDS:
                    c.execute(
                        "INSERT INTO voice_commands VALUES (?, ?, ?, ?)",
                        (v['id'], v['command'], v['action'], json.dumps(v['tips']))
                    )
            conn.commit()

    def _seed_mongo(self):
        try:
            g_col = self.mongo_db["gestures"]
            if g_col.count_documents({}) == 0:
                g_col.insert_many([dict(g) for g in INITIAL_GESTURES])

            v_col = self.mongo_db["voice"]
            if v_col.count_documents({}) == 0:
                v_col.insert_many([dict(v) for v in INITIAL_VOICE_COMMANDS])

            s_col = self.mongo_db["settings"]
            if s_col.count_documents({"key": "wake_word"}) == 0:
                s_col.insert_one({"key": "wake_word", "value": "system"})
        except Exception:
            pass

    # ── KV Settings API ──
    def get_setting(self, key: str, default: Any = None) -> Any:
        if self.is_mongo:
            doc = self.mongo_db["settings"].find_one({"key": key})
            return doc.get("value", default) if doc else default
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM kv_settings WHERE key = ?", (key,))
            row = c.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except Exception:
                    return row[0]
            return default

    def set_setting(self, key: str, value: Any):
        if self.is_mongo:
            self.mongo_db["settings"].update_one(
                {"key": key},
                {"$set": {"value": value, "updated_at": datetime.datetime.utcnow().isoformat()}},
                upsert=True
            )
            return
        val_str = json.dumps(value) if not isinstance(value, str) else value
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO kv_settings (key, value) VALUES (?, ?)", (key, val_str))
            conn.commit()

    # ── Gestures API ──
    def get_gestures(self) -> List[Dict[str, Any]]:
        if self.is_mongo:
            return list(self.mongo_db["gestures"].find({}, {"_id": False}))
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM gestures")
            return [dict(r) for r in c.fetchall()]

    def update_gesture_action(self, gesture_id: str, new_action: str) -> bool:
        if self.is_mongo:
            res = self.mongo_db["gestures"].update_one({"id": gesture_id}, {"$set": {"action": new_action}})
            return res.matched_count > 0
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE gestures SET action = ? WHERE id = ?", (new_action, gesture_id))
            conn.commit()
            return c.rowcount > 0

    # ── Voice Commands API ──
    def get_voice_commands(self) -> List[Dict[str, Any]]:
        if self.is_mongo:
            return list(self.mongo_db["voice"].find({}, {"_id": False}))
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM voice_commands")
            rows = []
            for r in c.fetchall():
                d = dict(r)
                if isinstance(d.get("tips"), str):
                    try:
                        d["tips"] = json.loads(d["tips"])
                    except Exception:
                        d["tips"] = []
                rows.append(d)
            return rows

    # ── System Logs API ──
    def log_event(self, event_type: str, action: str, details: str = ""):
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        if self.is_mongo:
            self.mongo_db["logs"].insert_one({
                "event_type": event_type,
                "action": action,
                "details": details,
                "timestamp": now_iso
            })
            return
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO logs (event_type, action, details, timestamp) VALUES (?, ?, ?, ?)",
                (event_type, action, details, now_iso)
            )
            conn.commit()

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self.is_mongo:
            return list(self.mongo_db["logs"].find({}, {"_id": False}).sort([("timestamp", -1)]).limit(limit))
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT event_type, action, details, timestamp FROM logs ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in c.fetchall()]

    # ── User & Biometrics API ──
    def register_user(self, username: str, password_hash: str, full_name: str, face_encoding: Optional[List[float]] = None) -> bool:
        now_iso = datetime.datetime.utcnow().isoformat()
        enc_str = json.dumps(face_encoding) if face_encoding else ""
        if self.is_mongo:
            self.mongo_db["users"].update_one(
                {"username": username.lower()},
                {"$set": {
                    "username": username.lower(),
                    "password_hash": password_hash,
                    "full_name": full_name,
                    "face_encoding": face_encoding,
                    "created_at": now_iso
                }},
                upsert=True
            )
            return True
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO users (username, password_hash, full_name, face_encoding, created_at) VALUES (?, ?, ?, ?, ?)",
                (username.lower(), password_hash, full_name, enc_str, now_iso)
            )
            conn.commit()
            return True

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        if self.is_mongo:
            return self.mongo_db["users"].find_one({"username": username.lower()}, {"_id": False})
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username = ?", (username.lower(),))
            row = c.fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("face_encoding"):
                try:
                    d["face_encoding"] = json.loads(d["face_encoding"])
                except Exception:
                    pass
            return d


# Global database manager instance
db = DatabaseManager()
