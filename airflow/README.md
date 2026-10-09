# Airflow

One DAG, `priority_pipeline`, runs the whole pipeline for one arrival day:

```
generate ──► load ──► dbt_seed ──► dbt_run ──► dbt_test ──► export ──► is_sunday ──► weekly_review
```

Every step is idempotent, so reruns and backfills are safe. `max_active_runs=1` because the
warehouse is a single DuckDB file and incremental models build on the previous day.
A failing dbt test (including reconciliation with the answer key) stops the run before export.

## Run it locally (no Docker needed)

```bash
python3 -m venv airflow/.venv
airflow/.venv/bin/pip install "apache-airflow==3.0.6" \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.0.6/constraints-3.9.txt"
source airflow/env.sh
airflow db migrate

airflow dags test priority_pipeline 2026-10-08     # run one day right now, in this terminal
airflow standalone                                 # web UI at http://localhost:8080 (login printed on start)
```

Backfill a range (with `airflow standalone` running):

```bash
airflow backfill create --dag-id priority_pipeline --from-date 2026-06-10 --to-date 2026-10-07
```

The generator and warehouse use their own virtual environments (see their READMEs); the DAG
calls them by path, so Airflow's dependencies never mix with dbt's.

Verified: `airflow dags test priority_pipeline 2026-10-08` → all tasks succeeded
(dbt_test: PASS=36 WARN=2 ERROR=0; weekly_review skipped on a Thursday).
