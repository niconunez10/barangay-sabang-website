"""Local SQLite storage for the website's from-scratch assistant."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


SAMPLE_RECORDS = (
    {
        "record_type": "event",
        "title": "Sample: Libreng Anti-Rabies Vaccination",
        "category": "Health",
        "details": "Demo sample only. Replace with an approved barangay announcement before publishing.",
    },
    {
        "record_type": "announcement",
        "title": "Sample: Senior Citizen Pension Payout",
        "category": "Services",
        "details": "Demo sample only. Add the official payout date, venue, and requirements before publishing.",
    },
    {
        "record_type": "event",
        "title": "Sample: Barangay Assembly",
        "category": "Community",
        "details": "Demo sample only. Replace with the assembly details approved by barangay officials.",
    },
    {
        "record_type": "event",
        "title": "Sample: Community Medical Mission",
        "category": "Health",
        "details": "Demo sample only. Add the confirmed schedule, location, and requirements before publishing.",
    },
)


class LocalDatabase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self):
        with closing(self.connect()) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS content_records (
                    record_type TEXT NOT NULL CHECK(
                        record_type IN ('announcement', 'event', 'guide')
                    ),
                    record_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    date_posted TEXT NOT NULL DEFAULT '',
                    event_date TEXT NOT NULL DEFAULT '',
                    event_time TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    requirements TEXT NOT NULL DEFAULT '',
                    details TEXT NOT NULL DEFAULT '',
                    keywords TEXT NOT NULL DEFAULT '[]',
                    media TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'Draft',
                    is_sample INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (record_type, record_id)
                );
                CREATE INDEX IF NOT EXISTS idx_content_status_type
                    ON content_records(status, record_type, is_sample);
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    requirements TEXT NOT NULL DEFAULT '',
                    details TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS chat_context (
                    session_id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            connection.commit()
        self._seed_samples_if_empty()

    def _seed_samples_if_empty(self):
        with closing(self.connect()) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM content_records WHERE is_sample = 1"
            ).fetchone()[0]
            if count:
                return
            with connection:
                connection.executemany(
                    """INSERT INTO content_records
                       (record_type, record_id, title, category, details, status, is_sample)
                       VALUES (?, ?, ?, ?, ?, 'Draft', 1)""",
                    [
                        (
                            record["record_type"], -index, record["title"],
                            record["category"], record["details"],
                        )
                        for index, record in enumerate(SAMPLE_RECORDS, start=1)
                    ],
                )

    def sync_portal_records(self, announcements, events, services, guides):
        """Replace the live local index from the portal's saved admin records."""
        content_rows = []
        for item in announcements:
            content_rows.append((
                "announcement", item["id"], item.get("title", ""),
                item.get("category", ""), item.get("date", ""),
                "", "", item.get("location", ""), item.get("requirements", ""),
                item.get("description", ""), json.dumps(item.get("keywords", [])),
                json.dumps(item.get("media", [])), item.get("status", "Published"),
            ))
        for item in events:
            content_rows.append((
                "event", item["id"], item.get("title", ""),
                item.get("category", "Events"), item.get("date_posted", ""),
                item.get("_sort", item.get("date", "")), item.get("time", ""),
                item.get("location", ""), item.get("requirements", ""),
                item.get("description", ""), json.dumps(item.get("keywords", [])),
                json.dumps(item.get("media", [])), item.get("status", "Published"),
            ))
        for item in guides:
            content_rows.append((
                "guide", item["id"], item.get("topic", ""), "Guide AI",
                item.get("date", ""), "", "", "", "",
                item.get("answer", ""), json.dumps(item.get("keywords", [])),
                json.dumps(item.get("media", [])), item.get("status", "Published"),
            ))

        with closing(self.connect()) as connection:
            with connection:
                connection.execute(
                    """UPDATE content_records SET record_id = -ABS(record_id)
                       WHERE is_sample = 1 AND record_id > 0"""
                )
                connection.execute("DELETE FROM content_records WHERE is_sample = 0")
                connection.executemany(
                    """INSERT INTO content_records
                       (record_type, record_id, title, category, date_posted, event_date,
                        event_time, location, requirements, details, keywords, media, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    content_rows,
                )
                connection.execute("DELETE FROM services")
                connection.executemany(
                    """INSERT INTO services
                       (id, name, category, description, requirements, details, active)
                       VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    [
                        (
                            index, item.get("name", ""), item.get("tag", ""),
                            item.get("description", ""), item.get("requirements", ""),
                            item.get("details", ""),
                        )
                        for index, item in enumerate(services, start=1)
                    ],
                )

    @staticmethod
    def _content_record(row):
        record = dict(row)
        for field in ("keywords", "media"):
            try:
                value = json.loads(record.get(field) or "[]")
            except (TypeError, ValueError):
                value = []
            record[field] = value if isinstance(value, list) else []
        return record

    def list_active_records(self, record_type=None):
        with closing(self.connect()) as connection:
            if record_type == "service":
                rows = connection.execute(
                    "SELECT * FROM services WHERE active = 1 ORDER BY id"
                ).fetchall()
                return [
                    {
                        "record_type": "service",
                        "record_id": row["id"],
                        "title": row["name"],
                        "category": row["category"],
                        "details": row["details"] or row["description"],
                        "requirements": row["requirements"],
                        "status": "Published",
                        "keywords": [],
                        "media": [],
                    }
                    for row in rows
                ]

            sql = """SELECT * FROM content_records
                     WHERE status = 'Published' AND is_sample = 0"""
            values = []
            if record_type:
                sql += " AND record_type = ?"
                values.append(record_type)
            sql += " ORDER BY record_id DESC"
            content_rows = connection.execute(sql, values).fetchall()
            service_rows = connection.execute(
                "SELECT * FROM services WHERE active = 1 ORDER BY id"
            ).fetchall() if record_type is None else []
            records = [self._content_record(row) for row in content_rows]
            records.extend(
                {
                    "record_type": "service",
                    "record_id": row["id"],
                    "title": row["name"],
                    "category": row["category"],
                    "details": row["details"] or row["description"],
                    "requirements": row["requirements"],
                    "status": "Published",
                    "keywords": [],
                    "media": [],
                }
                for row in service_rows
            )
            return records

    def list_recent_announcements(self, limit=5):
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM content_records
                   WHERE record_type = 'announcement' AND status = 'Published'
                     AND is_sample = 0
                   ORDER BY record_id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [self._content_record(row) for row in rows]

    def list_upcoming_events(self, today_iso, limit=10):
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM content_records
                   WHERE record_type = 'event' AND status = 'Published'
                     AND is_sample = 0 AND event_date >= ?
                   ORDER BY event_date, event_time, record_id LIMIT ?""",
                (today_iso, limit),
            ).fetchall()
            return [self._content_record(row) for row in rows]

    def get_active_record(self, record_type, record_id):
        if record_type == "service":
            records = self.list_active_records("service")
            return next((record for record in records
                         if record["record_id"] == record_id), None)
        with closing(self.connect()) as connection:
            row = connection.execute(
                """SELECT * FROM content_records
                   WHERE record_type = ? AND record_id = ? AND status = 'Published'
                     AND is_sample = 0""",
                (record_type, record_id),
            ).fetchone()
            return self._content_record(row) if row else None

    def set_chat_record(self, session_id, record_type, record_id):
        with closing(self.connect()) as connection:
            with connection:
                cutoff = (
                    datetime.now(timezone.utc) - timedelta(hours=2)
                ).isoformat(timespec="seconds")
                connection.execute(
                    "DELETE FROM chat_context WHERE updated_at < ?", (cutoff,)
                )
                connection.execute(
                    """INSERT INTO chat_context (session_id, record_type, record_id, updated_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(session_id) DO UPDATE SET
                         record_type = excluded.record_type,
                         record_id = excluded.record_id,
                         updated_at = excluded.updated_at""",
                    (
                        session_id, record_type, record_id,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    ),
                )

    def get_chat_record(self, session_id):
        with closing(self.connect()) as connection:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(hours=2)
            ).isoformat(timespec="seconds")
            with connection:
                connection.execute(
                    "DELETE FROM chat_context WHERE updated_at < ?", (cutoff,)
                )
                row = connection.execute(
                    "SELECT record_type, record_id FROM chat_context WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
        if not row:
            return None
        return self.get_active_record(row["record_type"], row["record_id"])
