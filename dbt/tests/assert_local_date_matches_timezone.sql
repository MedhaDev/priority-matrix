-- Mirrors local_date_mismatch: local_date must be occurred_at's day in the event's time zone.
-- Also proves the timestamp repair landed on the right day.
select event_id, occurred_at, local_date, timezone
from {{ ref('stg_events') }}
where local_date <> {{ local_date('occurred_at', 'timezone') }}
