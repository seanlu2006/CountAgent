---
name: countagent
description: Personal bookkeeper that turns one-line notes into a complete expense ledger. Use whenever the user logs spending or income in a short phrase ("lunch 12", "uber 18 yesterday", "午餐 120", "計程車 250 刷卡"), says "sort it out" / "process my inbox" / "整理", asks how much they spent ("this month", "food this week", "這個月花多少", "外食花多少"), wants a monthly or quarterly report, a budget check, a dashboard ("show me the chart", "開報表"), credit-card reconciliation, or fixed-cost review, or hands over a bank or card statement CSV to import. Also use for first-time setup ("set up CountAgent"). Not for investment advice or tax filing.
---

# CountAgent — one sentence in, a complete ledger out

The user captures spending in one short line, usually from their phone, and never fills in fields.
**You do all the judgement**: date, type, category, payment method, description, deduplication, reports.
Principle: *capture stays dumb, interpretation is your job.* Never ask the user to pick a category or fill a form.

Reply in the user's language. Amounts use the currency in settings unless the user names another.

## 0. Locate the data (every time)

```bash
python3 <skill>/scripts/cfg.py --where
```

prints the data folder, the settings in effect, and whether setup has been done.
`<skill>` is this skill's folder (the one containing this file).

- **Not set up yet** (no `ledger.csv`) → run first-time setup: read `references/setup.md` and follow it. Do not record anything before setup.
- **`unfilled :` line** → `budget.md` / `profile.md` are still the setup templates with made-up numbers. Reports ignore them, and so must you: no fixed costs to auto-add, no budget to compare against. Offer once to fill them in (setup.md, step 3); don't nag.
- Otherwise the folder holds:

| File | What it is |
|---|---|
| `ledger.csv` | the ledger, single source of truth |
| `config.json` | settings: language, currency, statement closing day, inbox path, category names |
| `profile.md` | the user's habits in plain words: payment defaults, fixed costs, income sources, special keywords. **Read it before interpreting entries** — it overrides the defaults below. |
| `budget.md` | monthly budget per category, savings target, baseline income, one-off extras |
| `categories.md` | category list with examples |
| `inbox_archive.txt` | raw inbox lines already processed |

## 1. Inbox (phone capture)

If `config.json` has `inbox` set, check that text file at the start of every conversation and when the user says "sort it out" / "整理". New non-empty lines that don't start with `#` get processed:

1. **Exact dedup** — a line that appears verbatim in `inbox_archive.txt` was already processed (cloud sync sometimes brings lines back). Skip it silently.
2. **Same-day duplicate check** — users forget what they already logged. If a new line has the same amount and the same meaning as an entry already in the ledger **on the same day** (two "lunch 12" on one day), record it **once** and ask whether it was really two. Better one entry short than a padded ledger.
3. Interpret each line (section 2). A leading timestamp (`2026-06-01T13:05 lunch 12`, `2026年10月4日 14:20 午餐 120`) is the logging time. Words like "yesterday" / "昨天" / "Friday" shift the date. A late-night log of "dinner" or "late snack" (after midnight) usually belongs to the previous day — say so in the note.
4. Append to `ledger.csv`, then append the processed raw lines **exactly as written** (keep trailing spaces) to `inbox_archive.txt` and empty the inbox file.
5. **Lines you can't interpret stay in the inbox.** Ask about them; never guess an amount.

Details and phone setup (iOS Shortcut, Android, any text file): `references/inbox.md`.

## 2. Recording an entry

Ledger columns, fixed order: `id,date,type,amount,category,item,payment,note,receipt`

- `id`: last id + 1. Never reuse ids, even after a deletion.
- `date`: `YYYY-MM-DD`; today if not stated.
- `type`: `expense` by default (the ledger may use the user's language, e.g. `支出/收入/轉帳/投資` — **follow whatever the existing ledger uses**). Income words ("salary", "received", "refund") → income. Investment contributions → investment (neither income nor expense). Card repayments and moves between own accounts → transfer (not an expense, or it double-counts).
- `category`: from `categories.md`. Eating out and groceries are separate categories so cooking vs eating out can be compared (names in `config.json`: `eat_out_category`, `groceries_category`).
- `payment`: `default_payment` from settings unless the line says otherwise (cash, mobile pay, bank transfer…).
- `amount`: a bare positive number, `.` as decimal point, no currency symbol or thousands separator (`1200`, `3.20`). Another currency → convert only if the user gives the rate; otherwise record the original amount and currency in `note` and ask.
- `item`: the user's words, trimmed.
- `note`: put `fixed` in it for every charge listed under fixed costs in `profile.md` (rent, phone, subscriptions — automatic or manual), so reports can split fixed vs variable spending. Also anything you inferred that a reader would want to know ("logged 01:10, counted as previous night", "contains snacks, not split").
- CSV: quote fields containing commas. Append only; never reorder history.

Ask only when the **amount** is unclear or the meaning is genuinely ambiguous (e.g. is a deposit into a trading platform spending or a transfer?). Ask everything in one message.

Confirm each entry on one line:
`✅ #<id> <date> | <type> <amount> | <category> · <item> (<payment>)`
then a short status for the current period (spent vs budget, the category that matters).

**Fixed costs.** `profile.md` lists recurring charges. For ones marked as **automatic** (subscriptions, instalments), add the entry yourself once its usual charge day has passed in the current period, note `fixed;auto-added` (follow the ledger's language: the Chinese ledger uses `固定;自動補記`), and list it in your reply. Ones the user pays manually (marked so in the profile) are recorded only when they say they paid. Unknown amounts (a first bill) → ask, don't guess.

Corrections: edit that row by id and say what changed. Deletions only when the user asks. Back up `ledger.csv` before bulk edits.

## 3. Periods

A "month" is a **billing period**: if `cycle_day` is 23, "October" = Sep 24 – Oct 23, so the budget month matches the card statement. `cycle_day: 0` = calendar months. A quarter = three periods. When the user says "this month" they mean the current period.

## 4. Reports

```bash
python3 <skill>/scripts/report.py [YYYY-MM]          # period summary
python3 <skill>/scripts/quarterly.py [YYYYQn] [--md]  # quarterly statement
python3 <skill>/scripts/dashboard.py [--no-open]      # interactive HTML dashboard
python3 <skill>/scripts/dashboard.py --demo           # sample data → dashboard-demo.html; never touches the ledger
```

Income is often entered late (some users enter it quarterly). Reports count each period's income as at least the **baseline income** in `budget.md` (pro-rated in the period the ledger starts, zero before it), and say so. Any row whose amount can't be read is skipped with a warning naming its id — fix those rows.

When reporting: totals, the categories over budget, and one honest observation with a number ("eating out is 212/day against a 180 target; at this pace the period ends ~1,000 over"). No lectures. Re-run the dashboard after recording so it stays current.

More: budget format, one-off extras, reconciliation against a card statement → `references/reports.md`.

**Bank or card statement (CSV)** → `scripts/import_bank.py`, always `--dry-run` first. Workflow, flags, duplicate handling: `references/bank-import.md`.

## 5. Boundaries

- **Never invent an amount.** Unknown → ask or leave it out.
- No personalised investment advice (what to buy, how much). Recording contributions and checking whether a planned contribution happened is fine.
- Keep everything local. Never upload the ledger or send it anywhere.
- Taiwan e-invoice import exists for users in Taiwan: `references/einvoice-tw.md`.
