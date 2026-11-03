# CountAgent

這個 repo 是 **CountAgent skill** 的原始碼:`skills/countagent/`。
記帳、整理收件匣、報表、儀表板一律照 [`skills/countagent/SKILL.md`](skills/countagent/SKILL.md) 做。

- 用 `python3 skills/countagent/scripts/cfg.py --where` 找資料夾與設定。
- 個人習慣、固定支出、收入關鍵字在資料夾裡的 `profile.md`,**解讀任何一筆帳之前先讀**。
- `data/`、`reports/` 是私人資料,已 gitignore,絕不 commit、絕不上傳。
- 語言跟著使用者;這個 repo 的維護者用繁體中文。

## 改 skill 時

- 改 scripts 前後,用維護者自己的帳本跑 `report.py` / `quarterly.py` / `dashboard.py` 比對數字,確認沒變。
- 新使用者流程用乾淨的 `HOME`(或 `COUNTAGENT_DATA=<暫存資料夾>`)測,不要碰真實資料。
- 文字放 `scripts/i18n.py`(zh-TW / en),範本放 `templates/<語言>/`。
