# 薩提爾活動 — 來源規格（Satir_source.md）

> 自動產生於 **2026-06-24 22:21**，由 `discover_sources.py` 讀 `/home/runner/work/SatirDaily/SatirDaily/Docs/Satir_website.md` 產出。
> **本檔為自動產物，請勿手改**；要增刪來源請改 `/home/runner/work/SatirDaily/SatirDaily/Docs/Satir_website.md`，再重跑腳本。
>
> 用途：每個來源在「來源細節」段提供 **入口、連線狀態、結構線索、建議解析路徑、對應 parser 模組**，讓各網站專屬爬蟲知道怎麼抓。

**統計**：共 7 筆　|　🟢 可連線 7　|　✅ 已可爬 0　🛠 待開發 0　⬜ 待勘查 7

---

## 來源總覽

| 代號 | 機構名稱 | 地區 | 爬蟲狀態 | 連線檢查 | 入口連結 |
|------|----------|------|----------|----------|----------|
| `shiuhli` | 旭立文教基金會 | — | ⬜ 待勘查 | 🟢 可連線 (HTTP 200) | [列表頁](https://www.shiuhli.org.tw/course) |
| `satir` | 台灣薩提爾人文發展中心 | — | ⬜ 待勘查 | 🟢 可連線 (HTTP 200) | [列表頁](https://www.satir.com.tw/) |
| `satir_org` | 台灣薩提爾成長模式推展協會 | — | ⬜ 待勘查 | 🟢 可連線 (HTTP 200) | [列表頁](https://www.satir.org.tw/) |
| `lopwilldo` | 長耳兔心靈維度 | — | ⬜ 待勘查 | 🟢 可連線 (HTTP 200) | [列表頁](https://lopwilldo.com/) |
| `comflow` | 心流逸境教育平台 | — | ⬜ 待勘查 | 🟢 可連線 (HTTP 200) | [列表頁](https://comflow.tw/category/%E6%B4%BB%E5%8B%95/%E8%96%A9%E6%8F%90%E7%88%BE) |
| `omia` | OMIA 學東西 | — | ⬜ 待勘查 | 🟢 可連線 (HTTP 200) | [列表頁](https://www.omia.com.tw/) |
| `accupass` | Accupass 活動通（售票平台） | — | ⬜ 待勘查 | 🟢 可連線 (HTTP 200) | [列表頁](https://www.accupass.com/search?q=%E8%96%A9%E6%8F%90%E7%88%BE) |

---

## 來源細節（供 parser 開發）

### `shiuhli` — 旭立文教基金會

- **首頁**：https://www.shiuhli.org.tw/
- **爬蟲入口**：https://www.shiuhli.org.tw/course
- **主要地區**：—
- **爬蟲狀態**：⬜ 待勘查
- **建議爬蟲模組**：`crawlers/shiuhli.py`
- **連線檢查**：🟢 可連線 (HTTP 200)　（檢查時間 2026-06-24 22:21）
- **Content-Type**：`text/html`
- **頁面標題**：旭立文教基金會
- **結構線索（自動偵測，需人工確認）**：偵測到分頁樣式（?page= 或 /page/）
- **建議解析路徑**：
    1. 解析 HTML：找重複的活動卡片區塊，逐塊取標題/日期/連結
    2. 分頁：沿 ?page= 或 /page/ 遞增直到無新資料
    3. 每筆對齊 events.json schema（id/title/date_start/region/signup_url/...）

### `satir` — 台灣薩提爾人文發展中心

- **首頁**：https://www.satir.com.tw/
- **爬蟲入口**：https://www.satir.com.tw/
- **主要地區**：—
- **爬蟲狀態**：⬜ 待勘查
- **建議爬蟲模組**：`crawlers/satir.py`
- **連線檢查**：🟢 可連線 (HTTP 200)　（檢查時間 2026-06-24 22:21）
- **Content-Type**：`text/html`
- **頁面標題**：薩提爾課程｜親子關係、自我覺察｜可以說錯話工作室
- **結構線索（自動偵測，需人工確認）**：疑似 WordPress（可試 /wp-json REST API）；含 JSON-LD 結構化資料（可直接取 Event schema）
- **建議解析路徑**：
    1. 優先：抓 <script type=application/ld+json>，取 schema.org Event/Course 結構化欄位
    2. 次選：試 REST API /wp-json/wp/v2/posts（或自訂 post type），回 JSON 免解 HTML
    3. 每筆對齊 events.json schema（id/title/date_start/region/signup_url/...）

### `satir_org` — 台灣薩提爾成長模式推展協會

- **首頁**：https://www.satir.org.tw/
- **爬蟲入口**：https://www.satir.org.tw/
- **主要地區**：—
- **爬蟲狀態**：⬜ 待勘查
- **建議爬蟲模組**：`crawlers/satir_org.py`
- **連線檢查**：🟢 可連線 (HTTP 200)　（檢查時間 2026-06-24 22:21）
- **Content-Type**：`text/html`
- **頁面標題**：首頁 - 台灣薩提爾成長模式推展協會
- **結構線索（自動偵測，需人工確認）**：含 JSON-LD 結構化資料（可直接取 Event schema）；頁面含 <table>，列表可能為表格
- **建議解析路徑**：
    1. 優先：抓 <script type=application/ld+json>，取 schema.org Event/Course 結構化欄位
    2. HTML 列表在 <table>：逐 <tr> 取欄位（日期/標題/連結）
    3. 每筆對齊 events.json schema（id/title/date_start/region/signup_url/...）

### `lopwilldo` — 長耳兔心靈維度

- **首頁**：https://lopwilldo.com/
- **爬蟲入口**：https://lopwilldo.com/
- **主要地區**：—
- **爬蟲狀態**：⬜ 待勘查
- **建議爬蟲模組**：`crawlers/lopwilldo.py`
- **連線檢查**：🟢 可連線 (HTTP 200)　（檢查時間 2026-06-24 22:21）
- **Content-Type**：`text/html`
- **頁面標題**：長耳兔心靈維度｜薩提爾工作坊、親子溝通與職場對話課程
- **結構線索（自動偵測，需人工確認）**：疑似 WordPress（可試 /wp-json REST API）；偵測到分頁樣式（?page= 或 /page/）；含 JSON-LD 結構化資料（可直接取 Event schema）；頁面含 <table>，列表可能為表格
- **建議解析路徑**：
    1. 優先：抓 <script type=application/ld+json>，取 schema.org Event/Course 結構化欄位
    2. 次選：試 REST API /wp-json/wp/v2/posts（或自訂 post type），回 JSON 免解 HTML
    3. HTML 列表在 <table>：逐 <tr> 取欄位（日期/標題/連結）
    4. 分頁：沿 ?page= 或 /page/ 遞增直到無新資料
    5. 每筆對齊 events.json schema（id/title/date_start/region/signup_url/...）

### `comflow` — 心流逸境教育平台

- **首頁**：https://comflow.tw/
- **爬蟲入口**：https://comflow.tw/category/%E6%B4%BB%E5%8B%95/%E8%96%A9%E6%8F%90%E7%88%BE
- **主要地區**：—
- **爬蟲狀態**：⬜ 待勘查
- **建議爬蟲模組**：`crawlers/comflow.py`
- **連線檢查**：🟢 可連線 (HTTP 200)　（檢查時間 2026-06-24 22:21）
- **Content-Type**：`text/html`
- **頁面標題**：薩提爾 - 心流逸境教育平台
- **結構線索（自動偵測，需人工確認）**：疑似 WordPress（可試 /wp-json REST API）；含 JSON-LD 結構化資料（可直接取 Event schema）
- **建議解析路徑**：
    1. 優先：抓 <script type=application/ld+json>，取 schema.org Event/Course 結構化欄位
    2. 次選：試 REST API /wp-json/wp/v2/posts（或自訂 post type），回 JSON 免解 HTML
    3. 每筆對齊 events.json schema（id/title/date_start/region/signup_url/...）

### `omia` — OMIA 學東西

- **首頁**：https://www.omia.com.tw/
- **爬蟲入口**：https://www.omia.com.tw/
- **主要地區**：—
- **爬蟲狀態**：⬜ 待勘查
- **建議爬蟲模組**：`crawlers/omia.py`
- **連線檢查**：🟢 可連線 (HTTP 200)　（檢查時間 2026-06-24 22:21）
- **Content-Type**：`text/html`
- **頁面標題**：OMIA學東西 線上課程讓生活更美好
- **結構線索（自動偵測，需人工確認）**：含 JSON-LD 結構化資料（可直接取 Event schema）
- **建議解析路徑**：
    1. 優先：抓 <script type=application/ld+json>，取 schema.org Event/Course 結構化欄位
    2. 每筆對齊 events.json schema（id/title/date_start/region/signup_url/...）

### `accupass` — Accupass 活動通（售票平台）

- **首頁**：https://www.accupass.com/
- **爬蟲入口**：https://www.accupass.com/search?q=%E8%96%A9%E6%8F%90%E7%88%BE
- **主要地區**：—
- **爬蟲狀態**：⬜ 待勘查
- **建議爬蟲模組**：`crawlers/accupass.py`
- **連線檢查**：🟢 可連線 (HTTP 200)　（檢查時間 2026-06-24 22:21）
- **Content-Type**：`text/html`
- **頁面標題**：Search for Events by 薩提爾｜ACCUPASS
- **結構線索（自動偵測，需人工確認）**：Accupass 售票平台（查公開 API / 動態載入）
- **建議解析路徑**：
    1. 此為售票平台：改打其搜尋 API / 觀察 XHR，勿硬解靜態 HTML
    2. 每筆對齊 events.json schema（id/title/date_start/region/signup_url/...）

---

## 如何新增來源

1. 在 `/home/runner/work/SatirDaily/SatirDaily/Docs/Satir_website.md` 加一行：`- [名稱](入口URL)`（其後可接 ` | 地區 | 備註`，只有 URL 必填）。
2. 重跑 `python discover_sources.py` 重建本檔，看連線、結構線索與建議解析路徑。
3. 依該來源的「建議解析路徑」開發對應 `crawlers/<代號>.py`。
