"""Load the generator's daily files into raw.events, one arrival day at a time.

  python warehouse/load.py                          # every file in generator/data/raw → DuckDB
  python warehouse/load.py --date 2026-09-15        # one day (what Airflow runs)
  python warehouse/load.py --target postgres        # any Postgres (connection from env)

raw.events keeps every delivered line exactly as received (as JSON), plus where
it came from. Loading a day deletes that day's rows first, so reruns never
duplicate anything (idempotent). All cleaning happens later, in dbt.

Postgres connection comes from the environment (put these in the repo's
git-ignored .env): PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD (or DATABASE_URL).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "generator" / "data" / "raw"
DEFAULT_DUCKDB = Path(os.environ.get("DUCKDB_PATH", ROOT / "warehouse" / "priority.duckdb"))

DDL = {
    "duckdb": """
        create schema if not exists raw;
        create table if not exists raw.events (
            arrived_on  date        not null,
            line_no     integer     not null,
            body        json        not null,
            source_file varchar     not null,
            loaded_at   timestamptz not null default current_timestamp,
            primary key (arrived_on, line_no)
        );""",
    "postgres": """
        create schema if not exists raw;
        create table if not exists raw.events (
            arrived_on  date        not null,
            line_no     integer     not null,
            body        jsonb       not null,
            source_file text        not null,
            loaded_at   timestamptz not null default now(),
            primary key (arrived_on, line_no)
        );""",
}

Row = Tuple[str, int, str, str]


def read_partition(path: Path) -> List[Row]:
    day = path.parent.name.split("=", 1)[1]
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            line = line.strip()
            if line:
                json.loads(line)   # fail loudly on a line that isn't JSON at all
                rows.append((day, n, line, str(path.relative_to(path.parents[2]))))
    return rows


def partitions(data: Path, date: dt.date | None) -> List[Path]:
    if date:
        p = data / f"arrived_on={date.isoformat()}" / "events.jsonl"
        if not p.exists():
            raise SystemExit(f"No file for {date}: {p}")
        return [p]
    return sorted(data.glob("arrived_on=*/events.jsonl"))


def connect(target: str):
    if target == "duckdb":
        import duckdb
        DEFAULT_DUCKDB.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(DEFAULT_DUCKDB))
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(url) if url else psycopg2.connect("")   # libpq reads PG* env vars


def load(target: str, files: List[Path]) -> int:
    con = connect(target)
    cur = con.cursor()
    cur.execute(DDL[target])
    total = 0
    for path in files:
        rows = read_partition(path)
        day = rows[0][0] if rows else path.parent.name.split("=", 1)[1]
        # One transaction per day: delete then insert, so a rerun replaces the day exactly.
        cur.execute("begin")
        cur.execute("delete from raw.events where arrived_on = %s" if target == "postgres"
                    else "delete from raw.events where arrived_on = ?", [day])
        if rows:
            if target == "postgres":
                from psycopg2.extras import execute_values
                execute_values(cur, "insert into raw.events (arrived_on, line_no, body, source_file) values %s", rows,
                               template="(%s, %s, %s::jsonb, %s)")
            else:
                cur.executemany("insert into raw.events (arrived_on, line_no, body, source_file) values (?, ?, ?, ?)", rows)
        cur.execute("commit")
        total += len(rows)
    con.close()
    return total


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load daily event files into raw.events")
    p.add_argument("--target", choices=["duckdb", "postgres"], default=os.environ.get("WAREHOUSE_TARGET", "duckdb"))
    p.add_argument("--data", type=Path, default=DEFAULT_DATA)
    p.add_argument("--date", type=dt.date.fromisoformat)
    args = p.parse_args(argv)
    files = partitions(args.data, args.date)
    if not files:
        print(f"No files found in {args.data}", file=sys.stderr)
        return 1
    n = load(args.target, files)
    where = DEFAULT_DUCKDB if args.target == "duckdb" else "postgres"
    print(f"loaded {n} rows from {len(files)} file(s) into raw.events ({where})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
