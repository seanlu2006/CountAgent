#!/usr/bin/env python3
"""把載具 App / 電子發票平台匯出的明細檔(CSV)匯入 ledger.csv。

不挑欄位名稱:自動辨識「日期 / 金額 / 店家 / 發票號碼」這幾欄,
台灣常見的 Big5/UTF-8 編碼都會自動嘗試。

用法:
    python3 scripts/import_csv.py 你的匯出檔.csv
    python3 scripts/import_csv.py 你的匯出檔.csv --dry-run     # 只預覽不寫入

匯入後:用發票號碼去重、依店家自動猜分類、note 標記 [發票匯入,分類待確認]。
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from categorize import categorize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "ledger.csv"
FIELDS = ["id", "date", "type", "amount", "category", "item", "payment", "note", "receipt"]

# 欄位辨識:看表頭含哪些關鍵字(小寫比對)
COL_HINTS = {
    "date":   ["發票日期", "交易日期", "日期", "消費日", "date"],
    "amount": ["總金額", "金額", "小計", "消費金額", "amount", "total"],
    "seller": ["商店名稱", "店家", "商家", "賣方", "商店", "店名", "seller", "store"],
    "invnum": ["發票號碼", "發票字軌", "號碼", "invnum", "invoicenumber"],
}


def read_rows(path: Path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        sys.exit("❌ 無法判讀檔案編碼,請另存成 UTF-8 CSV 再試。")

    # 嗅探分隔符號
    sample = text[:2048]
    delim = "\t" if sample.count("\t") > sample.count(",") else ","
    return list(csv.DictReader(text.splitlines(), delimiter=delim))


def map_columns(headers):
    found = {}
    low = {h: (h or "").strip().lower() for h in headers}
    for key, hints in COL_HINTS.items():
        for h in headers:
            if any(hint.lower() in low[h] for hint in hints):
                found[key] = h
                break
    return found


def to_num(s):
    try:
        return abs(float(str(s).replace(",", "").replace("$", "").strip()))
    except (ValueError, AttributeError):
        return 0.0


def existing_invoice_nums():
    nums = set()
    if LEDGER.exists():
        with LEDGER.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                note = r.get("note", "")
                if "發票:" in note:
                    nums.add(note.split("發票:")[1].split()[0].strip())
    return nums


def last_id():
    last = 0
    if LEDGER.exists():
        with LEDGER.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    last = max(last, int(r["id"]))
                except (ValueError, KeyError):
                    pass
    return last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="匯出的 CSV 檔路徑")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.file).expanduser()
    if not path.exists():
        sys.exit(f"❌ 找不到檔案:{path}")

    rows = read_rows(path)
    if not rows:
        sys.exit("❌ 檔案沒有資料列。")

    cols = map_columns(rows[0].keys())
    print(f"🔎 辨識到欄位:{cols if cols else '(無法辨識,請看下方提示)'}")
    if "date" not in cols or "amount" not in cols:
        sys.exit(
            "❌ 找不到「日期」或「金額」欄。請把檔案的表頭貼給我,我幫你調對應規則。\n"
            f"   檔案表頭:{list(rows[0].keys())}"
        )

    seen = existing_invoice_nums()
    next_id = last_id() + 1
    new_rows = []

    for r in rows:
        d = (r.get(cols["date"]) or "").strip().replace("/", "-")[:10]
        amt = to_num(r.get(cols["amount"]))
        if not d or amt == 0:
            continue
        seller = (r.get(cols.get("seller", "")) or "").strip() if cols.get("seller") else ""
        inv = (r.get(cols.get("invnum", "")) or "").strip() if cols.get("invnum") else ""
        if inv and inv in seen:
            continue
        if inv:
            seen.add(inv)
        note = f"發票:{inv} [發票匯入,分類待確認]" if inv else "[發票匯入,分類待確認]"
        new_rows.append({
            "id": next_id,
            "date": d,
            "type": "支出",
            "amount": f"{amt:.0f}",
            "category": categorize(seller),
            "item": seller or "電子發票",
            "payment": "其他",
            "note": note,
            "receipt": "",
        })
        next_id += 1

    if not new_rows:
        print("✅ 沒有新資料要匯入(可能都記過了)。")
        return

    print(f"\n📥 將新增 {len(new_rows)} 筆:")
    for r in new_rows:
        print(f"   #{r['id']} {r['date']} {r['amount']:>7}  {r['category']} · {r['item']}")

    if args.dry_run:
        print("\n(--dry-run,未寫入)")
        return

    write_header = not LEDGER.exists() or LEDGER.stat().st_size == 0
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        for r in new_rows:
            w.writerow(r)
    print(f"\n✅ 已寫入 {LEDGER}。分類是自動猜的,有錯跟我說 id 我改。")


if __name__ == "__main__":
    main()
