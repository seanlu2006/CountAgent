# Agensi 上架草稿(CountAgent)

> 草稿,上架前 Sean 過目。價格:3 USD(**Agensi 抽成待確認**)。授權:GitHub 維持 MIT(方案 A)。
> 所有功能敘述都對得上目前 repo 的實際功能;沒有編任何使用者數或評價。

## Name
CountAgent

## Tagline (≤ 80 chars)
One line in, a complete ledger out. Say "lunch 12" and the agent does the rest

## Short description
A bookkeeping skill for people who quit every expense app. You log spending in one short line, from your phone or the chat. The agent fills in date, category and payment method, catches duplicates, and keeps a plain CSV ledger on your own machine. Drop in a bank statement CSV to catch up in one go. Monthly and quarterly reports, budgets, and an offline HTML dashboard included.

## Long description

Expense apps ask for two seconds of form-filling at the worst moment: standing at the counter, phone in one hand. CountAgent drops the form. You type or dictate "uber 18 yesterday", and the agent works out the rest later.

**What it does**
- Turns one-line notes into a full entry: date, type, category, payment method, description. "Yesterday", timestamps and late-night logs land on the right day.
- Phone capture through a plain text file. Recipe included for iPhone (Shortcuts + Siri); any app that appends a line to a synced file works.
- Imports a bank or card statement CSV from any bank. It reads the columns, date order and number format itself, turns card repayments into transfers so nothing counts twice, and skips what you already logged by hand.
- Catches the duplicates people actually make: sync bringing back old lines, and the same lunch logged twice in different words.
- Records recurring charges you mark as automatic (subscriptions, instalments) once their day has passed. Bills you pay by hand wait until you say so.
- Budgets per category, savings targets, one-off extras ("150 more this month for a trip").
- Months can follow your credit-card statement (closing day of your choice) or the calendar.
- Reports: period summary, quarterly statement (savings rate, budget vs actual, fixed vs variable), and a single-file HTML dashboard with daily spending against budget and an eating-out view.
- English and Traditional Chinese. Any currency.
- Taiwan extra: e-invoice import from the carrier CSV export or the Ministry of Finance API.

**What it doesn't do**
No bank logins, no cloud, no account. Your ledger is a CSV in a folder you choose; nothing is uploaded. It won't give investment advice.

**Requirements**
Claude Code (or another agent that loads `SKILL.md` skills) and Python 3.8+. Standard library only, nothing to install.

**Setup**
Install the folder, then say "set up CountAgent". One round of questions (language, currency, statement day, usual payment method) and it's ready. Try `dashboard.py --demo` first to see the dashboard with made-up data.

## Tags
finance, budgeting, expense-tracker, personal-finance, bank-import, productivity, csv, dashboard

## Price
3 USD

The source is also public on GitHub under MIT. The listing is the ready-to-install version.

---

## 中文短版(若平台支援多語)

**一句話記帳,其他全交給 agent。**
說「午餐 120」就好:日期、分類、付款方式、重複檢查都由 agent 補。帳本是你電腦裡的一個 CSV,不上雲。銀行對帳單 CSV 丟進來就能一次補齊。
有月報、季報、預算,還有離線的 HTML 儀表板;月份可以跟信用卡結帳日走。
iPhone 捷徑 + Siri 隨手記的做法附在裡面。台灣使用者可以匯入載具電子發票。

