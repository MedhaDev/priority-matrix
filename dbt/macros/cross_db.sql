{#-
  Small cross-database helpers, so the same models run on DuckDB (local, CI)
  and Postgres (Supabase). Each macro dispatches to the adapter's version.
-#}

{# Text value at a JSON path, e.g. json_str('body', 'payload.text') #}
{% macro json_str(col, path) %}{{ return(adapter.dispatch('json_str')(col, path)) }}{% endmacro %}
{% macro duckdb__json_str(col, path) %}json_extract_string({{ col }}, '$.{{ path }}'){% endmacro %}
{% macro postgres__json_str(col, path) %}({{ col }} #>> '{ {{- path.split('.') | join(',') -}} }'){% endmacro %}

{# True when the value at a top-level key is a JSON number (not a string like "1") #}
{% macro json_is_number(col, key) %}{{ return(adapter.dispatch('json_is_number')(col, key)) }}{% endmacro %}
{% macro duckdb__json_is_number(col, key) %}coalesce(json_type({{ col }}, '$.{{ key }}') in ('UBIGINT', 'BIGINT', 'DOUBLE', 'HUGEINT'), false){% endmacro %}
{% macro postgres__json_is_number(col, key) %}coalesce(jsonb_typeof({{ col }} -> '{{ key }}') = 'number', false){% endmacro %}

{# Whole-string regular expression match #}
{% macro regex_match(col, pattern) %}{{ return(adapter.dispatch('regex_match')(col, pattern)) }}{% endmacro %}
{% macro duckdb__regex_match(col, pattern) %}regexp_full_match({{ col }}, '{{ pattern }}'){% endmacro %}
{% macro postgres__regex_match(col, pattern) %}({{ col }} ~ '^(?:{{ pattern }})$'){% endmacro %}

{# ISO timestamp text → UTC timestamptz. Text without an offset is local wall-clock time in `tz` (repairs the client bug). #}
{% macro to_utc(ts_text, tz) %}{{ return(adapter.dispatch('to_utc')(ts_text, tz)) }}{% endmacro %}
{% macro duckdb__to_utc(ts_text, tz) -%}
  case when {{ has_offset(ts_text) }} then cast({{ ts_text }} as timestamptz)
       else timezone({{ tz }}, cast({{ ts_text }} as timestamp)) end
{%- endmacro %}
{% macro postgres__to_utc(ts_text, tz) -%}
  case when {{ has_offset(ts_text) }} then cast({{ ts_text }} as timestamptz)
       else (cast({{ ts_text }} as timestamp) at time zone {{ tz }}) end
{%- endmacro %}

{% macro has_offset(ts_text) %}{{ regex_match(ts_text, '.*(Z|[+-][0-9]{2}:[0-9]{2})') }}{% endmacro %}

{# The local calendar date of a timestamptz in a given time zone #}
{% macro local_date(ts, tz) %}{{ return(adapter.dispatch('local_date')(ts, tz)) }}{% endmacro %}
{% macro duckdb__local_date(ts, tz) %}cast(timezone({{ tz }}, {{ ts }}) as date){% endmacro %}
{% macro postgres__local_date(ts, tz) %}cast(({{ ts }} at time zone {{ tz }}) as date){% endmacro %}

{# Seconds since 1970 (with milliseconds) — for exact durations #}
{% macro epoch_secs(ts) %}{{ return(adapter.dispatch('epoch_secs')(ts)) }}{% endmacro %}
{% macro duckdb__epoch_secs(ts) %}(epoch_ms({{ ts }}) / 1000.0){% endmacro %}
{% macro postgres__epoch_secs(ts) %}extract(epoch from {{ ts }}){% endmacro %}

{# Median of a numeric expression (same as Python's statistics.median) #}
{% macro median(expr) %}percentile_cont(0.5) within group (order by {{ expr }}){% endmacro %}

{# Raw JSON column as plain text (for the quarantine table) #}
{% macro json_as_text(col) %}cast({{ col }} as {{ dbt.type_string() }}){% endmacro %}
