"""Checks for phases 1 to 6 and Polish 1. Run: python tests.py"""
import os
import tempfile
from datetime import date, timedelta

os.environ.pop("PAYDAY_SEND_TO_CLIENTS", None)  # tests start in test mode
os.environ["PAYDAY_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
import app as payday  # noqa: E402

GOOD = dict(client_name="Kavya Rao", client_email="kavya@example.com", amount="48000.50",
            currency="INR", description="Brand identity", due_date="2026-11-20")


def client(email="owner@example.com"):
    """A test client signed in as `email`, creating the account on first use."""
    c = payday.app.test_client()
    with c.session_transaction() as s:
        s["csrf"] = "t"
    if not rows("SELECT 1 FROM users WHERE email=?", email):
        post(c, "/signup", email=email, password="correct horse")
    else:
        post(c, "/login", email=email, password="correct horse")
    with c.session_transaction() as s:
        s["csrf"] = "t"  # sign-in issues a fresh token; pin it for the helper
    return c


def post(c, url, **data):
    return c.post(url, data={**data, "_csrf": "t"})


def rows(sql, *args):
    db = payday.connect()
    out = db.execute(sql, args).fetchall()
    db.close()
    return out


def test_validation():
    for field, bad in [("amount", "0"), ("amount", "-5"), ("amount", "abc"), ("amount", "NaN"),
                       ("client_email", "not-an-email"), ("due_date", "2026-02-30"), ("client_name", "")]:
        _, errors = payday.parse_invoice({**GOOD, field: bad})
        assert field in errors, (field, bad)
    v, errors = payday.parse_invoice(GOOD)
    assert not errors and v["amount"] == 4800050  # stored in minor units


def test_create_edit_pay():
    c = client()
    assert post(c, "/invoices/new", **{**GOOD, "amount": "0"}).status_code == 400
    assert post(c, "/invoices/new", **GOOD).status_code == 302
    inv = rows("SELECT * FROM invoices")[0]
    assert inv["amount"] == 4800050 and inv["status"] == "open"
    post(c, f"/invoices/{inv['id']}/edit", **{**GOOD, "client_name": "K. Rao"})
    assert rows("SELECT client_name FROM invoices")[0][0] == "K. Rao"
    post(c, f"/invoices/{inv['id']}/paid", paid_on="2026-11-15")
    paid = rows("SELECT * FROM invoices")[0]
    assert paid["status"] == "paid" and paid["paid_on"] == "2026-11-15"
    assert post(c, f"/invoices/{inv['id']}/edit", **GOOD).status_code == 400  # F2


def test_list_splits_overdue_and_sorts():
    c = client()
    today = date.today()
    for name, offset in [("Later", 9), ("Late", -4), ("Soon", 2), ("Later still", 30)]:
        post(c, "/invoices/new", **{**GOOD, "client_name": name, "due_date": (today + timedelta(days=offset)).isoformat()})
    page = c.get("/invoices").get_data(as_text=True)
    order = [page.index(n) for n in ("Late<", "Soon<", "Later<", "Later still<")]
    assert order == sorted(order), order
    assert "K. Rao" not in page  # paid invoices leave the unpaid list
    assert "K. Rao" in c.get("/invoices?tab=paid").get_data(as_text=True)


def test_delete_or_archive():
    c = client()
    a, b = [r["id"] for r in rows("SELECT id FROM invoices WHERE status='open' ORDER BY id LIMIT 2")]
    post(c, f"/invoices/{a}/delete")
    assert not rows("SELECT 1 FROM invoices WHERE id=?", a)
    db = payday.connect()
    db.execute("INSERT INTO reminders (invoice_id, type, scheduled_for, status, created_at) VALUES (?, 'before_due', 'x', 'sent', 'x')", (b,))
    db.commit()
    db.close()
    post(c, f"/invoices/{b}/delete")  # F4: has a sent reminder, so it is archived
    assert rows("SELECT status FROM invoices WHERE id=?", b)[0][0] == "archived"


def test_csrf():
    assert client().post("/invoices/new", data=GOOD).status_code == 400


def anon():
    c = payday.app.test_client()
    with c.session_transaction() as s:
        s["csrf"] = "t"
    return c


def test_signup_and_login():
    c = anon()
    assert post(c, "/signup", email="bad", password="longenough").status_code == 400
    assert post(c, "/signup", email="a@example.com", password="short").status_code == 400
    assert post(c, "/signup", email="A@Example.com ", password="longenough").status_code == 302
    assert c.get("/invoices").status_code == 200  # signed in right after sign-up
    stored = rows("SELECT password_hash FROM users WHERE email='a@example.com'")[0][0]
    assert "longenough" not in stored and stored.count("$") >= 2  # hashed, never plain
    assert post(anon(), "/signup", email="a@example.com", password="longenough").status_code == 400  # duplicate
    other = anon()
    assert post(other, "/login", email="a@example.com", password="wrong").status_code == 400
    assert post(other, "/login", email="nobody@example.com", password="whatever").status_code == 400
    assert c.get("/login").status_code == 302  # already signed in
    assert post(other, "/login", email="a@example.com", password="longenough").status_code == 302


def test_login_required():
    c = anon()
    for url in ("/", "/dashboard", "/settings", "/invoices", "/invoices/new", "/invoices/1", "/invoices/1/edit"):
        r = c.get(url)
        assert r.status_code == 302 and "/login" in r.headers["Location"], url
    for url in ("/invoices/new", "/settings", "/invoices/1/paid", "/invoices/1/archive", "/invoices/1/delete", "/invoices/1/remind", "/invoices/1/reopen"):
        assert "/login" in post(c, url, **GOOD).headers["Location"], url
    assert c.get("/login").status_code == 200 and c.get("/signup").status_code == 200


def test_login_redirect_is_local_only():
    c = anon()
    r = post(c, "/login", email="a@example.com", password="longenough", next="https://evil.example/")
    assert r.headers["Location"].endswith("/invoices")
    c = anon()
    r = post(c, "/login", email="a@example.com", password="longenough", next="//evil.example/")
    assert r.headers["Location"].endswith("/invoices")
    c = anon()
    r = post(c, "/login", email="a@example.com", password="longenough", next="/invoices/new")
    assert r.headers["Location"].endswith("/invoices/new")


def test_logout():
    c = client("a@example.com")
    assert post(c, "/logout").status_code == 302
    assert c.get("/invoices").status_code == 302
    assert c.get("/logout").status_code == 405  # sign-out is POST only


def test_users_see_only_their_own_invoices():
    ann, ben = client("ann@example.com"), client("ben@example.com")
    post(ann, "/invoices/new", **{**GOOD, "client_name": "Ann Secret Client"})
    mine = rows("SELECT id FROM invoices WHERE client_name='Ann Secret Client'")[0][0]
    assert "Ann Secret Client" in ann.get("/invoices").get_data(as_text=True)
    assert "Ann Secret Client" not in ben.get("/invoices").get_data(as_text=True)
    for tab in ("paid", "archived"):
        assert "Ann Secret Client" not in ben.get(f"/invoices?tab={tab}").get_data(as_text=True)
    # Every way to reach, change, or remove someone else's invoice is a 404 and changes nothing.
    assert ben.get(f"/invoices/{mine}").status_code == 404
    assert ben.get(f"/invoices/{mine}/edit").status_code == 404
    for action in ("edit", "paid", "archive", "delete", "remind", "reopen"):
        assert post(ben, f"/invoices/{mine}/{action}", **{**GOOD, "client_name": "Hacked"}).status_code == 404, action
    row = rows("SELECT * FROM invoices WHERE id=?", mine)[0]
    assert row["client_name"] == "Ann Secret Client" and row["status"] == "open"
    assert row["user_id"] == rows("SELECT id FROM users WHERE email='ann@example.com'")[0][0]
    # A new invoice belongs to whoever creates it, whatever the form says.
    post(ben, "/invoices/new", **{**GOOD, "client_name": "Ben Client", "user_id": "1"})
    owner = rows("SELECT u.email FROM invoices i JOIN users u ON u.id=i.user_id WHERE client_name='Ben Client'")[0][0]
    assert owner == "ben@example.com"


def test_first_account_adopts_phase_1_invoices():
    # Fresh database standing in for one created in Phase 1 (invoices, no users).
    import importlib
    import sqlite3
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    db = sqlite3.connect(path)
    db.executescript(open(os.path.join(payday.app.root_path, "schema.sql")).read())
    db.execute("INSERT INTO invoices (client_name, client_email, amount, due_date, created_at, updated_at) "
               "VALUES ('Old Client', 'o@example.com', 100, '2026-12-01', 'x', 'x')")
    db.commit()
    db.close()
    saved = payday.app.config["DB"]
    payday.app.config["DB"] = path
    try:
        c = anon()
        post(c, "/signup", email="first@example.com", password="longenough")
        assert "Old Client" in c.get("/invoices").get_data(as_text=True)
        c2 = anon()
        post(c2, "/signup", email="second@example.com", password="longenough")
        assert "Old Client" not in c2.get("/invoices").get_data(as_text=True)
    finally:
        payday.app.config["DB"] = saved


# --- Phase 3: reminders ---

def _post_invoice(c, due):
    post(c, "/invoices/new", **{**GOOD, "client_name": "Rem", "due_date": due})
    return rows("SELECT MAX(id) FROM invoices")[0][0]


def _reminders(inv_id):
    return {r["type"]: r for r in rows("SELECT * FROM reminders WHERE invoice_id=?", inv_id)}


def test_reminders_created_at_10am_local():
    c = client("rem1@example.com")
    inv = _post_invoice(c, "2099-06-10")
    r = _reminders(inv)
    # Default zone Asia/Kolkata (UTC+5:30): 10:00 local = 04:30 UTC.
    assert r["before_due"]["scheduled_for"] == "2099-06-07T04:30:00+00:00"
    assert r["after_due"]["scheduled_for"] == "2099-06-11T04:30:00+00:00"
    assert all(x["status"] == "pending" and x["sent_at"] is None for x in r.values())
    assert "scheduled, not sent yet" in c.get(f"/invoices/{inv}").get_data(as_text=True)


def test_past_before_due_is_skipped():
    c = client("rem2@example.com")
    inv = _post_invoice(c, "2020-01-10")
    r = _reminders(inv)
    assert "before_due" not in r and "after_due" in r


def test_edit_moves_reminders_without_duplicates():
    c = client("rem3@example.com")
    inv = _post_invoice(c, "2099-06-10")
    post(c, f"/invoices/{inv}/edit", **{**GOOD, "client_name": "Rem", "due_date": "2099-07-01"})
    assert len(rows("SELECT * FROM reminders WHERE invoice_id=?", inv)) == 2
    assert _reminders(inv)["after_due"]["scheduled_for"] == "2099-07-02T04:30:00+00:00"


def test_paid_and_archived_cancel_reminders():
    c = client("rem4@example.com")
    a, b = _post_invoice(c, "2099-08-10"), _post_invoice(c, "2099-08-11")
    post(c, f"/invoices/{a}/paid")
    post(c, f"/invoices/{b}/archive")
    for inv in (a, b):
        assert {x["status"] for x in _reminders(inv).values()} == {"cancelled"}


def test_delete_removes_reminders():
    c = client("rem5@example.com")
    inv = _post_invoice(c, "2099-09-10")
    post(c, f"/invoices/{inv}/delete")
    assert rows("SELECT * FROM reminders WHERE invoice_id=?", inv) == []


# --- Phase 4: sending ---

def _make_due(inv, kind="before_due"):
    """Pretend the reminder's time has arrived. Other tests' leftovers are cancelled so they cannot send."""
    db = payday.connect()
    db.execute("UPDATE reminders SET status='cancelled' WHERE status='pending' AND invoice_id != ?", (inv,))
    db.execute("UPDATE reminders SET scheduled_for='2000-01-01T00:00:00+00:00' WHERE invoice_id=? AND type=?", (inv, kind))
    db.commit()
    db.close()


class _Outbox:
    def __init__(self, fail=False):
        self.msgs, self.fail = [], fail

    def __call__(self, msg):
        if self.fail:
            raise payday.SendError("boom")
        self.msgs.append(msg)


def _with_outbox(outbox):
    saved = payday.smtp_send
    payday.smtp_send = outbox
    return saved


def test_due_reminder_goes_to_owner_only_and_only_once():
    c = client("send1@example.com")
    inv = _post_invoice(c, "2099-06-10")
    box = _Outbox()
    saved = _with_outbox(box)
    try:
        _make_due(inv, "none")  # clears other tests' leftovers; nothing of ours is due yet
        assert payday.send_due_reminders() == (0, 0)
        _make_due(inv)
        assert payday.send_due_reminders() == (1, 0)
        assert payday.send_due_reminders() == (0, 0)  # never twice
    finally:
        payday.smtp_send = saved
    assert len(box.msgs) == 1
    m = box.msgs[0]
    assert m["To"] == "send1@example.com" and "kavya@example.com" in m.get_content()
    r = _reminders(inv)
    assert r["before_due"]["status"] == "sent" and r["before_due"]["sent_at"]
    assert r["after_due"]["status"] == "pending"


def test_paid_invoice_is_not_sent():
    c = client("send2@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    post(c, f"/invoices/{inv}/paid")
    box = _Outbox()
    saved = _with_outbox(box)
    try:
        assert payday.send_due_reminders() == (0, 0)
    finally:
        payday.smtp_send = saved
    assert box.msgs == []


# --- Phase 5: safety ---

T0 = "2001-01-01T00:00:00+00:00"


def _at(hours):
    from datetime import datetime, timedelta
    return (datetime.fromisoformat(T0) + timedelta(hours=hours)).isoformat(timespec="seconds")


def _run(box, at):
    saved = _with_outbox(box)
    try:
        return payday.send_due_reminders(at=at)
    finally:
        payday.smtp_send = saved


def test_failed_send_retries_hourly_then_fails_and_shows_on_dashboard():
    c = client("safe1@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    bad = _Outbox(fail=True)
    assert _run(bad, T0) == (0, 1)
    r = _reminders(inv)["before_due"]
    assert r["status"] == "pending" and r["attempts"] == 1 and r["scheduled_for"] == _at(1) and r["last_error"] == "boom"
    assert "attempt 1 failed, trying again" in c.get(f"/invoices/{inv}").get_data(as_text=True)
    assert "did not send" not in c.get("/dashboard").get_data(as_text=True)  # still retrying, not failed
    assert _run(bad, _at(0.5)) == (0, 0)  # too early: an hour has not passed
    assert _run(bad, _at(1)) == (0, 1) and _reminders(inv)["before_due"]["attempts"] == 2
    assert _run(bad, _at(2)) == (0, 1)  # third and last try
    r = _reminders(inv)["before_due"]
    assert r["status"] == "failed" and r["attempts"] == 3 and r["sent_at"] is None
    assert _run(bad, _at(9)) == (0, 0)  # never a fourth try
    page = c.get("/dashboard").get_data(as_text=True)
    assert "did not send" in page and "Failed after 3 attempts" in page and "boom" in page
    assert "failed after 3 attempts" in c.get(f"/invoices/{inv}").get_data(as_text=True)
    assert "Failed after 3 attempts" not in client("safe2@example.com").get("/dashboard").get_data(as_text=True)  # other users never see it


def test_retry_that_works_sends_once():
    c = client("safe3@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    assert _run(_Outbox(fail=True), T0) == (0, 1)
    good = _Outbox()
    assert _run(good, _at(1)) == (1, 0)
    assert _run(good, _at(2)) == (0, 0)  # run twice, no duplicate
    assert len(good.msgs) == 1
    r = _reminders(inv)["before_due"]
    assert r["status"] == "sent" and r["attempts"] == 2 and r["last_error"] is None


def test_paid_invoice_stops_retries():
    c = client("safe4@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    assert _run(_Outbox(fail=True), T0) == (0, 1)
    post(c, f"/invoices/{inv}/paid")
    assert _run(_Outbox(), _at(1)) == (0, 0)
    assert _reminders(inv)["before_due"]["status"] == "cancelled"


def test_dashboard_totals_and_overdue():
    c = client("safe5@example.com")
    assert "Nothing is waiting" in c.get("/dashboard").get_data(as_text=True)
    post(c, "/invoices/new", **{**GOOD, "client_name": "Late Co", "due_date": "2020-01-10", "amount": "100"})
    post(c, "/invoices/new", **{**GOOD, "client_name": "Fine Co", "due_date": "2099-01-10", "amount": "50"})
    page = c.get("/dashboard").get_data(as_text=True)
    assert "INR 150.00</span> across 2" in page and "INR 100.00</span> is late" in page and "Late Co" in page and "Fine Co" not in page
    assert c.get("/").status_code == 302 and c.get("/").headers["Location"].endswith("/dashboard")
    assert anon().get("/dashboard").status_code == 302


def test_sent_invoice_is_archived_not_deleted():
    c = client("send4@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    saved = _with_outbox(_Outbox())
    try:
        payday.send_due_reminders()
    finally:
        payday.smtp_send = saved
    post(c, f"/invoices/{inv}/delete")
    assert rows("SELECT status FROM invoices WHERE id=?", inv)[0][0] == "archived"


def test_smtp_not_configured_fails_cleanly():
    for k in ("SMTP_HOST",):
        os.environ.pop(k, None)
    try:
        payday.smtp_send(payday.EmailMessage())
        assert False
    except payday.SendError as e:
        assert "SMTP_HOST" in str(e)


def test_real_smtp_conversation():
    """Talk to a tiny local SMTP server to check the real smtplib path."""
    import socketserver
    import threading
    got = []

    class H(socketserver.StreamRequestHandler):
        def handle(self):
            w = lambda t: self.wfile.write((t + "\r\n").encode())
            w("220 test")
            while True:
                line = self.rfile.readline().decode().strip()
                if not line:
                    return
                cmd = line.upper()
                if cmd.startswith("EHLO") or cmd.startswith("HELO"):
                    w("250 ok")
                elif cmd == "DATA":
                    w("354 go")
                    body = []
                    while (l := self.rfile.readline().decode().rstrip("\r\n")) != ".":
                        body.append(l)
                    got.append("\n".join(body))
                    w("250 queued")
                elif cmd == "QUIT":
                    w("221 bye")
                    return
                else:
                    w("250 ok")

    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ.update(SMTP_HOST="127.0.0.1", SMTP_PORT=str(srv.server_address[1]),
                      SMTP_SECURITY="none", SMTP_FROM="payday@example.com")
    try:
        user = {"email": "me@example.com", "name": "Me"}
        inv = {"client_name": "Kavya", "client_email": "k@example.com", "amount": 1000, "currency": "INR",
               "description": "", "due_date": "2099-01-01"}
        payday.smtp_send(payday.build_message(user, inv, "after_due"))
    finally:
        srv.shutdown()
        for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_SECURITY", "SMTP_FROM"):
            os.environ.pop(k, None)
    assert got and "To: me@example.com" in got[0] and "From: payday@example.com" in got[0]


# --- Phase 6: settings, editable text, manual send ---

SETTINGS = dict(name="Prithvi", time_zone="Asia/Kolkata", before_due="", after_due="")


def _sent_text(c, inv, kind="before_due"):
    """Make a reminder due, send it through a fake outbox, and return the message that went out."""
    _make_due(inv, kind)
    box = _Outbox()
    _run(box, T0)
    assert len(box.msgs) == 1
    return box.msgs[0]


def test_settings_validation():
    c = client("set1@example.com")
    assert c.get("/settings").status_code == 200
    for field, bad in [("time_zone", "Mars/Olympus"), ("name", "x" * 101), ("before_due", "Hi {nope}"), ("after_due", "x" * 2001)]:
        r = post(c, "/settings", **{**SETTINGS, field: bad})
        assert r.status_code == 400 and 'aria-invalid="true"' in r.get_data(as_text=True), field
    assert rows("SELECT time_zone FROM users WHERE email='set1@example.com'")[0][0] == "Asia/Kolkata"  # nothing saved


def test_custom_text_name_and_default_reset():
    c = client("set2@example.com")
    assert post(c, "/settings", **{**SETTINGS, "before_due": "Dear {client_name}: {currency} {amount} is due {due_date}."}).status_code == 302
    inv = _post_invoice(c, "2099-06-10")
    msg = _sent_text(c, inv)
    body = msg.get_content()
    assert "Dear Rem: INR 48,000.50 is due 10 Jun 2099." in body and body.rstrip().endswith("Thanks,\nPrithvi")
    assert "friendly reminder" not in body  # custom text replaced the default
    # Clearing the box goes back to the default, and the stored row is removed.
    post(c, "/settings", **SETTINGS)
    assert rows("SELECT * FROM templates WHERE user_id=(SELECT id FROM users WHERE email='set2@example.com')") == []
    assert "Dear {client_name}" not in c.get("/settings").get_data(as_text=True)
    inv2 = _post_invoice(c, "2099-06-11")
    assert "friendly reminder" in _sent_text(c, inv2).get_content()


def test_client_name_cannot_inject_variables():
    assert payday.fill("Hi {client_name}, {amount}", "{amount}", "1", "INR", "d") == "Hi {amount}, 1"


def test_templates_are_per_user():
    ann, ben = client("set3@example.com"), client("set4@example.com")
    post(ann, "/settings", **{**SETTINGS, "before_due": "Ann's private wording"})
    assert "Ann's private wording" not in ben.get("/settings").get_data(as_text=True)
    assert "friendly reminder" in _sent_text(ben, _post_invoice(ben, "2099-06-12")).get_content()


def test_time_zone_change_moves_pending_reminders():
    c = client("set5@example.com")
    inv = _post_invoice(c, "2099-06-10")
    assert _reminders(inv)["before_due"]["scheduled_for"] == "2099-06-07T04:30:00+00:00"
    assert post(c, "/settings", **{**SETTINGS, "time_zone": "America/New_York"}).status_code == 302
    # 10:00 in New York in June is 14:00 UTC.
    assert _reminders(inv)["before_due"]["scheduled_for"] == "2099-06-07T14:00:00+00:00"
    assert _reminders(inv)["after_due"]["scheduled_for"] == "2099-06-11T14:00:00+00:00"


def test_manual_send_is_logged_and_leaves_scheduled_reminders_alone():
    c = client("man1@example.com")
    inv = _post_invoice(c, "2099-06-10")
    box = _Outbox()
    saved = _with_outbox(box)
    try:
        assert post(c, f"/invoices/{inv}/remind").status_code == 302
        post(c, f"/invoices/{inv}/remind")  # a second manual send is allowed
    finally:
        payday.smtp_send = saved
    assert len(box.msgs) == 2 and "friendly reminder" in box.msgs[0].get_content()  # due in the future: the "before" text
    manual = rows("SELECT * FROM reminders WHERE invoice_id=? AND type='manual'", inv)
    assert len(manual) == 2 and all(m["status"] == "sent" and m["sent_at"] for m in manual)
    r = _reminders(inv)
    assert r["before_due"]["status"] == "pending" and r["after_due"]["status"] == "pending"
    assert "Manual" in c.get(f"/invoices/{inv}").get_data(as_text=True)


def test_manual_send_uses_after_text_when_overdue_and_reports_failure():
    c = client("man2@example.com")
    inv = _post_invoice(c, "2020-01-10")
    saved = _with_outbox(_Outbox())
    try:
        post(c, f"/invoices/{inv}/remind")
    finally:
        payday.smtp_send = saved
    sent = rows("SELECT * FROM reminders WHERE invoice_id=? AND type='manual'", inv)[0]
    assert sent["status"] == "sent"
    saved = _with_outbox(_Outbox(fail=True))
    try:
        page = c.get(post(c, f"/invoices/{inv}/remind").headers["Location"]).get_data(as_text=True)
    finally:
        payday.smtp_send = saved
    assert "did not send: boom" in page
    failed = rows("SELECT * FROM reminders WHERE invoice_id=? AND type='manual' ORDER BY id DESC", inv)[0]
    assert failed["status"] == "pending" and failed["attempts"] == 1  # retried like any other


def test_manual_send_rules():
    c = client("man3@example.com")
    inv = _post_invoice(c, "2099-06-10")
    post(c, f"/invoices/{inv}/paid")
    assert post(c, f"/invoices/{inv}/remind").status_code == 400  # paid invoices get no reminders
    other = client("man4@example.com")
    inv2 = _post_invoice(other, "2099-06-10")
    assert post(c, f"/invoices/{inv2}/remind").status_code == 404  # someone else's invoice
    assert rows("SELECT * FROM reminders WHERE invoice_id=? AND type='manual'", inv2) == []


# --- Polish 1: scheduler, late-reminder guard, reopen ---

def test_scheduler_runs_every_round_and_survives_a_failed_run():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database is locked")

    saved = payday.send_due_reminders
    payday.send_due_reminders = flaky
    try:
        payday.scheduler_loop(0, rounds=3)
    finally:
        payday.send_due_reminders = saved
    assert len(calls) == 3  # the first run failed and the loop carried on


def test_scheduler_sends_each_reminder_once():
    c = client("pol1@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    box = _Outbox()
    saved, real = _with_outbox(box), payday.send_due_reminders
    payday.send_due_reminders = lambda: real(at=T0)
    try:
        payday.scheduler_loop(0, rounds=3)
    finally:
        payday.send_due_reminders, payday.smtp_send = real, saved
    assert len(box.msgs) == 1


def test_before_due_is_not_sent_once_the_due_date_has_passed():
    c = client("pol2@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)  # the job "was down": the before-due time passed long ago
    box = _Outbox()
    # 11 Jun 05:30 in Kolkata: the due date (10 Jun) is over. The after-due reminder (11 Jun 10:00) is not yet due.
    assert _run(box, "2099-06-11T00:00:00+00:00") == (0, 0)
    r = _reminders(inv)
    assert box.msgs == [] and r["before_due"]["status"] == "cancelled" and "due date" in r["before_due"]["last_error"]
    assert r["after_due"]["status"] == "pending"
    assert "Note: Not sent" in c.get(f"/invoices/{inv}").get_data(as_text=True)


def test_before_due_still_sends_on_the_due_date():
    c = client("pol3@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    assert _run(_Outbox(), "2099-06-10T12:00:00+00:00") == (1, 0)  # 17:30 on the due date in Kolkata
    assert _reminders(inv)["before_due"]["status"] == "sent"


def test_reopen_paid_invoice_restores_reminders():
    c = client("pol4@example.com")
    inv = _post_invoice(c, "2099-06-10")
    post(c, f"/invoices/{inv}/paid")
    assert _reminders(inv)["before_due"]["status"] == "cancelled"
    assert "Reopen invoice" in c.get(f"/invoices/{inv}").get_data(as_text=True)
    assert post(c, f"/invoices/{inv}/reopen").status_code == 302
    row = rows("SELECT * FROM invoices WHERE id=?", inv)[0]
    assert row["status"] == "open" and row["paid_on"] is None
    assert _reminders(inv)["before_due"]["status"] == "pending" and _reminders(inv)["after_due"]["status"] == "pending"
    assert post(c, f"/invoices/{inv}/reopen").status_code == 400  # already open
    assert post(c, f"/invoices/{inv}/edit", **{**GOOD, "client_name": "Edited"}).status_code == 302  # editable again


def test_reopen_archived_keeps_sent_reminders_sent():
    c = client("pol5@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    _run(_Outbox(), T0)
    post(c, f"/invoices/{inv}/archive")
    post(c, f"/invoices/{inv}/reopen")
    assert rows("SELECT status FROM invoices WHERE id=?", inv)[0][0] == "open"
    r = _reminders(inv)
    assert r["before_due"]["status"] == "sent" and r["after_due"]["status"] == "pending"
    assert _run(_Outbox(), T0) == (0, 0)  # the sent one is never sent again


def test_reopen_is_private():
    ann, ben = client("pol6@example.com"), client("pol7@example.com")
    inv = _post_invoice(ann, "2099-06-10")
    post(ann, f"/invoices/{inv}/paid")
    assert post(ben, f"/invoices/{inv}/reopen").status_code == 404
    assert rows("SELECT status FROM invoices WHERE id=?", inv)[0][0] == "paid"


# --- Polish 2: sending to clients is opt-in ---

def test_test_mode_is_the_default_and_message_has_date_and_id():
    c = client("live1@example.com")
    msg = _sent_text(c, _post_invoice(c, "2099-06-10"))
    assert msg["To"] == "live1@example.com" and msg["Subject"].startswith("[PayDay test]")
    assert msg["Date"] and msg["Message-ID"] and msg["Reply-To"] is None
    assert "Test mode" in c.get("/settings").get_data(as_text=True)


def test_live_mode_sends_to_the_client_with_reply_to_and_no_test_marks():
    os.environ["PAYDAY_SEND_TO_CLIENTS"] = "1"
    try:
        c = client("live2@example.com")
        post(c, "/settings", **{**SETTINGS, "name": "Prithvi"})
        inv = _post_invoice(c, "2099-06-10")
        msg = _sent_text(c, inv)
        body = msg.get_content()
        assert msg["To"] == "kavya@example.com"  # the invoice's client, not the owner
        assert msg["Reply-To"] == "live2@example.com"
        assert "[PayDay" not in msg["Subject"] and "PayDay test" not in body and "would be sent" not in body
        assert "Hi Rem," in body and body.rstrip().endswith("Thanks,\nPrithvi")
        assert "Reminders go to your clients" in c.get("/settings").get_data(as_text=True)
        box = _Outbox()
        saved = _with_outbox(box)
        try:
            page = c.get(post(c, f"/invoices/{inv}/remind").headers["Location"]).get_data(as_text=True)
        finally:
            payday.smtp_send = saved
        assert "Reminder sent to kavya@example.com" in page and box.msgs[0]["To"] == "kavya@example.com"
    finally:
        os.environ.pop("PAYDAY_SEND_TO_CLIENTS", None)


def test_only_the_value_1_turns_live_mode_on():
    for v in ("0", "true", "yes", ""):
        os.environ["PAYDAY_SEND_TO_CLIENTS"] = v
        assert payday.live_mode() is False, v
    os.environ.pop("PAYDAY_SEND_TO_CLIENTS", None)


# --- Polish 3: one log row per send attempt ---

def _attempts(inv):
    return rows("SELECT a.*, r.type FROM reminder_attempts a JOIN reminders r ON r.id=a.reminder_id "
                "WHERE r.invoice_id=? ORDER BY a.id", inv)


def test_every_attempt_is_logged_with_time_address_and_result():
    c = client("log1@example.com")
    inv = _post_invoice(c, "2099-06-10")
    assert _attempts(inv) == []
    _make_due(inv)
    bad = _Outbox(fail=True)
    _run(bad, T0)
    _run(bad, _at(1))
    _run(_Outbox(), _at(2))
    log = _attempts(inv)
    assert [a["result"] for a in log] == ["failed", "failed", "sent"]
    assert [a["attempted_at"] for a in log] == [_at(0), _at(1), _at(2)]
    assert [a["error"] for a in log] == ["boom", "boom", None]
    assert {a["type"] for a in log} == {"before_due"}
    assert log[2]["to_address"] == "log1@example.com"  # test mode: the owner's own address
    page = c.get(f"/invoices/{inv}").get_data(as_text=True)
    assert "Send history" in page and page.count("Before due date: ") == 3 and "sent to log1@example.com" in page
    assert "<small>boom</small>" in page


def test_manual_send_and_a_sent_reminder_are_logged_once_each():
    c = client("log2@example.com")
    inv = _post_invoice(c, "2099-06-10")
    saved = _with_outbox(_Outbox())
    try:
        post(c, f"/invoices/{inv}/remind")
    finally:
        payday.smtp_send = saved
    log = _attempts(inv)
    assert len(log) == 1 and log[0]["type"] == "manual" and log[0]["result"] == "sent"
    _make_due(inv)
    _run(_Outbox(), T0)
    _run(_Outbox(), _at(1))  # the sent reminder is not sent, so not logged, again
    assert len(_attempts(inv)) == 2


def test_nothing_is_logged_for_a_skipped_or_cancelled_reminder():
    c = client("log3@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    _run(_Outbox(), "2099-06-11T00:00:00+00:00")  # late guard cancels the before-due reminder
    assert _attempts(inv) == []
    assert "Send history" not in c.get(f"/invoices/{inv}").get_data(as_text=True)


def test_history_goes_away_with_the_invoice():
    c = client("log4@example.com")
    inv = _post_invoice(c, "2099-06-10")
    _make_due(inv)
    _run(_Outbox(fail=True), T0)  # a failed attempt only, so the invoice can still be deleted
    assert len(_attempts(inv)) == 1
    post(c, f"/invoices/{inv}/delete")
    assert rows("SELECT * FROM invoices WHERE id=?", inv) == [] and _attempts(inv) == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
