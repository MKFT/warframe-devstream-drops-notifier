[English](README.md) | 繁體中文

# Warframe Devstream Notifier

定時檢查 Warframe [Livestreams 版](https://forums.warframe.com/forum/113-livestreams/)，有新的 Devstream 公告就發一則 Discord 通知，並標註是否有 Twitch Drop。

只用 Python 標準庫，無需安裝套件，跑在 GitHub Actions 上。

## 運作方式

每次排程觸發 `main.py`：

1. 抓 Livestreams 版的 RSS（`/forum/113-livestreams.xml`）。主題頁會被 Cloudflare 擋，但 RSS 可正常存取。
2. 篩出標題含 `Devstream` 的主題，用主題 ID 去重。
3. 每篇新公告都發一則 Discord 通知，依內文標註 drop 狀態：
   - `🎁 偵測到 Twitch Drop`：附上那句話。
   - `❌ 公告說明這次沒有 Twitch Drop`：偵測到否定句。
   - `❓ 無法自動判斷`：沒抓到 drop 字樣，請點進去自行確認。

公告措辭多變，所以偵測只負責「標註」、不決定要不要發，這樣再怪的寫法都不會漏。偵測涵蓋 `Twitch Drop`、`there will be drops`，以及領獎勵句型（`to earn` / `earn yourself` / `earn a|an|數字`）。

## 狀態與心跳（state 分支）

去重用的 `seen.json` 存在獨立的 `state` 分支，`main` 只放程式碼。每次跑先從 `state` 取回 `seen.json`，跑完連同心跳 `last_run.txt` commit 回去。

「偵測到新公告」的 commit 會保留下來，形成一份變更紀錄（時間戳可拿來看 Devstream 頻率）；純心跳的 commit 則用 force-push 滾動、不累積。所以 state 分支大致就是所有真變更 commit，加最多一個尾端心跳。

心跳是為了避開 GitHub「排程 60 天無活動自動停用」：新公告約月頻才更新 `seen.json`，活動太稀疏，所以每次跑都 commit 一次讓 repo 保持活動。commit message 會標明這次是真更新還是心跳。

`seen.json` 寫回時只保留還在 RSS feed 裡的 ID，滾出 feed 的舊文就丟掉，檔案不會無限長大。

## 部署

1. Fork 這個 repo。
2. 建 Discord webhook：頻道 → 編輯頻道 → 整合 → Webhook → 複製網址。
3. repo 設 secret `DISCORD_WEBHOOK_URL`：Settings → Secrets and variables → Actions。
4. 到 Actions 分頁啟用 workflow（fork 的 repo 排程預設停用，需手動 Enable）。

第一次跑會把目前 RSS 上的 Devstream（約 5 篇）全部推一次，順便確認運作正常；之後只推新公告。排程頻率在 `.github/workflows/check.yml` 的 `cron`。想重置已看過紀錄就刪掉 `state` 分支，下次跑會重建。

## 發送失敗

發送 Discord 最多重試 3 次，都失敗就放棄該篇、不再重試，並以非零碼結束讓該次 run 標記失敗、寄信通知你。單篇失敗不影響其他篇，已處理的進度照樣寫回。

## 本機測試

```bash
# 沒有 seen.json 時，會把目前所有 Devstream 視為新公告
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

判斷完全依據 RSS 內文（實測帶的是一樓完整內文，非截斷摘要）。偵測只用來標註、不決定是否發送，所以即使措辭沒見過被判成「無法判斷」，你照樣會收到通知、不會漏。
