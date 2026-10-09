"""The simulated story must hold together, and every check must actually fire.

Two kinds of tests:
  1. Clean simulations (several seeds) produce zero violations.
  2. "Break it on purpose": corrupt a clean log in exactly one way and make
     sure the matching check catches it. A check that never fires is useless.
"""
import copy
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from priority_sim.config import load_persona
from priority_sim.invariants import check, parse_ts, summarize
from priority_sim.simulate import simulate

PERSONA = Path(__file__).resolve().parents[1] / "personas" / "medha.yaml"


def run(seed=None, days=None):
    cfg = load_persona(PERSONA)
    if seed is not None:
        cfg["simulation"]["seed"] = seed
    if days is not None:
        cfg["simulation"]["days"] = days
    return cfg, simulate(cfg)


@pytest.fixture(scope="module")
def clean():
    return run()[1]


# ── 1. clean data ─────────────────────────────────────────────
@pytest.mark.parametrize("seed", [7, 1, 42, 2026])
def test_clean_simulation_has_no_violations(seed):
    _, events = run(seed)
    violations = check(events)
    assert violations == [], summarize(violations)


def test_same_seed_same_data():
    assert run(7)[1] == run(7)[1]


def test_different_seed_different_data():
    assert run(7)[1] != run(8)[1]


def test_covers_every_day(clean):
    cfg = load_persona(PERSONA)
    start, days = cfg["simulation"]["start_date"], cfg["simulation"]["days"]
    expected = {(start + dt.timedelta(days=i)).isoformat() for i in range(days)}
    assert {e["local_date"] for e in clean} == expected


def test_sessions_respect_the_schedule(clean):
    cfg = load_persona(PERSONA)
    focus = cfg["focus"]
    for e in clean:
        if e["event_type"] != "pomodoro_started":
            continue
        local = parse_ts(e["occurred_at"]).astimezone(ZoneInfo(e["timezone"]))
        assert local.hour < focus["last_start_hour"], f"session starts too late: {local}"
        assert not (focus["lunch"][0] <= local.hour < focus["lunch"][1]), f"session starts at lunch: {local}"


def test_new_tasks_per_day_within_range(clean):
    cfg = load_persona(PERSONA)
    plan = cfg["planning"]
    per_day = {}
    for e in clean:
        if e["event_type"] == "task_created":
            per_day[e["local_date"]] = per_day.get(e["local_date"], 0) + 1
    for day, n in per_day.items():
        d = dt.date.fromisoformat(day)
        lo, hi = plan["new_tasks_per_day"]["weekend" if d.weekday() >= 5 else "weekday"]
        if d.weekday() == 0:
            hi = round(hi * plan["monday_overcommit"])
        assert n <= hi, f"{day}: {n} new tasks, max is {hi}"


# ── 2. break it on purpose ───────────────────────────────────
def first(events, pred):
    return next(i for i, e in enumerate(events) if pred(e))


def resort(events):
    return sorted(events, key=lambda e: e["occurred_at"])


def shift(ts, **delta):
    t = parse_ts(ts) + dt.timedelta(**delta)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def task_ids_with(events, kind):
    return [e["task_id"] for e in events if e["event_type"] == kind]


def corrupt(events, how):
    ev = copy.deepcopy(events)
    if how == "schema":
        ev[0]["quadrant"] = "someday"

    elif how == "duplicate_event_id":
        i = len(ev) // 2
        ev.insert(i + 1, copy.deepcopy(ev[i]))

    elif how == "out_of_order":
        i = first(ev, lambda e: e["occurred_at"] < ev[-1]["occurred_at"] and e["local_date"] != ev[0]["local_date"])
        ev[i], ev[i + 1] = ev[i + 1], ev[i]
        if ev[i]["occurred_at"] == ev[i + 1]["occurred_at"]:
            ev[i + 1]["occurred_at"] = shift(ev[i]["occurred_at"], seconds=-1)

    elif how == "local_date_mismatch":
        e = ev[100]
        e["local_date"] = (dt.date.fromisoformat(e["local_date"]) + dt.timedelta(days=1)).isoformat()

    elif how == "event_before_create":
        moved = task_ids_with(ev, "task_moved")[0]
        ev.pop(first(ev, lambda e: e["event_type"] == "task_created" and e["task_id"] == moved))

    elif how == "duplicate_create":
        i = first(ev, lambda e: e["event_type"] == "task_created")
        dup = copy.deepcopy(ev[i])
        dup["event_id"] = "00000000-0000-4000-8000-000000000001"
        ev.insert(i + 1, dup)

    elif how == "event_after_delete":
        i = first(ev, lambda e: e["event_type"] == "task_deleted")
        ghost = copy.deepcopy(ev[i])
        ghost.update(event_id="00000000-0000-4000-8000-000000000002", event_type="task_completed", payload={},
                     occurred_at=shift(ev[i]["occurred_at"], seconds=1))
        ev.insert(i + 1, ghost)

    elif how == "event_after_complete":
        i = first(ev, lambda e: e["event_type"] == "task_completed")
        edit = copy.deepcopy(ev[i])
        edit.update(event_id="00000000-0000-4000-8000-000000000003", event_type="task_edited",
                    payload={"old_text": "a", "new_text": "b"}, occurred_at=shift(ev[i]["occurred_at"], seconds=1))
        ev.insert(i + 1, edit)

    elif how == "quadrant_mismatch":
        e = ev[first(ev, lambda e: e["event_type"] == "task_completed")]
        e["quadrant"] = "eliminate" if e["quadrant"] != "eliminate" else "do"

    elif how == "bad_move":
        e = ev[first(ev, lambda e: e["event_type"] == "task_moved")]
        e["from_quadrant"] = "eliminate" if e["from_quadrant"] != "eliminate" else "schedule"

    elif how == "bad_carry":
        e = ev[first(ev, lambda e: e["event_type"] == "task_carried_over")]
        e["payload"]["to_date"] = e["payload"]["from_date"]

    elif how == "pomodoro_sequence":
        ev.pop(first(ev, lambda e: e["event_type"] == "pomodoro_paused"))

    elif how == "pomodoro_unfinished":
        ev.pop(first(ev, lambda e: e["event_type"] in ("pomodoro_finished", "pomodoro_abandoned")))

    elif how == "pomodoro_overlap":
        pid = ev[first(ev, lambda e: e["event_type"] == "pomodoro_finished")]["pomodoro_id"]
        twin = [copy.deepcopy(e) for e in ev if e["pomodoro_id"] == pid]
        for n, e in enumerate(twin):
            e.update(event_id=f"00000000-0000-4000-8000-1{n:011d}", pomodoro_id="00000000-0000-4000-8000-0000000000ff",
                     occurred_at=shift(e["occurred_at"], minutes=1))
        ev = resort(ev + twin)

    elif how == "focus_on_closed_task":
        i = first(ev, lambda e: e["event_type"] == "task_completed")
        done = ev[i]
        start = copy.deepcopy(done)
        start.update(event_id="00000000-0000-4000-8000-000000000004", event_type="pomodoro_started",
                     pomodoro_id="00000000-0000-4000-8000-0000000000ee", payload={"planned_secs": 1500},
                     occurred_at=shift(done["occurred_at"], seconds=1))
        end = copy.deepcopy(start)
        end.update(event_id="00000000-0000-4000-8000-000000000005", event_type="pomodoro_abandoned",
                   payload={"focused_secs": 1, "planned_secs": 1500, "reason": "test"},
                   occurred_at=shift(done["occurred_at"], seconds=2))
        ev = resort(ev + [start, end])

    elif how == "focus_wrong_day":
        # a task focused on the day it was created, never carried: claim it was planned for the day before
        carried = set(task_ids_with(ev, "task_carried_over"))
        created = {e["task_id"]: e for e in ev if e["event_type"] == "task_created"}
        focus = next(e for e in ev if e["event_type"] == "pomodoro_started" and e["task_id"] not in carried
                     and created[e["task_id"]]["local_date"] == e["local_date"])
        c = created[focus["task_id"]]
        c["payload"]["date"] = (dt.date.fromisoformat(c["local_date"]) - dt.timedelta(days=1)).isoformat()

    elif how == "focus_over_planned":
        e = ev[first(ev, lambda e: e["event_type"] == "pomodoro_finished")]
        e["payload"]["focused_secs"] = e["payload"]["planned_secs"] + 60

    elif how == "focus_over_wall_clock":
        e = ev[first(ev, lambda e: e["event_type"] == "pomodoro_abandoned")]
        e["payload"]["focused_secs"] = e["payload"]["planned_secs"]

    else:
        raise ValueError(how)
    return ev


CODES = [
    "schema", "duplicate_event_id", "out_of_order", "local_date_mismatch", "event_before_create",
    "duplicate_create", "event_after_delete", "event_after_complete", "quadrant_mismatch", "bad_move",
    "bad_carry", "pomodoro_sequence", "pomodoro_unfinished", "pomodoro_overlap", "focus_on_closed_task",
    "focus_wrong_day", "focus_over_planned", "focus_over_wall_clock",
]


@pytest.mark.parametrize("code", CODES)
def test_each_check_catches_its_problem(clean, code):
    found = summarize(check(corrupt(clean, code), schema=(code == "schema")))
    assert code in found, f"expected '{code}' to be flagged, got {found}"


def test_every_documented_code_is_tested():
    import priority_sim.invariants as inv
    documented = {line.split()[0] for line in inv.__doc__.split("Codes")[1].strip().splitlines() if line.strip()}
    assert documented == set(CODES)
