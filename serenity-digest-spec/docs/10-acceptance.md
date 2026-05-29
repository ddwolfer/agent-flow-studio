# 10 · 驗收標準

## 上線驗收（首週）

### 第一次手動執行

```bash
cd ~/Desktop/serenity-digest
node scripts/scrape-snapshot.mjs > test-snapshot.json
node scripts/compose-brief.mjs < test-snapshot.json > test-brief.md
bash scripts/send-telegram.sh < test-brief.md
```

確認每一步：

- [ ] `test-snapshot.json` 是有效 JSON，schema 對齊
- [ ] `priorityQueue.length >= 3`
- [ ] `hotStocks.length >= 10`
- [ ] `feedItems.length >= 5`
- [ ] `test-brief.md` 包含所有預期段落
- [ ] Brief 長度在預算內
- [ ] 沒有 anti-pattern 字
- [ ] Telegram 收到正確訊息

### 排程驗證

```
[ ] Cowork 排程任務已建立，可在排程列表看到
[ ] 排程任務手動觸發一次，等同 cron 行為
[ ] 排程任務時區設為 Asia/Taipei（非 UTC）
[ ] 排程任務失敗時有錯誤通知
```

### KG 驗證

```
[ ] knowledge-graph MCP 已掛載
[ ] 跑 memory_stats 回傳節點數 > 0（含 bootstrap anchors）
[ ] store_knowledge 一個測試節點，再 search_memory 找得到
[ ] 連續跑 3 天，KG 節點數至少 +30
```

### Persona 驗證

```
[ ] Phase 1（前 30 天）：可以沒有 SKILL.md，brief 用原站內容改寫
[ ] Phase 2 起：SKILL.md 存在於 skills/serenity-distill/output/
[ ] Persona 文件大小在 5-15 KB（太小 = 蒸餾不足；太大 = 拼湊太多）
[ ] Persona 包含五層內容（DNA、心智模型、決策啟發、反模式、誠實邊界）
```

## 每日驗收

每天 brief 完成後自動檢查：

```javascript
function dailyAcceptance(brief, log) {
  const checks = {
    length:  brief.length >= 800 && brief.length <= 4000,
    hasFooter: brief.includes("analysissite.vercel.app"),
    hasTier1:  /1\.\s+\*\w+\*/.test(brief),
    hasDate:   /\d{4}-\d{2}-\d{2}/.test(brief),
    noBanned:  !BANNED.some(re => re.test(brief)),
    dnaMarkers: countDnaMarkers(brief) >= 3,  // 至少 3 個 KOL DNA 詞
    sent:      log.includes("telegram send: 200")
  };
  
  const fails = Object.entries(checks).filter(([_, ok]) => !ok);
  if (fails.length > 0) {
    notifyOwner(`brief check failed: ${fails.map(([k]) => k).join(", ")}`);
  }
  return fails.length === 0;
}
```

任何 check 失敗 → 不阻止推送，但寫進 `logs/` 與 `index.jsonl` 的 `qualityFails` 欄位。

## 每週驗收

週反思腳本跑完後檢查：

```
[ ] maintain_graph 有實際清理（merged > 0 OR pruned > 0）
[ ] insight 節點 +1
[ ] 週報推送成功
[ ] 過去 7 天 brief 成功率 ≥ 6/7
```

## 每月驗收

月校準時：

```
[ ] 推送月報
[ ] index.jsonl 列出過去 30 天 status 統計
[ ] KG access 熱榜 top 10 報出
[ ] 新聞評分權重 review（漏網率 < 20%）
[ ] DB 大小報出，未超過 soft cap
```

## 90 天驗收（最關鍵）

```
[ ] v1 SKILL.md 已生成且使用 60+ 天
[ ] KG 節點 ≥ 1500
[ ] Level 3+ 節點 ≥ 50
[ ] 已有 ≥ 5 條 contradicts 邊
[ ] trackRecord.accuracy 至少有結果（不是 NaN）
[ ] 啟動 90 天決策樹流程
```

## 異常情況處理 SLA

| 異常 | 偵測 | SLA | 處理 |
| --- | --- | --- | --- |
| 爬蟲失敗 1 天 | 自動 | 立即 retry，沿用昨日 | 當日 brief 標 [STATUS] |
| 爬蟲失敗 3 天 | 自動 | 主動通知 owner | 切「KOL 暫離模式」 |
| Telegram 推送失敗 | 自動 | retry 2 次 | 失敗存 UNDELIVERED，明日合併 |
| Telegram 連續失敗 2 天 | 自動 | 通知 owner | 檢查 bot token 是否被吊銷 |
| KG MCP 不可用 | 自動 | 跳過 retrieval & 寫入 | 寫入暫存 pending-writes |
| KG MCP 不可用 7 天 | 自動 | 通知 owner | review 是否 DB 損壞 |
| Persona 漂移 > 30% | 季度蒸餾時 | 暫不啟用 v(N+1) | owner 24 小時內 review |
| KG 節點 > soft cap | 月校準時 | 加碼 maintain_graph | 仍超過 → 調整 prune 閾值 |

## 安全驗收

```
[ ] config.json 不在 git 追蹤
[ ] knowledge.db 不在 git 追蹤
[ ] 推送目標 chat_id 為 private DM（非 channel 非 group）
[ ] Brief 不被自動轉發到任何公開位置
[ ] Brief 結尾固定有 KOL 歸因連結
[ ] Brief 內容沒有逐字複製 KOL 連續 > 30 字段落（用 LCS 檢查）
```

## 回滾

如果 v(N+1) SKILL.md 啟用後 brief 品質下降：

```bash
# 1. 把 current.md 改回 v(N)
ln -sf ~/Desktop/serenity-digest-spec/skills/serenity-distill/output/serenity-perspective-vN.md \
       ~/.config/serenity-digest/persona-cache/current.md

# 2. 不要丟掉 v(N+1)，可能下個季度修正後再用
mv serenity-perspective-vN+1.md serenity-perspective-vN+1.SUSPENDED.md

# 3. log 一條 incident
echo "$(date -Iseconds) [INFO] persona rolled back from vN+1 to vN" \
  >> ~/Desktop/serenity-digest/logs/incidents.log
```

如果 KG 損壞需要重建：

```bash
# 1. 備份壞掉的 DB
cp ~/.config/serenity-digest/knowledge.db ~/.config/serenity-digest/knowledge.db.broken

# 2. 從 evidence pool 重播
node scripts/replay-snapshots.mjs --from 2026-05-01 --to today

# 3. 驗證
node -e "const stats = require('./scripts/kg-stats.mjs'); stats();"
```

## 標準

> 「系統運作得當」的定義：
> 連續 30 天每天 06:00 前 owner 收到一份合格的日報，
> 且每週日有一份反思週報，
> 且 KG 節點數穩定成長，
> 且 owner 還願意打開來看。

最後一條是最重要的。
