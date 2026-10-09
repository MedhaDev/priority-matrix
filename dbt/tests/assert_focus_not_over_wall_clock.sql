-- Mirrors focus_over_wall_clock: focused time can't exceed the time that actually passed.
select pomodoro_id, focused_secs, wall_clock_secs
from {{ ref('int_focus_sessions') }}
where is_complete and focused_secs > wall_clock_secs + 1
