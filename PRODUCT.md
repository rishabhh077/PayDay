# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Flask + SQLite, server-rendered pages. Chosen by the user. Runs locally with no external services.

## Users

A freelancer with 5 to 30 open invoices at a time, who invoices clients by email or PDF. They use PayDay on a laptop at their desk while doing admin work; phone is secondary.

Not the user for now: agencies with teams, accountants, or companies that need payment processing.

## Product Purpose

Freelancers chase late payments by hand, forget which invoices are unpaid, or feel awkward chasing them. PayDay stores each invoice (client, amount, due date, client email), sends one polite reminder before the due date and one after, and shows what is still unpaid.

Success for the first release: the reminder job never sends a duplicate, marking an invoice paid stops its reminders, a failed send is visible, and two accounts cannot see each other's invoices. Beyond that: 5 real freelancers use it for 2 weeks and say it saved them time.

## Operating Context

The freelancer creates invoices elsewhere (email, PDF) and enters the details here. Adding an invoice must take under one minute. The main working view is the list of unpaid invoices sorted by due date, with overdue ones separated.

## Capabilities and Constraints

- Invoice fields: client name, client email, amount (positive, stored in minor units), currency (default INR), due date, short description.
- Statuses: open, paid, archived. "Overdue" means open and past the due date.
- Reminders: "before due" (3 days before) and "after due" (1 day after), at 10:00 in the freelancer's time zone, never sent twice. Email only.
- No payment collection, no invoice or PDF generation, no teams, no SMS or WhatsApp, no bank detection.
- Built in six phases: data, accounts, reminders, sending, safety, polish. Source: the PRD, "Late Invoice PRD.md".
- Undecided: email provider, CSV import, whether default currency is per user.

## Brand Commitments

The name is PayDay.

## Evidence on Hand

No customers, testimonials, logo, or brand assets exist. None may be invented.

## Product Principles

1. Never embarrass the freelancer: no duplicate or wrong reminders.
2. What is unpaid, and what is overdue, is answerable at a glance.
3. Entering an invoice is faster than updating a spreadsheet.
4. Each phase ends with something that runs and can be checked.
