# Bank and card statement import

Use it when the user hands over a statement exported as CSV. It catches up on weeks of spending at once, and it reconciles what they logged by hand against what the bank actually charged.

```bash
python3 <skill>/scripts/import_bank.py <statement.csv> --payment card --dry-run
```

## Workflow

1. **Always dry-run first.** Read the preview before writing anything.
2. **Pick `--payment`.** Use `card` for a credit-card statement and `bank` for a current or checking account, written in the ledger's language (`信用卡` / `銀行`).
3. **Check the preview:**
   - `Columns:` should show a date, a description, and either an amount or debit/credit columns. If it's wrong, re-run with `--map date=…,amount=…,desc=…` (or `debit=…,credit=…`).
   - **Signs.** Purchases should come out as `expense`. If they show as `income` (the script warns when most rows do), it's a statement that lists purchases as positive numbers: add `--flip`.
   - **Dates.** If the script stops because dates like `03/04/2026` could go either way, ask the user whether their bank writes day or month first. Then use `--dates dmy` or `--dates mdy`.
4. **Possible duplicates.** Rows whose date and amount match an entry the user logged by hand are **skipped and listed**. Show the list, and ask about each one: is it the same purchase? Usually yes. If the bank row is better (the right amount, say), offer to correct the manual entry rather than importing a second one.
5. **Write**: the same command without `--dry-run`.
6. **Review categories.** Categories are guessed from the description and land in Other when nothing matches. Look over the rows noted `[bank import: check category]`, propose fixes in one message, and apply what the user confirms. Remove the bracketed marker once a row is confirmed, but keep `bank:<fingerprint>`.

## What it handles

- **Layouts:** a single signed amount, or separate debit and credit columns (`Paid out` / `Paid in`). Account-info lines above the header. Comma, semicolon or tab separators. UTF-8 or Windows encodings.
- **Number formats:** `1,234.56` / `1.234,56` / `(12.00)` / `12.00-` / `12.00 DR`.
- **Date formats:** `2026-11-03`, `03/11/2026`, `11/03/2026`, `03.11.2026`, `03 Nov 2026`, `Nov 3, 2026`, and ISO with a time.
- **Transfers:** card repayments ("payment thank you", "autopay"), moves to and from savings, and cash withdrawals become **transfers**, so they are not counted as spending.
- **Salary:** salary and payroll lines become income in the salary category.
- **Re-imports:** importing the same file (or an overlapping statement) twice adds nothing. Identical purchases on the same day (two coffees) are kept apart.

## Card and bank statements together

A card purchase appears on the card statement. The card repayment then appears on the bank statement. Import both, and the repayment comes in as a transfer, so nothing is counted twice. If a repayment ever lands as `expense`, change it to transfer.
