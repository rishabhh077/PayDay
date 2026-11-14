"""PayDay, Phase 1: invoices. No accounts and no email yet."""
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from markupsafe import Markup

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


def today():
    # shortcut: server's local date; becomes the user's time zone in Phase 2.
    return date.today().isoformat()


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


# --- routes -----------------------------------------------------------------

def get_invoice(invoice_id):
    row = get_db().execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
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
    rows = [dict(r) for r in db.execute(f"SELECT * FROM invoices WHERE status = ? ORDER BY {order}", (status,))]
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
                    "description=?, due_date=?, updated_at=? WHERE id=?", (*vals, ts, invoice_id))
            else:
                invoice_id = db.execute(
                    "INSERT INTO invoices (client_name, client_email, amount, currency, description, "
                    "due_date, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)", (*vals, ts, ts)).lastrowid
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
    inv["days"] = (date.fromisoformat(inv["due_date"]) - date.today()).days
    return render_template("invoice.html", inv=inv, today=today())


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
    db.execute("UPDATE invoices SET status='paid', paid_on=?, updated_at=? WHERE id=?", (paid_on, now(), invoice_id))
    db.commit()
    flash("Marked as paid.")
    return redirect(url_for("invoice", invoice_id=invoice_id))


@app.post("/invoices/<int:invoice_id>/archive")
def archive(invoice_id):
    get_invoice(invoice_id)
    db = get_db()
    db.execute("UPDATE invoices SET status='archived', updated_at=? WHERE id=?", (now(), invoice_id))
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
    db.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
    db.commit()
    flash("Invoice deleted.")
    return redirect(url_for("invoices"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5055)))
