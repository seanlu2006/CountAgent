"""CountAgent tests. Standard library only; never touches a real ledger.

Run from the repo root:  python3 -m unittest discover tests
"""
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "countagent" / "scripts"

# cfg.py reads the data folder at import time, so this has to come before the imports.
_module_dir = tempfile.TemporaryDirectory()
os.environ["COUNTAGENT_DATA"] = _module_dir.name
(Path(_module_dir.name) / "config.json").write_text(json.dumps({"cycle_day": 23}), encoding="utf-8")
sys.path.insert(0, str(SCRIPTS))

import import_bank as bank  # noqa: E402
import period  # noqa: E402
import reconcile as rec  # noqa: E402

FIELDS = ["id", "date", "type", "amount", "category", "item", "payment", "note", "receipt"]


def tx(day, amt, desc="shop", signed=None, fp="x", k="expense"):
    return {"date": date.fromisoformat(day), "signed": -amt if signed is None else signed,
            "amt": amt, "desc": desc, "kind": k, "cat": "Other", "fp": fp}


def row(i, day, amt, kind_="expense", payment="card", item="thing", note=""):
    return {"id": str(i), "date": day, "type": kind_, "amount": str(amt), "category": "Other",
            "item": item, "payment": payment, "note": note, "receipt": ""}


class Money(unittest.TestCase):
    def test_formats(self):
        cases = {"12.00": 12.0, "-12.00": -12.0, "12.00-": -12.0, "1,234.56-": -1234.56, "(12.00)": -12.0,
                 "10.99−": -10.99, "−10.99": -10.99, "12.00 DR": -12.0, "12.00 CR": 12.0,
                 "1,234.56": 1234.56, "1.234,56": 1234.56, "12,50": 12.5, "£5.00": 5.0}
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(bank.money(text), want)

    def test_blank_or_unreadable(self):
        for text in ("", None, "   ", "n/a"):
            with self.subTest(text=text):
                self.assertIsNone(bank.money(text))


class Dates(unittest.TestCase):
    def test_order_detected(self):
        self.assertEqual(bank.date_order(["2026-11-03"], ""), "ymd")
        self.assertEqual(bank.date_order(["03.11.2026"], ""), "dmy")
        self.assertEqual(bank.date_order(["25/11/2026"], ""), "dmy")
        self.assertEqual(bank.date_order(["11/25/2026"], ""), "mdy")
        self.assertEqual(bank.date_order(["03 Nov 2026"], ""), "text")

    def test_ambiguous_is_not_guessed(self):
        self.assertEqual(bank.date_order(["03/04/2026"], ""), "")
        self.assertEqual(bank.date_order(["03/04/2026"], "dmy"), "dmy")

    def test_parse(self):
        want = date(2026, 11, 3)
        self.assertEqual(bank.parse_date("2026-11-03T10:00:00", "ymd"), want)
        self.assertEqual(bank.parse_date("03.11.2026", "dmy"), want)
        self.assertEqual(bank.parse_date("11/03/2026", "mdy"), want)
        self.assertEqual(bank.parse_date("Nov 3, 2026", "text"), want)
        self.assertIsNone(bank.parse_date("not a date", "ymd"))

    def test_billing_period(self):
        self.assertEqual(period.period_of("2026-10-23"), "2026-10")
        self.assertEqual(period.period_of("2026-10-24"), "2026-11")
        self.assertEqual(period.period_of("2026-12-24"), "2027-01")
        self.assertEqual(period.period_range("2026-10"), (date(2026, 9, 24), date(2026, 10, 23)))


class Guess(unittest.TestCase):
    def test_keywords_start_a_word(self):
        self.assertEqual(bank.guess("NETFLIX.COM", -10), ("expense", "Entertainment"))

    def test_transfers_are_not_spending(self):
        self.assertEqual(bank.guess("ONLINE PAYMENT - THANK YOU", 100)[0], "transfer")
        self.assertEqual(bank.guess("網路銀行繳款", 3000)[0], "transfer")


class Columns(unittest.TestCase):
    def test_taiwan_card_statement_headers(self):
        self.assertEqual(bank.map_columns(["消費日", "摘要", "金額"], ""), {"date": "消費日", "amount": "金額", "desc": "摘要"})

    def test_purchase_date_preferred_over_posting_date(self):
        self.assertEqual(bank.map_columns(["入帳日", "消費日", "明細", "金額"], "")["date"], "消費日")


class PairUp(unittest.TestCase):
    def matched(self, txs, rows, window=3):
        return {i: (r["id"], gap) for i, (r, gap) in bank.pair_up(txs, rows, window).items()}

    def test_posting_lag_is_matched(self):
        self.assertEqual(self.matched([tx("2026-11-05", 12.0)], [row(1, "2026-11-03", 12)]), {0: ("1", 2)})

    def test_outside_window(self):
        self.assertEqual(self.matched([tx("2026-11-07", 12.0)], [row(1, "2026-11-03", 12)]), {})

    def test_window_zero_means_same_day(self):
        self.assertEqual(self.matched([tx("2026-11-04", 12.0)], [row(1, "2026-11-03", 12)], window=0), {})

    def test_amount_must_match(self):
        self.assertEqual(self.matched([tx("2026-11-03", 12.5)], [row(1, "2026-11-03", 12)]), {})

    def test_one_ledger_row_explains_one_statement_row(self):
        got = self.matched([tx("2026-11-03", 4.0), tx("2026-11-04", 4.0)], [row(1, "2026-11-03", 4)])
        self.assertEqual(got, {0: ("1", 0)})

    def test_closest_date_wins(self):
        got = self.matched([tx("2026-11-05", 4.0)], [row(1, "2026-11-03", 4), row(2, "2026-11-05", 4)])
        self.assertEqual(got, {0: ("2", 0)})

    def test_two_of_each_pair_off(self):
        got = self.matched([tx("2026-11-03", 4.0), tx("2026-11-05", 4.0)],
                           [row(1, "2026-11-03", 4), row(2, "2026-11-04", 4)])
        self.assertEqual(got, {0: ("1", 0), 1: ("2", 1)})

    def test_income_never_explains_spending(self):
        self.assertEqual(self.matched([tx("2026-11-03", 50.0)], [row(1, "2026-11-03", 50, "income")]), {})

    def test_money_in_matches_income_not_expense(self):
        money_in = tx("2026-11-03", 50.0, signed=50.0, k="income")
        self.assertEqual(self.matched([money_in], [row(1, "2026-11-03", 50)]), {})
        self.assertEqual(self.matched([money_in], [row(1, "2026-11-03", 50, "income")]), {0: ("1", 0)})

    def test_chinese_ledger_types(self):
        self.assertEqual(self.matched([tx("2026-11-03", 50.0)], [row(1, "2026-11-03", 50, "收入")]), {})


class ReconcileMaths(unittest.TestCase):
    def test_gap_equals_the_listed_differences(self):
        txs = [tx("2026-11-03", 10.0), tx("2026-11-04", 20.0), tx("2026-11-06", 7.0)]
        rows = [row(1, "2026-11-02", 10), row(2, "2026-11-04", 30)]
        res = rec.reconcile(txs, rows, "card", 3)
        self.assertEqual(res["statement_total"], 37.0)
        self.assertEqual(res["ledger_total"], 40.0)
        self.assertEqual(res["gap"], -3.0)
        self.assertEqual(res["gap"], round(res["statement_total"] - res["ledger_total"], 2))
        self.assertEqual([x["amt"] for x in res["only_statement"]], [20.0, 7.0])
        self.assertEqual([r["id"] for r in res["only_ledger"]], ["2"])

    def test_other_payment_method_matched_but_not_listed_as_missing(self):
        res = rec.reconcile([tx("2026-11-03", 10.0)], [row(1, "2026-11-03", 10, payment="cash")], "card", 3)
        self.assertEqual(len(res["pairs"]), 1)
        self.assertEqual(res["gap"], 0)

    def test_same_payment_method_preferred(self):
        rows = [row(1, "2026-11-03", 10, payment="cash"), row(2, "2026-11-01", 10, payment="card")]
        res = rec.reconcile([tx("2026-11-03", 10.0)], rows, "card", 3)
        self.assertEqual(res["pairs"][0][1]["id"], "2")

    def test_cash_outside_statement_is_ignored(self):
        res = rec.reconcile([tx("2026-11-03", 10.0)], [row(1, "2026-11-03", 99, payment="cash")], "card", 3)
        self.assertEqual(res["only_ledger"], [])

    def test_imported_fingerprint_wins(self):
        rows = [row(1, "2026-11-03", 10, note="bank:abc123 x"), row(2, "2026-11-03", 10)]
        res = rec.reconcile([tx("2026-11-03", 10.0, fp="abc123")], rows, "card", 3)
        self.assertEqual(res["pairs"][0][1]["id"], "1")
        self.assertEqual([r["id"] for r in res["only_ledger"]], ["2"])

    def test_transfers_and_income_stay_out(self):
        txs = [tx("2026-11-03", 10.0), tx("2026-11-04", 500.0, signed=500.0, k="transfer"),
               tx("2026-11-05", 5.0, signed=5.0, k="income")]
        res = rec.reconcile(txs, [row(1, "2026-11-04", 500, "transfer")], "card", 3)
        self.assertEqual((res["statement_total"], res["ledger_total"]), (10.0, 0))
        self.assertEqual((res["transfers"], res["money_in"], res["money_in_total"]), (1, 1, 5.0))

    def test_date_limits(self):
        txs = [tx("2026-10-20", 10.0), tx("2026-11-03", 20.0)]
        res = rec.reconcile(txs, [], "card", 3, start=date(2026, 11, 1), end=date(2026, 11, 30))
        self.assertEqual(res["statement_total"], 20.0)


class CommandLine(unittest.TestCase):
    STATEMENT = ("Date,Description,Amount\n"
                 "2026-11-05,COFFEE BAR,-4.50\n"
                 "2026-11-06,HARDWARE SHOP,-30.00\n"
                 "2026-11-07,PAYMENT THANK YOU,100.00\n")

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.root = Path(self._dir.name)
        self.ledger = self.root / "ledger.csv"
        self.statement = self.root / "statement.csv"
        self.statement.write_text(self.STATEMENT, encoding="utf-8")
        self.config({})

    def config(self, values):
        (self.root / "config.json").write_text(json.dumps(values), encoding="utf-8")

    def write_ledger(self, rows):
        with self.ledger.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    def read_ledger(self):
        with self.ledger.open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def run_script(self, name, *args):
        env = dict(os.environ, COUNTAGENT_DATA=str(self.root), PYTHONIOENCODING="utf-8")
        done = subprocess.run([sys.executable, str(SCRIPTS / name), *args], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        return done.stdout.decode("utf-8")

    def imp(self, *args):
        return self.run_script("import_bank.py", str(self.statement), "--payment", "card", *args)

    def test_dry_run_writes_nothing(self):
        self.write_ledger([row(1, "2026-11-01", 1)])
        before = self.ledger.read_bytes()
        self.assertIn("nothing written", self.imp("--dry-run"))
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_import_after_a_ledger_with_no_final_newline(self):
        self.write_ledger([row(1, "2026-11-01", 1, item="last row")])
        self.ledger.write_bytes(self.ledger.read_bytes().rstrip(b"\n"))
        self.imp()
        rows = self.read_ledger()
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["receipt"], "")
        self.assertEqual(rows[1]["item"], "COFFEE BAR")

    def test_import_then_reimport_adds_nothing(self):
        self.write_ledger([])
        self.imp()
        first = self.read_ledger()
        self.assertEqual([r["type"] for r in first], ["expense", "expense", "transfer"])
        self.assertIn("Nothing new", self.imp())
        self.assertEqual(self.read_ledger(), first)

    def test_fingerprints_stay_stable_for_past_imports(self):
        self.write_ledger([])
        self.imp()
        want = hashlib.sha1("2026-11-05|4.50|coffee bar|1".encode()).hexdigest()[:10]
        self.assertTrue(self.read_ledger()[0]["note"].startswith(f"bank:{want} "))

    def test_hand_logged_purchase_with_posting_lag_is_not_doubled(self):
        self.write_ledger([row(1, "2026-11-03", 4.5, item="coffee")])
        out = self.imp()
        self.assertIn("1 possible duplicates", out)
        self.assertIn("2d apart", out)
        self.assertEqual([r["item"] for r in self.read_ledger()], ["coffee", "HARDWARE SHOP", "PAYMENT THANK YOU"])

    def test_keep_imports_a_listed_row_once(self):
        self.write_ledger([row(1, "2026-11-03", 4.5, item="coffee")])
        code = hashlib.sha1("2026-11-05|4.50|coffee bar|1".encode()).hexdigest()[:10]
        self.imp("--keep", code)
        self.assertEqual(sum(r["item"] == "COFFEE BAR" for r in self.read_ledger()), 1)
        self.imp("--keep", code)
        self.assertEqual(sum(r["item"] == "COFFEE BAR" for r in self.read_ledger()), 1)

    def test_window_zero_imports_the_lagged_row(self):
        self.write_ledger([row(1, "2026-11-03", 4.5)])
        self.imp("--window", "0")
        self.assertEqual(len(self.read_ledger()), 4)

    def test_chinese_ledger_keeps_its_language(self):
        self.config({"language": "zh-TW"})
        self.write_ledger([row(1, "2026-11-01", 1, "支出")])
        self.imp()
        self.assertEqual([r["type"] for r in self.read_ledger()[1:]], ["支出", "支出", "轉帳"])

    def test_reconcile_reports_and_changes_nothing(self):
        self.write_ledger([row(1, "2026-11-04", 4.5), row(2, "2026-11-06", 8)])
        before = self.ledger.read_bytes()
        out = self.run_script("reconcile.py", str(self.statement), "--payment", "card")
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertIn("Statement spending: 34.50", out)
        self.assertIn("Ledger equivalent : 12.50", out)
        self.assertIn("Gap               : 22.00", out)
        self.assertIn("HARDWARE SHOP", out)
        self.assertIn("#2 2026-11-06", out)
        self.assertIn("may appear on the next one", out)

    def test_reconcile_warns_about_a_wrong_payment_name(self):
        self.write_ledger([row(1, "2026-11-04", 4.5, payment="信用卡")])
        self.assertIn("信用卡", self.run_script("reconcile.py", str(self.statement), "--payment", "card"))

    def test_reconcile_speaks_chinese(self):
        self.config({"language": "zh-TW", "currency": "TWD"})
        self.write_ledger([row(1, "2026-11-04", 4.5, "支出")])
        self.assertIn("對帳單支出", self.run_script("reconcile.py", str(self.statement), "--payment", "card"))

    def test_report_totals_leave_out_transfers_and_investments(self):
        self.write_ledger([row(1, "2026-11-03", 40), row(2, "2026-11-04", 500, "transfer"),
                           row(3, "2026-11-05", 100, "investment"), row(4, "2026-11-06", 900, "income")])
        out = self.run_script("report.py", "2026-11")
        self.assertRegex(out, r"Spending\s*:\s*\$?40\.00")
        self.assertRegex(out, r"Income\s*:\s*\$?900\.00")


if __name__ == "__main__":
    unittest.main()
