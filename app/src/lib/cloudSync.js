import { useCallback, useEffect, useRef, useState } from "react";
import { supabase } from "./supabase";
import { exportJSON } from "./exportData";
import { addDays, localDate } from "./dates";

// Cloud sync for tasks (real mode, signed in).
//
// The device keeps its own copy, so the app stays instant and works offline.
// Supabase is the shared copy (what Claude reads). A snapshot of what the
// cloud last confirmed is kept per device; any task that differs from it is a
// change still to be saved. Nothing is marked saved until Supabase confirms,
// and a failed save stays pending (and visible) until it goes through.
//
// Events (the focus/behavior log) stay on the device; only tasks sync.
//
// Only recent tasks go to the cloud: on a device's first sign-in, tasks
// dated in the last 7 days or later are uploaded. Older tasks stay on the
// device and are never sent (unless one is carried over to a recent day).

const SNAPSHOT_KEY = "pm2_cloud_snapshot";   // { user_id, since, rows: { [task id]: serialized } }
const HISTORY_DAYS = 7;
const BACKUP_KEY = "pm2_pre_cloud_backup";   // frozen copy of local data before the first sync
const RETRY_SECS = [5, 15, 30, 60];

function read(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}
function write(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage full: sync still works in memory */ }
}

const iso = (t) => (t ? new Date(t).toISOString() : null);

// Local task ↔ database row.
export function toRow(t, position, userId) {
  return {
    id: t.id,
    user_id: userId,
    title: t.text,
    quadrant: t.quadrant,
    status: t.done ? "done" : "open",
    task_date: t.date,
    subtasks: (t.subtasks ?? []).map((s) => ({ id: s.id, text: s.text, done: !!s.done })),
    position,
    created_at: iso(t.created_at) ?? new Date().toISOString(),
    completed_at: t.done ? iso(t.completed_at) : null,
    deleted_at: null,
  };
}

export function fromRow(r) {
  return {
    id: r.id,
    text: r.title,
    quadrant: r.quadrant,
    done: r.status === "done",
    date: r.task_date,
    subtasks: (r.subtasks ?? []).map((s) => ({ id: s.id, text: s.text, done: !!s.done })),
    created_at: iso(r.created_at),
    completed_at: iso(r.completed_at),
  };
}

// Everything that's saved, in a fixed order, so the same task always
// compares equal however it came back from the database.
const ser = (t, position) => JSON.stringify([
  t.text, t.quadrant, !!t.done, t.date,
  (t.subtasks ?? []).map((s) => [s.id, s.text, !!s.done]),
  position, iso(t.created_at), t.done ? iso(t.completed_at) : null,
]);

// What differs between this device and the last state the cloud confirmed.
// Tasks older than `since` that were never uploaded stay on the device.
function changesOf(tasks, rows, since = "") {
  const seen = new Set();
  const upserts = [];
  tasks.forEach((t, i) => {
    seen.add(t.id);
    if (rows[t.id] === undefined && t.date < since) return;
    const s = ser(t, i);
    if (rows[t.id] !== s) upserts.push({ t, i, s });
  });
  const deletes = Object.keys(rows).filter((id) => !seen.has(id));
  return { upserts, deletes };
}

export function useCloudSync({ enabled, tasks, events, setTasks }) {
  const [session, setSession] = useState(null);
  const [state, setState] = useState({ status: "idle", pending: 0, error: null });

  const tasksRef = useRef(tasks);
  const eventsRef = useRef(events);
  useEffect(() => { tasksRef.current = tasks; eventsRef.current = events; });

  const snapRef = useRef({ user_id: null, since: "", rows: {} });
  const queue = useRef(Promise.resolve());
  const retry = useRef({ timer: null, attempt: 0 });
  const debounce = useRef(null);

  const userId = session?.user?.id ?? null;
  const active = !!supabase && enabled && !!userId;

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  // Run sync steps one at a time, so a pull never overlaps a save.
  const enqueue = useCallback((fn) => {
    queue.current = queue.current.then(fn).catch(() => {});
    return queue.current;
  }, []);

  const fail = useCallback((err, flushLater) => {
    const { upserts, deletes } = changesOf(tasksRef.current, snapRef.current.rows, snapRef.current.since);
    const offline = typeof navigator !== "undefined" && navigator.onLine === false;
    setState({ status: offline ? "offline" : "error", pending: upserts.length + deletes.length, error: err?.message ?? String(err) });
    clearTimeout(retry.current.timer);
    const secs = RETRY_SECS[Math.min(retry.current.attempt, RETRY_SECS.length - 1)];
    retry.current.attempt += 1;
    retry.current.timer = setTimeout(flushLater, secs * 1000);
  }, []);

  const flush = useCallback(() => enqueue(async () => {
    if (!active) return;
    const rows = snapRef.current.rows;
    try {
      for (;;) {
        const { upserts, deletes } = changesOf(tasksRef.current, rows, snapRef.current.since);
        if (!upserts.length && !deletes.length) break;
        if (navigator.onLine === false) throw new Error("offline");
        setState((s) => ({ ...s, status: "syncing", pending: upserts.length + deletes.length }));
        if (upserts.length) {
          const { error } = await supabase.from("tasks").upsert(upserts.map((u) => toRow(u.t, u.i, userId)), { onConflict: "id" });
          if (error) throw error;
          upserts.forEach((u) => { rows[u.t.id] = u.s; });
        }
        if (deletes.length) {
          // Soft delete: the row stays (with deleted_at) so history isn't lost.
          const { error } = await supabase.from("tasks").update({ deleted_at: new Date().toISOString() }).in("id", deletes);
          if (error) throw error;
          deletes.forEach((id) => { delete rows[id]; });
        }
        write(SNAPSHOT_KEY, snapRef.current);
      }
      clearTimeout(retry.current.timer);
      retry.current.attempt = 0;
      setState({ status: "synced", pending: 0, error: null });
    } catch (err) {
      write(SNAPSHOT_KEY, snapRef.current);
      fail(err, () => flush());
    }
  }), [active, userId, enqueue, fail]);

  // Bring in the cloud copy and merge it with this device's copy. A task
  // changed here but not yet saved always wins; a task this device has never
  // saved is uploaded, never dropped.
  const pull = useCallback(() => enqueue(async () => {
    if (!active) return;
    setState((s) => ({ ...s, status: "syncing" }));
    const { data, error } = await supabase.from("tasks").select("*").order("position").order("created_at");
    if (error) { fail(error, () => pull().then(() => flush())); return; }

    const known = snapRef.current.rows;
    const local = new Map(tasksRef.current.map((t, i) => [t.id, { t, i }]));
    const edited = (id) => {
      const l = local.get(id);
      return l && known[id] !== undefined && ser(l.t, l.i) !== known[id];
    };
    const out = [];
    const rows = {};
    for (const r of data.filter((x) => !x.deleted_at)) {
      const cloud = fromRow(r);
      rows[r.id] = ser(cloud, r.position);
      const l = local.get(r.id);
      out.push(edited(r.id) ? { task: l.t, pos: l.i } : { task: cloud, pos: r.position });
    }
    for (const [id, { t, i }] of local) {
      if (rows[id] !== undefined) continue;
      if (known[id] !== undefined && !edited(id)) continue; // deleted on another device
      out.push({ task: t, pos: i });
    }
    out.sort((a, b) => a.pos - b.pos);
    snapRef.current = { ...snapRef.current, user_id: userId, rows };
    write(SNAPSHOT_KEY, snapRef.current);
    const next = out.map((o) => o.task);
    tasksRef.current = next;
    setTasks(next);
  }), [active, userId, enqueue, fail, flush, setTasks]);

  // Signing in on this device.
  useEffect(() => {
    if (!active) return;
    const stored = read(SNAPSHOT_KEY);
    if (stored?.user_id === userId) {
      snapRef.current = stored;
    } else {
      // First sync on this device: keep a frozen copy, and download a backup file.
      const data = { tasks: tasksRef.current, events: eventsRef.current };
      if (read(BACKUP_KEY) === null) write(BACKUP_KEY, { ...data, backed_up_at: new Date().toISOString() });
      if (data.tasks.length) exportJSON(data);
      // Tasks synced to a different account before must not move into this one.
      if (stored?.user_id) { tasksRef.current = []; setTasks([]); }
      snapRef.current = { user_id: userId, since: addDays(localDate(), -HISTORY_DAYS), rows: {} };
    }
    pull().then(() => flush());
  }, [active, userId, pull, flush, setTasks]);

  // Save shortly after each change.
  useEffect(() => {
    if (!active) return;
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => flush(), 400);
    return () => clearTimeout(debounce.current);
  }, [active, tasks, flush]);

  // Catch up when the app comes back online or to the foreground.
  useEffect(() => {
    if (!active) return;
    const pendingRetry = retry.current;
    const refresh = () => {
      if (document.visibilityState === "hidden") return;
      pull().then(() => flush());
    };
    window.addEventListener("online", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.removeEventListener("online", refresh);
      document.removeEventListener("visibilitychange", refresh);
      clearTimeout(pendingRetry.timer);
    };
  }, [active, pull, flush]);

  const signIn = (email, password) => supabase.auth.signInWithPassword({ email, password });
  const signUp = (email, password) => supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin } });
  const signOut = () => supabase.auth.signOut();

  return {
    available: !!supabase,
    user: session?.user ?? null,
    active,
    ...state,
    retryNow: () => { retry.current.attempt = 0; pull().then(() => flush()); },
    signIn, signUp, signOut,
  };
}

// One-line sync status for the footer and account dialog.
export function statusLine(cloud) {
  if (!cloud.active) return "Saved on this device";
  if (cloud.status === "syncing") return "Saving…";
  if (cloud.status === "offline") return `Offline · ${cloud.pending} to sync`;
  if (cloud.status === "error") return `Not saved · ${cloud.pending} pending`;
  return "Synced";
}
