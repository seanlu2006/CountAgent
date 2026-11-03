# Reports, budget and reconciliation

## Commands

```bash
python3 <skill>/scripts/report.py [YYYY-MM]            # one period (default: current)
python3 <skill>/scripts/quarterly.py [YYYYQn] [--md]   # quarter; --md also saves reports/<YYYY>-Q<n>.md
python3 <skill>/scripts/dashboard.py [--no-open]       # HTML dashboard → reports/dashboard.html
python3 <skill>/scripts/dashboard.py --demo            # made-up data → reports/dashboard-demo.html
```

All of these are standard-library Python 3.8+, with no installs. The dashboard is one offline HTML file: switch periods with ←/→, open the command palette with ⌘K, and use the eating-out toggle.

`YYYY-MM` names a **period**. With `cycle_day: 23`, `2026-10` is Sep 24 – Oct 23. Quarter n = periods 3n-2 … 3n.

## budget.md format

The reports parse these lines. Keep the shapes; the wording can be English or Chinese.

```markdown
Baseline monthly income: 2000

- Monthly savings target: 300
- Quarterly savings target: 900

## Monthly category budget
| Category | Budget |
|----------|--------|
| Dining | 200 |

## One-off extras
| Period | Category | Amount | Note |
|--------|----------|--------|------|
| 2026-11 | Treats | 150 | bonus, spend some |
```

- **Category names must match the ledger exactly.**
- **One-off extras** raise the budget for a single period only. Use them when the user says "I can spend 150 more this month on X". A new category name is fine.
- **Baseline income** is the per-period floor reports use for income. Some people enter income late, or once a quarter; without the floor, net and savings rate look terrible mid-period. Reports always say when the baseline was used, the floor is zero before the ledger starts and pro-rated by days in the period where it starts.
- If the user's real income changes, update the baseline. Never silently raise it to make the numbers look better.

## How to talk about the numbers

- Lead with spent vs budget for the current period, then the one category that matters.
- Give one observation, with a number and a projection: "Dining 212/day vs 180 planned; at this pace the period closes ~1,000 over."
- No lectures and no moralising. The user asked for clear books, not a finance class.
- Investments are not spending. Transfers (card repayments, moving money between own accounts) are neither income nor spending.

## Reconciling with a card statement

When the user shares a statement total (or the bank balance):

1. Sum the ledger's **card** payments for the same statement window (the period, if `cycle_day` matches the closing day).
2. Compare. The difference is usually unlogged small purchases, a subscription that renewed, or entries logged as card that were actually cash.
3. Show the gap, and list candidate missing items if the statement lines are available. **Don't invent entries to close the gap.** Ask, or record a single "unlogged spending (reconciliation)" entry only if the user says to.

## Budget planning conversations

If the user asks for help setting a budget, start from their actual average per category over the last 2–3 periods. Show it next to the proposed numbers, and make sure budget + savings ≤ baseline income. Edit `budget.md` only after they agree. Back up the file first (`budget.md.bak-YYYY-MM-DD`).
