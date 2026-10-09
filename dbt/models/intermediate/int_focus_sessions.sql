{#
  One row per focus session (pomodoro_id), rebuilt from its events.
  Quadrant and focus day come from the END event, matching the definition in
  docs/event-schema.md. Sessions whose start or end was lost are kept and flagged.
#}
with ev as (
    select * from {{ ref('stg_events') }} where pomodoro_id is not null
),

pause_pairs as (
    -- nth pause matched with nth resume
    select p.pomodoro_id, sum({{ epoch_secs('r.occurred_at') }} - {{ epoch_secs('p.occurred_at') }}) as paused_secs
    from (select pomodoro_id, occurred_at, row_number() over (partition by pomodoro_id order by occurred_at) as n
          from ev where event_type = 'pomodoro_paused') p
    join (select pomodoro_id, occurred_at, row_number() over (partition by pomodoro_id order by occurred_at) as n
          from ev where event_type = 'pomodoro_resumed') r
      on r.pomodoro_id = p.pomodoro_id and r.n = p.n
    group by p.pomodoro_id
),

s as (
    select
        pomodoro_id,
        max(task_id)                                                                          as task_id,
        min(case when event_type = 'pomodoro_started' then occurred_at end)                   as started_at,
        max(case when event_type in ('pomodoro_finished', 'pomodoro_abandoned') then occurred_at end) as ended_at,
        max(case when event_type in ('pomodoro_finished', 'pomodoro_abandoned') then event_type end)  as end_event,
        max(case when event_type in ('pomodoro_finished', 'pomodoro_abandoned') then quadrant end)    as end_quadrant,
        max(case when event_type = 'pomodoro_started' then quadrant end)                      as start_quadrant,
        max(case when event_type in ('pomodoro_finished', 'pomodoro_abandoned') then local_date end)  as end_local_date,
        max(case when event_type = 'pomodoro_started' then local_date end)                    as start_local_date,
        max(case when event_type in ('pomodoro_finished', 'pomodoro_abandoned') then focused_secs end) as focused_secs,
        max(coalesce(planned_secs, 0))                                                        as planned_secs,
        bool_or(case when event_type = 'pomodoro_finished' then early end)                    as finished_early,
        max(case when event_type = 'pomodoro_abandoned' then reason end)                      as abandon_reason,
        sum(case when event_type = 'pomodoro_paused' then 1 else 0 end)                       as pauses
    from ev
    group by pomodoro_id
)

select
    s.pomodoro_id,
    s.task_id,
    coalesce(s.end_quadrant, s.start_quadrant)                         as quadrant,
    coalesce(s.end_local_date, s.start_local_date)                     as focus_date,
    s.started_at,
    s.ended_at,
    case s.end_event when 'pomodoro_finished' then 'finished'
                     when 'pomodoro_abandoned' then 'abandoned'
                     else 'unfinished' end                             as outcome,
    s.focused_secs,
    s.planned_secs,
    s.finished_early,
    s.abandon_reason,
    s.pauses,
    coalesce(pp.paused_secs, 0)                                        as paused_secs,
    case when s.started_at is not null and s.ended_at is not null
         then {{ epoch_secs('s.ended_at') }} - {{ epoch_secs('s.started_at') }} end as wall_clock_secs,
    s.started_at is not null and s.ended_at is not null                as is_complete
from s
left join pause_pairs pp on pp.pomodoro_id = s.pomodoro_id
