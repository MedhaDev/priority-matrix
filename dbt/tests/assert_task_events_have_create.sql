-- Mirrors event_before_create. Lost task_created events leave orphans: warn, don't fail.
{{ config(severity='warn') }}
select task_id from {{ ref('int_tasks') }} where not has_create_event
