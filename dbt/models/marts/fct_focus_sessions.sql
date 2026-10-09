-- One row per focus session, with its task. Grain: pomodoro_id.
select
    s.*,
    t.task_text,
    t.created_quadrant as task_created_quadrant,
    round(s.focused_secs / 60.0, 1) as focused_minutes
from {{ ref('int_focus_sessions') }} s
left join {{ ref('int_tasks') }} t on t.task_id = s.task_id
