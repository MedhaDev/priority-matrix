"""Weekly review: the week's metrics, plus a short commentary written by Claude.

  python review/weekly_review.py --week-ending 2026-10-04            # writes reviews/2026-W40.md
  python review/weekly_review.py --week-ending 2026-10-04 --dry-run  # show the prompt, don't call the API

Numbers come from SQL (the dbt marts) and are written by this script as a table.
Claude only writes the commentary, and is told to use only the numbers it's given,
so every figure in the review is traceable to the warehouse.

Needs ANTHROPIC_API_KEY (or an `ant auth login` profile) in the environment.
Runs from the Airflow DAG on Sundays when a key is configured.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "warehouse"))
from export import fetch  # noqa: E402  (same connection logic as the CSV export)

MODEL = "claude-opus-5-5"
QUADRANTS = [("do", "Do first"), ("schedule", "Schedule"), ("delegate", "Delegate"), ("eliminate", "Eliminate")]

SYSTEM = """You write a short weekly review of someone's focus and prioritization data from a \
productivity app (Eisenhower Matrix + Pomodoro timer). The person is a research data specialist; \
the data comes from a simulation of their own working habits.

Write in plain, direct language, second person ("you"), like a thoughtful colleague. No hype, no \
emojis, no headings other than the three below. Use only the numbers provided; do not invent or \
estimate any figure. If a number is small or the week is partial, say so rather than drawing a \
strong conclusion. Keep it under 220 words.

Format (Markdown):
**What happened.** 2-3 sentences on where focus time went compared with what was on the list.
**Pattern to watch.** 1-3 sentences on urgency (tasks marked urgent that were later downgraded) \
or tasks being carried over day after day.
**One experiment for next week.** One concrete, small change to try, tied to the numbers."""


def iso_week(day: dt.date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def week_metrics(target: str, start: dt.date, end: dt.date) -> Dict[str, Any]:
    s, e = start.isoformat(), end.isoformat()

    def one(sql):
        return fetch(target, sql)[1]

    focus = {q: 0 for q, _ in QUADRANTS}
    finished = abandoned = 0
    for q, secs, fin, ab in one(f"""
        select quadrant, sum(focused_secs), sum(sessions_finished), sum(sessions_abandoned)
        from marts.daily_focus_metrics where focus_date between '{s}' and '{e}' group by quadrant"""):
        focus[q] = int(secs)
        finished += int(fin)
        abandoned += int(ab)
    on_list = {q: 0 for q, _ in QUADRANTS}
    for q, n in one(f"""
        select quadrant, count(*) from intermediate.int_task_days
        where plan_date between '{s}' and '{e}' group by quadrant"""):
        on_list[q] = int(n)
    urgent = one(f"""
        select count(*), sum(case when downgraded then 1 else 0 end),
               sum(case when downgraded_within_72h then 1 else 0 end),
               sum(case when open_next_morning then 1 else 0 end)
        from marts.h2_urgent_tasks where created_date between '{s}' and '{e}'""")[0]
    carried = one("""
        select task_text, current_quadrant, carry_count from marts.dim_tasks
        where status = 'open' and carry_count >= 3 order by carry_count desc, task_text limit 3""")

    total_focus, total_list = sum(focus.values()), sum(on_list.values())
    share = lambda part, whole: round(part / whole, 3) if whole else None
    return {
        "week": iso_week(end),
        "dates": f"{start.isoformat()} to {end.isoformat()}",
        "focus_hours": round(total_focus / 3600, 1),
        "sessions": {"finished": finished, "abandoned": abandoned},
        "by_quadrant": [
            {"quadrant": label, "focus_hours": round(focus[q] / 3600, 1),
             "share_of_focus": share(focus[q], total_focus), "share_of_list": share(on_list[q], total_list)}
            for q, label in QUADRANTS
        ],
        "urgent_tasks_created": int(urgent[0] or 0),
        "urgent_later_downgraded": int(urgent[1] or 0),
        "urgent_downgraded_within_72h": int(urgent[2] or 0),
        "urgent_still_open_next_morning": int(urgent[3] or 0),
        "note_on_recent_tasks": "tasks created late in the week may not have been downgraded yet",
        "most_carried_open_tasks": [{"task": t, "quadrant": q, "days_carried": int(c)} for t, q, c in carried],
    }


def metrics_table(m: Dict[str, Any]) -> str:
    pct = lambda x: "–" if x is None else f"{x:.0%}"
    rows = ["| Quadrant | Focus | Share of focus | Share of list |", "|---|---:|---:|---:|"]
    rows += [f"| {r['quadrant']} | {r['focus_hours']}h | {pct(r['share_of_focus'])} | {pct(r['share_of_list'])} |"
             for r in m["by_quadrant"]]
    s = m["sessions"]
    lines = [
        "\n".join(rows), "",
        f"- Focus: **{m['focus_hours']}h** over {s['finished'] + s['abandoned']} sessions ({s['abandoned']} abandoned)",
        f"- Urgent tasks created: **{m['urgent_tasks_created']}**, later downgraded: **{m['urgent_later_downgraded']}** "
        f"({m['urgent_downgraded_within_72h']} within 72h)",
    ]
    if m["most_carried_open_tasks"]:
        lines.append("- Carried the longest: " + "; ".join(
            f"{t['task']} ({t['days_carried']} days)" for t in m["most_carried_open_tasks"]))
    return "\n".join(lines)


def write_commentary(m: Dict[str, Any]) -> str:
    import anthropic

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            output_config={"effort": "medium"},
            # If a safety classifier declines, the API re-runs on its recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": "This week's numbers:\n\n" + json.dumps(m, indent=2)}],
        )
    except anthropic.RateLimitError:
        raise SystemExit("Rate limited by the Claude API; the DAG will retry.")
    except anthropic.APIStatusError as e:
        raise SystemExit(f"Claude API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise SystemExit("Couldn't reach the Claude API; the DAG will retry.")

    if response.stop_reason == "refusal":
        return "_The review couldn't be generated this week (the request was declined)._"
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if response.stop_reason == "max_tokens":
        text += "\n\n_(cut off)_"
    return text


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Write the weekly review")
    p.add_argument("--week-ending", type=dt.date.fromisoformat, required=True, help="last day of the week (usually a Sunday)")
    p.add_argument("--target", choices=["duckdb", "postgres"], default=os.environ.get("WAREHOUSE_TARGET", "duckdb"))
    p.add_argument("--out", type=Path, default=ROOT / "reviews")
    p.add_argument("--dry-run", action="store_true", help="print the metrics and prompt; don't call the API")
    args = p.parse_args(argv)

    end = args.week_ending
    m = week_metrics(args.target, end - dt.timedelta(days=6), end)

    if args.dry_run:
        print(metrics_table(m))
        print("\n--- system prompt ---\n" + SYSTEM)
        print("\n--- user message ---\nThis week's numbers:\n\n" + json.dumps(m, indent=2))
        return 0

    commentary = write_commentary(m)
    doc = (
        f"# Weekly review · {m['week']}\n\n"
        f"_{m['dates']} · synthetic data (Medha, simulated) · commentary by {MODEL}, numbers from the warehouse_\n\n"
        f"{metrics_table(m)}\n\n{commentary}\n"
    )
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{m['week']}.md"
    path.write_text(doc, encoding="utf-8")
    print(f"review → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
