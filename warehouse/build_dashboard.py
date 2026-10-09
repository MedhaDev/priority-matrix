"""Build a self-contained HTML preview of the dashboard from exports/*.csv.

  python warehouse/build_dashboard.py        # → exports/dashboard.html

The same views, colors and numbers as the Tableau Public dashboard
(docs/dashboard.md), as one file that opens anywhere. Synthetic data only.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "exports"


def read(name):
    with open(EXPORTS / f"{name}.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    try:
        data = {
            "h1": read("h1_focus_by_quadrant"),
            "weekly": read("weekly_focus_share"),
            "urgent": read("h2_urgent_tasks"),
            "h2": read("h2_downgrade_summary")[0],
            "dq": read("data_quality_summary"),
            "daily": read("daily_focus_metrics"),
            "meta": json.loads((EXPORTS / "_exported.json").read_text()),
        }
    except FileNotFoundError as e:
        print(f"Missing export ({e.filename}). Run warehouse/export.py first.", file=sys.stderr)
        return 1
    days = sorted({r["focus_date"] for r in data["daily"]})
    data["range"] = [days[0], days[-1]] if days else ["", ""]
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    out = EXPORTS / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"dashboard → {out}")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where My Focus Goes</title>
<link href="https://api.fontshare.com/v2/css?f[]=switzer@400,500,600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #f3f2ee; --sheet: #fcfbf8; --ink: #1c1b19; --muted: #6e6b65; --faint: #a6a39c;
    --rule: #e4e1da; --grid: #ece9e3; --fill: #ebe9e3; --neutral: #c9c6bf;
    --do: #d4512f; --schedule: #3f6fc6; --delegate: #d8a03a; --eliminate: #6b9a5e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--ink); font: 400 14.5px/1.5 "Switzer", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 36px 32px 56px; }
  header { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap; margin-bottom: 26px; }
  h1 { font-size: 30px; font-weight: 600; letter-spacing: -0.03em; line-height: 1.15; }
  .sub { color: var(--muted); margin-top: 6px; max-width: 640px; }
  .tag { font-size: 12.5px; color: var(--muted); background: var(--fill); padding: 5px 10px; border-radius: 7px; white-space: nowrap; }
  .card { background: var(--sheet); border: 1px solid var(--rule); border-radius: 12px; box-shadow: 0 1px 2px rgba(28,27,25,.04), 0 8px 24px -12px rgba(28,27,25,.08); padding: 20px 22px; min-width: 0; }
  .card h2 { font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }
  .card .desc { color: var(--muted); font-size: 13.5px; margin: 2px 0 14px; }
  .kpis { display: grid; grid-template-columns: 1.5fr 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .hero .value { font-size: 64px; font-weight: 500; letter-spacing: -0.045em; line-height: 1; margin: 6px 0 8px; }
  .tile .value { font-size: 34px; font-weight: 500; letter-spacing: -0.035em; line-height: 1.05; margin: 6px 0 6px; }
  .label { font-size: 13px; color: var(--muted); }
  .note { font-size: 12.5px; color: var(--faint); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12.5px; color: var(--muted); margin-bottom: 8px; }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .sw { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
  svg { display: block; width: 100%; height: auto; overflow: visible; }
  svg text { font-family: inherit; fill: var(--muted); font-size: 12px; }
  svg .val { fill: var(--ink); font-weight: 500; }
  svg .grid { stroke: var(--grid); stroke-width: 1; }
  details { margin-top: 12px; font-size: 13px; }
  summary { cursor: pointer; color: var(--muted); }
  table { border-collapse: collapse; margin-top: 8px; width: 100%; font-variant-numeric: tabular-nums; }
  th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--rule); }
  th { color: var(--muted); font-weight: 500; }
  td.n, th.n { text-align: right; }
  .dq td:first-child { color: var(--muted); }
  .tip { position: fixed; pointer-events: none; background: var(--ink); color: #fff; font-size: 12.5px; padding: 7px 9px; border-radius: 7px; box-shadow: 0 6px 18px rgba(0,0,0,.18); opacity: 0; transition: opacity .1s; z-index: 10; white-space: nowrap; }
  .tip b { font-weight: 600; }
  .tip .row { display: flex; align-items: center; gap: 6px; }
  footer { margin-top: 26px; color: var(--faint); font-size: 12.5px; display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
  footer a { color: inherit; }
  @media (max-width: 860px) {
    .wrap { padding: 24px 16px 40px; }
    .kpis { grid-template-columns: 1fr 1fr; }
    .hero { grid-column: 1 / -1; }
    .grid2 { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>Where my focus actually goes</h1>
      <p class="sub">An Eisenhower Matrix + Pomodoro app logs every action as an event. This is the pipeline's output for a simulated version of me, with my two hypotheses planted to see if the analysis finds them.</p>
    </div>
    <span class="tag" id="range"></span>
  </header>

  <section class="kpis">
    <div class="card hero">
      <div class="label">Do first's share of my focus vs. its share of my to-do list</div>
      <div class="value" id="hero"></div>
      <div class="note" id="hero-note"></div>
    </div>
    <div class="card tile"><div class="label">Focus time</div><div class="value" id="k-hours"></div><div class="note" id="k-sessions"></div></div>
    <div class="card tile"><div class="label">Urgent tasks later downgraded</div><div class="value" id="k-down"></div><div class="note">of those still open the next morning</div></div>
    <div class="card tile"><div class="label">Median time to downgrade</div><div class="value" id="k-median"></div><div class="note" id="k-72"></div></div>
  </section>

  <section class="grid2">
    <div class="card">
      <h2>Focus vs. the list, by quadrant</h2>
      <p class="desc">Hypothesis 1: urgent-important work gets more focus than its place on the list.</p>
      <div class="legend"><span><i class="sw" style="background:linear-gradient(90deg,var(--do) 25%,var(--schedule) 25% 50%,var(--delegate) 50% 75%,var(--eliminate) 75%)"></i>Share of focus time</span><span><i class="sw" style="background:var(--neutral)"></i>Share of task-days on the list</span></div>
      <div id="c-h1"></div>
      <details><summary>Show table</summary><div id="t-h1"></div></details>
    </div>
    <div class="card">
      <h2>Weekly share of focus time</h2>
      <p class="desc">Each week's focus split across the four quadrants.</p>
      <div class="legend" id="l-weekly"></div>
      <div id="c-weekly"></div>
      <details><summary>Show table</summary><div id="t-weekly"></div></details>
    </div>
  </section>

  <section class="grid2">
    <div class="card">
      <h2>How long "urgent" lasts</h2>
      <p class="desc">Hypothesis 2: time from creating an urgent task to moving it out of urgent.</p>
      <div id="c-h2"></div>
      <details><summary>Show table</summary><div id="t-h2"></div></details>
    </div>
    <div class="card">
      <h2>Pipeline health</h2>
      <p class="desc">What arrived and what staging had to fix. Problems are injected on purpose, then caught.</p>
      <table class="dq" id="t-dq"></table>
    </div>
  </section>

  <footer>
    <span>Synthetic data generated from my own estimates of how I work. Python generator → DuckDB/Postgres → dbt (tested, reconciled with an answer key) → Airflow.</span>
    <a href="https://github.com/MedhaDev/priority-matrix">Source on GitHub</a>
  </footer>
</div>
<div class="tip" id="tip" role="status" aria-live="polite"></div>

<script>
const D = __DATA__;
const Q = [
  { id: "do", label: "Do first", color: "#d4512f" },
  { id: "schedule", label: "Schedule", color: "#3f6fc6" },
  { id: "delegate", label: "Delegate", color: "#d8a03a" },
  { id: "eliminate", label: "Eliminate", color: "#6b9a5e" },
];
const NS = "http://www.w3.org/2000/svg";
const pct = (x, d = 0) => (x * 100).toFixed(d) + "%";
const fmtDate = (s) => new Date(s + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
const el = (tag, attrs = {}, parent) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
};
const svg = (w, h, label) => el("svg", { viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": label });
// Column with a 4px rounded data-end and a square baseline.
const barPath = (x, y, w, h, horizontal) => {
  const r = Math.min(4, (horizontal ? h : w) / 2, horizontal ? w : h);
  return horizontal
    ? `M${x},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} H${x} Z`
    : `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
};
const tip = document.getElementById("tip");
const showTip = (html, ev) => {
  tip.innerHTML = html;
  tip.style.opacity = 1;
  const x = Math.min(ev.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
  tip.style.left = x + "px";
  tip.style.top = ev.clientY + 14 + "px";
};
const hideTip = () => (tip.style.opacity = 0);
const table = (cols, rows) =>
  "<table><tr>" + cols.map((c) => `<th class="${c.n ? "n" : ""}">${c.h}</th>`).join("") + "</tr>" +
  rows.map((r) => "<tr>" + cols.map((c) => `<td class="${c.n ? "n" : ""}">${c.f(r)}</td>`).join("") + "</tr>").join("") + "</table>";

// ── header + KPIs ──
document.getElementById("range").textContent = `Synthetic · ${fmtDate(D.range[0])} – ${fmtDate(D.range[1])}, 2026`;
const h1 = Object.fromEntries(D.h1.map((r) => [r.quadrant, r]));
document.getElementById("hero").textContent = (+h1.do.focus_vs_list).toFixed(1) + "×";
document.getElementById("hero-note").textContent =
  `${pct(+h1.do.focus_share)} of focus time, ${pct(+h1.do.list_share)} of task-days. Schedule: ${pct(+h1.schedule.focus_share)} of focus, ${pct(+h1.schedule.list_share)} of the list.`;
const hours = D.h1.reduce((s, r) => s + +r.focused_secs, 0) / 3600;
const fin = D.h1.reduce((s, r) => s + +r.sessions_finished, 0), ab = D.h1.reduce((s, r) => s + +r.sessions_abandoned, 0);
document.getElementById("k-hours").textContent = Math.round(hours) + "h";
document.getElementById("k-sessions").textContent = `${fin + ab} sessions · ${pct(ab / (fin + ab))} abandoned`;
document.getElementById("k-down").textContent = pct(+D.h2.downgrade_rate_among_open_next_morning);
document.getElementById("k-median").textContent = (+D.h2.median_days_to_downgrade).toFixed(1) + " days";
document.getElementById("k-72").textContent = `${D.h2.downgraded_within_72h} of ${D.h2.downgraded} within 72 hours`;

// ── H1: paired horizontal bars ──
(function () {
  const W = 480, rowH = 52, top = 4, left = 78, right = 46, H = top + rowH * Q.length;
  const s = svg(W, H, "Share of focus time vs share of to-do list, by quadrant");
  const max = Math.max(...D.h1.map((r) => Math.max(+r.focus_share, +r.list_share)));
  const x = (v) => (v / max) * (W - left - right);
  Q.forEach((q, i) => {
    const r = h1[q.id], y = top + i * rowH;
    el("text", { x: 0, y: y + 22 }, s).textContent = q.label;
    const bars = [
      { v: +r.focus_share, color: q.color, y: y + 6, name: "Focus time" },
      { v: +r.list_share, color: "#c9c6bf", y: y + 6 + 16, name: "Task-days on list" },
    ];
    bars.forEach((b) => {
      el("path", { d: barPath(left, b.y, Math.max(1, x(b.v)), 14, true), fill: b.color }, s);
      const t = el("text", { x: left + x(b.v) + 6, y: b.y + 11, class: b.name === "Focus time" ? "val" : "" }, s);
      t.textContent = pct(b.v);
    });
    const hit = el("rect", { x: 0, y, width: W, height: rowH - 4, fill: "transparent" }, s);
    hit.addEventListener("mousemove", (ev) => showTip(
      `<b>${q.label}</b><div class="row"><i class="sw" style="background:${q.color}"></i>Focus time ${pct(+r.focus_share, 1)} · ${r.focused_hours}h</div>` +
      `<div class="row"><i class="sw" style="background:#c9c6bf"></i>On the list ${pct(+r.list_share, 1)} · ${r.task_days} task-days</div>` +
      `<div>${(+r.focus_vs_list).toFixed(2)}× its list share</div>`, ev));
    hit.addEventListener("mouseleave", hideTip);
  });
  document.getElementById("c-h1").appendChild(s);
  document.getElementById("t-h1").innerHTML = table(
    [{ h: "Quadrant", f: (r) => Q.find((q) => q.id === r.quadrant).label },
     { h: "Focus share", n: 1, f: (r) => pct(+r.focus_share, 1) }, { h: "List share", n: 1, f: (r) => pct(+r.list_share, 1) },
     { h: "Focus ÷ list", n: 1, f: (r) => (+r.focus_vs_list).toFixed(2) + "×" }, { h: "Hours", n: 1, f: (r) => r.focused_hours }],
    Q.map((q) => h1[q.id]));
})();

// ── Weekly focus share: four 2px lines, crosshair + tooltip ──
(function () {
  const weeks = [...new Set(D.weekly.map((r) => r.week_start))].sort();
  const val = {};
  D.weekly.forEach((r) => (val[r.week_start + "|" + r.quadrant] = +r.focus_share));
  const W = 480, H = 230, L = 34, R = 70, T = 8, B = 24;
  const s = svg(W, H, "Weekly share of focus time by quadrant");
  const x = (i) => L + (i / Math.max(1, weeks.length - 1)) * (W - L - R);
  const y = (v) => T + (1 - v) * (H - T - B);
  [0, 0.25, 0.5, 0.75, 1].forEach((g) => {
    el("line", { x1: L, x2: W - R, y1: y(g), y2: y(g), class: "grid" }, s);
    el("text", { x: L - 6, y: y(g) + 4, "text-anchor": "end" }, s).textContent = pct(g);
  });
  [0, Math.floor((weeks.length - 1) / 2), weeks.length - 1].forEach((i) =>
    (el("text", { x: x(i), y: H - 6, "text-anchor": "middle" }, s).textContent = fmtDate(weeks[i])));
  const ends = [];
  Q.forEach((q) => {
    const pts = weeks.map((w, i) => [x(i), y(val[w + "|" + q.id] || 0)]);
    el("path", { d: "M" + pts.map((p) => p.join(",")).join("L"), fill: "none", stroke: q.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, s);
    const last = pts[pts.length - 1];
    el("circle", { cx: last[0], cy: last[1], r: 4, fill: q.color, stroke: "#fcfbf8", "stroke-width": 2 }, s);
    ends.push({ q, y: last[1] });
  });
  // End labels; nudge only enough to avoid overlap, with a short leader line.
  ends.sort((a, b) => a.y - b.y);
  let prev = -Infinity;
  ends.forEach((e) => {
    const ly = Math.max(e.y, prev + 14);
    prev = ly;
    if (Math.abs(ly - e.y) > 2) el("line", { x1: W - R + 4, x2: W - R + 10, y1: e.y, y2: ly, stroke: "#c9c6bf" }, s);
    el("text", { x: W - R + 12, y: ly + 4 }, s).textContent = e.q.label;
  });
  const cross = el("line", { y1: T, y2: H - B, stroke: "#a6a39c", "stroke-width": 1, opacity: 0 }, s);
  const hit = el("rect", { x: L, y: T, width: W - L - R, height: H - T - B, fill: "transparent" }, s);
  hit.addEventListener("mousemove", (ev) => {
    const box = s.getBoundingClientRect();
    const px = ((ev.clientX - box.left) / box.width) * W;
    const i = Math.max(0, Math.min(weeks.length - 1, Math.round(((px - L) / (W - L - R)) * (weeks.length - 1))));
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("opacity", 1);
    showTip(`<b>Week of ${fmtDate(weeks[i])}</b>` + Q.map((q) =>
      `<div class="row"><i class="sw" style="background:${q.color}"></i>${q.label} ${pct(val[weeks[i] + "|" + q.id] || 0)}</div>`).join(""), ev);
  });
  hit.addEventListener("mouseleave", () => { hideTip(); cross.setAttribute("opacity", 0); });
  document.getElementById("l-weekly").innerHTML = Q.map((q) => `<span><i class="sw" style="background:${q.color}"></i>${q.label}</span>`).join("");
  document.getElementById("c-weekly").appendChild(s);
  document.getElementById("t-weekly").innerHTML = table(
    [{ h: "Week of", f: (w) => fmtDate(w) }, ...Q.map((q) => ({ h: q.label, n: 1, f: (w) => pct(val[w + "|" + q.id] || 0) }))], weeks);
})();

// ── H2: histogram of hours to downgrade (one series, one color) ──
(function () {
  const lags = D.urgent.filter((r) => r.downgraded === "true").map((r) => +r.hours_to_downgrade);
  // Downgrades happen at the morning review, so bin by day, not by hour.
  const bins = [[0, 24], [24, 48], [48, 72], [72, Infinity]];
  const names = ["Within a day", "Day 2", "Day 3", "Later"];
  const counts = bins.map(([a, b]) => lags.filter((h) => h >= a && h < b).length);
  const W = 480, H = 230, L = 30, R = 8, T = 18, B = 24, slot = (W - L - R) / bins.length, bw = Math.min(56, slot - 24);
  const s = svg(W, H, "Urgent tasks downgraded, by hours until downgrade");
  const max = Math.max(...counts), step = Math.ceil(max / 4 / 5) * 5 || 1;
  const y = (v) => T + (1 - v / (step * 4)) * (H - T - B);
  for (let g = 0; g <= 4; g++) {
    el("line", { x1: L, x2: W - R, y1: y(g * step), y2: y(g * step), class: "grid" }, s);
    el("text", { x: L - 6, y: y(g * step) + 4, "text-anchor": "end" }, s).textContent = g * step;
  }
  counts.forEach((c, i) => {
    const cx = L + slot * i + (slot - bw) / 2;
    el("path", { d: barPath(cx, y(c), bw, y(0) - y(c), false), fill: "#d4512f" }, s);
    if (c === max || i === counts.length - 1) el("text", { x: cx + bw / 2, y: y(c) - 6, "text-anchor": "middle", class: "val" }, s).textContent = c;
    el("text", { x: cx + bw / 2, y: H - 6, "text-anchor": "middle" }, s).textContent = names[i];
    const hit = el("rect", { x: L + slot * i, y: T, width: slot, height: H - T - B, fill: "transparent" }, s);
    hit.addEventListener("mousemove", (ev) => showTip(`<b>${names[i]}</b><div>${c} task${c === 1 ? "" : "s"} · ${pct(c / lags.length)} of downgrades</div>`, ev));
    hit.addEventListener("mouseleave", hideTip);
  });
  document.getElementById("c-h2").appendChild(s);
  document.getElementById("t-h2").innerHTML = table(
    [{ h: "Time to downgrade", f: (i) => names[i] }, { h: "Tasks", n: 1, f: (i) => counts[i] }, { h: "Share", n: 1, f: (i) => pct(counts[i] / lags.length) }],
    counts.map((_, i) => i)) +
    `<p class="note" style="margin-top:8px">${D.h2.downgraded} of ${D.h2.urgent_tasks} urgent tasks were downgraded (${pct(+D.h2.downgrade_rate)}); among the ${D.h2.urgent_tasks_open_next_morning} still open the next morning, ${pct(+D.h2.downgrade_rate_among_open_next_morning)}.</p>`;
})();

// ── Pipeline health table ──
document.getElementById("t-dq").innerHTML = D.dq.map((r) =>
  `<tr><td>${r.measure.charAt(0).toUpperCase() + r.measure.slice(1)}</td><td class="n">${(+r.value).toLocaleString()}</td></tr>`).join("");
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
