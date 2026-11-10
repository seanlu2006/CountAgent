#!/usr/bin/env python3
"""Compare a bank or card statement CSV with the ledger, without changing anything.

Usage:
    python3 reconcile.py statement.csv --payment card
Options:
    --payment NAME     the ledger's payment method for this statement (default: from settings)
    --from / --to      limit to these dates, YYYY-MM-DD (default: the statement's first and last row)
    --window N         days apart that still count as the same purchase (default 3)
    --flip --dates --map   same meaning as in import_bank.py

The script does the arithmetic. Deciding what a difference means is the agent's job.
Standard library only.
"""
import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfg import LEDGER, S  # noqa: E402
from i18n import amount, fmt, kind, t  # noqa: E402
from import_bank import ledger_rows, load_statement, pair_up, row_date  # noqa: E402

COMPARED = ("expense", "investment")  # money that leaves and is recorded as leaving


def same_method(a, b) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def reconcile(txs, rows, payment: str, window: int, start=None, end=None) -> dict:
    """The comparison itself → totals and row lists. gap == only_statement − only_ledger, always."""
    in_range = [x for x in txs if (not start or x["date"] >= start) and (not end or x["date"] <= end)]
    spend = [x for x in in_range if x["kind"] == "expense"]
    dates = [x["date"] for x in in_range]
    first = start or (min(dates) if dates else None)
    last = end or (max(dates) if dates else None)

    pool = []
    if first and last:
        lo, hi = first - timedelta(days=window), last + timedelta(days=window)
        pool = [r for r in rows if kind(r.get("type", "")) in COMPARED and row_date(r) and lo <= row_date(r) <= hi]

    matched, used = {}, set()

    def claim(indexes, candidates, win):
        found = pair_up([spend[i] for i in indexes], candidates, win)
        for n, (row, gap) in found.items():
            matched[indexes[n]] = (row, gap)
            used.add(id(row))

    # 1. Rows imported from a statement carry its fingerprint: that is certain.
    by_fp = {}
    for r in pool:
        m = re.search(r"bank:(\w+)", r.get("note") or "")
        if m:
            by_fp[m.group(1)] = r
    for i, x in enumerate(spend):
        r = by_fp.get(x["fp"])
        if r is not None and id(r) not in used:
            matched[i] = (r, 0)
            used.add(id(r))

    # 2. Same payment method first, 3. then anything else, which is worth flagging.
    for same in (True, False):
        left = [i for i in range(len(spend)) if i not in matched]
        claim(left, [r for r in pool if id(r) not in used and same_method(r.get("payment"), payment) == same], window)

    only_statement = [x for i, x in enumerate(spend) if i not in matched]
    only_ledger = [r for r in pool
                   if id(r) not in used and same_method(r.get("payment"), payment) and first <= row_date(r) <= last]
    pairs = [(spend[i], *matched[i]) for i in sorted(matched)]

    matched_total = round(sum(x["amt"] for x, _, _ in pairs), 2)
    only_statement_total = round(sum(x["amt"] for x in only_statement), 2)
    only_ledger_total = round(sum(amount(r.get("amount")) or 0 for r in only_ledger), 2)
    money_in = [x for x in in_range if x["kind"] == "income"]
    return {
        "first": first, "last": last, "spend": spend, "pairs": pairs,
        "only_statement": only_statement, "only_ledger": only_ledger,
        "statement_total": round(matched_total + only_statement_total, 2),
        "ledger_total": round(matched_total + only_ledger_total, 2),
        "only_statement_total": only_statement_total, "only_ledger_total": only_ledger_total,
        "gap": round(only_statement_total - only_ledger_total, 2),
        "transfers": sum(1 for x in in_range if x["kind"] == "transfer"),
        "money_in": len(money_in), "money_in_total": round(sum(x["amt"] for x in money_in), 2),
    }


def parse_day(v, flag):
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        sys.exit(f"❌ {flag} must be YYYY-MM-DD, got: {v}")


def main():
    ap = argparse.ArgumentParser(description="Compare a statement CSV with the ledger. Changes nothing.")
    ap.add_argument("file")
    ap.add_argument("--payment", default=S.get("default_payment", "card"))
    ap.add_argument("--from", dest="start", default="", help="first date, YYYY-MM-DD")
    ap.add_argument("--to", dest="end", default="", help="last date, YYYY-MM-DD")
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("--flip", action="store_true", help="positive amounts are spending")
    ap.add_argument("--dates", choices=["dmy", "mdy", "ymd"])
    ap.add_argument("--map", default="")
    args = ap.parse_args()
    if args.window < 0:
        sys.exit("❌ --window can't be negative.")

    path = Path(args.file).expanduser()
    if not path.exists():
        sys.exit(f"❌ File not found: {path}")
    if not LEDGER.exists():
        sys.exit("❌ " + t("no_ledger", path=LEDGER))
    txs, _, _, bad = load_statement(path, args.map, args.dates or "", args.flip)
    rows = ledger_rows()
    res = reconcile(txs, rows, args.payment, args.window, parse_day(args.start, "--from"), parse_day(args.end, "--to"))

    if bad:
        print(t("r_unreadable", n=len(bad), first=bad[0]))
    methods = sorted({(r.get("payment") or "").strip() for r in rows if (r.get("payment") or "").strip()})
    if rows and not any(same_method(m, args.payment) for m in methods):
        print(t("r_no_payment", p=args.payment, seen=t("sep").join(methods)))
    if res["money_in"] > len(txs) / 2:
        print(t("r_flip"))
    if not res["spend"]:
        print(t("r_no_spend"))
        return

    print(t("r_title", a=res["first"], b=res["last"], p=args.payment, w=args.window))
    print("=" * 50)
    print(t("r_stmt", v=fmt(res["statement_total"]), n=len(res["spend"])))
    print(t("r_ledger", v=fmt(res["ledger_total"]), n=len(res["pairs"]) + len(res["only_ledger"])))
    print(t("r_gap", v=fmt(res["gap"])))
    if not res["only_statement"] and not res["only_ledger"]:
        print(t("r_ok"))

    far = sum(1 for _, _, gap in res["pairs"] if gap)
    other_method = [(x, r) for x, r, _ in res["pairs"] if not same_method(r.get("payment"), args.payment)]
    print(t("r_matched", n=len(res["pairs"]), far=far, pay=len(other_method)))
    if other_method:
        print(t("r_pay"))
        for x, r in other_method:
            print(f"   #{r.get('id')} {r.get('date')} {fmt(x['amt']):>10}  {r.get('item')} ({r.get('payment')})")
    if res["only_statement"]:
        print(t("r_only_stmt", n=len(res["only_statement"]), v=fmt(res["only_statement_total"])))
        for x in res["only_statement"]:
            print(f"   {x['date'].isoformat()} {fmt(x['amt']):>10}  {x['desc'][:50]}")
    if res["only_ledger"]:
        print(t("r_only_ledger", n=len(res["only_ledger"]), v=fmt(res["only_ledger_total"])))
        for r in res["only_ledger"]:
            near = t("r_near_end") if row_date(r) > res["last"] - timedelta(days=args.window) else ""
            print(f"   #{r.get('id')} {r.get('date')} {fmt(amount(r.get('amount')) or 0):>10}  {r.get('item')}{near}")
    if res["transfers"] or res["money_in"]:
        print(t("r_excluded", t=res["transfers"], i=res["money_in"], v=fmt(res["money_in_total"])))


if __name__ == "__main__":
    main()
