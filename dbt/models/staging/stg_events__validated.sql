{#
  Every delivered row, parsed, with the reason it breaks the event contract
  (contracts/event.v1.schema.json), or null if it's fine. Nothing is dropped
  here: valid rows flow to stg_events, invalid ones to stg_events__quarantine.
#}
{% set event_types = ['task_created', 'task_edited', 'task_moved', 'task_completed', 'task_reopened', 'task_deleted',
                      'task_carried_over', 'pomodoro_started', 'pomodoro_paused', 'pomodoro_resumed',
                      'pomodoro_finished', 'pomodoro_abandoned'] %}
{% set quadrants = ['do', 'schedule', 'delegate', 'eliminate'] %}
{% set uuid = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' %}
{% set iso_ts = '[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})?' %}
{% set iso_date = '[0-9]{4}-[0-9]{2}-[0-9]{2}' %}

with parsed as (
    select
        arrived_on,
        line_no,
        body,
        {{ json_str('body', 'event_id') }}           as event_id,
        {{ json_str('body', 'schema_version') }}     as schema_version_text,
        {{ json_is_number('body', 'schema_version') }} as schema_version_is_number,
        {{ json_str('body', 'event_type') }}         as event_type,
        {{ json_str('body', 'task_id') }}            as task_id,
        {{ json_str('body', 'quadrant') }}           as quadrant,
        {{ json_str('body', 'from_quadrant') }}      as from_quadrant,
        {{ json_str('body', 'pomodoro_id') }}        as pomodoro_id,
        {{ json_str('body', 'occurred_at') }}        as occurred_at_text,
        {{ json_str('body', 'local_date') }}         as local_date_text,
        {{ json_str('body', 'timezone') }}           as timezone,
        {{ json_str('body', 'source') }}             as source,
        {{ json_str('body', 'payload.text') }}         as task_text,
        {{ json_str('body', 'payload.date') }}         as task_date_text,
        {{ json_str('body', 'payload.old_text') }}     as old_text,
        {{ json_str('body', 'payload.new_text') }}     as new_text,
        {{ json_str('body', 'payload.from_date') }}    as from_date_text,
        {{ json_str('body', 'payload.to_date') }}      as to_date_text,
        {{ json_str('body', 'payload.planned_secs') }} as planned_secs_text,
        {{ json_str('body', 'payload.focused_secs') }} as focused_secs_text,
        {{ json_str('body', 'payload.early') }}        as early_text,
        {{ json_str('body', 'payload.reason') }}       as reason
    from {{ source('raw', 'events') }}
)

select
    *,
    case
        when event_id is null or not {{ regex_match('event_id', uuid) }}            then 'invalid event_id'
        when not schema_version_is_number or schema_version_text <> '1'            then 'unsupported schema_version'
        when event_type is null or event_type not in ('{{ event_types | join("', '") }}') then 'unknown event_type'
        when quadrant is not null and quadrant not in ('{{ quadrants | join("', '") }}')   then 'unknown quadrant'
        when from_quadrant is not null and from_quadrant not in ('{{ quadrants | join("', '") }}') then 'unknown from_quadrant'
        when timezone is null or timezone = ''                                      then 'missing timezone'
        when occurred_at_text is null or not {{ regex_match('occurred_at_text', iso_ts) }} then 'unparseable occurred_at'
        when local_date_text is null or not {{ regex_match('local_date_text', iso_date) }} then 'invalid local_date'
        when source is null or source not in ('app', 'backfill', 'demo', 'synthetic') then 'unknown source'
        when event_type like 'task%' and (task_id is null or quadrant is null)       then 'task event without task or quadrant'
        when event_type = 'task_moved' and (from_quadrant is null or from_quadrant = quadrant) then 'move without a real from_quadrant'
        when event_type <> 'task_moved' and from_quadrant is not null               then 'from_quadrant on a non-move'
        when event_type like 'pomodoro%' and pomodoro_id is null                    then 'focus event without pomodoro_id'
        when event_type = 'task_created' and (task_text is null or task_date_text is null) then 'created without text or date'
        when event_type = 'task_carried_over' and (from_date_text is null or to_date_text is null) then 'carry without dates'
        when event_type in ('pomodoro_finished', 'pomodoro_abandoned')
             and (focused_secs_text is null or planned_secs_text is null)           then 'session end without durations'
    end as invalid_reason
from parsed
