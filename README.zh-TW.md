[English](README.md) | 繁體中文

# Warframe Devstream & Drops Notifier

定時檢查 Warframe [Livestreams 版](https://forums.warframe.com/forum/113-livestreams/)，有新的 **Devstream** 或 **Twitch Drop 活動**公告就發一則 Discord 通知。

只用 Python 標準庫，無需安裝套件，跑在 GitHub Actions 上。

> Discord 訊息是繁體中文。要改語言就改 `main.py` 的 `build_message`。

## 運作方式

每次排程觸發 `main.py`：

1. 抓 Livestreams 版的 RSS（`/forum/113-livestreams.xml`）。主題頁會被 Cloudflare 擋，但 RSS 可正常存取。
2. **依標題**篩出要追蹤的文章，用主題 ID 去重：
   - 先排除每週例行的**週播表**（標題含 `Community Stream Schedule`）。
   - 標題含 `Devstream` → 視為 **Devstream 公告**。
   - 標題含 `Twitch Drops` / `Drops Campaign` → 視為 **Twitch Drop 活動公告**。
3. 每篇新公告都發一則 Discord 通知：
   - 🎮 **Devstream**：依內文標註 drop 狀態 —— 🎁 偵測到 Twitch Drop（附上那句話）／❌ 明示這次沒有／❓ 無法自動判斷（請點進確認）。
   - 📣 **Twitch Drop 活動**：直接通知並附原文連結，不解析內文。

### 為什麼用「標題」判斷，而不是看內文？

週播表的內文幾乎每篇都會提到 Twitch Drops（介紹本週哪些直播開了 drops、怎麼綁定帳號），所以**用內文判斷會把週播表全部誤判成掉寶活動**。相對地，標題非常乾淨：實測抓了 255 篇歷史文章，其中 165 篇週播表**沒有任何一篇**標題含 `Twitch Drops`。所以「標題決定要不要發、內文只負責標註」是最不會出錯的設計。

Twitch Drop 活動公告之所以不解析「獎勵與時間」：DE 歷年的公告模板換過好幾種、標題與內文都寫得很隨便，硬解極易出錯，因此只通知並導流到原文。

## 狀態與心跳（state 分支）

去重用的 `seen.json` 存在獨立的 `state` 分支，`main` 只放程式碼。每次跑先從 `state` 取回 `seen.json`，跑完連同心跳 `last_run.txt` commit 回去。

「偵測到新公告」的 commit 會保留下來，形成一份變更紀錄（時間戳可拿來看公告頻率）；純心跳的 commit 則用 force-push 滾動、不累積。所以 state 分支大致就是所有真變更 commit，加最多一個尾端心跳。

心跳是為了避開 GitHub「排程 60 天無活動自動停用」：新公告約月頻才更新 `seen.json`，活動太稀疏，所以每次跑都 commit 一次讓 repo 保持活動。commit message 會標明這次是真更新還是心跳。

`seen.json` 寫回時只保留還在 RSS feed 裡的 ID，滾出 feed 的舊文就丟掉，檔案不會無限長大。

## 部署

1. Fork 這個 repo。
2. 建 Discord webhook：頻道 → 編輯頻道 → 整合 → Webhook → 複製網址。
3. repo 設 secret `DISCORD_WEBHOOK_URL`：Settings → Secrets and variables → Actions。
4. 到 Actions 分頁啟用 workflow（fork 的 repo 排程預設停用，需手動 Enable）。

第一次跑會把目前 RSS 上要追蹤的文章（Devstream + Twitch Drop 活動，約 5 篇）全部推一次，順便確認運作正常；之後只推新公告。排程頻率在 `.github/workflows/check.yml` 的 `cron`。想重置已看過紀錄就刪掉 `state` 分支，下次跑會重建。

## 發送失敗

發送 Discord 最多重試 3 次，都失敗就放棄該篇、不再重試，並以非零碼結束讓該次 run 標記失敗、寄信通知你。單篇失敗不影響其他篇，已處理的進度照樣寫回。

## 本機測試

```bash
# 沒有 seen.json 時，會把目前所有要追蹤的公告視為新公告
python3 main.py

# 不設 DISCORD_WEBHOOK_URL 只印偵測狀態、不發送；要實際發送就 export：
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python3 main.py
```

| 環境變數 | 說明 |
|---|---|
| `DISCORD_WEBHOOK_URL` | 未設定則只印 log 不發送 |
| `SEEN_PATH` | `seen.json` 路徑，預設為程式同目錄 |

## 已知限制

Devstream 的 drop 標註完全依據 RSS 內文（實測帶的是一樓完整內文，非截斷摘要）。標註只用來「標示」、不決定是否發送，所以即使措辭沒見過被判成「無法判斷」，你照樣會收到通知、不會漏。Twitch Drop 活動公告則一律只通知 + 附連結，不嘗試解析獎勵與時間。
