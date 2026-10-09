-- One row per data-quality measure, for the dashboard's pipeline-health panel.
select 'rows received' as measure, count(*) as value from {{ ref('stg_events__validated') }}
union all select 'events after dedupe', count(*) from {{ ref('stg_events') }}
union all select 'duplicate rows removed',
    (select count(*) from {{ ref('stg_events__validated') }} where invalid_reason is null) - (select count(*) from {{ ref('stg_events') }})
union all select 'rows quarantined', count(*) from {{ ref('stg_events__quarantine') }}
union all select 'timestamps repaired', sum(case when timestamp_repaired then 1 else 0 end) from {{ ref('stg_events') }}
union all select 'late events (arrived after the day they happened)', sum(case when arrived_on > local_date then 1 else 0 end) from {{ ref('stg_events') }}
union all select 'sessions missing a start or end (lost events)', sum(case when is_complete then 0 else 1 end) from {{ ref('int_focus_sessions') }}
union all select 'tasks missing their created event (lost events)', sum(case when has_create_event then 0 else 1 end) from {{ ref('int_tasks') }}
