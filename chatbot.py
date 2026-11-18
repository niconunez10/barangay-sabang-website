"""Local dialogue manager with SQLite-backed session context and safe templates."""

from datetime import date
import re


QUICK_SUGGESTIONS = [
    "Mga Bagong Anunsyo",
    "Schedule ng Event",
    "Barangay Clearance",
    "Health Center",
]
SIMILARITY_THRESHOLD = 0.35
SERVICE_INTENT_QUERIES = {
    "barangay_clearance": "barangay clearance certificate",
    "indigency_certificate": "indigency certificate",
    "health_center": "health center vaccine medical mission",
}
EMERGENCY_PATTERNS = (
    r"\b(?:fire|sunog|nasusunog|ambulance|emergency|911)\b",
    r"\b(?:heart attack|hirap huminga|hirap sa paghinga|hindi makahinga|walang malay|unconscious|not breathing)\b",
    r"\b(?:injured|nasugatan|dumudugo|bleeding|choking|poison|nalason)\b",
    r"\b(?:accident|aksidente|rescue|drowning|nalulunod|trapped|stranded|flooding|baha)\b",
    r"\b(?:crime in progress|ongoing crime|robbery|hold ?up|holdap|krimen|binubugbog|sinasaktan|domestic violence)\b",
    r"\b(?:saksak|binaril|gunshot|nabundol|need help now|kailangan ng rescue)\b",
)


class LocalChatbot:
    def __init__(self, database, ai_engine):
        self.database = database
        self.ai_engine = ai_engine

    @staticmethod
    def _is_tagalog(message):
        normalized = re.sub(r"[^\w\s]", " ", message.casefold())
        text = f" {normalized} "
        return any(marker in text for marker in (
            " po ", " opo ", " saan", " kailan", " ano ", " anong ",
            " kailangan", " mga ", " ba ", " ito", " salamat",
        ))

    @staticmethod
    def _followup_field(message):
        text = message.casefold()
        if any(term in text for term in (
            "requirements", "what should i bring", "what to bring", "need to bring",
            "anong kailangan", "ano ang kailangan", "ano po ang kailangan",
            "ano ang requirements", "dalhin",
        )):
            return "requirements"
        if any(term in text for term in ("where", "location", "venue", "saan", "lugar")):
            return "location"
        if any(term in text for term in ("what time", "time", "oras")):
            return "event_time"
        if any(term in text for term in ("when", "date", "kailan", "petsa")):
            return "event_date"
        return None

    def _response(self, reply, **extra):
        remaining = reply
        bubbles = []
        while len(remaining) > 1800:
            split_at = remaining.rfind("\n", 0, 1800)
            if split_at < 900:
                split_at = remaining.rfind(" ", 0, 1800)
            if split_at < 1:
                split_at = 1800
            bubbles.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        if remaining:
            bubbles.append(remaining)
        return {
            "reply": reply,
            "bubbles": bubbles,
            "suggestions": QUICK_SUGGESTIONS,
            "media": [],
            "sources": [],
            **extra,
        }

    def _fallback(self, tagalog=False):
        if tagalog:
            reply = (
                "Paumanhin po, wala akong sapat na detalye sa kasalukuyang opisyal na "
                "records para makasagot nang tama. Maaari po ninyong piliin ang isa sa "
                "mga paksa sa ibaba o magtanong sa Barangay Hall."
            )
        else:
            reply = (
                "Sorry, I don't have enough information in the current official records "
                "to answer accurately. Please choose a topic below or ask at the Barangay Hall."
            )
        return self._response(reply)

    @staticmethod
    def _field_value(record, field):
        mapping = {
            "location": "location",
            "event_date": "event_date",
            "event_time": "event_time",
            "requirements": "requirements",
        }
        value = str(record.get(mapping[field]) or "").strip()
        if field == "event_date":
            try:
                value = date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")
            except ValueError:
                pass
        return value

    def _answer_field(self, record, field, tagalog):
        value = self._field_value(record, field)
        if not value:
            labels_tl = {
                "location": "lugar",
                "event_date": "petsa",
                "event_time": "oras",
                "requirements": "mga kailangang dalhin o requirements",
            }
            labels_en = {
                "location": "location",
                "event_date": "date",
                "event_time": "time",
                "requirements": "requirements",
            }
            label = labels_tl[field] if tagalog else labels_en[field]
            reply = (
                f"Wala pong nakasaad na {label} sa opisyal na post na “{record['title']}”."
                if tagalog else
                f"The official post for “{record['title']}” does not list the {label}."
            )
        else:
            prefixes = {
                "location": ("Gaganapin po ito sa", "It will be held at"),
                "event_date": ("Ang nakatalang petsa po ay", "The listed date is"),
                "event_time": ("Ang nakatalang oras po ay", "The listed time is"),
                "requirements": ("Ang nakatalang requirements po ay", "The listed requirements are"),
            }
            prefix = prefixes[field][0 if tagalog else 1]
            reply = f"{prefix} {value}."
        return self._response(reply, topic=record["title"])

    def _format_record(self, record, tagalog):
        record_type = record["record_type"]
        title = record.get("title", "Barangay record")
        if record_type == "event":
            intro = f"Narito po ang nakatalang impormasyon para sa {title}:" if tagalog else f"Here is the listed information for {title}:"
            lines = [intro]
            fields = [
                ("Petsa", "event_date", "Date", "event_date"),
                ("Oras", "event_time", "Time", "event_time"),
                ("Lugar", "location", "Location", "location"),
                ("Requirements", "requirements", "Requirements", "requirements"),
                ("Detalye", "details", "Details", "details"),
            ]
            for tl_label, key, en_label, record_key in fields:
                value = str(record.get(record_key) or "").strip()
                if key == "event_date":
                    try:
                        value = date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")
                    except ValueError:
                        pass
                if value:
                    lines.append(f"{tl_label if tagalog else en_label}: {value}")
        elif record_type == "announcement":
            intro = f"Nakatalang anunsyo po: {title}." if tagalog else f"Listed announcement: {title}."
            lines = [intro]
            date_posted = str(record.get("date_posted") or "").strip()
            details = str(record.get("details") or "").strip()
            if date_posted:
                lines.append(f"{'Naipaskil' if tagalog else 'Posted'}: {date_posted}")
            if details:
                lines.append(f"{'Detalye' if tagalog else 'Details'}: {details}")
        elif record_type == "service":
            intro = f"Para sa {title} po:" if tagalog else f"For {title}:"
            lines = [intro]
            details = str(record.get("details") or "").strip()
            requirements = str(record.get("requirements") or "").strip()
            if details:
                lines.append(details)
            if requirements:
                lines.append(f"{'Requirements' if tagalog else 'Requirements'}: {requirements}")
        else:
            intro = f"Para sa {title} po:" if tagalog else f"For {title}:"
            details = str(record.get("details") or "").strip()
            lines = [intro, details] if details else [intro]
        if len(lines) == 1:
            lines.append(
                "Wala pang dagdag na detalyeng nakatala."
                if tagalog else "No additional details are listed."
            )
        return self._response("\n".join(lines), topic=title, media=record.get("media", []))

    def _list_reply(self, records, heading, tagalog):
        if not records:
            return self._fallback(tagalog)
        lines = [heading]
        for record in records:
            if record["record_type"] == "event":
                date_text = self._field_value(record, "event_date")
                if not date_text:
                    date_text = "Petsa ay hindi nakalista" if tagalog else "Date not listed"
                lines.append(f"• {record['title']} — {date_text}")
            else:
                lines.append(f"• {record['title']}")
        return self._response("\n".join(lines))

    def respond(self, message, session_id):
        tagalog = self._is_tagalog(message)
        intent = self.ai_engine.classify_intent(message)
        emergency_reported = any(
            re.search(pattern, message.casefold())
            for pattern in EMERGENCY_PATTERNS
        )
        intent_threshold = (
            0.18 if intent and intent["tag"] in {"greeting", "thanks"} else 0.25
        )
        intent_tag = (
            intent["tag"] if intent and intent["confidence"] >= intent_threshold else None
        )

        if emergency_reported or intent_tag == "emergency":
            reply = (
                "Emergency po ito. Tumawag agad sa 911 o humingi ng tulong sa Barangay Tanod."
                if tagalog else
                "This may be an emergency. Call 911 or contact the Barangay Tanod immediately."
            )
            return self._response(reply)
        if intent_tag == "greeting":
            reply = (
                "Magandang araw po. Paano kami makakatulong?"
                if tagalog else "Good day. How can I help you?"
            )
            return self._response(reply)
        if intent_tag == "thanks":
            reply = (
                "Walang anuman po. Narito lang kami para tumulong."
                if tagalog else "You're welcome. I'm here to help."
            )
            return self._response(reply)
        if intent_tag == "latest_announcements":
            return self._list_reply(
                self.database.list_recent_announcements(),
                "Mga pinakabagong anunsyo po:" if tagalog else "Recent announcements:",
                tagalog,
            )
        if intent_tag == "upcoming_events":
            return self._list_reply(
                self.database.list_upcoming_events(date.today().isoformat()),
                "Mga paparating na event po:" if tagalog else "Upcoming events:",
                tagalog,
            )

        field = self._followup_field(message)
        previous = self.database.get_chat_record(session_id) if field else None
        if previous and field:
            return self._answer_field(previous, field, tagalog)

        search_query = message
        if intent_tag in SERVICE_INTENT_QUERIES:
            search_query = f"{message} {SERVICE_INTENT_QUERIES[intent_tag]}"
        results = self.ai_engine.search(search_query, limit=5)
        match = next(
            (record for record in results
             if record["similarity"] >= SIMILARITY_THRESHOLD),
            None,
        )
        if not match:
            return self._fallback(tagalog)
        self.database.set_chat_record(
            session_id, match["record_type"], match["record_id"]
        )
        if field:
            return self._answer_field(match, field, tagalog)
        return self._format_record(match, tagalog)
