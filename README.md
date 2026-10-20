# Barangay Sabang Mock Website

A beginner-friendly local mockup built with HTML, CSS, JavaScript, and Python Flask.
Colors: white, blue, and red.

## Run on Windows (VS Code)

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
py app.py
```

Then open http://127.0.0.1:5000

## Admin login

- Page: http://127.0.0.1:5000/admin/login (or the "Admin login" link in the footer)
- Username: `admin`
- Password: `admin`

After logging in you can post announcements and events with photos, videos, and files,
add them to the archive (and restore them), teach the AI assistant ("Guide AI"),
read resident suggestions, and read problem reports. Logging out ends the session.

See **STEP_BY_STEP_GUIDE.md** for how every feature works and how to test it.

To use different credentials without editing code, set environment variables
before starting the server:

```powershell
$env:ADMIN_USERNAME = "myname"
$env:ADMIN_PASSWORD = "a-strong-password"
$env:SECRET_KEY = "any-long-random-text"
py app.py
```

## What is protected

- Admin pages and `/api/admin/*` require login (401 or redirect otherwise).
- Password is checked against a hash, not stored as plain text.
- 5 wrong logins lock that device for 5 minutes.
- Admin actions need a CSRF token, so other websites cannot trigger them.
- Login session expires after 2 hours.

## Where your data is saved

Everything (announcements, events, archive, AI guides, suggestions, problem reports)
is saved to `instance/data.json`, and uploaded photos/videos/files go to
`instance/uploads/`. Both survive a restart. **Back up the whole `instance` folder.**
It is ignored by git, so uploads are never committed.

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
- The chat assistant uses keyword matching plus the guides you write, not a trained AI model.
- Event dates and service details are sample content, not official information.
- Do not deploy publicly until it uses HTTPS, a database, and a strong password.
