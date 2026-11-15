"""PayDay, Phase 4: sending. Due reminders go out over SMTP, to the account owner's own address only."""
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import sys
from email.message import EmailMessage
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["DB"] = os.environ.get("PAYDAY_DB", os.path.join(app.root_path, "payday.db"))


def _secret_key():
    path = os.path.join(app.root_path, ".secret_key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read()


app.secret_key = os.environ.get("SECRET_KEY") or _secret_key()
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
log = logging.getLogger("payday.reminders")
log.setLevel(logging.INFO)
if not log.handlers:
    log.addHandler(logging.StreamHandler())


# --- database ---------------------------------------------------------------

def connect():
    db = sqlite3.connect(app.config["DB"])
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = connect()
    with open(os.path.join(app.root_path, "schema.sql")) as f:
        db.executescript(f.read())
    db.close()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def user_tz():
    name = g.user["time_zone"] if g.get("user") else "Asia/Kolkata"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def today():
    """Today's date in the signed-in user's time zone."""
    return datetime.now(user_tz()).date().isoformat()


# --- CSRF -------------------------------------------------------------------

@app.before_request
def check_csrf():
    if request.method == "POST":
        sent, kept = request.form.get("_csrf", ""), session.get("csrf", "")
        if not kept or not secrets.compare_digest(sent, kept):
            abort(400)


def csrf_field():
    token = session.setdefault("csrf", secrets.token_hex(16))
    return Markup('<input type="hidden" name="_csrf" value="%s">') % token


app.jinja_env.globals["csrf_field"] = csrf_field


# --- accounts ---------------------------------------------------------------

PUBLIC = {"login", "signup", "static"}
MIN_PASSWORD = 8


@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if not g.user:
            session.pop("uid", None)  # account no longer exists
    if g.user is None and request.endpoint not in PUBLIC:
        # Secure by default: every route needs a signed-in user unless listed in PUBLIC.
        if request.endpoint is None:
            return None  # 404s fall through
        target = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("login", next=target))


def safe_next(target):
    """Only follow redirects to a path on this site."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("invoices")


def sign_in(user_id):
    session.clear()  # new session on every sign-in, with a fresh CSRF token
    session["uid"] = user_id


# Checked against when the email is unknown, so the response time does not reveal which emails exist.
DUMMY_HASH = generate_password_hash("not-a-real-password")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("invoices"))
    errors, v = {}, {}
    if request.method == "POST":
        v = {"name": request.form.get("name", "").strip(),
             "email": request.form.get("email", "").strip().lower()}
        password = request.form.get("password", "")
        if not EMAIL.match(v["email"]):
            errors["email"] = "Enter an email address, like name@example.com."
        if len(password) < MIN_PASSWORD:
            errors["password"] = f"Use at least {MIN_PASSWORD} characters."
        if not errors:
            db = get_db()
            try:
                user_id = db.execute(
                    "INSERT INTO users (email, password_hash, name, created_at) VALUES (?,?,?,?)",
                    (v["email"], generate_password_hash(password), v["name"], now())).lastrowid
            except sqlite3.IntegrityError:
                errors["email"] = "That email already has an account. Sign in instead."
            else:
                # Invoices entered in Phase 1 have no owner; the first account adopts them.
                if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1:
                    db.execute("UPDATE invoices SET user_id = ? WHERE user_id IS NULL", (user_id,))
                db.commit()
                sign_in(user_id)
                flash("Welcome to PayDay.")
                return redirect(url_for("invoices"))
    return render_template("signup.html", v=v, errors=errors), 400 if errors else 200


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("invoices"))
    error, email = None, ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        ok = check_password_hash(user["password_hash"] if user else DUMMY_HASH, request.form.get("password", ""))
        if user and ok:
            sign_in(user["id"])
            return redirect(safe_next(request.form.get("next") or request.args.get("next")))
        error = "That email and password do not match."
    return render_template("login.html", email=email, error=error,
                           next=request.form.get("next") or request.args.get("next") or ""), 400 if error else 200


@app.post("/logout")
def logout():
    session.clear()
    flash("Signed out.")
    return redirect(url_for("login"))


# --- formatting -------------------------------------------------------------

@app.template_filter("money")
def money(minor):
    return f"{Decimal(minor) / 100:,.2f}"


@app.template_filter("d")
def fmt_date(iso, fmt="%d %b %Y"):
    return date.fromisoformat(iso).strftime(fmt)


# --- validation (F6) --------------------------------------------------------

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIELDS = ("client_name", "client_email", "amount", "currency", "description", "due_date")


def parse_invoice(form):
    """Return (clean values, {field: error message})."""
    v = {k: form.get(k, "").strip() for k in FIELDS}
    errors = {}
    if not v["client_name"]:
        errors["client_name"] = "Enter the client's name."
    if not EMAIL.match(v["client_email"]):
        errors["client_email"] = "Enter an email address, like name@example.com."
    try:
        minor = int((Decimal(v["amount"]) * 100).to_integral_value())
        if minor <= 0:
            raise InvalidOperation
        v["amount"] = minor
    except (InvalidOperation, ValueError):
        errors["amount"] = "Enter an amount greater than zero, like 12500 or 12500.50."
    v["currency"] = (v["currency"] or "INR").upper()
    if not re.fullmatch(r"[A-Z]{3}", v["currency"]):
        errors["currency"] = "Use a three-letter currency code, like INR."
    try:
        date.fromisoformat(v["due_date"])
    except ValueError:
        errors["due_date"] = "Choose a due date."
    return v, errors


# --- reminders (Phase 3) ----------------------------------------------------

REMINDER_DAYS = {"before_due": -3, "after_due": 1}  # days relative to the due date
REMINDER_HOUR = 10  # 10:00 in the freelancer's time zone


def schedule_for(due_date, kind, tz):
    """UTC timestamp for a reminder, or None if that moment has already passed (before-due only)."""
    day = date.fromisoformat(due_date) + timedelta(days=REMINDER_DAYS[kind])
    when = datetime.combine(day, time(REMINDER_HOUR), tzinfo=tz).astimezone(timezone.utc)
    if kind == "before_due" and when <= datetime.now(timezone.utc):
        return None  # never send a "before due" reminder after the fact
    return when.isoformat(timespec="seconds")


def sync_reminders(db, invoice_id, due_date, tz):
    """Make the reminder rows match the invoice's due date. Sent reminders are never touched."""
    ts = now()
    for kind in REMINDER_DAYS:
        want = schedule_for(due_date, kind, tz)
        row = db.execute("SELECT * FROM reminders WHERE invoice_id=? AND type=?", (invoice_id, kind)).fetchone()
        if row and row["status"] == "sent":
            continue
        if row is None:
            if want:
                db.execute("INSERT INTO reminders (invoice_id, type, scheduled_for, created_at) VALUES (?,?,?,?)",
                           (invoice_id, kind, want, ts))
                log.info("reminder created: invoice=%s type=%s scheduled_for=%s", invoice_id, kind, want)
        elif want:
            if row["status"] != "pending" or row["scheduled_for"] != want:
                db.execute("UPDATE reminders SET scheduled_for=?, status='pending', attempts=0, last_error=NULL WHERE id=?",
                           (want, row["id"]))
                log.info("reminder rescheduled: invoice=%s type=%s scheduled_for=%s", invoice_id, kind, want)
        elif row["status"] == "pending":
            db.execute("UPDATE reminders SET status='cancelled' WHERE id=?", (row["id"],))
            log.info("reminder cancelled (time passed): invoice=%s type=%s", invoice_id, kind)


def cancel_reminders(db, invoice_id):
    """Stop all pending reminders, used when an invoice is paid or archived."""
    n = db.execute("UPDATE reminders SET status='cancelled' WHERE invoice_id=? AND status='pending'", (invoice_id,)).rowcount
    if n:
        log.info("reminders cancelled: invoice=%s count=%s", invoice_id, n)


@app.template_filter("local")
def fmt_local(iso, fmt="%d %b %Y, %H:%M"):
    return datetime.fromisoformat(iso).astimezone(user_tz()).strftime(fmt)


# --- sending (Phase 4) ------------------------------------------------------
# Configured by environment variables: SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD,
# SMTP_FROM (defaults to SMTP_USER), SMTP_SECURITY ("starttls" default, "ssl", or "none").
# Until the product is trusted, every message goes to the account owner's own address,
# never to the client. The intended client address is shown inside the message.

class SendError(Exception):
    pass


def money_text(minor):
    return f"{Decimal(minor) / 100:,.2f}"


def build_message(user, inv, kind):
    due = date.fromisoformat(inv["due_date"]).strftime("%d %b %Y")
    amount = f"{inv['currency']} {money_text(inv['amount'])}"
    what = f" for {inv['description']}" if inv["description"] else ""
    if kind == "before_due":
        subject = f"Reminder: invoice of {amount} is due on {due}"
        text = (f"Hi {inv['client_name']},\n\nA friendly reminder that my invoice of {amount}{what} "
                f"is due on {due}.\n\nIf it is already on its way, thank you, and please ignore this note.\n")
    else:
        subject = f"Invoice of {amount} was due on {due}"
        text = (f"Hi {inv['client_name']},\n\nMy invoice of {amount}{what} was due on {due} and I "
                f"have not yet seen the payment.\n\nCould you let me know when to expect it? If you have "
                f"already paid, thank you, and please ignore this note.\n")
    sign = user["name"] or user["email"]
    msg = EmailMessage()
    msg["To"] = user["email"]  # own address only
    msg["Subject"] = f"[PayDay test] {subject}"
    msg.set_content(f"PayDay test copy. This would be sent to {inv['client_name']} <{inv['client_email']}>. "
                    f"It was sent to you only.\n\n----\n\n{text}\nThanks,\n{sign}\n")
    return msg


def smtp_send(msg):
    host = os.environ.get("SMTP_HOST")
    if not host:
        raise SendError("SMTP is not configured (set SMTP_HOST).")
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")
    if not sender:
        raise SendError("Set SMTP_FROM or SMTP_USER.")
    msg["From"] = sender
    mode = os.environ.get("SMTP_SECURITY", "starttls").lower()
    port = int(os.environ.get("SMTP_PORT", 465 if mode == "ssl" else 587))
    try:
        cls = smtplib.SMTP_SSL if mode == "ssl" else smtplib.SMTP
        with cls(host, port, timeout=20) as s:
            if mode == "starttls":
                s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise SendError(f"{type(e).__name__}: {e}") from e


def send_due_reminders(db=None):
    """Send every pending reminder whose time has come. Returns (sent, failed)."""
    own = db is None
    db = db or connect()
    sent = failed = 0
    try:
        due = db.execute(
            "SELECT r.id, r.type, r.attempts, r.invoice_id FROM reminders r JOIN invoices i ON i.id=r.invoice_id "
            "WHERE r.status='pending' AND i.status='open' AND r.scheduled_for <= ? ORDER BY r.scheduled_for", (now(),)).fetchall()
        for r in due:
            # Claim the row first, so two overlapping runs cannot both send it.
            claimed = db.execute("UPDATE reminders SET attempts=attempts+1 WHERE id=? AND status='pending' AND attempts=?",
                                 (r["id"], r["attempts"])).rowcount
            db.commit()
            if not claimed:
                continue
            inv = db.execute("SELECT * FROM invoices WHERE id=?", (r["invoice_id"],)).fetchone()
            user = db.execute("SELECT * FROM users WHERE id=?", (inv["user_id"],)).fetchone()
            try:
                if not user:
                    raise SendError("Invoice has no owner.")
                smtp_send(build_message(user, inv, r["type"]))
            except Exception as e:  # noqa: BLE001 - any failure must be recorded, never crash the run
                db.execute("UPDATE reminders SET status='failed', last_error=? WHERE id=?", (str(e)[:500], r["id"]))
                db.commit()
                log.error("reminder failed: invoice=%s type=%s error=%s", r["invoice_id"], r["type"], e)
                failed += 1
                continue
            db.execute("UPDATE reminders SET status='sent', sent_at=?, last_error=NULL WHERE id=?", (now(), r["id"]))
            db.commit()
            log.info("reminder sent: invoice=%s type=%s to=%s", r["invoice_id"], r["type"], user["email"])
            sent += 1
    finally:
        if own:
            db.close()
    return sent, failed


# --- routes -----------------------------------------------------------------

def get_invoice(invoice_id):
    # Scoped to the signed-in user; someone else's invoice is a 404, same as a missing one.
    row = get_db().execute("SELECT * FROM invoices WHERE id = ? AND user_id = ?", (invoice_id, g.user["id"])).fetchone()
    if not row:
        abort(404)
    return row


def sum_by_currency(rows):
    totals = {}
    for r in rows:
        totals[r["currency"]] = totals.get(r["currency"], 0) + r["amount"]
    return totals


@app.route("/")
def home():
    return redirect(url_for("invoices"))


@app.route("/invoices")
def invoices():
    tab = request.args.get("tab", "unpaid")
    if tab not in ("unpaid", "paid", "archived"):
        abort(404)
    db, t = get_db(), today()
    status = "open" if tab == "unpaid" else tab
    order = "due_date, id" if tab == "unpaid" else "COALESCE(paid_on, updated_at) DESC"
    rows = [dict(r) for r in db.execute(f"SELECT * FROM invoices WHERE user_id = ? AND status = ? ORDER BY {order}", (g.user["id"], status))]
    for r in rows:
        r["days"] = (date.fromisoformat(r["due_date"]) - date.fromisoformat(t)).days
    overdue = [r for r in rows if r["days"] < 0] if tab == "unpaid" else []
    upcoming = [r for r in rows if r["days"] >= 0] if tab == "unpaid" else rows
    return render_template(
        "invoices.html", tab=tab, today=t, overdue=overdue, upcoming=upcoming,
        unpaid_total=sum_by_currency(rows), overdue_total=sum_by_currency(overdue), count=len(rows),
    )


@app.route("/invoices/new", methods=["GET", "POST"])
@app.route("/invoices/<int:invoice_id>/edit", methods=["GET", "POST"])
def invoice_form(invoice_id=None):
    inv = get_invoice(invoice_id) if invoice_id else None
    if inv and inv["status"] != "open":
        abort(400)  # F2: editable only until paid
    errors = {}
    if request.method == "POST":
        v, errors = parse_invoice(request.form)
        if not errors:
            db, ts = get_db(), now()
            vals = [v[k] for k in FIELDS]
            if inv:
                db.execute(
                    "UPDATE invoices SET client_name=?, client_email=?, amount=?, currency=?, "
                    "description=?, due_date=?, updated_at=? WHERE id=? AND user_id=?", (*vals, ts, invoice_id, g.user["id"]))
            else:
                invoice_id = db.execute(
                    "INSERT INTO invoices (client_name, client_email, amount, currency, description, "
                    "due_date, user_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (*vals, g.user["id"], ts, ts)).lastrowid
            sync_reminders(db, invoice_id, v["due_date"], user_tz())
            db.commit()
            flash("Invoice saved.")
            return redirect(url_for("invoice", invoice_id=invoice_id))
        values = request.form
    elif inv:
        values = {**dict(inv), "amount": f"{Decimal(inv['amount']) / 100:.2f}"}
    else:
        values = {"currency": "INR"}
    return render_template("form.html", inv=inv, v=values, errors=errors), 400 if errors else 200


@app.route("/invoices/<int:invoice_id>")
def invoice(invoice_id):
    inv = dict(get_invoice(invoice_id))
    inv["days"] = (date.fromisoformat(inv["due_date"]) - date.fromisoformat(today())).days
    reminders = get_db().execute(
        "SELECT * FROM reminders WHERE invoice_id=? ORDER BY scheduled_for", (invoice_id,)).fetchall()
    return render_template("invoice.html", inv=inv, today=today(), reminders=reminders)


@app.post("/invoices/<int:invoice_id>/paid")
def mark_paid(invoice_id):
    inv = get_invoice(invoice_id)
    if inv["status"] != "open":
        abort(400)
    paid_on = request.form.get("paid_on") or today()
    try:
        date.fromisoformat(paid_on)
    except ValueError:
        flash("Choose the date the invoice was paid.")
        return redirect(url_for("invoice", invoice_id=invoice_id))
    db = get_db()
    db.execute("UPDATE invoices SET status='paid', paid_on=?, updated_at=? WHERE id=? AND user_id=?", (paid_on, now(), invoice_id, g.user["id"]))
    cancel_reminders(db, invoice_id)
    db.commit()
    flash("Marked as paid.")
    return redirect(url_for("invoice", invoice_id=invoice_id))


@app.post("/invoices/<int:invoice_id>/archive")
def archive(invoice_id):
    get_invoice(invoice_id)
    db = get_db()
    db.execute("UPDATE invoices SET status='archived', updated_at=? WHERE id=? AND user_id=?", (now(), invoice_id, g.user["id"]))
    cancel_reminders(db, invoice_id)
    db.commit()
    flash("Invoice archived.")
    return redirect(url_for("invoices", tab="archived"))


@app.post("/invoices/<int:invoice_id>/delete")
def delete(invoice_id):
    get_invoice(invoice_id)
    db = get_db()
    # F4: an invoice with sent reminders is archived, never deleted.
    sent = db.execute("SELECT COUNT(*) FROM reminders WHERE invoice_id=? AND status='sent'", (invoice_id,)).fetchone()[0]
    if sent:
        return archive(invoice_id)
    db.execute("DELETE FROM invoices WHERE id=? AND user_id=?", (invoice_id, g.user["id"]))
    db.commit()
    flash("Invoice deleted.")
    return redirect(url_for("invoices"))


init_db()

if __name__ == "__main__":
    if sys.argv[1:] == ["send-reminders"]:
        # Run this every few minutes (cron, launchd, or a loop).
        s, f = send_due_reminders()
        print(f"sent {s}, failed {f}")
        sys.exit(1 if f else 0)
    app.run(debug=True, port=int(os.environ.get("PORT", 5055)))
