{#
  One row per task, built from its events. Includes "orphan" tasks whose
  task_created was lost (seen only through later events), flagged by has_create_event.
#}
with ev as (
    select * from {{ ref('stg_events') }} where task_id is not null
),

created as (
    select task_id, occurred_at as created_at, local_date as created_date, quadrant as created_quadrant,
           task_text as created_text, task_date as first_planned_date
    from ev where event_type = 'task_created'
),

latest_task_event as (
    select task_id, quadrant as current_quadrant
    from (
        select task_id, quadrant,
               row_number() over (partition by task_id order by occurred_at desc, event_id) as rn
        from ev where event_type like 'task%'
    ) x where rn = 1
),

latest_text as (
    select task_id, new_text
    from (
        select task_id, new_text, row_number() over (partition by task_id order by occurred_at desc) as rn
        from ev where event_type = 'task_edited'
    ) x where rn = 1
),

latest_done_state as (
    select task_id, event_type as last_done_event, occurred_at as last_done_at
    from (
        select task_id, event_type, occurred_at,
               row_number() over (partition by task_id order by occurred_at desc) as rn
        from ev where event_type in ('task_completed', 'task_reopened')
    ) x where rn = 1
),

agg as (
    select
        task_id,
        max(local_date)                                                          as last_event_date,
        sum(case when event_type = 'task_carried_over' then 1 else 0 end)        as carry_count,
        sum(case when event_type = 'task_moved' then 1 else 0 end)               as move_count,
        max(case when event_type = 'task_carried_over' then to_date end)         as last_carried_to,
        max(case when event_type = 'task_deleted' then occurred_at end)          as deleted_at,
        -- hypothesis 2: the FIRST move that takes away urgency
        min(case when event_type = 'task_moved'
                  and from_quadrant in ('do', 'delegate') and quadrant in ('schedule', 'eliminate')
                 then occurred_at end)                                           as first_downgrade_at
    from ev
    group by task_id
)

select
    a.task_id,
    c.task_id is not null                                         as has_create_event,
    c.created_at,
    c.created_date,
    c.created_quadrant,
    coalesce(c.created_quadrant in ('do', 'delegate'), false)     as created_urgent,
    coalesce(t.new_text, c.created_text)                          as task_text,
    l.current_quadrant,
    coalesce(a.last_carried_to, c.first_planned_date)             as planned_date,
    a.carry_count,
    a.move_count,
    a.first_downgrade_at,
    case when d.last_done_event = 'task_completed' then d.last_done_at end as completed_at,
    a.deleted_at,
    case
        when a.deleted_at is not null then 'deleted'
        when d.last_done_event = 'task_completed' then 'done'
        else 'open'
    end                                                           as status,
    a.last_event_date > c.created_date                            as open_next_morning
from agg a
left join created c           on c.task_id = a.task_id
left join latest_task_event l on l.task_id = a.task_id
left join latest_text t       on t.task_id = a.task_id
left join latest_done_state d on d.task_id = a.task_id
