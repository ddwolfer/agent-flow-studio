#!/usr/bin/env node
/**
 * compose-brief.mjs
 *
 * 將 snapshot.json + 昨日 diff + (可選) KG retrieval + (可選) Persona
 * 組合為 Telegram Markdown brief。
 *
 * 用法：
 *   node compose-brief.mjs                            # 讀 data/{today}.json + data/{yesterday}.json
 *   node compose-brief.mjs --in path/to/snap.json     # 指定 snapshot
 *   cat snap.json | node compose-brief.mjs --stdin
 *
 * 輸出：
 *   brief markdown → stdout
 *   日誌 → stderr
 */

import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const DATA_DIR  = path.join(os.homedir(), "Desktop/serenity-digest/data");
const PERSONA   = path.join(os.homedir(), ".config/serenity-digest/persona-cache/current.md");
const CONFIG    = path.join(os.homedir(), ".config/serenity-digest/config.json");

const BANNED = [
  /強烈推薦|强烈推荐/,
  /目標價|目标价/,
  /翻倍|百分百|百分之百/,
  /必漲|必跌|必涨|必跌/,
  /\b100%\b|\babsolute(ly)?\b/i
];

async function readJSON(p) {
  return JSON.parse(await fs.readFile(p, "utf-8"));
}

async function tryRead(p) {
  try { return await fs.readFile(p, "utf-8"); } catch { return null; }
}

function todayISO() { return new Date().toISOString().slice(0, 10); }
function ymd(d) { return new Date(d).toISOString().slice(0, 10); }
function yesterdayISO() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

function diff(today, yesterday) {
  if (!yesterday) return { newInTop10: [], droppedFromTop10: [], priorityMovers: [] };
  const todaySet = new Set(today.hotStocks.map(s => s.ticker));
  const ySet     = new Set(yesterday.hotStocks.map(s => s.ticker));
  const newInTop10      = [...todaySet].filter(t => !ySet.has(t));
  const droppedFromTop10 = [...ySet].filter(t => !todaySet.has(t));
  const movers = [...todaySet]
    .filter(t => ySet.has(t))
    .map(t => {
      const today_p = today.hotStocks.find(s => s.ticker === t).priority || 0;
      const yest_p  = yesterday.hotStocks.find(s => s.ticker === t).priority || 0;
      return { ticker: t, delta: today_p - yest_p };
    })
    .filter(m => Math.abs(m.delta) > 0)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
    .slice(0, 3);
  return { newInTop10, droppedFromTop10, priorityMovers: movers };
}

function decideTier1Count(priorityQueue) {
  if (priorityQueue.length === 0) return 0;
  const top = priorityQueue[0].priority || 0;
  const cutoff = top * 0.95;
  const count = priorityQueue.slice(0, 10).filter(s => (s.priority || 0) >= cutoff).length;
  return Math.min(Math.max(count, 3), 5);
}

function tier1Block(stock, kgMemoryForTicker) {
  const stanceText =
    stock.stance === "bull_high_risk" ? "看多·高風險偏多" :
    stock.stance === "watch_high_risk" ? "中性·高風險觀察" :
    stock.stance === "bull" ? "看多" :
    stock.stance === "bear" ? "看空" :
    stock.stance === "caution" ? "看空·謹慎" :
    stock.stance === "neutral" ? "中性" : "—";
  const summary = stock.summary || "（無摘要）";
  const validation = extractValidationPoints(summary).slice(0, 3).join("、");
  return [
    `*${stock.ticker}* · 優先級 ${stock.priority ?? "—"} · ${stanceText}`,
    `   ${summary}`,
    validation ? `   需驗證：${validation}` : null,
    kgMemoryForTicker ? `   _${kgMemoryForTicker}_` : null
  ].filter(Boolean).join("\n");
}

function extractValidationPoints(summary) {
  // 從 summary 找出常見的「需要核驗 X、Y、Z」句型
  const m = summary.match(/(?:核验|核驗|验证|驗證)[:：]?\s*([\w\s、,，]+)/);
  if (m) return m[1].split(/[、,，]/).map(s => s.trim()).filter(Boolean);
  return [];
}

function tier2Block(stock) {
  const stance =
    stock.stance === "bull_high_risk" ? "看多·高風險偏多" :
    stock.stance === "watch_high_risk" ? "中性·高風險觀察" :
    (stock.tags ?? []).slice(0, 2).join("·") || "—";
  return `*${stock.ticker}* ${stock.priority ?? "—"} ${stance}`;
}

function checkBanned(text) {
  return BANNED.find(re => re.test(text));
}

function countDnaMarkers(text) {
  const markers = ["核驗", "核验", "驗證", "验证", "拆解", "映射", "叙事", "外溢", "邊際", "边际"];
  return markers.filter(m => text.includes(m)).length;
}

async function main() {
  const args = process.argv.slice(2);
  const stdin = args.includes("--stdin");
  const inFlag = args.indexOf("--in");
  const inPath = inFlag !== -1 ? args[inFlag + 1] : null;

  // Load snapshot
  let snap;
  if (stdin) {
    const text = await new Promise(r => {
      let data = "";
      process.stdin.on("data", c => data += c);
      process.stdin.on("end", () => r(data));
    });
    snap = JSON.parse(text);
  } else if (inPath) {
    snap = await readJSON(inPath);
  } else {
    snap = await readJSON(path.join(DATA_DIR, `${todayISO()}.json`));
  }

  const yesterday = await readJSON(path.join(DATA_DIR, `${yesterdayISO()}.json`)).catch(() => null);
  const dInfo = diff(snap, yesterday);

  // Load config
  const config = JSON.parse(await tryRead(CONFIG) ?? "{}");
  const depth = config.depth_preference ?? "medium";

  // Persona (optional, Phase 2+)
  const persona = await tryRead(PERSONA);

  // ---- Compose ----
  const lines = [];
  const dateStr = snap.fetchedAt.slice(0, 10);
  const timeStr = snap.fetchedAt.slice(11, 16);
  lines.push(`📊 *${dateStr} Serenity 日報* (${timeStr} 台北)`);
  lines.push("");

  // Status banner if degraded
  if (snap.stale) {
    lines.push(`⚠️ [STATUS] 今日爬取異常，沿用 ${snap.source.siteSnapshotAt?.slice(0,10) || "前次"} 快照`);
    lines.push("");
  }

  // Tier 1
  const t1count = decideTier1Count(snap.priorityQueue.length ? snap.priorityQueue : snap.hotStocks);
  const t1 = (snap.priorityQueue.length ? snap.priorityQueue : snap.hotStocks).slice(0, t1count);
  if (t1.length) {
    lines.push("▎*今日優先*");
    t1.forEach((s, i) => {
      lines.push(`${i + 1}. ${tier1Block(s, null /* TODO: KG retrieval */)}`);
    });
    lines.push("");
  }

  // Tier 2
  const t2budget = depth === "short" ? 5 : depth === "long" ? 10 : 8;
  const t2 = snap.hotStocks.slice(t1count, t1count + t2budget);
  if (t2.length) {
    lines.push("▎*掃描清單*");
    t2.forEach((s, i) => {
      lines.push(`${t1count + i + 1}. ${tier2Block(s)}`);
    });
    lines.push("");
  }

  // Tier 3 changes
  const t3parts = [];
  if (dInfo.newInTop10.length)      t3parts.push(`🆕 進榜：${dInfo.newInTop10.join(", ")}`);
  if (dInfo.droppedFromTop10.length) t3parts.push(`👋 退榜：${dInfo.droppedFromTop10.join(", ")}`);
  if (dInfo.priorityMovers.length > 0) {
    const ups = dInfo.priorityMovers.filter(m => m.delta > 0);
    const dns = dInfo.priorityMovers.filter(m => m.delta < 0);
    if (ups.length) t3parts.push(`📈 漲幅最大：${ups.map(m => `${m.ticker} +${m.delta}`).join(", ")}`);
    if (dns.length) t3parts.push(`📉 跌幅最大：${dns.map(m => `${m.ticker} ${m.delta}`).join(", ")}`);
  }
  if (t3parts.length) {
    lines.push("▎*昨日變化*");
    t3parts.forEach(p => lines.push(p));
    lines.push("");
  } else if (!yesterday) {
    lines.push("▎*昨日變化*");
    lines.push("（首次運行，無昨日對照）");
    lines.push("");
  }

  // KG 對照 (Phase 2+) — placeholder
  // TODO: integrate with KG MCP retrieval results

  // 相關訊號 — placeholder
  if (snap.feedItems.length) {
    lines.push("▎*相關訊號*");
    // MVP: 直接顯示前 3 條
    snap.feedItems.slice(0, 3).forEach(it => {
      lines.push(`• *${it.ticker}* · ${it.title}`);
    });
    lines.push("");
  }

  // Footer
  const personaVer = persona ? (persona.match(/version:\s*(v\d+)/)?.[1] ?? "v?") : "Phase 1（無 Persona）";
  lines.push("─────────");
  lines.push("📍 分析框架蒸餾自 [analysissite.vercel.app](https://analysissite.vercel.app/)");
  lines.push(`🧠 Persona ${personaVer}`);
  lines.push("🔗 完整看板：https://analysissite.vercel.app/");

  const brief = lines.join("\n");

  // Anti-pattern check
  const banned = checkBanned(brief);
  if (banned) {
    process.stderr.write(`[WARN] anti-pattern detected: ${banned}\n`);
  }
  process.stderr.write(`[INFO] brief composed: ${brief.length} chars, ${countDnaMarkers(brief)} DNA markers\n`);

  process.stdout.write(brief);
}

main().catch(err => {
  process.stderr.write(`[FATAL] ${err.message}\n`);
  process.exit(1);
});
