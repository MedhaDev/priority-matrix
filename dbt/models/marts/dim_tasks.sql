-- One row per task. Grain: task_id.
select * from {{ ref('int_tasks') }}
