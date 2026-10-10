#!/usr/bin/env python3
"""CountAgent 月報:彙總某月份的收支。月 = 信用卡帳期(上月 24 ~ 本月 23)。

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
from period import baseline_income, period_of, period_range  # noqa: E402

LEDGER = Path(__file__).resolve().parent.parent / "data" / "ledger.csv"


def fmt(n):
    return f"{n:,.0f}"


def main():
    month = sys.argv[1] if len(sys.argv) > 1 else period_of(date.today())

    if not LEDGER.exists():
        print(f"找不到帳本:{LEDGER}")
        return

    income = 0
    expense = 0
    by_cat = defaultdict(float)
    invest = 0
    rows = 0

    with LEDGER.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("date") or period_of(r["date"]) != month:
                continue
            try:
                amt = float(r["amount"])
            except (ValueError, KeyError):
                continue
            t = r.get("type", "")
            if t == "收入":
                income += amt
            elif t == "支出":
                expense += amt
                by_cat[r.get("category", "其他")] += amt
            elif t == "投資":
                invest += amt
            rows += 1

    a, b = period_range(month)
    print(f"📊 {month} 月報  ({a:%m/%d} ~ {b:%m/%d},依信用卡帳期)")
    print("=" * 32)
    print(f"筆數    : {rows}")
    floor = baseline_income(LEDGER.parent / "budget.md")
    if income < floor:
        print(f"總收入  : {fmt(floor)}   (實際入帳 {fmt(income)},以保底計;收入季末補)")
        income = floor
    else:
        print(f"總收入  : {fmt(income)}")
    print(f"總支出  : {fmt(expense)}")
    print(f"結餘    : {fmt(income - expense)}")
    if invest:
        print(f"定期投資: {fmt(invest)}")

    if by_cat:
        print("\n支出分類(由大到小):")
        for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
            pct = amt / expense * 100 if expense else 0
            bar = "█" * int(pct / 5)
            print(f"  {cat:<6} {fmt(amt):>10}  {pct:4.0f}% {bar}")


if __name__ == "__main__":
    main()
