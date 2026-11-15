# PayDay

A late-invoice reminder tool for freelancers. It stores each invoice, will send a polite reminder before and after the due date, and shows what is still unpaid.

## Status

Built in six phases. **Phases 1 and 2 are done.** Phase 1 added the database and the invoice pages. Phase 2 added accounts: sign up, sign in, and sign out, with each user seeing only their own invoices. Reminders and email arrive in Phases 3 to 6.

Notes on accounts:

- Every page needs sign-in except sign up and sign in.
- Someone else's invoice returns "not found", the same as one that does not exist.
- Passwords are stored hashed, and must be at least 8 characters.
- Invoices entered in Phase 1 have no owner. The first account created takes them over.
- Dates use the signed-in user's time zone (default Asia/Kolkata).

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

