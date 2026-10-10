# Priority Matrix: designing a product around the questions its data should answer

**Role:** solo: product, design, analytics, data management
**Tools:** React · Python · SQL (dbt) · DuckDB · Airflow · Tableau Public
**Code:** [github.com/MedhaDev/priority-matrix](https://github.com/MedhaDev/priority-matrix)

## The problem

I sort my work with an Eisenhower Matrix (urgent × important) and focus in 25-minute sessions.
To-do apps show what's on the list today, but not whether the system is working. Two questions
matter:

1. **Does my focus go to urgent work at the expense of important, non-urgent work?**
2. **Do tasks I label "urgent" stay urgent, or get downgraded within days?**

Gut feeling can't settle those. Data can, if the product records the right things.

## Product: record behavior, not just state

The original app stored only each task's *current* state. A task moved from Do first to
Schedule simply had a new label, and its history was gone, so neither question could be
answered. I redesigned it so **every action is recorded**: task created, moved (from → to),
completed, carried over, and every focus session started, paused, finished or abandoned.

Product decisions that came from thinking about the data:

- **Private by design.** No account, no server. Data stays on the device and leaves only when
  exported.
- **Carry-over moves a task instead of copying it.** Copies would split one task's history into
  several unrelated tasks and make question 2 unmeasurable.
- **Focus time comes from start and end times,** not a ticking counter, so it stays correct when
  the phone sleeps mid-session.
- **Dates follow local time.** Otherwise evening work counts toward tomorrow.
- **The answers live in the app.** A Patterns tab shows the numbers right where the work happens.

## Defining the metrics

The questions sound simple; the definitions are where analysis usually goes wrong.

- **Compare against the right baseline.** If urgent tasks fill most of the list, most focus
  going to them is fair. So each quadrant's **share of focus time** is compared with its
  **share of the list**. A bias shows up as the gap between the two.
- **Pick the fair denominator.** A task finished the day it was created never had a chance to be
  downgraded. "Urgent doesn't last" is measured only over **urgent tasks still open the next
  morning**.
- **Write definitions down once.** "Downgraded", "within a few days" and "open next morning"
  are defined in one place and used everywhere, so every chart means the same thing.

## The data pipeline

```
My app data → Database → Clean, define metrics, test → Dashboard
              (DuckDB)   (SQL with dbt)                 (Tableau Public)
```

1. **Source:** the app's event log, in one documented format.
2. **Load:** events go into the database one day at a time. Re-running a day replaces it, so
   nothing is counted twice.
3. **Clean:** duplicates removed, fixable rows repaired, broken rows set aside.
4. **Model:** SQL models in dbt turn events into focus sessions, daily task lists and the two
   metrics, in clear layers from raw to clean to final.
5. **Report:** the final tables are exported for the Tableau dashboard, and an AI tool writes
   a short weekly summary. The numbers come from SQL; the AI only writes the commentary, so
   every figure can be traced.

Airflow runs the steps in order, and GitHub Actions re-runs every check whenever the code
changes.

*For privacy, the data in the public repo is synthetic, in the same format as the app's own
data.*

## Data management

- **A data contract.** Every event follows one documented format ([data contract](event-schema.md)):
  what each field means, which values are allowed, and what changes count as breaking.
- **Data-quality rules.** Event data is messy: duplicate uploads, events arriving days late,
  missing time zones, broken rows from older app versions. Each problem has a rule:
  - Duplicates: removed.
  - Fixable rows: repaired.
  - Broken rows: set aside and counted, never silently deleted.
- **A data-health report.** Every run reports how many rows came in, how many were removed,
  repaired or set aside, and why.
- **Tested numbers.** 54 automated checks cover the cleaned data and the metrics, including
  checks that the final numbers match the expected answers row by row.
- **Lineage.** Any number on the dashboard can be traced back to the events behind it.

## Lessons

- **Measurement starts in the product.** The most important data decision was in the UI:
  record the history, not just the current state.
- **Define metrics before building dashboards.** A metric without a written definition and a
  fair baseline can say almost anything.
- **Deleting a bad row is losing data.** Repair what can be repaired, and count what can't.
- **Know the right answer before trusting the analysis.** Testing against expected answers
  turned "looks plausible" into "provably right".

## What's next

- A Tableau Public dashboard built on the same metrics.
