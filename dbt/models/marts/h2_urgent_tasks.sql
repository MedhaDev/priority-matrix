-- Hypothesis 2, one row per task created as urgent (Do first or Delegate).
select
    task_id,
    task_text,
    created_at,
    created_date,
    created_quadrant,
    first_downgrade_at,
    first_downgrade_at is not null                                              as downgraded,
    case when first_downgrade_at is not null
         then round(({{ epoch_secs('first_downgrade_at') }} - {{ epoch_secs('created_at') }}) / 3600.0, 2) end as hours_to_downgrade,
    coalesce(({{ epoch_secs('first_downgrade_at') }} - {{ epoch_secs('created_at') }}) <= 72 * 3600, false) as downgraded_within_72h,
    coalesce(open_next_morning, false)                                          as open_next_morning,
    status
from {{ ref('int_tasks') }}
where has_create_event and created_urgent
