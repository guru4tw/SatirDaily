# Satir 網站清單（人工維護的輸入檔）
#
# 這份檔只放「來源網站」，是你日常唯一要手改的檔。
# discover_sources.py 會讀這裡每一條，做連線檢查與結構偵測，
# 產出 parser 友善的 Satir_source.md（那份是自動產物，勿手改）。
#
# 一行一個來源，欄位用 | 分隔，URL 之外都可省略：
#     名稱 | 入口URL | 地區 | 備註
# 規則：
#   - 含 http(s):// 的那一段視為 URL（必填）
#   - URL 之前的字 = 名稱（省略則用網域當名稱）
#   - URL 之後第一段 = 地區，其餘 = 備註
#   - 行首的「-」「*」會被忽略（可寫成 markdown 清單）
#   - # 開頭的行與空行會被忽略
#
# 台灣薩提爾相關機構與課程連結清單

- [旭立文教基金會](https://www.shiuhli.org.tw/course)
- [台灣薩提爾人文發展中心](https://www.satir.com.tw/)
- [台灣薩提爾成長模式推展協會](https://www.satir.org.tw/)
- [長耳兔心靈維度](https://lopwilldo.com/)
- [心流逸境教育平台](https://comflow.tw/category/%E6%B4%BB%E5%8B%95/%E8%96%A9%E6%8F%90%E7%88%BE)
- [OMIA 學東西](https://www.omia.com.tw/)
- [Accupass 活動通（售票平台）](https://www.accupass.com/search?q=%E8%96%A9%E6%8F%90%E7%88%BE)