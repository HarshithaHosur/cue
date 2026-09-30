# ============================================================
#  INTERVIEW MODULE — SQLite Store (idempotent table creation)
# ============================================================

import json
import sqlite3
import uuid
import time
import logging
from typing import List, Optional, Dict, Any

from intent_platform.config.settings import BASE_DIR

logger = logging.getLogger(__name__)

INTERVIEW_DB_PATH = BASE_DIR / "database" / "local_store.db"


class InterviewStore:
    """SQLite-based persistence for interview data.
    Uses the SAME SQLite file as the main app, with its own tables.
    Idempotent: tables are created if they do not exist.
    """

    def __init__(self):
        self._ensure_tables()

    def _conn(self):
        return sqlite3.connect(str(INTERVIEW_DB_PATH))

    def _ensure_tables(self):
        INTERVIEW_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS interviews (
                    interview_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    candidate_name TEXT NOT NULL,
                    candidate_email TEXT DEFAULT '',
                    job_role TEXT NOT NULL,
                    interview_type TEXT DEFAULT 'Technical',
                    duration_minutes INTEGER DEFAULT 45,
                    difficulty TEXT DEFAULT 'Medium',
                    meeting_link TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    resume_path TEXT DEFAULT '',
                    status TEXT DEFAULT 'scheduled',
                    created_at REAL,
                    started_at REAL,
                    ended_at REAL,
                    actual_duration_s REAL DEFAULT 0
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS interview_events (
                    event_id TEXT PRIMARY KEY,
                    interview_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT DEFAULT '',
                    payload TEXT DEFAULT '',
                    timestamp REAL,
                    reviewed INTEGER DEFAULT 0,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS interview_transcript (
                    entry_id TEXT PRIMARY KEY,
                    interview_id TEXT NOT NULL,
                    speaker TEXT DEFAULT 'candidate',
                    text TEXT DEFAULT '',
                    duration REAL DEFAULT 0,
                    question_index INTEGER DEFAULT -1,
                    timestamp REAL,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS interview_questions (
                    question_id TEXT PRIMARY KEY,
                    interview_id TEXT NOT NULL,
                    idx INTEGER DEFAULT 0,
                    text TEXT NOT NULL,
                    category TEXT DEFAULT '',
                    difficulty TEXT DEFAULT 'Medium',
                    asked_at REAL,
                    is_custom INTEGER DEFAULT 0,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS interview_notes (
                    note_id TEXT PRIMARY KEY,
                    interview_id TEXT NOT NULL,
                    question_index INTEGER DEFAULT -1,
                    content TEXT DEFAULT '',
                    note_type TEXT DEFAULT 'manual',
                    auto_analysis TEXT DEFAULT '',
                    timestamp REAL,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS interview_reports (
                    report_id TEXT PRIMARY KEY,
                    interview_id TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at REAL,
                    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
                )
            ''')
            conn.commit()

    # ── Interview CRUD ──
    def create_interview(self, data: Dict[str, Any]) -> str:
        iid = data.get("interview_id") or str(uuid.uuid4())
        with self._conn() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO interviews
                (interview_id, title, candidate_name, candidate_email, job_role,
                 interview_type, duration_minutes, difficulty, meeting_link, notes,
                 resume_path, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                iid,
                data.get("title", ""),
                data.get("candidate_name", ""),
                data.get("candidate_email", ""),
                data.get("job_role", ""),
                data.get("interview_type", "Technical"),
                data.get("duration_minutes", 45),
                data.get("difficulty", "Medium"),
                data.get("meeting_link", ""),
                data.get("notes", ""),
                data.get("resume_path", ""),
                data.get("status", "scheduled"),
                data.get("created_at", time.time())
            ))
            conn.commit()
        return iid

    def get_interview(self, interview_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM interviews WHERE interview_id = ?", (interview_id,))
            row = c.fetchone()
            return dict(row) if row else None

    def update_interview_status(self, interview_id: str, status: str, **kwargs):
        sets = ["status = ?"]
        vals = [status]
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(interview_id)
        with self._conn() as conn:
            c = conn.cursor()
            c.execute(f"UPDATE interviews SET {', '.join(sets)} WHERE interview_id = ?", vals)
            conn.commit()

    def list_interviews(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if status:
                c.execute("SELECT * FROM interviews WHERE status = ? ORDER BY created_at DESC", (status,))
            else:
                c.execute("SELECT * FROM interviews ORDER BY created_at DESC")
            return [dict(r) for r in c.fetchall()]

    def get_interview_count(self, status: Optional[str] = None) -> int:
        with self._conn() as conn:
            c = conn.cursor()
            if status:
                c.execute("SELECT COUNT(*) FROM interviews WHERE status = ?", (status,))
            else:
                c.execute("SELECT COUNT(*) FROM interviews")
            return c.fetchone()[0]

    # ── Events ──
    def add_event(self, interview_id: str, event_type: str, message: str,
                  payload: str = "", timestamp: Optional[float] = None) -> str:
        eid = str(uuid.uuid4())
        ts = timestamp or time.time()
        with self._conn() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO interview_events
                (event_id, interview_id, event_type, message, payload, timestamp, reviewed)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', (eid, interview_id, event_type, message, payload, ts))
            conn.commit()
        return eid

    def get_events(self, interview_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT * FROM interview_events WHERE interview_id = ? ORDER BY timestamp ASC",
                (interview_id,)
            )
            return [dict(r) for r in c.fetchall()]

    def mark_event_reviewed(self, event_id: str):
        with self._conn() as conn:
            c = conn.cursor()
            c.execute("UPDATE interview_events SET reviewed = 1 WHERE event_id = ?", (event_id,))
            conn.commit()

    # ── Transcript ──
    def add_transcript(self, interview_id: str, speaker: str, text: str,
                       duration: float = 0, question_index: int = -1,
                       timestamp: Optional[float] = None) -> str:
        eid = str(uuid.uuid4())
        ts = timestamp or time.time()
        with self._conn() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO interview_transcript
                (entry_id, interview_id, speaker, text, duration, question_index, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (eid, interview_id, speaker, text, duration, question_index, ts))
            conn.commit()
        return eid

    def get_transcript(self, interview_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT * FROM interview_transcript WHERE interview_id = ? ORDER BY timestamp ASC",
                (interview_id,)
            )
            return [dict(r) for r in c.fetchall()]

    # ── Questions ──
    def add_question(self, interview_id: str, index: int, text: str,
                     category: str = "", difficulty: str = "Medium",
                     is_custom: bool = False) -> str:
        qid = str(uuid.uuid4())
        with self._conn() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO interview_questions
                (question_id, interview_id, idx, text, category, difficulty, is_custom)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (qid, interview_id, index, text, category, difficulty, 1 if is_custom else 0))
            conn.commit()
        return qid

    def get_questions(self, interview_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT * FROM interview_questions WHERE interview_id = ? ORDER BY idx ASC",
                (interview_id,)
            )
            return [dict(r) for r in c.fetchall()]

    def mark_question_asked(self, question_id: str, asked_at: Optional[float] = None):
        ts = asked_at or time.time()
        with self._conn() as conn:
            c = conn.cursor()
            c.execute("UPDATE interview_questions SET asked_at = ? WHERE question_id = ?", (ts, question_id))
            conn.commit()

    # ── Notes ──
    def add_note(self, interview_id: str, content: str, question_index: int = -1,
                 note_type: str = "manual", auto_analysis: str = "",
                 timestamp: Optional[float] = None) -> str:
        nid = str(uuid.uuid4())
        ts = timestamp or time.time()
        with self._conn() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO interview_notes
                (note_id, interview_id, question_index, content, note_type, auto_analysis, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (nid, interview_id, question_index, content, note_type, auto_analysis, ts))
            conn.commit()
        return nid

    def get_notes(self, interview_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT * FROM interview_notes WHERE interview_id = ? ORDER BY timestamp ASC",
                (interview_id,)
            )
            return [dict(r) for r in c.fetchall()]

    # ── Reports ──
    def save_report(self, interview_id: str, report_dict: Dict[str, Any]) -> str:
        rid = str(uuid.uuid4())
        with self._conn() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO interview_reports (report_id, interview_id, report_json, created_at)
                VALUES (?, ?, ?, ?)
            ''', (rid, interview_id, json.dumps(report_dict, default=str), time.time()))
            conn.commit()
        return rid

    def get_report(self, interview_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT * FROM interview_reports WHERE interview_id = ? ORDER BY created_at DESC LIMIT 1",
                (interview_id,)
            )
            row = c.fetchone()
            if row:
                d = dict(row)
                d["report"] = json.loads(d["report_json"])
                return d
            return None

    def list_reports(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''
                SELECT r.report_id, r.interview_id, r.created_at, i.title, i.candidate_name, i.job_role
                FROM interview_reports r
                JOIN interviews i ON r.interview_id = i.interview_id
                ORDER BY r.created_at DESC
            ''')
            return [dict(r) for r in c.fetchall()]


# Global store instance
interview_store = InterviewStore()
