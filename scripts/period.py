"""帳期:以信用卡結帳日切月。過了結帳日就算下個月。

結帳日 23 號 → 「10 月」= 9/24 ~ 10/23。季 = 三個帳期(Q4 = 9/24 ~ 12/23)。
"""
from datetime import date, timedelta

CUTOFF = 23  # 信用卡結帳日,見 data/sean_profile.md


def period_of(d) -> str:
    """'2026-09-24' 或 date → 所屬帳期 'YYYY-MM'。"""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    y, m = d.year, d.month
    if d.day > CUTOFF:
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}"


def period_range(ym: str):
    """帳期 'YYYY-MM' → (起日, 迄日),含頭含尾。"""
    y, m = map(int, ym.split("-"))
    end = date(y, m, CUTOFF)
    py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
    return date(py, pm, CUTOFF + 1), end


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
    """budget.md 裡的「保底月收入」。收入季末才補,季中每期至少用這個數字算。"""
    import re
    from pathlib import Path
    p = Path(budget_file)
    if not p.exists():
        return 0.0
    m = re.search(r"保底月收入\s*\**\s*([\d,]+)", p.read_text(encoding="utf-8"))
    return float(m.group(1).replace(",", "")) if m else 0.0


def income_with_floor(actual_by_period: dict, periods, floor: float) -> float:
    """每期收入 = max(實際入帳, 保底)。"""
    return sum(max(actual_by_period.get(p, 0.0), floor) for p in periods)
