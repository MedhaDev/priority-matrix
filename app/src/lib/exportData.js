import { SCHEMA_VERSION } from "./events";
import { localDate } from "./dates";

function download(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Full backup: restore it on another device with "import backup".
export function exportJSON({ tasks, events }) {
  const body = { app: "priority-matrix", schema_version: SCHEMA_VERSION, exported_at: new Date().toISOString(), tasks, events };
  download(`priority-matrix-backup-${localDate()}.json`, JSON.stringify(body, null, 2), "application/json");
}

// Flat event log for spreadsheets / pandas / loading into a database.
const COLUMNS = ["event_id", "schema_version", "event_type", "task_id", "quadrant", "from_quadrant", "pomodoro_id", "occurred_at", "local_date", "timezone", "source", "payload"];
const cell = (v) => {
  if (v == null) return "";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function exportEventsCSV(events) {
  const rows = [COLUMNS.join(","), ...events.map((e) => COLUMNS.map((c) => cell(e[c])).join(","))];
  download(`priority-matrix-events-${localDate()}.csv`, rows.join("\n"), "text/csv");
}

export async function readBackupFile(file) {
  const data = JSON.parse(await file.text());
  if (data.app !== "priority-matrix" || !Array.isArray(data.tasks) || !Array.isArray(data.events)) {
    throw new Error("That file isn't a Priority Matrix backup.");
  }
  return { tasks: data.tasks, events: data.events };
}
