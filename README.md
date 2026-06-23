# SatirDaily

全台薩提爾活動每日自動匯整網站。每天主動搜尋各來源活動,依日期遠近排序,提供自訂排序與多關鍵字搜尋。

**架構**:GitHub Pages(顯示)+ GitHub Actions(每日排程)+ `events.json`(資料)。全部免費,前端純靜態。

## 檔案

| 檔 | 說明 |
|---|---|
| `index.html` | 前端,讀 `events.json`,排序/搜尋/篩選全在瀏覽器端 |
| `events.json` | 活動資料(目前為手填範例) |
| `Docs/discover_sources.py` | 來源探索:維護 `SEED_SOURCES`、健康檢查、產 `Satir_list.md` |
| `Docs/Satir_list.md` | 來源名冊(自動產生,勿手改) |
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
- [ ] 部署 GitHub Pages

成本:免費。詳見計畫書。
