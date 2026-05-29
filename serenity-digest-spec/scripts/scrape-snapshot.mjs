#!/usr/bin/env node
/**
 * scrape-snapshot.mjs
 *
 * 抓取 analysissite.vercel.app 首頁，解析成結構化 snapshot JSON。
 * 適用：每天 06:00 排程任務的第一個階段。
 *
 * 用法：
 *   node scripts/scrape-snapshot.mjs           # 寫到 ~/Desktop/serenity-digest/data/YYYY-MM-DD.json
 *   node scripts/scrape-snapshot.mjs --stdout  # 寫到 stdout
 *   node scripts/scrape-snapshot.mjs --dry     # 只解析不寫檔
 */

import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import crypto from "node:crypto";

const URL = "https://analysissite.vercel.app/";
const UA  = "SerenityDigest/1.0 (personal-digest; +mailto:910063@gmail.com)";
const RETRY = 1;
const RETRY_DELAY_MS = 60_000;
const DATA_DIR = path.join(os.homedir(), "Desktop/serenity-digest/data");
const RAW_DIR  = path.join(os.homedir(), "Desktop/serenity-digest/raw");

async function fetchHTML(url, attempt = 0) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 30_000);
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": UA, "Accept": "text/html" },
      signal: ctrl.signal
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.text();
  } catch (err) {
    if (attempt < RETRY) {
      await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
      return fetchHTML(url, attempt + 1);
    }
    throw err;
  } finally {
    clearTimeout(t);
  }
}

/**
 * 解析策略：
 * - 用文字錨點（中文 heading）而非 CSS selector，提高抗改版能力
 * - 多級 fallback
 * - 失敗時欄位填 null，不丟整份
 */
function parseSnapshot(html) {
  const snap = {
    $schema: "snapshot-v1",
    fetchedAt: new Date().toISOString(),
    source: { url: URL, siteSnapshotAt: null },
    metrics: { activeSignals: null, coverage: null, delta24h: null, delta7d: null, delta30d: null, newsDriven: null },
    priorityQueue: [],
    hotStocks: [],
    feedItems: [],
    distribution: {},
    industries: null,
    raw: {
      htmlLength: html.length,
      checksum: "sha256:" + crypto.createHash("sha256").update(html).digest("hex")
    }
  };

  // ---- site snapshot timestamp ----
  // 站台首頁通常會有「2026-05-29 11:50」這類戳記
  const tsMatch = html.match(/(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2})/);
  if (tsMatch) snap.source.siteSnapshotAt = tsMatch[1].replace(" ", "T") + ":00+08:00";

  // ---- metrics ----
  // 站台格式：「活躍信號 439」「股票覆蓋 701」
  const grabNumber = (label, fallbackLabel) => {
    const re = new RegExp(`${label}\\s*\\D*?(\\d+)`);
    const m = html.match(re);
    if (m) return parseInt(m[1], 10);
    if (fallbackLabel) {
      const re2 = new RegExp(`${fallbackLabel}\\s*\\D*?(\\d+)`);
      const m2 = html.match(re2);
      if (m2) return parseInt(m2[1], 10);
    }
    return null;
  };

  snap.metrics.activeSignals = grabNumber("活跃信号|活躍信號");
  snap.metrics.coverage      = grabNumber("股票覆盖|股票覆蓋");
  snap.metrics.delta24h      = grabNumber("24h\\s*活跃|24h\\s*活躍");
  snap.metrics.delta7d       = grabNumber("7天活跃|7天活躍");
  snap.metrics.delta30d      = grabNumber("30天活跃|30天活躍");
  snap.metrics.newsDriven    = grabNumber("新闻驱动|新聞驅動");

  // ---- priorityQueue & hotStocks ----
  // 提取所有 ticker 條目（在首頁出現如 [1NVDA05-27 11:49...]）
  // 用 ticker pattern + 後面的優先級數字
  const tickerEntryRe = /\[?\d?\*?([A-Z]{2,6})\*?\s*(?:05-\d{2}|06-\d{2}|07-\d{2}|08-\d{2}|09-\d{2}|10-\d{2}|11-\d{2}|12-\d{2}|01-\d{2}|02-\d{2}|03-\d{2}|04-\d{2})/g;
  const priorityRe = /优先级\s*(\d+)|優先級\s*(\d+)/g;

  const tickers = [];
  let m;
  while ((m = tickerEntryRe.exec(html)) !== null) {
    if (!tickers.includes(m[1])) tickers.push(m[1]);
    if (tickers.length >= 20) break;
  }

  const priorities = [];
  while ((m = priorityRe.exec(html)) !== null) {
    priorities.push(parseInt(m[1] || m[2], 10));
    if (priorities.length >= 20) break;
  }

  // priorityQueue = top 3
  // hotStocks = top 10
  for (let i = 0; i < Math.min(tickers.length, 10); i++) {
    const stock = {
      rank: i + 1,
      ticker: tickers[i],
      priority: priorities[i] ?? null,
      stance: inferStance(html, tickers[i]),
      aiChange: html.includes(`GPT xhigh 更新 · ${tickers[i]}`) ? "xhigh" : null,
      summary: extractSummary(html, tickers[i]),
      tags: extractTags(html, tickers[i]),
      updatedAt: snap.source.siteSnapshotAt
    };
    snap.hotStocks.push(stock);
    if (i < 3) snap.priorityQueue.push({ ...stock });
  }

  // ---- feedItems ----
  // 「最新信息流」段下方
  const feedSection = extractSection(html, "最新信息流", "队列分布|隊列分布|当前观点|當前觀點");
  if (feedSection) {
    snap.feedItems = parseFeedItems(feedSection);
  }

  // ---- distribution ----
  // 「队列分布」下方
  const distRe = /(观察|積極觀察|积极观察|高风险观察|高風險觀察|谨慎|謹慎|高风险偏多|高風險偏多)(\d+)/g;
  while ((m = distRe.exec(html)) !== null) {
    snap.distribution[m[1]] = parseInt(m[2], 10);
  }

  return snap;
}

function inferStance(html, ticker) {
  const ctx = extractContextForTicker(html, ticker, 200);
  if (!ctx) return null;

  const hasBull = /看多/.test(ctx);
  const hasBear = /看空/.test(ctx);
  const hasHighRisk = /高风险偏多|高風險偏多/.test(ctx);
  const hasWatch    = /高风险观察|高風險觀察/.test(ctx);
  const hasCaution  = /谨慎|謹慎/.test(ctx);
  const hasNeutral  = /中性/.test(ctx);

  if (hasBull && hasHighRisk) return "bull_high_risk";
  if (hasNeutral && hasWatch) return "watch_high_risk";
  if (hasBear || hasCaution)  return "caution";
  if (hasBull) return "bull";
  if (hasNeutral) return "neutral";
  return null;
}

function extractContextForTicker(html, ticker, charsAround = 200) {
  const idx = html.indexOf(ticker);
  if (idx === -1) return null;
  return html.slice(Math.max(0, idx - 20), idx + charsAround);
}

function extractSummary(html, ticker) {
  const ctx = extractContextForTicker(html, ticker, 400);
  if (!ctx) return null;
  // 抓最後一段中文（粗略版本，真實實作可用 DOMParser）
  const tail = ctx.replace(/[A-Z]+\d*/g, "").replace(/\d{2}-\d{2}/g, "").trim();
  return tail.slice(0, 120);
}

function extractTags(html, ticker) {
  const ctx = extractContextForTicker(html, ticker, 200);
  if (!ctx) return [];
  const out = [];
  if (/看多/.test(ctx))         out.push("看多");
  if (/看空/.test(ctx))         out.push("看空");
  if (/中性/.test(ctx))         out.push("中性");
  if (/高风险偏多|高風險偏多/.test(ctx)) out.push("高风险偏多");
  if (/高风险观察|高風險觀察/.test(ctx)) out.push("高风险观察");
  if (/谨慎|謹慎/.test(ctx))    out.push("谨慎");
  if (/GPT xhigh/.test(ctx))    out.push("GPT xhigh");
  if (/24h/.test(ctx))          out.push("24h");
  return out;
}

function extractSection(html, startMarker, endMarker) {
  const startRe = new RegExp(startMarker);
  const endRe   = new RegExp(endMarker);
  const s = html.search(startRe);
  if (s === -1) return null;
  const rest = html.slice(s);
  const e = rest.search(endRe);
  return e === -1 ? rest : rest.slice(0, e);
}

function parseFeedItems(section) {
  // 粗略：抓「[時間 GPT xhigh TICKER...]」這類條目
  const items = [];
  const itemRe = /\[?(\d{2}-\d{2}\s*\d{2}:\d{2})\s*(GPT\s+\w+)?\s*([A-Z]{2,6})/g;
  let m;
  let i = 0;
  while ((m = itemRe.exec(section)) !== null && i < 20) {
    items.push({
      id: `feed-${i++}`,
      kind: "ai",
      ticker: m[3],
      title: `GPT xhigh 更新 · ${m[3]}`,
      body: "",  // 完整版要再從首頁提取；MVP 留空
      badges: [
        { label: m[2] || "GPT xhigh", tone: "ai" }
      ],
      publishedAt: m[1]
    });
  }
  return items;
}

async function main() {
  const args = process.argv.slice(2);
  const stdout = args.includes("--stdout");
  const dry    = args.includes("--dry");

  let html;
  try {
    html = await fetchHTML(URL);
  } catch (err) {
    process.stderr.write(`[ERROR] fetch failed: ${err.message}\n`);
    process.exit(2);
  }

  const snap = parseSnapshot(html);

  if (dry) {
    process.stderr.write(`[INFO] parsed: ${snap.priorityQueue.length} priorityQueue, ${snap.hotStocks.length} hotStocks, ${snap.feedItems.length} feedItems\n`);
    if (stdout) process.stdout.write(JSON.stringify(snap, null, 2));
    return;
  }

  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.mkdir(RAW_DIR,  { recursive: true });

  const date = new Date().toISOString().slice(0, 10);
  const out  = path.join(DATA_DIR, `${date}.json`);
  await fs.writeFile(out, JSON.stringify(snap, null, 2));
  await fs.writeFile(path.join(DATA_DIR, "latest.json"), JSON.stringify(snap, null, 2));
  await fs.writeFile(path.join(RAW_DIR,  `${date}.html`), html);

  process.stderr.write(`[INFO] snapshot saved: ${out}\n`);
  if (stdout) process.stdout.write(JSON.stringify(snap, null, 2));
}

main().catch(err => {
  process.stderr.write(`[FATAL] ${err.message}\n`);
  process.exit(1);
});
