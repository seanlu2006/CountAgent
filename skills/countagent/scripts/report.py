#!/usr/bin/env python3
"""CountAgent 月報:彙總某帳期的收支(帳期依 config.json 的 cycle_day)。

用法:
    python3 scripts/report.py            # 當月
    python3 scripts/report.py 2026-05    # 指定月份
"""
import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from period import CUTOFF, baseline_income, first_date, floor_for, period_of, period_range  # noqa: E402

from cfg import BUDGET, LEDGER  # noqa: E402
from i18n import CW, amount, fmt, kind, other, t, warn_bad  # noqa: E402


def main():
    month = sys.argv[1] if len(sys.argv) > 1 else period_of(date.today())

    if not LEDGER.exists():
        print(t("no_ledger", path=LEDGER))
        return

    income = 0
    expense = 0
    by_cat = defaultdict(float)
    invest = 0
    rows = 0

    with LEDGER.open(encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))
    bad = []
    for r in all_rows:
        if not r.get("date") or period_of(r["date"]) != month:
            continue
        amt = amount(r.get("amount"))
        if amt is None:
            bad.append(r.get("id") or "?")
            continue
        k = kind(r.get("type", ""))
        if k == "income":
            income += amt
        elif k == "expense":
            expense += amt
            by_cat[r.get("category") or other()] += amt
        elif k == "investment":
            invest += amt
        rows += 1

    a, b = period_range(month)
    print(t("m_title" if CUTOFF else "m_title_cal", ym=month, a=f"{a:%m/%d}", b=f"{b:%m/%d}"))
    print("=" * 32)
    print(t("m_rows", n=rows))
    warn_bad(bad)
    floor = floor_for(month, baseline_income(BUDGET), first_date(all_rows))
    if income < floor:
        print(t("m_income_floor", floor=fmt(floor), actual=fmt(income)))
        income = floor
    else:
        print(t("m_income", v=fmt(income)))
    print(t("m_expense", v=fmt(expense)))
    print(t("m_net", v=fmt(income - expense)))
    if invest:
        print(t("m_invest", v=fmt(invest)))

    if by_cat:
        print(t("m_cats"))
        for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
            pct = amt / expense * 100 if expense else 0
            bar = "█" * int(pct / 5)
            print(f"  {cat:<{CW}} {fmt(amt):>10}  {pct:4.0f}% {bar}")


if __name__ == "__main__":
    main()
