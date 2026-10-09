"""Command line: write the synthetic event log to disk.

  python -m priority_sim                      # full run: every day in the persona's range
  python -m priority_sim --through 2026-09-30 # full run up to a day
  python -m priority_sim --date 2026-09-15    # just the file for one arrival day (Airflow)

Output (default: generator/data/):
  raw/arrived_on=YYYY-MM-DD/events.jsonl   what ingestion receives, one file per arrival day
  truth.json                               answer key: "full" (clean data) and "recoverable"
                                           (what a correct pipeline can report from what arrived)
  manifest.json                            every injected problem, with event_ids
  --seeds-dir DIR                          also write the answer key as dbt seed CSVs

Same persona + seed + day → byte-identical files, so reruns and backfills are safe.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

from .config import ConfigError, load_persona
from .mess import add_mess
from .simulate import simulate
from .staging import stage
from .truth import compute_truth

HERE = Path(__file__).resolve().parents[1]


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _jsonl(rows: List[Dict[str, Any]]) -> str:
    return "".join(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n" for r in rows)


def _write_csv(path: Path, header: List[str], rows: List[List[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def build(cfg: Dict[str, Any], through: dt.date) -> Dict[str, Any]:
    """Everything for one horizon: deliveries that have arrived by `through`, truth, manifest."""
    clean = simulate(cfg, through)
    deliveries, manifest = add_mess(clean, cfg)
    horizon = through.isoformat()
    arrived = [d for d in deliveries if d["arrived_on"] <= horizon]
    manifest["horizon"] = horizon
    manifest["not_yet_arrived"] = len(deliveries) - len(arrived)
    staged, quarantined = stage([d["event"] for d in arrived])
    full, recoverable = compute_truth(clean, cfg), compute_truth(staged, cfg)
    for t in (full, recoverable):
        t["last_day"] = horizon
    truth = {
        "horizon": horizon,
        "full": full,
        "recoverable": recoverable,
        "quarantined_rows": len(quarantined),
        "note": "The pipeline must reproduce 'recoverable' exactly. 'full' minus 'recoverable' "
                "is the cost of dropped, quarantined and not-yet-arrived events.",
    }
    return {"arrived": arrived, "truth": truth, "manifest": manifest, "quarantined": quarantined}


def write_partition(out: Path, day: str, rows: List[Dict[str, Any]]) -> Path:
    path = out / "raw" / f"arrived_on={day}" / "events.jsonl"
    _write_atomic(path, _jsonl(rows))
    return path


def write_seeds(seeds_dir: Path, truth: Dict[str, Any], manifest: Dict[str, Any]) -> None:
    rec = truth["recoverable"]
    h1, h2 = rec["hypothesis_1_focus"], rec["hypothesis_2_downgrades"]
    _write_csv(seeds_dir / "truth_daily_focus.csv", ["local_date", "quadrant", "focused_secs", "sessions"],
               [[r["local_date"], r["quadrant"], r["focused_secs"], r["sessions"]] for r in h1["daily"]])
    summary = [
        ["h1_total_focused_secs", h1["total_focused_secs"]],
        *[[f"h1_focused_secs_{q}", v] for q, v in h1["focused_secs_by_quadrant"].items()],
        ["h1_sessions_finished", h1["sessions"]["finished"]],
        ["h1_sessions_abandoned", h1["sessions"]["abandoned"]],
        ["h2_urgent_tasks", h2["urgent_tasks"]],
        ["h2_downgraded", h2["downgraded"]],
        ["h2_downgraded_within_72h", h2["downgraded_within_72h"]],
        ["h2_urgent_tasks_open_next_morning", h2["urgent_tasks_open_next_morning"]],
        ["h2_median_days_to_downgrade", h2["median_days_to_downgrade"]],
    ]
    _write_csv(seeds_dir / "truth_summary.csv", ["metric", "value"], summary)
    horizon = truth["horizon"]
    _write_csv(seeds_dir / "expected_quarantine.csv", ["event_id", "how"],
               [[e["event_id"], e["how"]] for e in manifest["problems"]["malformed"]["events"]
                if _arrived(e, manifest) <= horizon])


def _arrived(e: Dict[str, Any], manifest: Dict[str, Any]) -> str:
    return e.get("arrived_on", e["local_date"])


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="priority_sim", description="Generate the synthetic Priority Matrix event log.")
    p.add_argument("--persona", default=str(HERE / "personas" / "medha.yaml"))
    p.add_argument("--out", default=str(HERE / "data"))
    p.add_argument("--through", type=dt.date.fromisoformat, help="last simulated day (default: persona's range)")
    p.add_argument("--date", type=dt.date.fromisoformat, help="write only this arrival day's file")
    p.add_argument("--seeds-dir", help="also write the answer key as dbt seed CSVs here")
    args = p.parse_args(argv)

    try:
        cfg = load_persona(args.persona)
    except ConfigError as e:
        print(f"Invalid persona settings:\n{e}", file=sys.stderr)
        return 2

    start = cfg["simulation"]["start_date"]
    default_end = start + dt.timedelta(days=cfg["simulation"]["days"] - 1)
    through = args.date or args.through or default_end
    if through < start:
        print(f"{through} is before the simulation starts ({start})", file=sys.stderr)
        return 2

    out = Path(args.out)
    result = build(cfg, through)

    if args.date:
        day = args.date.isoformat()
        rows = [d["event"] for d in result["arrived"] if d["arrived_on"] == day]
        path = write_partition(out, day, rows)
        print(f"{day}: {len(rows)} rows → {path}")
        # Backfills: newer days may already be on disk (and loaded). The answer key
        # must describe everything on disk, so compute it up to the newest file.
        on_disk = sorted(p.name.split("=", 1)[1] for p in (out / "raw").glob("arrived_on=*"))
        newest = dt.date.fromisoformat(on_disk[-1]) if on_disk else args.date
        if newest > args.date:
            result = build(cfg, newest)
    else:
        if (out / "raw").exists():
            shutil.rmtree(out / "raw")   # full run replaces everything
        by_day: Dict[str, List[Dict[str, Any]]] = {}
        for d in result["arrived"]:
            by_day.setdefault(d["arrived_on"], []).append(d["event"])
        for day, rows in sorted(by_day.items()):
            write_partition(out, day, rows)
        print(f"{start} → {through}: {len(result['arrived'])} rows in {len(by_day)} daily files → {out / 'raw'}")

    _write_atomic(out / "truth.json", json.dumps(result["truth"], indent=2, sort_keys=True) + "\n")
    _write_atomic(out / "manifest.json", json.dumps(result["manifest"], indent=2) + "\n")
    if args.seeds_dir:
        write_seeds(Path(args.seeds_dir), result["truth"], result["manifest"])

    rec = result["truth"]["recoverable"]
    h1, h2 = rec["hypothesis_1_focus"], rec["hypothesis_2_downgrades"]
    print(f"truth: Do first {h1['share_by_quadrant']['do']:.0%} of focus · "
          f"{h2['downgraded']}/{h2['urgent_tasks']} urgent tasks downgraded · "
          f"{result['truth']['quarantined_rows']} rows quarantined")
    return 0
