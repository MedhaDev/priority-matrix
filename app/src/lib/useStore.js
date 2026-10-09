import { useCallback, useEffect, useMemo, useState } from "react";
import { loadData, saveData } from "./storage";
import { makeEvent, newId } from "./events";

// Every change to a task goes through here, so each one is saved AND
// recorded as an event in the same step. The log can't drift from the UI.
export function useStore(mode) {
  const [data, setData] = useState(() => loadData(mode));

  useEffect(() => { saveData(mode, data); }, [mode, data]);

  // fn(tasks) returns { tasks?, events? } or null for "no change"
  const apply = useCallback((fn) => setData((prev) => {
    const res = fn(prev.tasks);
    if (!res) return prev;
    return {
      tasks: res.tasks ?? prev.tasks,
      events: res.events?.length ? [...prev.events, ...res.events] : prev.events,
    };
  }), []);

  const actions = useMemo(() => {
    const update = (tasks, id, patch) => tasks.map((t) => (t.id === id ? { ...t, ...patch } : t));
    const find = (tasks, id) => tasks.find((t) => t.id === id);

    return {
      add(text, quadrant, date) {
        apply((tasks) => {
          const created_at = new Date().toISOString();
          const task = { id: newId(), text, quadrant, done: false, date, subtasks: [], created_at, completed_at: null };
          return {
            tasks: [...tasks, task],
            events: [makeEvent("task_created", { task_id: task.id, quadrant, occurred_at: created_at, payload: { text, date } })],
          };
        });
      },

      edit(id, text) {
        apply((tasks) => {
          const t = find(tasks, id);
          if (!t || t.text === text) return null;
          return {
            tasks: update(tasks, id, { text }),
            events: [makeEvent("task_edited", { task_id: id, quadrant: t.quadrant, payload: { old_text: t.text, new_text: text } })],
          };
        });
      },

      // Moving within the same quadrant just reorders (no event).
      move(id, to, beforeId = null) {
        apply((tasks) => {
          const t = find(tasks, id);
          if (!t || id === beforeId) return null;
          const rest = tasks.filter((x) => x.id !== id);
          let idx = beforeId ? rest.findIndex((x) => x.id === beforeId) : -1;
          if (idx === -1) idx = rest.length;
          rest.splice(idx, 0, { ...t, quadrant: to });
          return {
            tasks: rest,
            events: t.quadrant === to ? [] : [makeEvent("task_moved", { task_id: id, from_quadrant: t.quadrant, quadrant: to })],
          };
        });
      },

      toggle(id) {
        apply((tasks) => {
          const t = find(tasks, id);
          if (!t) return null;
          const now = new Date().toISOString();
          return {
            tasks: update(tasks, id, { done: !t.done, completed_at: t.done ? null : now }),
            events: [makeEvent(t.done ? "task_reopened" : "task_completed", { task_id: id, quadrant: t.quadrant, occurred_at: now })],
          };
        });
      },

      remove(id) {
        apply((tasks) => {
          const t = find(tasks, id);
          if (!t) return null;
          return {
            tasks: tasks.filter((x) => x.id !== id),
            events: [makeEvent("task_deleted", { task_id: id, quadrant: t.quadrant, payload: { text: t.text, was_done: t.done } })],
          };
        });
      },

      // Carry-over MOVES the task to another day (the old version made copies,
      // which split one task's history into several unrelated tasks).
      carry(ids, toDate) {
        apply((tasks) => {
          const events = [];
          const next = tasks.map((t) => {
            if (!ids.includes(t.id) || t.date === toDate) return t;
            events.push(makeEvent("task_carried_over", { task_id: t.id, quadrant: t.quadrant, payload: { from_date: t.date, to_date: toDate } }));
            return { ...t, date: toDate };
          });
          return events.length ? { tasks: next, events } : null;
        });
      },

      // Ticking the last subtask completes the task; unticking one reopens it.
      setSubtasks(id, subtasks) {
        apply((tasks) => {
          const t = find(tasks, id);
          if (!t) return null;
          const allDone = subtasks.length > 0 && subtasks.every((s) => s.done);
          const wasAllDone = t.subtasks.length > 0 && t.subtasks.every((s) => s.done);
          const now = new Date().toISOString();
          if (allDone && !t.done) {
            return {
              tasks: update(tasks, id, { subtasks, done: true, completed_at: now }),
              events: [makeEvent("task_completed", { task_id: id, quadrant: t.quadrant, occurred_at: now, payload: { via: "subtasks" } })],
            };
          }
          if (t.done && wasAllDone && !allDone) {
            return {
              tasks: update(tasks, id, { subtasks, done: false, completed_at: null }),
              events: [makeEvent("task_reopened", { task_id: id, quadrant: t.quadrant, occurred_at: now, payload: { via: "subtasks" } })],
            };
          }
          return { tasks: update(tasks, id, { subtasks }) };
        });
      },

      // For focus-session events, which don't change any task.
      log(events) { apply(() => ({ events })); },

      replace(next) { setData(next); },
    };
  }, [apply]);

  return { tasks: data.tasks, events: data.events, actions };
}
