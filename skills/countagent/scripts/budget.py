"""讀 budget.md。中英文標題都認得,所有腳本共用這一份解析。

認得的內容(冒號、表格格式別動):
  ## 每月分類預算 / ## Monthly category budget   | 分類 | 金額 |
  ## 單期加碼 / ## One-off extras                 | 帳期 YYYY-MM | 分類 | 金額 | 說明 |
  每月淨存目標: N / Monthly savings target: N
  每季淨存目標: N / Quarterly savings target: N
  保底月收入 N / Baseline monthly income: N
"""
import re
from pathlib import Path

from cfg import is_unfilled

CATS = ("每月分類預算", "monthly category budget")
EXTRAS = ("單期加碼", "one-off extras")
SAVE_M = ("每月淨存目標", "monthly savings target")
SAVE_Q = ("每季淨存目標", "quarterly savings target")
BASE = ("保底月收入", "baseline monthly income")
HEADERS = {"分類", "項目", "帳期", "category", "item", "period"}

NUM = r"(\d[\d,]*(?:\.\d+)?)"


def _has(line: str, keys) -> bool:
    low = line.lower()
    return any(k in low for k in keys)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def load(path) -> dict:
    out = {"cats": {}, "save_month": 0.0, "save_quarter": 0.0, "baseline": 0.0, "extras": {}}
    p = Path(path)
    if not p.exists() or is_unfilled(p):
        return out
    section = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            section = "cats" if _has(line, CATS) else "extras" if _has(line, EXTRAS) else None
            continue
        if _has(line, SAVE_M):
            m = re.search(NUM, line.split(":")[-1])
            out["save_month"] = _num(m.group(1)) if m else 0.0
        elif _has(line, SAVE_Q):
            m = re.search(NUM, line.split(":")[-1])
            out["save_quarter"] = _num(m.group(1)) if m else 0.0
        elif _has(line, BASE) and not out["baseline"]:
            m = re.search(r"(?:保底月收入|baseline monthly income)\W*" + NUM, line, re.I)
            out["baseline"] = _num(m.group(1)) if m else 0.0
        elif section == "cats":
            m = re.match(r"\s*\|\s*([^|]+?)\s*\|\s*" + NUM + r"\s*\|", line)
            if m and m.group(1).lower() not in HEADERS:
                out["cats"][m.group(1)] = _num(m.group(2))
        elif section == "extras":
            m = re.match(r"\s*\|\s*(\d{4}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*" + NUM + r"\s*\|", line)
            if m:
                cat = out["extras"].setdefault(m.group(1), {})
                cat[m.group(2)] = cat.get(m.group(2), 0.0) + _num(m.group(3))
    return out
