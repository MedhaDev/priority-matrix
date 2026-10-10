#!/usr/bin/env bash
# Run the whole pipeline once, end to end, on the local DuckDB warehouse:
#   generate synthetic events → load raw.events → dbt build (models + tests + reconciliation)
#
#   ./warehouse/run_pipeline.sh                 # full rebuild
#   ./warehouse/run_pipeline.sh 2026-09-15      # one arrival day, incremental (like Airflow)
#
# Uses each part's own virtual environment (see README). Set WAREHOUSE_TARGET=postgres
# and DBT_TARGET=postgres (plus PG* variables) to run against Postgres instead.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DUCKDB_PATH="${DUCKDB_PATH:-$ROOT/warehouse/priority.duckdb}"
GEN="$ROOT/generator/.venv/bin/python"
WH="$ROOT/warehouse/.venv/bin/python"
DBT="$ROOT/warehouse/.venv/bin/dbt"
DAY="${1:-}"

if [[ -z "$DAY" ]]; then
  "$GEN" -m priority_sim --seeds-dir "$ROOT/dbt/seeds"
  [[ "${WAREHOUSE_TARGET:-duckdb}" == "duckdb" ]] && rm -f "$DUCKDB_PATH"
  "$WH" "$ROOT/warehouse/load.py"
  (cd "$ROOT/dbt" && "$DBT" build --profiles-dir . --full-refresh)
else
  "$GEN" -m priority_sim --date "$DAY" --seeds-dir "$ROOT/dbt/seeds"
  "$WH" "$ROOT/warehouse/load.py" --date "$DAY"
  (cd "$ROOT/dbt" && "$DBT" build --profiles-dir .)
fi
