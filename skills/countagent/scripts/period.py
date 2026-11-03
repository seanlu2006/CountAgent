"""帳期:以信用卡結帳日切月,過了結帳日就算下個月。

結帳日 23 號 → 「10 月」= 9/24 ~ 10/23;季 = 三個帳期(Q4 = 9/24 ~ 12/23)。
結帳日在 <資料夾>/config.json 的 cycle_day;0 = 一般日曆月。
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

import budget
from cfg import S

CUTOFF = int(S.get("cycle_day") or 0)


def _end(y: int, m: int) -> date:
    """帳期 y-m 的最後一天(結帳日大於當月天數時取月底)。"""
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(CUTOFF, last) if CUTOFF else last)


def period_of(d) -> str:
    """'2026-09-24' 或 date → 所屬帳期 'YYYY-MM'。"""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    y, m = d.year, d.month
    if d > _end(y, m):
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}"


def period_range(ym: str):
    """帳期 'YYYY-MM' → (起日, 迄日),含頭含尾。"""
    y, m = map(int, ym.split("-"))
    py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
    return _end(py, pm) + timedelta(days=1), _end(y, m)


def period_days(ym: str, until: date | None = None):
    """帳期內的每一天;給 until 就截到那天為止。"""
    start, end = period_range(ym)
    if until and until < end:
        end = until
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def quarter_of(ym: str):
    y, m = map(int, ym.split("-"))
    return y, (m - 1) // 3 + 1


def baseline_income(budget_file) -> float:
    """budget.md 裡的保底月收入。收入晚記時,每期至少用這個數字算。"""
    return budget.load(budget_file)["baseline"]


def floor_for(p: str, floor: float, first: str = "") -> float:
    """某期該套的保底收入。first = 帳本最早一筆的日期:
    之前的期不套;開始記帳的那一期按記帳天數比例折算。"""
    if not first or not floor:
        return floor
    fp = period_of(first)
    if p < fp:
        return 0.0
    if p > fp:
        return floor
    a, b = period_range(p)
    d0 = date.fromisoformat(first)
    return floor * ((b - d0).days + 1) / ((b - a).days + 1)


def income_with_floor(actual_by_period: dict, periods, floor: float, first: str = "") -> float:
    """每期收入 = max(實際入帳, 保底)。"""
    return sum(max(actual_by_period.get(p, 0.0), floor_for(p, floor, first)) for p in periods)


def first_date(rows) -> str:
    """帳本最早一筆的日期;空帳本回傳空字串。"""
    dates = [r["date"] for r in rows if r.get("date")]
    return min(dates) if dates else ""


def budget_extras(budget_file) -> dict:
    """budget.md「單期加碼」表 → {帳期: {分類: 金額}}。只加在指定帳期。"""
    return budget.load(budget_file)["extras"]
