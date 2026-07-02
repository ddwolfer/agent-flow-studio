# carry-smoke notes(2026-07-02 實跑)

> Smoke script: `arb-sentinel/scripts/carry-smoke.py`
> Spec: `2026-07-02-carry-guardian.md`

## TL;DR — 3 個關鍵單位 / shape 差異必記

1. **`pledgeRate` 是 percent 字串**(`"61.71"`),不是 decimal。要 `/100` 才能跟 config 的 `ltv_watch=0.72` 比。
2. **`hourInterestRate` 是 percent-per-hour 字串**(`"0.000313"` = 0.000313% per hour)。同樣要 `/100` 才能跟 config 的 `borrow_hour_rate_warn=0.0000057`(小數格式)比。
3. **`savings/records` 用任何 `type` filter 都回訂閱記錄**(orderType="subscribe"),**沒有每日派息**。要改「balance delta」法(記昨日 productAmount,今日算差)。

## 詳細單位表(2026-07-02 快照 vs Spec §1)

| 欄位 | Spec §1 值 | 實測值 | 單位 | 正規化 |
|---|---|---|---|---|
| `pledgeRate` | 63.45% | **61.71** | percent 字串 | `/100 → 0.6171 decimal` |
| `supRate` | 85 | **85** | percent 字串 | `/100 → 0.85` |
| `forceRate` | 91 | **91** | percent 字串 | `/100 → 0.91` |
| `hourInterestRate` | 0.000342% | **0.000313** | percent-per-hour 字串 | `/100 * 24 * 365 → 0.02741 (2.74%)` |
| `loanAmount` | 21580.39 | **21580.3944434** | decimal 字串 | as-is |
| `interestAmount` | — | **0.64870669** | decimal 字串 | 已計利未還 |
| `pledgeAmount` | 0.56571125 | **0.56571125** | decimal 字串 | as-is |

**LTV 相對 spec 略降**(63.45% → 61.71%),BTC 略漲。

## 帳戶版本

**v2 classic**(`/api/v2/earn/loan/ongoing-orders`)。orderId `1454384882276573190` 直接在 v2 回傳裡。**不必走 v3 UTA**。

## 4 個 endpoint 逐一確認

### 1. `GET /api/v2/earn/loan/ongoing-orders`(簽名)

Response shape:
```json
{"code": "00000", "msg": "success", "data": [{ ...order fields... }]}
```

`data` **是 list 直接掛在頂層**,不是 `data.resultList`。

欄位齊全:orderId / loanCoin / loanAmount / interestAmount / hourInterestRate / pledgeCoin / pledgeAmount / pledgeRate / supRate / forceRate / borrowTime / expireTime。

### 2. `GET /api/v2/earn/loan/public/hour-interest?coin=USDC`(公開)

Response shape 略(smoke 有 dump,可查 log)。**這個是全市場 baseline 時利率**,跟 order 上綁的 `hourInterestRate` 可能一致也可能不。監控時建議用 order 上綁的那個,§5.3 純市場觀察可用 public 這個。

### 3. `GET /api/v2/earn/savings/assets`(簽名)

用於抓 USDGO 餘額。**productAmount 是 balance** 欄位(以實測為準,可能還有 marketPrice/coinName 等)。

### 3b. `GET /api/v2/earn/savings/records`(簽名)

**⚠️ 用任何 `type=interest|profit|settleInterest|sub_income` 都回訂閱記錄**(orderType="subscribe"),沒有每日派息事件。

**§5.2 派息稽核改用 balance delta**:
- 每次 carry task 執行時,把 `usdgo_balance` 寫入 state.json
- Daily digest 時算 `yesterday_balance` → `today_balance` 差,扣除已知手動 subscribe/redeem
- 這是 spec §5.2 的替代實作。合理性:USDGO 只在這一個部位裡,除非手動動它,delta 就是派息。

若之後想補簽名端點取真實派息事件,可以再試 `/api/v2/earn/savings/bill-list` 或 `/api/v2/earn/records/get`(smoke 沒試)。

### 4. `GET /api/v2/spot/market/orderbook?symbol=USDGOUSDC&limit=15`(公開)

Response `data.bids` / `data.asks` 是 list of `[price_str, qty_str]`。

**2026-07-02 實測**:
- Top bid: 1.0002 USDC(USDGO **溢價** 交易,離 depeg 觸發 0.9990 極遠)
- 15 檔累計 bid 量: **1,546,850 USDGO**
- 部位: 24,604 USDGO
- 深度倍數: **62.9x**(門檻 2.0x)→ 深度充足,即使全平也無滑點問題

USDGO 這幾天流動性極好,§5.4 深度告警應該很少觸發。

## 對 §5 規則影響清單

| 規則 | 需要調整? |
|---|---|
| §5.1 LTV 分級 | ✅ 除 `/100` 正規化 |
| §5.2 派息稽核 | ⚠️ **改用 balance-delta** 法,不用 records endpoint |
| §5.3 借款利率 | ✅ 除 `/100` 正規化 hourInterestRate |
| §5.4 USDGO 深度 | ✅ 直接 bids[0][0] 比 config,深度 sum 沒問題 |
| §5.5 Daily digest | ✅ 全部欄位 available |

## 未來 collector 直接複製的 shape

```python
# loan_ongoing_orders response:
{
  "data": [{
    "orderId": "1454384882276573190",
    "loanCoin": "USDC",
    "loanAmount": "21580.3944434",       # decimal string
    "interestAmount": "0.64870669",       # accrued unpaid interest
    "hourInterestRate": "0.000313",       # percent-per-hour, /100 for decimal
    "pledgeCoin": "BTC",
    "pledgeAmount": "0.56571125",
    "pledgeRate": "61.71",                # percent, /100 for LTV decimal
    "supRate": "85",                      # 補保線 percent
    "forceRate": "91",                    # 強平線 percent
    "borrowTime": "1782478297775",        # ms epoch
    "expireTime": "0"                     # 0 = 活期無到期
  }]
}
```
