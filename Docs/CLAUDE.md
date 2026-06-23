# CLAUDE.md — 薩提爾活動清單網站

> 全台薩提爾活動每日自動匯整網站。GitHub Pages + GitHub Actions + `events.json`，全部免費。
> 完整計畫見 [satir-events-plan.htm](satir-events-plan.htm)。

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

1. `discover_sources.py` — 重建 `Satir_list.md`(來源名冊 + 健康檢查),**不抓活動內容**
2. 依 `Satir_list.md` 逐站跑專屬爬蟲(如 `crawlers/shiuhli.py`)→ 寫 `events.json`
3. Actions commit + Pages 刷新

**為何來源清單與活動爬取分開**:來源變動慢、人工可讀;活動變動快、機器抓。分層後新增機構只要加一筆 + 寫一支 parser,互不干擾。

---

## 檔案地圖(現況)

| 檔 | 狀態 | 說明 |
|---|---|---|
| `discover_sources.py` | 已可運作 | 維護 `SEED_SOURCES` 名冊、HTTP 健康檢查、產 `Satir_list.md` |
| `Satir_list.md` | 自動產生 | 勿手改,改 `SEED_SOURCES` 後重跑腳本重建 |
| `satir-events-plan.htm` | 計畫書 | 唯讀參考,單檔內嵌 CSS |
| `crawlers/*.py` | 待開發 | 各來源專屬 parser,輸出符合資料模型的 JSON |
| `events.json` | 待建 | 活動資料,前端讀取 |

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

第一個待開發:`shiuhli`(旭立文教基金會),課程頁含薩提爾分類標籤、日期、價格、講師、分頁 `?page=N`,結構穩定。

---

## 開發紀律

- **新增來源** — 改 `discover_sources.py` 的 `SEED_SOURCES`,填 `key/name/url/homepage/region/notes`,勘查後設 `planned` 並規劃 `parser_module`,寫好爬蟲改 `ready`,重跑腳本。
- **爬蟲友善** — 沿用既有 `HEADERS`(SatirEventBot UA)與請求間延遲,勿短時間連發。
- **Facebook** — 反爬嚴格、條款受限,列低優先,改人工補登或僅貼連結,勿硬爬。
- **正評真實性** — `highlights` 須有出處或同意,避免不實宣傳。
- **資料正確性** — 卡片標「資料更新日」(`fetched_at`),保留 `signup_url` 讓使用者核對。
- **Python 編碼** — 檔案 UTF-8,`# -*- coding: utf-8 -*-`,沿用 dataclass + type hint 風格。

---

## 環境

- cwd:`H:\ALG_Joe\Satir\Docs`(目前所有檔在此;repo 化後 `crawlers/`、`events.json`、前端置於 repo 根)
- 依賴:`requests`(必要)、`beautifulsoup4`(`--discover` 探索模式才需)
- 執行:`python discover_sources.py`(健康檢查 + 重建清單);`--discover` 加搜尋探索;`--timeout N` 改逾時
- 非 git repo(尚未初始化)
