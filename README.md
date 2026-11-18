# Barangay Sabang Mock Website

A beginner-friendly local mockup built with HTML, CSS, JavaScript, and Python Flask.
Colors: white, blue, and red.

## Run on Windows (VS Code)

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-local.txt
py app.py
```

Then open http://127.0.0.1:5000

The local website needs no `.env` AI credentials, web-search keys, model download,
or pretrained weights. Its main components are:

```text
app.py                 Flask pages, admin APIs, and local chat endpoint
ai_engine.py           Preprocessing, typo/synonym handling, TF-IDF, Naive Bayes
chatbot.py             Local intent routing, safe templates, and session follow-ups
database.py            SQLite schema, sample drafts, record sync, and chat context
intents.json           Editable local intent training phrases
synonyms.json          Editable Tagalog/English synonyms and common typos
templates/             Resident, admin, and login pages
static/css/style.css   Senior-friendly and responsive styles
static/js/main.js      Chat UI, quick replies, browser speech controls
instance/barangay.db  Created automatically: content_records, services, chat_context
```


## Optional: ping the developers when a problem is reported

```powershell
$env:DEV_WEBHOOK_URL = "https://discord.com/api/webhooks/...your-webhook..."
```

Reports always appear in the admin "Problem reports" tab and in the server console.

## Try it on a phone (same Wi-Fi)

```powershell
$env:HOST = "0.0.0.0"
py app.py
```

Then open `http://YOUR-PC-IP:5000` on the phone (find the IP with `ipconfig`).

## Important limitations

- `admin` / `admin` is a demo password. Change it before anyone else can reach the site.
- Single admin account only. A real database (PostgreSQL) and roles come next.
- The website assistant is fully local: custom preprocessing, synonyms/fuzzy matching, TF-IDF/cosine retrieval, and a Naive Bayes intent classifier implemented in `ai_engine.py`. It does not call an AI or search API and does not load pretrained model weights.
- Only published Guide AI entries, services, announcements, and events are indexed in `instance/barangay.db`. Admin changes rebuild the index. The four demo sample posts in SQLite are drafts and are never shown to residents.
- Answers are templates grounded in matched local records. The assistant does not generate facts; if the similarity is below 0.35 or the requested field is absent, it says that the records do not contain the answer.
- Native browser speech recognition is optional and browser-dependent; it may require internet and may send audio to the browser provider. Typing keeps resident messages local to this website. The website backend itself does not send chat messages to third-party AI services.
- Event dates and service details are sample content, not official information.
- Do not deploy publicly until it uses HTTPS, a database, and a strong password.

The SQLite AI index is created and synchronized automatically. Event and
announcement checks now only refresh local keywords and index metadata; their
**Local Only** badge explicitly means no independent external fact-check has
occurred. Admins must confirm official schedules and requirements before posting.

## Messenger AI backend (separate service)

The portal's Flask website and its chat are local-only. A separate FastAPI service
for Facebook Messenger is in `messenger_backend/`; it is a distinct application
and still uses the API-based integrations described below. Running the local
website requires only `requirements-local.txt`; do not start the Messenger
service if you need the entire installation to remain offline.
The backend files are organized as:

```text
messenger_backend/
  main.py                 FastAPI app, webhook verification, pipeline and Messenger delivery
  config.py               Environment and .env settings
  privacy.py              Local regex and NER PII masking
  prompts/                Intent and grounded-answer prompt templates
  db/schema.sql           Supabase pgvector table, indexes and hybrid-search RPC
  data/                   Example local-announcement JSON feed
  tests/                  Focused privacy, webhook and response tests
```

To run the separate Messenger service only, copy `.env.example` to `.env`,
configure its Facebook, model, Supabase, search, NER, and duty-desk settings,
then create the local feed and install its NER model:

```powershell
Copy-Item .env.example .env
Copy-Item messenger_backend\data\announcements.example.json messenger_backend\data\announcements.json
py -m pip install -r requirements.txt
py -m spacy download en_core_web_sm
```

The copied announcement is only a schema example and is intentionally stale;
replace it with current, verified barangay information before using the service.

Apply `messenger_backend/db/schema.sql` to the Supabase project and populate
`barangay_documents` with approved, chunked Charter/ordinance text and matching
1536-dimensional `text-embedding-3-small` embeddings. Configure a current, trusted barangay announcements
feed at the path in `ANNOUNCEMENTS_FEED_PATH`; feed entries must include
`title`, `content`, an ISO `published_at`, and an HTTPS `source_url`.
Configure the actual Barangay Tanod outpost number and a private HTTPS duty-desk
alert endpoint before production use.

Run the backend separately:

```powershell
py -m uvicorn messenger_backend.main:app --host 127.0.0.1 --port 8000
```

Set Facebook's webhook callback URL to `https://YOUR_HOST/webhook`, subscribe to
the `messages` event, and use the same `FACEBOOK_VERIFY_TOKEN` configured here.
`GET /health/ready` reports missing core settings; `/health/live` is a liveness
check. The webhook validates `X-Hub-Signature-256`. Incoming message bodies are
never logged, and PII filtering fails closed if the local NER model is not ready.
This filtering is a technical safeguard, not a guarantee of legal compliance;
validate the selected NER model and retention/consent process with the barangay's
Data Protection Officer before deployment.

Track A searches Supabase with semantic and lexical ranking; Track B accepts only
recent (seven days by default), dated sources on the configured trusted-domain
allowlist; Track C skips answer generation and sends a duty-desk alert without
including the resident's message text. Current-events responses include source
URLs and publication dates. Messenger limits quick-reply titles to 20 characters,
so the button is labeled **Talk to Secretary** while its payload remains
`TALK_TO_BARANGAY_SECRETARY`.
