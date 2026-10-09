-- Reconciliation: staging must quarantine exactly the rows the generator broke on purpose.
{{ config(enabled=var('reconcile')) }}
with q as (select event_id, invalid_reason from {{ ref('stg_events__quarantine') }}),
     e as (select event_id, how from {{ ref('expected_quarantine') }})
select coalesce(q.event_id, e.event_id) as event_id, q.invalid_reason, e.how
from q full outer join e on e.event_id = q.event_id
where q.event_id is null or e.event_id is null
