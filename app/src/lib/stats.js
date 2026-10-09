// Everything here is derived from the event log, the same way the dbt models
// will do it later. Small in-app preview of the real analysis.
import { isUrgent, quadrantLabel, QUADRANTS } from "./events";
import { weekdayName } from "./dates";

const ENDED = new Set(["pomodoro_finished", "pomodoro_abandoned"]);
const focusSecs = (e) => (ENDED.has(e.event_type) ? e.payload?.focused_secs || 0 : 0);
const DAY_MS = 86400000;

// Per-task facts for the little chips on each card.
export function taskMeta(events) {
  const meta = new Map();
  const get = (id) => {
    if (!meta.has(id)) meta.set(id, { sessions: 0, focusSecs: 0, carried: 0, lastMoveFrom: null });
    return meta.get(id);
  };
  for (const e of events) {
    if (!e.task_id) continue;
    if (ENDED.has(e.event_type)) { const m = get(e.task_id); m.sessions += 1; m.focusSecs += focusSecs(e); }
    else if (e.event_type === "task_carried_over") get(e.task_id).carried += 1;
    else if (e.event_type === "task_moved") get(e.task_id).lastMoveFrom = e.from_quadrant;
  }
  return meta;
}

// "1h 15m", "25m"
export function fmtDuration(mins) {
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60), m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

// { lead: "3 of 9 done. 1h 15m focused today", soft: "83% of it on Do first.", nudge }
export function daySummary({ tasks, events, date, isToday, now = Date.now() }) {
  const total = tasks.length;
  const done = tasks.filter((t) => t.done).length;
  const byQ = {};
  let secs = 0;
  for (const e of events) {
    if (e.local_date !== date || !ENDED.has(e.event_type)) continue;
    secs += focusSecs(e);
    byQ[e.quadrant] = (byQ[e.quadrant] || 0) + focusSecs(e);
  }
  const mins = Math.round(secs / 60);

  let lead, soft = null;
  if (total === 0) lead = isToday ? "Nothing planned yet" : "No tasks this day";
  else lead = `${done} of ${total} done`;

  if (mins > 0) {
    lead += `. ${fmtDuration(mins)} focused${isToday ? " today" : ""}`;
    const [topQ, topSecs] = Object.entries(byQ).sort((a, b) => b[1] - a[1])[0];
    const share = topSecs / secs;
    soft = share >= 0.5 ? `${Math.round(share * 100)}% of it on ${quadrantLabel(topQ)}.` : "spread across quadrants.";
  } else if (total > 0) {
    lead += ". No focus time yet";
  }

  // The nudge behind hypothesis 1: is the important-not-urgent work getting any attention?
  let nudge = null;
  if (isToday && tasks.some((t) => t.quadrant === "schedule" && !t.done)) {
    const last = [...events].reverse().find((e) => e.quadrant === "schedule" && (ENDED.has(e.event_type) || e.event_type === "task_completed"));
    if (!last) nudge = "Schedule hasn't had any focus time yet";
    else if (now - new Date(last.occurred_at) > 1.5 * DAY_MS) nudge = `Schedule hasn't had focus time since ${weekdayName(last.occurred_at)}`;
  }
  return { lead, soft, nudge };
}

// ── Patterns tab ──────────────────────────────────────────────
export function patterns(tasks, events) {
  // H1: where does focus time go?
  const focusByQ = Object.fromEntries(QUADRANTS.map((q) => [q.id, 0]));
  let totalFocus = 0, finished = 0, abandoned = 0;
  const byHour = Array(24).fill(0);
  for (const e of events) {
    if (!ENDED.has(e.event_type)) continue;
    const s = focusSecs(e);
    if (e.quadrant in focusByQ) focusByQ[e.quadrant] += s;
    totalFocus += s;
    if (e.event_type === "pomodoro_finished") finished += 1; else abandoned += 1;
    // attribute the session to the hour it started
    byHour[new Date(new Date(e.occurred_at) - s * 1000).getHours()] += s;
  }

  // H2: do "urgent" labels survive?
  const created = new Map();
  const firstDowngrade = new Map();
  for (const e of events) {
    if (e.event_type === "task_created" && isUrgent(e.quadrant) && !e.payload?.quadrant_inferred) created.set(e.task_id, e.occurred_at);
    if (e.event_type === "task_moved" && created.has(e.task_id) && !firstDowngrade.has(e.task_id)
        && isUrgent(e.from_quadrant) && !isUrgent(e.quadrant)) firstDowngrade.set(e.task_id, e.occurred_at);
  }
  const lags = [...firstDowngrade].map(([id, at]) => (new Date(at) - new Date(created.get(id))) / DAY_MS).sort((a, b) => a - b);
  const median = lags.length ? lags[Math.floor(lags.length / 2)] : null;

  // completion by the quadrant a task ended up in
  const completion = QUADRANTS.map((q) => {
    const ts = tasks.filter((t) => t.quadrant === q.id);
    return { id: q.id, label: q.label, done: ts.filter((t) => t.done).length, total: ts.length };
  });

  const days = new Set(events.map((e) => e.local_date));
  return {
    totalFocusMins: Math.round(totalFocus / 60),
    focusShare: QUADRANTS.map((q) => ({ id: q.id, label: q.label, mins: Math.round(focusByQ[q.id] / 60), share: totalFocus ? focusByQ[q.id] / totalFocus : 0 })),
    sessions: { finished, abandoned },
    byHour: byHour.map((s) => Math.round(s / 60)),
    urgent: { created: created.size, downgraded: lags.length, within3: lags.filter((d) => d <= 3).length, medianDays: median },
    completion,
    activeDays: days.size,
  };
}
