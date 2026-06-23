# SatirDaily

網站:https://guru4tw.github.io/SatirDaily/

全台薩提爾活動每日自動匯整網站。每天主動搜尋各來源活動,依日期遠近排序,提供自訂排序與多關鍵字搜尋。

**架構**:GitHub Pages(顯示)+ GitHub Actions(每日排程)+ `events.json`(資料)。全部免費,前端純靜態。

## 檔案

| 檔 | 說明 |
|---|---|
| `index.html` | 前端,讀 `events.json`,排序/搜尋/篩選全在瀏覽器端 |
| `events.json` | 活動資料(目前為手填範例) |
| `Docs/Satir_website.md` | 人工維護的來源網站清單(`- [名稱](URL)`),唯一手改檔 |
| `Docs/discover_sources.py` | 讀 `Satir_website.md`,逐站連線檢查 + 結構偵測,產 `Satir_source.md` |
| `Docs/Satir_source.md` | 來源規格(自動產生,含結構線索與建議解析路徑,勿手改) |
| `Docs/satir-events-plan.htm` | 完整計畫書 |
| `crawlers/` | 各來源專屬爬蟲(待開發) |

## 本地預覽

需用 HTTP server(前端 `fetch` 不支援 `file://`):

```bash
python -m http.server 8000
# 開 http://localhost:8000/
```

## 每日 pipeline(規劃)

1. `python Docs/discover_sources.py` — 重建來源清單
2. 依清單逐站跑爬蟲 → 更新 `events.json`
3. GitHub Actions commit + Pages 刷新

## 開發進度

- [x] 前端骨架 + 範例 `events.json`(可顯示)
- [x] `discover_sources.py` 來源探索
- [ ] 第一支爬蟲 `crawlers/shiuhli.py`(旭立)
- [ ] GitHub Actions 每日排程
- [x] 部署 GitHub Pages

成本:免費。詳見計畫書。

## 分享 / 授權與注意事項

本專案匯整各機構**公開**的薩提爾活動資訊,無後端、無使用者資料、無 API 金鑰,適合公開。公開前/維護時請留意三點:

1. **公開前掃一次 git 歷史** — 確認從未誤 commit 過 `.env`、cookie、個人筆記等敏感檔。建議用 [gitleaks](https://github.com/gitleaks/gitleaks):`gitleaks detect --source .`。本 repo 為全新 git 起點,歷史乾淨。
2. **GitHub Actions 權限最小化** — workflow 僅用內建 `GITHUB_TOKEN` 且只開 `contents: write`(見 `.github/workflows/daily.yml`),無外洩風險;請勿在 repo Settings → Actions 把預設權限改寬。
3. **爬蟲禮儀** — 爬蟲沿用 `SatirEventBot` UA + 請求間延遲。fork 本專案者請遵守各來源站的 `robots.txt` 與服務條款,勿短時間連發。

**授權**:程式碼採 MIT。活動資料僅為匯整呈現,著作權歸原機構;**活動詳情一律以卡片「來源」連回的原始頁面為準**,本站不保證即時正確。
