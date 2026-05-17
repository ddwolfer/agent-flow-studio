# US Macroeconomic Indicators — Complete Reference

## FRED Series IDs and Definitions

### Growth & Output
| Indicator | FRED Series | Frequency | Unit | Description |
|-----------|-------------|-----------|------|-------------|
| Real GDP Growth (QoQ annualized) | A191RL1Q225SBEA | Quarterly | % | 美國實質 GDP 季增年率，衡量經濟整體產出變化 |
| Real GDP Level | GDPC1 | Quarterly | Billions $ | 實質 GDP 水準（2017 年不變價格） |
| GDP Now (Atlanta Fed) | GDPNOW | Daily | % | 亞特蘭大聯儲即時 GDP 預估 |
| Industrial Production | INDPRO | Monthly | Index | 工業生產指數（2017=100），衡量製造、礦業、公用事業產出 |
| Capacity Utilization | TCU | Monthly | % | 產能利用率，高於 80% 通常暗示通膨壓力 |

### Labor Market
| Indicator | FRED Series | Frequency | Unit | Description |
|-----------|-------------|-----------|------|-------------|
| Unemployment Rate | UNRATE | Monthly | % | 失業率（U-3），最廣泛使用的就業指標 |
| U-6 Unemployment | U6RATE | Monthly | % | 廣義失業率（含半失業、灰心求職者） |
| Nonfarm Payrolls | PAYEMS | Monthly | Thousands | 非農就業人數，就業市場最重要指標 |
| Nonfarm Payrolls Change | — | Monthly | Thousands | 非農就業月增（從 PAYEMS 計算） |
| Average Hourly Earnings YoY | CES0500000003 | Monthly | $/hr | 平均時薪，薪資通膨的關鍵指標 |
| Initial Jobless Claims | ICSA | Weekly | Thousands | 初次申請失業救濟金人數，就業市場即時指標 |
| Continuing Claims | CCSA | Weekly | Thousands | 持續申請失業救濟金人數 |
| Job Openings (JOLTS) | JTSJOL | Monthly | Thousands | 職位空缺數，衡量勞動力市場緊俏程度 |
| Quits Rate (JOLTS) | JTSQUR | Monthly | % | 自願離職率，勞工信心指標 |
| Labor Force Participation | CIVPART | Monthly | % | 勞動參與率 |

### Inflation
| Indicator | FRED Series | Frequency | Unit | Description |
|-----------|-------------|-----------|------|-------------|
| CPI All Items YoY | CPIAUCSL | Monthly | % | 消費者物價指數年增率（所有項目） |
| CPI Core YoY | CPILFESL | Monthly | % | 核心 CPI 年增率（排除食品和能源） |
| CPI MoM | — | Monthly | % | CPI 月增率（從 CPIAUCSL 計算） |
| PCE Price Index YoY | PCEPI | Monthly | % | 個人消費支出物價指數年增率（Fed 偏好指標） |
| Core PCE YoY | PCEPILFE | Monthly | % | 核心 PCE 年增率（Fed 最重視的通膨指標） |
| PPI Final Demand YoY | PPIFIS | Monthly | % | 生產者物價指數年增率，領先 CPI 的通膨指標 |
| 5Y Breakeven Inflation | T5YIE | Daily | % | 5 年期通膨預期（TIPS 隱含） |
| 10Y Breakeven Inflation | T10YIE | Daily | % | 10 年期通膨預期 |
| University of Michigan Inflation Expectations | MICH | Monthly | % | 密西根大學消費者通膨預期（1 年） |

### Interest Rates & Monetary Policy
| Indicator | FRED Series | Frequency | Unit | Description |
|-----------|-------------|-----------|------|-------------|
| Fed Funds Rate (Upper) | DFEDTARU | Daily | % | 聯邦基金利率上限 |
| Fed Funds Rate (Lower) | DFEDTARL | Daily | % | 聯邦基金利率下限 |
| Fed Funds Effective | DFF | Daily | % | 聯邦基金有效利率 |
| 2-Year Treasury | DGS2 | Daily | % | 2 年期美國公債殖利率（短期利率預期） |
| 5-Year Treasury | DGS5 | Daily | % | 5 年期美國公債殖利率 |
| 10-Year Treasury | DGS10 | Daily | % | 10 年期美國公債殖利率（全球資產定價基準） |
| 30-Year Treasury | DGS30 | Daily | % | 30 年期美國公債殖利率 |
| 10Y-2Y Spread | T10Y2Y | Daily | % | 殖利率曲線斜率（10Y-2Y），倒掛常預示衰退 |
| 10Y-3M Spread | T10Y3M | Daily | % | 殖利率曲線斜率（10Y-3M），另一衰退指標 |
| 3-Month T-Bill | DTB3 | Daily | % | 3 個月國庫券利率 |
| Fed Balance Sheet | WALCL | Weekly | Millions $ | 聯準會資產負債表規模（QT/QE 指標） |
| Reverse Repo | RRPONTSYD | Daily | Billions $ | 隔夜逆回購規模（流動性指標） |

### Consumer & Business Sentiment
| Indicator | FRED Series | Frequency | Unit | Description |
|-----------|-------------|-----------|------|-------------|
| Consumer Confidence (Conference Board) | CSCICP03USM665S | Monthly | Index | 消費者信心指數 |
| University of Michigan Consumer Sentiment | UMCSENT | Monthly | Index | 密西根大學消費者信心指數 |
| ISM Manufacturing PMI | MANEMP | Monthly | Index | ISM 製造業 PMI，>50 為擴張 |
| ISM Services PMI | — | Monthly | Index | ISM 服務業 PMI（非 FRED，需 Yahoo Finance） |
| Retail Sales MoM | RSAFS | Monthly | % | 零售銷售月增率 |
| Personal Spending MoM | PCE | Monthly | % | 個人消費支出月增率 |
| Personal Income MoM | PI | Monthly | % | 個人所得月增率 |
| Personal Saving Rate | PSAVERT | Monthly | % | 個人儲蓄率 |

### Housing
| Indicator | FRED Series | Frequency | Unit | Description |
|-----------|-------------|-----------|------|-------------|
| Housing Starts | HOUST | Monthly | Thousands | 新屋開工數 |
| Building Permits | PERMIT | Monthly | Thousands | 建築許可數（新屋開工領先指標） |
| Existing Home Sales | EXHOSLUSM495S | Monthly | Millions | 成屋銷售 |
| New Home Sales | HSN1F | Monthly | Thousands | 新屋銷售 |
| Case-Shiller Home Price Index | CSUSHPINSA | Monthly | Index | 凱斯-席勒房價指數（全國） |
| 30-Year Mortgage Rate | MORTGAGE30US | Weekly | % | 30 年期固定房貸利率 |

### Financial Conditions
| Indicator | FRED Series | Frequency | Unit | Description |
|-----------|-------------|-----------|------|-------------|
| Chicago Fed Financial Conditions | NFCI | Weekly | Index | 芝加哥聯儲金融環境指數（0=平均，正值=緊縮） |
| St. Louis Fed Financial Stress | STLFSI2 | Weekly | Index | 聖路易聯儲金融壓力指數 |
| TED Spread | — | Daily | % | LIBOR-T-Bill 利差（信用風險指標） |
| High Yield Spread | BAMLH0A0HYM2 | Daily | % | 高收益債利差（信用風險溫度計） |
| Investment Grade Spread | BAMLC0A0CM | Daily | % | 投資等級債利差 |

### Trade & External
| Indicator | FRED Series | Frequency | Unit | Description |
|-----------|-------------|-----------|------|-------------|
| Trade Balance | BOPGSTB | Monthly | Millions $ | 貿易餘額 |
| Dollar Index (DXY) | DTWEXBGS | Daily | Index | 美元指數（貿易加權） |

## Interpretation Guidelines

### Key Thresholds
- **Unemployment**: <4% = tight labor market, >6% = significant slack
- **CPI YoY**: Fed target ~2%, >3% = concern, >5% = serious inflation
- **Core PCE**: Fed's 2% target, most closely watched inflation metric
- **10Y-2Y Spread**: <0 = inverted (recession signal), >1% = normal steepening
- **ISM PMI**: >50 = expansion, <50 = contraction, 50 = neutral
- **VIX**: <15 = complacent, 15-25 = normal, 25-35 = elevated fear, >35 = panic
- **High Yield Spread**: <3% = risk-on, 3-5% = normal, >5% = stress, >8% = crisis

### Release Calendar (approximate)
- **Weekly**: Jobless Claims (Thu), Fed Balance Sheet (Thu)
- **Monthly Week 1**: ISM Mfg PMI (1st biz day), Nonfarm Payrolls (1st Fri)
- **Monthly Week 2**: CPI (10th-14th), PPI (same week)
- **Monthly Week 3**: Retail Sales, Housing Starts, Industrial Production
- **Monthly Week 4**: PCE Price Index, Personal Income/Spending, Consumer Confidence
- **Quarterly**: GDP (advance ~4 weeks after quarter end, revised twice)
- **FOMC**: 8 meetings/year (~every 6 weeks), statement + dot plot + press conference
