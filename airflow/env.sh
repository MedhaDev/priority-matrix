# Source this before any airflow command:  source airflow/env.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
export PRIORITY_ROOT="$ROOT"
export AIRFLOW_HOME="$ROOT/airflow/.home"          # Airflow's own database and logs (git-ignored)
export AIRFLOW__CORE__DAGS_FOLDER="$ROOT/airflow/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export DUCKDB_PATH="${DUCKDB_PATH:-$ROOT/warehouse/priority.duckdb}"
export PATH="$ROOT/airflow/.venv/bin:$PATH"
