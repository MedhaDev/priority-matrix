"""The JSON Schema in contracts/ is the event contract. These tests pin down
what it accepts and rejects, so it can't quietly drift."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "event.v1.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

TASK = "b8a4e0b2-3c1d-4f6a-9e2b-7d5c4a3b2e1f"
POMO = "0b6d2c1e-5f4a-4e3b-8a9c-1d2e3f4a5b6c"


def event(**overrides):
    base = {
        "event_id": "5f0c1c1e-8a0e-4c5e-9d0b-2a7f3c1e9b10",
        "schema_version": 1,
        "event_type": "task_moved",
        "task_id": TASK,
        "quadrant": "schedule",
        "from_quadrant": "do",
        "pomodoro_id": None,
        "payload": {},
        "occurred_at": "2026-10-08T13:02:11.000Z",
        "local_date": "2026-10-08",
        "timezone": "America/New_York",
        "source": "app",
    }
    base.update(overrides)
    return base


def errors(e):
    return [err.message for err in VALIDATOR.iter_errors(e)]


def test_schema_itself_is_valid():
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("e", [
    event(),  # the example from docs/event-schema.md
    event(event_type="task_created", from_quadrant=None, payload={"text": "Write tests", "date": "2026-10-08"}),
    event(event_type="task_edited", from_quadrant=None, payload={"old_text": "a", "new_text": "b"}),
    event(event_type="task_carried_over", from_quadrant=None, payload={"from_date": "2026-10-07", "to_date": "2026-10-08"}),
    event(event_type="task_completed", from_quadrant=None),
    event(event_type="pomodoro_started", from_quadrant=None, pomodoro_id=POMO, payload={"planned_secs": 1500}),
    event(event_type="pomodoro_finished", from_quadrant=None, pomodoro_id=POMO,
          payload={"focused_secs": 1500, "planned_secs": 1500, "early": False}),
    event(event_type="pomodoro_abandoned", from_quadrant=None, pomodoro_id=POMO, task_id=None, quadrant=None,
          payload={"focused_secs": 300, "planned_secs": 1500, "reason": "exited"}),
    event(source="synthetic"),
])
def test_valid_events_pass(e):
    assert errors(e) == []


@pytest.mark.parametrize("change, why", [
    ({"event_type": "task_teleported"}, "unknown event type"),
    ({"quadrant": "urgent"}, "unknown quadrant"),
    ({"from_quadrant": None}, "a move must say where it came from"),
    ({"event_type": "task_completed"}, "only moves may have from_quadrant"),
    ({"event_id": "not-a-uuid"}, "event_id must be a UUID"),
    ({"schema_version": 2}, "wrong schema version"),
    ({"local_date": "08/10/2026"}, "dates are YYYY-MM-DD"),
    ({"source": "spreadsheet"}, "unknown source"),
    ({"occurred_at": "2026-10-08T09:02:11"}, "timestamps must carry a time zone"),
    ({"pomodoro_id": POMO}, "task events have no pomodoro_id"),
    ({"extra_field": 1}, "no undeclared fields"),
])
def test_invalid_events_fail(change, why):
    assert errors(event(**change)), why


def test_required_payloads():
    created = event(event_type="task_created", from_quadrant=None, payload={"text": "x"})
    assert errors(created), "task_created needs payload.date"
    finished = event(event_type="pomodoro_finished", from_quadrant=None, pomodoro_id=POMO, payload={"planned_secs": 1500})
    assert errors(finished), "pomodoro_finished needs payload.focused_secs"
    missing = copy.deepcopy(event())
    del missing["timezone"]
    assert errors(missing), "every field is required"
