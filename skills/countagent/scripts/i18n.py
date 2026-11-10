"""報表文字(zh-TW / en)與帳本欄位值的正規化。

帳本可以用中文或英文寫 type(支出 / expense…),腳本內部一律轉成英文代號比較。
"""
import re
import sys

from cfg import S

LANG = "zh-TW" if str(S.get("language", "en")).lower().startswith("zh") else "en"
SYM = S.get("currency_symbol", "$")
# 小數位:台幣、日圓這類沒有小數的幣別用 0,其餘 2;config 可用 "decimals" 指定
_ZERO_DEC = {"TWD", "JPY", "KRW", "VND", "IDR", "CLP", "HUF", "ISK"}
DEC = int(S.get("decimals", 0 if str(S.get("currency", "")).upper() in _ZERO_DEC else 2))
CW = 6 if LANG == "zh-TW" else 14  # 分類欄寬(中文字佔兩格)

_TYPES = {
    "expense": ("支出", "expense", "expenses", "spend", "spending"),
    "income": ("收入", "income"),
    "investment": ("投資", "investment", "invest"),
    "transfer": ("轉帳", "transfer"),
}
_LOOKUP = {w.lower(): k for k, ws in _TYPES.items() for w in ws}


def kind(t: str) -> str:
    """帳本的 type 欄 → expense / income / investment / transfer(認不得就原樣)。"""
    return _LOOKUP.get((t or "").strip().lower(), (t or "").strip())


def amount(v):
    """金額欄 → float;"1,200"、"£5"、" 12.5 " 都吃。讀不懂回傳 None。"""
    s = re.sub(r"[^\d.\-]", "", str(v or ""))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def fmt(n) -> str:
    return f"{n:,.{DEC}f}"


def warn_bad(bad: list):
    """把讀不懂金額的列印到 stderr,不默默吞掉。"""
    if bad:
        print(t("bad_rows", n=len(bad), ids=", ".join(bad[:10])), file=sys.stderr)


def is_fixed(note: str) -> bool:
    n = (note or "").lower()
    return "固定" in n or "fixed" in n


def other() -> str:
    return "其他" if LANG == "zh-TW" else "Other"


def month_label(ym: str) -> str:
    m = int(ym[5:])
    if LANG == "zh-TW":
        return f"{m}月"
    return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]


_MSG = {
    "zh-TW": {
        "no_ledger": "找不到帳本:{path}",
        "m_title": "📊 {ym} 月報  ({a} ~ {b},依信用卡帳期)",
        "m_title_cal": "📊 {ym} 月報  ({a} ~ {b})",
        "m_rows": "筆數    : {n}",
        "m_income_floor": "總收入  : {floor}   (實際入帳 {actual},以保底計;收入季末補)",
        "m_income": "總收入  : {v}",
        "m_expense": "總支出  : {v}",
        "m_net": "結餘    : {v}",
        "m_invest": "定期投資: {v}",
        "m_cats": "\n支出分類(由大到小):",
        "q_title": "📈 {y} 第 {q} 季財報  ({a} ~ {b},依信用卡帳期)   已過 {e}/3 月",
        "q_title_cal": "📈 {y} 第 {q} 季財報  ({a} ~ {b})   已過 {e}/3 月",
        "q_income": "  總收入    {v:>12}",
        "q_floored": "   (含保底估計:{ms})",
        "q_expense": "  總支出    {v:>12}",
        "q_net": "  淨結餘    {v:>12}   (儲蓄率 {r:.0f}%)",
        "q_invest": "  其中投資  {v:>12}   (定期定額實際扣款,已含在淨結餘)",
        "q_left": "  留在帳上  {v:>12}   (淨結餘扣掉投資)",
        "q_ok": "✅ 達標", "q_behind": "⚠️ 落後",
        "q_save_h": "── 儲蓄目標 ──  (淨結餘計,含投資)",
        "q_save": "  季目標 {t} · 到目前應達 {p} · 實際 {r}  {s}",
        "q_months_h": "── 每月收支 ──",
        "q_month": "  {m} ({rng})   收 {i:>8}   支 {x:>8}   投 {v:>8}   餘 {n:>8}",
        "q_fixed_h": "── 固定 vs 變動支出 ──",
        "q_fixed": "  固定 {f:>10} ({fp:.0f}%)   變動 {v:>10} ({vp:.0f}%)",
        "q_bud_h": "── 預算 vs 實際 ──  (季預算＝月預算×3;進度以已過 {e} 月折算)",
        "q_bud_cols": ("分類", "季預算", "實際", "應花", "狀態"),
        "q_over": "⚠️超",
        "q_cats_h": "── 支出分類 ──",
        "o_save_ok": "儲蓄進度達標:淨結餘 {r},超出階段目標 {d}。",
        "o_save_bad": "儲蓄落後:淨結餘 {r},比階段目標少 {d}——本季後段留意變動支出。",
        "o_over": "超出預算節奏的分類:{c}。",
        "o_top": "最大支出類別:{c} {v}。",
        "o_invest": "本季已定期投入 {v} 到投資,這是你真正的資產累積。",
        "md_title": "# {y} Q{q} 財報",
        "md_obs": "## 觀察與建議",
        "md_saved": "\n✅ 已存季報:{p}",
        "sep": "、",
        "d_done": "✅ 已產生儀表板{tag}:{p}",
        "d_demo": " (示範資料)",
        "bad_rows": "⚠️ {n} 列金額讀不懂,已略過(id:{ids})",
        "r_title": "🧾 對帳  {a} ~ {b}  (付款方式:{p},日期容差 ±{w} 天)",
        "r_stmt": "對帳單支出: {v}  ({n} 筆)",
        "r_ledger": "帳本對應  : {v}  ({n} 筆)",
        "r_gap": "差額      : {v}  (對帳單 − 帳本)",
        "r_ok": "✅ 兩邊完全對上",
        "r_matched": "\n對上 {n} 筆,其中 {far} 筆日期差幾天,{pay} 筆付款方式不同",
        "r_pay": "\n對上了,但帳本記的付款方式不同:",
        "r_only_stmt": "\n只在對帳單 {n} 筆,合計 {v} (可能漏記):",
        "r_only_ledger": "\n只在帳本 {n} 筆,合計 {v} (可能記錯付款方式或金額,或還沒入帳):",
        "r_near_end": "  ← 接近對帳單最後一天,可能列在下一期",
        "r_excluded": "\n未列入比較:轉帳 {t} 筆;入帳或退款 {i} 筆,合計 {v}",
        "r_no_spend": "這份對帳單在指定期間沒有支出。",
        "r_flip": "⚠️ 大部分列被判成入帳。如果這份信用卡對帳單的消費是正數,請加 --flip 重跑。",
        "r_no_payment": "⚠️ 帳本沒有付款方式「{p}」的紀錄。帳本裡有:{seen}。請用 --payment 指定正確名稱。",
        "r_unreadable": "⚠️ {n} 列的日期或金額讀不懂,已略過(第一列:{first})",
    },
    "en": {
        "no_ledger": "Ledger not found: {path}",
        "m_title": "📊 {ym} summary  ({a} – {b}, billing period)",
        "m_title_cal": "📊 {ym} summary  ({a} – {b})",
        "m_rows": "Entries   : {n}",
        "m_income_floor": "Income    : {floor}   (recorded {actual}; baseline used until income is entered)",
        "m_income": "Income    : {v}",
        "m_expense": "Spending  : {v}",
        "m_net": "Net       : {v}",
        "m_invest": "Invested  : {v}",
        "m_cats": "\nSpending by category:",
        "q_title": "📈 {y} Q{q} statement  ({a} – {b}, billing periods)   {e}/3 periods in",
        "q_title_cal": "📈 {y} Q{q} statement  ({a} – {b})   {e}/3 months in",
        "q_income": "  Income       {v:>12}",
        "q_floored": "   (baseline used for: {ms})",
        "q_expense": "  Spending     {v:>12}",
        "q_net": "  Net          {v:>12}   (savings rate {r:.0f}%)",
        "q_invest": "  of which inv.{v:>12}   (actual contributions, already inside net)",
        "q_left": "  Kept as cash {v:>12}   (net minus investments)",
        "q_ok": "✅ on track", "q_behind": "⚠️ behind",
        "q_save_h": "── Savings target ──  (net, including investments)",
        "q_save": "  Quarter target {t} · due so far {p} · actual {r}  {s}",
        "q_months_h": "── By period ──",
        "q_month": "  {m} ({rng})   in {i:>8}   out {x:>8}   inv {v:>8}   net {n:>8}",
        "q_fixed_h": "── Fixed vs variable spending ──",
        "q_fixed": "  Fixed {f:>10} ({fp:.0f}%)   Variable {v:>10} ({vp:.0f}%)",
        "q_bud_h": "── Budget vs actual ──  (quarter = monthly × 3; pace after {e} periods)",
        "q_bud_cols": ("Category", "Budget", "Actual", "Pace", "Status"),
        "q_over": "⚠️ over",
        "q_cats_h": "── Spending by category ──",
        "o_save_ok": "Savings on track: net {r}, {d} ahead of the target so far.",
        "o_save_bad": "Savings behind: net {r}, {d} short of the target so far — watch variable spending.",
        "o_over": "Ahead of budget pace: {c}.",
        "o_top": "Largest category: {c} {v}.",
        "o_invest": "Invested {v} this quarter.",
        "md_title": "# {y} Q{q} statement",
        "md_obs": "## Observations",
        "md_saved": "\n✅ Saved: {p}",
        "sep": ", ",
        "d_done": "✅ Dashboard written{tag}: {p}",
        "d_demo": " (demo data)",
        "bad_rows": "⚠️ {n} rows have an unreadable amount and were skipped (id: {ids})",
        "r_title": "🧾 Reconciliation  {a} – {b}  (payment: {p}, dates within ±{w} days)",
        "r_stmt": "Statement spending: {v}  ({n} rows)",
        "r_ledger": "Ledger equivalent : {v}  ({n} rows)",
        "r_gap": "Gap               : {v}  (statement − ledger)",
        "r_ok": "✅ Both sides match",
        "r_matched": "\nMatched {n} rows: {far} with dates a few days apart, {pay} with a different payment method",
        "r_pay": "\nMatched, but the ledger has a different payment method:",
        "r_only_stmt": "\nOnly on the statement: {n} rows, total {v} (possibly not logged):",
        "r_only_ledger": "\nOnly in the ledger: {n} rows, total {v} (wrong payment method or amount, or not posted yet):",
        "r_near_end": "  ← near the statement's last day, may appear on the next one",
        "r_excluded": "\nNot compared: {t} transfers; {i} money-in or refund rows, total {v}",
        "r_no_spend": "No spending on this statement in the chosen dates.",
        "r_flip": "⚠️ Most rows came out as money in. If this card statement lists purchases as positive numbers, re-run with --flip.",
        "r_no_payment": "⚠️ The ledger has no rows paid by \"{p}\". It has: {seen}. Name the right one with --payment.",
        "r_unreadable": "⚠️ {n} rows skipped: unreadable date or amount (first: {first})",
    },
}


def t(key: str, **kw):
    msg = _MSG[LANG][key]
    return msg.format(**kw) if kw else msg


# 儀表板前端文字({x} 由 JS 代入)
DASH = {
    "zh-TW": {
        "htmlLang": "zh-Hant", "palette": "指令面板", "exp": "支出", "inc": "收入", "net": "結餘", "inv": "定期投資",
        "daily": "每日", "weekly": "每週", "spend": "支出", "eatOut": "外食", "budget": "預算 ", "eatBudget": "外食預算 ",
        "onlyEatOut": "只看外食", "empty": "這段期間還沒有支出", "catVsBud": "分類 vs 預算", "highlights": "重點",
        "tx": "交易", "eatLog": "外食紀錄", "cols": ["日期", "分類", "品項", "付款", "金額"],
        "palPh": "切換月份、季、外食模式…", "noRec": "沒有紀錄", "budgetN": "預算 {n}",
        "avgDay": "日均支出", "days": "{n} 天", "biggest": "最大單筆", "eatUsed": "外食預算用掉", "fixed": "固定支出",
        "fixedShare": "佔支出 {n}%", "cookVsOut": "自己煮 vs 外食", "grocLine": "{g}（{p}%）· 外食 {f}",
        "count": "{n} 筆", "fixedTag": "固定", "toastEat": "{l}外食 {f}，是預算的 {p}%", "toastEat0": "{l}外食 {f}",
        "goTo": "切換到 {l}", "quarter": "季報", "eatOff": "關閉外食模式", "switch": "開關",
        "budUsed": "預算 {b} · 用掉 {p}%", "floorUsed": "以保底 {f}/月計，季末補實際", "incLater": "收入季末整理",
        "rate": "儲蓄率 {p}%", "netLater": "收入補齊後才準", "invNot": "不計入支出", "invNone": "這段期間沒有扣款",
        "over": "{l}有 {n} 類超出預算，最多的是{c}（{p}%）", "noOver": "{l}有預算的分類都沒超支",
        "foot": "產生於 {d} · 資料來源 ledger.csv · ←/→ 切換,⌘K 指令面板", "hello": "{l}支出 {e}，按 ←／→ 或 ⌘K 切換期間",
    },
    "en": {
        "htmlLang": "en", "palette": "Command palette", "exp": "Spending", "inc": "Income", "net": "Net", "inv": "Invested",
        "daily": "Daily ", "weekly": "Weekly ", "spend": "spending", "eatOut": "eating out", "budget": "budget ",
        "eatBudget": "eating-out budget ", "onlyEatOut": "Eating out only", "empty": "No spending in this period yet",
        "catVsBud": "Category vs budget", "highlights": "Highlights", "tx": "Transactions", "eatLog": "Eating out",
        "cols": ["Date", "Category", "Item", "Paid with", "Amount"], "palPh": "Jump to a month, quarter, eating-out mode…",
        "noRec": "Nothing recorded", "budgetN": "Budget {n}", "avgDay": "Per day", "days": "{n} days",
        "biggest": "Largest", "eatUsed": "Eating-out budget used", "fixed": "Fixed costs", "fixedShare": "{n}% of spending",
        "cookVsOut": "Cooking vs eating out", "grocLine": "{g} ({p}%) · eating out {f}", "count": "{n} entries",
        "fixedTag": "fixed", "toastEat": "{l}: eating out {f}, {p}% of budget", "toastEat0": "{l}: eating out {f}",
        "goTo": "Go to {l}", "quarter": "quarter", "eatOff": "Show all spending", "switch": "toggle",
        "budUsed": "Budget {b} · {p}% used", "floorUsed": "Baseline {f}/period until income is entered",
        "incLater": "Income not entered yet", "rate": "Savings rate {p}%", "netLater": "Accurate once income is in",
        "invNot": "Not counted as spending", "invNone": "No contributions this period",
        "over": "{l}: {n} categories over budget, most is {c} ({p}%)", "noOver": "{l}: every budgeted category is within budget",
        "foot": "Generated {d} · source ledger.csv · ←/→ to switch, ⌘K for commands", "hello": "{l}: spent {e}. Use ←/→ or ⌘K to switch",
    },
}
