-- Mirrors bad_carry (the part checkable per row): carry-overs only move tasks to a later day.
select event_id, from_date, to_date
from {{ ref('stg_events') }}
where event_type = 'task_carried_over' and to_date <= from_date
