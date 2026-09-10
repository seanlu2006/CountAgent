#!/usr/bin/env python3
"""CountAgant 月報:彙總某月份的收支。

用法:
    python3 scripts/report.py            # 當月
    python3 scripts/report.py 2026-05    # 指定月份
"""
import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "data" / "ledger.csv"


def fmt(n):
    return f"{n:,.0f}"


def main():
    month = sys.argv[1] if len(sys.argv) > 1 else date.today().strftime("%Y-%m")

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
            if not r.get("date", "").startswith(month):
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

    print(f"📊 {month} 月報")
    print("=" * 32)
    print(f"筆數    : {rows}")
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
