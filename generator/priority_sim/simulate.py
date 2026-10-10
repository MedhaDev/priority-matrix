"""Simulate a persona using the Priority Matrix app, one day at a time.

Each day has three parts:
  1. Morning   carry leftovers forward (or drop stale ones), then re-triage:
               some older urgent tasks lose their urgency      ← hypothesis 2
  2. Workday   a time-ordered queue of task arrivals, focus sessions and
               renames, processed in clock order so a session can only pick
               a task that already exists                      ← hypothesis 1
  3. Evening   tick off a few more tasks

Output: a list of events in exactly the app's format (docs/event.v1.schema.json).
All randomness, including IDs, comes from one seeded generator, so the same
persona + seed always produces exactly the same events.
"""
from __future__ import annotations

import datetime as dt
import heapq
import random
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from . import SCHEMA_VERSION

POMODORO_SECS = 25 * 60
URGENT = ("do", "delegate")
EDIT_SUFFIXES = (" (follow-up)", ": first pass", ", part 2", " for Friday")


@dataclass
class Task:
    id: str
    text: str
    quadrant: str
    category: str
    date: dt.date          # the day it's currently planned for
    created_day: dt.date


class Simulation:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.rng = random.Random(cfg["simulation"]["seed"])
        self.tz = ZoneInfo(cfg["persona"]["timezone"])
        self.events: List[Dict[str, Any]] = []
        self.open: Dict[str, Task] = {}   # tasks not yet completed or deleted

    # ── small helpers ─────────────────────────────────────────
    def uid(self) -> str:
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def between(self, span: Sequence[int]) -> int:
        return self.rng.randint(int(span[0]), int(span[1]))

    def chance(self, p: float) -> bool:
        return self.rng.random() < p

    def weighted(self, weights: Dict[str, float]) -> str:
        keys = list(weights)
        return self.rng.choices(keys, weights=[weights[k] for k in keys])[0]

    def at(self, day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
        """A local wall-clock time on `day`, with random seconds for realism."""
        return dt.datetime.combine(day, dt.time(0, 0), tzinfo=self.tz) + dt.timedelta(
            hours=hour, minutes=minute, seconds=self.rng.randint(0, 59), milliseconds=self.rng.randint(0, 999))

    def emit(self, event_type: str, when: dt.datetime, task: Optional[Task] = None, *,
             from_quadrant: Optional[str] = None, pomodoro_id: Optional[str] = None,
             payload: Optional[Dict[str, Any]] = None) -> None:
        utc = when.astimezone(dt.timezone.utc)
        self.events.append({
            "event_id": self.uid(),
            "schema_version": SCHEMA_VERSION,
            "event_type": event_type,
            "task_id": task.id if task else None,
            "quadrant": task.quadrant if task else None,
            "from_quadrant": from_quadrant,
            "pomodoro_id": pomodoro_id,
            "payload": payload or {},
            "occurred_at": utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z",
            "local_date": when.astimezone(self.tz).date().isoformat(),
            "timezone": self.cfg["persona"]["timezone"],
            "source": "synthetic",
        })

    # ── the simulation ────────────────────────────────────────
    def run(self, through: Optional[dt.date] = None) -> List[Dict[str, Any]]:
        """Simulate from start_date through `through` (default: start_date + days - 1).

        Days are simulated in order from one random stream, so the first N days
        come out identical no matter how far the simulation runs. That's what
        lets Airflow generate one day at a time and get the same data.
        """
        start: dt.date = self.cfg["simulation"]["start_date"]
        last = through or start + dt.timedelta(days=self.cfg["simulation"]["days"] - 1)
        day = start
        while day <= last:
            self.simulate_day(day)
            day += dt.timedelta(days=1)
        # Within a day events are already in order; sort anyway so the
        # contract "events are in time order" never depends on loop details.
        self.events.sort(key=lambda e: e["occurred_at"])
        return self.events

    def simulate_day(self, day: dt.date) -> None:
        weekend = day.weekday() >= 5
        kind = "weekend" if weekend else "weekday"
        self.morning(day)

        # Build the day's queue: (time, tiebreak, action, data)
        queue: List[Tuple[dt.datetime, int, str, Any]] = []
        seq = 0

        def push(when: dt.datetime, action: str, data: Any = None) -> None:
            nonlocal seq
            heapq.heappush(queue, (when, seq, action, data))
            seq += 1

        n_tasks = self.between(self.cfg["planning"]["new_tasks_per_day"][kind])
        if day.weekday() == 0:
            n_tasks = round(n_tasks * self.cfg["planning"]["monday_overcommit"])
        for _ in range(n_tasks):
            if self.chance(0.6):   # planned in the morning…
                push(self.at(day, 8, self.rng.randint(0, 40)), "arrive")
            else:                  # …or lands during the day as a request
                push(self.at(day, self.rng.randint(9, 16), self.rng.randint(0, 59)), "arrive")

        focus = self.cfg["focus"]
        sessions = self.between(focus["sessions_per_day"][kind])
        if sessions:
            push(self.at(day, self.between(focus["first_session_hour"]), self.rng.randint(0, 59)), "session", sessions)

        while queue:
            when, _, action, data = heapq.heappop(queue)
            if action == "arrive":
                task = self.create_task(day, when, kind)
                if task and self.chance(self.cfg["completion"]["edit_chance"]):
                    edit_at = when + dt.timedelta(minutes=self.rng.randint(20, 240))
                    if edit_at.hour < self.cfg["completion"]["evening_hour"]:   # never after the evening sweep
                        push(edit_at, "edit", task.id)
            elif action == "edit":
                self.rename(data, when)
            elif action == "session":
                end = self.focus_session(day, when)
                remaining = data - 1
                if remaining > 0:
                    nxt = (end or when) + dt.timedelta(minutes=self.between(focus["break_minutes"]))
                    lunch_start, lunch_end = focus["lunch"]
                    if lunch_start <= nxt.hour < lunch_end:
                        nxt = self.at(day, lunch_end, self.rng.randint(0, 30))
                    if nxt.hour < focus["last_start_hour"]:
                        push(nxt, "session", remaining)

        self.evening(day)

    # 1. Morning ────────────────────────────────────────────────
    def morning(self, day: dt.date) -> None:
        clock = self.at(day, 7, 40)
        plan = self.cfg["planning"]
        for task in list(self.open.values()):
            if task.date >= day:
                continue
            clock += dt.timedelta(seconds=self.rng.randint(5, 40))
            if (day - task.created_day).days > plan["drop_after_days"] and self.chance(plan["drop_chance"]):
                self.emit("task_deleted", clock, task, payload={"text": task.text, "was_done": False})
                del self.open[task.id]
            else:
                self.emit("task_carried_over", clock, task,
                          payload={"from_date": task.date.isoformat(), "to_date": day.isoformat()})
                task.date = day

        # Re-triage: urgent tasks from earlier days quietly lose their urgency (hypothesis 2).
        clock = max(clock, self.at(day, 7, 50))
        urgency = self.cfg["urgency"]
        for task in list(self.open.values()):
            if task.created_day == day or task.quadrant not in URGENT:
                continue
            if self.chance(urgency["morning_downgrade_chance"]):
                clock += dt.timedelta(seconds=self.rng.randint(10, 60))
                old = task.quadrant
                task.quadrant = self.weighted(urgency["downgrade_to"][old])
                self.emit("task_moved", clock, task, from_quadrant=old)

    # 2a. New tasks ─────────────────────────────────────────────
    def create_task(self, day: dt.date, when: dt.datetime, kind: str) -> Optional[Task]:
        category = self.weighted(self.cfg["task_mix"][kind])
        quadrant = self.weighted(self.cfg["planning"]["create_mix"])
        taken = {t.text for t in self.open.values()}
        free = [t for t in self.cfg["tasks"][category][quadrant] if t not in taken]
        if not free:   # every idea in this pile is already on the list
            return None
        task = Task(self.uid(), self.rng.choice(free), quadrant, category, day, day)
        self.open[task.id] = task
        self.emit("task_created", when, task, payload={"text": task.text, "date": day.isoformat()})
        return task

    def rename(self, task_id: str, when: dt.datetime) -> None:
        task = self.open.get(task_id)
        if task is None or task.date != when.astimezone(self.tz).date():
            return   # finished, deleted or moved on before the rename
        old = task.text
        task.text = old + self.rng.choice(EDIT_SUFFIXES)
        self.emit("task_edited", when, task, payload={"old_text": old, "new_text": task.text})

    # 2b. Focus sessions (hypothesis 1) ─────────────────────────
    def focus_session(self, day: dt.date, start: dt.datetime) -> Optional[dt.datetime]:
        today = [t for t in self.open.values() if t.date == day]
        if not today:
            return None
        focus = self.cfg["focus"]
        wanted = self.weighted(focus["quadrant_mix"])
        preferred = focus["prefer_category"]["weekend" if day.weekday() >= 5 else "weekday"]
        # Most specific match first: right quadrant AND right kind of task, then loosen.
        pool = ([t for t in today if t.quadrant == wanted and t.category == preferred]
                or [t for t in today if t.quadrant == wanted]
                or [t for t in today if t.category == preferred]
                or today)
        task = self.rng.choice(pool)

        period = "morning" if start.hour < 12 else "afternoon"
        abandon = self.chance(focus["abandon_chance"][period])
        focused_min = self.between(focus["abandoned_after_minutes"]) if abandon else POMODORO_SECS // 60
        pid = self.uid()

        self.emit("pomodoro_started", start, task, pomodoro_id=pid, payload={"planned_secs": POMODORO_SECS})
        end = start + dt.timedelta(minutes=focused_min)
        if focused_min > 6 and self.chance(focus["pause_chance"]):
            paused_at = start + dt.timedelta(minutes=self.rng.randint(2, focused_min - 2))
            gap = dt.timedelta(minutes=self.rng.randint(2, 6))
            self.emit("pomodoro_paused", paused_at, task, pomodoro_id=pid)
            self.emit("pomodoro_resumed", paused_at + gap, task, pomodoro_id=pid)
            end += gap

        if abandon:
            self.emit("pomodoro_abandoned", end, task, pomodoro_id=pid,
                      payload={"focused_secs": focused_min * 60, "planned_secs": POMODORO_SECS, "reason": "interrupted"})
        else:
            self.emit("pomodoro_finished", end, task, pomodoro_id=pid,
                      payload={"focused_secs": POMODORO_SECS, "planned_secs": POMODORO_SECS, "early": False})
            if self.chance(self.cfg["completion"]["after_focus_chance"]):
                self.emit("task_completed", end + dt.timedelta(minutes=1), task)
                del self.open[task.id]
        return end

    # 3. Evening ────────────────────────────────────────────────
    def evening(self, day: dt.date) -> None:
        done = self.cfg["completion"]
        clock = self.at(day, done["evening_hour"], self.rng.randint(0, 20))
        for task in list(self.open.values()):
            if task.date == day and self.chance(done["evening_chance"][task.quadrant]):
                clock += dt.timedelta(minutes=self.rng.randint(1, 4))
                self.emit("task_completed", clock, task)
                del self.open[task.id]


def simulate(cfg: Dict[str, Any], through: Optional[dt.date] = None) -> List[Dict[str, Any]]:
    """Run the simulation for a validated persona config."""
    return Simulation(cfg).run(through)
