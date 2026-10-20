import json
import os
import re
import secrets
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

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
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "instance"          # already listed in .gitignore
UPLOAD_DIR = DATA_DIR / "uploads"
DATA_FILE = DATA_DIR / "data.json"
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


def save_data():
    """Writes everything to disk safely (temp file first, then swap)."""
    with data_lock:
        payload = {"announcements": announcements, "events": events, "guides": guides,
                   "suggestions": suggestions, "reports": reports, "ids": ids}
        tmp = DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, DATA_FILE)


def load_data():
    if not DATA_FILE.exists():
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


load_data()


def new_id(kind):
    with data_lock:
        value = ids[kind]
        ids[kind] += 1
        return value


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


def public_item(item):
    """Copy of an item that is safe to send to residents."""
    clean = {k: v for k, v in item.items() if not k.startswith("_")}
    clean["media"] = [{k: m[k] for k in ("id", "name", "url", "kind", "size")}
                      for m in item.get("media", [])]
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
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def find_guide(question):
    """Returns the admin-taught guide that best matches the question, or None."""
    best, best_score = None, 0
    for g in guides:
        if g.get("status") != "Published":
            continue
        terms = [k for k in g.get("keywords", []) if k] + [g["topic"].lower()]
        # Keywords of 4+ letters also match longer forms ("print" finds "printer",
        # "printing"). Short ones must match the whole word ("id" must not match "idea").
        score = sum(1 for t in terms
                    if re.search(rf"\b{re.escape(t)}{r'\w*' if len(t) >= 4 else r'\b'}", question))
        if score > best_score:
            best, best_score = g, score
    return best


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
    return jsonify([public_item(i) for i in COLLECTIONS[kind]])


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
    return jsonify({"ok": True, "announcement": public_item(item)})


@app.post("/api/admin/events")
@admin_required
def add_event():
    data, files = form_data()
    title = str(data.get("title", "")).strip()
    date_text = str(data.get("date", "")).strip()          # YYYY-MM-DD from <input type=date>
    time_text = str(data.get("time", "")).strip()
    location = str(data.get("location", "")).strip()
    description = str(data.get("description", "")).strip()

    if not title or not date_text or not location:
        return jsonify({"ok": False, "message": "Title, date, and location are required."}), 400
    if len(title) > 140 or len(location) > 140 or len(description) > 600:
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
            "description": description or "Details to be announced.",
            "_sort": date_text, "status": "Published", "media": media}
    events.append(item)
    events.sort(key=lambda e: e.get("_sort", "9999-99-99"))
    save_data()
    return jsonify({"ok": True, "event": public_item(item)})


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
    return jsonify({"ok": True, "message": "Restored. Residents can see it again."})


@app.delete("/api/admin/<kind>/<int:item_id>")
@admin_required
def delete_item(kind, item_id):
    item = find_item(kind, item_id)
    if not item:
        return jsonify({"ok": False, "message": "Item not found."}), 404
    if item.get("status") != "Archived":
        return jsonify({"ok": False, "message": "Please archive the item first, then delete it from the archive."}), 400
    COLLECTIONS[kind].remove(item)
    delete_media_files(item.get("media", []))
    save_data()
    return jsonify({"ok": True, "message": "Deleted permanently."})


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
