-- What arrived each day and what staging had to do about it. Grain: arrived_on.
with v as (select * from {{ ref('stg_events__validated') }}),
dups as (
    select arrived_on, count(*) - count(distinct event_id) as duplicate_rows
    from v where invalid_reason is null group by arrived_on
)
select
    v.arrived_on,
    count(*)                                                                         as rows_received,
    sum(case when v.invalid_reason is not null then 1 else 0 end)                    as rows_quarantined,
    max(d.duplicate_rows)                                                            as duplicate_rows_same_day,
    sum(case when v.invalid_reason is null and cast(v.local_date_text as date) < v.arrived_on then 1 else 0 end) as late_rows,
    sum(case when v.invalid_reason is null and not {{ has_offset('v.occurred_at_text') }} then 1 else 0 end) as repaired_timestamps
from v
left join dups d on d.arrived_on = v.arrived_on
group by v.arrived_on
