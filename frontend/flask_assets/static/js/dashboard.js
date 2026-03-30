/**
 * dashboard.js — Smart Traffic AI Dashboard
 * Real-time polling of Flask API endpoints.
 * Updates signal display, lane cards, Chart.js history, and prediction panel.
 */

"use strict";

// ── Config ────────────────────────────────────────────────────────────────────
const API_LANES   = "/api/lanes";
const API_SIGNALS = "/api/signals";
const API_STATUS  = "/api/status";
const API_HISTORY = "/api/history";
const POLL_MS     = 500;

const LANE_NAMES  = ["LEFT", "LEFT-CENTER", "RIGHT-CENTER", "RIGHT"];
const LANE_COLORS = {
  "LEFT":         "#fbbf24",
  "LEFT-CENTER":  "#38bdf8",
  "RIGHT-CENTER": "#e879f9",
  "RIGHT":        "#34d399",
};

// ── Chart.js setup ────────────────────────────────────────────────────────────
const MAX_HISTORY_POINTS = 60;

const histCtx = document.getElementById("hist-chart").getContext("2d");
const histDatasets = LANE_NAMES.map(ln => ({
  label:            ln,
  data:             [],
  borderColor:      LANE_COLORS[ln],
  backgroundColor:  LANE_COLORS[ln] + "20",
  borderWidth:      2,
  tension:          0.4,
  pointRadius:      0,
  fill:             false,
}));

const histChart = new Chart(histCtx, {
  type: "line",
  data: {
    labels:   [],
    datasets: histDatasets,
  },
  options: {
    animation:    false,
    responsive:   true,
    maintainAspectRatio: false,
    interaction:  { mode: "index", intersect: false },
    plugins: {
      legend: {
        labels: {
          color: "#94a3b8",
          boxWidth: 12,
          font: { size: 11, family: "Inter" },
        },
      },
      tooltip: {
        backgroundColor: "rgba(8,13,20,0.9)",
        borderColor:     "rgba(59,130,246,0.3)",
        borderWidth:     1,
        titleColor:      "#e2e8f0",
        bodyColor:       "#94a3b8",
        callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`,
        },
      },
    },
    scales: {
      x: {
        display: false,
      },
      y: {
        min: 0, max: 100,
        grid:  { color: "rgba(255,255,255,0.04)" },
        ticks: { color: "#475569", font: { size: 10 }, callback: v => v + "%" },
        border: { dash: [4, 4] },
      },
    },
  },
});

// ── State ─────────────────────────────────────────────────────────────────────
let historyBuffer = {};  // lane → [float, ...]
LANE_NAMES.forEach(ln => { historyBuffer[ln] = []; });
let chartTickCount = 0;

// ── Initialise DOM ────────────────────────────────────────────────────────────
function initLaneSignals() {
  const container = document.getElementById("lane-signals");
  container.innerHTML = "";
  LANE_NAMES.forEach(ln => {
    const item = document.createElement("div");
    item.className = "lane-sig-item";
    item.id = `sig-item-${ln}`;
    item.innerHTML = `
      <div class="sig-dot red" id="sdot-${ln}"></div>
      <div class="sig-ln-name">${ln}</div>
    `;
    container.appendChild(item);
  });
}

function initLanesGrid() {
  const grid = document.getElementById("lanes-grid");
  grid.innerHTML = "";
  LANE_NAMES.forEach(ln => {
    const color = LANE_COLORS[ln];
    const card = document.createElement("div");
    card.className = "lane-stat-card";
    card.id = `lsc-${ln}`;
    card.innerHTML = `
      <div class="lsc-header">
        <div class="lsc-name" style="color:${color}">${ln}</div>
        <div class="lsc-trend-arrow" id="trend-${ln}">→</div>
      </div>
      <div class="lsc-bar-wrap">
        <div class="lsc-bar" id="lbar-${ln}" style="width:0%;background:${color}"></div>
      </div>
      <div class="lsc-pressure" id="lpres-${ln}" style="color:${color}">—</div>
      <div class="lsc-counts">
        <div class="count-pill">🟢 <span id="lmov-${ln}">0</span></div>
        <div class="count-pill">🔴 <span id="lstp-${ln}">0</span></div>
        <div class="count-pill">🚗 <span id="ltot-${ln}">0</span></div>
      </div>
      <div class="lsc-types" id="ltypes-${ln}"></div>
    `;
    grid.appendChild(card);
  });
}

function initPredictGrid() {
  const grid = document.getElementById("predict-grid");
  grid.innerHTML = "";
  LANE_NAMES.forEach(ln => {
    const color = LANE_COLORS[ln];
    const item = document.createElement("div");
    item.className = "predict-item";
    item.id = `pred-${ln}`;
    item.innerHTML = `
      <div class="predict-label" style="color:${color}">${ln}</div>
      <div class="predict-now" id="pred-now-${ln}">Current: —</div>
      <div class="predict-future" id="pred-fut-${ln}" style="color:${color}">—</div>
    `;
    grid.appendChild(item);
  });
}

// ── Update helpers ────────────────────────────────────────────────────────────

function setSignalLights(isGreen) {
  const red   = document.getElementById("sig-red");
  const amber = document.getElementById("sig-amber");
  const green = document.getElementById("sig-green");
  [red, amber, green].forEach(el => el.classList.remove("active"));
  if (isGreen) green.classList.add("active");
  else         red.classList.add("active");
}

function updateSignals(data) {
  const { signals, active_lane, state, time_remaining, green_duration } = data;

  // Header chip
  const chip = document.getElementById("system-state-chip");
  chip.textContent = "● " + state;
  chip.className = "status-chip";
  if (state === "AMBULANCE_OVERRIDE") chip.classList.add("emergency");
  else if (state === "FAILSAFE")      chip.classList.add("failsafe");

  // Ambulance banner
  const banner = document.getElementById("amb-banner");
  if (state === "AMBULANCE_OVERRIDE") banner.classList.remove("hidden");
  else                                banner.classList.add("hidden");

  // Active lane display
  document.getElementById("active-lane-name").textContent = active_lane;
  setSignalLights(true);

  // Timer bar
  const ratio = time_remaining / Math.max(1, green_duration);
  document.getElementById("timer-bar").style.width = (ratio * 100).toFixed(1) + "%";
  document.getElementById("timer-remain").textContent = time_remaining.toFixed(1);
  document.getElementById("timer-total").textContent  = green_duration;

  // 4-lane mini signals
  LANE_NAMES.forEach(ln => {
    const item = document.getElementById(`sig-item-${ln}`);
    const dot  = document.getElementById(`sdot-${ln}`);
    if (!item || !dot) return;
    const isG = signals[ln] === "GREEN";
    dot.className = "sig-dot " + (isG ? "green" : "red");
    item.className = "lane-sig-item" + (isG ? " green-lane" : "");
  });
}

function updateLanes(lanesData, predicted, trends) {
  LANE_NAMES.forEach((ln, idx) => {
    const stats = lanesData[ln] || {};
    const pred  = (predicted || {})[ln] ?? null;
    const trend = (trends    || {})[ln] ?? "STABLE";

    // Lane stat card
    const card = document.getElementById(`lsc-${ln}`);
    if (card) {
      const isActive = document.getElementById("active-lane-name")?.textContent === ln;
      card.className = "lane-stat-card" + (isActive ? " active" : "");
    }

    const pressure = stats.pressure ?? 0;
    const barEl = document.getElementById(`lbar-${ln}`);
    if (barEl) barEl.style.width = pressure.toFixed(1) + "%";

    const presEl = document.getElementById(`lpres-${ln}`);
    if (presEl) presEl.textContent = pressure.toFixed(1) + "%";

    const movEl = document.getElementById(`lmov-${ln}`);
    if (movEl) movEl.textContent = stats.moving ?? 0;

    const stpEl = document.getElementById(`lstp-${ln}`);
    if (stpEl) stpEl.textContent = stats.stopped ?? 0;

    const totEl = document.getElementById(`ltot-${ln}`);
    if (totEl) totEl.textContent = stats.total ?? 0;

    // Vehicle type breakdown
    const typesEl = document.getElementById(`ltypes-${ln}`);
    if (typesEl) {
      const counts = stats.vehicle_counts ?? {};
      typesEl.textContent = Object.entries(counts)
        .map(([k, v]) => `${k}: ${v}`)
        .join(" · ") || "—";
    }

    // Trend arrow
    const trendEl = document.getElementById(`trend-${ln}`);
    if (trendEl) {
      const up = "#ef4444", dn = "#22c55e", st = "#475569";
      if (trend === "UP")     { trendEl.textContent = "↑"; trendEl.style.color = up; }
      else if (trend === "DOWN") { trendEl.textContent = "↓"; trendEl.style.color = dn; }
      else                    { trendEl.textContent = "→"; trendEl.style.color = st; }
    }

    // Congestion badge on signal card
    if (ln === document.getElementById("active-lane-name")?.textContent) {
      const badge = document.getElementById("cong-badge");
      if (badge) {
        badge.textContent  = stats.congestion_level ?? "—";
        badge.className    = "cong-badge " + (stats.congestion_level ?? "LOW");
      }
    }

    // Prediction panel
    const nowEl = document.getElementById(`pred-now-${ln}`);
    const futEl = document.getElementById(`pred-fut-${ln}`);
    if (nowEl) nowEl.textContent = `Now: ${pressure.toFixed(1)}%`;
    if (futEl && pred !== null) {
      futEl.textContent = pred.toFixed(1) + "%";
      const color = pred < 33 ? "#22c55e" : pred < 66 ? "#f59e0b" : "#ef4444";
      futEl.style.color = color;
    }

    // History chart  
    if (!historyBuffer[ln]) historyBuffer[ln] = [];
    historyBuffer[ln].push(pressure);
    if (historyBuffer[ln].length > MAX_HISTORY_POINTS)
      historyBuffer[ln].shift();
    histDatasets[idx].data = [...historyBuffer[ln]];
  });

  // Update chart labels
  chartTickCount++;
  histChart.data.labels = historyBuffer[LANE_NAMES[0]].map((_, i) => i);
  histChart.update("none");
}

function updateStatus(data) {
  const fpsEl    = document.getElementById("fps-val");
  const frameEl  = document.getElementById("frame-val");
  const uptimeEl = document.getElementById("uptime-val");
  if (fpsEl)    fpsEl.textContent    = data.fps ?? "—";
  if (frameEl)  frameEl.textContent  = (data.frame_count ?? 0).toLocaleString();
  if (uptimeEl) uptimeEl.textContent = formatUptime(data.uptime_s ?? 0);
}

function formatUptime(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return [h, m, sec].map(x => String(x).padStart(2, "0")).join(":");
}

// ── Polling loop ──────────────────────────────────────────────────────────────
async function fetchAll() {
  try {
    const [sigRes, laneRes, statRes] = await Promise.all([
      fetch(API_SIGNALS),
      fetch(API_LANES),
      fetch(API_STATUS),
    ]);

    if (sigRes.ok)  updateSignals(await sigRes.json());
    if (laneRes.ok) {
      const ld = await laneRes.json();
      updateLanes(ld.lanes, ld.predicted, ld.trends);
    }
    if (statRes.ok) updateStatus(await statRes.json());
  } catch (e) {
    // Server not yet up — silently retry
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
initLaneSignals();
initLanesGrid();
initPredictGrid();
setInterval(fetchAll, POLL_MS);
fetchAll();   // immediate first poll
