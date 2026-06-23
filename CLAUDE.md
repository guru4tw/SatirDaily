# CLAUDE.md — 薩提爾活動清單網站

> 全台薩提爾活動每日自動匯整網站。GitHub Pages + GitHub Actions + `events.json`，全部免費。
> 完整計畫見 [satir-events-plan.htm](Docs/satir-events-plan.htm)。

---

## 專案目標

每天主動搜尋全台薩提爾相關活動，依日期遠近排序，提供自訂排序與多關鍵字搜尋。
資料宗旨、內容、正面回饋為呈現重點(畫龍點睛),不要弱化成冷冰冰條列。

---

## 架構(三層全靜態 / 全免費)

| 層 | 角色 | 說明 |
|---|---|---|
| GitHub Actions | Scheduler | cron 每日觸發,跑爬蟲、更新 JSON、自動 commit |
| Python 爬蟲 | Crawler | 抓各來源活動,正規化後寫入 `events.json` |
| GitHub Pages | Frontend | 純靜態 HTML + JS,排序/搜尋/篩選全在瀏覽器端 |

關鍵:Pages 只負責顯示,不跑程式;「每天更新」由 Actions 完成。前端無後端、無運算費。

---

## 每日 pipeline(順序固定)

1. `discover_sources.py` — 讀人工維護的 `Satir_website.md`,逐站健康檢查 + 結構偵測,重建 `Satir_source.md`,**不抓活動內容**
2. 依 `Satir_source.md` 逐站跑專屬爬蟲(如 `crawlers/shiuhli.py`)→ 寫 `events.json`
3. Actions commit + Pages 刷新

**為何來源清單與活動爬取分開**:來源變動慢、人工可讀;活動變動快、機器抓。分層後新增機構只要加一筆 + 寫一支 parser,互不干擾。

---

## 檔案地圖(現況)

| 檔 | 狀態 | 說明 |
|---|---|---|
| `Satir_website.md` | **人工維護** | 唯一手改檔。一行一來源:`名稱 \| URL \| 地區 \| 備註`(只有 URL 必填) |
| `Py/discover_sources.py` | 已可運作 | 讀 `Docs/Satir_website.md`,逐站健康檢查 + 結構偵測,產 `Docs/Satir_source.md` |
| `Satir_source.md` | 自動產生 | parser 規格(連線/結構線索/建議解析路徑/模組名),勿手改;改 `Satir_website.md` 後重跑 |
| `satir-events-plan.htm` | 計畫書 | 唯讀參考,單檔內嵌 CSS |
| `Py/crawlers/*.py` | 開發中 | 各來源專屬 parser,輸出符合資料模型的 JSON。`shiuhli.py`(列表+詳情 HTML)、`lopwilldo.py`(The Events Calendar REST API)、`comflow.py`(分類頁 HTML)、`satir_org.py`(Joomla EventBooking 詳情頁)、`omia.py`(搜尋頁內嵌 cardList JSON)已完成 |
| `Py/build_site_json.py` | 已建 | 橋接腳本:讀 `Docs/events.json`(扁平陣列)→ 加 `price_min`(parse `price` 取最低)→ 包成 `{updated_at, count, events}` → 寫根 `events.json`。爬蟲與前端各自契約都不動 |
| `.github/workflows/daily.yml` | 已建 | 每日 cron(台北 05:00)+ 手動觸發:discover → 五站爬蟲 `--out` → build → 有變動才 commit/push |
| `Docs/events.json` | 已建(部分) | 爬蟲合併寫入的扁平陣列。目前 77 筆:shiuhli 18 + lopwilldo 26 + comflow 3 + satir_org 28 + omia 2 |
| `events.json`(根) | 自動產生 | GitHub Pages 服務的檔,前端 `index.html` fetch 此檔。由 `build_site_json.py` 從 `Docs/events.json` 正規化而來,勿手改 |

> Python 腳本統一置於 `Py/`(`discover_sources.py`、`crawlers/`);資料檔(`*.md`、`events.json`)仍在 `Docs/`。腳本內以 `__file__` 錨定 `../Docs`,故從任何 cwd 執行都對得到資料檔。

---

## 資料模型(`events.json` 單筆)

核心欄位:`id` `title` `purpose`(宗旨) `summary`(內容) `highlights`(正評,**須註明出處**) `date_start` `date_end` `region` `venue` `facilitator` `organizer` `price` `signup_url` `source` `fetched_at`。

新爬蟲輸出必須對齊此 schema,欄位名勿自創。完整範例見計畫書 §03。

---

## 來源狀態(`crawler_status`)

| 值 | 意義 |
|---|---|
| `ready` | 已寫好爬蟲,可實際抓 |
| `planned` | 已勘查結構、可爬,爬蟲待開發 |
| `todo` | 尚未勘查 |

**實勘修正**:多站首頁雖被自動偵測「含 JSON-LD」,實為 Yoast SEO 樣板(Organization/WebSite/WebPage),**非** Event/Course schema,勿盲信「JSON-LD 可直取活動」這條建議路徑。各站真實落點:`lopwilldo` = The Events Calendar REST(`/wp-json/tribe/events/v1/events`);`comflow` 的 `academy_courses` 不開 REST(404),改解分類頁 HTML(且為「依報名場次」之常設課程,無固定日期);`satir` 僅標準部落格 `post`(非活動);`satir_org`/`omia` 非 WordPress。`satir_org` 課程清單在 `/schedule`(依地區分頁),詳情頁為 Joomla EventBooking 外掛(`class="eb-event-*"`,含課程日期/截止日期/費用/講師),28 門皆有固定日期;`omia` 搜尋頁 `/searchProject/薩提爾` 伺服器端渲染,drupalSettings 內嵌 `cardList` JSON,命中 2 門李崇建線上課(隨到隨學、無固定日期)。待勘查:`satir`、`accupass`。

---

## 開發紀律

- **新增來源** — 在 `Docs/Satir_website.md` 加一行 `名稱 \| URL \| 地區 \| 備註`(只有 URL 必填),重跑 `python Py/discover_sources.py`。`key` 由網域自動推導,`homepage`/`parser_module`/結構線索皆自動產生。`crawler_status` 目前一律 `todo`,寫好爬蟲後到 parser 端管理。
- **合併寫入** — 每支爬蟲 `--out` 走各自的 `merge_into()`:讀現有 `events.json` → 去掉自家 `source` 舊筆 → 加新筆 → 依 `date_start` 排序寫回。故 pipeline 任何執行順序皆 idempotent,不會清掉別站資料。新爬蟲須沿用同模式(勿覆寫全檔)。
- **爬蟲友善** — 沿用既有 `HEADERS`(SatirEventBot UA)與請求間延遲,勿短時間連發。
- **Facebook** — 反爬嚴格、條款受限,列低優先,改人工補登或僅貼連結,勿硬爬。
- **正評真實性** — `highlights` 須有出處或同意,避免不實宣傳。
- **資料正確性** — 卡片標「資料更新日」(`fetched_at`),保留 `signup_url` 讓使用者核對。
- **Python 編碼** — 檔案 UTF-8,`# -*- coding: utf-8 -*-`,沿用 dataclass + type hint 風格。

---

## 環境

- cwd:`H:\ALG_Joe\Satir\Docs`(資料檔在此;Python 腳本在 `Py/`)
- 依賴:`requests`(必要)、`beautifulsoup4`(`--discover` 探索模式才需)
- 執行:`python Py/discover_sources.py`(健康檢查 + 重建清單,從 repo 根跑);`--timeout N` 改逾時
- 跑爬蟲:`python Py/crawlers/shiuhli.py --out`(寫 `Docs/events.json`,不帶值即用預設路徑)
- git repo(已初始化)
