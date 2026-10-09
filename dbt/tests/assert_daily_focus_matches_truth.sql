-- Reconciliation: every day × quadrant must match the generator's answer key exactly.
{{ config(enabled=var('reconcile')) }}
with m as (select focus_date as local_date, quadrant, focused_secs, sessions from {{ ref('daily_focus_metrics') }}),
     t as (select local_date, quadrant, focused_secs, sessions from {{ ref('truth_daily_focus') }})
select
    coalesce(m.local_date, t.local_date) as local_date,
    coalesce(m.quadrant, t.quadrant)     as quadrant,
    m.focused_secs as model_secs, t.focused_secs as truth_secs,
    m.sessions as model_sessions, t.sessions as truth_sessions
from m
full outer join t on t.local_date = m.local_date and t.quadrant = m.quadrant
where m.local_date is null or t.local_date is null
   or m.focused_secs <> t.focused_secs or m.sessions <> t.sessions
