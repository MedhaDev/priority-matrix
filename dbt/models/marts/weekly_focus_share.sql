-- Hypothesis 1 over time: each quadrant's share of the week's focus. Grain: week_start × quadrant.
with weekly as (
    select {{ dbt.date_trunc('week', 'focus_date') }} as week_start, quadrant, sum(focused_secs) as focused_secs
    from {{ ref('daily_focus_metrics') }}
    group by 1, 2
)
select
    cast(week_start as date) as week_start,
    quadrant,
    focused_secs,
    round(focused_secs / 60.0, 1) as focused_minutes,
    round(cast(focused_secs as numeric) / sum(focused_secs) over (partition by week_start), 4) as focus_share
from weekly
