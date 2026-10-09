# Warehouse + dbt

Turns the generator's daily event files into tested, analysis-ready tables.

```
generator/data/raw/arrived_on=*/events.jsonl
        │  warehouse/load.py   (idempotent per day: delete + insert)
        ▼
raw.events                     every delivered line, untouched (JSON)
        │  dbt
        ▼
staging       stg_events__validated → stg_events (clean, typed, deduped, incremental)
                                     → stg_events__quarantine (contract breakers, kept)
intermediate  int_tasks · int_focus_sessions · int_task_days
marts         daily_focus_metrics · weekly_focus_share · h1_focus_by_quadrant
              h2_urgent_tasks · h2_downgrade_summary · fct_focus_sessions · dim_tasks
              data_quality_daily · data_quality_summary
```

## Run it

```bash
python3 -m venv warehouse/.venv && warehouse/.venv/bin/pip install -r warehouse/requirements.txt
./warehouse/run_pipeline.sh               # generate → load → dbt build, full rebuild (DuckDB)
./warehouse/run_pipeline.sh 2026-09-15    # one arrival day, incremental (what Airflow runs)
```

Requires the generator's environment too (see `generator/README.md`).

## What staging handles

| Problem in the raw data | What staging does |
|---|---|
| Duplicate deliveries (upload retries) | keeps the first delivery of each `event_id` |
| Late arrivals (phone offline) | incremental runs re-read a 3-day lookback window; ordering uses `occurred_at`, never arrival |
| Timestamp without a time zone | repaired: interpreted in the event's `timezone` |
| Rows that break the contract | quarantined in `stg_events__quarantine` with a reason, excluded from models |
| Lost events | can't be recovered: orphans are flagged (`is_complete`, `has_create_event`) and counted in `data_quality_summary` |

## Tests (`dbt build` runs them all)

- **Generic:** unique / not null / accepted values / relationships on every key table.
- **Invariants** (mirroring `generator/priority_sim/invariants.py`): no session over 25 min or over
  wall-clock time, `local_date` matches the time zone, carry-overs move forward. Orphan checks
  *warn* instead of fail, because lost events are real.
- **Reconciliation** against the generator's answer key: `daily_focus_metrics` must match row for
  row, the hypothesis numbers must match, and the quarantine must contain exactly the rows the
  generator broke on purpose. Turned off for real data with `--vars '{reconcile: false}'`.

Verified on both **DuckDB** (local, CI, Airflow) and **Postgres 16** (same engine as Supabase):
`PASS=54 WARN=2 ERROR=0`. Incremental day-by-day loads, including out-of-order days and
backfills, produce exactly the same tables as a full rebuild.

## Supabase (optional, synthetic data only)

1. Review and run `supabase/migrations/001_warehouse.sql` in the Supabase SQL Editor
   (replace the placeholder password first). It creates the schemas, a `pipeline` role, and
   locks everything away from the public API.
2. Copy `.env.example` to `.env` and fill in the **Session pooler** connection
   (Project Settings → Database). With the pooler, the user is `pipeline.<project-ref>`.
3. Run with the Postgres target:
   ```bash
   set -a; source .env; set +a
   WAREHOUSE_TARGET=postgres DBT_TARGET=postgres ./warehouse/run_pipeline.sh
   ```
