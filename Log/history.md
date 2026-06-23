# 修改紀錄 (history.md)

SatirDaily 的精簡修改 log。每次有意義的調整補一筆,最新在最上面。
格式:`日期 — 重點`,需要時補一兩行說明。完整逐 commit 細節看 `git log`。

---

## 2026-06-24

- **修正:首頁標題點不進活動子頁(JS 版漏連結)** — 首頁 `#list` 同時裝預渲染版(給爬蟲,標題本就有 `<a href="events/{id}.html">`)與 JS 互動版。`render()` 用 `innerHTML` 蓋掉 `#list` 後,JS 版標題是純文字,使用者點不到 `events/{id}.html` 子頁(只剩「我要報名」連 signup_url 外站);長尾子頁實質只有爬蟲走得到。修法:JS 卡片標題包成 `<a href="events/${encodeURIComponent(ev.id)}.html">`,與預渲染版對齊;補 `.card h3 a` CSS(繼承標題色、hover 變色加底線)。preview 實證 JS 渲染後 46 張標題皆為可點連結,`shiuhli-1040` 正確指向 `events/shiuhli-1040.html`。

- **SEO 整合計畫實作:過期分離 + SSG 多頁 + og:image**(依 `Docs/SatirDaily_SEO_Plan.html`) — 把「單頁 SPA」升級為「多頁靜態站」,打破長尾與 Event Rich Result 天花板:
  - **過期活動分離**:`build_site_json.py` 以今天為界把活動分 `upcoming`/`undated`/`past`。首頁預渲染與首頁 JSON-LD 只收有效活動(upcoming+undated,共 46+5);過期 26 筆進 `/archive/index.html`(仍可索引,不稀釋首頁相關性)。前端 `injectJsonLd` 同步加 `!isPast` 過濾,避免 JS 載入後又把過期活動灌回 ld-events。
  - **SSG 三階段(每日 build 生成)**:① `events/{id}.html` 每場有效活動一頁(單一 `Event` + `BreadcrumbList` JSON-LD、canonical、og、講師/地區交叉連結、報名 CTA);② `facilitators/{slug}.html` 講師彙整頁(講師欄以逗號/頓號/&/分號切分,不切空白以保「林佳逸 Jerry Lin」);③ `regions/{slug}.html` 地區彙整頁。各頁含 ItemList JSON-LD。實測:活動 51 / 講師 31 / 地區 8 / 歸檔 1。子頁目錄每次 build 乾淨重建(`shutil.rmtree`),不留下架孤兒頁。
  - **sitemap 擴充**:由首頁 1 條 → 92 條(首頁 + 51 活動 + 31 講師 + 8 地區 + 歸檔)。首頁卡片預渲染 `<a href>` 改指向 `events/{id}.html`,爬蟲爬到真實長尾 URL。
  - **og:image 自動生成**:新增 `Py/build_og.py`(Pillow),1200×630 漸層品牌底圖浮上標題/日期/地區·講師·主辦,輸出 `assets/og/{id}.png` + `default.png`;`build_site_json.py` 依檔案存在與否寫入各頁 `og:image`/`twitter:card`(圖不在就不寫死 404)。index.html head 補上預設 og:image 與 twitter:card。
  - **workflow**:`daily.yml` 加裝 `Pillow` + `fonts-noto-cjk`,新增 `build_og`(在 build_site_json 前)步驟,commit 納入 `events/ facilitators/ regions/ archive/ assets/`。
  - **待人工**(零成本、最即時):GSC「Sitemap」分頁提交 `sitemap.xml`、「網址審查」要求建立索引;向 5 來源機構爭取反向連結。
- **上線修正(同日稍晚)** — 前述工程一度只完成「本機 build」即記為完成,但 `D:\JoeProj\SatirDaily` 從未 `git init`/接 remote,故**從沒 push**,線上仍是 06-23 舊單頁站(活動頁 404、sitemap 仍 1 條)。本次補做:在 D `git init` → 接 `guru4tw/SatirDaily` remote → `reset --soft origin/main`(保留工作樹)→ 安全審查(151 新增/7 修改/**0 刪除**,遠端 google 驗證檔等未動)→ commit + push(`52fbb08..1165edc`)→ Pages 重建 `built`。線上實證:`events/shiuhli-1040.html` 不再 404、`sitemap.xml` 1→92。**教訓:「完成」一律以線上 URL 為準,本機 build ≠ 部署;新工作目錄先確認 `.git` 存在再宣告完成。** 反向連結 5 家成品見 `Docs/outreach_letters.md`。GSC 提交仍待人工。

## 2026-06-23

- **design-review 6-8 + 兩段標題副標一致化** — 首頁「薩提爾模式的傳承,與他們留下的話」原為粗襯線(`.voices-intro`),改為與「陪你找到你自己的內在聲音」(`.lede`)同格式(Noto Sans / 細體 / `--ink-soft`)。design-review 綜整清單第 7、8 項落地:(7) 用 `localStorage`(`satirdaily.prefs`)記住分頁/地區/排序/關鍵字,回訪自動還原,`selectTab` 加 `keepSort` 讓還原時不被分頁預設排序覆蓋;(8) 有日期的活動新增「加入 Google 行事曆」按鈕,開 `calendar.google.com/calendar/render?action=TEMPLATE` 預填頁,自動帶入標題/全天日期(dates 結束日 exclusive)/說明(宗旨+內容+報名連結)/地點。第 6 項(帶領者/主辦可點篩選)前一筆已完成。
- **design-review 落地 + 成蒂稱謂調整** — 移除「✓ 連結已驗證」徽章(連結正常為常態,不另標;僅 `link_ok===false` 留「⚠ 連結待確認」);次要文字色加深至 WCAG AA(`--ink-faint` → `#647571`);tab 補 aria-controls/tabindex/方向鍵與 focus-visible;加載入骨架與更友善的空/錯誤狀態;帶領者・主辦改可點 chip → 篩選 + 進行中篩選條件可清除。成蒂稱謂改「薩提爾嫡傳 ·體驗式家族,婚姻伴侶治療」(index 與 `Docs/design-review.html` 同步)。
- **首頁加入薩提爾理念傳承 + 兩段式版面** — hero 分兩部分:文案區(標題「薩提爾」+「薩提爾模式的傳承,與他們留下的話」+ 四位專家卡:Virginia Satir / Maria Gomori / John Banmen / 成蒂,各含代表提示、透鏡、三則語錄);活動區(標題「台灣薩提爾活動」+ 副標「陪你找到你自己的內在聲音」)。語錄同出處合併標示(只在末句掛書名)。eyebrow 由「每天自動更新」改為動態「上次更新 <updated_at>」,計數膠囊改「共 N 場活動」。語錄出處:成蒂《我們之間》、葛茉莉《愛與自由》、貝曼薩提爾轉化系統治療;Satir 三句為通行格言、未查到確切書目故留白。另設計健檢文件 `Docs/design-review.html` 由六位擴為八位專家視角(補 Satir、成蒂)。
- **連結溯源 + 自動驗證** — 每筆活動的「來源」改成可點連結,直接連回原始活動頁(`source_url`,由 `signup_url` 推導)。新增獨立驗證器 `Py/verify_links.py`:逐筆連回原始頁確認連結有效,把 `link_ok` / `link_checked_at` 寫回資料,前端以「✓ 連結已驗證 / ⚠ 連結待確認」標示。產報告 `Docs/link_report.json`。daily pipeline 串成 crawl → verify_links → build → commit。首次全量驗證:77 筆全通過。
- **首頁文案/視覺調整** — 大 logo 配色對齊小 logo(`#2c8c84`/`#7cc0b8`,opacity .7);hero 大字改「薩提爾」;副標改「台灣薩提爾活動資訊!」。(commit `f5ce57a`)

## 2026-06-22 ~ 06-23(初版建置)

- **三 tab 前端 + 爬蟲 + 橋接** — 前端分「近期 / 日期未定 / 已過去」三 tab;完成 5 支爬蟲(shiuhli / lopwilldo / comflow / satir_org / omia);`build_site_json.py` 把 `Docs/events.json` 正規化成前端契約。events.json 共 77 筆。(commit `3a8cf6e`)
- **GitHub Pages 部署** — 網址 https://guru4tw.github.io/SatirDaily/ ,觸發 Pages rebuild。(commit `400ea8c` / `99610e2`)
- **專案初始化** — SatirDaily 前端骨架 + 範例 events.json。三層全靜態架構(GitHub Actions 排程 + Python 爬蟲 + GitHub Pages 前端),全部免費。(commit `714d5a8`)
