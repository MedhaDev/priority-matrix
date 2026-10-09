"""Daily pipeline: one synthetic arrival day, end to end.

    generate ──► load ──► dbt_seed ──► dbt_run ──► dbt_test ──► export
                                                                  └──► weekly_review (Sundays, optional)

Each run handles ONE logical date ({{ ds }}): the events that *arrived* that day.
Every step is idempotent (same date → same files → same tables), so reruns
and backfills are safe:

    airflow backfill create --dag-id priority_pipeline \
        --from-date 2026-06-10 --to-date 2026-10-07

max_active_runs=1 because the warehouse is a single DuckDB file and dbt
incremental models build on the previous day.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG

try:  # Airflow 3
    from airflow.providers.standard.operators.bash import BashOperator
    from airflow.providers.standard.operators.python import ShortCircuitOperator
except ImportError:  # Airflow 2
    from airflow.operators.bash import BashOperator
    from airflow.operators.python import ShortCircuitOperator

ROOT = Path(os.environ.get("PRIORITY_ROOT", Path(__file__).resolve().parents[2]))
GEN = ROOT / "generator" / ".venv" / "bin" / "python"
WH = ROOT / "warehouse" / ".venv" / "bin" / "python"
DBT = ROOT / "warehouse" / ".venv" / "bin" / "dbt"

ENV = {
    "PATH": "/usr/bin:/bin",
    "DUCKDB_PATH": os.environ.get("DUCKDB_PATH", str(ROOT / "warehouse" / "priority.duckdb")),
    "WAREHOUSE_TARGET": os.environ.get("WAREHOUSE_TARGET", "duckdb"),
    "DBT_TARGET": os.environ.get("DBT_TARGET", "duckdb"),
}
# Pass through Postgres / API settings when present (never hard-coded here).
for key in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PGSSLMODE", "ANTHROPIC_API_KEY"):
    if os.environ.get(key):
        ENV[key] = os.environ[key]

DBT_CMD = f"cd {ROOT / 'dbt'} && {DBT} {{cmd}} --profiles-dir . --target {ENV['DBT_TARGET']}"


def is_sunday_with_key(ds: str, **_) -> bool:
    """Weekly review only on Sundays, and only if an API key is configured."""
    return datetime.fromisoformat(ds).weekday() == 6 and bool(os.environ.get("ANTHROPIC_API_KEY"))


with DAG(
    dag_id="priority_pipeline",
    description="Synthetic events → warehouse → dbt (models, tests, reconciliation) → Tableau CSVs",
    start_date=datetime(2026, 6, 10),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["priority-matrix", "synthetic"],
    doc_md=__doc__,
) as dag:

    generate = BashOperator(
        task_id="generate",
        bash_command=f"{GEN} -m priority_sim --date {{{{ ds }}}} --seeds-dir {ROOT / 'dbt' / 'seeds'}",
        env=ENV,
        doc_md="Write `arrived_on={{ ds }}/events.jsonl` and refresh the answer key (dbt seeds).",
    )

    load = BashOperator(
        task_id="load",
        bash_command=f"{WH} {ROOT / 'warehouse' / 'load.py'} --date {{{{ ds }}}}",
        env=ENV,
        doc_md="Replace the day's rows in raw.events (delete + insert in one transaction).",
    )

    dbt_seed = BashOperator(task_id="dbt_seed", bash_command=DBT_CMD.format(cmd="seed"), env=ENV)
    dbt_run = BashOperator(task_id="dbt_run", bash_command=DBT_CMD.format(cmd="run"), env=ENV)
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=DBT_CMD.format(cmd="test"),
        env=ENV,
        doc_md="Generic tests, invariants and reconciliation. A failure stops the export.",
    )

    export = BashOperator(
        task_id="export",
        bash_command=f"{WH} {ROOT / 'warehouse' / 'export.py'} && {WH} {ROOT / 'warehouse' / 'build_dashboard.py'}",
        env=ENV,
        doc_md="Overwrite the Tableau CSVs and the HTML dashboard preview in exports/.",
    )

    sunday = ShortCircuitOperator(task_id="is_sunday", python_callable=is_sunday_with_key)
    weekly_review = BashOperator(
        task_id="weekly_review",
        bash_command=f"{WH} {ROOT / 'review' / 'weekly_review.py'} --week-ending {{{{ ds }}}}",
        env=ENV,
        doc_md="Optional: an AI-written review of the week's metrics (Phase 6).",
    )

    generate >> load >> dbt_seed >> dbt_run >> dbt_test >> export >> sunday >> weekly_review
