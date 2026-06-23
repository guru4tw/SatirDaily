# SatirDaily 網站 Google 排名提升（SEO）策略指南

> 本指南針對 **SatirDaily**（https://guru4tw.github.io/SatirDaily/）量身打造。
> **網站定位（重要）**：SatirDaily 是「**全台薩提爾活動／課程／工作坊每日匯整清單**」——
> 使用者是來**找工作坊、找課程、找報名連結**的，屬於**交易型搜尋意圖**。
> （早期版本誤把本站當成「每日金句／自我覺察練習網站」，關鍵字方向因此瞄錯，本版已修正。）

託管於 GitHub Pages，載入快、自帶 CDN 與 HTTPS；技術型 SEO 與內容權重則需針對性優化。

---

## 〇、最近一次更新已完成項（2026-06）

| 項目 | 狀態 | 備註 |
| :--- | :---: | :--- |
| `<title>` / `<meta description>` 對準活動意圖 | ✅ | 已改為「薩提爾工作坊・課程・活動總覽」 |
| `robots.txt` | ✅ | 根目錄，未擋 Googlebot，指向 sitemap |
| `sitemap.xml` | ✅ | 由 `build_site_json.py` 每日自動產，`lastmod`=資料更新日 |
| Google Search Console 驗證 | ✅ | HTML 檔驗證（`googlede28061b78c7b0f2.html`）已上線 |
| Event 結構化資料（JSON-LD） | ✅ | `ItemList<Event>`，**伺服器端預渲染**進 `index.html`，72 筆 |
| 內容預渲染（解決 SPA 空白 HTML） | ✅ | 77 場活動寫入原始 HTML，Googlebot 不靠 JS 即可索引 |
| Open Graph / canonical | ✅ | 分享預覽 + 正規網址 |
| 「關於薩提爾」長文字（抗 thin content） | ✅ | 含 2 則 FAQ，覆蓋核心關鍵字 |
| LINE / Facebook 分享按鈕 | ✅ | 頁尾分享列 |
| 在 GSC 提交 sitemap | ⬜ | **待手動**：GSC 左側 Sitemap → 提交 `sitemap.xml` |
| 反向連結 / 社群擴散 | ⬜ | 長期經營（見 §四） |

---

## 一、 關鍵字策略（對準交易型意圖）

搜尋引擎的核心是「滿足使用者意圖」。本站使用者意圖是**找活動、要報名**，
應主打**交易型**長尾關鍵字，而非資訊型（金句、練習）。

### 1. 關鍵字佈局

* **核心關鍵字：** 薩提爾工作坊、薩提爾課程、薩提爾活動、薩提爾研習。
* **長尾／高轉換關鍵字：**
    * 帶領者型：李崇建工作坊、張天安工作坊、陳桂芳工作坊…（依清單講師動態補充）。
    * 主題型：薩提爾親子工作坊、薩提爾伴侶／婚姻課程、薩提爾自我覺察課程、原生家庭療癒。
    * 地區型：台北／台中／高雄 薩提爾課程、北部薩提爾工作坊。
    * 行動型：薩提爾 報名、薩提爾課程 推薦、薩提爾活動 時間。
* **應用位置：** `<title>`、`<meta description>`、`<h1>`（含 sr-only 描述）、
  「關於薩提爾」長文字、各活動卡片標題（講師＋主題天然帶關鍵字）。

### 2. 內容深度（抗 Thin Content）

* 已加「關於薩提爾模式與本站」+「如何挑選工作坊」「多久更新」FAQ。
* **可再做**：為熱門帶領者或主題建立獨立介紹段落／頁面，增加主題關聯度（Topical Relevance）。

### 3. 語意化 HTML

* 單一 `<h1>`（「薩提爾」+ sr-only 完整描述），`<h2>` 用於「台灣薩提爾活動」「關於薩提爾」，
  預渲染活動以 `<h3>` 標題——層級正確，利於爬蟲理解結構。

---

## 二、 技術型 SEO（靜態站基礎設施）

### 1. SPA 內容可索引性（本站最關鍵的一役，已處理）

**問題**：前端以 JS `fetch` 渲染活動，原始 HTML 幾乎空白；Google 對 JS 內容收錄慢且常漏。
**解法（已實作）**：`build_site_json.py` 每日把活動清單 + JSON-LD **預渲染寫進 `index.html`**，
Googlebot 抓原始 HTML 就看得到 77 場活動與結構化資料；前端 JS 載入後再以互動版覆寫（漸進增強）。

### 2. Sitemap / robots.txt（已完成）

```text
User-agent: *
Allow: /
Sitemap: https://guru4tw.github.io/SatirDaily/sitemap.xml
```

### 3. Google Search Console（已驗證；待提交 sitemap）

1. 驗證擁有權 ✅（HTML 檔法）。
2. **待辦**：左側 Sitemap → 輸入 `sitemap.xml` → 提交。
3. 收錄加速：用「網址審查」貼首頁，按「要求建立索引」。

### 4. 行動裝置友善（Mobile-First）

* 確認 RWD 在各尺寸正常；互動元件（分頁、報名鈕）≥ 48×48 px。

---

## 三、 網站效能與體驗（Core Web Vitals）

* GitHub Pages 自帶 CDN；注意第三方資源：
    * Google Fonts 已用 `preconnect` + `display=swap`，避免阻塞渲染。
    * 若日後加圖片／插圖，轉 WebP 並壓縮。
* HTTPS：repo 設定勾選 **Enforce HTTPS**。

---

## 四、 外部權重與社群推廣（Off-Page SEO）

反向連結是權威度核心，對活動站尤其能同時帶來**流量**與**信任**。

* **機構互連（最高價值）**：主動聯繫清單上的機構（長耳兔、旭立、薩提爾協會、心流逸境、OMIA…），
  請對方在自家網站放一個「活動總覽」連結——你幫他們曝光，他們給你高相關反向連結，雙贏。
* **社群擴散**：到 Facebook 的薩提爾／親職／諮商成長社團分享；頁面已內建 LINE/FB 分享鈕。
* **內容平台**：在 Matters、方格子、Medium 寫薩提爾相關文章並嵌入本站連結（contextual backlink）。
* **開源資源**：README 寫明專案動機，爭取 GitHub Stars 與心理／開源 Awesome List 收錄。

---

## 五、 下一步檢核清單（依效益排序）

| 檢查項目 | 預估效益 | 優先級 | 狀態 |
| :--- | :--- | :---: | :---: |
| 在 GSC 提交 `sitemap.xml` | 加速收錄 | 高 | ⬜ 待手動 |
| 用「網址審查」要求建立索引 | 立即送進佇列 | 高 | ⬜ 待手動 |
| 取得 1～3 個機構反向連結 | 權威度 + 流量 | 高 | ⬜ |
| 為熱門帶領者／主題加介紹段落 | 主題關聯 + 長尾 | 中 | ⬜ |
| 在心理成長社團分享 | 自然曝光 | 中 | ⬜ |
| 持續監看 Core Web Vitals | 維持體驗分數 | 低 | ⬜ |
