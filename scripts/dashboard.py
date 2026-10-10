#!/usr/bin/env python3
"""把 ledger.csv 變成互動儀表板 reports/dashboard.html。

用法:
    python3 scripts/dashboard.py            # 用真實帳本產生並開啟
    python3 scripts/dashboard.py --demo      # 用示範假資料看長相(不碰帳本)
    python3 scripts/dashboard.py --no-open    # 只產生不自動開啟

單一 HTML 檔,不連網、不載任何函式庫。動態沿用 morph-motion 的做法:
每個會動的數值都是閉式彈簧的疊加,分頁指示器兩個邊緣各自一條彈簧。
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from period import baseline_income, income_with_floor, period_days, period_of, period_range, quarter_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "ledger.csv"
BUDGET_FILES = [ROOT / "data" / "budget.md", ROOT / "data" / "budget.example.md"]
OUT = ROOT / "reports" / "dashboard.html"


def _demo_date(months_ago: int, day: int) -> str:
    """示範資料的日期要跟著今天走,不然 --demo 會隨時間愈來愈空。
    day 是帳期內第幾天(1~28);當期只排到今天為止。"""
    today = date.today()
    y, m = map(int, period_of(today).split("-"))
    m -= months_ago
    while m <= 0:
        m += 12
        y -= 1
    start = period_range(f"{y:04d}-{m:02d}")[0]
    offset = day - 1
    if months_ago == 0:
        offset = round(offset * (today - start).days / 27)
    return (start + timedelta(days=offset)).isoformat()


# 全部都是假資料,只為了展示儀表板長相。
DEMO_ROWS = [
    {"date": _demo_date(2, 5), "type": "收入", "amount": "52000", "category": "薪資", "item": "月薪"},
    {"date": _demo_date(2, 12), "type": "支出", "amount": "6500", "category": "居住", "item": "房租", "note": "固定"},
    {"date": _demo_date(2, 20), "type": "支出", "amount": "3200", "category": "飲食", "item": "外食合計"},
    {"date": _demo_date(1, 5), "type": "收入", "amount": "52000", "category": "薪資", "item": "月薪"},
    {"date": _demo_date(1, 8), "type": "收入", "amount": "8000", "category": "副業", "item": "接案"},
    {"date": _demo_date(1, 12), "type": "支出", "amount": "6500", "category": "居住", "item": "房租", "note": "固定"},
    {"date": _demo_date(1, 15), "type": "支出", "amount": "4800", "category": "飲食", "item": "餐飲合計"},
    {"date": _demo_date(1, 18), "type": "支出", "amount": "1250", "category": "交通", "item": "捷運+加油"},
    {"date": _demo_date(1, 20), "type": "投資", "amount": "5000", "category": "投資", "item": "ETF 定期定額"},
    {"date": _demo_date(0, 3), "type": "收入", "amount": "52000", "category": "薪資", "item": "月薪"},
    {"date": _demo_date(0, 5), "type": "支出", "amount": "6500", "category": "居住", "item": "房租", "note": "固定"},
    {"date": _demo_date(0, 6), "type": "支出", "amount": "185", "category": "飲食", "item": "午餐"},
    {"date": _demo_date(0, 8), "type": "支出", "amount": "320", "category": "飲食", "item": "晚餐"},
    {"date": _demo_date(0, 9), "type": "支出", "amount": "860", "category": "食材", "item": "超市採買"},
    {"date": _demo_date(0, 11), "type": "支出", "amount": "3600", "category": "購物", "item": "衣服"},
    {"date": _demo_date(0, 12), "type": "支出", "amount": "140", "category": "飲食", "item": "午餐"},
    {"date": _demo_date(0, 14), "type": "支出", "amount": "1500", "category": "醫療", "item": "看診拿藥"},
    {"date": _demo_date(0, 15), "type": "支出", "amount": "260", "category": "飲食", "item": "晚餐"},
    {"date": _demo_date(0, 17), "type": "支出", "amount": "1250", "category": "交通", "item": "捷運+加油"},
    {"date": _demo_date(0, 19), "type": "支出", "amount": "480", "category": "飲食", "item": "聚餐"},
    {"date": _demo_date(0, 20), "type": "支出", "amount": "990", "category": "娛樂", "item": "電影+串流"},
    {"date": _demo_date(0, 21), "type": "投資", "amount": "5000", "category": "投資", "item": "ETF 定期定額"},
    {"date": _demo_date(0, 22), "type": "支出", "amount": "680", "category": "日用", "item": "生活用品"},
    {"date": _demo_date(0, 24), "type": "支出", "amount": "120", "category": "飲食", "item": "午餐 便當"},
    {"date": _demo_date(0, 25), "type": "支出", "amount": "540", "category": "食材", "item": "市場買菜"},
]


def load_rows(demo: bool):
    if demo:
        return DEMO_ROWS
    if not LEDGER.exists():
        return []
    with LEDGER.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_budget(demo: bool = False):
    """讀 data/budget.md(沒有就讀範本)的「每月分類預算」表格。--demo 只讀範本,不碰私人預算。"""
    for p in (BUDGET_FILES[1:] if demo else BUDGET_FILES):
        if not p.exists():
            continue
        cats, save, in_tbl = {}, 0.0, False
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                in_tbl = "每月分類預算" in line
            if "每月淨存目標" in line:
                m = re.search(r"(\d[\d,]*)", line.split(":")[-1])
                save = float(m.group(1).replace(",", "")) if m else 0.0
            elif in_tbl:
                m = re.match(r"\s*\|\s*([^|]+?)\s*\|\s*(\d[\d,]*)\s*\|", line)
                if m and m.group(1) not in ("分類", "項目"):
                    cats[m.group(1).strip()] = float(m.group(2).replace(",", ""))
        return cats, save
    return {}, 0.0


def num(r):
    try:
        return float(str(r.get("amount", "0")).replace(",", ""))
    except ValueError:
        return 0.0


def _row(r):
    return {"date": r.get("date", ""), "type": r.get("type", ""), "amount": round(num(r)),
            "category": r.get("category", ""), "item": r.get("item", ""),
            "payment": r.get("payment", ""), "fixed": "固定" in (r.get("note") or "")}


def _point(label, day_rows):
    exp = [r for r in day_rows if r["type"] == "支出"]
    items = sorted(exp, key=lambda r: -r["amount"])[:6]
    return {"label": label,
            "total": sum(r["amount"] for r in exp),
            "food": sum(r["amount"] for r in exp if r["category"] == "飲食"),
            "items": [[r["item"], r["amount"], r["category"]] for r in items]}


def build_view(key, label, kind, days, rows, budget, save, floor=0.0):
    """days: 這個視圖涵蓋的日期(只到今天為止)。"""
    span = {d.isoformat() for d in days}
    vr = [r for r in rows if r["date"] in span]
    exp = [r for r in vr if r["type"] == "支出"]
    cats = defaultdict(float)
    for r in exp:
        cats[r["category"] or "其他"] += r["amount"]

    by_day = defaultdict(list)
    for r in vr:
        by_day[r["date"]].append(r)
    if kind == "month":
        points = [_point(f"{d.month}/{d.day}", by_day[d.isoformat()]) for d in days]
    else:  # 季:每週一根
        weeks = defaultdict(list)
        for d in days:
            weeks[d - timedelta(days=d.weekday())].extend(by_day[d.isoformat()])
        points = [_point(f"{w.month}/{w.day}", weeks[w]) for w in sorted(weeks)]

    periods = sorted({period_of(d) for d in days})
    n_months = len(periods)
    inc_by = defaultdict(float)
    for r in vr:
        if r["type"] == "收入":
            inc_by[period_of(r["date"])] += r["amount"]
    actual_income = sum(inc_by.values())
    income = income_with_floor(inc_by, periods, floor)
    biggest = max(exp, key=lambda r: r["amount"], default=None)
    return {
        "key": key, "label": label, "kind": kind,
        "range": f"{days[0].month}/{days[0].day}–{days[-1].month}/{days[-1].day}" if days else "",
        "nDays": len(days), "nMonths": n_months,
        "income": income,
        "floorUsed": income > actual_income,
        "floor": floor,
        "expense": sum(r["amount"] for r in exp),
        "invest": sum(r["amount"] for r in vr if r["type"] == "投資"),
        "fixed": sum(r["amount"] for r in exp if r["fixed"]),
        "cats": {k: round(v) for k, v in cats.items()},
        "budget": {k: v * n_months for k, v in budget.items()},
        "save": save * n_months,
        "points": points,
        "biggest": [biggest["item"], biggest["amount"], biggest["date"]] if biggest else None,
        "rows": sorted(vr, key=lambda r: r["date"], reverse=True),
    }


def build(raw, budget, save, floor=0.0):
    rows = [_row(r) for r in raw if r.get("date")]
    today = date.today()
    # 月 = 信用卡帳期(上月 24 ~ 本月 23),見 period.py
    months = sorted({period_of(r["date"]) for r in rows if r["type"] == "支出"})[-6:]

    def month_days(ym):
        return period_days(ym, until=today)

    views = [build_view(ym, f"{int(ym[5:])}月", "month", month_days(ym), rows, budget, save, floor)
             for ym in months]

    # 季:三個帳期,資料裡至少有兩期才列
    quarters = defaultdict(list)
    for ym in months:
        quarters[quarter_of(ym)].append(ym)
    for (y, q), yms in sorted(quarters.items()):
        if len(yms) >= 2:
            days = [d for ym in yms for d in month_days(ym)]
            views.append(build_view(f"{y}Q{q}", f"Q{q}", "quarter", days, rows, budget, save, floor))

    month_views = [i for i, v in enumerate(views) if v["kind"] == "month"]
    default = month_views[-1] if month_views else 0
    if len(month_views) > 1 and sum(1 for r in views[default]["rows"] if r["type"] == "支出") < 3:
        default = month_views[-2]

    all_cats = sorted({c for v in views for c in v["cats"]} | set(budget))
    return {"views": views, "default": default, "cats": all_cats,
            "generated": today.isoformat()}


HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CountAgent</title>
<style>
  :root{
    --bg:#e8e6e1; --panel:#f3f1ec; --ink:#111110; --mut:rgba(17,17,16,.52); --line:rgba(17,17,16,.09);
    --obj:#111110; --on:#fff; --on-mut:rgba(255,255,255,.55); --bar:#474745; --lime:#a8f07a; --over:#e5533d;
    --tabbg:#dcd9d2; --shadow:0 22px 54px rgba(35,30,22,.16),0 2px 6px rgba(35,30,22,.10);
  }
  @media (prefers-color-scheme:dark){:root{
    --bg:#0f0f0e; --panel:#1a1a18; --ink:#f2f0eb; --mut:rgba(242,240,235,.5); --line:rgba(242,240,235,.08);
    --obj:#1f1f1d; --bar:#5d5d59; --tabbg:#232321; --shadow:0 18px 44px rgba(0,0,0,.45);
  }}
  *{box-sizing:border-box}
  html,body{margin:0;background:var(--bg);color:var(--ink)}
  body{font-family:-apple-system,"SF Pro Text","PingFang TC","Noto Sans TC",sans-serif;
       -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
  button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer}
  .wrap{max-width:1120px;margin:0 auto;padding:28px 22px 90px}

  header{display:flex;align-items:center;gap:18px;margin-bottom:22px;flex-wrap:wrap}
  .brand{font-weight:700;font-size:19px;letter-spacing:-.01em;display:flex;align-items:center;gap:9px}
  .dot{width:11px;height:11px;border-radius:50%;background:var(--lime);box-shadow:0 0 0 3px rgba(168,240,122,.25)}
  .tabs{position:relative;display:flex;background:var(--tabbg);border-radius:999px;padding:4px;margin-left:auto}
  .tab{position:relative;z-index:1;padding:9px 16px;border-radius:999px;font-weight:600;font-size:14px;white-space:nowrap}
  .tab:focus-visible{outline:2px solid var(--lime);outline-offset:2px}
  .ind{position:absolute;top:4px;bottom:4px;border-radius:999px;background:var(--obj);box-shadow:0 4px 12px rgba(0,0,0,.18)}
  .kbtn{padding:8px 12px;border-radius:12px;background:var(--panel);font-weight:600;font-size:13px;color:var(--mut)}
  .kbtn kbd{font-family:"SF Mono",ui-monospace,Menlo,monospace}

  .obj{background:var(--obj);color:var(--on);border-radius:36px;padding:28px 30px 22px;box-shadow:var(--shadow)}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
  .kpi .lbl{color:var(--on-mut);font-size:13px;font-weight:600}
  .kpi{min-width:0} .kpi .val{font-size:clamp(22px,3.4vw,34px);font-weight:700;letter-spacing:-.02em;margin-top:6px;line-height:1.05;white-space:nowrap}
  .kpi .sub{color:var(--on-mut);font-size:12px;margin-top:6px;min-height:15px}
  .kpi.neg .val{color:#ff8a73} .kpi.pos .val{color:var(--lime)}

  .chead{display:flex;align-items:center;gap:14px;margin:26px 0 10px}
  .chead h2{margin:0;font-size:14px;color:var(--on-mut);font-weight:600}
  .legend{font-size:12px;color:var(--on-mut);display:flex;align-items:center;gap:6px}
  .legend i{display:inline-block;width:16px;border-top:2px dashed var(--lime)}
  .toggle{margin-left:auto;display:flex;align-items:center;gap:10px;font-size:13px;font-weight:600;color:var(--on-mut)}
  .sw{position:relative;width:52px;height:30px;border-radius:999px;background:rgba(255,255,255,.14);overflow:hidden}
  .sw .fill{position:absolute;inset:0;background:var(--lime)}
  .sw .knob{position:absolute;top:3px;height:24px;border-radius:999px;background:#fff}
  .chart{position:relative;height:250px;margin-top:6px;touch-action:none}
  .bars{position:absolute;left:0;right:0;top:0;height:220px}
  .bar{position:absolute;bottom:0;border-radius:6px 6px 3px 3px;background:var(--bar)}
  .bline{position:absolute;left:0;right:0;border-top:2px dashed var(--lime);opacity:.85}
  .xl{position:absolute;top:228px;font-size:11px;color:var(--on-mut);transform:translateX(-50%);white-space:nowrap}
  .tip{position:absolute;top:6px;pointer-events:none;background:#fff;color:#111110;border-radius:14px;padding:10px 12px;
       font-size:12px;min-width:150px;box-shadow:0 12px 30px rgba(0,0,0,.28)}
  .tip b{font-size:15px} .tip .r{display:flex;justify-content:space-between;gap:12px;color:#555;margin-top:3px}
  .empty{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--on-mut);font-size:14px}

  .grid{display:grid;grid-template-columns:1.25fr 1fr;gap:18px;margin-top:18px}
  .panel{background:var(--panel);border-radius:28px;padding:22px 24px}
  .panel h3{margin:0 0 16px;font-size:14px;color:var(--mut);font-weight:600;display:flex;justify-content:space-between}
  .cats{position:relative}
  .crow{position:absolute;left:0;right:0;height:46px}
  .crow .top{display:flex;justify-content:space-between;font-size:14px;font-weight:600}
  .crow .top span:last-child{color:var(--mut);font-weight:500}
  .track{position:relative;height:8px;border-radius:99px;background:var(--line);margin-top:7px;overflow:visible}
  .track .f{position:absolute;left:0;top:0;bottom:0;border-radius:99px;background:var(--ink)}
  .track .o{position:absolute;top:0;bottom:0;border-radius:0 99px 99px 0;background:var(--over)}
  .track .m{position:absolute;top:-4px;bottom:-4px;width:3px;margin-left:-1.5px;border-radius:2px;background:var(--lime);
            box-shadow:0 0 0 2px var(--panel)}
  .stats{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .stat{background:var(--bg);border-radius:20px;padding:14px 16px}
  .stat .l{font-size:12px;color:var(--mut);font-weight:600}
  .stat .v{font-size:22px;font-weight:700;margin-top:4px;letter-spacing:-.01em}
  .stat .s{font-size:12px;color:var(--mut);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .split{height:10px;border-radius:99px;overflow:hidden;display:flex;margin-top:10px;background:var(--line)}
  .split i{display:block;height:100%}

  .list{margin-top:18px}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th{text-align:left;font-size:12px;color:var(--mut);font-weight:600;padding:0 8px 10px}
  td{padding:10px 8px;border-top:1px solid var(--line)}
  td.a{text-align:right;font-weight:600} th.a{text-align:right}
  td .c{font-size:12px;color:var(--mut)}
  tr.in td.a{color:#3e9a2a} tr.iv td.a{color:#6a5acd}
  @media (prefers-color-scheme:dark){tr.in td.a{color:var(--lime)} tr.iv td.a{color:#a99cff}}
  tbody tr{animation:rise .42s cubic-bezier(.2,.9,.25,1.15) both}
  @keyframes rise{from{opacity:0;transform:translateY(8px);filter:blur(4px)}}

  .toast{position:fixed;left:50%;bottom:26px;display:flex;align-items:center;gap:12px;background:var(--obj);color:#fff;
         padding:14px 20px 16px;border-radius:24px;box-shadow:var(--shadow);font-size:14px;font-weight:600;max-width:calc(100vw - 32px)}
  .toast .td{width:10px;height:10px;border-radius:50%;background:var(--lime);flex:none}
  .toast .tl{position:absolute;left:20px;right:20px;bottom:7px;height:3px;border-radius:2px;background:rgba(255,255,255,.12);overflow:hidden}
  .toast .tl i{display:block;height:100%;background:var(--lime)}

  .pal-bg{position:fixed;inset:0;background:rgba(17,17,16,.32);display:flex;align-items:flex-start;justify-content:center;padding-top:14vh}
  .pal{width:min(560px,calc(100vw - 32px));background:var(--obj);color:#fff;border-radius:28px;padding:10px;box-shadow:var(--shadow)}
  .pal input{width:100%;background:none;border:0;outline:0;color:#fff;font:600 18px -apple-system,"PingFang TC",sans-serif;padding:14px 14px 12px}
  .pal .it{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:16px;font-size:15px;font-weight:600}
  .pal .it .k{margin-left:auto;font-size:12px;color:var(--on-mut);font-weight:500}
  .pal .it.sel{background:rgba(255,255,255,.1)} .pal .it.sel .b{background:var(--lime)}
  .pal .b{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.3)}
  .foot{margin-top:26px;font-size:12px;color:var(--mut);text-align:center}
  [hidden]{display:none!important}

  @media (max-width:820px){
    .kpis{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}
    .tabs{margin-left:0;width:100%;overflow-x:auto} .kbtn{display:none}
    .obj{border-radius:28px;padding:22px 18px}
  }
  @media (prefers-reduced-motion:reduce){tbody tr{animation:none}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand"><span class="dot"></span>CountAgent</div>
    <nav class="tabs" id="tabs" role="tablist"><div class="ind" id="ind"></div></nav>
    <button class="kbtn" id="kbtn" title="指令面板"><kbd>⌘K</kbd></button>
  </header>

  <section class="obj">
    <div class="kpis">
      <div class="kpi" id="k-exp"><div class="lbl">支出</div><div class="val">0</div><div class="sub"></div></div>
      <div class="kpi" id="k-inc"><div class="lbl">收入</div><div class="val">0</div><div class="sub"></div></div>
      <div class="kpi" id="k-net"><div class="lbl">結餘</div><div class="val">0</div><div class="sub"></div></div>
      <div class="kpi" id="k-inv"><div class="lbl">定期投資</div><div class="val">0</div><div class="sub"></div></div>
    </div>
    <div class="chead">
      <h2 id="ctitle">每日支出</h2>
      <span class="legend"><i></i><span id="ltext">每日預算</span></span>
      <button class="toggle" id="toggle" role="switch" aria-checked="false">只看外食
        <span class="sw"><span class="fill" id="swfill"></span><span class="knob" id="knob"></span></span></button>
    </div>
    <div class="chart" id="chart">
      <div class="bars" id="bars"><div class="bline" id="bline"></div></div>
      <div id="xls"></div>
      <div class="tip" id="tip"></div>
      <div class="empty" id="cempty" hidden>這段期間還沒有支出</div>
    </div>
  </section>

  <div class="grid">
    <section class="panel"><h3><span>分類 vs 預算</span><span id="cbud"></span></h3><div class="cats" id="cats"></div></section>
    <section class="panel"><h3><span>重點</span></h3><div class="stats" id="stats"></div></section>
  </div>

  <section class="panel list">
    <h3><span id="ltitle">交易</span><span id="lcount"></span></h3>
    <table><thead><tr><th>日期</th><th>分類</th><th>品項</th><th>付款</th><th class="a">金額</th></tr></thead>
    <tbody id="rows"></tbody></table>
  </section>
  <div class="foot" id="foot"></div>
</div>

<div class="toast" id="toast"><span class="td"></span><span id="ttext"></span><span class="tl"><i id="tbar"></i></span></div>
<div class="pal-bg" id="palbg" hidden><div class="pal" id="pal"><input id="pin" placeholder="切換月份、季、外食模式…" autocomplete="off"><div id="plist"></div></div></div>

<script>
const D = __DATA__;
(() => {
  // ---------------------------------------------------------------- 彈簧(同 morph-motion 的閉式解)
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const mix = (a, b, k) => a + (b - a) * k;
  function S(tau, w, z) {
    if (tau <= 0) return 0;
    if (z >= 1) return 1 - Math.exp(-w * tau) * (1 + w * tau);
    const wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * tau) * (Math.cos(wd * tau) + (z * w / wd) * Math.sin(wd * tau));
  }
  const SP = { snap: [24, .86], morph: [15, .82], grow: [12, .84], camera: [9, 1], lead: [22, .85], trail: [13, .85] };
  const now = () => performance.now() / 1000;
  const live = new Set(); let raf = 0;
  /* 目標每改一次就疊一條階躍響應;跑完的響應併回 base,值不跳。 */
  function spring(v0 = 0) {
    const s = { base: v0, last: v0, ev: [],
      set(v, p = 'morph', delay = 0) {
        if (v === s.last) return;
        if (RM) { s.jump(v); kick(); return; }
        s.ev.push({ t: now() + delay, d: v - s.last, p: SP[p] }); s.last = v; live.add(s); kick();
      },
      jump(v) { s.base = v; s.last = v; s.ev = []; },
      get(t = now()) { let f = s.base; for (const e of s.ev) f += e.d * S(t - e.t, e.p[0], e.p[1]); return f; },
      settle(t) { s.ev = s.ev.filter(e => (t - e.t > 3 ? (s.base += e.d, false) : true)); return !s.ev.length; },
    };
    return s;
  }
  function kick() { if (!raf) raf = requestAnimationFrame(frame); }
  function frame() {
    const t = now(); render(t);
    for (const s of live) if (s.settle(t)) live.delete(s);
    raf = live.size || toastUntil > t ? requestAnimationFrame(frame) : 0;
  }
  // 進退場:淡入 + 模糊 + 微位移(同 morph-motion 的 show())
  function show(el, v, drift = 6, blur = 6) {
    v = clamp(v); el.style.opacity = v.toFixed(3);
    el.style.filter = v < .999 ? `blur(${((1 - v) * blur).toFixed(2)}px)` : 'none';
    el.style.visibility = v < .002 ? 'hidden' : 'visible';
    return (1 - v) * drift;
  }

  // ---------------------------------------------------------------- 工具
  const $ = s => document.querySelector(s);
  const fmt = n => Math.round(n).toLocaleString('en-US');
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const V = D.views;
  let cur = D.default, foodMode = false;

  // ---------------------------------------------------------------- 液態分頁
  const tabsEl = $('#tabs'), ind = $('#ind');
  const tabEls = V.map((v, i) => {
    const b = document.createElement('button');
    b.className = 'tab'; b.textContent = v.label; b.setAttribute('role', 'tab');
    b.onclick = () => select(i); tabsEl.appendChild(b); return b;
  });
  const indL = spring(), indR = spring();
  function tabGeom(i) { const b = tabEls[i]; return [b.offsetLeft, b.offsetLeft + b.offsetWidth]; }
  function moveInd(i, instant) {
    const [l, r] = tabGeom(i);
    if (instant) { indL.jump(l); indR.jump(r); return; }
    const right = l > indL.last;               // 前緣硬、後緣軟,指示器會被「拉長」再收回
    indL.set(l, right ? 'trail' : 'lead'); indR.set(r, right ? 'lead' : 'trail');
  }

  // ---------------------------------------------------------------- KPI
  const K = {};
  for (const k of ['exp', 'inc', 'net', 'inv']) K[k] = { el: $('#k-' + k), s: spring() };

  // ---------------------------------------------------------------- 長條圖
  const barsEl = $('#bars'), chartEl = $('#chart'), tip = $('#tip'), bline = $('#bline');
  const BH = 220; let bars = [], pts = [], maxV = 1;
  const colW = spring(10), lineY = spring(BH), tipV = spring(0), tipX = spring(0);
  let hover = -1, tipSide = false;
  function ensureBars(n) {
    while (bars.length < n) {
      const el = document.createElement('div'); el.className = 'bar'; barsEl.appendChild(el);
      bars.push({ el, h: spring(0), hi: spring(0) });
    }
  }
  function dayBudget(v) {
    const b = v.budget, tot = foodMode ? (b['飲食'] || 0) : Object.values(b).reduce((a, c) => a + c, 0);
    return tot / v.nMonths / (v.kind === 'month' ? 30 : 30 / 7) || 0;
  }
  function setChart(v, first) {
    pts = v.points; const n = pts.length; ensureBars(n);
    const val = p => foodMode ? p.food : p.total;
    const bud = dayBudget(v);
    maxV = Math.max(1, bud * 1.15, ...pts.map(val)) * 1.08;
    const W = chartEl.clientWidth;
    first ? colW.jump(W / Math.max(n, 1)) : colW.set(W / Math.max(n, 1), 'morph');
    const stagger = Math.min(.04, .6 / Math.max(n, 1));     // morph-motion 是 40ms 一根
    bars.forEach((b, k) => b.h.set(k < n ? val(pts[k]) / maxV * BH : 0, 'morph', k * stagger));
    lineY.set(BH - bud / maxV * BH, 'morph');
    $('#ltext').textContent = (v.kind === 'month' ? '每日' : '每週') + (foodMode ? '外食預算 ' : '預算 ') + fmt(bud);
    $('#ctitle').textContent = (v.kind === 'month' ? '每日' : '每週') + (foodMode ? '外食' : '支出');
    $('#cempty').hidden = pts.some(p => val(p) > 0);
    // x 軸標籤:最多 8 個
    const xls = $('#xls'); xls.innerHTML = '';
    const step = Math.ceil(n / 8);
    pts.forEach((p, k) => { if (k % step === 0) { const s = document.createElement('div'); s.className = 'xl'; s.textContent = p.label; s.dataset.k = k; xls.appendChild(s); } });
    setHover(-1);
  }
  function setHover(k) {
    if (k === hover) return;
    if (hover >= 0 && bars[hover]) bars[hover].hi.set(0, 'snap');
    hover = k;
    if (k < 0) { tipV.set(0, 'snap'); return; }
    bars[k].hi.set(1, 'snap');
    const p = pts[k], items = p.items.filter(i => !foodMode || i[2] === '飲食');
    tip.innerHTML = `<div>${esc(p.label)}</div><b>NT$${fmt(foodMode ? p.food : p.total)}</b>` +
      (items.length ? items.slice(0, 4).map(i => `<div class="r"><span>${esc(i[0])}</span><span>${fmt(i[1])}</span></div>`).join('') : '<div class="r">沒有紀錄</div>');
    tipX.set((k + .5) * colW.last, tipV.get() > .3 ? 'snap' : 'snap');
    if (tipV.get() < .05) tipX.jump((k + .5) * colW.last);
    tipV.set(1, 'snap');
  }
  chartEl.addEventListener('pointermove', e => {
    const r = chartEl.getBoundingClientRect(), k = Math.floor((e.clientX - r.left) / colW.last);
    setHover(k >= 0 && k < pts.length ? k : -1);
  });
  chartEl.addEventListener('pointerleave', () => setHover(-1));

  // ---------------------------------------------------------------- 分類 vs 預算(列會依金額重新排序並滑動)
  const catsEl = $('#cats'), RH = 52;
  const CR = {};
  D.cats.forEach(c => {
    const el = document.createElement('div'); el.className = 'crow';
    el.innerHTML = `<div class="top"><span>${esc(c)}</span><span></span></div><div class="track"><i class="f"></i><i class="o"></i><i class="m"></i></div>`;
    catsEl.appendChild(el);
    CR[c] = { el, amt: el.querySelector('.top span:last-child'), f: el.querySelector('.f'), o: el.querySelector('.o'), m: el.querySelector('.m'),
      y: spring(0), vis: spring(0), fw: spring(0), ow: spring(0), mx: spring(0), a: spring(0) };
  });
  const catsH = spring(0);
  function setCats(v, first) {
    const act = c => v.cats[c] || 0, bud = c => v.budget[c] || 0;
    const shown = D.cats.filter(c => act(c) > 0 || bud(c) > 0).sort((a, b) => act(b) - act(a) || bud(b) - bud(a));
    const scale = Math.max(1, ...shown.map(c => Math.max(act(c), bud(c))));
    D.cats.forEach(c => {
      const R = CR[c], i = shown.indexOf(c), A = act(c), B = bud(c);
      const go = (s, val, p = 'morph', d = 0) => first ? s.jump(val) : s.set(val, p, d);
      go(R.y, i < 0 ? shown.length * RH : i * RH);
      go(R.vis, i < 0 ? 0 : 1, 'snap');
      go(R.fw, (B ? Math.min(A, B) : A) / scale * 100, 'morph', i * .03);
      go(R.ow, B && A > B ? (A - B) / scale * 100 : 0, 'morph', i * .03 + .08);
      go(R.mx, B / scale * 100);
      go(R.a, A);
      R.bud = B;
    });
    first ? catsH.jump(shown.length * RH) : catsH.set(shown.length * RH);
    const tb = Object.values(v.budget).reduce((a, c) => a + c, 0);
    $('#cbud').textContent = tb ? `預算 ${fmt(tb)}` : '';
  }

  // ---------------------------------------------------------------- 重點卡
  const statsEl = $('#stats');
  function setStats(v) {
    const days = v.nDays, food = v.cats['飲食'] || 0, groc = v.cats['食材'] || 0;
    const fb = v.budget['飲食'] || 0;
    const big = v.biggest;
    const cards = [
      ['日均支出', `NT$${fmt(v.expense / Math.max(days, 1))}`, `${days} 天`],
      ['最大單筆', big ? `NT$${fmt(big[1])}` : '—', big ? `${big[2].slice(5).replace('-', '/')} ${big[0]}` : ''],
      ['外食預算用掉', fb ? `${Math.round(food / fb * 100)}%` : '—', fb ? `${fmt(food)} / ${fmt(fb)}` : ''],
      ['固定支出', `NT$${fmt(v.fixed)}`, v.expense ? `佔支出 ${Math.round(v.fixed / v.expense * 100)}%` : ''],
    ];
    const ratio = food + groc ? groc / (food + groc) : 0;
    statsEl.innerHTML = cards.map(c => `<div class="stat"><div class="l">${c[0]}</div><div class="v">${c[1]}</div><div class="s">${esc(c[2])}</div></div>`).join('') +
      `<div class="stat" style="grid-column:1/-1"><div class="l">自己煮 vs 外食</div>
        <div class="split"><i style="width:${(ratio * 100).toFixed(1)}%;background:var(--lime)"></i><i style="flex:1;background:var(--ink);opacity:.85"></i></div>
        <div class="s">食材 NT$${fmt(groc)}（${Math.round(ratio * 100)}%）· 外食 NT$${fmt(food)}</div></div>`;
  }

  // ---------------------------------------------------------------- 交易表
  function setRows(v) {
    const rows = v.rows.filter(r => !foodMode || r.category === '飲食');
    $('#ltitle').textContent = (foodMode ? '外食紀錄' : '交易') + ' · ' + v.range;
    $('#lcount').textContent = `${rows.length} 筆`;
    const sign = r => r.type === '收入' ? '+' : r.type === '支出' ? '−' : '';
    const cls = r => r.type === '收入' ? 'in' : r.type === '投資' ? 'iv' : '';
    $('#rows').innerHTML = rows.map((r, i) => `<tr class="${cls(r)}" style="animation-delay:${Math.min(i, 24) * 18}ms">
      <td>${r.date.slice(5).replace('-', '/')}</td><td>${esc(r.category)}${r.fixed ? ' <span class="c">固定</span>' : ''}</td>
      <td>${esc(r.item)}</td><td class="c">${esc(r.payment)}</td><td class="a">${sign(r)}${fmt(r.amount)}</td></tr>`).join('');
  }

  // ---------------------------------------------------------------- 外食開關(旋鈕兩邊各一條彈簧,萊姆綠從左側湧入)
  const tg = $('#toggle'), knob = $('#knob'), swfill = $('#swfill');
  const kL = spring(3), kR = spring(27), lime = spring(0);
  function setToggle(on) {
    foodMode = on; tg.setAttribute('aria-checked', on);
    kL.set(on ? 25 : 3, on ? 'trail' : 'lead'); kR.set(on ? 49 : 27, on ? 'lead' : 'trail');
    lime.set(on ? 1 : 0, 'morph');
    const v = V[cur]; setChart(v); setRows(v);
    const food = v.cats['飲食'] || 0, fb = v.budget['飲食'] || 0;
    if (on) toast(fb ? `${v.label}外食 NT$${fmt(food)}，是預算的 ${Math.round(food / fb * 100)}%` : `${v.label}外食 NT$${fmt(food)}`);
  }
  tg.onclick = () => setToggle(!foodMode);

  // ---------------------------------------------------------------- toast(底部計時線走完就收)
  const toastEl = $('#toast'), tv = spring(0); let toastAt = 0, toastUntil = 0;
  function toast(msg, dur = 3.2) {
    $('#ttext').textContent = msg; toastAt = now(); toastUntil = toastAt + dur + .6;
    tv.set(1, 'snap'); clearTimeout(toast.h); toast.h = setTimeout(() => tv.set(0, 'snap'), dur * 1000); kick();
  }

  // ---------------------------------------------------------------- ⌘K 指令面板
  const palbg = $('#palbg'), pin = $('#pin'), plist = $('#plist'), pv = spring(0);
  let pItems = [], pSel = 0;
  function cmds() {
    return [...V.map((v, i) => ({ t: `切換到 ${v.label}`, k: v.kind === 'month' ? v.key : '季報', run: () => select(i) })),
      { t: foodMode ? '關閉外食模式' : '只看外食', k: '開關', run: () => setToggle(!foodMode) }];
  }
  function drawPal() {
    const q = pin.value.trim().toLowerCase();
    pItems = cmds().filter(c => !q || (c.t + c.k).toLowerCase().includes(q));
    pSel = Math.min(pSel, Math.max(0, pItems.length - 1));
    plist.innerHTML = pItems.map((c, i) => `<div class="it${i === pSel ? ' sel' : ''}" data-i="${i}"><span class="b"></span>${esc(c.t)}<span class="k">${esc(c.k)}</span></div>`).join('');
  }
  function openPal(o) {
    if (o) { palbg.hidden = false; pin.value = ''; pSel = 0; drawPal(); pin.focus(); }
    pv.set(o ? 1 : 0, 'snap');
    if (!o) setTimeout(() => { if (pv.last === 0) palbg.hidden = true; }, 260);
  }
  $('#kbtn').onclick = () => openPal(true);
  palbg.onclick = e => { if (e.target === palbg) openPal(false); };
  plist.onclick = e => { const it = e.target.closest('.it'); if (it) { openPal(false); pItems[+it.dataset.i].run(); } };
  pin.oninput = () => { pSel = 0; drawPal(); };
  addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPal(palbg.hidden); return; }
    if (!palbg.hidden) {
      if (e.key === 'Escape') openPal(false);
      else if (e.key === 'ArrowDown') { pSel = (pSel + 1) % Math.max(1, pItems.length); drawPal(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { pSel = (pSel - 1 + pItems.length) % Math.max(1, pItems.length); drawPal(); e.preventDefault(); }
      else if (e.key === 'Enter' && pItems[pSel]) { openPal(false); pItems[pSel].run(); }
      return;
    }
    if (e.target.tagName === 'INPUT') return;
    if (e.key === 'ArrowRight') select(Math.min(V.length - 1, cur + 1));
    if (e.key === 'ArrowLeft') select(Math.max(0, cur - 1));
  });

  // ---------------------------------------------------------------- 切換視圖
  function select(i, first) {
    cur = i; const v = V[i];
    tabEls.forEach((b, k) => b.setAttribute('aria-selected', k === i));
    moveInd(i, first);
    const go = (s, val) => first ? s.jump(val) : s.set(val, 'morph');
    go(K.exp.s, v.expense); go(K.inc.s, v.income); go(K.net.s, v.income - v.expense); go(K.inv.s, v.invest);
    const fb = v.budget['飲食'] || 0, tb = Object.values(v.budget).reduce((a, c) => a + c, 0);
    K.exp.el.querySelector('.sub').textContent = tb ? `預算 ${fmt(tb)} · 用掉 ${Math.round(v.expense / tb * 100)}%` : '';
    K.inc.el.querySelector('.sub').textContent = v.floorUsed ? `以保底 ${fmt(v.floor)}/月計，季末補實際` : (v.income ? '' : '收入季末整理');
    K.net.el.querySelector('.sub').textContent = v.income ? `儲蓄率 ${Math.round((v.income - v.expense) / v.income * 100)}%` : '收入補齊後才準';
    K.inv.el.querySelector('.sub').textContent = v.invest ? '不計入支出' : '這段期間沒有扣款';
    setChart(v, first); setCats(v, first); setStats(v); setRows(v);
    if (!first) {
      const over = Object.keys(v.budget).filter(c => v.budget[c] > 0 && (v.cats[c] || 0) > v.budget[c]).sort((a, b) => (v.cats[b] / v.budget[b]) - (v.cats[a] / v.budget[a]));
      toast(over.length ? `${v.label}有 ${over.length} 類超出預算，最多的是${over[0]}（${Math.round(v.cats[over[0]] / v.budget[over[0]] * 100)}%）` : `${v.label}有預算的分類都沒超支`);
    }
    kick();
  }

  // ---------------------------------------------------------------- render:每一格畫面都只看彈簧當下的值
  function render(t) {
    const L = indL.get(t), R = indR.get(t);
    ind.style.left = Math.min(L, R) + 'px'; ind.style.width = Math.abs(R - L) + 'px';
    tabEls.forEach(b => {
      const a = b.offsetLeft, z = a + b.offsetWidth;
      const cover = clamp((Math.min(z, R) - Math.max(a, L)) / (z - a));
      b.style.color = cover > .5 ? '#fff' : '';
      b.style.opacity = mix(.62, 1, cover).toFixed(3);
    });
    for (const k in K) K[k].el.querySelector('.val').textContent = (k === 'net' && K[k].s.get(t) < -0.5 ? '−' : '') + 'NT$' + fmt(Math.abs(K[k].s.get(t)));
    K.net.el.className = 'kpi ' + (K.net.s.last < 0 ? 'neg' : K.net.s.last > 0 ? 'pos' : '');

    const cw = colW.get(t), gap = Math.max(1, Math.min(6, cw * .22));
    bars.forEach((b, k) => {
      const h = Math.max(0, b.h.get(t)), hi = clamp(b.hi.get(t)), s = b.el.style;
      s.left = (k * cw + gap / 2) + 'px'; s.width = Math.max(1, cw - gap) + 'px'; s.height = h + 'px';
      s.background = hi > .01 ? `rgb(${Math.round(mix(71, 168, hi))},${Math.round(mix(71, 240, hi))},${Math.round(mix(69, 122, hi))})` : '';
      s.opacity = k < pts.length ? 1 : clamp(h / 20);
    });
    bline.style.top = lineY.get(t) + 'px';
    document.querySelectorAll('.xl').forEach(x => x.style.left = ((+x.dataset.k + .5) * cw) + 'px');
    const drift = show(tip, tipV.get(t));
    // 放在長條旁邊,不蓋住自己指的那根:右半邊的長條把卡片放左側
    const right = hover >= 0 ? hover >= pts.length / 2 : tipSide;
    if (hover >= 0) tipSide = right;
    const off = cw / 2 + 10;
    tip.style.left = tipX.get(t) + 'px';
    tip.style.transform = `translate(${right ? `calc(-100% - ${off}px)` : off + 'px'}, ${(-drift).toFixed(2)}px)`;

    for (const c in CR) {
      const R2 = CR[c], vis = clamp(R2.vis.get(t));
      R2.el.style.transform = `translateY(${R2.y.get(t).toFixed(2)}px)`;
      R2.el.style.opacity = vis.toFixed(3); R2.el.style.visibility = vis < .01 ? 'hidden' : 'visible';
      const fw = Math.max(0, R2.fw.get(t)), ow = Math.max(0, R2.ow.get(t));
      R2.f.style.width = fw + '%'; R2.o.style.left = fw + '%'; R2.o.style.width = ow + '%';
      R2.f.style.borderRadius = ow > .3 ? '99px 0 0 99px' : '';
      R2.m.style.left = R2.mx.get(t) + '%'; R2.m.style.display = R2.bud ? '' : 'none';
      const A = R2.a.get(t);
      R2.amt.textContent = 'NT$' + fmt(A) + (R2.bud ? ` · ${Math.round(R2.a.last / R2.bud * 100)}%` : '');
    }
    catsEl.style.height = catsH.get(t) + 'px';

    knob.style.left = Math.min(kL.get(t), kR.get(t)) + 'px'; knob.style.width = Math.abs(kR.get(t) - kL.get(t)) + 'px';
    const lr = clamp(lime.get(t), 0, 1.1) * 70;
    swfill.style.clipPath = swfill.style.webkitClipPath = `circle(${lr.toFixed(1)}px at 0% 50%)`;
    knob.style.background = lime.get(t) > .5 ? '#111110' : '#fff';

    const d = show(toastEl, tv.get(t), 10, 8);
    toastEl.style.transform = `translate(-50%, ${d.toFixed(2)}px) scale(${mix(.94, 1, clamp(tv.get(t))).toFixed(4)})`;
    $('#tbar').style.width = (clamp((t - toastAt) / 3.2) * 100).toFixed(2) + '%';

    if (!palbg.hidden) {
      const p = clamp(pv.get(t)); palbg.style.opacity = p.toFixed(3);
      $('#pal').style.transform = `translateY(${((1 - p) * -12).toFixed(2)}px) scale(${mix(.96, 1, p).toFixed(4)})`;
      $('#pal').style.filter = p < .999 ? `blur(${((1 - p) * 6).toFixed(2)}px)` : 'none';
    }
  }

  addEventListener('resize', () => { moveInd(cur, true); colW.jump(chartEl.clientWidth / Math.max(pts.length, 1)); kick(); });
  $('#foot').textContent = `產生於 ${D.generated} · 資料來源 data/ledger.csv · ←/→ 切換,⌘K 指令面板`;
  if (!V.length) { $('#cempty').hidden = false; return; }
  select(cur, true); render(now());
  // 開場:長條從 0 錯開升起,分類條長出來
  requestAnimationFrame(() => {
    const v = V[cur]; bars.forEach(b => b.h.jump(0)); setChart(v);
    D.cats.forEach(c => { CR[c].fw.jump(0); CR[c].ow.jump(0); CR[c].a.jump(0); }); setCats(v);
    K.exp.s.jump(0); K.exp.s.set(v.expense); K.inv.s.jump(0); K.inv.s.set(v.invest);
    setTimeout(() => toast(`${v.label}支出 NT$${fmt(v.expense)}，按 ←／→ 或 ⌘K 切換期間`), 500);
  });
})();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="用示範假資料")
    ap.add_argument("--no-open", action="store_true", help="不自動開啟瀏覽器")
    args = ap.parse_args()

    budget, save = load_budget(args.demo)
    floor = baseline_income(BUDGET_FILES[1] if args.demo or not BUDGET_FILES[0].exists() else BUDGET_FILES[0])
    data = build(load_rows(args.demo), budget, save, floor)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    OUT.write_text(HTML.replace("__DATA__", payload), encoding="utf-8")

    tag = " (示範資料)" if args.demo else ""
    print(f"✅ 已產生儀表板{tag}:{OUT}")
    if not args.no_open and sys.platform == "darwin":
        subprocess.run(["open", str(OUT)], check=False)


if __name__ == "__main__":
    main()
