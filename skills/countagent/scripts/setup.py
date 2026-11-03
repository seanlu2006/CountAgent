#!/usr/bin/env python3
"""第一次設定:建立資料夾、複製範本、寫入 config.json。已存在的檔案一律不覆蓋。

用法:
    python3 setup.py --language en --currency USD --symbol '$' --cycle-day 0 \
        [--data-dir ~/CountAgent/data] [--payment card] [--inbox PATH] \
        [--eat-out Dining --groceries Groceries]
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfg  # noqa: E402

FILES = {  # 範本檔 → 資料夾裡的檔名
    "ledger.example.csv": "ledger.csv",
    "budget.example.md": "budget.md",
    "profile.example.md": "profile.md",
    "categories.md": "categories.md",
}

NAMES = {
    "en": ("Dining", "Groceries", "card"),
    "zh-TW": ("飲食", "食材", "信用卡"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir")
    ap.add_argument("--language", default="en", choices=sorted(NAMES))
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--symbol", default="$")
    ap.add_argument("--cycle-day", type=int, default=0)
    ap.add_argument("--payment")
    ap.add_argument("--inbox", default="")
    ap.add_argument("--eat-out")
    ap.add_argument("--groceries")
    a = ap.parse_args()

    eat, groc, pay = NAMES[a.language]
    data = Path(a.data_dir).expanduser() if a.data_dir else cfg.data_dir()
    data.mkdir(parents=True, exist_ok=True)

    # 不是預設位置就寫指標檔,之後所有腳本都找得到
    default = Path.home() / "CountAgent" / "data"
    if data.resolve() != default.resolve():
        cfg.POINTER.parent.mkdir(parents=True, exist_ok=True)
        cfg.POINTER.write_text(json.dumps({"data_dir": str(data)}, indent=2), encoding="utf-8")

    conf = data / "config.json"
    if not conf.exists():
        conf.write_text(json.dumps({
            "language": a.language,
            "currency": a.currency,
            "currency_symbol": a.symbol,
            "cycle_day": a.cycle_day,
            "default_payment": a.payment or pay,
            "inbox": a.inbox,
            "eat_out_category": a.eat_out or eat,
            "groceries_category": a.groceries or groc,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    src = cfg.TEMPLATES / a.language
    made = []
    for t, name in FILES.items():
        dst = data / name
        if dst.exists():
            continue
        if t == "ledger.example.csv":  # 帳本只留表頭,範例資料不要混進真帳
            header = (src / t).read_text(encoding="utf-8").splitlines()[0]
            dst.write_text(header + "\n", encoding="utf-8")
        else:
            shutil.copy(src / t, dst)
        made.append(name)
    (data / "inbox_archive.txt").touch()

    print(f"✅ data folder: {data}")
    print(f"   created: {', '.join(made) or '(nothing new — existing files kept)'}")
    print(f"   settings: {conf}")


if __name__ == "__main__":
    main()
