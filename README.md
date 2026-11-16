# PayDay

A late-invoice reminder tool for freelancers. It stores each invoice, will send a polite reminder before and after the due date, and shows what is still unpaid.

## Status

Built in six phases. **All six phases are done.** Phase 1 added the database and the invoice pages. Phase 2 added accounts: sign up, sign in, and sign out, with each user seeing only their own invoices. Phase 3 added reminders: records are created and logged automatically. Phase 4 sends them as real email over SMTP, to your own address only. Phase 5 added safety: failed sends retry, and failures show on a dashboard. Phase 6 added polish: a settings page, editable reminder text, a manual "Send reminder now", and a Docker setup.

Notes on reminders:

- Saving an open invoice creates two reminder records: 3 days before the due date and 1 day after, both at 10:00 in the user's time zone.
- Changing the due date moves the pending reminders. Marking an invoice paid or archiving it cancels them. Deleting it removes them.
- A "before due" reminder whose time has already passed is not created. An "after due" reminder is always created, so an invoice entered already overdue gets one as soon as sending exists.
- Every create, reschedule and cancel is written to the log, and each invoice page lists its reminders. 

Notes on sending:

- Every message goes to the account owner's own address, never the client's. It is marked "[PayDay test]" and names the client it would have gone to.
- Set these environment variables: `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (defaults to `SMTP_USER`), `SMTP_SECURITY` (`starttls` by default, or `ssl`, or `none`). For Gmail use `smtp.gmail.com` and an app password.
- Send due reminders by running `.venv/bin/python app.py send-reminders`. Run it every few minutes (cron or launchd). It does not run by itself.
- A reminder is sent only if it is pending, its time has come and the invoice is still open. Each one is claimed before sending, so overlapping runs cannot send it twice.
- A failed send is tried again an hour later, up to 3 attempts in all. After the third failure the reminder is marked `failed`, with the error shown on the invoice page and on the dashboard. Marking the invoice paid or archiving it stops any retries.
- The run prints how many attempts failed. It exits with an error code when any did, so cron can alert you.
- The dashboard (the page you land on after signing in) lists reminders that failed for good, the overdue invoices, and your unpaid and overdue totals.
- With no SMTP settings, every due reminder fails with "SMTP is not configured" and ends up `failed` after 3 attempts. Set the variables before the first run.

Notes on accounts:

- Every page needs sign-in except sign up and sign in.
- Someone else's invoice returns "not found", the same as one that does not exist.
- Passwords are stored hashed, and must be at least 8 characters.
- Invoices entered in Phase 1 have no owner. The first account created takes them over.
- Dates use the signed-in user's time zone (default Asia/Kolkata).

Notes on settings and reminder text:

- **Settings** holds your name (it signs each reminder), your time zone (reminders go out at 10:00 there), and the two reminder texts. Changing the time zone moves the pending reminders to 10:00 in the new zone.
- Each text can use `{client_name}`, `{amount}`, `{currency}` and `{due_date}`. Any other `{word}` is refused when you save. Below each box you see how it reads for an example invoice. Clear a box to go back to the default wording.
- **Send reminder now** (on an open invoice) sends one straight away, logged like the others, and shown in the invoice's reminder list as "Manual". It uses the "before" wording until the due date has passed, and the "after" wording from then on. A failed manual send is retried like any other.
- While PayDay is in test mode, every email, manual ones included, goes to your own address and not the client's.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open http://localhost:5055. The database is one file, `payday.db`, created on first run.

## Test it

```bash
.venv/bin/python tests.py
```

## Deploy it

PayDay needs one process for the website and one job that sends reminders. The database is a single SQLite file, so run one copy of the app.

```bash
docker build -t payday .
docker run -d --name payday -p 8000:8000 -v payday-data:/data \
  -e SECRET_KEY="$(openssl rand -hex 32)" -e PAYDAY_HTTPS=1 \
  -e SMTP_HOST=smtp.gmail.com -e SMTP_USER=you@gmail.com -e SMTP_PASSWORD=your-app-password \
  payday
```

- Keep `SECRET_KEY` the same between runs, or everyone is signed out on each restart. `PAYDAY_HTTPS=1` marks the session cookie secure; only set it when the site is served over https (put a reverse proxy such as Caddy or nginx in front for that).
- The database lives in the `payday-data` volume.
- Send reminders on a schedule, for example with this cron line (every 10 minutes):

```
*/10 * * * * docker exec payday python app.py send-reminders
```

Without Docker: `pip install -r requirements.txt`, then `gunicorn --bind 0.0.0.0:8000 --workers 2 app:app`.
