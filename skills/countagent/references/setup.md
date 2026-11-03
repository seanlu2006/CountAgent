# First-time setup

Run this once, when `cfg.py --where` says **NOT DONE**. Takes about a minute. Ask everything in **one** message, offer the defaults, and accept "just use defaults".

## 1. Ask (one message)

| Question | Default | Flag |
|---|---|---|
| Language for reports: English or 繁體中文? | follow the user's language | `--language en` / `zh-TW` |
| Currency code and symbol? | USD, `$` (TWD → `NT$`, EUR → `€`, GBP → `£`, JPY → `¥`) | `--currency` `--symbol` |
| Do you want "a month" to follow your credit-card statement? If so, what day does it close? | no → calendar months | `--cycle-day 23` (0 = calendar month) |
| How do you usually pay? | card | `--payment` |
| Where should the data live? | `~/CountAgent/data` | `--data-dir` |
| Logging from your phone? (see `inbox.md`) | not now | `--inbox <path>` |

Don't ask about category names; the defaults are fine and the user can rename later.

## 2. Run

```bash
python3 <skill>/scripts/setup.py --language en --currency USD --symbol '$' --cycle-day 0 --payment card
```

It creates the data folder with `ledger.csv` (header only), `config.json`, `budget.md`, `profile.md`, `categories.md` and `inbox_archive.txt`. It never overwrites an existing file. A non-default `--data-dir` is remembered in `~/.countagent/config.json`, so every script finds it from any folder.

Advanced: the env var `COUNTAGENT_DATA=/path` overrides everything (useful for a test ledger).

## 3. Fill in the two files that matter

Walk through these with the user — conversationally, not as a form. Skipping is fine; the ledger works without them.
While a file is still exactly the template, the reports **ignore it** (its numbers are made up). Once edited it counts as real — so replace or delete every sample row when you fill it in, and delete the "Template —" note.

- **`budget.md`**: the monthly budget per category and the income they can count on each month (`Baseline monthly income: N`). Without it, reports still work but show no budget comparison.
- **`profile.md`**: habits in plain words. Most useful: recurring charges (mark each **auto** or **manual**), how income arrives, personal shorthand ("mum" transfers are income, etc.).

The templates contain made-up numbers. Replace them, or delete the rows.

## 4. Confirm

```bash
python3 <skill>/scripts/cfg.py --where
```

should say `setup : done`. Tell the user they can now just type spending in one line, for example "lunch 12".

## Changing settings later

Edit `<data_dir>/config.json`:

```json
{
  "language": "en",
  "currency": "USD",
  "currency_symbol": "$",
  "cycle_day": 0,
  "default_payment": "card",
  "inbox": "",
  "eat_out_category": "Dining",
  "groceries_category": "Groceries",
  "reports_dir": ""
}
```

- `reports_dir` (optional, not written by setup): empty or absent means `<data_dir>/../reports`.
- `decimals` (optional): digits shown in reports. Defaults to 0 for currencies without minor units (TWD, JPY, KRW…) and 2 otherwise.
- If you rename a category, rename it in `budget.md` too. Renaming the eat-out or groceries category also means updating the two `*_category` keys.

## Moving an existing ledger in

If the user has a spreadsheet already: map its columns onto `id,date,type,amount,category,item,payment,note,receipt` (amounts positive, type expense/income/investment/transfer), show the first 5 converted rows, and append only after they confirm. Number the ids from 1.
