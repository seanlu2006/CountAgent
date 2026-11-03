"""CountAgent 的資料夾與使用者設定。所有腳本都從這裡拿路徑,不寫死。

資料夾決定順序:
  1. 環境變數 COUNTAGENT_DATA
  2. ~/.countagent/config.json 裡的 "data_dir"
  3. 預設 ~/CountAgent/data

使用者設定放在 <資料夾>/config.json,沒寫的欄位用 DEFAULTS。
"""
import json
import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_DIR / "templates"
POINTER = Path.home() / ".countagent" / "config.json"

DEFAULTS = {
    "language": "en",            # en | zh-TW,報表與儀表板的語言
    "currency": "USD",
    "currency_symbol": "$",
    "cycle_day": 0,              # 信用卡結帳日;0 = 用日曆月
    "default_payment": "card",
    "inbox": "",                 # 手機捕捉用的文字檔,空字串 = 不用收件匣
    "eat_out_category": "Dining",
    "groceries_category": "Groceries",
    "reports_dir": "",           # 空字串 = 資料夾旁邊的 reports/
}


def data_dir() -> Path:
    env = os.environ.get("COUNTAGENT_DATA")
    if env:
        return Path(env).expanduser()
    if POINTER.exists():
        try:
            d = json.loads(POINTER.read_text(encoding="utf-8")).get("data_dir")
        except (ValueError, OSError):
            d = None
        if d:
            return Path(d).expanduser()
    return Path.home() / "CountAgent" / "data"


def settings() -> dict:
    s = dict(DEFAULTS)
    f = data_dir() / "config.json"
    if f.exists():
        s.update(json.loads(f.read_text(encoding="utf-8")))
    return s


def template(name: str) -> Path:
    """依語言找範本檔,找不到就退回英文。"""
    lang = settings()["language"]
    for d in (TEMPLATES / lang, TEMPLATES / "en"):
        if (d / name).exists():
            return d / name
    return TEMPLATES / "en" / name


DATA = data_dir()
LEDGER = DATA / "ledger.csv"
BUDGET = DATA / "budget.md"
SECRETS = DATA / "secrets.json"
S = settings()
REPORTS = Path(S["reports_dir"]).expanduser() if S["reports_dir"] else DATA.parent / "reports"


def is_unfilled(path: Path) -> bool:
    """資料夾裡的 budget.md / profile.md 若跟範本一字不差,數字都是假的,不該拿來算。
    使用者改過任何一處就當作已填(避免改了數字卻因為留著範本說明而被忽略)。"""
    p = Path(path)
    if not p.exists() or TEMPLATES in p.resolve().parents:
        return False
    text = p.read_text(encoding="utf-8").strip()
    for t in TEMPLATES.glob(f"*/{p.stem}.example.md"):
        if t.read_text(encoding="utf-8").strip() == text:
            return True
    return False


if __name__ == "__main__":
    import sys
    if "--where" in sys.argv:
        ready = LEDGER.exists()
        print(f"data_dir : {DATA}")
        print(f"reports  : {REPORTS}")
        print(f"setup    : {'done' if ready else 'NOT DONE — run setup first (references/setup.md)'}")
        print("settings : " + json.dumps(S, ensure_ascii=False))
        todo = [n for n in ("budget.md", "profile.md") if is_unfilled(DATA / n)]
        if ready and todo:
            print(f"unfilled : {', '.join(todo)} still the template (made-up numbers, ignored by reports) — offer to fill in")
        if ready and S.get("inbox"):
            inbox = Path(S["inbox"]).expanduser()
            print(f"inbox    : {inbox} ({'found' if inbox.exists() else 'missing'})")
