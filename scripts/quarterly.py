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

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "ledger.csv"
BUDGET = ROOT / "data" / "budget.md"
QUARTERS = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}


def fmt(n):
    return f"{n:,.0f}"


def parse_quarter(arg):
    if arg and re.match(r"\d{4}Q[1-4]", arg.upper()):
        y, q = arg.upper().split("Q")
        return int(y), int(q)
    today = date.today()
    return today.year, (today.month - 1) // 3 + 1


def num(r):
    try:
        return float(str(r.get("amount", "0")).replace(",", ""))
    except ValueError:
        return 0.0


def load_budget():
    cfg = {"save_month": 0, "save_quarter": 0, "cats": {}}
    if not BUDGET.exists():
        return cfg
    in_cat_table = False
    for line in BUDGET.read_text(encoding="utf-8").splitlines():
        # 只在「每月分類預算」段落內解析表格,避免誤讀其他表格
        if line.startswith("#"):
            in_cat_table = "每月分類預算" in line
        if "每月淨存目標" in line:
            m = re.search(r"(\d[\d,]*)", line.split(":")[-1])
            if m:
                cfg["save_month"] = float(m.group(1).replace(",", ""))
        elif "每季淨存目標" in line:
            m = re.search(r"(\d[\d,]*)", line.split(":")[-1])
            if m:
                cfg["save_quarter"] = float(m.group(1).replace(",", ""))
        elif in_cat_table:
            m = re.match(r"\s*\|\s*([^\|]+?)\s*\|\s*(\d[\d,]*)\s*\|", line)
            if m and m.group(1) not in ("分類", "項目"):
                cfg["cats"][m.group(1).strip()] = float(m.group(2).replace(",", ""))
    return cfg


def collect(year, q):
    months = [f"{year}-{m:02d}" for m in QUARTERS[q]]
    d = {
        "months": months,
        "m_income": defaultdict(float), "m_expense": defaultdict(float),
        "m_invest": defaultdict(float), "cats": defaultdict(float),
        "fixed": 0.0, "variable": 0.0,
    }
    with LEDGER.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ym = (r.get("date") or "")[:7]
            if ym not in months:
                continue
            amt = num(r)
            t = r.get("type")
            if t == "收入":
                d["m_income"][ym] += amt
            elif t == "支出":
                d["m_expense"][ym] += amt
                d["cats"][r.get("category", "其他")] += amt
                if "固定" in (r.get("note") or ""):
                    d["fixed"] += amt
                else:
                    d["variable"] += amt
            elif t == "投資":
                d["m_invest"][ym] += amt
    return d


def build_lines(year, q, d, bud):
    months = d["months"]
    income = sum(d["m_income"].values())
    expense = sum(d["m_expense"].values())
    invest = sum(d["m_invest"].values())
    net = income - expense
    rate = (net / income * 100) if income else 0

    today = date.today()
    elapsed = sum(1 for m in months if m <= today.strftime("%Y-%m")) or 3

    L = []
    L.append(f"📈 {year} 第 {q} 季財報  ({months[0]} ~ {months[-1]})   已過 {elapsed}/3 月")
    L.append("=" * 50)
    L.append(f"  總收入    {fmt(income):>12}")
    L.append(f"  總支出    {fmt(expense):>12}")
    L.append(f"  淨結餘    {fmt(net):>12}   (儲蓄率 {rate:.0f}%)")
    L.append(f"  定期投資  {fmt(invest):>12}   (不計入支出)")
    L.append(f"  真實留存  {fmt(net + invest):>12}   (結餘＋投資,你實際沒花掉的錢)")

    # 儲蓄目標
    tgt_q = bud["save_quarter"] or bud["save_month"] * 3
    tgt_prorated = bud["save_month"] * elapsed if bud["save_month"] else tgt_q * elapsed / 3
    if tgt_q:
        real = net + invest
        status = "✅ 達標" if real >= tgt_prorated else "⚠️ 落後"
        L.append("")
        L.append(f"── 儲蓄目標 ──  (真實留存計)")
        L.append(f"  季目標 {fmt(tgt_q)} · 到目前應達 {fmt(tgt_prorated)} · 實際 {fmt(real)}  {status}")

    L.append("")
    L.append("── 每月收支 ──")
    for m in months:
        inc, exp, iv = d["m_income"].get(m, 0), d["m_expense"].get(m, 0), d["m_invest"].get(m, 0)
        L.append(f"  {m}   收 {fmt(inc):>8}   支 {fmt(exp):>8}   投 {fmt(iv):>8}   餘 {fmt(inc-exp):>8}")

    if expense:
        L.append("")
        L.append("── 固定 vs 變動支出 ──")
        L.append(f"  固定 {fmt(d['fixed']):>10} ({d['fixed']/expense*100:.0f}%)   變動 {fmt(d['variable']):>10} ({d['variable']/expense*100:.0f}%)")

    # 預算 vs 實際
    if bud["cats"]:
        L.append("")
        L.append(f"── 預算 vs 實際 ──  (季預算＝月預算×3;進度以已過 {elapsed} 月折算)")
        L.append(f"  {'分類':<6}{'季預算':>9}{'實際':>9}{'應花':>9}  狀態")
        for cat in sorted(bud["cats"], key=lambda c: -d["cats"].get(c, 0)):
            q_bud = bud["cats"][cat] * 3
            pace = bud["cats"][cat] * elapsed
            act = d["cats"].get(cat, 0)
            flag = "⚠️超" if act > pace else "✅"
            L.append(f"  {cat:<6}{fmt(q_bud):>9}{fmt(act):>9}{fmt(pace):>9}  {flag}")

    L.append("")
    L.append("── 支出分類 ──")
    for cat, amt in sorted(d["cats"].items(), key=lambda x: -x[1]):
        pct = amt / expense * 100 if expense else 0
        L.append(f"  {cat:<6} {fmt(amt):>10}  {pct:4.0f}% {'█' * int(pct/5)}")

    return L, dict(income=income, expense=expense, invest=invest, net=net,
                   rate=rate, elapsed=elapsed)


def observations(d, bud, s):
    obs = []
    real = s["net"] + s["invest"]
    tgt = (bud["save_month"] * s["elapsed"]) if bud["save_month"] else 0
    if tgt:
        if real >= tgt:
            obs.append(f"儲蓄進度達標:真實留存 {fmt(real)},超出階段目標 {fmt(real-tgt)}。")
        else:
            obs.append(f"儲蓄落後:真實留存 {fmt(real)},比階段目標少 {fmt(tgt-real)}——本季後段留意變動支出。")
    over = [c for c in bud["cats"] if d["cats"].get(c, 0) > bud["cats"][c] * s["elapsed"]]
    if over:
        obs.append("超出預算節奏的分類:" + "、".join(over) + "。")
    if d["cats"]:
        top = max(d["cats"].items(), key=lambda x: x[1])
        obs.append(f"最大支出類別:{top[0]} {fmt(top[1])}。")
    if s["invest"]:
        obs.append(f"本季已定期投入 {fmt(s['invest'])} 到投資,這是你真正的資產累積。")
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
        md = [f"# {year} Q{q} 財報", ""]
        md.append("```")
        md.extend(lines)
        md.append("```")
        md.append("")
        md.append("## 觀察與建議")
        for o in obs:
            md.append(f"- {o}")
        out = ROOT / "reports" / f"{year}-Q{q}.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text("\n".join(md), encoding="utf-8")
        print(f"\n✅ 已存季報:{out}")


if __name__ == "__main__":
    main()
