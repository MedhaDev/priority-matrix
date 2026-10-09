"""Inject realistic data problems into a clean event log, and record them.

Each event's fate is decided by a random draw seeded with its OWN event_id,
so it doesn't depend on how many days were simulated. A given day's file is
therefore identical whether it's generated alone (Airflow) or in a full run.
One draw per event also means no event gets two problems.

Returns "deliveries": what ingestion actually receives, each event paired with
the local day it ARRIVED. Normally that's the day it happened; late events
arrive 1–3 days later and land at the end of a later day's file.
"""
from __future__ import annotations

import copy
import datetime as dt
import random
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

from .invariants import parse_ts

PROBLEMS = {
    "dropped": {
        "cause": "events lost in transit and never delivered",
        "detect": "orphans downstream (sessions that never end, events for unknown tasks)",
        "fix": "not recoverable: flag orphans, exclude incomplete sessions from metrics",
    },
    "naive_timestamps": {
        "cause": "client bug: occurred_at written as local wall-clock time with no offset",
        "detect": "schema (timestamp without time zone)",
        "fix": "repair in staging: interpret in the event's timezone field",
    },
    "malformed": {
        "cause": "an old app version sent a row that breaks the contract",
        "detect": "schema",
        "fix": "quarantine in staging (kept in a quarantine table, excluded from models)",
    },
    "duplicates": {
        "cause": "phone retried an upload, so the same event arrives twice",
        "detect": "duplicate_event_id",
        "fix": "deduplicate on event_id in staging",
    },
    "late_arrivals": {
        "cause": "phone was offline; events arrive 1–3 days after they happened",
        "detect": "arrived_on later than local_date (out of order within a day's file)",
        "fix": "incremental loads re-read a lookback window; order by occurred_at, not arrival",
    },
}
ORDER = ("dropped", "naive_timestamps", "malformed", "duplicates", "late_arrivals")
RATE_KEY = {"dropped": "dropped_rate", "naive_timestamps": "naive_timestamp_rate", "malformed": "malformed_rate",
            "duplicates": "duplicate_rate", "late_arrivals": "late_rate"}
MALFORMATIONS = ("legacy_event_type", "legacy_quadrant", "missing_timezone", "string_schema_version")


def _malform(e: Dict[str, Any], how: str) -> None:
    if how == "legacy_event_type":
        e["event_type"] = "task_done"
    elif how == "legacy_quadrant":
        e["quadrant"] = "Q1"
    elif how == "missing_timezone":
        del e["timezone"]
    elif how == "string_schema_version":
        e["schema_version"] = "1"


def _local_wall_clock(e: Dict[str, Any]) -> str:
    local = parse_ts(e["occurred_at"]).astimezone(ZoneInfo(e["timezone"]))
    return local.strftime("%Y-%m-%dT%H:%M:%S.") + f"{local.microsecond // 1000:03d}"


def fate(event_id: str, seed: int, mess: Dict[str, Any]) -> Tuple[str, random.Random]:
    """Which problem (if any) hits this event. Depends only on (seed, event_id)."""
    r = random.Random(f"mess:{seed}:{event_id}")
    u, edge = r.random(), 0.0
    for name in ORDER:
        edge += mess[RATE_KEY[name]]
        if u < edge:
            return name, r
    return "none", r


def add_mess(events: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return (deliveries, manifest). `events` is not modified."""
    m, seed = cfg["mess"], cfg["simulation"]["seed"]
    deliveries: List[Dict[str, Any]] = []
    affected: Dict[str, List[Dict[str, Any]]] = {name: [] for name in PROBLEMS}

    for original in events:
        e = copy.deepcopy(original)
        arrived_on = e["local_date"]
        problem, r = fate(e["event_id"], seed, m)
        note: Dict[str, Any] = {"event_id": e["event_id"], "event_type": e["event_type"], "local_date": e["local_date"]}

        if problem == "dropped":
            affected["dropped"].append(note)
            continue
        if problem == "naive_timestamps":
            e["occurred_at"] = _local_wall_clock(e)
            affected["naive_timestamps"].append(note)
        elif problem == "malformed":
            how = r.choice(MALFORMATIONS)
            _malform(e, how)
            affected["malformed"].append({**note, "how": how})
        elif problem == "late_arrivals":
            delay = r.randint(*m["late_days"])
            arrived_on = (dt.date.fromisoformat(e["local_date"]) + dt.timedelta(days=delay)).isoformat()
            affected["late_arrivals"].append({**note, "arrived_on": arrived_on})

        deliveries.append({"arrived_on": arrived_on, "event": e})
        if problem == "duplicates":
            deliveries.append({"arrived_on": arrived_on, "event": copy.deepcopy(e)})   # the retry
            affected["duplicates"].append(note)

    # Grouped by arrival day; late events land after that day's on-time events.
    deliveries.sort(key=lambda d: (d["arrived_on"], d["arrived_on"] != d["event"]["local_date"]))

    manifest = {
        "seed": seed,
        "clean_events": len(events),
        "delivered_rows": len(deliveries),
        "problems": {
            name: {**PROBLEMS[name], "count": len(affected[name]), "events": affected[name]}
            for name in PROBLEMS
        },
    }
    return deliveries, manifest
