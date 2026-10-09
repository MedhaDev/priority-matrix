{#
  One row per task per day it sat on the list (the day it was planned for, and
  every day it was carried to), with its quadrant at the end of that day.
  Used to compare focus share with "what was even on the list" (availability).
#}
with ev as (
    select * from {{ ref('stg_events') }} where task_id is not null and event_type like 'task%'
),

plan_days as (
    select task_id, task_date as plan_date from ev where event_type = 'task_created'
    union
    select task_id, to_date as plan_date from ev where event_type = 'task_carried_over'
),

last_state_that_day as (
    select task_id, local_date, quadrant
    from (
        select task_id, local_date, quadrant,
               row_number() over (partition by task_id, local_date order by occurred_at desc, event_id) as rn
        from ev
    ) x where rn = 1
)

select
    p.task_id,
    p.plan_date,
    s.quadrant
from plan_days p
join last_state_that_day s on s.task_id = p.task_id and s.local_date = p.plan_date
