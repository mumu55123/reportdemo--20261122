# 台股情報查詢系統（GitHub Pages 版）

這個資料夾可直接作為 GitHub repository 的根目錄。網站是靜態頁面；每日新聞與上市櫃行情由 GitHub Actions 在雲端取得並部署，使用者電腦不需要安裝 Python。

## 部署

1. 在 GitHub 建立一個新的 **Public** repository，主要分支使用 `main`。
2. 將本資料夾中的所有檔案與 `.github` 資料夾上傳到 repository 根目錄。
3. 在 repository 開啟 **Settings → Pages**，將 **Build and deployment → Source** 設為 **GitHub Actions**。
4. 開啟 **Actions**，執行 **Update daily data and publish site** workflow。成功後可在 workflow 的部署摘要看到網站網址。

之後每次更新程式時，push 到 `main` 會重新部署；Actions 也會在平日排程更新資料。

## 每日更新

排程設為 UTC 01:05（台北時間 09:05），取證交所與櫃買中心的上市櫃公司清單及行情快照，並產生 `data/stocks.json`、`data/news.json`。新聞只保留前一平日 13:30 至當日 09:00 發布的國際政經報導，從 Yahoo 股市國際財經 RSS、鉅亨網頭條與 Reuters Business 新聞來源篩選，排除股市漲跌、開收盤與指數走勢，最多五篇。GitHub Actions 排程可能延遲執行；台灣休市日目前以週末推算，尚未接入交易所休市日曆。

股票搜尋可查詢擷取清單內的上市櫃公司，顯示公司名稱、產業分類、當日開盤及前一交易日收盤。報價端點或新聞來源若暫時無法取得，該次 workflow 會在 Actions 執行記錄中顯示錯誤。

## 來源與連結

- 上市公司資料：[TWSE OpenAPI](https://openapi.twse.com.tw/)
- 上櫃公司資料：[TPEx OpenAPI](https://www.tpex.org.tw/openapi/)
- Yahoo 個股頁面使用 `https://tw.stock.yahoo.com/quote/{代碼}`。
- 鉅亨個股頁面使用 `https://www.cnyes.com/twstock/profile.aspx?code={代碼}`。
- 排程使用 GitHub Actions 的 `schedule` 事件；時間以 UTC 表示，GitHub 可能延遲執行。
