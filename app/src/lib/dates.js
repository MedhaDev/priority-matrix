// All dates in the app are LOCAL calendar days ("YYYY-MM-DD"), never UTC.
// (The old version used toISOString(), which flips to tomorrow in the evening.)

const pad = (n) => String(n).padStart(2, "0");

export function localDate(d = new Date()) {
  const x = d instanceof Date ? d : new Date(d);
  return `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}`;
}

// Noon avoids daylight-saving edge cases when doing day arithmetic.
const atNoon = (dateStr) => new Date(dateStr + "T12:00:00");

export function addDays(dateStr, n) {
  const d = atNoon(dateStr);
  d.setDate(d.getDate() + n);
  return localDate(d);
}

export const daysBetween = (a, b) => Math.round((atNoon(b) - atNoon(a)) / 86400000);

// "Thu · Oct 08"
export function fmtDay(dateStr) {
  const d = atNoon(dateStr);
  const wd = d.toLocaleDateString("en-US", { weekday: "short" });
  const mo = d.toLocaleDateString("en-US", { month: "short" });
  return `${wd} · ${mo} ${pad(d.getDate())}`;
}

// "Monday"
export const weekdayName = (iso) => new Date(iso).toLocaleDateString("en-US", { weekday: "long" });

// "9:14am"
export const fmtTime = (iso) =>
  new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).replace(" ", "").toLowerCase();

export const timezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;
