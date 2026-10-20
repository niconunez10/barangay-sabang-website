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
pip install -r requirements.txt
py app.py
```

3. Open http://127.0.0.1:5000 (website) and http://127.0.0.1:5000/admin/login (admin / admin).

### Files that changed

| File | What changed |
|---|---|
| `app.py` | Uploads, media, archive, Guide AI, formal chat replies, problem reports, saving data to disk |
| `templates/index.html` | Report-a-problem button and window, expanded viewer, phone/home-screen tags |
| `templates/admin.html` | Photo/video/file pickers, Archive sections, Guide AI tab, Problem reports tab |
| `static/js/main.js` | Sliders, hover preview, expanded view, chat demo buttons, report sending |
| `static/js/admin.js` | Upload forms, "Add more photos", archive/restore, guides, reports |
| `static/css/style.css` | New styles added at the **bottom** of the file |
| `static/manifest.webmanifest`, `static/img/icon-*.png` | New: lets phones add the site to the home screen |

**If you already edited your own copy:** copy the files above over your copy one at a time and test after each, or compare them with a tool such as VS Code's "Compare Selected".

---

## Part 1 – Photos, videos, and files in announcements and events

### Step 1: Allow uploads on the server (`app.py`)

This is the foundation for everything else.

1. **Where files are stored.** Uploaded files go in `instance/uploads/` with a random name (for example `a3f9...c1.jpg`). The original name is kept in the data so downloads still show the right name.
2. **What is allowed** (top of `app.py`):
   - Photos: jpg, jpeg, png, gif, webp (up to 10 MB each)
   - Videos: mp4, webm, mov, m4v (up to 100 MB each)
   - Files: pdf, doc, docx, xls, xlsx, ppt, pptx, txt, csv (up to 20 MB each)
3. **Safety checks** in `save_uploads()`: the file type must be on the list, photos and PDFs must really start with the correct bytes (a renamed virus cannot pose as a `.jpg`), and the size limit applies. If any file in a batch fails, none of that batch is saved.
4. **Showing files to residents.** The `/media/<name>` route serves them. It supports "Range" requests, which iPhones **require** to play videos.

To change the limits, edit `SIZE_LIMIT`, `IMAGE_EXT`, `VIDEO_EXT`, and `FILE_EXT` at the top of `app.py`.

### Step 2: Admin can attach media when posting (`admin.html` + `admin.js`)

1. Open Admin → **Announcements**.
2. Fill in a title and description.
3. Click **+ Add more photos, videos, or files**. Choose one or more files. Click the same button again to add more, and use the **×** to remove any. Photos and videos can be mixed freely.
4. Click **Publish announcement**.

The same picker exists for **Events** and **Guide AI**.

**How it works:** the form is sent as `FormData` (the only way a browser can upload files). `admin.js` sets the CSRF token but must *not* set a JSON `Content-Type` for files, which is why `api()` checks `body instanceof FormData`.

### Step 3: "Add more photos" on an existing post

Each item in the admin list has a **+ Add more photos** button. Click it, choose files, and they are added to that post immediately. Each thumbnail has a red **×** to remove one file, and clicking a thumbnail previews it.

Server routes behind this: `POST /api/admin/<kind>/<id>/media` (add) and `DELETE /api/admin/<kind>/<id>/media/<media_id>` (remove). `<kind>` is `announcements`, `events`, or `guides`.

### Step 4: Residents see photos and videos on the main page (`main.js`)

Every announcement or event with media now shows it at the top of its card:

- **Slider.** One photo or video fills the card. Several become a slider with arrows, dots, and a "2/5" counter. Photos and videos can be mixed.
- **Hover preview (computers).** When a resident hovers over a card, videos play silently and photos rotate every 2.4 seconds. A playing video finishes before moving on.
- **Touch (phones/tablets).** Swipe left or right. Hover is not used on touch screens; tapping opens the large view.
- **Files** (PDF, Word, etc.) appear as small cards under the slider with **Expand** and **Download** buttons.

### Step 5: Expanded view

The **⤢ Expand** button (top-right of the slider), or tapping the media, opens a full-screen viewer:

- Photos and videos shown large (videos have play controls and work on iPhone without forcing full screen).
- Arrow buttons, keyboard arrows, and swipe move between items.
- **Esc**, the **×** button, or tapping the dark area closes it.
- PDFs show inside the viewer on computers. On phones (small screens), PDFs and other files show an **Open file** and **Download** card, because phone browsers handle embedded PDFs poorly.
- "Open in new tab" is always available.

**To test Part 1:** post an announcement with 2 photos, 1 video, and 1 PDF. Open the home page in another tab. Hover, swipe, click Expand, and open the PDF.

---

## Part 2 – Archive ("Add to archive")

### Step 6: How the archive works

- Each active announcement, event, and guide has an **Add to archive** button.
- Archived items are **hidden from residents** (the public API only returns `status == "Published"`).
- Archived items go to the **Archive** section under the list. They **never expire**: there is no date logic anywhere, and the data is saved to `instance/data.json`.
- Click **Restore** and it is visible to residents again.
- **Delete permanently** exists only inside the archive, so nothing is lost by accident. The server also refuses to delete an item that is not archived first. Deleting also erases that item's uploaded files.

**To test:** archive an announcement, refresh the public page (it disappears), then Restore it (it returns).

---

## Part 3 – Guide the AI

### Step 7: Teach the assistant (Admin → **Guide AI** tab)

1. **Topic**: e.g. `How to use the free printing service`.
2. **Keywords**: words residents may use, separated by commas, e.g. `print, printing, printer, xerox`. Keywords of 4+ letters also match longer forms ("print" matches "printer"). Short ones such as `id` must match the whole word.
3. **What should the AI say?** Write the steps in clear, formal wording. The assistant shows your text exactly as written.
4. **Video demo or guide pictures** (optional): upload the demo video **you** made, or screenshots or photos that explain the steps.
5. Click **Save guide**.

Use **Try the assistant** (right side) to type a question and check the result before residents see it.

### Step 8: What residents see

When a resident's question matches your guide:

- The assistant replies with your answer.
- If you uploaded a video, a red **▶ Click for video demo** button appears under the answer. It opens the video in the expanded viewer.
- If you uploaded pictures, a blue **🖼 View guide pictures** button opens them as a gallery.

Guides are checked **before** the built-in answers, so your guide always wins. A guide can be archived (the AI stops using it) and restored.

### Step 9: Polite and formal tone

All the built-in replies in `app.py` (`chat()`) were rewritten, for example:

> "Good day. I regret that I do not have a verified answer to your question at this time. May I kindly ask you to rephrase it, or to contact authorized barangay personnel for assistance?"

The greeting, "thank you" replies, event lists, and announcement lists are also formal. For **your guides**, the tone is whatever you type, so write them politely (for example, "Kindly bring…", "Please proceed to…").

> **Honest note:** this assistant matches keywords and shows what you taught it. It is not a trained AI model, so it cannot answer questions you have not guided it on. If you connect a real AI model later, the tone rule would go into its instructions, for example: *"Always respond politely and formally, as a courteous barangay assistant. Use only the information provided."*

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
- [ ] Try uploading a `.exe` → refused with a clear message.
- [ ] Guide AI: create a guide with a video; ask the chat → **Click for video demo** works.
- [ ] Ask the chat something unknown → polite, formal reply.
- [ ] Submit a suggestion → shows in Admin → Suggestions. No email anywhere.
- [ ] Report a problem → appears in Admin → Problem reports with technical details.
- [ ] Turn off Wi-Fi, send a report → "saved on this device"; turn Wi-Fi on → it arrives once.
- [ ] Open the site on a phone and an iPad: no sideways scrolling, swipe works, Add to Home Screen works.

---

## Part 8 – Things to know

- **Data is now saved** to `instance/data.json` (it no longer resets when Flask restarts). Back up the `instance` folder. This is what lets archived items last forever. For a real launch, move to a database (PostgreSQL), as already planned in your README.
- **Uploaded files have unguessable web addresses**, but anyone with a direct link can open it, even if the post is archived. Do not upload private documents (IDs, forms with personal data) until real file permissions exist.
- **Before going public:** change `admin` / `admin`, set `SECRET_KEY`, turn off debug, use HTTPS, and review who may upload. Videos can be large, so check your hosting storage and bandwidth.
- **Not built (ask me if wanted):** video compression, editing an announcement's text after posting, drag-to-reorder photos, and separate developer accounts.
