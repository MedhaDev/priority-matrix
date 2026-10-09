-- Hypothesis 1: where focus goes, next to what was on the list.
-- focus_vs_list > 1 means a quadrant gets more focus than its share of the to-do list.
{% set quadrants = ['do', 'schedule', 'delegate', 'eliminate'] %}
with q as (
    {% for q in quadrants %}select '{{ q }}' as quadrant, {{ loop.index }} as sort_order{% if not loop.last %} union all {% endif %}{% endfor %}
),
focus as (
    select quadrant, sum(focused_secs) as focused_secs, sum(sessions_finished) as sessions_finished,
           sum(sessions_abandoned) as sessions_abandoned
    from {{ ref('daily_focus_metrics') }} group by quadrant
),
list as (
    select quadrant, count(*) as task_days from {{ ref('int_task_days') }} group by quadrant
)
select
    q.quadrant,
    q.sort_order,
    coalesce(f.focused_secs, 0)                                                    as focused_secs,
    round(coalesce(f.focused_secs, 0) / 3600.0, 1)                                 as focused_hours,
    round(cast(coalesce(f.focused_secs, 0) as numeric) / sum(coalesce(f.focused_secs, 0)) over (), 4) as focus_share,
    coalesce(f.sessions_finished, 0)                                               as sessions_finished,
    coalesce(f.sessions_abandoned, 0)                                              as sessions_abandoned,
    coalesce(l.task_days, 0)                                                       as task_days,
    round(cast(coalesce(l.task_days, 0) as numeric) / sum(coalesce(l.task_days, 0)) over (), 4) as list_share,
    round(
        (cast(coalesce(f.focused_secs, 0) as numeric) / sum(coalesce(f.focused_secs, 0)) over ())
        / nullif(cast(coalesce(l.task_days, 0) as numeric) / sum(coalesce(l.task_days, 0)) over (), 0)
    , 3)                                                                           as focus_vs_list
from q
left join focus f on f.quadrant = q.quadrant
left join list l on l.quadrant = q.quadrant
