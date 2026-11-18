import json
import os
import re
import secrets
<<<<<<< HEAD
import sqlite3
import threading
import time
import urllib.error
=======
import threading
import time
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
import urllib.request
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

<<<<<<< HEAD
from dotenv import load_dotenv
from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from ai_engine import LocalAIEngine
from chatbot import LocalChatbot
from database import LocalDatabase
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

=======
from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
app = Flask(__name__)

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)
# Largest single request (one post with several photos/videos). Flask rejects
# anything bigger with HTTP 413 before it reaches our code.
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin"))

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300
failed_logins = {}  # ip -> {"count": int, "locked_until": float}

# Optional: a Discord/Slack-style webhook URL that pings the developers the
# moment a resident reports a problem. Leave unset to skip it.
DEV_WEBHOOK_URL = os.environ.get("DEV_WEBHOOK_URL", "")

# ---------------------------------------------------------------------------
# FILE UPLOAD SETTINGS
# ---------------------------------------------------------------------------
<<<<<<< HEAD
DATA_DIR = BASE_DIR / "instance"          # already listed in .gitignore
UPLOAD_DIR = DATA_DIR / "uploads"
DATA_FILE = DATA_DIR / "data.json"
AI_DB_FILE = DATA_DIR / "barangay_ai.sqlite3"
LOCAL_DB_FILE = DATA_DIR / "barangay.db"
=======
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "instance"          # already listed in .gitignore
UPLOAD_DIR = DATA_DIR / "uploads"
DATA_FILE = DATA_DIR / "data.json"
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp"}
VIDEO_EXT = {"mp4", "webm", "mov", "m4v"}
FILE_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"}
KIND_BY_EXT = {**{e: "image" for e in IMAGE_EXT},
               **{e: "video" for e in VIDEO_EXT},
               **{e: "file" for e in FILE_EXT}}
SIZE_LIMIT = {"image": 10 * 1024 * 1024,
              "video": 100 * 1024 * 1024,
              "file": 20 * 1024 * 1024}
MAX_FILES_PER_REQUEST = 12
MAX_MEDIA_PER_ITEM = 30


def today_label():
    now = datetime.now()
    return f"{now.strftime('%B')} {now.day}, {now.year}"


# ---------------------------------------------------------------------------
# DATA (kept in memory AND saved to instance/data.json so it survives restarts)
# ---------------------------------------------------------------------------
announcements = [
    {"id": 1, "category": "Community", "date": "October 20, 2026",
     "title": "Welcome to the Barangay Sabang Information Portal",
     "description": "Find community announcements, upcoming activities, and selected resident services in one place.",
     "status": "Published", "media": []},
    {"id": 2, "category": "Services", "date": "October 18, 2026",
     "title": "Check service details before visiting",
     "description": "Residents are encouraged to check the posted instructions and schedules for available barangay services.",
     "status": "Published", "media": []},
    {"id": 3, "category": "Youth", "date": "October 15, 2026",
     "title": "Stay updated on SK activities",
     "description": "Visit the events section for sample upcoming and past community activities.",
     "status": "Published", "media": []},
]

events = [
    {"id": 1, "day": "25", "month": "OCT", "title": "Community Clean-Up Drive",
     "date": "October 25, 2026", "time": "8:00 AM", "location": "Barangay Sabang",
     "description": "A sample community activity. Confirm the actual schedule with barangay personnel.",
     "_sort": "2026-10-25", "status": "Published", "media": []},
    {"id": 2, "day": "29", "month": "OCT", "title": "Youth Community Meeting",
     "date": "October 29, 2026", "time": "2:00 PM", "location": "To be confirmed",
     "description": "A sample SK-related event. Confirm venue and schedule before publishing.",
     "_sort": "2026-10-29", "status": "Published", "media": []},
]

services = [
    {"icon": "▤", "name": "Free Printing Service", "tag": "Resident Service",
     "description": "Check the approved instructions, schedule, and applicable rules before visiting.",
     "details": "Please confirm the current operating schedule, printing limits, requirements, and availability with authorized barangay personnel."},
    {"icon": "▣", "name": "E-Library", "tag": "Learning Facility",
     "description": "Find information about access to the e-library and available learning resources.",
     "details": "Please confirm opening hours, access rules, and available resources with authorized barangay personnel."},
    {"icon": "⌘", "name": "Computer Facilities", "tag": "Community Facility",
     "description": "Learn how residents may access the available computer facilities.",
     "details": "Please confirm availability, operating hours, usage guidelines, and any requirements with authorized barangay personnel."},
]

guides = []        # things the admin has taught the AI (see /api/admin/guides)
suggestions = []
reports = []       # problem reports sent by residents
ids = {"announcements": 4, "events": 3, "guides": 1, "suggestions": 1, "reports": 1}

CATEGORIES = ["Community", "Services", "Youth"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# Collections that can hold photos/videos/files and be archived.
COLLECTIONS = {"announcements": announcements, "events": events, "guides": guides}

data_lock = threading.RLock()
<<<<<<< HEAD
LOCAL_DATABASE = LocalDatabase(LOCAL_DB_FILE)
LOCAL_AI_ENGINE = LocalAIEngine(BASE_DIR)
LOCAL_CHATBOT = LocalChatbot(LOCAL_DATABASE, LOCAL_AI_ENGINE)

def sync_ai_context_db():
    """Keep the local AI context database aligned with the portal's saved records."""
    connection = sqlite3.connect(AI_DB_FILE, timeout=5)
    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS guide_ai_entries (
                id INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                keywords TEXT NOT NULL,
                answer TEXT NOT NULL,
                media TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS barangay_services (
                id INTEGER PRIMARY KEY,
                icon TEXT NOT NULL,
                name TEXT NOT NULL,
                tag TEXT NOT NULL,
                description TEXT NOT NULL,
                details TEXT NOT NULL,
                active INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                verification_status TEXT DEFAULT 'pending',
                verified_reference TEXT,
                auto_keywords TEXT,
                source_urls TEXT,
                last_checked_at TEXT,
                media TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                sort_key TEXT NOT NULL,
                status TEXT NOT NULL,
                verification_status TEXT DEFAULT 'pending',
                verified_reference TEXT,
                auto_keywords TEXT,
                source_urls TEXT,
                last_checked_at TEXT,
                media TEXT NOT NULL DEFAULT '[]'
            );
        """)
        for table in ("announcements", "events"):
            columns = {
                row[1] for row in connection.execute(f"PRAGMA table_info({table})")
            }
            migrations = {
                "verification_status": "TEXT DEFAULT 'pending'",
                "verified_reference": "TEXT",
                "auto_keywords": "TEXT",
                "source_urls": "TEXT",
                "last_checked_at": "TEXT",
                "media": "TEXT NOT NULL DEFAULT '[]'",
            }
            for name, definition in migrations.items():
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                    )
        service_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(barangay_services)")
        }
        with connection:
            if "icon" not in service_columns:
                connection.execute(
                    "ALTER TABLE barangay_services ADD COLUMN icon TEXT NOT NULL DEFAULT ''"
                )
            if "tag" not in service_columns:
                connection.execute(
                    "ALTER TABLE barangay_services ADD COLUMN tag TEXT NOT NULL DEFAULT ''"
                )
        with data_lock, connection:
            for table in ("guide_ai_entries", "barangay_services", "announcements", "events"):
                connection.execute(f"DELETE FROM {table}")
            connection.executemany(
                """INSERT INTO guide_ai_entries (id, topic, keywords, answer, media, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item["id"], item["topic"], json.dumps(item.get("keywords", [])),
                        item["answer"], json.dumps(item.get("media", [])), item.get("status", "Published"),
                    )
                    for item in guides
                ],
            )
            connection.executemany(
                """INSERT INTO barangay_services
                   (id, icon, name, tag, description, details, active)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                [
                    (
                        index, item["icon"], item["name"], item["tag"],
                        item["description"], item["details"],
                    )
                    for index, item in enumerate(services, start=1)
                ],
            )
            connection.executemany(
                """INSERT INTO announcements
                   (id, category, date, title, description, status, verification_status,
                    verified_reference, auto_keywords, source_urls, last_checked_at, media)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item["id"], item["category"], item["date"], item["title"],
                        item["description"], item.get("status", "Published"),
                        item.get("verification_status", "pending"),
                        item.get("verified_reference", ""),
                        json.dumps(item.get("auto_keywords", []), ensure_ascii=False),
                        json.dumps(item.get("source_urls", []), ensure_ascii=False),
                        item.get("last_checked_at", ""),
                        json.dumps(item.get("media", []), ensure_ascii=False),
                    )
                    for item in announcements
                ],
            )
            connection.executemany(
                """INSERT INTO events
                   (id, date, time, title, location, description, sort_key, status,
                    verification_status, verified_reference, auto_keywords, source_urls,
                    last_checked_at, media)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item["id"], item["date"], item["time"], item["title"],
                        item["location"], item["description"], item.get("_sort", ""),
                        item.get("status", "Published"),
                        item.get("verification_status", "pending"),
                        item.get("verified_reference", ""),
                        json.dumps(item.get("auto_keywords", []), ensure_ascii=False),
                        json.dumps(item.get("source_urls", []), ensure_ascii=False),
                        item.get("last_checked_at", ""),
                        json.dumps(item.get("media", []), ensure_ascii=False),
                    )
                    for item in events
                ],
            )
    finally:
        connection.close()

    LOCAL_DATABASE.sync_portal_records(announcements, events, services, guides)
    LOCAL_AI_ENGINE.rebuild_index(LOCAL_DATABASE.list_active_records())


def load_ai_context():
    """Read only active portal records for the website assistant."""
    connection = sqlite3.connect(AI_DB_FILE, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        guide_rows = connection.execute(
            """SELECT id, topic, keywords, answer, media FROM guide_ai_entries
               WHERE status = 'Published' ORDER BY id DESC"""
        ).fetchall()
        services_rows = connection.execute(
            """SELECT icon, name, tag, description, details FROM barangay_services
               WHERE active = 1 ORDER BY id"""
        ).fetchall()
        announcement_rows = connection.execute(
            """SELECT id, category, date, title, description, verification_status,
                      verified_reference, auto_keywords, source_urls, last_checked_at
               FROM announcements
               WHERE status = 'Published' ORDER BY id DESC"""
        ).fetchall()
        event_rows = connection.execute(
            """SELECT id, date, time, title, location, description, sort_key,
                      verification_status, verified_reference, auto_keywords,
                      source_urls, last_checked_at
               FROM events
               WHERE status = 'Published' ORDER BY sort_key, id"""
        ).fetchall()

        def decode_json_array(row, field):
            try:
                value = json.loads(row[field] or "[]")
            except (TypeError, ValueError):
                return []
            return value if isinstance(value, list) else []

        def content_row(row):
            item = dict(row)
            item["auto_keywords"] = decode_json_array(row, "auto_keywords")
            item["source_urls"] = decode_json_array(row, "source_urls")
            return item

        return {
            "guide_ai_entries": [
                {
                    **dict(row),
                    "keywords": json.loads(row["keywords"]),
                    "media": json.loads(row["media"]),
                }
                for row in guide_rows
            ],
            "services_list": [dict(row) for row in services_rows],
            "announcements": [content_row(row) for row in announcement_rows],
            "events": [content_row(row) for row in event_rows],
        }
    finally:
        connection.close()
=======
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd


def save_data():
    """Writes everything to disk safely (temp file first, then swap)."""
    with data_lock:
        payload = {"announcements": announcements, "events": events, "guides": guides,
                   "suggestions": suggestions, "reports": reports, "ids": ids}
        tmp = DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, DATA_FILE)
<<<<<<< HEAD
        sync_ai_context_db()


def _local_only_metadata(item):
    text = " ".join(
        str(item.get(field, ""))
        for field in ("title", "description", "date", "time", "location", "requirements")
    )
    item.update({
        "verification_status": "local_only",
        "auto_keywords": list(dict.fromkeys(LOCAL_AI_ENGINE.preprocessor.tokens(text)))[:20],
        "verified_reference": (
            "Indexed from the admin's local post only. This is not an independent "
            "fact-check; confirm changing details with barangay personnel."
        ),
        "source_urls": [],
        "last_checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    })
=======
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd


def load_data():
    if not DATA_FILE.exists():
<<<<<<< HEAD
        for collection in (announcements, events):
            for item in collection:
                if item.get("status", "Published") == "Published":
                    _local_only_metadata(item)
=======
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
        save_data()
        return
    try:
        saved = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        app.logger.warning("data.json could not be read; starting with sample data.")
        return
    with data_lock:
        for name, target in (("announcements", announcements), ("events", events),
                             ("guides", guides), ("suggestions", suggestions),
                             ("reports", reports)):
            if name in saved:
                target[:] = saved[name]
        ids.update(saved.get("ids", {}))
<<<<<<< HEAD
        for collection in (announcements, events):
            for item in collection:
                if item.get("status") == "Published":
                    _local_only_metadata(item)


load_data()
sync_ai_context_db()
=======


load_data()
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd


def new_id(kind):
    with data_lock:
        value = ids[kind]
        ids[kind] += 1
        return value


<<<<<<< HEAD
EVENT_CONTENT_TABLES = {"announcements", "events"}
_EVENT_CHECKS_IN_FLIGHT = set()
_EVENT_CHECKS_LOCK = threading.Lock()
def _run_event_background_check_in_context(event_id, kind):
    """Update a local-only index note; the post is not externally verified."""
    if kind not in EVENT_CONTENT_TABLES:
        app.logger.error("Local AI index rejected unsupported content type: %s", kind)
        return
    with app.app_context(), data_lock:
        item = find_item(kind, event_id)
        if not item or item.get("status") != "Published":
            return
        _local_only_metadata(item)
        save_data()


def run_event_background_check(event_id, kind="events"):
    check_key = (kind, event_id)
    try:
        with app.app_context():
            _run_event_background_check_in_context(event_id, kind)
    except (sqlite3.Error, OSError, TypeError, ValueError) as exc:
        app.logger.error(
            "Local AI index refresh failed for %s/%s (%s).",
            kind, event_id, type(exc).__name__,
        )
    finally:
        with _EVENT_CHECKS_LOCK:
            _EVENT_CHECKS_IN_FLIGHT.discard(check_key)


def start_event_background_check(event_id, kind):
    """Mark a post as pending and start its checker without blocking the request."""
    if kind not in EVENT_CONTENT_TABLES:
        raise ValueError("Only announcements and events can be checked.")
    check_key = (kind, event_id)
    with _EVENT_CHECKS_LOCK:
        if check_key in _EVENT_CHECKS_IN_FLIGHT:
            return True
        _EVENT_CHECKS_IN_FLIGHT.add(check_key)
    with data_lock:
        item = find_item(kind, event_id)
        if not item or item.get("status") != "Published":
            with _EVENT_CHECKS_LOCK:
                _EVENT_CHECKS_IN_FLIGHT.discard(check_key)
            return False
        item.update({
            "verification_status": "pending",
            "verified_reference": "",
            "auto_keywords": [],
            "source_urls": [],
            "last_checked_at": "",
        })
        save_data()
    try:
        threading.Thread(
            target=run_event_background_check,
            args=(event_id, kind),
            daemon=True,
        ).start()
    except RuntimeError as exc:
        app.logger.error("Could not start AI reference check for %s/%s (%s).",
                         kind, event_id, type(exc).__name__)
        with data_lock:
            item = find_item(kind, event_id)
            if item:
                item.update({
                    "verification_status": "local_only",
                    "verified_reference": (
                        "The post is included in the synchronous local AI index, but its "
                        "status refresh could not start."
                    ),
                })
                save_data()
        with _EVENT_CHECKS_LOCK:
            _EVENT_CHECKS_IN_FLIGHT.discard(check_key)
    return True


def start_pending_event_checks(kind):
    if kind not in EVENT_CONTENT_TABLES:
        return
    with data_lock:
        pending_ids = [
            item["id"] for item in COLLECTIONS[kind]
            if item.get("status") == "Published"
            and item.get("verification_status", "pending") == "pending"
        ]
    for item_id in pending_ids:
        start_event_background_check(item_id, kind)


=======
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
# ---------------------------------------------------------------------------
# UPLOAD HELPERS
# ---------------------------------------------------------------------------
def looks_valid(ext, head):
    """Checks the first bytes so a renamed .exe cannot pose as a .jpg."""
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "png":
        return head.startswith(b"\x89PNG")
    if ext == "gif":
        return head.startswith(b"GIF8")
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == "pdf":
        return head.startswith(b"%PDF")
    return True


def save_uploads(file_list):
    """Saves uploaded files. Returns (list_of_media_dicts, error_message)."""
    file_list = [f for f in file_list if f and f.filename]
    if len(file_list) > MAX_FILES_PER_REQUEST:
        return [], f"Please upload at most {MAX_FILES_PER_REQUEST} files at a time."
    saved = []

    def fail(message):
        for m in saved:
            (UPLOAD_DIR / m["stored"]).unlink(missing_ok=True)
        return [], message

    for f in file_list:
        original = secure_filename(f.filename) or "file"
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        kind = KIND_BY_EXT.get(ext)
        if not kind:
            return fail(f"'{original}' is not an allowed file type.")
        head = f.stream.read(16)
        f.stream.seek(0)
        if not looks_valid(ext, head):
            return fail(f"'{original}' does not look like a real .{ext} file.")
        stored = f"{secrets.token_hex(12)}.{ext}"
        path = UPLOAD_DIR / stored
        f.save(path)
        size = path.stat().st_size
        saved.append({"id": secrets.token_hex(6), "name": original, "stored": stored,
                      "url": f"/media/{stored}", "kind": kind, "size": size})
        if size > SIZE_LIMIT[kind]:
            limit_mb = SIZE_LIMIT[kind] // (1024 * 1024)
            return fail(f"'{original}' is too large. The limit for this type is {limit_mb} MB.")
    return saved, None


def delete_media_files(media_list):
    for m in media_list:
        (UPLOAD_DIR / m["stored"]).unlink(missing_ok=True)


def find_item(kind, item_id):
    for item in COLLECTIONS.get(kind, []):
        if item["id"] == item_id:
            return item
    return None


<<<<<<< HEAD
def public_item(item, for_admin=False):
    """Copy of an item that is safe to send to residents."""
    internal_fields = {
        "verification_status", "verified_reference", "auto_keywords",
        "source_urls", "last_checked_at",
    }
    clean = {
        k: v for k, v in item.items()
        if not k.startswith("_") and (for_admin or k not in internal_fields)
    }
    clean["media"] = [{k: m[k] for k in ("id", "name", "url", "kind", "size")}
                      for m in item.get("media", [])]
    if for_admin:
        clean.setdefault("verification_status", "pending")
        clean.setdefault("verified_reference", "")
        clean.setdefault("auto_keywords", [])
        clean.setdefault("source_urls", [])
        clean.setdefault("last_checked_at", "")
        clean["date_input"] = item.get("_sort", "")
=======
def public_item(item):
    """Copy of an item that is safe to send to residents."""
    clean = {k: v for k, v in item.items() if not k.startswith("_")}
    clean["media"] = [{k: m[k] for k in ("id", "name", "url", "kind", "size")}
                      for m in item.get("media", [])]
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
    return clean


# ---------------------------------------------------------------------------
# SIMPLE RATE LIMIT (stops spam on public forms)
# ---------------------------------------------------------------------------
rate_hits = {}  # (bucket, ip) -> [timestamps]


def rate_limited(bucket, limit, window_seconds):
    now = time.time()
    key = (bucket, request.remote_addr or "unknown")
    hits = [t for t in rate_hits.get(key, []) if now - t < window_seconds]
    if len(hits) >= limit:
        rate_hits[key] = hits
        return True
    hits.append(now)
    rate_hits[key] = hits
    return False



# ---------------------------------------------------------------------------
# LOGIN HELPERS
# ---------------------------------------------------------------------------
def admin_required(view):
    """Protects a route. Pages redirect to the login form; API calls get 401."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("is_admin"):
            return view(*args, **kwargs)
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "message": "Please log in as admin first."}), 401
        return redirect(url_for("login", next=request.path))
    return wrapped


def get_csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.before_request
def check_csrf_on_admin_writes():
    """Blocks forged requests from other websites on admin actions."""
    if (request.path.startswith("/api/admin/")
            and request.method in ("POST", "PUT", "PATCH", "DELETE")):
        sent = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf", "")
        if not expected or not secrets.compare_digest(sent, expected):
            return jsonify({"ok": False, "message": "Session expired. Please refresh and log in again."}), 400


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"  # SAMEORIGIN lets our own PDF viewer work
    response.headers["Referrer-Policy"] = "same-origin"
    if request.path.startswith("/admin") or request.path.startswith("/api/admin"):
        response.headers["Cache-Control"] = "no-store"
    return response



# ---------------------------------------------------------------------------
# PUBLIC PAGES + API
# ---------------------------------------------------------------------------
@app.errorhandler(413)
def too_big(_error):
    return jsonify({"ok": False, "message": "The upload is too large. Please send fewer or smaller files."}), 413


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/media/<name>")
def media_file(name):
    """Serves an uploaded file. Range requests are supported (iPhones need
    this to play videos)."""
    if not re.fullmatch(r"[0-9a-f]{24}\.[a-z0-9]{2,4}", name):
        abort(404)
    ext = name.rsplit(".", 1)[1]
    if ext not in KIND_BY_EXT:
        abort(404)
    download_name = None
    if KIND_BY_EXT[ext] == "file" and ext != "pdf":
        for coll in COLLECTIONS.values():
            for item in coll:
                for m in item.get("media", []):
                    if m["stored"] == name:
                        download_name = m["name"]
    return send_from_directory(UPLOAD_DIR, name, conditional=True,
                               as_attachment=bool(download_name),
                               download_name=download_name)


@app.get("/api/announcements")
def get_announcements():
    query = request.args.get("q", "").strip().lower()
    category = request.args.get("category", "All")
    result = [
        public_item(item) for item in announcements
        if item["status"] == "Published"
        and (not query or query in item["title"].lower()
             or query in item["description"].lower()
             or query in item["category"].lower())
        and (category == "All" or item["category"] == category)
    ]
    return jsonify(result)


@app.get("/api/events")
def get_events():
    return jsonify([public_item(e) for e in events if e.get("status") == "Published"])


@app.get("/api/services")
def get_services():
    return jsonify(services)


@app.post("/api/suggestions")
def submit_suggestion():
    if rate_limited("suggestion", 5, 600):
        return jsonify({"ok": False, "message": "You have sent several suggestions recently. Kindly try again in a few minutes."}), 429
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    subject = str(data.get("subject", "")).strip()
    message = str(data.get("message", "")).strip()

    if not subject or not message:
        return jsonify({"ok": False, "message": "Please complete the subject and message fields."}), 400
    if len(subject) > 100 or len(message) > 1500 or len(name) > 100:
        return jsonify({"ok": False, "message": "One of your fields is too long. Please shorten it and try again."}), 400

    # The suggestion goes ONLY to the Suggestions tab of the admin page.
    # (No email is sent anywhere.)
    suggestions.insert(0, {
        "id": new_id("suggestions"),
        "name": name or "Anonymous",
        "subject": subject,
        "message": message,
        "date": today_label(),
        "status": "New",
    })
    save_data()
    return jsonify({"ok": True, "message": "Thank you. Your suggestion has been received and forwarded to the barangay administrators."})


# ---- Report a problem -------------------------------------------------------
PROBLEM_TYPES = ["Something is not working", "A page looks wrong", "Photo, video, or file problem",
                 "The chat assistant", "Other"]


def notify_devs(report):
    """Prints to the server console and (optionally) pings a webhook.
    Runs in a background thread so a slow webhook never blocks the resident."""
    text = (f"New problem report #{report['id']} [{report['type']}]: "
            f"{report['details'][:300]} (page: {report['page_url']})")
    app.logger.warning(text)
    if not DEV_WEBHOOK_URL:
        return

    def send():
        try:
            body = json.dumps({"content": text, "text": text}).encode("utf-8")
            req = urllib.request.Request(DEV_WEBHOOK_URL, data=body,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=8).read()
        except Exception as exc:  # never let a notification failure break the site
            app.logger.warning("Webhook failed: %s", exc)
    threading.Thread(target=send, daemon=True).start()


@app.post("/api/problem-reports")
def submit_problem_report():
    if rate_limited("report", 6, 600):
        return jsonify({"ok": False, "message": "Several reports were received from your device recently. Kindly wait a few minutes before sending another."}), 429
    data = request.get_json(silent=True) or {}
    details = str(data.get("details", "")).strip()
    if len(details) < 5:
        return jsonify({"ok": False, "message": "Please describe the problem in a few words."}), 400

    problem_type = str(data.get("type", "Other"))
    errors = data.get("js_errors", [])
    if not isinstance(errors, list):
        errors = []
    report = {
        "id": new_id("reports"),
        "date": today_label(),
        "time": datetime.now().strftime("%I:%M %p").lstrip("0"),
        "type": problem_type if problem_type in PROBLEM_TYPES else "Other",
        "details": details[:2000],
        "contact": str(data.get("contact", "")).strip()[:150],
        "page_url": str(data.get("page_url", ""))[:300],
        "user_agent": str(data.get("user_agent", ""))[:300],
        "viewport": str(data.get("viewport", ""))[:40],
        "js_errors": [str(e)[:300] for e in errors[:5]],
        "status": "New",
    }
    reports.insert(0, report)
    save_data()
    notify_devs(report)
    return jsonify({"ok": True, "id": report["id"],
                    "message": f"Thank you. Your report (No. {report['id']}) has been sent to the developers."})


# ---- AI assistant -----------------------------------------------------------
def has_word(text, words):
    """Whole-word match, so 'hi' does not trigger on 'this' or 'which'."""
<<<<<<< HEAD
    text = text.lower()
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def find_guide(question, entries=None):
    """Returns the admin-taught guide that best matches the question, or None."""
    best, best_score = None, 0
    for g in guides if entries is None else entries:
        if g.get("status", "Published") != "Published":
=======
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def find_guide(question):
    """Returns the admin-taught guide that best matches the question, or None."""
    best, best_score = None, 0
    for g in guides:
        if g.get("status") != "Published":
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
            continue
        terms = [k for k in g.get("keywords", []) if k] + [g["topic"].lower()]
        # Keywords of 4+ letters also match longer forms ("print" finds "printer",
        # "printing"). Short ones must match the whole word ("id" must not match "idea").
<<<<<<< HEAD
        score = sum(
            1 for term in terms
            if re.search(
                r"\b" + re.escape(term) + (r"\w*" if len(term) >= 4 else r"\b"),
                question,
            )
        )
=======
        score = sum(1 for t in terms
                    if re.search(rf"\b{re.escape(t)}{r'\w*' if len(t) >= 4 else r'\b'}", question))
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
        if score > best_score:
            best, best_score = g, score
    return best


<<<<<<< HEAD
def _matching_guides(question, entries):
    return _rank_records(question, entries, ("topic", "keywords"))[:5]


def _relevant_announcements_and_events(question, context):
    general_terms = {
        "announcement", "announcements", "event", "events", "activity", "activities",
        "schedule", "upcoming", "latest", "news", "update", "updates",
    }
    terms = _search_terms(question)
    if terms and terms <= general_terms:
        return context["announcements"][:5], context["events"][:5]

    fields = (
        "title", "description", "category", "date", "time", "location",
        "auto_keywords", "verified_reference", "source_urls",
    )
    return (
        _rank_records(question, context["announcements"], fields)[:5],
        _rank_records(question, context["events"], fields)[:5],
    )


BARANGAY_SYSTEM_PROMPT = """You are the Official AI Assistant for Barangay Sabang. Your job is to assist residents politely, respectfully, and clearly using the admin's official guide below as your factual reference.

<matched_guide>
Topic: {topic}
Admin Reference Notes: {admin_notes}
Has Attached Video/Photos: {has_media}
</matched_guide>

<other_barangay_context>
{other_active_guides_and_events}
</other_barangay_context>

<matched_guides_and_ai_event_references>
{matched_guides_and_verified_posts}
</matched_guides_and_ai_event_references>

Current Date: {current_date}

Instructions for Crafting Your Response:
1. USE THE GUIDE AS REFERENCE, NOT A SCRIPT: Do not simply copy-paste the Admin Reference Notes word-for-word. Rewrite and organize the information into a complete, helpful, and easy-to-understand explanation that directly answers the resident's question.
2. RESPECTFUL & WELCOMING TONE: Match the resident's language (Tagalog, Taglish, or English). Always maintain a courteous, formal, and public-service tone—use "po" and "opo" naturally when replying in Tagalog or Taglish.
3. DELIVER THE ESSENTIAL ANSWER CLEARLY: State the exact action the resident needs to take. Do not add a location, contact, or procedure unless it is stated in the official records.
4. ZERO HALLUCINATION: Stick strictly to the facts provided in <matched_guide>, <other_barangay_context>, and <matched_guides_and_ai_event_references>. Do not invent specific fees, document requirements, or schedules that are not mentioned in official records.
5. ATTACHED MEDIA REMINDER: If "Has Attached Video/Photos" is True, add a short, polite note at the end letting the resident know they can view the guide photos or click the video demo button below for a visual walkthrough.
6. MISSING INFORMATION: If the answer is not in the provided barangay records, say: "Paumanhin po, wala pa akong opisyal na detalye tungkol dito. Maaari po kayong magtanong nang direkta sa Barangay Sabang Hall o makipag-ugnayan sa Barangay Secretary."
7. EMERGENCIES: If a resident reports an active fire, medical emergency, crime, or urgent rescue need, immediately tell them to call 911 or contact the Barangay Sabang Tanod outpost right away instead of giving standard office procedures.
8. EVENT VERIFICATION: Do not describe a local_only or needs_review post as externally verified. When an official source URL is supplied, cite it for changing event/announcement information; do not make up citations.
"""


_FALLBACK_STOP_WORDS = {
    "a", "about", "an", "and", "are", "can", "do", "does", "for", "how", "i",
    "in", "is", "it", "me", "of", "on", "or", "please", "po", "tell", "the",
    "to", "up", "what", "when", "where", "which", "who", "with", "would", "you",
    "ako", "ang", "ba", "mga", "ng", "opo", "paki", "pa", "saan", "ano",
    "paano", "may", "sa", "naman", "pwede", "puwede", "ko", "ito", "yung",
    "coming", "next", "offer", "offers", "show",
}


def _search_terms(text):
    terms = set(re.findall(r"\w+", text.lower(), flags=re.UNICODE))
    return {term[:-1] if len(term) > 4 and term.endswith("s") else term
            for term in terms if len(term) > 1 and term not in _FALLBACK_STOP_WORDS}


def _record_match_score(question, fields):
    question_terms = _search_terms(question)
    record_text = " ".join(str(value) for value in fields if value)
    record_terms = _search_terms(record_text)
    score = len(question_terms & record_terms)
    normalized_question = " ".join(re.findall(r"\w+", question.lower(), flags=re.UNICODE))
    for value in fields:
        phrase = " ".join(re.findall(r"\w+", str(value).lower(), flags=re.UNICODE))
        if len(phrase) > 2 and phrase in normalized_question:
            score += 2
    return score


def _rank_records(question, records, fields):
    ranked = [
        (_record_match_score(question, [record.get(field, "") for field in fields]), record)
        for record in records
    ]
    return [record for score, record in sorted(ranked, key=lambda pair: pair[0], reverse=True) if score > 0]


def _missing_information(question):
    tagalog_markers = (" po", "opo", "paano", "saan", "ano", "kailangan", "ba ")
    if any(marker in f" {question.lower()}" for marker in tagalog_markers):
        return (
            "Paumanhin po, wala pa akong opisyal na detalye tungkol dito. Maaari po kayong "
            "magtanong nang direkta sa Barangay Sabang Hall o makipag-ugnayan sa Barangay Secretary."
        )
    return (
        "I don't have official details about that yet. Please ask directly at Barangay "
        "Sabang Hall or contact the Barangay Secretary."
    )


def _keyword_chat_fallback(question, context, matched_guide,
                           matched_announcements=None, matched_events=None):
    question = question.lower()
    emergency_terms = (
        "fire", "sunog", "medical emergency", "heart attack", "stroke",
        "crime in progress", "holdap", "robbery", "urgent rescue", "life-threatening flood",
    )
    if has_word(question, emergency_terms):
        if has_word(question, ["sunog", "baha", "tulong", "po", "opo"]):
            return (
                "Emergency po ito. Tumawag agad sa 911 o makipag-ugnayan sa Barangay "
                "Sabang Tanod outpost. Kung ligtas, lumipat sa ligtas na lugar."
            )
        return (
            "This may be an emergency. Call 911 or contact the Barangay Sabang Tanod "
            "outpost right away. Move to a safe place if you can."
        )
    if matched_guide:
        answer = matched_guide["answer"]
        if any(item.get("kind") in ("video", "image") for item in matched_guide.get("media", [])):
            note = (
                "Maaari po ninyong tingnan ang mga larawan o i-click ang video demo button sa ibaba."
                if has_word(question, ["po", "opo", "paano", "saan", "ano", "salamat"])
                else "You can view the guide photos or click the video demo button below for a visual walkthrough."
            )
            answer = f"{answer.rstrip()}\n\n{note}"
        related_posts = (matched_announcements or []) + (matched_events or [])
        if related_posts:
            answer += "\n\nRelated barangay records:\n" + "\n".join(
                _format_chat_post(record) for record in related_posts[:3]
            )
        return answer

    broad_terms = {
        "announcement", "announcements", "event", "events", "activity", "activities",
        "schedule", "upcoming", "latest", "news", "update", "updates", "service",
        "services", "serbisyo",
    }
    query_terms = _search_terms(question)
    if has_word(question, ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "kumusta"]):
        return (
            "Good day! I am the Barangay Sabang assistant. You may ask me about "
            "barangay services, announcements, or events."
        )
    if has_word(question, ["thanks", "thank", "salamat"]):
        return "You are welcome po. Please let me know if you need help with barangay information."

    if query_terms <= broad_terms and has_word(question, ["service", "services", "serbisyo"]):
        if context["services_list"]:
            return "Barangay services:\n" + "\n".join(
                f"• {item['name']}: {item['details'] or item['description']}"
                for item in context["services_list"]
            )
    if query_terms <= broad_terms and has_word(question, ["event", "events", "activity", "activities", "schedule", "upcoming"]):
        today = datetime.now().date().isoformat()
        upcoming_events = [
            item for item in context["events"]
            if item.get("sort_key") and item["sort_key"] >= today
        ]
        if upcoming_events:
            return "Listed barangay events:\n" + "\n".join(
                _format_chat_post(item)
                for item in upcoming_events
            )
        return "There are no upcoming events in the current barangay records."
    if query_terms <= broad_terms and has_word(question, ["announcement", "announcements", "news", "update", "updates", "latest"]):
        if context["announcements"]:
            return "Recent barangay announcements:\n" + "\n".join(
                _format_chat_post(item)
                for item in context["announcements"][:3]
            )

    service_matches = _rank_records(
        question, context["services_list"], ("name", "description", "details")
    )
    if service_matches:
        item = service_matches[0]
        return f"{item['name']}: {item['details'] or item['description']}"

    other_records = [
        (record, ("title", "description", "category", "auto_keywords", "verified_reference"))
        for record in context["announcements"]
    ] + [
        (record, ("title", "description", "location", "auto_keywords", "verified_reference"))
        for record in context["events"]
    ]
    ranked = [
        (_record_match_score(question, [record.get(field, "") for field in fields]), record)
        for record, fields in other_records
    ]
    matches = [record for score, record in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:3] if score > 0]
    if matches:
        return "\n".join(
            _format_chat_post(record)
            for record in matches
        )
    return _missing_information(question)


def _format_chat_post(record):
    answer = f"• {record['title']} ({record['date']})"
    if record.get("time") or record.get("location"):
        answer += f", {record.get('time', '')} at {record.get('location', '')}"
    answer += f": {record['description']}"
    reference = str(record.get("verified_reference") or "").strip()
    if reference:
        answer += f"\n  AI reference ({record.get('verification_status', 'pending')}): {reference}"
    source_urls = record.get("source_urls", [])
    if source_urls:
        answer += "\n  Sources: " + ", ".join(source_urls)
    return answer


def _format_system_prompt(context, matched_guide, matched_guides=None,
                          matched_announcements=None, matched_events=None):
    other_context = {
        "other_active_guides": [
            {key: guide[key] for key in ("topic", "keywords", "answer")}
            for guide in context["guide_ai_entries"]
            if not matched_guides or guide["id"] not in {
                entry["id"] for entry in matched_guides
            }
        ],
        "services": context["services_list"],
        "announcements": context["announcements"],
        "events": context["events"],
    }
    event_references = {
        "matched_guides": [
            {key: guide[key] for key in ("topic", "keywords", "answer")}
            for guide in (matched_guides or [])
        ],
        "announcements": [
            {key: record.get(key) for key in (
                "title", "date", "category", "description", "verification_status",
                "verified_reference", "auto_keywords", "source_urls", "last_checked_at",
            )}
            for record in (matched_announcements or [])
        ],
        "events": [
            {key: record.get(key) for key in (
                "title", "date", "time", "location", "description", "verification_status",
                "verified_reference", "auto_keywords", "source_urls", "last_checked_at",
            )}
            for record in (matched_events or [])
        ],
    }
    matched_guide_context = {
        "topic": matched_guide["topic"] if matched_guide else "No directly matched guide",
        "admin_notes": matched_guide["answer"] if matched_guide else "No directly matched guide notes",
        "has_media": bool(matched_guide and any(
            item.get("kind") in ("video", "image")
            for item in matched_guide.get("media", [])
        )),
    }
    replacements = {
        "{topic}": matched_guide_context["topic"],
        "{admin_notes}": matched_guide_context["admin_notes"],
        "{has_media}": str(matched_guide_context["has_media"]),
        "{other_active_guides_and_events}": json.dumps(other_context, ensure_ascii=False, indent=2),
        "{matched_guides_and_verified_posts}": json.dumps(
            event_references, ensure_ascii=False, indent=2
        ),
        "{current_date}": datetime.now().strftime("%Y-%m-%d"),
    }
    prompt = BARANGAY_SYSTEM_PROMPT
    pattern = re.compile("|".join(re.escape(key) for key in replacements))
    return pattern.sub(lambda match: replacements[match.group(0)], BARANGAY_SYSTEM_PROMPT)


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    question = str(data.get("message", "")).strip()
    if not question:
        return jsonify({"reply": "Kindly type your question first."}), 400
    if len(question) > 500:
        return jsonify({"reply": "Please keep your question under 500 characters."}), 400

    session_id = session.get("local_chat_session_id")
    if not session_id:
        session_id = secrets.token_urlsafe(24)
        session["local_chat_session_id"] = session_id
    try:
        result = LOCAL_CHATBOT.respond(question, session_id)
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        app.logger.error("Local assistant failed (%s).", type(exc).__name__)
        return jsonify({
            "message": "The assistant's local records are temporarily unavailable."
        }), 503
    return jsonify(result)
=======
@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    question = str(data.get("message", "")).strip().lower()
    if not question:
        return jsonify({"reply": "Kindly type your question first."}), 400

    # 1) Things the admin taught the assistant always come first.
    guide = find_guide(question)
    if guide:
        visual = [{"name": m["name"], "url": m["url"], "kind": m["kind"]}
                  for m in guide.get("media", []) if m["kind"] in ("video", "image")]
        return jsonify({"reply": guide["answer"], "topic": guide["topic"], "media": visual})

    # 2) Built-in answers (polite and formal).
    if has_word(question, ["print", "printing", "printer"]):
        reply = "Good day. For the free printing service, kindly refer to the barangay's approved schedule, requirements, and usage rules. Verified details have not yet been provided in this portal, so we respectfully advise you to confirm them with authorized barangay personnel."
    elif has_word(question, ["library", "e-library", "ebook", "ebooks"]):
        reply = "Good day. For access to the e-library, we kindly ask you to confirm the current operating hours and available resources with authorized barangay personnel."
    elif has_word(question, ["computer", "computers", "pc", "facility", "facilities"]):
        reply = "Good day. Regarding the computer facilities, we kindly ask you to confirm their availability, operating hours, and usage guidelines with authorized barangay personnel."
    elif has_word(question, ["event", "events", "activity", "activities", "schedule", "upcoming"]):
        live = [e for e in events if e.get("status") == "Published"]
        if live:
            lines = [f"• {e['title']} on {e['date']} at {e['time']} ({e['location']})" for e in live]
            reply = "Certainly. The following events are currently listed:\n" + "\n".join(lines) + "\n\nWe respectfully advise you to confirm the final schedule with the barangay."
        else:
            reply = "I regret to inform you that there are no events listed at this time. Kindly check again at a later date."
    elif has_word(question, ["announcement", "announcements", "news", "update", "updates"]):
        latest = [a for a in announcements if a["status"] == "Published"][:3]
        if latest:
            lines = [f"• {a['title']} ({a['date']})" for a in latest]
            reply = "Certainly. These are the latest announcements:\n" + "\n".join(lines) + "\n\nYou may view all of them in the Announcements section of this page."
        else:
            reply = "I regret to inform you that there are no announcements posted at this time."
    elif has_word(question, ["thanks", "thank"]):
        reply = "You are most welcome. Please do not hesitate to ask should you need any further assistance."
    elif has_word(question, ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]):
        reply = "Good day, and welcome to the Barangay Sabang portal. I am the virtual assistant. You may ask me about announcements, events, free printing, the e-library, or the computer facilities. How may I help you?"
    else:
        reply = "Good day. I regret that I do not have a verified answer to your question at this time. May I kindly ask you to rephrase it, or to contact authorized barangay personnel for assistance?"
    return jsonify({"reply": reply, "media": []})
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd



# ---------------------------------------------------------------------------
# ADMIN LOGIN / LOGOUT
# ---------------------------------------------------------------------------
def client_ip():
    return request.remote_addr or "unknown"


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    error = None
    ip = client_ip()
    record = failed_logins.get(ip, {"count": 0, "locked_until": 0})

    if request.method == "POST":
        now = time.time()
        if record["locked_until"] > now:
            minutes = int((record["locked_until"] - now) // 60) + 1
            error = f"Too many failed attempts. Try again in about {minutes} minute(s)."
        else:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if (secrets.compare_digest(username, ADMIN_USERNAME)
                    and check_password_hash(ADMIN_PASSWORD_HASH, password)):
                failed_logins.pop(ip, None)
                session.clear()
                session.permanent = True
                session["is_admin"] = True
                session["admin_name"] = username
                get_csrf_token()
                nxt = request.args.get("next", "")
                # only allow redirects to our own admin pages
                if nxt.startswith("/admin") and not nxt.startswith("//"):
                    return redirect(nxt)
                return redirect(url_for("admin_dashboard"))

            record["count"] += 1
            if record["count"] >= MAX_ATTEMPTS:
                record["locked_until"] = now + LOCKOUT_SECONDS
                record["count"] = 0
                error = "Too many failed attempts. Login is locked for 5 minutes."
            else:
                left = MAX_ATTEMPTS - record["count"]
                error = f"Incorrect username or password. {left} attempt(s) left."
            failed_logins[ip] = record

    return render_template("login.html", error=error), (401 if error else 200)


@app.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



# ---------------------------------------------------------------------------
# ADMIN DASHBOARD + API (all require login)
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html",
                           admin_name=session.get("admin_name", "admin"),
                           csrf_token=get_csrf_token())


@app.get("/api/admin/summary")
@admin_required
def admin_summary():
    live = lambda items: len([i for i in items if i.get("status") == "Published"])
    return jsonify({
        "announcements": live(announcements),
        "archived": len([i for i in announcements + events if i.get("status") == "Archived"]),
        "events": live(events),
        "guides": live(guides),
        "suggestions": len(suggestions),
        "new_suggestions": len([s for s in suggestions if s["status"] == "New"]),
        "new_reports": len([r for r in reports if r["status"] == "New"]),
    })


def form_data():
    """Reads either a multipart form (with files) or plain JSON."""
    if request.mimetype == "multipart/form-data":
        return request.form, request.files.getlist("media")
    return (request.get_json(silent=True) or {}), []


@app.get("/api/admin/<kind>")
@admin_required
def admin_list(kind):
    if kind not in COLLECTIONS:
        abort(404)
<<<<<<< HEAD
    if kind in EVENT_CONTENT_TABLES:
        start_pending_event_checks(kind)
    return jsonify([public_item(i, for_admin=True) for i in COLLECTIONS[kind]])
=======
    return jsonify([public_item(i) for i in COLLECTIONS[kind]])
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd


@app.post("/api/admin/announcements")
@admin_required
def add_announcement():
    data, files = form_data()
    title = str(data.get("title", "")).strip()
    category = str(data.get("category", "Community")).strip()
    description = str(data.get("description", "")).strip()
    if not title or not description:
        return jsonify({"ok": False, "message": "Title and description are required."}), 400
    if len(title) > 140 or len(description) > 1200:
        return jsonify({"ok": False, "message": "Please shorten the title or description."}), 400
    media, error = save_uploads(files)
    if error:
        return jsonify({"ok": False, "message": error}), 400
    item = {"id": new_id("announcements"),
            "category": category if category in CATEGORIES else "Community",
            "date": today_label(), "title": title, "description": description,
            "status": "Published", "media": media}
    announcements.insert(0, item)
    save_data()
<<<<<<< HEAD
    start_event_background_check(item["id"], "announcements")
    return jsonify({"ok": True, "announcement": public_item(item, for_admin=True)})
=======
    return jsonify({"ok": True, "announcement": public_item(item)})
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd


@app.post("/api/admin/events")
@admin_required
def add_event():
    data, files = form_data()
    title = str(data.get("title", "")).strip()
    date_text = str(data.get("date", "")).strip()          # YYYY-MM-DD from <input type=date>
    time_text = str(data.get("time", "")).strip()
    location = str(data.get("location", "")).strip()
    description = str(data.get("description", "")).strip()
<<<<<<< HEAD
    requirements = str(data.get("requirements", "")).strip()

    if not title or not date_text or not location:
        return jsonify({"ok": False, "message": "Title, date, and location are required."}), 400
    if (len(title) > 140 or len(location) > 140 or len(description) > 600
            or len(requirements) > 600):
=======

    if not title or not date_text or not location:
        return jsonify({"ok": False, "message": "Title, date, and location are required."}), 400
    if len(title) > 140 or len(location) > 140 or len(description) > 600:
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
        return jsonify({"ok": False, "message": "Please shorten one of the fields."}), 400
    try:
        when = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return jsonify({"ok": False, "message": "Please choose a valid date."}), 400

    shown_time = "Time to be confirmed"
    if time_text:
        try:
            t = datetime.strptime(time_text, "%H:%M")
            shown_time = f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"
        except ValueError:
            return jsonify({"ok": False, "message": "Please choose a valid time."}), 400

    media, error = save_uploads(files)
    if error:
        return jsonify({"ok": False, "message": error}), 400
    item = {"id": new_id("events"), "day": str(when.day), "month": MONTHS[when.month - 1],
            "title": title, "date": f"{when.strftime('%B')} {when.day}, {when.year}",
            "time": shown_time, "location": location,
<<<<<<< HEAD
            "description": description, "requirements": requirements,
=======
            "description": description or "Details to be announced.",
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
            "_sort": date_text, "status": "Published", "media": media}
    events.append(item)
    events.sort(key=lambda e: e.get("_sort", "9999-99-99"))
    save_data()
<<<<<<< HEAD
    start_event_background_check(item["id"], "events")
    return jsonify({"ok": True, "event": public_item(item, for_admin=True)})


@app.put("/api/admin/<kind>/<int:item_id>")
@admin_required
def edit_event_content(kind, item_id):
    if kind not in EVENT_CONTENT_TABLES:
        abort(404)
    item = find_item(kind, item_id)
    if not item:
        return jsonify({"ok": False, "message": "Item not found."}), 404
    if item.get("status") != "Published":
        return jsonify({"ok": False, "message": "Restore this post before editing it."}), 400
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    if not title or (kind == "announcements" and not description):
        return jsonify({"ok": False, "message": "Title and required details are needed."}), 400

    if kind == "announcements":
        if len(title) > 140 or len(description) > 1200:
            return jsonify({"ok": False, "message": "Please shorten the title or description."}), 400
        category = str(data.get("category", "Community")).strip()
        item.update({
            "title": title,
            "description": description,
            "category": category if category in CATEGORIES else "Community",
        })
    else:
        date_text = str(data.get("date", "")).strip()
        location = str(data.get("location", "")).strip()
        time_text = str(data.get("time", "")).strip()
        requirements = str(data.get("requirements", "")).strip()
        if not date_text or not location:
            return jsonify({"ok": False, "message": "Date and location are required."}), 400
        if (len(title) > 140 or len(description) > 600 or len(location) > 140
                or len(requirements) > 600):
            return jsonify({"ok": False, "message": "Please shorten one of the fields."}), 400
        try:
            when = datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError:
            return jsonify({"ok": False, "message": "Please choose a valid date."}), 400
        shown_time = "Time to be confirmed"
        if time_text:
            try:
                parsed_time = datetime.strptime(time_text, "%H:%M")
                shown_time = (
                    f"{parsed_time.hour % 12 or 12}:{parsed_time.minute:02d} "
                    f"{'AM' if parsed_time.hour < 12 else 'PM'}"
                )
            except ValueError:
                return jsonify({"ok": False, "message": "Please choose a valid time."}), 400
        item.update({
            "title": title,
            "description": description,
            "date": f"{when.strftime('%B')} {when.day}, {when.year}",
            "_sort": date_text,
            "day": str(when.day),
            "month": MONTHS[when.month - 1],
            "time": shown_time,
            "location": location,
            "requirements": requirements,
        })
        events.sort(key=lambda event: event.get("_sort", "9999-99-99"))

    save_data()
    start_event_background_check(item_id, kind)
    return jsonify({"ok": True, "item": public_item(item, for_admin=True)})
=======
    return jsonify({"ok": True, "event": public_item(item)})
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd


@app.post("/api/admin/guides")
@admin_required
def add_guide():
    """Teach the AI: a topic, the words residents use, and the answer to give.
    Photos/videos/files uploaded here become the 'video demo' / guide pictures."""
    data, files = form_data()
    topic = str(data.get("topic", "")).strip()
    answer = str(data.get("answer", "")).strip()
    keywords = [k.strip().lower() for k in str(data.get("keywords", "")).split(",") if k.strip()]
    if not topic or not answer:
        return jsonify({"ok": False, "message": "Topic and the answer are required."}), 400
    if len(topic) > 100 or len(answer) > 1200 or len(keywords) > 20:
        return jsonify({"ok": False, "message": "Please shorten the topic or answer (max 20 keywords)."}), 400
    media, error = save_uploads(files)
    if error:
        return jsonify({"ok": False, "message": error}), 400
    item = {"id": new_id("guides"), "topic": topic, "keywords": keywords, "answer": answer,
            "date": today_label(), "status": "Published", "media": media}
    guides.insert(0, item)
    save_data()
    return jsonify({"ok": True, "guide": public_item(item)})


# ---- shared actions: add more media, remove one media, archive, restore, delete
@app.post("/api/admin/<kind>/<int:item_id>/media")
@admin_required
def add_media(kind, item_id):
    item = find_item(kind, item_id)
    if not item:
        return jsonify({"ok": False, "message": "Item not found."}), 404
    files = request.files.getlist("media")
    if not [f for f in files if f and f.filename]:
        return jsonify({"ok": False, "message": "Please choose at least one file."}), 400
    if len(item.get("media", [])) + len(files) > MAX_MEDIA_PER_ITEM:
        return jsonify({"ok": False, "message": f"Each post can hold up to {MAX_MEDIA_PER_ITEM} files."}), 400
    media, error = save_uploads(files)
    if error:
        return jsonify({"ok": False, "message": error}), 400
    item.setdefault("media", []).extend(media)
    save_data()
<<<<<<< HEAD
    if kind in EVENT_CONTENT_TABLES and item.get("status") == "Published":
        start_event_background_check(item_id, kind)
=======
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
    return jsonify({"ok": True, "added": len(media)})


@app.delete("/api/admin/<kind>/<int:item_id>/media/<media_id>")
@admin_required
def remove_media(kind, item_id, media_id):
    item = find_item(kind, item_id)
    if not item:
        return jsonify({"ok": False, "message": "Item not found."}), 404
    gone = [m for m in item.get("media", []) if m["id"] == media_id]
    if not gone:
        return jsonify({"ok": False, "message": "File not found."}), 404
    item["media"] = [m for m in item["media"] if m["id"] != media_id]
    delete_media_files(gone)
    save_data()
<<<<<<< HEAD
    if kind in EVENT_CONTENT_TABLES and item.get("status") == "Published":
        start_event_background_check(item_id, kind)
=======
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
    return jsonify({"ok": True})


@app.post("/api/admin/<kind>/<int:item_id>/archive")
@admin_required
def archive_item(kind, item_id):
    item = find_item(kind, item_id)
    if not item:
        return jsonify({"ok": False, "message": "Item not found."}), 404
    item["status"] = "Archived"          # hidden from residents; no expiry date exists
    item["archived_on"] = today_label()
    save_data()
    return jsonify({"ok": True, "message": "Moved to the archive. Residents can no longer see it."})


@app.post("/api/admin/<kind>/<int:item_id>/restore")
@admin_required
def restore_item(kind, item_id):
    item = find_item(kind, item_id)
    if not item:
        return jsonify({"ok": False, "message": "Item not found."}), 404
    item["status"] = "Published"
    item.pop("archived_on", None)
    save_data()
<<<<<<< HEAD
    if kind in EVENT_CONTENT_TABLES:
        start_event_background_check(item_id, kind)
    return jsonify({"ok": True, "message": "Restored. Residents can see it again."})


@app.post("/api/admin/<kind>/<int:item_id>/recheck")
@admin_required
def recheck_event_content(kind, item_id):
    if kind not in EVENT_CONTENT_TABLES:
        abort(404)
    item = find_item(kind, item_id)
    if not item:
        return jsonify({"ok": False, "message": "Item not found."}), 404
    if item.get("status") != "Published":
        return jsonify({"ok": False, "message": "Restore this post before checking it."}), 400
    start_event_background_check(item_id, kind)
    return jsonify({"ok": True, "message": "Local AI index refresh started."})


=======
    return jsonify({"ok": True, "message": "Restored. Residents can see it again."})


>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
@app.delete("/api/admin/<kind>/<int:item_id>")
@admin_required
def delete_item(kind, item_id):
    item = find_item(kind, item_id)
    if not item:
        return jsonify({"ok": False, "message": "Item not found."}), 404
<<<<<<< HEAD
    if kind != "announcements" and item.get("status") != "Archived":
=======
    if item.get("status") != "Archived":
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd
        return jsonify({"ok": False, "message": "Please archive the item first, then delete it from the archive."}), 400
    COLLECTIONS[kind].remove(item)
    delete_media_files(item.get("media", []))
    save_data()
<<<<<<< HEAD
    message = "Announcement deleted permanently." if kind == "announcements" else "Deleted permanently."
    return jsonify({"ok": True, "message": message})
=======
    return jsonify({"ok": True, "message": "Deleted permanently."})
>>>>>>> d87743001bf31ccb31f9319a6740a485ad88bccd


# ---- suggestions ------------------------------------------------------------
@app.get("/api/admin/suggestions")
@admin_required
def admin_suggestions():
    return jsonify(suggestions)


@app.post("/api/admin/suggestions/<int:suggestion_id>/read")
@admin_required
def mark_suggestion_read(suggestion_id):
    for s in suggestions:
        if s["id"] == suggestion_id:
            s["status"] = "Read"
            save_data()
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Suggestion not found."}), 404


@app.delete("/api/admin/suggestions/<int:suggestion_id>")
@admin_required
def delete_suggestion(suggestion_id):
    before = len(suggestions)
    suggestions[:] = [s for s in suggestions if s["id"] != suggestion_id]
    if len(suggestions) == before:
        return jsonify({"ok": False, "message": "Suggestion not found."}), 404
    save_data()
    return jsonify({"ok": True, "message": "Suggestion deleted."})


# ---- problem reports ----------------------------------------------------------
@app.get("/api/admin/reports")
@admin_required
def admin_reports():
    return jsonify(reports)


@app.post("/api/admin/reports/<int:report_id>/resolve")
@admin_required
def resolve_report(report_id):
    for r in reports:
        if r["id"] == report_id:
            r["status"] = "Resolved"
            save_data()
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Report not found."}), 404


@app.delete("/api/admin/reports/<int:report_id>")
@admin_required
def delete_report(report_id):
    before = len(reports)
    reports[:] = [r for r in reports if r["id"] != report_id]
    if len(reports) == before:
        return jsonify({"ok": False, "message": "Report not found."}), 404
    save_data()
    return jsonify({"ok": True, "message": "Report deleted."})


if __name__ == "__main__":
    # debug=True is fine on your laptop. Never leave it on in a public deployment.
    # host="0.0.0.0" lets phones on the same Wi-Fi open the site (see the guide).
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")),
            debug=os.environ.get("FLASK_DEBUG", "1") == "1")
