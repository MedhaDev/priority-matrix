"""The answer key must be right, so test it on tiny logs with hand-worked answers."""
import json
from pathlib import Path

import pytest

from priority_sim.config import load_persona
from priority_sim.simulate import simulate
from priority_sim.truth import compute_truth, downgrade_truth, focus_truth

PERSONA = Path(__file__).resolve().parents[1] / "personas" / "medha.yaml"


def ev(kind, at, task=None, quadrant=None, frm=None, **payload):
    """A minimal event: only the fields the truth calculations read."""
    return {"event_type": kind, "occurred_at": at, "local_date": at[:10], "task_id": task,
            "quadrant": quadrant, "from_quadrant": frm, "payload": payload}


# ── hypothesis 1: focus time ─────────────────────────────────
def test_focus_by_quadrant_and_day():
    log = [
        ev("pomodoro_finished", "2026-07-01T14:00:00.000Z", "a", "do", focused_secs=1500),
        ev("pomodoro_finished", "2026-07-01T15:00:00.000Z", "a", "do", focused_secs=1500),
        ev("pomodoro_abandoned", "2026-07-01T16:00:00.000Z", "b", "schedule", focused_secs=600),
        ev("pomodoro_started", "2026-07-02T13:35:00.000Z", "b", "schedule", planned_secs=1500),  # ignored
        ev("pomodoro_finished", "2026-07-02T14:00:00.000Z", "b", "schedule", focused_secs=1500),
    ]
    t = focus_truth(log)
    assert t["total_focused_secs"] == 5100
    assert t["focused_secs_by_quadrant"] == {"do": 3000, "schedule": 2100, "delegate": 0, "eliminate": 0}
    assert t["share_by_quadrant"]["do"] == pytest.approx(3000 / 5100, abs=1e-4)
    assert t["do_vs_schedule_ratio"] == pytest.approx(3000 / 2100, abs=1e-3)
    assert t["sessions"] == {"finished": 3, "abandoned": 1}
    assert t["daily"] == [
        {"local_date": "2026-07-01", "quadrant": "do", "focused_secs": 3000, "sessions": 2},
        {"local_date": "2026-07-01", "quadrant": "schedule", "focused_secs": 600, "sessions": 1},
        {"local_date": "2026-07-02", "quadrant": "schedule", "focused_secs": 1500, "sessions": 1},
    ]


def test_no_focus_at_all():
    t = focus_truth([])
    assert t["total_focused_secs"] == 0 and t["do_vs_schedule_ratio"] is None and t["daily"] == []


# ── hypothesis 2: downgrades ─────────────────────────────────
def test_downgrade_definitions():
    log = [
        # A: urgent, downgraded after 23h → counts, within 72h
        ev("task_created", "2026-07-01T09:00:00.000Z", "A", "do"),
        # B: urgent, finished the same day → never had a chance
        ev("task_created", "2026-07-01T09:00:00.000Z", "B", "do"),
        ev("task_completed", "2026-07-01T17:00:00.000Z", "B", "do"),
        # C: urgent, downgraded after 95h → counts, but NOT within 72h
        ev("task_created", "2026-07-01T09:00:00.000Z", "C", "delegate"),
        # D: not urgent; becoming urgent is not a downgrade
        ev("task_created", "2026-07-01T09:00:00.000Z", "D", "schedule"),
        # E: urgent → urgent first (not a downgrade), then do → eliminate after 50h
        ev("task_created", "2026-07-01T09:00:00.000Z", "E", "delegate"),
        ev("task_moved", "2026-07-02T08:00:00.000Z", "A", "schedule", "do"),
        ev("task_moved", "2026-07-02T08:00:00.000Z", "D", "do", "schedule"),
        ev("task_moved", "2026-07-02T09:00:00.000Z", "E", "do", "delegate"),
        ev("task_moved", "2026-07-03T11:00:00.000Z", "E", "eliminate", "do"),
        ev("task_carried_over", "2026-07-02T07:40:00.000Z", "C", "delegate"),
        ev("task_moved", "2026-07-05T08:00:00.000Z", "C", "eliminate", "delegate"),
        ev("task_moved", "2026-07-06T08:00:00.000Z", "A", "do", "schedule"),   # later moves don't matter
    ]
    log.sort(key=lambda e: e["occurred_at"])
    t = downgrade_truth(log)
    assert t["urgent_tasks"] == 4                       # A, B, C, E
    assert t["downgraded"] == 3                         # A, C, E
    assert t["downgraded_within_72h"] == 2              # A (23h), E (50h)
    assert t["rate"] == 0.75
    assert t["rate_within_72h"] == 0.5
    assert t["urgent_tasks_open_next_morning"] == 3     # A, C, E (B was done on day one)
    assert t["rate_among_open_next_morning"] == 1.0
    assert t["median_days_to_downgrade"] == pytest.approx(50 / 24, abs=1e-3)


def test_no_urgent_tasks():
    t = downgrade_truth([ev("task_created", "2026-07-01T09:00:00.000Z", "D", "schedule")])
    assert t["urgent_tasks"] == 0 and t["rate"] is None and t["median_days_to_downgrade"] is None


# ── the real simulation ──────────────────────────────────────
@pytest.fixture(scope="module")
def truth():
    cfg = load_persona(PERSONA)
    return compute_truth(simulate(cfg), cfg)


def test_truth_is_json_and_deterministic(truth):
    cfg = load_persona(PERSONA)
    again = compute_truth(simulate(cfg), cfg)
    assert json.dumps(truth, sort_keys=True) == json.dumps(again, sort_keys=True)


def test_daily_rows_add_up(truth):
    h1 = truth["hypothesis_1_focus"]
    assert sum(r["focused_secs"] for r in h1["daily"]) == h1["total_focused_secs"]
    assert sum(r["sessions"] for r in h1["daily"]) == sum(h1["sessions"].values())


def test_planted_hypotheses_show_up(truth):
    """Not exact numbers, just that the planted pattern is visible.

    Note: the realized Do-first share is LOWER than the planted 66%. When Do
    first is empty, sessions fall back to whatever is open (mostly the Schedule
    backlog). A preference isn't an outcome: you can only focus on what's on
    your list. So we test the hypothesis itself, not the planted number.
    """
    share = truth["hypothesis_1_focus"]["share_by_quadrant"]
    assert share["do"] == max(share.values())
    assert share["do"] > share["schedule"]
    h2 = truth["hypothesis_2_downgrades"]
    assert h2["downgraded"] > 0
    assert h2["median_days_to_downgrade"] <= 3
