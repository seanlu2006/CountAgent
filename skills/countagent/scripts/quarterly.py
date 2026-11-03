#!/usr/bin/env python3
"""季度財報:收支、儲蓄目標、預算vs實際、固定/變動、定期投資。

用法:
    python3 scripts/quarterly.py             # 當季,印在終端機
    python3 scripts/quarterly.py 2026Q3       # 指定季度
    python3 scripts/quarterly.py 2026Q3 --md  # 另存 reports/2026-Q3.md
"""
import csv
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from period import CUTOFF, baseline_income, budget_extras, first_date, floor_for, period_of, period_range  # noqa: E402

import budget  # noqa: E402
from cfg import BUDGET, LEDGER, REPORTS  # noqa: E402
from i18n import CW, amount, fmt, is_fixed, kind, other, t, warn_bad  # noqa: E402
QUARTERS = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}


def parse_quarter(arg):
    if arg and re.match(r"\d{4}Q[1-4]", arg.upper()):
        y, q = arg.upper().split("Q")
        return int(y), int(q)
    y, m = map(int, period_of(date.today()).split("-"))
    return y, (m - 1) // 3 + 1


def load_budget():
    b = budget.load(BUDGET)
    return {"save_month": b["save_month"], "save_quarter": b["save_quarter"], "cats": b["cats"]}


def collect(year, q):
    months = [f"{year}-{m:02d}" for m in QUARTERS[q]]
    d = {
        "months": months,
        "m_income": defaultdict(float), "m_expense": defaultdict(float),
        "m_invest": defaultdict(float), "cats": defaultdict(float),
        "fixed": 0.0, "variable": 0.0,
    }
    with LEDGER.open(encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))
    d["first"] = first_date(all_rows)
    bad = []
    for r in all_rows:
        if not r.get("date"):
            continue
        ym = period_of(r["date"])  # 月 = 信用卡帳期
        if ym not in months:
            continue
        amt = amount(r.get("amount"))
        if amt is None:
            bad.append(r.get("id") or "?")
            continue
        k = kind(r.get("type"))
        if k == "income":
            d["m_income"][ym] += amt
        elif k == "expense":
            d["m_expense"][ym] += amt
            d["cats"][r.get("category") or other()] += amt
            if is_fixed(r.get("note")):
                d["fixed"] += amt
            else:
                d["variable"] += amt
        elif k == "investment":
            d["m_invest"][ym] += amt
    warn_bad(bad)
    return d


def build_lines(year, q, d, bud):
    months = d["months"]
    # 收入季末才補:每期至少以保底計(還沒到的期不算)
    floor = baseline_income(BUDGET)
    today_p = period_of(date.today())
    for m in months:
        f = floor_for(m, floor, d["first"])
        if m <= today_p and f and d["m_income"].get(m, 0) < f:
            d["m_income"][m] = f
            d.setdefault("floored", []).append(m)
    income = sum(d["m_income"].values())
    expense = sum(d["m_expense"].values())
    invest = sum(d["m_invest"].values())
    net = income - expense
    rate = (net / income * 100) if income else 0

    today = date.today()
    elapsed = sum(1 for m in months if m <= period_of(today)) or 3
    q_start, q_end = period_range(months[0])[0], period_range(months[-1])[1]

    L = []
    L.append(t("q_title" if CUTOFF else "q_title_cal", y=year, q=q, a=f"{q_start:%m/%d}", b=f"{q_end:%m/%d}", e=elapsed))
    L.append("=" * 50)
    L.append(t("q_income", v=fmt(income)) + (t("q_floored", ms=t("sep").join(d["floored"])) if d.get("floored") else ""))
    L.append(t("q_expense", v=fmt(expense)))
    L.append(t("q_net", v=fmt(net), r=rate))
    # 收入已包含要拿去投資的錢,所以投資扣款已經在淨結餘裡,不能再加一次
    L.append(t("q_invest", v=fmt(invest)))
    L.append(t("q_left", v=fmt(net - invest)))

    # 儲蓄目標
    tgt_q = bud["save_quarter"] or bud["save_month"] * 3
    tgt_prorated = bud["save_month"] * elapsed if bud["save_month"] else tgt_q * elapsed / 3
    if tgt_q:
        real = net
        status = t("q_ok") if real >= tgt_prorated else t("q_behind")
        L.append("")
        L.append(t("q_save_h"))
        L.append(t("q_save", t=fmt(tgt_q), p=fmt(tgt_prorated), r=fmt(real), s=status))

    L.append("")
    L.append(t("q_months_h"))
    for m in months:
        inc, exp, iv = d["m_income"].get(m, 0), d["m_expense"].get(m, 0), d["m_invest"].get(m, 0)
        a, b = period_range(m)
        L.append(t("q_month", m=m, rng=f"{a.month}/{a.day}–{b.month}/{b.day}", i=fmt(inc), x=fmt(exp), v=fmt(iv), n=fmt(inc - exp)))

    if expense:
        L.append("")
        L.append(t("q_fixed_h"))
        L.append(t("q_fixed", f=fmt(d["fixed"]), fp=d["fixed"] / expense * 100, v=fmt(d["variable"]), vp=d["variable"] / expense * 100))

    # 預算 vs 實際(單期加碼只加在該帳期)
    extra = defaultdict(float)
    for m in months:
        for c, amt in budget_extras(BUDGET).get(m, {}).items():
            extra[c] += amt
    for c in extra:
        bud["cats"].setdefault(c, 0.0)
    if bud["cats"]:
        L.append("")
        L.append(t("q_bud_h", e=elapsed))
        c0, c1, c2, c3, c4 = t("q_bud_cols")
        L.append(f"  {c0:<{CW}}{c1:>9}{c2:>9}{c3:>9}  {c4}")
        for cat in sorted(bud["cats"], key=lambda c: -d["cats"].get(c, 0)):
            q_bud = bud["cats"][cat] * 3 + extra.get(cat, 0)
            pace = bud["cats"][cat] * elapsed + extra.get(cat, 0)
            act = d["cats"].get(cat, 0)
            flag = t("q_over") if act > pace else "✅"
            L.append(f"  {cat:<{CW}}{fmt(q_bud):>9}{fmt(act):>9}{fmt(pace):>9}  {flag}")

    L.append("")
    L.append(t("q_cats_h"))
    for cat, amt in sorted(d["cats"].items(), key=lambda x: -x[1]):
        pct = amt / expense * 100 if expense else 0
        L.append(f"  {cat:<{CW}} {fmt(amt):>10}  {pct:4.0f}% {'█' * int(pct/5)}")

    return L, dict(income=income, expense=expense, invest=invest, net=net,
                   rate=rate, elapsed=elapsed)


def observations(d, bud, s):
    obs = []
    real = s["net"]
    tgt = (bud["save_month"] * s["elapsed"]) if bud["save_month"] else 0
    if tgt:
        if real >= tgt:
            obs.append(t("o_save_ok", r=fmt(real), d=fmt(real - tgt)))
        else:
            obs.append(t("o_save_bad", r=fmt(real), d=fmt(tgt - real)))
    over = [c for c in bud["cats"] if d["cats"].get(c, 0) > bud["cats"][c] * s["elapsed"]]
    if over:
        obs.append(t("o_over", c=t("sep").join(over)))
    if d["cats"]:
        top = max(d["cats"].items(), key=lambda x: x[1])
        obs.append(t("o_top", c=top[0], v=fmt(top[1])))
    if s["invest"]:
        obs.append(t("o_invest", v=fmt(s["invest"])))
    return obs


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    to_md = "--md" in sys.argv
    year, q = parse_quarter(args[0] if args else None)

    bud = load_budget()
    d = collect(year, q)
    lines, s = build_lines(year, q, d, bud)
    print("\n".join(lines))

    if to_md:
        obs = observations(d, bud, s)
        md = [t("md_title", y=year, q=q), ""]
        md.append("```")
        md.extend(lines)
        md.append("```")
        md.append("")
        md.append(t("md_obs"))
        for o in obs:
            md.append(f"- {o}")
        out = REPORTS / f"{year}-Q{q}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(md), encoding="utf-8")
        print(t("md_saved", p=out))


if __name__ == "__main__":
    main()
