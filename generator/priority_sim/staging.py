"""Reference staging: exactly what the dbt staging models do, in Python.

Used to compute the "recoverable" answer key: what a correct pipeline should
report given what was actually delivered. The dbt models must match it.

  1. repair   timestamps without an offset → interpret in the event's timezone
  2. quarantine rows that still break the contract
  3. dedupe   keep the first delivery of each event_id
  4. order    by occurred_at (not arrival)
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

from .invariants import check

HAS_OFFSET = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


def repair_timestamp(e: Dict[str, Any]) -> Dict[str, Any]:
    ts, tz = e.get("occurred_at"), e.get("timezone")
    if not isinstance(ts, str) or HAS_OFFSET.search(ts) or not tz:
        return e
    try:
        local = dt.datetime.fromisoformat(ts).replace(tzinfo=ZoneInfo(tz))
    except ValueError:
        return e
    utc = local.astimezone(dt.timezone.utc)
    return {**e, "occurred_at": utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"}


def stage(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (staged events, quarantined rows)."""
    staged, quarantined, seen = [], [], set()
    for row in rows:
        e = repair_timestamp(row)
        if any(v.code == "schema" for v in check([e])):
            quarantined.append(row)
            continue
        if e["event_id"] in seen:
            continue
        seen.add(e["event_id"])
        staged.append(e)
    staged.sort(key=lambda e: e["occurred_at"])
    return staged, quarantined
