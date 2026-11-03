# CountAgent → Skill 改版計畫(2026-11-03)

目標:把 CountAgent 包成可安裝的 Agent Skill(SKILL.md),任何人裝了就能用;
Sean 自己的帳本留在 `~/CountAgant/data/` 不搬。目標上架 Agensi,定價約 1 USD(最低價待確認)。

## 驗收條件
1. Sean 在**任何資料夾**說「整理」「午餐 120」都會觸發 skill,讀寫的仍是 `~/CountAgant/data/`。
2. Sean 的月報/季報/儀表板數字跟改版前完全一樣(改版前快照比對)。
3. 新使用者(乾淨 HOME、英文)照 SKILL.md 首次設定 → 能記帳、出月報、出儀表板,全程不碰 Sean 的資料。
4. 可設定:幣別、語言(zh-TW / en)、結帳日(0 = 日曆月)、預設付款方式、收件匣路徑、外食/食材分類名。
5. 報表(終端機 + 儀表板)支援 zh-TW 與 en。
6. 公開的 repo / skill 內沒有 Sean 的私人資料或個人規則。
7. fresh agent read-back SKILL.md 沒有找到會讓新使用者卡住的地方。

## 步驟
- [x] P1 結構:scripts 搬進 `skills/countagent/scripts/`,新增 `cfg.py` 解析資料夾與設定;Sean 的 config;symlink 安裝;前後數字比對
- [x] P2 SKILL.md(英文、觸發詞中英)+ references(setup / inbox / reports / 台灣發票)+ templates(zh-TW、en)
- [x] P3 i18n:report / quarterly / dashboard 的文字、幣別符號、外食分類改讀設定
- [ ] P4 新使用者實測(乾淨 HOME、英文)+ fresh agent 審 SKILL.md
- [ ] P5 README、repo CLAUDE.md 瘦身、Agensi 上架文案;commit 前先問 Sean

## 進度紀錄
- 2026-11-03 P1–P3 完成:Sean 的月報/季報/儀表板資料與改版前快照逐字相同(SAME-REPORT/Q/DASH);
  乾淨 HOME 英文流程:setup → 記帳 → 月報 → 季報 → 儀表板(含 demo)皆可跑。
  `~/.claude/skills/countagent` → repo 的 symlink 已裝;`data/sean_profile.md` 改名 `data/profile.md`。
  新規則:保底收入不套用在帳本第一筆之前的帳期(新使用者季報才不會灌水)。
