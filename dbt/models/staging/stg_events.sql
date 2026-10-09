{#
  Clean, typed, deduplicated events: one row per event_id.

  - Repair: timestamps without an offset are local time in the event's timezone.
  - Dedupe: keep the first delivery of each event_id (phones retry uploads).
  - Incremental: each run re-reads the last `lookback_days` of arrivals and
    inserts only event_ids it hasn't seen. Late events land in later files and
    backfilled days within the window are picked up; `--full-refresh` rebuilds all.
#}
{{ config(materialized='incremental', incremental_strategy='append', on_schema_change='fail') }}

with valid as (
    select * from {{ ref('stg_events__validated') }}
    where invalid_reason is null
    {% if is_incremental() %}
      and arrived_on >= (select {{ dbt.dateadd('day', -var('lookback_days'), 'max(arrived_on)') }} from {{ this }})
    {% endif %}
),

first_delivery as (
    select
        *,
        row_number() over (partition by event_id order by arrived_on, line_no) as delivery_rank
    from valid
)

select
    event_id,
    event_type,
    task_id,
    quadrant,
    from_quadrant,
    pomodoro_id,
    {{ to_utc('occurred_at_text', 'timezone') }}                as occurred_at,
    cast(local_date_text as date)                                as local_date,
    timezone,
    source,
    not {{ has_offset('occurred_at_text') }}                     as timestamp_repaired,
    task_text,
    cast(task_date_text as date)                                 as task_date,
    old_text,
    new_text,
    cast(from_date_text as date)                                 as from_date,
    cast(to_date_text as date)                                   as to_date,
    cast(planned_secs_text as integer)                           as planned_secs,
    cast(focused_secs_text as integer)                           as focused_secs,
    cast(early_text as boolean)                                  as early,
    reason,
    arrived_on,
    line_no
from first_delivery
where delivery_rank = 1
{% if is_incremental() %}
  and event_id not in (select event_id from {{ this }})
{% endif %}
