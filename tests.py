"""Phase 1 checks. Run: python tests.py"""
import os
import tempfile
from datetime import date, timedelta

os.environ["PAYDAY_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
import app as payday  # noqa: E402

GOOD = dict(client_name="Kavya Rao", client_email="kavya@example.com", amount="48000.50",
            currency="INR", description="Brand identity", due_date="2026-11-20")


def client():
    c = payday.app.test_client()
    with c.session_transaction() as s:
        s["csrf"] = "t"
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
    assert payday.app.test_client().post("/invoices/new", data=GOOD).status_code == 400


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
