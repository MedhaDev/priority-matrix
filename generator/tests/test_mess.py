"""The injected problems must be recorded, detectable, and stable per day."""
import copy
import datetime as dt
import json
import math
from pathlib import Path

import pytest

from priority_sim.cli import build, main
from priority_sim.config import load_persona
from priority_sim.invariants import check, summarize
from priority_sim.mess import add_mess
from priority_sim.simulate import simulate
from priority_sim.staging import repair_timestamp, stage

PERSONA = Path(__file__).resolve().parents[1] / "personas" / "medha.yaml"


def cfg_with(**mess):
    cfg = load_persona(PERSONA)
    cfg["mess"].update(mess)
    return cfg


@pytest.fixture(scope="module")
def built():
    cfg = load_persona(PERSONA)
    clean = simulate(cfg)
    deliveries, manifest = add_mess(clean, cfg)
    return cfg, clean, deliveries, manifest


def ids(manifest, problem):
    return {e["event_id"] for e in manifest["problems"][problem]["events"]}


def test_clean_input_untouched(built):
    cfg, clean, _, _ = built
    before = copy.deepcopy(clean)
    add_mess(clean, cfg)
    assert clean == before


def test_counts_match_rates_and_rows_add_up(built):
    cfg, clean, deliveries, manifest = built
    n, p = len(clean), manifest["problems"]
    for name, key in [("duplicates", "duplicate_rate"), ("late_arrivals", "late_rate"), ("dropped", "dropped_rate"),
                      ("naive_timestamps", "naive_timestamp_rate"), ("malformed", "malformed_rate")]:
        expected = n * cfg["mess"][key]
        assert abs(p[name]["count"] - expected) <= 4 * math.sqrt(expected) + 3, name
    assert len(deliveries) == n - p["dropped"]["count"] + p["duplicates"]["count"]


def test_each_event_has_at_most_one_problem(built):
    _, _, _, manifest = built
    sets = [ids(manifest, name) for name in manifest["problems"]]
    assert sum(len(s) for s in sets) == len(set().union(*sets))


def test_late_events_arrive_later_and_nothing_else_does(built):
    _, _, deliveries, manifest = built
    late = ids(manifest, "late_arrivals")
    for d in deliveries:
        e = d["event"]
        assert (d["arrived_on"] > e["local_date"]) == (e["event_id"] in late)


def test_problems_are_detectable(built):
    _, _, deliveries, manifest = built
    violations = check([d["event"] for d in deliveries])
    found = summarize(violations)
    assert found["duplicate_event_id"] == manifest["problems"]["duplicates"]["count"]
    schema_ids = {v.event_id for v in violations if v.code == "schema"}
    assert schema_ids == ids(manifest, "naive_timestamps") | ids(manifest, "malformed")
    assert found.get("out_of_order", 0) > 0


def test_naive_timestamps_repair_exactly(built):
    _, clean, deliveries, manifest = built
    original = {e["event_id"]: e["occurred_at"] for e in clean}
    naive = ids(manifest, "naive_timestamps")
    assert naive
    for d in deliveries:
        if d["event"]["event_id"] in naive:
            assert repair_timestamp(d["event"])["occurred_at"] == original[d["event"]["event_id"]]


def test_staging_quarantines_exactly_the_malformed_rows(built):
    _, _, deliveries, manifest = built
    _, quarantined = stage([d["event"] for d in deliveries])
    assert {q["event_id"] for q in quarantined} == ids(manifest, "malformed")


def test_staging_fully_fixes_duplicates_late_and_naive():
    cfg = cfg_with(dropped_rate=0.0, malformed_rate=0.0)
    deliveries, _ = add_mess(simulate(cfg), cfg)
    staged, _ = stage([d["event"] for d in deliveries])
    assert summarize(check(staged)) == {}
    assert staged == simulate(cfg)   # byte-for-byte the clean data again


def test_removed_rows_leave_orphans(built):
    """Dropped and quarantined rows are lost: their task's later events become orphans."""
    _, _, deliveries, _ = built
    staged, _ = stage([d["event"] for d in deliveries])
    leftover = summarize(check(staged))
    assert leftover and not {"schema", "duplicate_event_id", "out_of_order"} & set(leftover)


# ── stable per day: what Airflow relies on ───────────────────
def test_a_days_file_does_not_depend_on_the_horizon():
    cfg = load_persona(PERSONA)
    day = dt.date(2026, 9, 15)
    short = build(cfg, day)["arrived"]
    long = build(cfg, day + dt.timedelta(days=20))["arrived"]
    rows = lambda ds: [d["event"] for d in ds if d["arrived_on"] == day.isoformat()]
    assert rows(short) == rows(long) and rows(short)


def test_cli_single_day_matches_full_run(tmp_path):
    full, single = tmp_path / "full", tmp_path / "single"
    assert main(["--out", str(full), "--through", "2026-07-15"]) == 0
    assert main(["--out", str(single), "--date", "2026-07-12"]) == 0
    name = "raw/arrived_on=2026-07-12/events.jsonl"
    assert (full / name).read_bytes() == (single / name).read_bytes()
    assert main(["--out", str(single), "--date", "2026-07-12"]) == 0      # rerun: identical
    assert (full / name).read_bytes() == (single / name).read_bytes()


def test_cli_writes_truth_manifest_and_seeds(tmp_path):
    assert main(["--out", str(tmp_path / "d"), "--through", "2026-07-31", "--seeds-dir", str(tmp_path / "s")]) == 0
    truth = json.loads((tmp_path / "d" / "truth.json").read_text())
    assert truth["horizon"] == "2026-07-31" and truth["full"]["events"] >= truth["recoverable"]["events"]
    for f in ("truth_daily_focus.csv", "truth_summary.csv", "expected_quarantine.csv"):
        assert (tmp_path / "s" / f).exists()


def test_cli_rejects_bad_persona(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text(PERSONA.read_text().replace("pause_chance: 0.20", "pause_chance: 3"))
    assert main(["--persona", str(bad), "--out", str(tmp_path)]) == 2
    assert "pause_chance" in capsys.readouterr().err
