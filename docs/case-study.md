# Priority Matrix: a to-do app that studies how I actually prioritize

**Role:** solo: product, design, data engineering, analytics
**Stack:** React PWA · Python · DuckDB / Postgres (Supabase) · dbt · Airflow · GitHub Actions · Tableau Public
**Code:** [github.com/MedhaDev/priority-matrix](https://github.com/MedhaDev/priority-matrix)

## The question

I sort my work with an Eisenhower Matrix (urgent × important) and focus with 25-minute
Pomodoro sessions. I had two suspicions about myself:

1. **Most of my focus goes to urgent-important work, at the expense of important-not-urgent work.**
2. **Things I label "urgent" often stop being urgent within a few days.**

Gut feeling can't settle those. Data can, if the app records the right things.

## Product: make the app record behavior, not just state

The original app only stored each task's *current* state: a task moved from Do first to
Schedule simply had a new quadrant, and the history was gone. I redesigned it so **every
action is an event**: created, moved (from → to), completed, carried over, and every focus
session started, paused, finished or abandoned. The event format is a written contract
([JSON Schema](../contracts/event.v1.schema.json)) shared by the app, the data generator and
the warehouse.

Product decisions that came out of thinking about the data:

- **Private by design.** No accounts, no server. My real data stays on my phone (installable
  PWA, works offline); it leaves only if I export it.
- **Carry-over moves a task instead of copying it.** Copies split one task's history into
  several unrelated tasks, which would have made hypothesis 2 unmeasurable.
- **Focus time is measured from timestamps,** not a ticking counter, so it's right even when
  the phone sleeps or the OS kills the app mid-session.
- **Local dates, not UTC.** Otherwise evening work lands on tomorrow.

## Data: a simulated me, with known answers

Waiting months for real data and publishing my own life weren't options, so I built a
**persona generator**: a day-by-day simulation of my routine (4–7 new tasks on workdays,
scattered focus between requests, side projects on weekends). Every setting is labeled as
something I know about myself, a planted hypothesis, or an assumption to correct.

Two things make it more than fake data:

- **Planted truth.** The hypotheses are built in on purpose, and the generator writes an
  **answer key** computed from what actually happened. The pipeline is then tested against it.
- **Realistic mess, on purpose and counted.** Duplicate uploads, events arriving days late,
  lost events, timestamps without a time zone, malformed rows from an "old app version".
  Every injected problem is listed with its event ID.

## Engineering: pipeline

```
generator ─► daily JSONL files (by arrival day) ─► raw.events ─► dbt ─► marts ─► Tableau / HTML
   Python          idempotent per day             DuckDB / Postgres     tested    CSV export
                     └──────────────── orchestrated daily by Airflow; CI on every PR ───────┘
```

- **Staging repairs what can be repaired** (timestamps without an offset → interpreted in the
  event's time zone), **quarantines what can't** (kept, never silently dropped), dedupes on
  `event_id`, and loads **incrementally with a 3-day lookback** for late and backfilled files.
- **Tests at every layer:** 80 Python tests (including 18 story invariants, each proven to fire
  by breaking a clean log on purpose); 54 dbt tests mirroring those invariants in SQL; and
  **reconciliation tests** that compare dbt's output with the answer key row by row.
  I tampered with the answer key by 60 seconds to confirm the build fails.
- **Same SQL on two engines.** Small cross-database macros let the models run on DuckDB (local,
  CI, Airflow) and Postgres 16 (the engine behind Supabase). Testing on both caught a real
  portability bug (`max()` over booleans works in DuckDB, not Postgres).
- **Idempotent and reproducible.** Each event's fate depends only on its own ID, so a day's
  file is byte-identical whether generated alone or in a full run. Loading days one at a time,
  out of order, gives exactly the same tables as a full rebuild.

## What the data says (simulated me, Jun 10 – Oct 8)

**Hypothesis 1, confirmed, and stronger than it first looked.** Do first gets **52% of focus
time**, but it's only **14% of the to-do list** (task-days): **3.6× its share**. Schedule is
**55% of the list** but gets **28% of focus** (0.5×).

The interesting part: I planted "pick Do first 66% of the time", and the raw focus share came
out at only 52%. When Do first is empty, focus spills into whatever's open, mostly the
Schedule backlog. **Preference isn't outcome: you can only focus on what's on your list.**
Comparing focus share with list share is what makes the bias visible.

**Hypothesis 2, confirmed, with a denominator lesson.** 28% of all urgent tasks were later
downgraded, but **62% of the urgent tasks still open the next morning** were. Tasks finished
on day one never had the chance, so the second number is the fair test. Downgrades happen
fast: **median 1.0 day, 74 of 77 within 72 hours**, almost all at the first morning review.

**Pipeline health:** 3,509 rows received → 3,466 clean events. 36 duplicates removed,
8 timestamps repaired, 7 rows quarantined, 95 late arrivals handled. 11 orphans from
deliberately lost events are flagged, not hidden.

## Lessons

- **Instrument behavior, not state.** The most important data decision was in the UI.
- **Decide definitions before dashboards.** "Downgraded", "within a few days" and "open next
  morning" are written down once and implemented twice (Python and SQL), then reconciled.
- **Removing a row is losing data.** Quarantined rows behave like dropped ones downstream, so
  repair what's repairable first.
- **Know the right answer before trusting the analysis.** The answer key turned "the numbers
  look plausible" into "the numbers are provably right".

## What's next

- Run the same pipeline privately on my real exported data and compare it with the simulation.
- Optional weekly review: Claude writes a short commentary on the week's numbers (the numbers
  themselves come from SQL, so every figure is traceable).
