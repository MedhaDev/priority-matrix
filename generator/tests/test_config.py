import copy
from pathlib import Path

import pytest
import yaml

from priority_sim.config import ConfigError, load_persona, validate

PERSONA = Path(__file__).resolve().parents[1] / "personas" / "medha.yaml"


@pytest.fixture
def persona():
    return yaml.safe_load(PERSONA.read_text())


def test_persona_loads():
    cfg = load_persona(PERSONA)
    assert cfg["persona"]["name"] == "Medha (simulated)"
    assert cfg["simulation"]["days"] == 120


def test_persona_has_no_problems(persona):
    assert validate(persona) == []


def test_mix_must_add_up(persona):
    bad = copy.deepcopy(persona)
    bad["planning"]["create_mix"]["do"] = 0.9
    assert any("create_mix must add up to 1.0" in p for p in validate(bad))


def test_chance_must_be_0_to_1(persona):
    bad = copy.deepcopy(persona)
    bad["urgency"]["morning_downgrade_chance"] = 1.4
    assert any("morning_downgrade_chance" in p for p in validate(bad))


def test_unknown_quadrant_rejected(persona):
    bad = copy.deepcopy(persona)
    bad["focus"]["quadrant_mix"] = {"do": 0.5, "someday": 0.5}
    assert any("quadrant_mix may only use keys" in p for p in validate(bad))


def test_reversed_range_rejected(persona):
    bad = copy.deepcopy(persona)
    bad["focus"]["sessions_per_day"]["weekday"] = [6, 3]
    assert any("sessions_per_day.weekday" in p for p in validate(bad))


def test_bad_timezone_rejected(persona):
    bad = copy.deepcopy(persona)
    bad["persona"]["timezone"] = "Mars/Olympus_Mons"
    assert any("timezone" in p for p in validate(bad))


def test_every_problem_reported_at_once(persona, tmp_path):
    bad = copy.deepcopy(persona)
    bad["planning"]["create_mix"]["do"] = 0.9
    bad["focus"]["pause_chance"] = -1
    del bad["completion"]["evening_hour"]
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(ConfigError) as exc:
        load_persona(path)
    message = str(exc.value)
    assert "create_mix" in message and "pause_chance" in message and "evening_hour" in message


def test_task_library_needs_every_quadrant(persona):
    bad = copy.deepcopy(persona)
    bad["tasks"]["personal"]["delegate"] = []
    assert any("tasks.personal.delegate needs at least one task" in p for p in validate(bad))


def test_task_mix_only_uses_known_categories(persona):
    bad = copy.deepcopy(persona)
    bad["task_mix"]["weekend"] = {"side_project": 0.5, "napping": 0.5}
    assert any("task_mix.weekend may only use keys" in p for p in validate(bad))
