# Event schema (v1)

Every action in the app is recorded as one **event**. The event log is the
contract between three parts of this project:

1. **The app** writes events (source: [`src/lib/events.js`](../app/src/lib/events.js)).
2. **Synthetic data** (`generator/`), used in the public repo for privacy, follows exactly this format.
3. **The dbt models** read only this format.

Change all three together, and bump `schema_version` for breaking changes.
The machine-checkable version is [`event.v1.schema.json`](event.v1.schema.json) (JSON Schema).

## Fields

| Field | Type | Notes |
|---|---|---|
| `event_id` | uuid | Unique per event. Lets loads be idempotent (safe to re-run). |
| `schema_version` | int | Currently `1`. |
| `event_type` | text | See below. |
| `task_id` | uuid | Stable for the task's whole life. Survives carry-over and deletion. |
| `quadrant` | text | `do` · `schedule` · `delegate` · `eliminate`. The task's quadrant **after** the event; for pomodoro events, the quadrant **while focusing**. |
| `from_quadrant` | text | Only on `task_moved`. |
| `pomodoro_id` | uuid | Groups the events of one focus session. |
| `payload` | json | Event-specific details (below). |
| `occurred_at` | timestamptz | Device clock, ISO 8601 UTC. |
| `local_date` | date | The user's local calendar day when it happened. |
| `timezone` | text | IANA name, e.g. `America/New_York`. |
| `source` | text | `app` (live), `backfill` (converted from the old v1 app), `demo` (in-app demo), `synthetic` (the generator). |

## Event types

| Event | Payload |
|---|---|
| `task_created` | `text`, `date` (the day it's planned for) · backfills add `quadrant_inferred: true` (v1 didn't record moves, so only the final quadrant is known) |
| `task_edited` | `old_text`, `new_text` |
| `task_moved` | — (`from_quadrant` → `quadrant`) |
| `task_completed` | optional `via: "subtasks"` |
| `task_reopened` | optional `via: "subtasks"` |
| `task_deleted` | `text`, `was_done` |
| `task_carried_over` | `from_date`, `to_date` |
| `pomodoro_started` | `planned_secs` |
| `pomodoro_paused` / `pomodoro_resumed` | — |
| `pomodoro_finished` | `focused_secs`, `planned_secs`, `early` |
| `pomodoro_abandoned` | `focused_secs`, `planned_secs`, `reason` (`gave_up` · `exited` · `v1_paused_or_reset`) |

`focused_secs` excludes paused time.

## Useful definitions (for the dbt layer)

These are the exact definitions used by the answer key (`generator/priority_sim/truth.py`); the dbt models must match them.

- **Focus time**: sum of `payload.focused_secs` on `pomodoro_finished` + `pomodoro_abandoned`, grouped by the event's `quadrant` (the task's quadrant during the session) and `local_date`. Hypothesis 1.
- **Urgent task**: a task whose `task_created` quadrant is `do` or `delegate`.
- **Downgrade**: an urgent task's **first** `task_moved` from an urgent quadrant (`do`, `delegate`) to a non-urgent one (`schedule`, `eliminate`). Urgent → urgent moves don't count. Hypothesis 2.
- **Within a few days**: downgrade `occurred_at` minus `task_created` `occurred_at` ≤ 72 hours.
- **Open next morning**: an urgent task with any event on a later `local_date` than its creation (finished-same-day tasks never get a chance to be downgraded, so report the rate both ways).
- **Carry count**: number of `task_carried_over` events per `task_id`.

## Example

```json
{
  "event_id": "5f0c1c1e-8a0e-4c5e-9d0b-2a7f3c1e9b10",
  "schema_version": 1,
  "event_type": "task_moved",
  "task_id": "b8a4e0b2-3c1d-4f6a-9e2b-7d5c4a3b2e1f",
  "quadrant": "schedule",
  "from_quadrant": "do",
  "pomodoro_id": null,
  "payload": {},
  "occurred_at": "2026-10-08T13:02:11.000Z",
  "local_date": "2026-10-08",
  "timezone": "America/New_York",
  "source": "app"
}
```
