"""Phase 1 and 2 checks. Run: python tests.py"""
import os
import tempfile
from datetime import date, timedelta

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
    for url in ("/", "/invoices", "/invoices/new", "/invoices/1", "/invoices/1/edit"):
        r = c.get(url)
        assert r.status_code == 302 and "/login" in r.headers["Location"], url
    for url in ("/invoices/new", "/invoices/1/paid", "/invoices/1/archive", "/invoices/1/delete"):
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
    for action in ("edit", "paid", "archive", "delete"):
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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
