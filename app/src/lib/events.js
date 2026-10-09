// ─────────────────────────────────────────────────────────────
// The event format: the contract between this app, the synthetic
// data generator (Phase 2) and the dbt models (Phase 3).
// Documented in docs/event-schema.md. Change both together.
// ─────────────────────────────────────────────────────────────
import { localDate, timezone } from "./dates";

export const SCHEMA_VERSION = 1;

export const QUADRANTS = [
  { id: "do",        label: "Do first",  sub: "Urgent · Important" },
  { id: "schedule",  label: "Schedule",  sub: "Important" },
  { id: "delegate",  label: "Delegate",  sub: "Urgent" },
  { id: "eliminate", label: "Eliminate", sub: "Neither" },
];
export const QUADRANT_IDS = QUADRANTS.map((q) => q.id);
export const quadrantLabel = (id) => QUADRANTS.find((q) => q.id === id)?.label ?? id;
export const isUrgent = (q) => q === "do" || q === "delegate";

export const quadrantFor = (urgent, important) =>
  urgent && important ? "do" : important ? "schedule" : urgent ? "delegate" : "eliminate";

export const EVENT_TYPES = [
  "task_created",       // payload: { text, date }
  "task_edited",        // payload: { old_text, new_text }
  "task_moved",         // from_quadrant → quadrant
  "task_completed",
  "task_reopened",
  "task_deleted",
  "task_carried_over",  // payload: { from_date, to_date }
  "pomodoro_started",   // payload: { planned_secs }
  "pomodoro_paused",
  "pomodoro_resumed",
  "pomodoro_finished",  // payload: { focused_secs, planned_secs, early }
  "pomodoro_abandoned", // payload: { focused_secs, planned_secs, reason }
];

export const POMODORO_SECS = 25 * 60;

// crypto.randomUUID only exists on https/localhost; fall back for LAN testing.
export function newId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function makeEvent(event_type, {
  task_id = null,
  quadrant = null,        // quadrant AFTER the event (for pomodoros: the task's quadrant while focusing)
  from_quadrant = null,   // only for task_moved
  pomodoro_id = null,
  payload = {},
  occurred_at = new Date().toISOString(),
  source = "app",         // "app" | "backfill" (imported from the old version) | "demo"
} = {}) {
  if (!EVENT_TYPES.includes(event_type)) throw new Error(`Unknown event type: ${event_type}`);
  return {
    event_id: newId(),
    schema_version: SCHEMA_VERSION,
    event_type,
    task_id,
    quadrant,
    from_quadrant,
    pomodoro_id,
    payload,
    occurred_at,
    local_date: localDate(new Date(occurred_at)),
    timezone: timezone(),
    source,
  };
}

const byTime = (a, b) => (a.occurred_at < b.occurred_at ? -1 : a.occurred_at > b.occurred_at ? 1 : 0);
export const sortEvents = (events) => [...events].sort(byTime);

// Rebuild current task state purely from events. Used for demo data, and a
// handy proof that the event log alone is enough to reconstruct the app.
export function replayEvents(events) {
  const tasks = new Map();
  for (const e of sortEvents(events)) {
    const t = tasks.get(e.task_id);
    switch (e.event_type) {
      case "task_created":
        tasks.set(e.task_id, {
          id: e.task_id, text: e.payload.text, quadrant: e.quadrant, done: false,
          date: e.payload.date ?? e.local_date, subtasks: [], created_at: e.occurred_at, completed_at: null,
        });
        break;
      case "task_edited":    if (t) t.text = e.payload.new_text; break;
      case "task_moved":     if (t) t.quadrant = e.quadrant; break;
      case "task_completed": if (t) { t.done = true; t.completed_at = e.occurred_at; } break;
      case "task_reopened":  if (t) { t.done = false; t.completed_at = null; } break;
      case "task_carried_over": if (t) t.date = e.payload.to_date; break;
      case "task_deleted":   tasks.delete(e.task_id); break;
      default: break;
    }
  }
  return [...tasks.values()];
}
