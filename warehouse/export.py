"""Export the dashboard tables (dbt marts) as CSV files for Tableau Public.

  python warehouse/export.py                  # from the local DuckDB warehouse → exports/
  python warehouse/export.py --target postgres

Tableau Public can't connect to a database, so the dashboard reads these files.
They contain only synthetic data. Re-running overwrites them (idempotent).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "exports"
DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", ROOT / "warehouse" / "priority.duckdb"))

TABLES = [
    ("daily_focus_metrics", "focus_date, quadrant"),
    ("weekly_focus_share", "week_start, quadrant"),
    ("h1_focus_by_quadrant", "sort_order"),
    ("h2_urgent_tasks", "created_at"),
    ("h2_downgrade_summary", None),
    ("fct_focus_sessions", "started_at"),
    ("dim_tasks", "created_at"),
    ("data_quality_daily", "arrived_on"),
    ("data_quality_summary", None),
]


def fetch(target: str, sql: str):
    if target == "duckdb":
        import duckdb
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    else:
        import psycopg2
        url = os.environ.get("DATABASE_URL")
        con = psycopg2.connect(url) if url else psycopg2.connect("")
    cur = con.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    con.close()
    return cols, rows


def fmt(v):
    if isinstance(v, dt.datetime):
        return v.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if v.tzinfo else v.isoformat()
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, bool):
        return "true" if v else "false"
    return "" if v is None else v


def export(target: str, out: Path) -> List[str]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for table, order in TABLES:
        cols, rows = fetch(target, f"select * from marts.{table}" + (f" order by {order}" if order else ""))
        path = out / f"{table}.csv"
        tmp = path.with_suffix(".csv.tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows([fmt(v) for v in r] for r in rows)
        os.replace(tmp, path)
        written.append(f"{table}.csv ({len(rows)} rows)")
    (out / "_exported.json").write_text(json.dumps({
        "exported_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": target, "files": written, "data": "synthetic (Medha, simulated)",
    }, indent=2) + "\n")
    return written


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export dbt marts to CSV for Tableau")
    p.add_argument("--target", choices=["duckdb", "postgres"], default=os.environ.get("WAREHOUSE_TARGET", "duckdb"))
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    files = export(args.target, args.out)
    print(f"exported {len(files)} tables → {args.out}: " + ", ".join(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
