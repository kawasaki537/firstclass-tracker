# 龍蝦 AI｜網頁版機票搜尋 Beta

此分支加入 `index.html` 顧客端表單，以及 `worker.js` Cloudflare Worker API。

## 必要限制
- 網頁需先部署 Worker 並設定 Secrets 才能執行真實搜尋。
- Worker 會將結果傳到已設定的單一 Telegram `CHAT_ID`，尚不是多位顧客各自收件的服務。
- Amadeus 報價不等於已保留座位。訂票連結目前是 Google Flights 航班搜尋頁，**不是精確對應該筆報價的直達結帳頁**，使用者需再次核對即時價格與座位。
- 日期彈性、行李條件與排序的部分選項目前只是表單收集，後端尚未完整套用；不可宣稱這些條件已被保證篩選。
- Amadeus 的航線、航空公司與票價覆蓋可能有限，先實測再對外提供服務。

## 部署
1. 在 Cloudflare Dashboard → Workers & Pages 建立 Worker，把 `worker.js` 貼上並部署。
2. 在 Worker 的 Settings → Variables and Secrets 設定 Secret：`AMADEUS_CLIENT_ID`、`AMADEUS_CLIENT_SECRET`、`BOT_TOKEN`、`CHAT_ID`。
3. 設定一般變數 `ALLOWED_ORIGIN` 為 GitHub Pages 網站來源，例如 `https://kawasaki537.github.io`。公開使用前不要保留萬用來源。
4. 複製 Worker URL，修改 `index.html` 裡的 `API_BASE_URL`，將 placeholder 換成 Worker URL（不含尾端斜線）。
5. 合併此分支後，進 GitHub Repo Settings → Pages，選 main 分支與根目錄 `/(root)` 發布。
6. 用近期日期實測搜尋、Telegram 實際收件與訂票入口，再記錄 Amadeus 價格與網站價格差異。

直接在瀏覽器開啟 `index.html` 可以預覽表單；後端未設定時，按搜尋會顯示需要部署的提示。不要把任何 API Token 寫進前端或公開 Repo。
