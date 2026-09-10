# CountAgant

**一個跑在 Claude Code 上的個人記帳 agent —— 捕捉端笨到極點，判斷端全交給 AI。**

在外面對 Siri 說一句「午餐 120」，回到電腦說一聲「整理」，
剩下的分類、補欄位、算預算、產報表，全部由 agent 完成。

---

## 為什麼做這個

記帳 App 滿街都是，但我每次都撐不過兩週。問題不在功能不夠，
而在**當下那兩秒**：要開 App、等載入、選分類、選付款方式、填欄位——
等於每記一筆，都要先幫 App 把資料整理好。人在店門口、雨中、跟朋友講話時，不會想做這件事。

所以我不想再做一個「更好用的記帳 App」。我想試的是：
**如果記錄這件事可以退化成「講一句話」，聰明的部分全部由 AI 事後補，會怎麼樣？**

## 核心概念：把智慧從 App 移到 Agent

一般記帳 App 把智慧放在**介面**：下拉選單、分類樹、標籤、規則引擎。
智慧放在介面的代價，是使用者必須配合資料庫的 schema 思考——
你不是在「記帳」，你是在「替資料表填欄位」。

CountAgant 反過來，把捕捉端和整理端徹底切開：

| | 捕捉 | 整理 |
|---|---|---|
| 在哪 | iPhone，任何地方 | 電腦，有空時 |
| 誰做 | 你，兩秒一句話 | Agent，全自動 |
| 要多聰明 | **笨到極點**（純文字附加到一個檔案） | **很聰明**（語意解析 + 常識判斷） |
| 失敗率 | 幾乎為零，沒有網路也能用 | 出錯可事後修，不影響記錄 |

**捕捉端笨，是刻意的設計，不是偷懶。**
它只做一件事：把一行字附加到一個純文字檔。沒有欄位、沒有選單、沒有登入、沒有網路請求。
笨到不可能故障，也就笨到讓人沒有藉口不用。

**判斷的苦工，全部推給 agent。**
把「昨天宵夜 97」變成一列九欄的帳，需要推斷日期（昨天是幾號）、收支類型、
分類（宵夜屬飲食）、付款方式（沒講就用預設）、品項描述。
這正好是 LLM 擅長、而傳統規則引擎最脆弱的地方——關鍵字表永遠寫不完使用者的講法。

**而規則本身是自然語言，不是程式碼。**
Agent 的完整行為定義寫在 [`CLAUDE.md`](CLAUDE.md)：怎麼推斷分類、什麼情況該反問、
投資為什麼不算支出、發票匯入後要主動複查哪些可疑分類。
要改規則（例如「沒講付款方式就預設信用卡」）就是改一句中文，不必重寫 parser。
記帳規則因此能跟著生活習慣演化，而不是每次都要動到程式。

對使用者的實際差別：
記一筆的成本從「開 App → 選分類 → 填金額 → 存檔」變成「對 Siri 講一句話」；
整理的成本從「永遠不會做」變成「有空時說一聲『整理』」。

## 核心功能

- **零摩擦捕捉** — iOS 捷徑 + Siri 語音把一句話寫進 iCloud 的 `inbox.txt`，離線可用，自動帶時間戳
- **語意解析建帳** — agent 逐行判讀，自動補齊日期、收支類型、分類、付款方式、品項九個欄位
- **去重防呆** — iCloud 同步可能把已處理的舊行帶回來，以歸檔檔逐字比對後跳過
- **電子發票匯入** — 支援載具匯出的 CSV（欄名不拘、Big5/UTF-8 自動判讀）與財政部載具 API，用發票號碼去重
- **多維報表** — 月報、季度財報（儲蓄率、預算 vs 實際、固定 vs 變動支出）、HTML 儀表板
- **自煮成本追蹤** — 記錄食材消耗速度，換算自煮與外食的真實單餐成本

## 快速開始

需要 [Claude Code](https://claude.com/claude-code) 與 Python 3（腳本只用標準函式庫，**不需 pip 安裝任何套件**）。

```bash
git clone https://github.com/seanlu2006/CountAgent.git
cd CountAgent
```

**先看長相**（用內建假資料，不會碰到任何帳本）：

```bash
python3 scripts/dashboard.py --demo
```

**開始自己用**——複製範本建立你的私人資料檔（這些檔案都已被 `.gitignore` 排除）：

```bash
cp data/ledger.example.csv   data/ledger.csv        # 主帳本
cp data/budget.example.md    data/budget.md         # 預算（季報會讀）
cp data/profile.example.md   data/sean_profile.md   # 個人設定（付款習慣、固定支出）
cp data/food_notes.example.md data/food_notes.md    # 食材成本筆記（選用）
```

範本裡的數字全是假的，記得換成自己的。接著在專案資料夾開 Claude Code：

```bash
claude
```

然後直接講話就好，**記帳不需要任何指令**：

> 你：午餐 120
> Agent：#42 2026-05-31 | 支出 120 | 飲食 · 午餐（信用卡）

說「整理」，agent 會去讀 iCloud 收件匣，把累積的語音記錄一次消化進帳本。

**報表指令**：

```bash
python3 scripts/report.py                 # 本月月報
python3 scripts/report.py 2026-08         # 指定月份
python3 scripts/quarterly.py              # 本季財報
python3 scripts/quarterly.py 2026Q3       # 指定季度
python3 scripts/quarterly.py 2026Q3 --md  # 另存 reports/2026-Q3.md
python3 scripts/dashboard.py              # 產生並開啟 HTML 儀表板
python3 scripts/dashboard.py --no-open    # 只產生不開瀏覽器
```

**電子發票匯入**：

```bash
python3 scripts/import_csv.py 匯出檔.csv --dry-run   # 先預覽不寫入
python3 scripts/import_csv.py 匯出檔.csv
```

若要走財政部載具 API，複製 `data/secrets.example.json` 成 `data/secrets.json` 填入憑證後：

```bash
python3 scripts/fetch_invoices.py --days 30 --dry-run
```

**設定 Siri 捕捉端**（選用，但這是整套設計的重點）：
用 iOS 捷徑 App 建一個捷徑，動作選「附加到文字檔案」，
目標檔為 iCloud 捷徑資料夾中的 `inbox.txt`，內容設為聽寫文字加時間戳，
命名為「記一筆」即可用 Siri 喚起。Mac 端會自動同步收到。

## 技術架構

```
[捕捉] iPhone / Siri 一句話
   └─▶ 附加到 iCloud inbox.txt（純文字，一行一筆，帶時間戳）
              │  iCloud 自動同步
              ▼
[解析] Claude Code agent 讀 inbox.txt
   ├─▶ 比對 inbox_archive.txt 去重
   └─▶ 依 CLAUDE.md 的規則逐行判讀語意
              │
[分類] 對照 categories.md 推斷分類，用 profile 補付款方式預設值
              │
[儲存] append 一列到 data/ledger.csv（九欄，永不重排歷史列）
              │  清空 inbox、原始行存進 archive
              ▼
[報表] report.py（月）│ quarterly.py（季，讀 budget.md）│ dashboard.py（HTML）
              └─▶ reports/

另一條進帳路徑：
電子發票 CSV / 財政部 API ─▶ categorize.py 依店名猜分類 ─▶ 同一份 ledger.csv
                              （標記「分類待確認」，由 agent 事後複查）
```

`ledger.csv` 是唯一的事實來源：純 CSV、可用 Excel 直接開、易備份與遷移，
不綁任何 App 或資料庫。

## 專案結構

```
CountAgant/
├── CLAUDE.md                    # Agent 行為定義（本專案的核心，用自然語言寫的規則）
├── data/
│   ├── categories.md            # 分類定義（公開）
│   ├── ledger.example.csv       # 帳本範本（假資料）
│   ├── budget.example.md        # 預算範本（假資料）
│   ├── profile.example.md       # 個人設定範本（假資料）
│   ├── food_notes.example.md    # 食材成本範本（假資料）
│   └── secrets.example.json     # 發票 API 憑證範本
├── scripts/
│   ├── report.py                # 月報
│   ├── quarterly.py             # 季度財報（讀 budget.md）
│   ├── dashboard.py             # HTML 儀表板（Chart.js CDN）
│   ├── import_csv.py            # 電子發票 CSV 匯入
│   ├── fetch_invoices.py        # 財政部載具 API 抓取
│   └── categorize.py            # 店名 → 分類的共用規則
└── reports/                     # 產出的報表（不進版控）
```

實際的帳本、預算、個人設定與報表都不在版控內，clone 下來只有程式碼、行為定義與假資料範本。

## 已知限制

- **依賴 Claude Code**：這不是獨立 App。沒有 Claude Code 的話，剩下的只是幾支能讀 CSV 的 Python 腳本，記帳那一半不會動。
- **LLM 判讀不保證全對**：語意模糊的句子（「那個 300」）會被留在收件匣等人確認；電子發票是**用店名猜分類**，超商買日用品就會歸錯，需要事後複查。
- **單人單機**：靠 iCloud 檔案同步，沒有多人共帳、沒有多裝置即時同步。同步有延遲，也可能把舊行帶回來（靠歸檔比對去重處理）。
- **捕捉端綁 Apple 生態**：Siri + iOS 捷徑寫 iCloud 檔案。換平台就得自己做一個「能附加一行字到某個檔案」的捕捉端——不過也就這樣而已，這層本來就設計得很薄。
- **財政部 API 需要 AppID**，申請頁常在維護，所以目前主用 CSV 匯入那條路。

## 授權

尚未指定（規劃採用 MIT，待補上 `LICENSE` 檔）。
