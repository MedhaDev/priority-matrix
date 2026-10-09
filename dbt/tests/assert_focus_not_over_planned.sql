-- Mirrors the generator invariant focus_over_planned: no session focuses longer than planned.
select pomodoro_id, focused_secs, planned_secs
from {{ ref('int_focus_sessions') }}
where focused_secs > planned_secs
