# Spec: price-zone v0.3 — delta from v0.2.1

> 版本:v0.3.1(已實作,含 FVG-cap 修訂)
> 基礎:v0.2.1(spec: `2026-07-08-price-zone-design.md`)
> 修訂歷史:
>  - v0.3(commit 0cfcb7c → 1fdc917):6 項變更
>  - v0.3.1(此次):FVG-basis buy_zone 不再 ATR-撐開;加入 actionable-width 下限
> 目標讀者:Claude Code(實作者)

---

## 0. 變更緣由

v0.2.1 對 IVV / TSLA / MU / MSFT / RDDT / GOOG / NVDA / NOW 8 檔真數據驗證後,發現 1 個 bug + 5 個實務可用性缺陷。這份 v0.3 delta 集中處理它們。

**v0.2.1 沒動的東西不重複**;本文件只列 delta。合起讀:v0.2.1 spec + 本文件 = v0.3 完整規格。

---

## 1. 六項變更列表

| # | 項目 | 觸發 ticker(v0.2.1 驗證) | 類型 |
|---|---|---|---|
| 1 | RDDT CHoCH trigger 選錯 swing high | RDDT(down trend,trigger $182.41 < 現價 $194) | **bug fix** |
| 2 | zone 為 null 時,warning 需文字化說明 | GOOG / IVV(sell_zone null 但無提示原因) | UX |
| 3 | `in_zone` flag:現價落在 buy/sell zone 內 | NOW(現價 $106.70 落在 sell zone $105.5–$110.84 內) | 新欄位 |
| 4 | `zones_overlapping_pivotal` warning | TSLA(buy.high $398.52 > sell.low $397.47) | 新 warning |
| 5 | `intraday_stress_level` 獨立欄位 | 通用(先前討論 SMC 語意分離) | 新欄位 |
| 6 | FVG 時間衰減(只保留最近 60 bars) | MU(35 筆 unfilled FVG,絕大多數來自去年) | 演算法收斂 |

---

## 2. 逐項規格

### 2.1 RDDT CHoCH trigger fix

**問題:** 當 `trend.direction == "down"` 時,`buy_zone_pending.watch_price_for_choch` 應該挑「**現價之上**、尚未被突破的最近 swing high」— 這才是「還沒觸發、還在等的 CHoCH watch」。

v0.2.1 挑「最近一個 confirmed swing high」而不管價位關係,結果 RDDT 選到 $182.41(位於現價 $194 之下,早已被突破),trigger 是死的。

**正確邏輯:**

```python
# v0.3 fix
recent_high = None
for s in reversed(swings):
    if s.confirmed and s.kind == "H" and s.price > current_price:
        recent_high = s
        break
if recent_high is None:
    # 所有 confirmed swing high 都在現價之下 → CHoCH 已功能性觸發
    # 但 determine_trend 仍歸類為 down(基於前 4 swing 序列)
    # → 這是趨勢判定與價格行為的分歧,需要 warning
    warnings.append("choch_functionally_fired_but_swing_structure_still_down")
    buy_zone_pending = {
        "reason": "downtrend by swing structure, but price already above all confirmed swing highs — CHoCH may have functionally fired",
        "watch_price_for_choch": None,
        "watch_rule": None,
    }
```

**對稱地**,若未來加入 uptrend 的 CHoCH 反轉監控,應挑「現價之下、尚未被突破的最近 swing low」。

### 2.2 zone null 的文字化說明

**問題:** GOOG / IVV 的 `sell_zone = null` 且僅有 `structure_already_broken_above` warning。§8 讀者不知道「為什麼沒賣區」。

**修訂:** 新增 `sell_zone_note` / `buy_zone_note` 欄位(當對應 zone 為 null 時填入)。

**schema 新增:**

```json
"sell_zone": null,
"sell_zone_note": "無 SMC 減碼目標:所有 premium swing high 皆已被突破,需等待新 swing high 形成",
"buy_zone": null,
"buy_zone_note": "無 SMC 買進目標:discount 區無未回補 FVG 且無 confirmed swing low"
```

**觸發條件與文字對應表:**

| Warning | zone.note 文字 |
|---|---|
| `structure_already_broken_above` | 「無 SMC 減碼目標:所有 premium swing high 皆已被突破,需等待新 swing high 形成」 |
| `no_valid_sell_basis_in_premium` | 「無 SMC 減碼目標:premium 區無 confirmed swing high 或 equal highs」 |
| `no_valid_buy_basis_in_discount` | 「無 SMC 買進目標:discount 區無未回補 bullish FVG 或 confirmed swing low」 |
| `buy_zone_above_price_anomaly` | 「異常:buy_zone.low 高於現價,基準邏輯需人工檢視」 |
| `choch_functionally_fired_but_swing_structure_still_down` | 「趨勢分歧:swing 結構仍為 down,但價格已高於所有 confirmed swing high;CHoCH 可能已功能性觸發」 |

`zone_note` 為 `null` 表示對應 zone 有效,不需說明。

### 2.3 `in_zone` flag

**問題:** NOW 現價 $106.70 落在 sell_zone $105.50–$110.84 內。這是**訊息量最大的訊號**(「你現在正在減碼區裡」),不該和「賣區在 $1254 遙遠上方」用同樣措辭。

**schema 新增:**

```json
"buy_zone": {
  ...,
  "price_in_zone": false      // 現價是否 ∈ [zone.low, zone.high]
},
"sell_zone": {
  ...,
  "price_in_zone": true       // NOW 賣區觸發
}
```

**§8 措辭對應**(SKILL.md 硬規則同步):

- `price_in_zone == true` 且是 sell_zone:「⚠️ **現價已在減碼區內** $A–$B,基本面若同時看空 → 減碼觸發訊號」
- `price_in_zone == true` 且是 buy_zone:「⚠️ **現價已在買區內** $A–$B,若逢分歧或動能弱化 → 進場觸發訊號」
- `price_in_zone == false`:照 v0.2.1 舊有措辭(「等待回檔到 xx–xx」等)

### 2.4 `zones_overlapping_pivotal` warning

**問題:** TSLA 的 buy_zone.high $398.52 > sell_zone.low $397.47。這是「demand 和 supply 短兵相接,市場即將選邊」的關鍵狀態。

**觸發條件:**

```python
if buy_zone and sell_zone and buy_zone["high"] > sell_zone["low"]:
    warnings.append("zones_overlapping_pivotal")
```

**§8 措辭:** 若此 warning 存在,§8 頂部加獨立警示塊:

> ⚠️ **買賣區重疊(pivotal state)**:buy $X–$Y 與 sell $A–$B 交集於 $[max(low), min(high)]。demand/supply 短兵相接,方向未明;下一根 K 的收盤方向為關鍵訊號。

### 2.5 `intraday_stress_level` 獨立欄位

**背景:** 先前(2026-07-08 對話)討論的「盤中掃損但沒收破」訊號 — 用獨立欄位表達,不模糊 `invalidation_price` 定義。

**schema 新增:**

```json
"buy_zone": {
  ...,
  "intraday_stress_level": 725.00,   // 盤中觸及此價 = 壓力測試,收盤未破 = 通過
  "intraday_stress_rule": "any low <= 725.00 within 5 trading days"
}
```

**計算公式:**

```python
buy_zone.intraday_stress_level = _r(buy_zone.invalidation_price - 0.3 * atr14)
sell_zone.intraday_stress_level = _r(sell_zone.invalidation_price + 0.3 * atr14)
```

0.3 × ATR 是任意選定,取 SMC 常用「小掃損 sweep」的統計中位數。這欄位是**觀察用**,不影響 zone 有效性判定。

**§8 呈現:** 選擇性顯示(若某日盤中低點/高點觸及該價位),Tier A 才呈現;Tier B 略。

### 2.6 FVG 時間衰減

**問題:** MU 產生 35 筆 unfilled FVG,絕大多數來自 2025 年老 gap,對日線波段參考已無實務意義。

**規則:** 只保留 `date >= today - 60 * calendar_days` 的 FVG。實作上 = 只掃描 `bars[-90:]`(留 buffer)進行 FVG 檢測,而不是整個 12mo 資料。

```python
def find_unfilled_fvg(bars: list[Bar], recent_bars_only: int = 90) -> list[dict]:
    scan_range = bars[-recent_bars_only:] if len(bars) > recent_bars_only else bars
    # ... 其餘不變,但只在 scan_range 內找 gap
```

**注意:** 這會影響 `pick_buy_basis` 的 FVG 選擇範圍。MU 的 v0.2.1 買區依據 2026-05-22 的 FVG,距今約 47 天,仍在 60 天窗口內,不會被剔除。但若時間再過 15 天,那個 FVG 會被剔,買區改由「最近 confirmed HL swing low」承擔,實務上更合理。

---

## 3. Schema 變更清單

`schema_version` bump 至 `"v0.3"`。

**新欄位:**

| 位置 | 欄位 | 型別 |
|---|---|---|
| root | `schema_version` | `"v0.3"` |
| root | `buy_zone_note` | `str \| null` |
| root | `sell_zone_note` | `str \| null` |
| `buy_zone` | `price_in_zone` | `bool` |
| `buy_zone` | `intraday_stress_level` | `float` |
| `buy_zone` | `intraday_stress_rule` | `str` |
| `sell_zone` | `price_in_zone` | `bool` |
| `sell_zone` | `intraday_stress_level` | `float` |
| `sell_zone` | `intraday_stress_rule` | `str` |

**新 warnings 列舉:**

- `zones_overlapping_pivotal`
- `choch_functionally_fired_but_swing_structure_still_down`

**沿用 v0.2.1 政策:** 欄位可增不可減。既有 consumers(SKILL.md、未來 golden-file)可安全略過未認得的新欄位。

---

## 4. SKILL.md 硬規則新增

在既有 §5 硬規則後追加:

**H1(v0.3)** — 若 `sell_zone` / `buy_zone` 為 null 且對應 `_note` 有內容,§8 **必須**顯示該 note 文字(不得靜默略過)。

**H2(v0.3)** — 若 `warnings` 含 `zones_overlapping_pivotal`,§8 **必須**在 zone 說明前加獨立警示塊,措辭見 §2.4。

**H3(v0.3)** — 若對應 zone 之 `price_in_zone == true`,§8 措辭必須用「現價已在 X 區內」的強調語,不得用「等待回檔」等偏被動語意。

**H4(v0.3)** — `intraday_stress_level` 僅 Tier A 呈現;Tier B 略以節省 token。呈現時需標明「盤中壓力測試位,非失效」以區隔於 `invalidation_price`。

---

## 5. 驗收標準(補充 v0.2.1 §6)

- ☐ **RDDT bug**:重跑後 `buy_zone_pending.watch_price_for_choch` 為 `null` 且 warnings 含 `choch_functionally_fired_but_swing_structure_still_down`(RDDT 現況);若情境變化(RDDT 出現高於現價的 confirmed swing high),則 trigger 為該 swing high 價位
- ☐ **null note**:GOOG / IVV 的 `sell_zone_note` 為對應解釋文字
- ☐ **in_zone**:NOW `sell_zone.price_in_zone == true`
- ☐ **overlap**:TSLA `warnings` 含 `zones_overlapping_pivotal`
- ☐ **stress_level**:任一有效 zone 都有 `intraday_stress_level` 且為 `invalidation ∓ 0.3 * ATR`
- ☐ **FVG time decay**:MU 的 `unfilled_fvg` 從 35 筆降至 ≤ 5 筆(全落在最近 90 bars 內)
- ☐ **backwards compat**:v0.2.1 的 sanity(zone.low ≤ invalidation ≤ zone.high)在 v0.3 8 檔仍全通過

---

## 6. 不做的事(v0.3 non-goal)

- ❌ 不改 fractal N、ATR period、range window 等常數
- ❌ 不加 volume profile(續 v0.2 排除)
- ❌ 不引入多時間框架(1H 級別仍延後)
- ❌ 不動 wire-in(SKILL.md 主結構),只加 §5 硬規則的 4 條 H1-H4

---

## 6.5 v0.3.1 patch:FVG-cap + min actionable width

**問題:** v0.3 對 TSLA 產生假的 `zones_overlapping_pivotal` warning。追根究底,v0.2.1 的公式 `bz_high = max(FVG.top, invalidation + 2×half_width)` 對 FVG basis **強制 ATR 撐開**,產生 FVG 頂之上「憑空的」zone 高度,恰好與 sell zone 的 ATR 尾端重疊。

**修訂:**

```python
if basis["kind"] == "fvg":
    # FVG has physical edges; use FVG.top as ceiling.
    # But guarantee actionable width when FVG is razor-thin.
    fvg_top = basis["extras"]["top"]
    min_thick = max(0.25 * atr14, 0.008 * price)
    bz_high = _r(max(fvg_top, invalidation + min_thick))
else:  # swing_low: 單點,天然需要 ATR 撐開
    bz_high = _r(invalidation + 2 * hw)
```

**兩個原則:**
1. FVG 有實體邊界 — 用 FVG.top,不加 2×hw 過度撐開
2. 但 FVG 若薄至不 actionable(如 TSLA 2026-06-29 天然厚度 $0.18),用 `max(0.25×ATR, 0.008×price)` 作為最小可下單寬度下限

**8 檔驗收(2026-07-08):**

| Ticker | v0.3 buy | v0.3.1 buy | Δ width | overlap |
|---|---|---|---|---|
| TSLA | $379.12–$398.52 | $379.12–$384.01 | -75% | **消失** |
| MU | $735.57–$782.89 | $735.57–$758.22 | -52% | 無 |
| GOOG | $319.24–$329.88 | $319.24–$328.46 | -13% | 無 |
| IVV | $687.98–$699.16 | $687.98–$695.62 | -32% | 無 |
| NVDA | $189.66–$196.42 | $189.66–$195.74 | -10% | 無 |
| NOW | $99.64–$104.96 | $99.64–$103.84 | -21% | 無 |
| MSFT(swing_low)| unchanged | unchanged | 0 | 無 |

所有 buy_zone 更貼近實體 basis,無假重疊。

## 7. 版本升級路徑

v0.2.1 → v0.3 的 consumer(主要是 SKILL.md 內建 LLM prompt)需注意:

1. 讀 JSON 時預期 `schema_version == "v0.3"`,並且**能容忍**未來新增欄位(不做嚴格 keys 檢查)
2. 現有渲染邏輯仍可用(v0.2.1 欄位全數保留);v0.3 新欄位為**增強型**
3. 若 downgrade 至 v0.2.1(如 golden-file 未同步升級),應該仍能運作 — 但 v0.3 新增的三個驗收要點會失敗
