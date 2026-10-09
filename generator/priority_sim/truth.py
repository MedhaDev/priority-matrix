"""The answer key: what actually happened in the clean simulated data.

Computed from the EVENTS, not the settings. Planted settings are chances,
so the realized numbers differ a little; the truth is what really happened.
In Phase 3 the dbt models must reproduce these numbers.

Definitions (also in docs/event-schema.md, keep them in sync):
  Focus time     focused_secs on pomodoro_finished + pomodoro_abandoned,
                 grouped by the event's quadrant (the task's quadrant during
                 the session) and by local_date.
  Urgent task    a task whose task_created quadrant is do or delegate.
  Downgrade      the task's FIRST task_moved from an urgent quadrant
                 (do, delegate) to a non-urgent one (schedule, eliminate).
  Within 3 days  downgrade occurred_at - created occurred_at <= 72 hours.
"""
from __future__ import annotations

import datetime as dt
from statistics import median
from typing import Any, Dict, List, Optional

from . import SCHEMA_VERSION
from .invariants import parse_ts

QUADRANTS = ("do", "schedule", "delegate", "eliminate")
URGENT = ("do", "delegate")
ENDS = ("pomodoro_finished", "pomodoro_abandoned")
WITHIN_HOURS = 72


def _round(x: Optional[float], n: int = 4) -> Optional[float]:
    return None if x is None else round(x, n)


def focus_truth(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    secs = {q: 0 for q in QUADRANTS}
    sessions = {"finished": 0, "abandoned": 0}
    daily: Dict[tuple, Dict[str, int]] = {}
    for e in events:
        if e["event_type"] not in ENDS:
            continue
        s = e["payload"]["focused_secs"]
        secs[e["quadrant"]] += s
        sessions["finished" if e["event_type"] == "pomodoro_finished" else "abandoned"] += 1
        row = daily.setdefault((e["local_date"], e["quadrant"]), {"focused_secs": 0, "sessions": 0})
        row["focused_secs"] += s
        row["sessions"] += 1

    total = sum(secs.values())
    share = {q: _round(secs[q] / total) if total else 0.0 for q in QUADRANTS}
    return {
        "total_focused_secs": total,
        "focused_secs_by_quadrant": secs,
        "share_by_quadrant": share,
        "do_vs_schedule_ratio": _round(secs["do"] / secs["schedule"], 3) if secs["schedule"] else None,
        "sessions": sessions,
        "abandon_rate": _round(sessions["abandoned"] / sum(sessions.values())) if sum(sessions.values()) else None,
        # Exactly what the dbt daily focus mart should contain, row for row.
        "daily": [
            {"local_date": d, "quadrant": q, **v}
            for (d, q), v in sorted(daily.items())
        ],
    }


def downgrade_truth(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    created: Dict[str, Dict[str, Any]] = {}     # urgent tasks only
    first_downgrade: Dict[str, dt.datetime] = {}
    open_next_morning = set()
    for e in events:
        tid, kind = e["task_id"], e["event_type"]
        if kind == "task_created" and e["quadrant"] in URGENT:
            created[tid] = {"at": parse_ts(e["occurred_at"]), "day": e["local_date"]}
        elif tid in created:
            if e["local_date"] > created[tid]["day"]:
                open_next_morning.add(tid)   # still around on a later day
            if (kind == "task_moved" and tid not in first_downgrade
                    and e["from_quadrant"] in URGENT and e["quadrant"] not in URGENT):
                first_downgrade[tid] = parse_ts(e["occurred_at"])

    lags_h = sorted((first_downgrade[t] - created[t]["at"]).total_seconds() / 3600 for t in first_downgrade)
    within = sum(1 for h in lags_h if h <= WITHIN_HOURS)
    n, survivors = len(created), len(open_next_morning)
    return {
        "urgent_tasks": n,
        "downgraded": len(lags_h),
        "downgraded_within_72h": within,
        "rate": _round(len(lags_h) / n) if n else None,
        "rate_within_72h": _round(within / n) if n else None,
        # Tasks finished on day one never get a chance to be downgraded.
        "urgent_tasks_open_next_morning": survivors,
        "rate_among_open_next_morning": _round(len(lags_h) / survivors) if survivors else None,
        "median_days_to_downgrade": _round(median(lags_h) / 24, 3) if lags_h else None,
    }


def compute_truth(events: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for e in events:
        counts[e["event_type"]] = counts.get(e["event_type"], 0) + 1
    start = cfg["simulation"]["start_date"]
    return {
        "persona": cfg["persona"]["name"],
        "seed": cfg["simulation"]["seed"],
        "schema_version": SCHEMA_VERSION,
        "first_day": start.isoformat(),
        "last_day": (start + dt.timedelta(days=cfg["simulation"]["days"] - 1)).isoformat(),
        "events": len(events),
        "event_counts": dict(sorted(counts.items())),
        "definitions": {
            "focus_time": "sum of payload.focused_secs on pomodoro_finished + pomodoro_abandoned, by event quadrant and local_date",
            "urgent_task": "task_created in do or delegate",
            "downgrade": "first task_moved from do/delegate to schedule/eliminate",
            "within_72h": "downgrade occurred_at minus task_created occurred_at <= 72 hours",
        },
        # What we set vs. what happened.
        "planted": {
            "focus_quadrant_mix": cfg["focus"]["quadrant_mix"],
            "create_mix": cfg["planning"]["create_mix"],
            "morning_downgrade_chance": cfg["urgency"]["morning_downgrade_chance"],
        },
        "hypothesis_1_focus": focus_truth(events),
        "hypothesis_2_downgrades": downgrade_truth(events),
    }
