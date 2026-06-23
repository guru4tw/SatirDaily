# 修改紀錄 (history.md)

SatirDaily 的精簡修改 log。每次有意義的調整補一筆,最新在最上面。
格式:`日期 — 重點`,需要時補一兩行說明。完整逐 commit 細節看 `git log`。

---

## 2026-06-23

- **design-review 落地 + 成蒂稱謂調整** — 移除「✓ 連結已驗證」徽章(連結正常為常態,不另標;僅 `link_ok===false` 留「⚠ 連結待確認」);次要文字色加深至 WCAG AA(`--ink-faint` → `#647571`);tab 補 aria-controls/tabindex/方向鍵與 focus-visible;加載入骨架與更友善的空/錯誤狀態;帶領者・主辦改可點 chip → 篩選 + 進行中篩選條件可清除。成蒂稱謂改「薩提爾嫡傳 ·體驗式家族,婚姻伴侶治療」(index 與 `Docs/design-review.html` 同步)。
- **首頁加入薩提爾理念傳承 + 兩段式版面** — hero 分兩部分:文案區(標題「薩提爾」+「薩提爾模式的傳承,與他們留下的話」+ 四位專家卡:Virginia Satir / Maria Gomori / John Banmen / 成蒂,各含代表提示、透鏡、三則語錄);活動區(標題「台灣薩提爾活動」+ 副標「陪你找到你自己的內在聲音」)。語錄同出處合併標示(只在末句掛書名)。eyebrow 由「每天自動更新」改為動態「上次更新 <updated_at>」,計數膠囊改「共 N 場活動」。語錄出處:成蒂《我們之間》、葛茉莉《愛與自由》、貝曼薩提爾轉化系統治療;Satir 三句為通行格言、未查到確切書目故留白。另設計健檢文件 `Docs/design-review.html` 由六位擴為八位專家視角(補 Satir、成蒂)。
- **連結溯源 + 自動驗證** — 每筆活動的「來源」改成可點連結,直接連回原始活動頁(`source_url`,由 `signup_url` 推導)。新增獨立驗證器 `Py/verify_links.py`:逐筆連回原始頁確認連結有效,把 `link_ok` / `link_checked_at` 寫回資料,前端以「✓ 連結已驗證 / ⚠ 連結待確認」標示。產報告 `Docs/link_report.json`。daily pipeline 串成 crawl → verify_links → build → commit。首次全量驗證:77 筆全通過。
- **首頁文案/視覺調整** — 大 logo 配色對齊小 logo(`#2c8c84`/`#7cc0b8`,opacity .7);hero 大字改「薩提爾」;副標改「台灣薩提爾活動資訊!」。(commit `f5ce57a`)

## 2026-06-22 ~ 06-23(初版建置)

- **三 tab 前端 + 爬蟲 + 橋接** — 前端分「近期 / 日期未定 / 已過去」三 tab;完成 5 支爬蟲(shiuhli / lopwilldo / comflow / satir_org / omia);`build_site_json.py` 把 `Docs/events.json` 正規化成前端契約。events.json 共 77 筆。(commit `3a8cf6e`)
- **GitHub Pages 部署** — 網址 https://guru4tw.github.io/SatirDaily/ ,觸發 Pages rebuild。(commit `400ea8c` / `99610e2`)
- **專案初始化** — SatirDaily 前端骨架 + 範例 events.json。三層全靜態架構(GitHub Actions 排程 + Python 爬蟲 + GitHub Pages 前端),全部免費。(commit `714d5a8`)
