# Google Careers Apply-Button Tracker

A dashboard that watches Google Careers job listings and tells you the moment the "Apply" button goes live, so you don't have to keep refreshing the page yourself.

Google frequently posts job listings before applications actually open — the page exists, but there's no way to apply yet. This tool polls a listing in the background and pushes a notification (phone + desktop) as soon as the apply link appears.

## How it works

1. Paste a Google Careers job URL into the dashboard and click **Track**.
2. The job is checked immediately, then re-checked automatically every `POLL_INTERVAL_SECONDS` (default 60s) until its Apply button appears.
3. Once found, you get a push notification (via [ntfy.sh](https://ntfy.sh)) and/or a desktop notification, and the dashboard shows a direct "Apply link" for that job.
4. Jobs that already found their apply button stop being polled — only jobs still in the `waiting` state are re-checked.

## Architecture

```
app.py            Flask routes, background scheduler, request handling
job_checker.py    Fetches a job page and extracts title + apply URL
store.py          SQLite persistence (jobs table)
notifier.py       Notification backends (ntfy.sh push, desktop via plyer)
templates/
  dashboard.html  The single-page dashboard UI
jobs.db           SQLite database file (created automatically)
```

**Request flow:**
- `GET /` renders the dashboard from the current DB state.
- `POST /jobs` adds a new job and checks it once immediately (so "Added" and "Last checked" line up right away instead of waiting for the next poll).
- `POST /jobs/<id>/check` lets you manually re-check a single job on demand.
- `POST /jobs/<id>/delete` removes a tracked job.

**Background polling:**
An APScheduler `BackgroundScheduler` runs `poll_all_waiting_jobs()` on a fixed interval inside the same process as the Flask app. It iterates every job with `status = 'waiting'`, fetches the page, and either marks it checked (still waiting, or errored) or found (apply button appeared → fires a notification).

### Why the apply link needed special handling

Google Careers is an Angular single-page app. Its "Apply" button's `href` is a *relative* URL — but relative to the page's `<base href="https://www.google.com/about/careers/applications/">` tag, not relative to the job listing's own URL. Resolving it naively against the job URL silently drops the job-ID path segment and lands on a broken "job not found" page. `job_checker.py` reads the actual `<base>` tag out of the fetched HTML and resolves the apply link against *that*, matching what a real browser click does.

## Data model (`jobs.db`, SQLite)

| Column | Meaning |
|---|---|
| `url` | The tracked job listing URL (unique) |
| `title` | Job title, filled in on first successful check |
| `status` | `waiting` or `found` |
| `apply_url` | Resolved apply link, once found |
| `added_at` / `last_checked_at` / `found_at` | ISO-8601 UTC timestamps (rendered in local time in the UI via a `friendly_time` template filter) |
| `last_error` | Last fetch error, if any, shown inline in the dashboard |

## Notifications

`notifier.py` tries every configured channel, best-effort:
- **ntfy.sh** — free, no signup, push to phone/desktop. Configure `NTFY_TOPIC` (pick something hard to guess — public ntfy topics aren't private) and subscribe to the same topic in the ntfy app or at `https://ntfy.sh/<topic>`.
- **Desktop notification** — via `plyer`, works locally; not applicable when running on a headless server.

## Configuration

Copy `.env.example` to `.env` and fill in real values (never commit `.env`):

| Variable | Default | Purpose |
|---|---|---|
| `POLL_INTERVAL_SECONDS` | `300` | How often the background poller re-checks waiting jobs |
| `PORT` | `5000` | Port the dashboard listens on |
| `NTFY_TOPIC` | *(blank)* | ntfy.sh topic for push notifications; blank disables push |
| `NTFY_SERVER` | `https://ntfy.sh` | ntfy server, in case of self-hosting |

`.env` is only read once, at process startup — changing it requires restarting the app.

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then edit .env
python app.py
```
Visit `http://localhost:5000`.

## Deployment

Currently running on an Oracle Cloud Always Free instance (Ubuntu, VM.Standard shape) as a `systemd` service (`gcareers.service`), so it stays up across reboots and restarts automatically if it crashes:

```bash
sudo systemctl status gcareers      # check it's running
sudo journalctl -u gcareers -f      # tail logs
sudo systemctl restart gcareers     # after pulling new code / editing .env
```

Two firewalls have to allow inbound traffic on the app's port: the Oracle **Security List** (console-level) and the instance's own **iptables** rules (OS-level) — both were opened for port 5000 during setup.

The app runs on Flask's built-in development server rather than a production WSGI server (gunicorn, etc.). For a single-user tool with no authentication or public write access beyond adding/removing tracked URLs, that's an acceptable tradeoff; revisit if this ever needs to handle real traffic or sit directly on the open internet long-term.

## Known limitations

- **No authentication.** The dashboard is open to anyone who reaches the IP/port — fine for a personal box, not fine if the URL leaks.
- **Flask dev server.** Not hardened for production traffic (see above); acceptable at current scale.
- **Sequential polling.** `poll_all_waiting_jobs()` checks jobs one at a time in a single background thread — fine for a handful of jobs, would slow down noticeably with dozens.
- **No retry/backoff.** A single failed fetch (network blip, Google rate-limiting) just gets logged as `last_error` and waits for the next scheduled poll; there's no exponential backoff or immediate retry.
- **Scraping-based.** Relies on Google's current HTML structure (`id="apply-action-button"`, the `<base>` tag). No official API is used, so a Google Careers redesign could silently break detection.
- **ntfy.sh topic is unauthenticated.** Anyone who guesses/finds the topic name can read your notifications (or publish fake ones) unless self-hosting a private ntfy server.

## Future ideas

- Swap the Flask dev server for gunicorn + nginx if this ever needs to be reachable more broadly or over HTTPS.
- Add basic auth (or an allowlist) in front of the dashboard.
- Detect Google's HTML structure changing and surface a clear "site format changed" error instead of a silent `apply_url: None`.
- Track additional job metadata (location, posted date) for a quick glance without opening the listing.
- Optional email notification channel alongside ntfy/desktop.
