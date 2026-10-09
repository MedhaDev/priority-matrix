-- Focus time per day and quadrant. Grain: focus_date × quadrant (only days with focus).
-- Reconciled row-for-row against the generator's answer key.
select
    focus_date,
    quadrant,
    cast(focus_date as {{ dbt.type_string() }}) || '|' || quadrant         as day_quadrant_key,
    sum(focused_secs)                                                     as focused_secs,
    round(sum(focused_secs) / 60.0, 1)                                    as focused_minutes,
    count(*)                                                              as sessions,
    sum(case when outcome = 'finished' then 1 else 0 end)                 as sessions_finished,
    sum(case when outcome = 'abandoned' then 1 else 0 end)                as sessions_abandoned
from {{ ref('int_focus_sessions') }}
where outcome in ('finished', 'abandoned')
group by focus_date, quadrant
