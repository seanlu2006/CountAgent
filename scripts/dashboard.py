#!/usr/bin/env python3
"""把 ledger.csv 變成視覺化儀表板 reports/dashboard.html。

用法:
    python3 scripts/dashboard.py            # 用真實帳本產生並開啟
    python3 scripts/dashboard.py --demo      # 用示範假資料看長相(不碰帳本)
    python3 scripts/dashboard.py --no-open    # 只產生不自動開啟

需連網載入 Chart.js(CDN)。
"""
import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "ledger.csv"
OUT = ROOT / "reports" / "dashboard.html"

PALETTE = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
           "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac"]

def _demo_date(months_ago: int, day: int) -> str:
    """示範資料的日期要跟著今天走。

    寫死日期的話,--demo 產出的儀表板會隨著時間過去愈來愈空
    (「本月」那幾張卡片會全部變成 0),看起來像壞掉。
    """
    today = date.today()
    month = today.month - months_ago
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    if months_ago == 0:
        # 把原本散在整個月的日期等比壓縮進「本月已經過的天數」,
        # 這樣既不會出現未來日期,也不會全部擠在同一天。
        day = max(1, round(day * today.day / 28))
    return f"{year:04d}-{month:02d}-{day:02d}"


# 全部都是假資料,只為了展示儀表板長相。日期相對於今天,最近一個月最完整。
DEMO_ROWS = [
    {"date": _demo_date(2, 5), "type": "收入", "amount": "52000", "category": "薪資", "item": "月薪"},
    {"date": _demo_date(2, 12), "type": "支出", "amount": "15000", "category": "居住", "item": "房租"},
    {"date": _demo_date(2, 20), "type": "支出", "amount": "3200", "category": "飲食", "item": "外食合計"},

    {"date": _demo_date(1, 5), "type": "收入", "amount": "52000", "category": "薪資", "item": "月薪"},
    {"date": _demo_date(1, 8), "type": "收入", "amount": "8000", "category": "副業", "item": "接案"},
    {"date": _demo_date(1, 12), "type": "支出", "amount": "15000", "category": "居住", "item": "房租"},
    {"date": _demo_date(1, 15), "type": "支出", "amount": "4800", "category": "飲食", "item": "餐飲合計"},
    {"date": _demo_date(1, 18), "type": "支出", "amount": "1250", "category": "交通", "item": "捷運+加油"},

    {"date": _demo_date(0, 3), "type": "收入", "amount": "52000", "category": "薪資", "item": "月薪"},
    {"date": _demo_date(0, 5), "type": "支出", "amount": "15000", "category": "居住", "item": "房租"},
    {"date": _demo_date(0, 8), "type": "支出", "amount": "4800", "category": "飲食", "item": "餐飲合計"},
    {"date": _demo_date(0, 11), "type": "支出", "amount": "3600", "category": "購物", "item": "衣服"},
    {"date": _demo_date(0, 14), "type": "支出", "amount": "1500", "category": "醫療", "item": "看診拿藥"},
    {"date": _demo_date(0, 17), "type": "支出", "amount": "1250", "category": "交通", "item": "捷運+加油"},
    {"date": _demo_date(0, 20), "type": "支出", "amount": "990", "category": "娛樂", "item": "電影+串流"},
    {"date": _demo_date(0, 22), "type": "支出", "amount": "680", "category": "日用", "item": "生活用品"},
    {"date": _demo_date(0, 24), "type": "支出", "amount": "120", "category": "飲食", "item": "午餐 便當"},
]


def load_rows(demo: bool):
    if demo:
        return DEMO_ROWS
    if not LEDGER.exists():
        return []
    with LEDGER.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(r):
    try:
        return float(str(r.get("amount", "0")).replace(",", ""))
    except ValueError:
        return 0.0


def build(rows):
    this_month = date.today().strftime("%Y-%m")

    month_income = defaultdict(float)
    month_expense = defaultdict(float)
    cat_this_month = defaultdict(float)

    for r in rows:
        d = (r.get("date") or "")[:7]
        t = r.get("type")
        amt = num(r)
        if t == "收入":
            month_income[d] += amt
        elif t == "支出":
            month_expense[d] += amt
            if d == this_month:
                cat_this_month[r.get("category") or "其他"] += amt

    months = sorted(set(list(month_income) + list(month_expense)))[-6:]

    inc = round(month_income.get(this_month, 0))
    exp = round(month_expense.get(this_month, 0))

    cats = sorted(cat_this_month.items(), key=lambda x: -x[1])

    # 最近交易(依日期新到舊,全部顯示)
    recent = sorted(
        [r for r in rows if r.get("date")],
        key=lambda r: r["date"], reverse=True,
    )
    recent_clean = [{
        "date": r.get("date", ""),
        "type": r.get("type", ""),
        "amount": round(num(r)),
        "category": r.get("category", ""),
        "item": r.get("item", ""),
    } for r in recent]

    return {
        "thisMonth": this_month,
        "income": inc,
        "expense": exp,
        "balance": inc - exp,
        "months": months,
        "monthIncome": [round(month_income.get(m, 0)) for m in months],
        "monthExpense": [round(month_expense.get(m, 0)) for m in months],
        "catLabels": [c for c, _ in cats],
        "catValues": [round(v) for _, v in cats],
        "recent": recent_clean,
        "palette": PALETTE,
    }


HTML = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CountAgant 帳本儀表板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root{--bg:#0f1115;--card:#1a1d24;--ink:#e8eaed;--mut:#9aa0a6;--line:#2a2e37;
        --pos:#59a14f;--neg:#e15759;--accent:#4e79a7}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font-family:-apple-system,"PingFang TC","Noto Sans TC",sans-serif}
  .wrap{max-width:1040px;margin:0 auto;padding:28px 20px 60px}
  h1{font-size:20px;margin:0 0 4px} .sub{color:var(--mut);font-size:13px;margin-bottom:22px}
  .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:22px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
  .card .lbl{color:var(--mut);font-size:13px} .card .val{font-size:26px;font-weight:700;margin-top:6px}
  .pos{color:var(--pos)} .neg{color:var(--neg)}
  .grid{display:grid;grid-template-columns:1fr 1.2fr;gap:14px;margin-bottom:22px}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
  .panel h2{font-size:14px;margin:0 0 14px;color:var(--mut);font-weight:600}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line)}
  th{color:var(--mut);font-weight:600;font-size:12px}
  td.amt{text-align:right;font-variant-numeric:tabular-nums}
  .tag{font-size:11px;color:var(--mut)}
  .empty{color:var(--mut);text-align:center;padding:40px 0}
  @media(max-width:760px){.cards,.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <h1>📊 CountAgant 帳本</h1>
  <div class="sub">本月 <span id="ym"></span>　·　產生時間會隨重跑更新</div>

  <div class="cards">
    <div class="card"><div class="lbl">本月收入</div><div class="val pos" id="kIn"></div></div>
    <div class="card"><div class="lbl">本月支出</div><div class="val neg" id="kOut"></div></div>
    <div class="card"><div class="lbl">本月結餘</div><div class="val" id="kBal"></div></div>
  </div>

  <div class="grid">
    <div class="panel"><h2>本月支出分類</h2><canvas id="pie"></canvas>
      <div id="pieEmpty" class="empty" style="display:none">本月還沒有支出</div></div>
    <div class="panel"><h2>近 6 個月收支</h2><canvas id="bar"></canvas></div>
  </div>

  <div class="panel"><h2>最近交易</h2>
    <table><thead><tr><th>日期</th><th>類型</th><th>分類</th><th>品項</th><th class="amt">金額</th></tr></thead>
    <tbody id="rows"></tbody></table>
    <div id="rowsEmpty" class="empty" style="display:none">帳本還是空的 — 丟一句帳給我就有資料了</div>
  </div>
</div>

<script>
const D = __DATA__;
const nt = n => "NT$" + (n||0).toLocaleString("en-US");
document.getElementById("ym").textContent = D.thisMonth;
document.getElementById("kIn").textContent  = nt(D.income);
document.getElementById("kOut").textContent = nt(D.expense);
const bal = document.getElementById("kBal");
bal.textContent = nt(D.balance); bal.className = "val " + (D.balance>=0?"pos":"neg");

const tb = document.getElementById("rows");
if(!D.recent.length){document.getElementById("rowsEmpty").style.display="block";}
D.recent.forEach(r=>{
  const tr=document.createElement("tr");
  const sign = r.type==="收入" ? "+" : (r.type==="支出" ? "−" : "");
  const cls  = r.type==="收入" ? "pos" : (r.type==="支出" ? "neg" : "");
  tr.innerHTML=`<td>${r.date}</td><td class="tag">${r.type}</td><td>${r.category}</td>
    <td>${r.item}</td><td class="amt ${cls}">${sign}${nt(r.amount)}</td>`;
  tb.appendChild(tr);
});

Chart.defaults.color = "#9aa0a6";
Chart.defaults.borderColor = "#2a2e37";

if(D.catValues.length){
  new Chart(document.getElementById("pie"),{type:"doughnut",
    data:{labels:D.catLabels,datasets:[{data:D.catValues,backgroundColor:D.palette,borderWidth:0}]},
    options:{plugins:{legend:{position:"right",labels:{boxWidth:12,padding:10}},
      tooltip:{callbacks:{label:c=>` ${c.label}: ${nt(c.parsed)}`}}}}});
}else{document.getElementById("pie").style.display="none";
  document.getElementById("pieEmpty").style.display="block";}

new Chart(document.getElementById("bar"),{type:"bar",
  data:{labels:D.months,datasets:[
    {label:"收入",data:D.monthIncome,backgroundColor:"#59a14f"},
    {label:"支出",data:D.monthExpense,backgroundColor:"#e15759"}]},
  options:{plugins:{legend:{labels:{boxWidth:12}}},
    scales:{y:{ticks:{callback:v=>nt(v)}}}}});
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="用示範假資料")
    ap.add_argument("--no-open", action="store_true", help="不自動開啟瀏覽器")
    args = ap.parse_args()

    rows = load_rows(args.demo)
    data = build(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False)), encoding="utf-8")

    tag = " (示範資料)" if args.demo else ""
    print(f"✅ 已產生儀表板{tag}:{OUT}")

    if not args.no_open and sys.platform == "darwin":
        subprocess.run(["open", str(OUT)], check=False)


if __name__ == "__main__":
    main()
