讀取今天的 Eason 報告 ${HTML_FILE} 和 log ${LOG_FILE}，萃取 Eason 今天**明確帶方向提及**的個股，寫入 SQLite 資料庫 eason_picks 表。

嚴格規則（寧可漏也不要亂寫）：
1. **只萃取以下三類**：
   - 新推薦（今天首次明確建議進場）→ signal_type='新推', status='active'
   - 抗跌觀察 / 候選名單（可買訊號、觀察）→ signal_type='抗跌觀察', status='active'
   - 明確喊出場或停損 → UPDATE 該 ticker 最近一筆 status='active' 紀錄 → status='closed', close_reason='Eason 出場' 或 '停損'
2. **不要寫入**：
   - 只是泛論產業沒點名個股
   - 順帶提到但沒帶方向
   - 維持持倉沒新動作（重複紀錄沒意義）
   - 列名稱但沒任何評論傾向
3. **去重**：先用 mcp__sqlite__query 查 SELECT id FROM eason_picks WHERE ticker=? AND pick_date=?，已有就跳過
4. **欄位對應**：
   - pick_date = ${DATE}
   - ticker, name = 從報告中取
   - entry_price = 當日收盤（若報告有寫）
   - category = 散熱/CPO/記憶體/ASIC/被動元件/設備/AI伺服器/金融/其他
   - confidence = 強（重押/主戰場語氣）/ 中（推薦但不強調）/ 弱（順帶提一下）
   - reason_industry / reason_technical / reason_chips = 分別填（沒有就 NULL）
   - reason_summary = 一句話總結（≤50字）
   - source = 'Eason daily ${DATE}'
5. 完成後輸出單行：『[picks] 新增 N 筆 / 更新 M 筆出場 / 跳過 K 筆重複』

若判斷不出來或資料不足，寧可不寫入，不要腦補。
