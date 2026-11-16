-- PayDay data model (PRD section 8). Phase 1 uses invoices only;
-- users, reminders and templates are created now and used from Phase 2 on.
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  time_zone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),  -- owner; filled from Phase 2
  client_name TEXT NOT NULL,
  client_email TEXT NOT NULL,
  amount INTEGER NOT NULL CHECK (amount > 0),  -- whole minor units, e.g. paise
  currency TEXT NOT NULL DEFAULT 'INR',
  description TEXT NOT NULL DEFAULT '',
  due_date TEXT NOT NULL,  -- YYYY-MM-DD
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'paid', 'archived')),
  paid_on TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('before_due', 'after_due', 'manual')),
  scheduled_for TEXT NOT NULL,
  sent_at TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'cancelled')),
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TEXT NOT NULL
);
-- R3: one scheduled reminder per invoice and type; manual sends may repeat.
CREATE UNIQUE INDEX IF NOT EXISTS reminders_one_per_type
  ON reminders (invoice_id, type) WHERE type != 'manual';

CREATE TABLE IF NOT EXISTS templates (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  type TEXT NOT NULL CHECK (type IN ('before_due', 'after_due')),
  body TEXT NOT NULL,
  UNIQUE (user_id, type)
);

-- One row per send attempt (R5): when, to whom, and whether it worked.
CREATE TABLE IF NOT EXISTS reminder_attempts (
  id INTEGER PRIMARY KEY,
  reminder_id INTEGER NOT NULL REFERENCES reminders(id) ON DELETE CASCADE,
  attempted_at TEXT NOT NULL,
  to_address TEXT,
  result TEXT NOT NULL CHECK (result IN ('sent', 'failed')),
  error TEXT
);
CREATE INDEX IF NOT EXISTS reminder_attempts_by_reminder ON reminder_attempts (reminder_id);
