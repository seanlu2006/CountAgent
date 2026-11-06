#!/usr/bin/env python3
"""Import a bank or credit-card statement exported as CSV into ledger.csv.

Works with most banks without configuration: it finds the date, description and
amount columns (a single signed amount, or separate debit / credit columns),
works out the date order and the decimal separator, and skips rows already imported.

Usage:
    python3 import_bank.py statement.csv --dry-run          # preview, write nothing
    python3 import_bank.py statement.csv --payment card     # a credit-card statement
    python3 import_bank.py statement.csv --payment bank     # a bank-account statement
Options:
    --flip               amounts are positive for spending (some card statements)
    --dates dmy|mdy|ymd  date order, when the file alone can't tell (e.g. 03/04/2026)
    --map date=Posted,amount=Value,desc=Details   name the columns yourself

Every imported row gets a note `bank:<fingerprint> [bank import: check category]`
(`[銀行匯入,分類待確認]` in a Chinese ledger).
Rows that look like something already in the ledger (same date and amount, not
imported) are skipped and listed as possible duplicates, so nothing is counted twice.
Standard library only.
"""
import argparse
import csv
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfg import LEDGER, S  # noqa: E402
from i18n import LANG, amount, kind  # noqa: E402

FIELDS = ["id", "date", "type", "amount", "category", "item", "payment", "note", "receipt"]

# Header keywords, lower-case. First match wins, so the more specific words come first.
COL_HINTS = {
    "date":   ["transaction date", "posting date", "posted date", "value date", "booking date",
               "date", "交易日期", "入帳日期", "日期", "buchungstag", "valuta", "datum", "fecha", "data"],
    "desc":   ["description", "details", "narrative", "merchant", "payee", "memo", "reference",
               "transaction", "name", "說明", "摘要", "備註", "商店", "verwendungszweck", "buchungstext",
               "beschreibung", "auftraggeber", "concepto", "libellé", "libelle"],
    "debit":  ["debit", "withdrawal", "paid out", "money out", "out", "支出", "提款"],
    "credit": ["credit", "deposit", "paid in", "money in", "in", "存入", "收入"],
    "amount": ["amount", "value", "sum", "金額", "betrag", "importe", "montant"],
}
SKIP_HEADERS = ("balance", "餘額", "saldo", "solde")

# Keyword → category. Names follow the ledger's language; anything unmatched → Other.
CATS = {
    "Dining": ["restaurant", "cafe", "coffee", "starbucks", "mcdonald", "kfc", "burger", "pizza",
               "deliveroo", "uber eats", "ubereats", "doordash", "just eat", "grubhub", "pret",
               "subway", "foodpanda", "bar ", "pub "],
    "Groceries": ["tesco", "sainsbury", "asda", "aldi", "lidl", "waitrose", "morrisons", "walmart",
                  "kroger", "costco", "whole foods", "trader joe", "carrefour", "rewe", "edeka",
                  "supermarket", "grocery", "market", "全聯", "家樂福"],
    "Transport": ["uber", "lyft", "bolt", "taxi", "tfl", "transport", "rail", "train", "metro",
                  "bus ", "shell", "bp ", "esso", "chevron", "fuel", "petrol", "parking", "airline",
                  "ryanair", "easyjet"],
    "Entertainment": ["netflix", "spotify", "disney", "youtube", "apple.com/bill", "steam",
                      "playstation", "xbox", "nintendo", "cinema", "hbo", "prime video"],
    "Shopping": ["amazon", "ebay", "zara", "h&m", "uniqlo", "ikea", "apple store", "etsy", "shein"],
    "Health": ["pharmacy", "boots", "cvs", "walgreens", "dental", "dentist", "clinic", "doctor",
               "hospital", "gym"],
    "Housing": ["rent", "mortgage", "electric", "energy", "water", "gas ", "council tax",
                "internet", "broadband", "vodafone", "verizon", "at&t", "t-mobile", "o2 ", "ee "],
}
CATS_ZH = {"Dining": "飲食", "Groceries": "食材", "Transport": "交通", "Entertainment": "娛樂",
           "Shopping": "購物", "Health": "醫療", "Housing": "居住", "Other": "其他",
           "Income": "其他", "Salary": "薪資", "Transfer": "轉帳"}
# Moving money between your own accounts, not spending or income.
TRANSFER_HINTS = ["payment thank you", "payment received", "card payment", "credit card payment",
                  "autopay", "transfer to", "transfer from", "to savings", "from savings",
                  "own account", "internal transfer", "atm", "cash withdrawal", "卡費", "轉帳"]
SALARY_HINTS = ["salary", "payroll", "wages", "gehalt", "lohn", "薪資", "薪水"]

DATE_FORMATS = {
    "ymd": ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"],
    "dmy": ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y"],
    "mdy": ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y"],
    "text": ["%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%d-%b-%Y", "%d %b %y", "%d-%b-%y"],
}


def read_rows(path: Path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "cp950"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        sys.exit("❌ Can't read the file's encoding. Save it as UTF-8 CSV and try again.")
    lines = text.splitlines()
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ","
    # Some banks put account info above the real header: start at the first line
    # that looks like a header (has a date-ish column and enough fields).
    for i, line in enumerate(lines[:30]):
        cells = [c.strip().lower() for c in next(csv.reader([line], delimiter=delim), [])]
        if len(cells) >= 3 and any(any(h in c for h in COL_HINTS["date"]) for c in cells):
            lines = lines[i:]
            break
    return list(csv.DictReader(lines, delimiter=delim))


def map_columns(headers, override: str):
    found = {}
    if override:
        for pair in override.split(","):
            k, _, v = pair.partition("=")
            found[k.strip()] = v.strip()
        return found
    headers = [h for h in headers if h and not any(s in h.lower() for s in SKIP_HEADERS)]
    taken = set()
    for key in ("date", "debit", "credit", "amount", "desc"):
        for hint in COL_HINTS[key]:
            for h in headers:
                low = h.strip().lower()
                # short hints ("in", "out") must match the whole header, not a substring
                hit = low == hint if len(hint) <= 3 else hint in low
                if hit and h not in taken:
                    found[key] = h
                    taken.add(h)
                    break
            if key in found:
                break
    return found


def money(s):
    """Bank amount → float. Handles 1,234.56 / 1.234,56 / (12.00) / 12.00- / 12.00 DR."""
    t = str(s or "").strip().replace("\u2212", "-")  # some banks export a Unicode minus sign
    if not t:
        return None
    neg = t.startswith("(") and t.endswith(")") or t.endswith("-") or t.upper().endswith(" DR")
    t = re.sub(r"(?i)\s*(cr|dr)$", "", t).rstrip("- ")
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif re.search(r",\d{1,2}\D*$", t):
        t = t.replace(",", ".")
    v = amount(t)
    if v is None:
        return None
    return -abs(v) if neg else v


def date_order(values, forced: str):
    if forced:
        return forced
    nums = [re.findall(r"\d+", v.strip().split("T")[0].split(" ")[0]) for v in values if v]
    if any(len(n) == 3 and len(n[0]) == 4 for n in nums) or any(len(n) == 1 and len(n[0]) == 8 for n in nums):
        return "ymd"
    if any(re.search(r"[A-Za-z]{3}", v) for v in values):
        return "text"
    if any(re.match(r"\s*\d{1,2}\.\d{1,2}\.\d{2,4}", v) for v in values):
        return "dmy"  # 03.11.2026 is day-first everywhere it is used
    if any(len(n) == 3 and int(n[0]) > 12 for n in nums):
        return "dmy"
    if any(len(n) == 3 and int(n[1]) > 12 for n in nums):
        return "mdy"
    return ""


def parse_date(s: str, order: str):
    s = s.strip().split("T")[0].split(" ")[0] if order != "text" else s.strip()
    for f in DATE_FORMATS[order]:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    return None


def _has(text: str, word: str) -> bool:
    """Latin keywords must start a word ("tfl" is not in "netflix"); CJK ones match anywhere."""
    if word.isascii():
        return re.search(r"(?<![a-z0-9])" + re.escape(word), text) is not None
    return word in text


def guess(desc: str, signed: float):
    """→ (kind, category key)."""
    # "ONLINE PAYMENT - THANK YOU" → " online payment thank you "
    d = " " + " ".join(re.sub(r"[^\w&.*/]+", " ", desc.lower()).split()) + " "
    if any(_has(d, h) for h in TRANSFER_HINTS):
        return "transfer", "Transfer"
    if signed > 0:
        return "income", "Salary" if any(_has(d, h) for h in SALARY_HINTS) else "Income"
    for cat, words in CATS.items():
        if any(_has(d, w) for w in words):
            return "expense", cat
    return "expense", "Other"


def ledger_rows():
    if not LEDGER.exists():
        return []
    with LEDGER.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description="Import a bank / card statement CSV.")
    ap.add_argument("file")
    ap.add_argument("--payment", default=S.get("default_payment", "card"),
                    help="payment method for every row: card, bank, … (default: from settings)")
    ap.add_argument("--flip", action="store_true", help="positive amounts are spending")
    ap.add_argument("--dates", choices=["dmy", "mdy", "ymd"], help="date order, if ambiguous")
    ap.add_argument("--map", default="", help="date=Col,amount=Col,desc=Col (or debit=,credit=)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.file).expanduser()
    if not path.exists():
        sys.exit(f"❌ File not found: {path}")
    rows = read_rows(path)
    if not rows:
        sys.exit("❌ No data rows in the file.")

    cols = map_columns(list(rows[0].keys()), args.map)
    has_amount = "amount" in cols or ("debit" in cols or "credit" in cols)
    print(f"🔎 Columns: {cols}")
    if "date" not in cols or not has_amount:
        sys.exit("❌ Can't find the date or amount column. Headers in the file:\n"
                 f"   {list(rows[0].keys())}\n   Re-run with --map date=…,amount=…,desc=…")

    order = date_order([r.get(cols["date"]) or "" for r in rows], args.dates)
    if not order:
        sys.exit("❌ Dates like 03/04/2026 could be either order. Ask the user, then re-run with "
                 "--dates dmy (day first) or --dates mdy (month first).")

    existing = ledger_rows()
    zh = any(kind(r.get("type", "")) != r.get("type", "") for r in existing) or (not existing and LANG == "zh-TW")
    type_word = {"expense": "支出", "income": "收入", "transfer": "轉帳"} if zh else \
                {"expense": "expense", "income": "income", "transfer": "transfer"}
    seen = {m.group(1) for r in existing for m in [re.search(r"bank:(\w+)", r.get("note") or "")] if m}
    manual = {}
    for r in existing:
        if "bank:" in (r.get("note") or ""):
            continue
        a = amount(r.get("amount"))
        if a is not None:
            manual.setdefault((r.get("date"), round(a, 2)), []).append(r.get("id"))

    next_id = max([int(r["id"]) for r in existing if (r.get("id") or "").isdigit()] or [0]) + 1
    new, dupes, bad, repeats = [], [], [], {}
    for r in rows:
        raw_date = (r.get(cols["date"]) or "").strip()
        if not raw_date:
            continue
        d = parse_date(raw_date, order)
        if "amount" in cols:
            signed = money(r.get(cols["amount"]))
        else:
            out_, in_ = money(r.get(cols.get("debit", ""))), money(r.get(cols.get("credit", "")))
            signed = (abs(in_) if in_ else 0.0) - (abs(out_) if out_ else 0.0) if (out_ or in_) else None
        if d is None or signed is None:
            bad.append(raw_date)
            continue
        if signed == 0:
            continue
        if args.flip:
            signed = -signed
        desc = " ".join((r.get(cols.get("desc", "")) or "").split()) if cols.get("desc") else ""
        k, cat = guess(desc, signed)
        amt = round(abs(signed), 2)
        # Same date + amount + description can legitimately repeat (two coffees): number them.
        base = f"{d.isoformat()}|{amt:.2f}|{desc.lower()}"
        repeats[base] = repeats.get(base, 0) + 1
        fp = hashlib.sha1(f"{base}|{repeats[base]}".encode()).hexdigest()[:10]
        if fp in seen:
            continue
        if (d.isoformat(), amt) in manual and k != "transfer":
            dupes.append((d.isoformat(), amt, desc, manual[(d.isoformat(), amt)]))
            continue
        category = CATS_ZH.get(cat, cat) if zh else ("Other" if cat == "Income" else cat)
        if cat == "Dining":
            category = S.get("eat_out_category", category)
        elif cat == "Groceries":
            category = S.get("groceries_category", category)
        new.append({
            "id": next_id, "date": d.isoformat(), "type": type_word[k],
            "amount": str(int(amt)) if amt == int(amt) else f"{amt:.2f}",
            "category": category, "item": desc[:60] or "bank transaction",
            "payment": args.payment,
            "note": f"bank:{fp} " + ("[銀行匯入,分類待確認]" if zh else "[bank import: check category]"), "receipt": "",
        })
        next_id += 1

    if bad:
        print(f"⚠️  {len(bad)} rows skipped: unreadable date or amount (first: {bad[0]})")
    if dupes:
        print(f"⚠️  {len(dupes)} possible duplicates skipped (same date and amount already in the ledger):")
        for dd, a, desc, ids in dupes:
            print(f"   {dd} {a:>9}  {desc[:40]}  ← #{', #'.join(ids)}")
    if not new:
        print("✅ Nothing new to import.")
        return

    if sum(1 for r in new if kind(r["type"]) == "income") > len(new) / 2:
        print("⚠️  Most rows came out as income. If this is a card statement that lists purchases as "
              "positive numbers, re-run with --flip.")
    spend = sum(float(r["amount"]) for r in new if kind(r["type"]) == "expense")
    print(f"\n📥 {len(new)} new rows ({order} dates); spending in them: {spend:,.2f}")
    for r in new:
        print(f"   #{r['id']} {r['date']} {kind(r['type']):<8} {r['amount']:>9}  {r['category']} · {r['item']}")
    if args.dry_run:
        print("\n(--dry-run: nothing written)")
        return

    write_header = not LEDGER.exists() or LEDGER.stat().st_size == 0
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerows(new)
    print(f"\n✅ Written to {LEDGER}. Categories are guesses from the description: review the flagged rows.")


if __name__ == "__main__":
    main()
