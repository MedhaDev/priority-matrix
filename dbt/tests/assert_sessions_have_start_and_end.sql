-- Mirrors pomodoro_unfinished / pomodoro_sequence. Lost events make this happen in real
-- data, so it warns (and is counted in data_quality_summary) instead of failing the build.
{{ config(severity='warn') }}
select pomodoro_id, started_at, ended_at
from {{ ref('int_focus_sessions') }}
where not is_complete
