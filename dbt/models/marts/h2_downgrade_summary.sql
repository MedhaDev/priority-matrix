-- Hypothesis 2 in one row. Two denominators: all urgent tasks, and urgent tasks
-- still open the next morning (ones finished on day one never had a chance).
with u as (select * from {{ ref('h2_urgent_tasks') }}),
lags as (
    select ({{ epoch_secs('first_downgrade_at') }} - {{ epoch_secs('created_at') }}) / 86400.0 as days
    from u where downgraded
)
select
    count(*)                                                                        as urgent_tasks,
    sum(case when downgraded then 1 else 0 end)                                     as downgraded,
    sum(case when downgraded_within_72h then 1 else 0 end)                          as downgraded_within_72h,
    sum(case when open_next_morning then 1 else 0 end)                              as urgent_tasks_open_next_morning,
    round(cast(sum(case when downgraded then 1 else 0 end) as numeric) / nullif(count(*), 0), 4) as downgrade_rate,
    round(cast(sum(case when downgraded_within_72h then 1 else 0 end) as numeric) / nullif(count(*), 0), 4) as downgrade_rate_within_72h,
    round(cast(sum(case when downgraded then 1 else 0 end) as numeric)
          / nullif(sum(case when open_next_morning then 1 else 0 end), 0), 4)       as downgrade_rate_among_open_next_morning,
    (select round(cast({{ median('days') }} as numeric), 3) from lags)              as median_days_to_downgrade
from u
