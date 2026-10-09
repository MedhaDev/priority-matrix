-- Reconciliation: the hypothesis numbers must match the generator's answer key.
{{ config(enabled=var('reconcile')) }}
with h1 as (select quadrant, focused_secs from {{ ref('h1_focus_by_quadrant') }}),
     h2 as (select * from {{ ref('h2_downgrade_summary') }}),
model as (
    select 'h1_total_focused_secs' as metric, cast(sum(focused_secs) as double precision) as value from h1
    {% for q in ['do', 'schedule', 'delegate', 'eliminate'] %}
    union all select 'h1_focused_secs_{{ q }}', cast(focused_secs as double precision) from h1 where quadrant = '{{ q }}'
    {% endfor %}
    union all select 'h1_sessions_finished', cast(sum(sessions_finished) as double precision) from {{ ref('h1_focus_by_quadrant') }}
    union all select 'h1_sessions_abandoned', cast(sum(sessions_abandoned) as double precision) from {{ ref('h1_focus_by_quadrant') }}
    union all select 'h2_urgent_tasks', cast(urgent_tasks as double precision) from h2
    union all select 'h2_downgraded', cast(downgraded as double precision) from h2
    union all select 'h2_downgraded_within_72h', cast(downgraded_within_72h as double precision) from h2
    union all select 'h2_urgent_tasks_open_next_morning', cast(urgent_tasks_open_next_morning as double precision) from h2
    union all select 'h2_median_days_to_downgrade', cast(median_days_to_downgrade as double precision) from h2
)
select t.metric, m.value as model_value, t.value as truth_value
from {{ ref('truth_summary') }} t
left join model m on m.metric = t.metric
where m.value is null or abs(m.value - t.value) > 0.001
