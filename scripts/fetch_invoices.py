#!/usr/bin/env python3
"""從財政部電子發票平台,用手機條碼載具自動撈發票,匯入 ledger.csv。

用法:
    python3 scripts/fetch_invoices.py                 # 抓最近 60 天
    python3 scripts/fetch_invoices.py --days 30        # 抓最近 30 天
    python3 scripts/fetch_invoices.py --start 2026/05/01 --end 2026/05/31
    python3 scripts/fetch_invoices.py --dry-run        # 只看會匯入什麼,不寫檔

憑證放在 data/secrets.json(由 secrets.example.json 複製):
    { "app_id": "...", "card_no": "/XXXXXXX", "card_encrypt": "驗證碼" }

只純標準函式庫,不需 pip 安裝。
財政部 API: POST https://api.einvoice.nat.gov.tw/PB2CAPIVAN/invServ/InvServ
"""
import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from categorize import categorize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "ledger.csv"
SECRETS = ROOT / "data" / "secrets.json"

API_URL = "https://api.einvoice.nat.gov.tw/PB2CAPIVAN/invServ/InvServ"
CARD_TYPE = "3J0002"  # 手機條碼
FIELDS = ["id", "date", "type", "amount", "category", "item", "payment", "note", "receipt"]


def load_secrets():
    if not SECRETS.exists():
        sys.exit(
            f"❌ 找不到憑證檔 {SECRETS}\n"
            f"   請複製 data/secrets.example.json 成 data/secrets.json 並填入 app_id / card_no / card_encrypt。"
        )
    cfg = json.loads(SECRETS.read_text(encoding="utf-8"))
    for k in ("app_id", "card_no", "card_encrypt"):
        if not cfg.get(k) or str(cfg[k]).startswith("你"):
            sys.exit(f"❌ data/secrets.json 的 {k} 還沒填。")
    return cfg


def api_post(action: str, cfg: dict, extra: dict) -> dict:
    now = int(time.time())
    params = {
        "version": "0.3",
        "action": action,
        "cardType": CARD_TYPE,
        "cardNo": cfg["card_no"],
        "cardEncrypt": cfg["card_encrypt"],
        "appID": cfg["app_id"],
        "timeStamp": str(now + 10),
        "expTimeStamp": str(now + 1000),
    }
    params.update(extra)
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "CountAgent/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_headers(cfg, start, end):
    res = api_post("carrierInvChk", cfg, {
        "startDate": start,
        "endDate": end,
        "onlyWinningInv": "N",
    })
    if str(res.get("code")) != "200":
        sys.exit(f"❌ API 回應錯誤 code={res.get('code')}: {res.get('msg')}")
    return res.get("details", [])


def existing_invoice_nums():
    nums = set()
    if not LEDGER.exists():
        return nums
    with LEDGER.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            note = r.get("note", "")
            if "發票:" in note:
                nums.add(note.split("發票:")[1].split()[0].strip())
    return nums


def last_id():
    if not LEDGER.exists():
        return 0
    last = 0
    with LEDGER.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                last = max(last, int(r["id"]))
            except (ValueError, KeyError):
                pass
    return last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_secrets()

    if args.start and args.end:
        start, end = args.start, args.end
    else:
        today = date.today()
        start = (today - timedelta(days=args.days)).strftime("%Y/%m/%d")
        end = today.strftime("%Y/%m/%d")

    print(f"🔎 查詢載具發票 {start} ~ {end} …")
    headers = fetch_headers(cfg, start, end)
    print(f"   回傳 {len(headers)} 筆發票。")

    seen = existing_invoice_nums()
    next_id = last_id() + 1
    new_rows = []

    for h in headers:
        inv = (h.get("invNum") or "").strip()
        if not inv or inv in seen:
            continue
        seen.add(inv)
        inv_date = (h.get("invDate") or "").replace("/", "-")
        seller = (h.get("sellerName") or "").strip()
        amount = h.get("amount") or "0"
        try:
            amt = abs(float(str(amount).replace(",", "")))
        except ValueError:
            amt = 0
        new_rows.append({
            "id": next_id,
            "date": inv_date,
            "type": "支出",
            "amount": f"{amt:.0f}",
            "category": categorize(seller),
            "item": seller or "電子發票",
            "payment": "其他",
            "note": f"發票:{inv} [發票匯入,分類待確認]",
            "receipt": "",
        })
        next_id += 1

    if not new_rows:
        print("✅ 沒有新發票要匯入(都已記過了)。")
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
