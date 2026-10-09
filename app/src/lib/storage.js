// Everything is saved in this browser's localStorage. Nothing is sent anywhere.
//
// Keys:
//   pm2_*        your real data (version 2 format)
//   pm2_demo_*   demo data, kept completely separate so it can't mix with yours
//   pm_*         the OLD version's data. Never modified or deleted.
//   pm_v1_backup a frozen copy of the old data, taken before the first conversion
import { makeEvent, newId, sortEvents, QUADRANT_IDS, POMODORO_SECS } from "./events";
import { localDate } from "./dates";

function read(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : fallback;
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    if (value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage full or blocked (private mode): the app keeps working in memory
  }
}

const keysFor = (mode) => {
  const p = mode === "demo" ? "pm2_demo_" : "pm2_";
  return { tasks: p + "tasks", events: p + "events", focus: p + "active_focus", carryAsked: p + "carry_asked" };
};

export const loadMode = () => (read("pm2_mode", "real") === "demo" ? "demo" : "real");
export const saveMode = (mode) => write("pm2_mode", mode);

export function loadData(mode) {
  if (mode === "real") migrateV1IfNeeded();
  const k = keysFor(mode);
  return { tasks: read(k.tasks, []), events: read(k.events, []) };
}

export function saveData(mode, { tasks, events }) {
  const k = keysFor(mode);
  write(k.tasks, tasks);
  write(k.events, events);
}

export const clearDemo = () => Object.values(keysFor("demo")).forEach((k) => write(k, null));

export const loadActiveFocus = (mode) => read(keysFor(mode).focus, null);
export const saveActiveFocus = (mode, focus) => write(keysFor(mode).focus, focus);

export const carryAskedOn = (mode) => read(keysFor(mode).carryAsked, null);
export const markCarryAsked = (mode, date) => write(keysFor(mode).carryAsked, date);

// Before an import replaces your data, keep the previous copy one step back.
export function backupBeforeImport(data) {
  write("pm2_pre_import_backup", { ...data, backed_up_at: new Date().toISOString() });
}

// ── One-time conversion from the old format ───────────────────
const V1_SEED_TEXTS = new Set([
  "Reply to urgent client email", "Plan next week's goals", "Fix printer jam", "Browse social media",
]);

function migrateV1IfNeeded() {
  if (localStorage.getItem("pm2_tasks") !== null) return; // already converted (or fresh v2 user)
  const v1Tasks = read("pm_tasks", null);
  if (!v1Tasks) return;
  const v1Sessions = read("pm_sessions", []);

  if (localStorage.getItem("pm_v1_backup") === null) {
    write("pm_v1_backup", {
      tasks: v1Tasks, sessions: v1Sessions, last_date: localStorage.getItem("pm_last_date"),
      backed_up_at: new Date().toISOString(),
    });
  }

  // The old version shipped four example tasks. Don't import those as real history.
  const onlyExamples = v1Sessions.length === 0 && v1Tasks.every((t) => V1_SEED_TEXTS.has(t.text));
  const { tasks, events } = onlyExamples ? { tasks: [], events: [] } : convertV1(v1Tasks, v1Sessions);
  saveData("real", { tasks, events });
  write("pm2_migrated_at", new Date().toISOString());
}

export function convertV1(v1Tasks, v1Sessions) {
  const tasks = v1Tasks.map((t) => {
    const created = t.created_at || new Date().toISOString();
    return {
      id: newId(), // old IDs changed on every reload, so they can't be trusted
      text: t.text,
      quadrant: QUADRANT_IDS.includes(t.quadrant) ? t.quadrant : "eliminate",
      done: !!t.done,
      date: t.date || localDate(new Date(created)),
      subtasks: (t.subtasks || []).map((s) => ({ id: newId(), text: s.text, done: !!s.done })),
      created_at: created,
      completed_at: t.done ? t.completed_at || null : null,
    };
  });

  const events = [];
  for (const t of tasks) {
    // quadrant_inferred: the old app didn't record moves, so we only know the latest quadrant.
    events.push(makeEvent("task_created", {
      task_id: t.id, quadrant: t.quadrant, occurred_at: t.created_at, source: "backfill",
      payload: { text: t.text, date: t.date, quadrant_inferred: true },
    }));
    if (t.completed_at) {
      events.push(makeEvent("task_completed", { task_id: t.id, quadrant: t.quadrant, occurred_at: t.completed_at, source: "backfill" }));
    }
  }

  // Old sessions pointed at task IDs that no longer exist; match them by task text instead.
  for (const s of v1Sessions) {
    if (!s.started_at || !s.ended_at) continue;
    const match = tasks.find((t) => t.text === s.task_text && t.quadrant === s.quadrant)
      || tasks.find((t) => t.text === s.task_text);
    const pomodoro_id = newId();
    const common = { task_id: match?.id ?? null, quadrant: s.quadrant ?? match?.quadrant ?? null, pomodoro_id, source: "backfill" };
    events.push(makeEvent("pomodoro_started", { ...common, occurred_at: s.started_at, payload: { planned_secs: POMODORO_SECS } }));
    const focused_secs = Math.round((s.duration_mins || 0) * 60);
    events.push(s.completed
      ? makeEvent("pomodoro_finished", { ...common, occurred_at: s.ended_at, payload: { focused_secs, planned_secs: POMODORO_SECS, early: false } })
      : makeEvent("pomodoro_abandoned", { ...common, occurred_at: s.ended_at, payload: { focused_secs, planned_secs: POMODORO_SECS, reason: "v1_paused_or_reset" } }));
  }

  return { tasks, events: sortEvents(events) };
}
