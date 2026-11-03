# 台灣電子發票匯入(僅台灣使用者)

有用**手機條碼載具**的消費(超商、超市、餐飲、網購、藥妝…),可以整批匯入,不必一筆一筆講。
兩條路,結果都寫進同一個 `ledger.csv`,用發票號碼去重。

## 路線 B(建議):匯出 CSV 再匯入,免申請

1. 在「統一發票兌獎」App 或財政部電子發票整合服務平台,匯出載具消費明細(CSV)。
2. 把檔案交給助理:

```bash
python3 <skill>/scripts/import_csv.py <匯出檔.csv> --dry-run   # 先預覽
python3 <skill>/scripts/import_csv.py <匯出檔.csv>
```

匯入器自動辨識日期 / 金額 / 店家 / 發票號碼欄(欄名不拘,Big5 / UTF-8 都吃)。
辨識失敗時,把表頭貼出來,在 `scripts/import_csv.py` 的 `COL_HINTS` 補上欄名。

## 路線 A(備援):財政部 API 自動撈,需要 AppID

```bash
python3 <skill>/scripts/fetch_invoices.py [--days 60 | --start YYYY/MM/DD --end YYYY/MM/DD] [--dry-run]
```

憑證放在資料夾裡的 `secrets.json`(格式見 `templates/zh-TW/secrets.example.json`):
`app_id`、`card_no`(/開頭的載具號碼)、`card_encrypt`(驗證碼)。**這個檔絕不能上傳或分享。**
AppID 申請頁常在維護,申請不到就走路線 B。

## 匯入後(助理要做的)

- 分類是**用店名猜的**,`note` 會標 `發票:<號碼> [發票匯入,分類待確認]`。
  主動掃一遍可疑的(超商買的不一定是飲食;藥妝店可能是日用也可能是醫療),一次問完;
  使用者確認後拿掉「分類待確認」。
- `payment` 一律先記 `其他`(發票看不出付款方式),使用者說了再改。
- 匯入器寫中文的 type(`支出`)與中文分類;英文帳本的使用者匯入後要把 type / 分類換成帳本慣用的寫法。
- 跟收件匣的手動記帳**可能重複**(同一天、同金額、同一家店)。發現時保留發票那筆、刪手動那筆前先問。

**發票進不來的**:沒掃載具的現金消費、國外消費、房租、轉帳、所有收入——這些照一般方式一句話記。
