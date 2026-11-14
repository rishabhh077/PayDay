# PayDay

A late-invoice reminder tool for freelancers. It stores each invoice, will send a polite reminder before and after the due date, and shows what is still unpaid.

## Status

Built in six phases. **Phase 1 (data) is done:** database tables, and adding, editing, listing, paying, archiving, and deleting invoices. Accounts, reminders, and email arrive in Phases 2 to 6.

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
