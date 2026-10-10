"""Rules every event log must obey: the story has to hold together.

`check(events)` replays the log in time order, keeps track of each task and
focus session, and returns a list of Violations. A clean simulation must
return none. The deliberately messy data (step 5) should trip specific codes,
and each code maps to a dbt test in Phase 3.

Codes
  schema                 event doesn't match docs/event.v1.schema.json
  duplicate_event_id     the same event_id appears twice
  out_of_order           log isn't sorted by occurred_at
  local_date_mismatch    local_date isn't occurred_at's day in the event's time zone
  event_before_create    a task event before (or without) its task_created
  duplicate_create       a task created twice
  event_after_delete     anything happening to a deleted task
  event_after_complete   a done task changed without being reopened first
  quadrant_mismatch      event's quadrant isn't the task's current quadrant
  bad_move               task_moved whose from_quadrant is wrong, or doesn't change anything
  bad_carry              carry-over that isn't from the task's current day to a later day
  pomodoro_sequence      session events out of order (e.g. resumed without paused, ended twice)
  pomodoro_unfinished    a session that starts but never ends
  pomodoro_overlap       a new session starts while another is still running
  focus_on_closed_task   focusing on a task that's done or deleted
  focus_wrong_day        focusing on a task that's planned for a different day
  focus_over_planned     focused_secs greater than planned_secs
  focus_over_wall_clock  focused_secs greater than the time that actually passed
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "event.v1.schema.json"
TASK_EVENTS = {"task_created", "task_edited", "task_moved", "task_completed", "task_reopened",
               "task_deleted", "task_carried_over"}
ENDS = {"pomodoro_finished", "pomodoro_abandoned"}


@dataclass(frozen=True)
class Violation:
    code: str
    event_id: Optional[str]
    message: str


@dataclass
class TaskState:
    quadrant: str
    date: str
    done: bool = False
    deleted: bool = False


@dataclass
class Session:
    task_id: Optional[str]
    started: dt.datetime
    last: str = "pomodoro_started"
    ended: bool = False
    events: List[str] = field(default_factory=list)


def parse_ts(s: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)   # naive stamps are already flagged by the schema


def check(events: Iterable[Dict[str, Any]], *, schema: bool = True) -> List[Violation]:
    events = list(events)
    out: List[Violation] = []

    def flag(code: str, e: Optional[Dict[str, Any]], msg: str) -> None:
        out.append(Violation(code, e.get("event_id") if e else None, msg))

    if schema:
        # Like dbt staging: rows that break the contract are reported, then set
        # aside, so one bad row can't crash or confuse the story checks below.
        invalid = _check_schema(events, flag)
        events = [e for e in events if id(e) not in invalid]

    # ── log-level ─────────────────────────────────────────────
    seen = set()
    for e in events:
        if e["event_id"] in seen:
            flag("duplicate_event_id", e, f"event_id {e['event_id']} appears more than once")
        seen.add(e["event_id"])
    for prev, cur in zip(events, events[1:]):
        if cur["occurred_at"] < prev["occurred_at"]:
            flag("out_of_order", cur, f"{cur['occurred_at']} comes after {prev['occurred_at']}")
    for e in events:
        local = parse_ts(e["occurred_at"]).astimezone(ZoneInfo(e["timezone"])).date().isoformat()
        if local != e["local_date"]:
            flag("local_date_mismatch", e, f"local_date {e['local_date']} but occurred_at is {local} in {e['timezone']}")

    # ── replay ────────────────────────────────────────────────
    tasks: Dict[str, TaskState] = {}
    sessions: Dict[str, Session] = {}
    running: Optional[str] = None   # pomodoro_id of the session currently running

    for e in sorted(events, key=lambda x: x["occurred_at"]):
        kind, tid = e["event_type"], e["task_id"]

        if kind in TASK_EVENTS:
            t = tasks.get(tid)
            if kind == "task_created":
                if t is not None:
                    flag("duplicate_create", e, f"task {tid} created twice")
                    continue
                tasks[tid] = TaskState(e["quadrant"], e["payload"].get("date", e["local_date"]))
                continue
            if t is None:
                flag("event_before_create", e, f"{kind} for task {tid} before it was created")
                continue
            if t.deleted:
                flag("event_after_delete", e, f"{kind} for task {tid} after it was deleted")
                continue
            if t.done and kind not in ("task_reopened", "task_deleted"):
                flag("event_after_complete", e, f"{kind} for task {tid} while it is done")

            if kind == "task_moved":
                if e["from_quadrant"] != t.quadrant or e["quadrant"] == e["from_quadrant"]:
                    flag("bad_move", e, f"moved {e['from_quadrant']}→{e['quadrant']} but task was in {t.quadrant}")
                t.quadrant = e["quadrant"]
            elif e["quadrant"] != t.quadrant:
                flag("quadrant_mismatch", e, f"{kind} says {e['quadrant']} but task is in {t.quadrant}")

            if kind == "task_carried_over":
                p = e["payload"]
                if p.get("from_date") != t.date or not p.get("to_date") or p["to_date"] <= p["from_date"]:
                    flag("bad_carry", e, f"carry {p.get('from_date')}→{p.get('to_date')} but task is planned for {t.date}")
                t.date = p.get("to_date", t.date)
            elif kind == "task_completed":
                t.done = True
            elif kind == "task_reopened":
                t.done = False
            elif kind == "task_deleted":
                t.deleted = True
            continue

        # pomodoro events
        pid = e["pomodoro_id"]
        at = parse_ts(e["occurred_at"])
        s = sessions.get(pid)
        if kind == "pomodoro_started":
            if s is not None:
                flag("pomodoro_sequence", e, f"session {pid} started twice")
                continue
            if running and not sessions[running].ended:
                flag("pomodoro_overlap", e, f"session {pid} started while {running} was still running")
            sessions[pid] = Session(tid, at)
            running = pid
            t = tasks.get(tid) if tid else None
            if tid and t is None:
                flag("event_before_create", e, f"focus on task {tid} before it was created")
            elif t is not None:
                if t.done or t.deleted:
                    flag("focus_on_closed_task", e, f"focus on task {tid} which is {'deleted' if t.deleted else 'done'}")
                if e["local_date"] != t.date:
                    flag("focus_wrong_day", e, f"focus on {e['local_date']} but task is planned for {t.date}")
            continue

        if s is None:
            flag("pomodoro_sequence", e, f"{kind} for session {pid} that never started")
            continue
        if s.ended:
            flag("pomodoro_sequence", e, f"{kind} after session {pid} already ended")
            continue
        if e["task_id"] != s.task_id:
            flag("pomodoro_sequence", e, f"{kind} names task {e['task_id']} but session is on {s.task_id}")
        allowed = {"pomodoro_paused": {"pomodoro_started", "pomodoro_resumed"},
                   "pomodoro_resumed": {"pomodoro_paused"}}
        if kind in allowed and s.last not in allowed[kind]:
            flag("pomodoro_sequence", e, f"{kind} right after {s.last} in session {pid}")
        if kind in ENDS:
            s.ended = True
            p = e["payload"]
            focused, planned = p.get("focused_secs", 0), p.get("planned_secs", 0)
            if focused > planned:
                flag("focus_over_planned", e, f"focused {focused}s but planned {planned}s")
            elapsed = (at - s.started).total_seconds()
            if focused > elapsed + 1:
                flag("focus_over_wall_clock", e, f"focused {focused}s but only {elapsed:.0f}s passed")
        s.last = kind

    for pid, s in sessions.items():
        if not s.ended:
            out.append(Violation("pomodoro_unfinished", None, f"session {pid} started but never ended"))
    return out


@lru_cache(maxsize=1)
def _validator():
    from jsonschema import Draft202012Validator, FormatChecker
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text()), format_checker=FormatChecker())


def _check_schema(events, flag) -> set:
    validator = _validator()
    invalid = set()
    for e in events:
        errs = list(validator.iter_errors(e))
        if errs:
            invalid.add(id(e))
            flag("schema", e, errs[0].message)   # one violation per bad row
    return invalid


def summarize(violations: List[Violation]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for v in violations:
        counts[v.code] = counts.get(v.code, 0) + 1
    return dict(sorted(counts.items()))
