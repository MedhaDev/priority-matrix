// @vitest-environment jsdom
// Cloud sync against an in-memory stand-in for Supabase. The fake returns
// data the way Postgres does (timestamps as "+00:00", jsonb keys reordered),
// so these tests also catch formats that would cause endless re-uploads.
import { act, renderHook, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const db = vi.hoisted(() => ({ rows: new Map(), fail: false, upserts: 0 }));

vi.mock("./exportData", () => ({ exportJSON: vi.fn() }));
vi.mock("./supabase", () => {
  const pgTime = (t) => (t == null ? null : new Date(t).toISOString().replace("Z", "+00:00"));
  const jsonb = (subtasks) => subtasks.map((s) => ({ id: s.id, done: s.done, text: s.text }));
  const result = (data) => (db.fail ? { data: null, error: { message: "network down" } } : { data, error: null });
  const save = (row) => db.rows.set(row.id, {
    ...db.rows.get(row.id), ...row,
    created_at: pgTime(row.created_at), completed_at: pgTime(row.completed_at), subtasks: jsonb(row.subtasks),
  });
  return {
    supabase: {
      auth: {
        getSession: async () => ({ data: { session: { user: { id: "user-1", email: "me@example.com" } } } }),
        onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
      },
      from: () => ({
        upsert: async (rows) => {
          if (db.fail) return result();
          db.upserts += 1;
          rows.forEach(save);
          return result(null);
        },
        update: (patch) => ({
          in: async (_col, ids) => {
            if (db.fail) return result();
            ids.forEach((id) => db.rows.has(id) && db.rows.set(id, { ...db.rows.get(id), deleted_at: pgTime(patch.deleted_at) }));
            return result(null);
          },
        }),
        select: () => {
          const query = {
            order: () => query,
            then: (ok, err) => Promise.resolve(result([...db.rows.values()].sort((a, b) => a.position - b.position))).then(ok, err),
          };
          return query;
        },
      }),
    },
  };
});

import { exportJSON } from "./exportData";
import { useCloudSync } from "./cloudSync";
import { addDays, localDate } from "./dates";

const TODAY = localDate();

const task = (id, text, extra = {}) => ({
  id, text, quadrant: "do", done: false, date: TODAY,
  subtasks: [{ id: `${id}-s`, text: "step", done: false }],
  created_at: "2026-10-26T09:00:00.000Z", completed_at: null, ...extra,
});

function setup(initial) {
  return renderHook(() => {
    const [tasks, setTasks] = useState(initial);
    const cloud = useCloudSync({ enabled: true, tasks, events: [], setTasks });
    return { tasks, setTasks, cloud };
  });
}
const synced = (result) => waitFor(() => expect(result.current.cloud.status).toBe("synced"));

beforeEach(() => {
  localStorage.clear();
  db.rows.clear();
  db.fail = false;
  db.upserts = 0;
  vi.mocked(exportJSON).mockClear();
});

describe("cloud sync", () => {
  it("uploads this device's tasks on first sign-in, after backing them up", async () => {
    const { result } = setup([task("a", "Write report"), task("b", "Call bank", { done: true, completed_at: "2026-10-26T10:00:00.000Z" })]);
    await synced(result);
    expect(db.rows.size).toBe(2);
    expect(db.rows.get("a")).toMatchObject({ user_id: "user-1", title: "Write report", status: "open", task_date: TODAY });
    expect(db.rows.get("b")).toMatchObject({ status: "done" });
    expect(JSON.parse(localStorage.getItem("pm2_pre_cloud_backup")).tasks).toHaveLength(2);
    expect(exportJSON).toHaveBeenCalledTimes(1);
  });

  it("doesn't re-upload tasks that came back from the database unchanged", async () => {
    const { result } = setup([task("a", "Write report")]);
    await synced(result);
    const before = db.upserts;
    await act(() => result.current.cloud.retryNow());
    await synced(result);
    expect(db.upserts).toBe(before);
  });

  it("saves edits and soft-deletes removed tasks, keeping the row", async () => {
    const { result } = setup([task("a", "Write report"), task("b", "Call bank")]);
    await synced(result);
    act(() => result.current.setTasks([{ ...result.current.tasks[0], text: "Write the report" }]));
    await waitFor(() => expect(db.rows.get("a").title).toBe("Write the report"));
    await waitFor(() => expect(db.rows.get("b").deleted_at).not.toBeNull());
    expect(db.rows.size).toBe(2);
  });

  it("keeps a failed save on the device and reports it, then retries", async () => {
    const { result } = setup([task("a", "Write report")]);
    await synced(result);
    db.fail = true;
    act(() => result.current.setTasks([...result.current.tasks, task("c", "New while offline")]));
    await waitFor(() => expect(result.current.cloud.status).toBe("error"));
    expect(result.current.cloud.pending).toBe(1);
    expect(result.current.cloud.error).toBe("network down");
    expect(result.current.tasks.map((t) => t.id)).toEqual(["a", "c"]);
    db.fail = false;
    await act(() => result.current.cloud.retryNow());
    await synced(result);
    expect(db.rows.get("c").title).toBe("New while offline");
  });

  it("merges changes made on another device", async () => {
    const { result } = setup([task("a", "Write report"), task("b", "Call bank")]);
    await synced(result);
    // Another device renames a, deletes b, and adds d.
    db.rows.set("a", { ...db.rows.get("a"), title: "Write report (phone)" });
    db.rows.set("b", { ...db.rows.get("b"), deleted_at: "2026-10-26T12:00:00+00:00" });
    db.rows.set("d", { ...db.rows.get("a"), id: "d", title: "Added on phone", position: 5 });
    await act(() => result.current.cloud.retryNow());
    await synced(result);
    expect(result.current.tasks.map((t) => t.text)).toEqual(["Write report (phone)", "Added on phone"]);
  });

  it("keeps an unsaved local edit over the cloud copy", async () => {
    const { result } = setup([task("a", "Write report")]);
    await synced(result);
    db.fail = true;
    act(() => result.current.setTasks([{ ...result.current.tasks[0], text: "Edited here" }]));
    await waitFor(() => expect(result.current.cloud.status).toBe("error"));
    db.fail = false;
    db.rows.set("a", { ...db.rows.get("a"), title: "Edited elsewhere" });
    await act(() => result.current.cloud.retryNow());
    await synced(result);
    expect(result.current.tasks[0].text).toBe("Edited here");
    expect(db.rows.get("a").title).toBe("Edited here");
  });

  it("uploads only the last 7 days; older tasks stay on the device", async () => {
    const { result } = setup([
      task("old", "From two weeks ago", { date: addDays(TODAY, -14) }),
      task("edge", "From exactly a week ago", { date: addDays(TODAY, -7) }),
      task("now", "Today"),
      task("next", "Tomorrow", { date: addDays(TODAY, 1) }),
    ]);
    await synced(result);
    expect([...db.rows.keys()].sort()).toEqual(["edge", "next", "now"]);
    expect(result.current.tasks.map((t) => t.id)).toEqual(["old", "edge", "now", "next"]);

    // Carrying the old task over to today makes it current, so it syncs.
    act(() => result.current.setTasks(result.current.tasks.map((t) => (t.id === "old" ? { ...t, date: TODAY } : t))));
    await waitFor(() => expect(db.rows.get("old")?.task_date).toBe(TODAY));
  });

  it("doesn't move one account's tasks into another account", async () => {
    localStorage.setItem("pm2_cloud_snapshot", JSON.stringify({ user_id: "someone-else", rows: { a: "x" } }));
    const { result } = setup([task("a", "Someone else's task")]);
    await synced(result);
    expect(db.rows.size).toBe(0);
    expect(result.current.tasks).toEqual([]);
  });
});
