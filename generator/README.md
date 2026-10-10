# priority-sim

Simulates a synthetic version of me ("Medha (simulated)") using the Priority Matrix app for months and
writes their event log in exactly the app's format
([contract](../docs/event.v1.schema.json), [docs](../docs/event-schema.md)).

The public pipeline and dashboard run on this data, never on my real data. The habits are my own estimates, tagged in the persona file as ✔ (I said so), ★ (planted hypothesis) or ~ (assumption to correct).

- **Planted truth**: habits are set in [`personas/medha.yaml`](personas/medha.yaml), so the
  analysis has a known right answer to recover.
- **Deterministic**: the same persona + seed always produces the same data.

## Setup

```bash
cd generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Generate

```bash
python -m priority_sim                       # every day in the persona's range → data/
python -m priority_sim --date 2026-09-15     # only the file for one arrival day (what Airflow runs)
python -m priority_sim --seeds-dir ../dbt/seeds   # also write the answer key for dbt tests
```

| Output | What it is |
|---|---|
| `data/raw/arrived_on=YYYY-MM-DD/events.jsonl` | what ingestion receives, one file per arrival day (late events land in later files) |
| `data/truth.json` | answer key. `full`: the clean data. `recoverable`: what a correct pipeline can report from what arrived |
| `data/manifest.json` | every injected problem (duplicates, late, dropped, naive timestamps, malformed), with event_ids |

Every event's fate depends only on its own id, so a day's file is byte-identical whether
generated alone or in a full run. Reruns and backfills are safe.

## Test

```bash
pytest
```

80 tests: the contract, the settings checker, 18 story invariants (each proven to fire),
the answer key on hand-worked examples, the mess layer, and day-by-day stability.
