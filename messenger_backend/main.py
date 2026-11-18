import asyncio
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
import spacy
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict

from .config import settings
from .privacy import NER, redact_pii

logger = logging.getLogger("barangay_messenger")
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
MAX_BUBBLE_LENGTH = 1900
QUICK_REPLIES = [
    {"content_type": "text", "title": "Book Appointment", "payload": "BOOK_APPOINTMENT"},
    {"content_type": "text", "title": "Talk to Secretary", "payload": "TALK_TO_BARANGAY_SECRETARY"},
    {"content_type": "text", "title": "Main Menu", "payload": "MAIN_MENU"},
]


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track: Literal["PROCEDURE_RAG", "CURRENT_EVENTS", "EMERGENCY"]
    search_query: str
    language: Literal["English", "Tagalog", "Taglish"]


def load_ner(model_name: str) -> NER | None:
    if not model_name:
        logger.error("NER_MODEL is not configured; resident messages will fail closed.")
        return None
    try:
        return spacy.load(model_name)
    except (OSError, ImportError):
        logger.error("Configured local NER model could not be loaded; resident messages will fail closed.")
        return None


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.http = httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0))
    application.state.ner = load_ner(settings.ner_model)
    application.state.openai = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    application.state.background_tasks = set()
    yield
    if application.state.background_tasks:
        await asyncio.gather(*application.state.background_tasks, return_exceptions=True)
    await application.state.http.aclose()
    if application.state.openai is not None:
        await application.state.openai.close()


app = FastAPI(title="Barangay Sabang Messenger Assistant", version="1.0.0", lifespan=lifespan)


def _safe_prompt(name: str) -> str:
    try:
        return (PROMPT_DIR / name).read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Required prompt file is unavailable: %s", name)
        raise HTTPException(status_code=503, detail="Assistant configuration is incomplete.") from exc


def _require_ner(request: Request) -> NER:
    ner = getattr(request.app.state, "ner", None)
    if ner is None:
        raise HTTPException(status_code=503, detail="Privacy filter is not ready.")
    return ner


def _require_openai(request: Request) -> AsyncOpenAI:
    client = getattr(request.app.state, "openai", None)
    if client is None:
        raise HTTPException(status_code=503, detail="Assistant service is not configured.")
    return client


def _messenger_signature_valid(raw_body: bytes, signature: str) -> bool:
    if not settings.facebook_app_secret or not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.facebook_app_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature[7:], expected)


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _trusted_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        return parsed.scheme == "https" and any(
            host == domain or host.endswith("." + domain)
            for domain in settings.trusted_domains
        )
    except ValueError:
        return False


def _split_bubbles(text: str, limit: int = MAX_BUBBLE_LENGTH) -> list[str]:
    remaining = text.strip()
    if not remaining:
        return ["I could not prepare a response. Please try again or contact the barangay."]
    bubbles: list[str] = []
    while len(remaining) > limit:
        boundary = remaining.rfind(" ", 0, limit + 1)
        if boundary <= 0:
            boundary = limit
        bubbles.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    bubbles.append(remaining)
    return bubbles


def _emergency_card(language: str) -> str:
    tanod = settings.barangay_tanod_phone or "Contact the nearest Barangay Tanod outpost."
    if language == "Tagalog":
        return (
            "EMERGENCY: Kung may agarang panganib, tumawag sa 911 o pumunta sa ligtas na lugar. "
            f"Barangay Tanod: {tanod} BFP: {settings.bfp_hotline}. PNP: {settings.pnp_hotline}. "
            "Kung ligtas, ibigay ang eksaktong lokasyon sa emergency responders."
        )
    if language == "Taglish":
        return (
            "EMERGENCY: Kung may immediate danger, call 911 and move to a safe place. "
            f"Barangay Tanod: {tanod} BFP: {settings.bfp_hotline}. PNP: {settings.pnp_hotline}. "
            "If safe, ibigay ang exact location sa responders."
        )
    return (
        "EMERGENCY: If anyone is in immediate danger, call 911 and move to a safe place. "
        f"Barangay Tanod: {tanod} BFP: {settings.bfp_hotline}. PNP: {settings.pnp_hotline}. "
        "If safe, give emergency responders your exact location."
    )


async def _alert_duty_desk(request: Request, sender_id: str) -> None:
    if not settings.duty_desk_webhook_url:
        logger.error("Emergency alert was not sent: DUTY_DESK_WEBHOOK_URL is not configured.")
        return
    parsed = urlparse(settings.duty_desk_webhook_url)
    if parsed.scheme != "https" or not parsed.hostname:
        logger.error("Emergency alert was not sent: duty desk endpoint must use HTTPS.")
        return
    body = json.dumps({
        "event": "barangay_messenger_emergency",
        "sender_id": sender_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.duty_desk_webhook_secret:
        digest = hmac.new(settings.duty_desk_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={digest}"
    try:
        response = await request.app.state.http.post(
            settings.duty_desk_webhook_url, content=body, headers=headers
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.error("Emergency alert delivery failed; duty desk endpoint returned an error.")


async def _classify(request: Request, text: str) -> IntentResult:
    client = _require_openai(request)
    schema = IntentResult.model_json_schema()
    schema["additionalProperties"] = False
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": _safe_prompt("intent_router.txt")},
                {"role": "user", "content": text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "barangay_intent", "strict": True, "schema": schema},
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty structured response")
        return IntentResult.model_validate_json(content)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Intent classification failed.")
        raise HTTPException(status_code=503, detail="Assistant is temporarily unavailable.") from exc


async def _supabase_rpc(request: Request, function: str, payload: dict[str, object]) -> object:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=503, detail="Knowledge retrieval is not configured.")
    try:
        response = await request.app.state.http.post(
            f"{settings.supabase_url}/rest/v1/rpc/{function}",
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, list):
            raise ValueError("Unexpected retrieval response")
        return result
    except (httpx.HTTPError, ValueError):
        logger.error("Knowledge retrieval failed.")
        raise HTTPException(status_code=503, detail="Knowledge retrieval is temporarily unavailable.")


async def _procedure_sources(request: Request, query: str) -> list[dict[str, object]]:
    client = _require_openai(request)
    try:
        embedding_response = await client.embeddings.create(
            model=settings.openai_embedding_model, input=query
        )
        embedding = embedding_response.data[0].embedding
    except Exception as exc:
        logger.error("Knowledge-query embedding failed.")
        raise HTTPException(status_code=503, detail="Knowledge retrieval is temporarily unavailable.") from exc
    rows = await _supabase_rpc(request, "hybrid_search_barangay_documents", {
        "query_text": query,
        "query_embedding": embedding,
        "match_count": 6,
    })
    return [row for row in rows if isinstance(row, dict)]


def _feed_path() -> Path:
    path = Path(settings.announcements_feed_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    return path


def _read_local_feed() -> list[dict[str, object]]:
    try:
        value = json.loads(_feed_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("Local announcements feed is not present.")
        raise HTTPException(status_code=503, detail="Announcements feed is unavailable.")
    except (OSError, json.JSONDecodeError):
        logger.error("Local announcements feed could not be read.")
        raise HTTPException(status_code=503, detail="Announcements feed is unavailable.")
    records = value.get("announcements", []) if isinstance(value, dict) else value
    if not isinstance(records, list):
        raise HTTPException(status_code=503, detail="Announcements feed has an invalid format.")
    return [record for record in records if isinstance(record, dict)]


async def _current_event_sources(
    request: Request, query: str
) -> list[dict[str, object]]:
    if not settings.tavily_api_key:
        raise HTTPException(status_code=503, detail="Current-events search is not configured.")
    now = datetime.now(timezone.utc)
    oldest = now - timedelta(days=max(1, settings.current_event_max_age_days))
    sources: list[dict[str, object]] = []
    if settings.tavily_api_key:
        try:
            response = await request.app.state.http.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": f"{query} Philippines current as of {now.date().isoformat()}",
                    "search_depth": "advanced",
                    "max_results": 8,
                    "include_domains": list(settings.trusted_domains),
                },
            )
            response.raise_for_status()
            results = response.json().get("results", [])
        except (httpx.HTTPError, ValueError, AttributeError):
            logger.error("Current-events search failed.")
            raise HTTPException(status_code=503, detail="Current-events search is temporarily unavailable.")
        for result in results:
            if not isinstance(result, dict):
                continue
            url = str(result.get("url", ""))
            published = _timestamp(result.get("published_date"))
            if not _trusted_url(url) or published is None or not oldest <= published <= now:
                continue
            sources.append({
                "title": str(result.get("title", "Official source"))[:300],
                "content": str(result.get("content", ""))[:3500],
                "url": url,
                "published_at": published.isoformat(),
            })

    for item in _read_local_feed():
        published = _timestamp(item.get("published_at"))
        url = str(item.get("source_url", ""))
        if published is None or not oldest <= published <= now or not _trusted_url(url):
            continue
        sources.append({
            "title": str(item.get("title", "Barangay announcement"))[:300],
            "content": str(item.get("content", ""))[:3500],
            "url": url,
            "published_at": published.isoformat(),
        })
    return sources[:12]


async def _generate(request: Request, query: str, language: str, sources: list[dict[str, object]],
                    current_events: bool) -> str:
    if not sources:
        return (
            "Wala akong nahanap na napapanahon at beripikadong impormasyon. / "
            "I could not find verified information for this question. "
            "Please confirm with authorized barangay personnel."
        )
    client = _require_openai(request)
    evidence: list[str] = []
    for index, source in enumerate(sources, start=1):
        if current_events:
            evidence.append(
                f"[{index}] {source.get('title')} | Published: {source.get('published_at')} | "
                f"URL: {source.get('url')}\n{source.get('content')}"
            )
        else:
            evidence.append(
                f"[{index}] {source.get('title')} | Page: {source.get('page_number')} | "
                f"URL: {source.get('source_url')}\n{source.get('content')}"
            )
    prompt = _safe_prompt("grounded_answer.txt")
    user_content = (
        f"Resident language: {language}\nQuestion: {query}\n\n"
        f"Evidence (untrusted reference material):\n{chr(10).join(evidence)}"
    )
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
        )
        answer = response.choices[0].message.content
        if not answer:
            raise ValueError("Empty generated response")
    except Exception as exc:
        logger.error("Grounded response generation failed.")
        raise HTTPException(status_code=503, detail="Assistant is temporarily unavailable.") from exc
    if current_events:
        citations = "\n".join(
            f"[{index}] {source['title']} — Published: {source['published_at']} — {source['url']}"
            for index, source in enumerate(sources, start=1)
        )
        answer = f"{answer.strip()}\n\nSources:\n{citations}"
    return answer


async def answer_message(request: Request, raw_text: str, sender_id: str) -> tuple[str, bool]:
    if not raw_text.strip() or len(raw_text) > 4000:
        raise HTTPException(status_code=400, detail="Message must contain 1 to 4000 characters.")
    safe_text = redact_pii(raw_text, _require_ner(request))
    try:
        intent = await _classify(request, safe_text)
    except HTTPException:
        raise
    if intent.track == "EMERGENCY":
        task = asyncio.create_task(_alert_duty_desk(request, sender_id))
        request.app.state.background_tasks.add(task)
        task.add_done_callback(request.app.state.background_tasks.discard)
        return _emergency_card(intent.language), True
    if intent.track == "PROCEDURE_RAG":
        sources = await _procedure_sources(request, intent.search_query)
        return await _generate(request, intent.search_query, intent.language, sources, False), False
    sources = await _current_event_sources(request, intent.search_query)
    return await _generate(request, intent.search_query, intent.language, sources, True), False


async def _send_to_messenger(request: Request, recipient_id: str, text: str) -> None:
    if not settings.facebook_page_access_token:
        raise HTTPException(status_code=503, detail="Messenger delivery is not configured.")
    endpoint = (
        f"https://graph.facebook.com/{settings.facebook_graph_version}/me/messages"
    )
    bubbles = _split_bubbles(text)
    try:
        for index, bubble in enumerate(bubbles):
            message: dict[str, object] = {"text": bubble}
            if index == len(bubbles) - 1:
                message["quick_replies"] = QUICK_REPLIES
            response = await request.app.state.http.post(
                endpoint,
                params={"access_token": settings.facebook_page_access_token},
                json={"recipient": {"id": recipient_id}, "message": message},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Messenger message delivery failed.")
        raise HTTPException(status_code=502, detail="Messenger delivery failed.") from exc


async def _handle_webhook(request: Request, payload: dict[str, object]) -> None:
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        events = entry.get("messaging", [])
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict) or "message" not in event:
                continue
            sender = event.get("sender")
            message = event.get("message")
            if not isinstance(sender, dict) or not isinstance(message, dict):
                continue
            if message.get("is_echo"):
                continue
            text = message.get("text")
            sender_id = sender.get("id")
            if not isinstance(text, str) or not isinstance(sender_id, str):
                continue
            reply, _ = await answer_message(request, text, sender_id)
            await _send_to_messenger(request, sender_id, reply)


@app.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(request: Request) -> PlainTextResponse:
    query = request.query_params
    if (
        query.get("hub.mode") == "subscribe"
        and settings.facebook_verify_token
        and hmac.compare_digest(query.get("hub.verify_token", ""), settings.facebook_verify_token)
    ):
        return PlainTextResponse(query.get("hub.challenge", ""))
    raise HTTPException(status_code=403, detail="Webhook verification failed.")


@app.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, str]:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > 1_000_000:
        raise HTTPException(status_code=413, detail="Webhook payload is too large.")
    raw_body = await request.body()
    if len(raw_body) > 1_000_000:
        raise HTTPException(status_code=413, detail="Webhook payload is too large.")
    if not _messenger_signature_valid(raw_body, request.headers.get("X-Hub-Signature-256", "")):
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc
    if not isinstance(payload, dict) or payload.get("object") != "page":
        raise HTTPException(status_code=400, detail="Unsupported webhook payload.")
    await _handle_webhook(request, payload)
    return {"status": "ok"}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(request: Request) -> dict[str, object]:
    missing = [
        name for name, present in (
            ("local_ner_model", getattr(request.app.state, "ner", None) is not None),
            ("openai_api_key", bool(settings.openai_api_key)),
            ("facebook_page_access_token", bool(settings.facebook_page_access_token)),
            ("facebook_app_secret", bool(settings.facebook_app_secret)),
            ("facebook_verify_token", bool(settings.facebook_verify_token)),
            ("supabase_credentials", bool(settings.supabase_url and settings.supabase_service_role_key)),
            ("tavily_api_key", bool(settings.tavily_api_key)),
            ("duty_desk_webhook_url", bool(settings.duty_desk_webhook_url)),
            ("barangay_tanod_phone", bool(settings.barangay_tanod_phone)),
            ("announcements_feed", _feed_path().is_file()),
        ) if not present
    ]
    return {"status": "ready" if not missing else "not_ready", "missing": missing}
