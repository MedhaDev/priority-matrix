// Demo data for visitors: a simulated person, NOT anyone's real data.
// The habits below are planted on purpose so the Patterns tab (and later
// the dbt models) have something true to find.
import { makeEvent, newId, replayEvents, sortEvents, isUrgent, POMODORO_SECS } from "./events";
import { localDate, addDays, daysBetween } from "./dates";
import { loadMode, saveData, saveMode } from "./storage";

export const PERSONA = {
  days: 28,
  newTasksPerDay: { weekday: [3, 6], weekend: [1, 3] },
  // Over-labels things as urgent.
  createMix: { do: 0.38, schedule: 0.3, delegate: 0.17, eliminate: 0.15 },
  // Hypothesis 2: each morning, an urgent task has this chance of losing its urgency.
  morningDowngradeChance: 0.4,
  // Hypothesis 1: focus time goes mostly to "do first".
  focusMix: { do: 0.66, schedule: 0.14, delegate: 0.12, eliminate: 0.08 },
  pomodoros: { weekday: [3, 6], weekend: [0, 2] },
  abandonChance: { morning: 0.12, afternoon: 0.35 }, // post-lunch slump
  pauseChance: 0.15,
  completeAfterFocusChance: 0.35,
  eveningCompleteChance: { do: 0.4, schedule: 0.12, delegate: 0.35, eliminate: 0.25 },
  dropAfterDays: 5, // stale tasks eventually get deleted
};

const TEXTS = {
  do: ["Fix broken survey export", "Send numbers to finance", "Prep slides for 2pm review", "Reply to grant officer",
    "Patch the dashboard filter bug", "Submit conference abstract", "Respond to data request from partners", "Renew parking permit",
    "Finish cohort QA checks", "Call landlord about the leak"],
  schedule: ["Read dbt docs: incremental models", "Draft portfolio case study", "Plan next quarter's learning goals", "Refactor cleaning pipeline",
    "Write tests for the ingest script", "Book annual physical", "Outline blog post on Airflow", "Learn window functions properly",
    "Set up a budget spreadsheet", "Research PhD programs"],
  delegate: ["Book a room for the meetup", "Ask IT about database access", "Order team lunch", "Forward invoice to admin",
    "Schedule the vendor demo", "Get building access card fixed", "Collect RSVPs for the workshop"],
  eliminate: ["Reorganize Notion (again)", "Tweak terminal colors", "Read every unread newsletter", "Rewatch conference talk",
    "Clean up old screenshots", "Compare note-taking apps", "Rearrange the desk"],
};

function mulberry32(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function generateDemo({ seed = 7, now = new Date() } = {}) {
  // Before lunch, let the simulated day run to 11:30 so visitors always see a lively "today".
  const lateMorning = new Date(now); lateMorning.setHours(11, 30, 0, 0);
  const cutoff = now < lateMorning ? lateMorning : now;
  const r = mulberry32(seed);
  const between = ([a, b]) => a + Math.floor(r() * (b - a + 1));
  const pick = (arr) => arr[Math.floor(r() * arr.length)];
  const weighted = (weights) => {
    let x = r() * Object.values(weights).reduce((s, w) => s + w, 0);
    for (const [k, w] of Object.entries(weights)) if ((x -= w) < 0) return k;
    return Object.keys(weights)[0];
  };

  const events = [];
  const open = new Map(); // task_id → { quadrant, date, createdDay, text }
  const emit = (type, when, fields) => {
    if (when <= cutoff) events.push(makeEvent(type, { ...fields, occurred_at: when.toISOString(), source: "demo" }));
  };
  const at = (day, h, m) => {
    const d = new Date(day + "T00:00:00");
    d.setHours(h, m, Math.floor(r() * 60), 0);
    return d;
  };
  const plusMin = (d, m) => new Date(d.getTime() + m * 60000);

  const today = localDate(now);
  for (let i = PERSONA.days - 1; i >= 0; i--) {
    const day = addDays(today, -i);
    const weekend = [0, 6].includes(new Date(day + "T12:00:00").getDay());
    let clock = at(day, 8, 0);

    // 1. Morning: carry yesterday's leftovers forward, drop the stale ones.
    for (const [id, t] of open) {
      if (t.date >= day) continue;
      clock = plusMin(clock, 1);
      if (daysBetween(t.createdDay, day) > PERSONA.dropAfterDays && r() < 0.6) {
        emit("task_deleted", clock, { task_id: id, quadrant: t.quadrant });
        open.delete(id);
      } else {
        emit("task_carried_over", clock, { task_id: id, quadrant: t.quadrant, payload: { from_date: t.date, to_date: day } });
        t.date = day;
      }
    }

    // 2. New tasks (with a bias toward calling things urgent).
    clock = at(day, 8, 15);
    const n = between(weekend ? PERSONA.newTasksPerDay.weekend : PERSONA.newTasksPerDay.weekday);
    for (let j = 0; j < n; j++) {
      const quadrant = weighted(PERSONA.createMix);
      const taken = new Set([...open.values()].map((t) => t.text));
      const free = TEXTS[quadrant].filter((x) => !taken.has(x));
      if (!free.length) continue; // every idea in this pile is already on the list
      const text = pick(free);
      const id = newId();
      clock = plusMin(clock, between([2, 6]));
      emit("task_created", clock, { task_id: id, quadrant, payload: { text, date: day } });
      open.set(id, { quadrant, date: day, createdDay: day, text });
    }

    // 3. Morning re-triage: older "urgent" tasks quietly lose their urgency.
    clock = at(day, 8, 50);
    for (const [id, t] of open) {
      if (t.createdDay === day || !isUrgent(t.quadrant) || r() >= PERSONA.morningDowngradeChance) continue;
      const to = t.quadrant === "do" ? (r() < 0.8 ? "schedule" : "eliminate") : (r() < 0.7 ? "eliminate" : "schedule");
      clock = plusMin(clock, 1);
      emit("task_moved", clock, { task_id: id, from_quadrant: t.quadrant, quadrant: to });
      t.quadrant = to;
    }

    // 4. Focus sessions.
    let start = at(day, 9, between([0, 40]));
    const sessions = between(weekend ? PERSONA.pomodoros.weekend : PERSONA.pomodoros.weekday);
    for (let s = 0; s < sessions && open.size; s++) {
      if (start.getHours() === 12) start = at(day, 13, between([20, 50]));
      if (start.getHours() >= 17 && start.getMinutes() > 30) break;
      const wanted = weighted(PERSONA.focusMix);
      const pool = [...open].filter(([, t]) => t.quadrant === wanted);
      const [task_id, t] = pick(pool.length ? pool : [...open]);
      const pomodoro_id = newId();
      const fields = { task_id, quadrant: t.quadrant, pomodoro_id };
      const abandon = r() < (start.getHours() < 12 ? PERSONA.abandonChance.morning : PERSONA.abandonChance.afternoon);
      const focusedMin = abandon ? between([4, 20]) : 25;

      emit("pomodoro_started", start, { ...fields, payload: { planned_secs: POMODORO_SECS } });
      let end = plusMin(start, focusedMin);
      if (r() < PERSONA.pauseChance && focusedMin > 8) {
        const pauseAt = plusMin(start, Math.floor(focusedMin / 2));
        const gap = between([2, 6]);
        emit("pomodoro_paused", pauseAt, fields);
        emit("pomodoro_resumed", plusMin(pauseAt, gap), fields);
        end = plusMin(end, gap);
      }
      emit(abandon ? "pomodoro_abandoned" : "pomodoro_finished", end, {
        ...fields,
        payload: abandon
          ? { focused_secs: focusedMin * 60, planned_secs: POMODORO_SECS, reason: "gave_up" }
          : { focused_secs: focusedMin * 60, planned_secs: POMODORO_SECS, early: false },
      });
      if (!abandon && r() < PERSONA.completeAfterFocusChance) {
        emit("task_completed", plusMin(end, 1), { task_id, quadrant: t.quadrant });
        open.delete(task_id);
      }
      start = plusMin(end, between([5, 25]));
    }

    // 5. Evening sweep: tick off a few more.
    clock = at(day, 18, 30);
    for (const [id, t] of open) {
      if (r() >= PERSONA.eveningCompleteChance[t.quadrant]) continue;
      clock = plusMin(clock, between([1, 4]));
      emit("task_completed", clock, { task_id: id, quadrant: t.quadrant });
      open.delete(id);
    }
  }

  const sorted = sortEvents(events);
  return { tasks: replayEvents(sorted), events: sorted };
}

// A link ending in ?demo opens the app straight into demo mode (used for the
// README's "Try the demo" link). Runs once, before the app renders.
export function openDemoFromLink() {
  const params = new URLSearchParams(window.location.search);
  if (!params.has("demo")) return;
  if (loadMode() !== "demo") {
    saveData("demo", generateDemo());
    saveMode("demo");
  }
  params.delete("demo");
  const query = params.toString();
  history.replaceState(null, "", window.location.pathname + (query ? `?${query}` : "") + window.location.hash);
}
