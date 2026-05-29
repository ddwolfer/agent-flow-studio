---
name: serenity-distill
description: 蒸餾 Serenity KOL 的認知框架，產出 serenity-perspective-v{N}.md。當需要建立或更新 Persona Layer 時使用——首次蒸餾（Day 30）、季度重蒸餾（Day 90 / 180 / 270 / 365）、或框架明顯漂移後的修正。
---

# Serenity Distillation

改造自 [nuwa-skill](https://github.com/alchaincyf/nuwa-skill)。
nuwa 原本設計用於蒸餾公眾人物，本 skill 針對 Serenity KOL 的單一語料源（看板）特化。

## When to invoke

- 首次蒸餾：Day 30（已累積 30 天 snapshot）
- 季度重蒸餾：每季首日 14:00 排程
- Owner 手動下達「重新蒸餾 serenity 框架」
- 季度 diff 超過 30% 且通過 owner 確認後

## Prerequisites

- `~/Desktop/serenity-digest/data/` 至少 30 個 snapshot.json
- knowledge-graph MCP 可用（Phase 2+ 蒸餾要用 KG 內容）
- 上一版 SKILL.md 存在（首次蒸餾除外）

## Procedure

### Step 1：採集語料

```
N = 90 (首次蒸餾) or 90 (季度蒸餾的最近 90 天)

corpus = []
for date in last_N_days:
    snapshot = read data/YYYY-MM-DD.json
    corpus.extend([
        ...snapshot.priorityQueue,
        ...snapshot.hotStocks,
        ...snapshot.feedItems
    ])

# 過濾：留下 KOL 的原始輸出，去重
unique_items = dedupe(corpus, by="ticker+summary")
```

從 Phase 2+ 起，額外加入 KG retrieval：

```
kg_principles = list_knowledge({
  filters: { source: "serenity-site", trust: "principle" },
  limit: 500
})
corpus.extend(kg_principles)
```

### Step 2：套用 nuwa adapter prompt

讀 `prompts/distillation-bootstrap.md` 當 system prompt，把 corpus 當 user input。

prompt 要求抽取五層：

1. 表達 DNA
2. 心智模型（3-7 個）
3. 決策啟發（5-10 條）
4. 反模式
5. 誠實邊界

### Step 3：三重驗證

對每個候選心智模型 / 決策啟發，跑：

```
驗證 1：跨域出現
  在 corpus 中找這個 pattern 的實例
  if 跨 5+ 檔股票出現 → pass
  else → 降為 observation，不寫入 SKILL

驗證 2：預測力
  取 corpus 中 KOL 未明確表態的標的 X
  問：用這個 mental model 推論，會推出什麼立場？
  如果推論與 KOL 後來實際立場（如有）一致 → pass

驗證 3：排他性
  問：這是金融教科書通用知識嗎？
  如「估值收窄」是 → 不收錄
  如「叙事 vs 證據分離」否 → 收錄
```

三個都過才寫入 SKILL.md。

### Step 4：品質測試

挑 3 檔 KOL 已表態的，用蒸餾出的框架推論 → 至少 2/3 與 KOL 一致。

挑 1 檔 KOL 未表態的 → 框架應給出「需要更多資訊」「待驗證」的保留答案，不應斬釘截鐵。

不通過 → 縮窄框架重跑。

### Step 5：寫入

產出 `output/serenity-perspective-v{N}.md`，按 `docs/03-persona-distillation.md` 的格式。

Frontmatter 必須含：

```yaml
---
version: vN
distilled_at: YYYY-MM-DD
corpus_range: YYYY-MM-DD ~ YYYY-MM-DD
corpus_size:
  snapshots: 90
  unique_stocks: 47
  feed_items: 280
confidence: 中 / 高 / 低
prev_version: v(N-1)
---
```

### Step 6：產出 diff（非首次蒸餾才做）

對比上一版：

```
diff = compare(v(N-1), v(N))

產出 output/diff-v(N-1)-v(N).md：
  - 新增的心智模型
  - 強化 / 修正的決策啟發
  - 廢棄的條目
  - 信心變化
  - 整體變動百分比
```

### Step 7：通知 owner

```
如果 diff < 20% → 自動採用，推送 1 段 Telegram 訊息簡述
如果 20% ≤ diff < 30% → 推送詳細 diff，預設採用
如果 diff ≥ 30% → 推送詳細 diff，**不採用**，等 owner 24 小時內回覆「採用」或「保留 v(N-1)」
```

### Step 8：更新軟連結（被採用時）

```bash
ln -sf ~/Desktop/serenity-digest-spec/skills/serenity-distill/output/serenity-perspective-v{N}.md \
       ~/.config/serenity-digest/persona-cache/current.md
```

下次 `serenity-digest` 啟動就會載入新版。

## Output

- `output/serenity-perspective-v{N}.md`
- `output/diff-v(N-1)-v(N).md`（非首次蒸餾）
- Telegram 通知 owner
- 軟連結 `persona-cache/current.md` 更新（如被採用）

## Quality criteria

- SKILL.md 大小 5-15 KB
- 包含五層完整內容
- 每層至少有 1 條（誠實邊界至少 3 條）
- 三重驗證 pass rate ≥ 80%
- 品質測試 3/4 通過

## Failure modes

- 語料不足（< 30 個 snapshot）→ 拒絕執行
- 三重驗證 < 60% pass → 標 confidence=低，仍寫入但 owner 必須 review
- 品質測試 < 50% 通過 → 不寫入，alert owner
- nuwa adapter 回應格式錯誤 → 重試一次，仍錯則手動 review

## Related skills

- `serenity-digest`：使用 SKILL.md 的 daily consumer
- `serenity-reflect`：補充週反思層級的觀察
