{# Rows that break the contract: kept (never silently dropped) but excluded from every model. #}
{{ config(materialized='table') }}

select
    arrived_on,
    line_no,
    event_id,
    event_type,
    invalid_reason,
    {{ json_as_text('body') }} as raw_body
from {{ ref('stg_events__validated') }}
where invalid_reason is not null
