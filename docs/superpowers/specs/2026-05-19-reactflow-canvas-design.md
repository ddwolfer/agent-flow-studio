# ReactFlow 視覺化畫布 v1 — 設計規格

**Date:** 2026-05-19 · **Status:** approved (brainstorm) → pending user spec review
**Topic:** agent-flow-studio Route A 後半:可編輯的節點編排畫布(v1)

## 1. 目標與背景

Route A 的資料/編排層(v1 + Phase 2 + FU-1..6)已完成且穩定。本規格是 Route A 的後半:在既有 Next.js app 上加一個 **ReactFlow 可編輯畫布**,把現有 eason pipeline 視覺化,並讓使用者直接在畫布上：

- 新增/啟用/停用/編輯 YouTuber 頻道
- 編輯 pipeline 設定(model / max_turns / quality_sections)
- 編輯 prompt 檔(main / digest / references / picks)
- 觸發一次 run,並看最近 run 狀態(running/succeeded/failed、qualityOk)

**鎖定決策(brainstorm)：** 可編輯畫布;固定拓撲(反映真實 runner,不做圖驅動執行);粗粒度 6 節點;Approach 1(config 衍生靜態圖 + 各資源獨立 REST 編輯器);編輯存回現有 config 檔(無新資料模型)。

## 2. 範圍邊界(YAGNI — 明確排除)

- 不做拓撲編輯、不引入 graph schema、不做拖拉改變執行順序。
- 節點固定位置,只 pan/zoom,**不持久化版面**。
- v1 只有 `eason` pipeline 及其 prompts 可編(API 依 name 泛用,UI 對準選中頻道的 pipeline)。
- 無認證(本機自用,與現有 app 一致)。
- runner / 既有 lib 不改(本功能純粹是 UI + 薄讀寫 API,疊在已驗證的 runner 之上)。

## 3. 架構

- `studio/app/page.tsx` 改為畫布頁(舊的 placeholder 清單移除,不另開路由)。
- 新依賴:`@xyflow/react`（v12，React 19 / Next 15 相容;不可用 legacy `reactflow` v11）。
- Client component 渲染 6 個固定節點 + 邊;圖形狀為靜態定義(它本來就固定 —— 改 runner 階段是改程式碼,不該資料驅動)。
- 右側抽屜式側欄(SidePanel),內容依選中節點型別切換編輯器。
- 頂部 RunBar:Run 按鈕 + 最近 run 狀態。

### 6 節點(固定拓撲)

`頻道(Channels)` → `摘要(Digest)` → `分析(Analysis)` → `後處理(PostProcess)` → `品質(Quality)` → `持久化(Persistence)`

| 節點 | 代表 | 點擊側欄 |
|---|---|---|
| 頻道 | channels.yaml | 頻道 CRUD(新增/編輯/啟用切換) |
| 摘要 | digestPass + digest.md | `pipeline.digest.model` 編輯、digest.md 編輯 |
| 分析 | runClaude + main.md + references | 頂層 `model`、`max_turns`(共用欄位,只在此節點編輯以免兩處衝突)、main.md + 各 reference .md 編輯 |
| 後處理 | postProcess(pdf/notify/picks) | `post.pdf`/`post.notify` 旗標、`post.picks.model`、picks.md 編輯 |
| 品質 | mechanicalChecks | quality_sections 清單編輯 |
| 持久化 | sqlite(training/daily/picks) | 唯讀說明(v1 不可編,只展示三張表用途) |

## 4. 元件 / 檔案

**前端**
- `app/page.tsx` — 畫布頁(client):ReactFlow 圖 + RunBar + SidePanel 宿主、選中節點狀態。
- `app/canvas/nodes.ts` — 靜態 nodes/edges 定義(純資料,可單測:恰 6 節點、邊合法、節點 id 唯一)。
- `components/canvas/StageNode.tsx` — 自訂 ReactFlow 節點(標題、副標、狀態色)。
- `components/canvas/SidePanel.tsx` — 依選中節點 id 切換編輯器(純切換邏輯可單測)。
- `components/canvas/editors/ChannelsEditor.tsx` — 頻道 CRUD,讀寫 `/api/channels`。
- `components/canvas/editors/PipelineEditor.tsx` — pipeline 欄位,讀寫 `/api/pipeline/[name]`。
- `components/canvas/editors/PromptEditor.tsx` — 選 prompt 檔 + textarea,讀寫 `/api/prompts`。
- `components/canvas/RunBar.tsx` — Run 觸發 + 最近 run 狀態,讀 `/api/runs`、`/api/runs/[id]`。

**後端 API(Next route handlers)**
- `app/api/pipeline/[name]/route.ts` — GET 回 pipeline yaml 解析後物件;PUT 收物件 → `PipelineFile` zod 驗證 → 寫 `config/pipelines/<name>.yaml`。name 須命中既有檔白名單。
- `app/api/prompts/route.ts` — GET `?path=` 回檔內容;PUT `{path, content}` 寫入。`path` 必須通過白名單 helper。
- 沿用 `app/api/channels/route.ts`(已有 GET/PUT + zod)、`app/api/runs/*`(已有)。

**lib**
- `lib/config/promptPaths.ts` — 匯出「允許編輯的 prompt 相對路徑集合」(由 eason pipeline 的 template/references/digest/picks 推導)+ `resolveSafePromptPath(rel): string | null`:對 `STUDIO_ROOT` 解析,拒絕 `..`/絕對路徑/不在白名單者,回 null 表示拒絕。

## 5. 資料流

1. **載入**:`page.tsx` 抓 `/api/channels`、`/api/runs`。點節點 → 對應 editor 抓該資源(pipeline yaml / prompt md)。
2. **存檔**:editor PUT → API 驗證(yaml zod / 路徑白名單)→ 用 `STUDIO_ROOT` 相對路徑寫檔 → 下次 run 即生效(同一份 runner 讀的 config,無新模型)。存後重抓,不做樂觀更新。
3. **跑**:RunBar POST `/api/runs {channelId}` → 輪詢 `/api/runs` + `/api/runs/[id]` 顯示狀態 pill。

## 6. 錯誤處理

- API:YAML/JSON 壞或 zod 失敗 → 400 + 訊息,**不寫檔**(沿用 channels PUT 模式)。prompt 路徑不在白名單 → 400。檔案 IO 錯 → 500 JSON,route 不 crash。
- 路徑安全:`resolveSafePromptPath` 拒絕脫離 `prompts/eason/` 的任何路徑(無 `..`、非絕對、須命中白名單檔名);pipeline `name` 同樣白名單化。
- UI:非 200 → 側欄就地顯示錯誤訊息,不清空使用者輸入。run 失敗 → 狀態 pill 顯示 `failed · <stage>`。

## 7. 測試

- Vitest API 測試:
  - `pipeline/[name]` GET 回正確物件;PUT 有效 → 寫檔且可讀回;PUT 無效(zod 不過 / 壞 yaml)→ 400 且檔案未變;未知 name → 400。
  - `prompts` GET 有效檔;PUT 有效 → 寫入;`../` 與絕對路徑與未知檔 → 400 且未寫入。
- 純邏輯單測:`nodes.ts` 恰 6 節點、邊端點皆存在、id 唯一;`SidePanel` 依節點 id 選對 editor;`resolveSafePromptPath` 白名單/traversal 案例。
- 不重度單測 ReactFlow 渲染(jsdom 限制)。
- 驗收(UI 正確性,誠實標明不能純靠自動測試):`npm run dev` → 載入畫布 → 編一個 prompt 存檔 → 新增一個停用頻道存檔 → 觸發 eason run → 看狀態 pill 由 running→succeeded。納入實作計畫最後一個確認步驟。

## 8. 對既有程式的影響

- 取代 `app/page.tsx` 內容(舊清單為 placeholder)。
- 新增上述前端元件 + 2 支 API route + 1 支 lib helper + `@xyflow/react` 依賴。
- **不改** `lib/runner/*`、`lib/config/{schema,load}.ts`、prompts 內容、runner 行為。channels/runs API 沿用不改。
- 風險面:僅限新 UI 與兩支薄寫入 API;寫入皆經 zod/白名單;對已驗證的 pipeline 零行為變更。

## 9. 交付定義(v1 完成 = 全部成立)

1. 載入 `/` 顯示 6 節點 eason 圖,可 pan/zoom。
2. 頻道節點可新增/編輯/啟用切換並存回 channels.yaml(zod 驗證)。
3. 摘要/分析/後處理/品質節點可編輯對應 pipeline 欄位與 prompt 檔並存回(zod/白名單驗證,壞輸入被擋)。
4. RunBar 可觸發 eason run 並輪詢顯示最近 run 狀態 + qualityOk。
5. API + 純邏輯單測綠;手動驗收流程通過並記錄誠實證據。
