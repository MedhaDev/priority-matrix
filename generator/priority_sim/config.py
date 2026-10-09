"""Load and check a persona settings file (personas/*.yaml).

Bad settings fail loudly here, before any data is generated, with every
problem listed at once.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

QUADRANTS = ("do", "schedule", "delegate", "eliminate")


class ConfigError(ValueError):
    """Raised when a persona file has one or more invalid settings."""


def load_persona(path: str | Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    problems = validate(cfg)
    if problems:
        raise ConfigError(f"{path}:\n  - " + "\n  - ".join(problems))
    return cfg


def _get(cfg: Dict[str, Any], dotted: str) -> Any:
    node: Any = cfg
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            raise KeyError(dotted)
        node = node[key]
    return node


def validate(cfg: Any) -> List[str]:
    if not isinstance(cfg, dict):
        return ["file is empty or not a mapping"]
    problems: List[str] = []

    def need(dotted: str) -> Any:
        try:
            return _get(cfg, dotted)
        except KeyError:
            problems.append(f"missing setting: {dotted}")
            return None

    def chance(dotted: str) -> None:
        v = need(dotted)
        if v is not None and not (isinstance(v, (int, float)) and 0 <= v <= 1):
            problems.append(f"{dotted} must be between 0 and 1 (got {v!r})")

    def mix(dotted: str, keys=QUADRANTS) -> None:
        v = need(dotted)
        if v is None:
            return
        if not isinstance(v, dict) or not set(v) <= set(keys):
            problems.append(f"{dotted} may only use keys {list(keys)} (got {v!r})")
            return
        if any(not isinstance(x, (int, float)) or x < 0 for x in v.values()):
            problems.append(f"{dotted} values must be non-negative numbers")
        elif abs(sum(v.values()) - 1) > 1e-6:
            problems.append(f"{dotted} must add up to 1.0 (got {sum(v.values()):.2f})")

    def span(dotted: str, lo: float = 0, hi: float = float("inf")) -> None:
        v = need(dotted)
        if v is None:
            return
        if (not isinstance(v, list) or len(v) != 2 or not all(isinstance(x, (int, float)) for x in v)
                or v[0] > v[1] or v[0] < lo or v[1] > hi):
            problems.append(f"{dotted} must be [min, max] with {lo} <= min <= max <= {hi} (got {v!r})")

    # persona + simulation
    need("persona.name")
    tz = need("persona.timezone")
    if tz:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            problems.append(f"persona.timezone is not a known time zone: {tz!r}")
    start = need("simulation.start_date")
    if start is not None and not isinstance(start, dt.date):
        problems.append(f"simulation.start_date must be a date like 2026-06-10 (got {start!r})")
    days = need("simulation.days")
    if days is not None and not (isinstance(days, int) and 1 <= days <= 3650):
        problems.append(f"simulation.days must be a whole number from 1 to 3650 (got {days!r})")
    seed = need("simulation.seed")
    if seed is not None and not isinstance(seed, int):
        problems.append(f"simulation.seed must be a whole number (got {seed!r})")

    # planning
    span("planning.new_tasks_per_day.weekday", 0, 50)
    span("planning.new_tasks_per_day.weekend", 0, 50)
    m = need("planning.monday_overcommit")
    if m is not None and not (isinstance(m, (int, float)) and m > 0):
        problems.append("planning.monday_overcommit must be a positive number")
    mix("planning.create_mix")
    need("planning.drop_after_days")
    chance("planning.drop_chance")

    # urgency (hypothesis 2)
    chance("urgency.morning_downgrade_chance")
    mix("urgency.downgrade_to.do", ("schedule", "eliminate"))
    mix("urgency.downgrade_to.delegate", ("schedule", "eliminate"))

    # focus (hypothesis 1)
    span("focus.sessions_per_day.weekday", 0, 20)
    span("focus.sessions_per_day.weekend", 0, 20)
    mix("focus.quadrant_mix")
    span("focus.first_session_hour", 0, 23)
    need("focus.last_start_hour")
    span("focus.lunch", 0, 23)
    span("focus.break_minutes", 0, 240)
    chance("focus.pause_chance")
    chance("focus.abandon_chance.morning")
    chance("focus.abandon_chance.afternoon")
    span("focus.abandoned_after_minutes", 1, 24)

    # completion
    chance("completion.after_focus_chance")
    for q in QUADRANTS:
        chance(f"completion.evening_chance.{q}")
    need("completion.evening_hour")
    chance("completion.edit_chance")

    # mess (data problems injected on purpose)
    for key in ("duplicate_rate", "late_rate", "dropped_rate", "naive_timestamp_rate", "malformed_rate"):
        chance(f"mess.{key}")
    span("mess.late_days", 1, 30)

    # task library: every category used in task_mix needs tasks for all four quadrants
    tasks = need("tasks")
    if isinstance(tasks, dict):
        categories = tuple(tasks)
        mix("task_mix.weekday", categories)
        mix("task_mix.weekend", categories)
        for kind in ("weekday", "weekend"):
            pref = need(f"focus.prefer_category.{kind}")
            if pref is not None and pref not in categories:
                problems.append(f"focus.prefer_category.{kind} must be one of {list(categories)} (got {pref!r})")
        for cat, pools in tasks.items():
            for q in QUADRANTS:
                pool = pools.get(q) if isinstance(pools, dict) else None
                if not pool or not all(isinstance(t, str) and t.strip() for t in pool):
                    problems.append(f"tasks.{cat}.{q} needs at least one task name")
                elif len(set(pool)) != len(pool):
                    problems.append(f"tasks.{cat}.{q} has duplicate task names")
    elif tasks is not None:
        problems.append("tasks must be a mapping of category → quadrant → list of task names")

    return problems
