# Taiwan Macroeconomic Indicators — Complete Reference

## TWSE MCP Data Points

### Stock Market (from TWSE MCP)
| Indicator | Source | Frequency | Description |
|-----------|--------|-----------|-------------|
| 加權股價指數 (TAIEX) | TWSE | Real-time | 台灣加權股價指數，涵蓋所有上市股票 |
| 成交量 (Volume) | TWSE | Daily | 每日成交金額（億元）與成交股數 |
| 外資買賣超 | TWSE | Daily | 外國機構投資人每日淨買超/賣超金額 |
| 投信買賣超 | TWSE | Daily | 投資信託（基金公司）每日淨買超/賣超 |
| 自營商買賣超 | TWSE | Daily | 自營商每日淨買超/賣超 |
| 融資餘額 | TWSE | Daily | 融資（信用交易借款買股）餘額 |
| 融券餘額 | TWSE | Daily | 融券（借股賣出）餘額 |
| 外資持股比例 | TWSE | Daily | 外資在台股總市值中的持股比例 |
| 個股漲跌排行 | TWSE | Daily | 每日漲幅/跌幅前 N 名個股 |
| 成交量排行 | TWSE | Daily | 每日成交金額前 N 名個股 |

### Taiwan Sector Classification (TWSE)
| Sector Code | Sector Name | Representative Stocks | Weight |
|-------------|-------------|----------------------|--------|
| 半導體 | Semiconductor | 台積電(2330), 聯發科(2454), 日月光投控(3711) | ~40% |
| 電子零組件 | Electronic Parts | 鴻海(2317), 台達電(2308), 大立光(3008) | ~15% |
| 金融保險 | Financial | 富邦金(2881), 國泰金(2882), 中信金(2891) | ~12% |
| 航運 | Shipping | 長榮(2603), 陽明(2609), 萬海(2615) | ~3% |
| 鋼鐵 | Steel | 中鋼(2002), 東和鋼鐵(2006) | ~2% |
| 塑化 | Plastics/Chemical | 台塑(1301), 南亞(1303), 台化(1326) | ~3% |
| 紡織 | Textile | 遠東新(1402), 儒鴻(1476) | ~1% |
| 食品 | Food | 統一(1216), 大成(1210) | ~2% |
| 營建 | Construction | 興富發(2542), 華固(2548) | ~1% |
| 生技醫療 | Biotech | 藥華藥(6446), 合一(4743) | ~2% |
| 通信網路 | Communication | 中華電(2412), 台灣大(3045) | ~2% |
| 電機機械 | Electrical | 東元(1504), 上銀(2049) | ~2% |
| 觀光餐旅 | Tourism | 晶華(2707), 雄獅(2731) | ~0.5% |
| 汽車 | Auto | 裕隆(2201), 和泰車(2207) | ~1% |

### Yahoo Finance Tickers for Taiwan
| Indicator | Ticker | Description |
|-----------|--------|-------------|
| TAIEX | ^TWII | 台灣加權指數 |
| TWD/USD | TWD=X | 新台幣兌美元匯率 |
| TAIEX Futures | — | 台指期貨 |

## Central Bank of Taiwan (CBC) Key Rates
| Indicator | Current Source | Description |
|-----------|---------------|-------------|
| 重貼現率 | CBC website (web-research) | 央行基準利率，影響所有借貸利率 |
| 擔保放款融通利率 | CBC website | 銀行向央行借款的利率 |
| 短期融通利率 | CBC website | 短期資金融通利率 |
| M2 貨幣供給年增率 | CBC website | 廣義貨幣供給成長率 |
| 外匯存底 | CBC website | 台灣外匯準備金（通常全球前 5） |

## DGBAS (主計總處) Key Statistics
| Indicator | Frequency | Description |
|-----------|-----------|-------------|
| GDP 成長率 | Quarterly | 台灣 GDP 年增率（季度） |
| CPI 年增率 | Monthly | 消費者物價指數年增率 |
| 核心 CPI | Monthly | 排除蔬果及能源的核心 CPI |
| WPI 年增率 | Monthly | 躉售物價指數（生產面通膨） |
| 失業率 | Monthly | 台灣失業率 |
| 薪資成長率 | Monthly | 經常性薪資 + 非經常性薪資 年增率 |
| 工業生產指數 | Monthly | 製造業生產指數 |
| 外銷訂單 | Monthly | 外銷訂單金額及年增率（出口領先指標） |
| 出口金額 | Monthly | 海關出口統計（美元計） |
| 進口金額 | Monthly | 海關進口統計 |
| 貿易餘額 | Monthly | 出口 - 進口 |
| 景氣燈號 | Monthly | 景氣對策信號（紅黃綠藍燈） |
| 景氣領先指標 | Monthly | 景氣領先綜合指標 |
| 景氣同時指標 | Monthly | 景氣同時綜合指標 |

## Interpretation Guidelines

### Key Taiwan-Specific Thresholds
- **TAIEX Volume**: 正常 2000-3000 億/日, >4000 億=高量, <1500 億=量縮
- **外資買賣超**: 連續 5 日以上同方向=趨勢性，單日 >200 億=大量
- **融資增減**: 融資大增+指數上漲=散戶追高（警戒）, 融資大減+指數下跌=恐慌性殺出
- **CBC 利率**: 通常每季理監事會調整一次（3/6/9/12 月），每次調幅 0.125%（半碼）
- **景氣燈號**: 紅燈(38-45 分)=過熱, 黃紅(32-37)=溫熱, 綠燈(23-31)=穩定, 黃藍(17-22)=低迷, 藍燈(9-16)=衰退
- **外銷訂單**: 連續 N 月年增/年減 是判斷出口景氣的關鍵
- **台幣匯率**: 30-32 TWD/USD 為近年常態區間，央行傾向阻升不阻貶

### Taiwan Economic Calendar (approximate)
- **每月 7 日前**: 前月海關進出口統計
- **每月 5-10 日**: 前月 CPI/WPI
- **每月 20 日前**: 前月外銷訂單
- **每月月底**: 前月失業率、工業生產
- **每季末+1 月**: GDP 初估（概估→修正→最終）
- **3/6/9/12 月**: 央行理監事會議（利率決議）
- **每月 27 日前後**: 景氣燈號公布
