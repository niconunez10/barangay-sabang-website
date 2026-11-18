# Barangay Sabang: Step-by-Step Guide to the New Features

This guide walks through every change you asked for: what it does, which file it lives in, how to test it, and how to adjust it. The finished code is already in this project, so you can follow along and test each step.

---

## Part 0 – Read this first

### The suggestion-box email: it is not in this version

You asked me to remove the feature that sends suggestions to a temporary email. I searched every file in `barangay_sabang_mock_v2.zip` (Python, HTML, JavaScript) for `mailto`, `smtp`, `emailjs`, `formspree`, `formsubmit`, and `email`. **None of them exist in this version.** Here, suggestions already go only to the admin page, and `/api/suggestions` in `app.py` only saves them to the Suggestions tab.

So there is nothing to delete in this zip. If an older or other copy of your project still has the email feature, **Part 5** below shows exactly how to find and remove it.

### Before you change anything

1. Make a backup copy of your whole project folder.
2. Unzip the new project. Run it (Windows, VS Code terminal):

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-local.txt
py app.py
```

3. Open http://127.0.0.1:5000 (website) and http://127.0.0.1:5000/admin/login (admin / admin).

### Files that changed

| File | What changed |
|---|---|
| `app.py` | Uploads, media, archive, Guide AI, formal chat replies, problem reports, saving data to disk |
| `ai_engine.py`, `chatbot.py`, `database.py` | Local-only preprocessing, retrieval, intent classification, dialogue context, and SQLite |
| `intents.json`, `synonyms.json` | Local training examples and editable synonym/typo mappings |

---

## Part 3 – Guide the AI

### Step 7: Teach the assistant (Admin → **Guide AI** tab)

1. **Topic**: e.g. `How to use the free printing service`.
2. **Keywords**: words residents may use, separated by commas, e.g. `print, printing, printer, xerox`. Keywords of 4+ letters also match longer forms ("print" matches "printer"). Short ones such as `id` must match the whole word.
3. **What should the AI say?** Enter complete, accurate, resident-ready steps in clear wording. The local assistant uses a fixed template and does not paraphrase shorthand or add unsupported details.
4. **Video demo or guide pictures** (optional): upload the demo video **you** made, or screenshots or photos that explain the steps.
5. Click **Save guide**.

Use **Try the assistant** (right side) to type a question and check the result before residents see it.

### Step 8: What residents see

When a resident's question matches your guide:

- The local TF-IDF index retrieves published guides, services, events, or announcements. Only matched record fields are used in a fixed response template.
- If the best match is below 0.35, the assistant does not guess and offers topic suggestions.
- Event/announcement records are local admin posts, not externally verified references.
- If you uploaded a video, a red **▶ Click for video demo** button appears under the answer. It opens the video in the expanded viewer.
- If you uploaded pictures, a blue **🖼 View guide pictures** button opens them as a gallery.

Guides are checked **before** the built-in answers, so your guide always wins. A guide can be archived (the AI stops using it) and restored.

### Step 9: Polite and formal tone

The local template replies are polite and use the resident's language when possible. They do not use a generative model or paraphrase admin notes, so enter clear, resident-ready guide text:

Greetings, thank-you responses, event lists, emergency guidance, and missing-information replies are local templates. The speech-recognition button is provided by the browser and may require internet; typing is the offline option. For details on the custom tokenizer, TF-IDF/cosine ranking, 0.35 threshold, and Naive Bayes intents, see `ai_engine.py`.

---

## Part 4 – "Report a problem" for residents

### Step 10: What residents see

A **⚑ Report a problem** button floats at the bottom-left of every page (just the flag icon on small phones), and there is also a link in the footer. It opens a short form:

- Kind of problem (dropdown)
- What happened (required)
- How to reach them (optional)
- A tick-box (on by default) to include **technical details**: device/browser, page address, screen size, and the last few JavaScript errors. This helps you fix bugs you cannot reproduce.

### Step 11: How the developers are notified, and why it is reliable

You said bugs might appear when residents use it, so this feature is built to be dependable:

1. **Saved first.** The report is saved in `instance/data.json` and appears in Admin → **Problem reports** (with a red badge for new ones). Open **Technical details** on a report to see the device, page, and errors.
2. **Console alert.** The server console (your terminal) prints a line for every report.
3. **Optional instant ping.** To get a message in Discord or Slack, create a webhook in that app and set it before starting the server:

```powershell
$env:DEV_WEBHOOK_URL = "https://discord.com/api/webhooks/...your-webhook..."
py app.py
```

   If the webhook fails, nothing breaks. It runs in the background and errors are ignored.
4. **Works with a bad connection.** If a resident's phone cannot reach the server, the report is kept on the device and **sent automatically** when the connection returns (they are told this). Duplicates are prevented.
5. **Spam limit.** One device can send at most 6 reports per 10 minutes.
6. When you fix something, click **Mark as resolved**.

> The admin page currently has one shared login, so "the devs" read reports there. When you add real accounts later, give developers their own.

---

## Part 5 – Suggestion box

### Step 12: Confirm suggestions go to the admin only

In this project the whole path is:

`index.html` form → `main.js` posts to `/api/suggestions` → `app.py` saves it → Admin → **Suggestions** tab.

**To test:** submit a suggestion on the home page, then open Admin → Suggestions → Refresh.

The thank-you message was changed to a formal one: *"Your suggestion has been received and forwarded to the barangay administrators."* A limit of 5 suggestions per 10 minutes per device was added against spam.

### If an older copy of your project still sends email, remove it like this

1. In VS Code press **Ctrl+Shift+F** (search the whole project) and search each of these words, one at a time: `mailto`, `smtplib`, `smtp`, `emailjs`, `formspree`, `formsubmit`, `sendgrid`, `mailgun`, `tempmail`, `fetch("https://`.
2. **HTML:** delete any `<form action="https://...">` pointing to an email service, and any `<a href="mailto:...">` tied to suggestions.
3. **JavaScript:** in `main.js`, the suggestion form's submit handler should only call `api("/api/suggestions", ...)`. Delete any `emailjs.send(...)` / extra `fetch(...)` to another site, and any `<script src="...emailjs...">` tag in the HTML.
4. **Python:** delete `import smtplib`, any `send_email(...)` function, and calls to it inside `submit_suggestion()`. Also delete leftover email addresses, passwords, or API keys from the code or `.env`.
5. Run the project and test: the suggestion must show in Admin → Suggestions, and nothing should be sent anywhere.
6. If you ever put a real key in the code, **treat it as exposed and generate a new one** at that provider.

---

## Part 6 – Phones and tablets (iOS, Android, other devices)

### What was done

- The site is **responsive**: the layout switches to a single column on phones, and the viewer, forms, and admin page all fit with no sideways scrolling (checked at phone width in a test browser).
- Form fields use 16 px text so iPhones do not zoom in when you tap them.
- Videos use `playsinline` so iPhones play them inside the page.
- Buttons have comfortable tap sizes, and the viewer supports swipe.
- Safe-area spacing for iPhones with a notch.
- **Add to Home Screen:** the site now has an icon and manifest, so it opens like an app.
  - **iPhone (Safari):** Share → **Add to Home Screen**
  - **Android (Chrome):** ⋮ menu → **Install app** / **Add to Home screen**

> This is a **website that behaves like an app**, not a separate App Store/Play Store app. A store app would be a later step (for example, wrapping this site with a tool such as Capacitor).

### Test on your own phone (same Wi-Fi)

1. Stop the server, then in PowerShell:

```powershell
$env:HOST = "0.0.0.0"
py app.py
```

2. Find your PC's IP with `ipconfig` (look for "IPv4 Address", e.g. `192.168.1.5`).
3. On the phone, open `http://192.168.1.5:5000`. If it does not load, allow Python through Windows Firewall when prompted.

### Tips for admins uploading from a phone

- **Videos:** use **MP4 (H.264)**. iPhone `.mov` files play in Safari but not always in Chrome/Android, so MP4 is safest. Keep videos under 100 MB.
- **iPhone photos:** the picker only lists JPEG/PNG/WebP/GIF, so iOS normally converts HEIC photos to JPEG for you. If a photo is refused, ask the iPhone user to choose "Most Compatible" under Settings → Camera → Formats.
- On mobile, the "+ Add more" buttons open the phone's photo/file picker.

---

## Part 7 – Full test checklist

Tick each one:

- [ ] Post an announcement with 2 photos + 1 video + 1 PDF → all appear on the home page.
- [ ] Hover over it on a computer → video plays, photos rotate.
- [ ] Click **Expand** → large view; arrows, Esc, and close all work.
- [ ] Open the PDF in Expand (computer) and Download (phone).
- [ ] Admin: **+ Add more photos** on an existing post → new photo appears.
- [ ] **Add to archive** → disappears from the public page. **Restore** → returns.
- [ ] Edit an event/announcement and verify its AI Reference status returns to Checking, then updates.
- [ ] Re-check an active post and verify the badge and source note refresh.
