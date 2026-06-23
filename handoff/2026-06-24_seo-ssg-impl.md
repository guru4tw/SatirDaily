# Handoff: SEO 計畫技術工程完成,剩 GSC 提交 + 反向連結信

**Date**: 2026-06-24 (session 末)
**Context @ handoff**: —
**Status**: milestone(技術全完成,剩人工項)

## TL;DR

依 `Docs/SatirDaily_SEO_Plan.html` 完成全部技術工程:過期活動分離、SSG 三階段多頁(活動/講師/地區頁)、archive 歸檔頁、sitemap 1→92 條、og:image 自動生成、workflow 串接。全部本機 build + 瀏覽器實測通過。剩兩件「只有使用者能做」的零成本人工項(GSC 提交 sitemap、反向連結信),以及一個我可代勞但待使用者點頭的選項(整理 §7 定稿信成可複製成品)。

## 已交付

- `Py/build_site_json.py` — 大幅擴充:bucket(upcoming/undated/past)、`build_pages()` 生成 events/facilitators/regions/archive 子頁、單一 Event+BreadcrumbList / ItemList JSON-LD、sitemap 擴充、og 依檔案存在寫入、首頁注入只收有效活動
- `Py/build_og.py` — 新檔,Pillow 畫 1200×630 分享圖到 `assets/og/{id}.png` + `default.png`,無 Pillow/字型則 graceful 略過
- `index.html` — head 加 og:image/twitter:card;JS `injectJsonLd` 加 `!isPast` 過濾;prerender 卡片改連 `events/{id}.html`(由 build 注入)
- `.github/workflows/daily.yml` — 裝 Pillow + fonts-noto-cjk,加 build_og 步驟(在 build_site_json 前),commit 納入 events/ facilitators/ regions/ archive/ assets/
- `events/`(51)、`facilitators/`(31)、`regions/`(8)、`archive/index.html`(1)、`assets/og/`(52)、`sitemap.xml`(92 URL) — build 產物
- `Log/history.md`、`CLAUDE.md` — 補 2026-06-24 紀錄與檔案地圖

## 未竟事項

**首要(需使用者親手,我做不到)**:
- [ ] **GSC 提交 sitemap** — Search Console「Sitemap」分頁交 `sitemap.xml`(別誤交 google 驗證檔 `googlede28061b78c7b0f2.html`);再「網址審查」對首頁要求建立索引。OAuth 後台,Claude 無法代勞
- [ ] **反向連結信** — 向長耳兔/旭立/薩提爾協會/心流逸境/OMIA 各發一封,範本在 `Docs/SatirDaily_SEO_Plan.html` §7

**我可代勞(待使用者點頭)**:
- [ ] 把 §7 定稿信整理成可直接複製貼上的成品(含 5 家各別稱呼)— session 末已主動提議,使用者尚未回覆

**選配/長期(計畫 P3)**:
- [ ] `/guide/` 主題知識文 + 內部連結;自訂網域(唯一破「全免費」項)

## 易踩坑 / Session-only 知識

新 session 不會自動知之事:

- **`python -c "..."` 與含 `&&`/`grep` 的 Bash 複合命令會被 sandbox 擋** — 改用 dedicated Read/Grep 工具,或跑單一 `python Py/xxx.py`(這類專案腳本可過)。驗證資料別寫一次性 python -c
- **build_og 必須在 build_site_json 之前跑** — 後者用 `og_url_if_exists()` 檢查 PNG 是否存在才寫 og meta,圖不在就不寫(避免 404)。workflow 已排好順序;本機手動重建也要照此序
- **build_og 預設只補缺漏(skip 已存在),不重畫** — 活動標題改了 og 圖不會更新;要全重畫用 `--force`。刻意如此避免每日 commit 51 張 PNG 造成 repo 膨脹。assets/og 只增不刪(過期活動的圖會殘留,目前可接受)
- **講師欄切分刻意不切空白** — 用逗號/頓號/&/分號切(`FAC_SPLIT_RE`),保「林佳逸 Jerry Lin」這種中英並列同一人。代價:「張蘊心 鍾淑華」這種空白分隔的兩人會被當一頁(可接受,計畫 §4 已標講師正規化為已知難點)
- **TODAY 用 `datetime.date.today()`** — 本機實測當天 upcoming:46 undated:5 past:26。換日會變,屬正常
- **子頁目錄每次 build `shutil.rmtree` 乾淨重建** — 手改 events/facilitators/regions/archive 內檔案會被下次 build 清掉,勿手改;改模板要改 `build_site_json.py` 的 template 函式
- **本機驗證用 preview server**:`.claude/launch.json` 已設 `satir-static`(python http.server 8765);中文路徑頁要 percent-encode(如 `regions/%E5%8F%B0%E5%8C%97.html`)
