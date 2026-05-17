# Eason 常用指標 + MCP 對應

> 基於 9 支影片的出現頻率排序

## Tier 1：每集必提（9/9 出現率）

| 指標 | Eason 用法 | MCP 工具 | 取得方式 |
|------|-----------|---------|---------|
| 季線（60MA） | 多空分界線。不破=看回不看空 | Yahoo Finance | `get_historical_stock_prices` → 計算 60MA |
| 月線（20MA） | 短期支撐壓力。月線上=偏多 | Yahoo Finance | `get_historical_stock_prices` → 計算 20MA |
| 外資淨空單 | 恐慌/信心指標。連降=轉多 | TWSE | `get_margin_trading_info` 或 `get_daily_market_trading_info` |

## Tier 2：高頻（6-7/9 出現率）

| 指標 | Eason 用法 | MCP 工具 |
|------|-----------|---------|
| 成交量 | 量縮=賣壓竭盡；量增=多頭回歸 | TWSE | `get_daily_market_trading_info` |
| 美光(MU)股價 | 記憶體龍頭指標。月線撐=台股記憶體可買 | Yahoo Finance | `get_stock_info` ticker=MU |
| 櫃買指數 | 中小型AI股溫度計。創高=主升段 | TWSE | `get_market_index_info` |

## Tier 3：中頻（2-4/9 出現率）

| 指標 | Eason 用法 | MCP 工具 |
|------|-----------|---------|
| 布蘭特原油 | 系統性風險指標。>120=警戒 | Yahoo Finance | `get_stock_info` ticker=BZ=F |
| 黃金價格 | 避險情緒。暴跌=資金解構 | Yahoo Finance | `get_stock_info` ticker=GC=F |
| 費半指數 | AI半導體景氣。台股跟費半走 | Yahoo Finance | `get_stock_info` ticker=^SOX |
| 融資餘額 | 散戶信心。斷頭=底部訊號 | TWSE | `get_margin_trading_info` |
| 歸離率 | 偏離月線%。>15%=過熱要降溫 | 計算 | (收盤-20MA)/20MA×100 |
| 外資現貨買賣超 | 權值股壓力。連賣=避開權值 | TWSE | `get_foreign_investment_by_industry` |
| 台積電本益比 | 估值安全邊際。20倍=合理 | Yahoo Finance | `get_stock_info` ticker=2330.TW |

## 關鍵價位判讀規則

| 指標組合 | Eason 結論 |
|---------|-----------|
| 季線不破 + 外資空單↓ + 櫃買創高 | 強多頭，積極進場 |
| 月線附近 + 量縮 + 美光撐住 | 看回不看空，找買點 |
| 歸離率>15% + 連漲多日 | 過熱，短線可做空避險 |
| 季線跌破 + 外資空單創高 | ❓ 尚無數據（可能轉空） |
