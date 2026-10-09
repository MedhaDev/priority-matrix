import { useCallback, useEffect, useState } from "react";
import { loadActiveFocus, saveActiveFocus } from "./storage";
import { makeEvent, newId, POMODORO_SECS } from "./events";

// The Pomodoro timer as a small state machine:
//   ready → (start) → running ⇄ paused → finished | abandoned
// Time is measured from timestamps, not by counting ticks, so it stays
// correct when a phone locks the screen. The session is also saved, so a
// reload (or iOS killing the app) doesn't lose it.
export function useFocus({ mode, tasks, log }) {
  const [active, setActive] = useState(() => loadActiveFocus(mode));
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => { saveActiveFocus(mode, active); }, [mode, active]);

  const quadrantOf = useCallback(
    (a) => tasks.find((t) => t.id === a.task_id)?.quadrant ?? a.quadrant,
    [tasks],
  );

  const event = useCallback((type, a, extra = {}) => makeEvent(type, {
    task_id: a.task_id, quadrant: quadrantOf(a), pomodoro_id: a.pomodoro_id, ...extra,
  }), [quadrantOf]);

  const end = useCallback((type, { at = Date.now(), ...payload } = {}) => {
    if (!active?.pomodoro_id) return;
    const focused_ms = active.acc_ms + (active.running_since ? at - active.running_since : 0);
    const focused_secs = Math.round(Math.min(focused_ms, active.planned_ms) / 1000);
    log([event(type, active, {
      occurred_at: new Date(at).toISOString(),
      payload: { focused_secs, planned_secs: active.planned_ms / 1000, ...payload },
    })]);
    if (type === "pomodoro_finished" && navigator.vibrate) navigator.vibrate([120, 80, 120]);
    setActive({ ...active, pomodoro_id: null, running_since: null, ended: { type, focused_secs } });
  }, [active, event, log]);

  // Tick while running; finish automatically when the time is up (even if
  // that moment passed while the app was in the background).
  useEffect(() => {
    if (!active?.running_since) return;
    const iv = setInterval(() => {
      const t = Date.now();
      if (active.acc_ms + (t - active.running_since) >= active.planned_ms) {
        end("pomodoro_finished", { at: active.running_since + (active.planned_ms - active.acc_ms), early: false });
      } else {
        setNow(t);
      }
    }, 250);
    return () => clearInterval(iv);
  }, [active, end]);

  const fresh = (task) => ({
    task_id: task.id, text: task.text, quadrant: task.quadrant,
    pomodoro_id: null, planned_ms: POMODORO_SECS * 1000, acc_ms: 0, running_since: null, started_at: null, ended: null,
  });

  const elapsed = active ? active.acc_ms + (active.running_since ? Math.max(0, now - active.running_since) : 0) : 0;

  return {
    active,
    status: !active ? "off" : active.ended ? "ended" : active.running_since ? "running" : active.pomodoro_id ? "paused" : "ready",
    remainingMs: active ? Math.max(0, active.planned_ms - elapsed) : 0,
    progress: active ? Math.min(1, elapsed / active.planned_ms) : 0,
    endsAt: active?.running_since ? new Date(active.running_since + active.planned_ms - active.acc_ms).toISOString() : null,

    open: (task) => { setNow(Date.now()); setActive(fresh(task)); },
    again: () => setActive((a) => fresh({ id: a.task_id, text: a.text, quadrant: a.quadrant })),
    start: () => {
      const t = Date.now();
      setNow(t);
      if (!active.pomodoro_id) {
        const next = { ...active, pomodoro_id: newId(), running_since: t, started_at: new Date(t).toISOString() };
        log([event("pomodoro_started", next, { payload: { planned_secs: active.planned_ms / 1000 } })]);
        setActive(next);
      } else {
        log([event("pomodoro_resumed", active)]);
        setActive({ ...active, running_since: t });
      }
    },
    pause: () => {
      const t = Date.now();
      log([event("pomodoro_paused", active)]);
      setActive({ ...active, acc_ms: active.acc_ms + (t - active.running_since), running_since: null });
    },
    finishEarly: () => end("pomodoro_finished", { early: true }),
    abandon: (reason = "gave_up") => end("pomodoro_abandoned", { reason }),
    // Leaving mid-session counts as abandoning it.
    close: () => {
      if (active?.pomodoro_id) end("pomodoro_abandoned", { reason: "exited" });
      setActive(null);
    },
  };
}
