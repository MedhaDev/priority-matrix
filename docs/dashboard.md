# Dashboard: "Where my focus actually goes"

Tableau Public can't connect to a database, so the dashboard reads the CSVs the pipeline
exports. The HTML preview (`exports/dashboard.html`, rebuilt on every pipeline run) is the
reference design: same views, colors and numbers. Build the Tableau version to match it.

```bash
./warehouse/run_pipeline.sh                          # data → warehouse → dbt (tested)
warehouse/.venv/bin/python warehouse/export.py       # → exports/*.csv
warehouse/.venv/bin/python warehouse/build_dashboard.py   # → exports/dashboard.html
```

## Data sources (exports/)

| File | Grain | Used for |
|---|---|---|
| `h1_focus_by_quadrant.csv` | quadrant | Hero number, "Focus vs. the list" |
| `weekly_focus_share.csv` | week × quadrant | "Weekly share of focus time" |
| `h2_urgent_tasks.csv` | urgent task | "How long urgent lasts" histogram |
| `h2_downgrade_summary.csv` | one row | Downgrade KPI tiles |
| `data_quality_summary.csv` | measure | "Pipeline health" table |
| `daily_focus_metrics.csv` | day × quadrant | Date range, optional daily view |
| `fct_focus_sessions.csv` + `dim_tasks.csv` | session / task | Drill-down (relate on `task_id`) |

## Look and feel

- **Quadrant colors** (assign once to the `quadrant` field: Edit Colors → each value).
  These were checked with a color-blindness validator; keep the legend and direct labels on,
  because Delegate/Eliminate are only just far enough apart for red-green color blindness.

  | Quadrant | Hex |
  |---|---|
  | Do first (`do`) | `#d4512f` |
  | Schedule | `#3f6fc6` |
  | Delegate | `#d8a03a` |
  | Eliminate | `#6b9a5e` |
  | "On the list" (comparison bars) | `#c9c6bf` |

- Background `#f3f2ee`, cards `#fcfbf8`, text `#1c1b19`, secondary text `#6e6b65`.
- Font: Tableau Public can't load Switzer; use **Tableau Book** for text and
  **Tableau Medium** for numbers (closest neutral grotesk).
- Thin marks: bar size about ⅓ of the band, gridlines on the value axis only, light gray, no
  borders. Label the important value directly, not every mark.
- Quadrant aliases: `do` → "Do first", `schedule` → "Schedule", and so on. Sort with `sort_order`.

## Sheets

1. **Hero: Do first × its list share.** `h1_focus_by_quadrant`, filter `quadrant = do`.
   Text mark: `focus_vs_list` formatted `0.0"×"`, about 60pt. Caption:
   "52% of focus time, 14% of task-days."
2. **KPI tiles** (four text sheets): focus hours (`SUM(focused_hours)`), sessions abandoned
   (`SUM(sessions_abandoned) / (SUM(sessions_finished)+SUM(sessions_abandoned))`), urgent tasks
   downgraded (`downgrade_rate_among_open_next_morning`, label "of those still open the next
   morning"), median time to downgrade (`median_days_to_downgrade`, "days").
3. **Focus vs. the list.** `h1_focus_by_quadrant`. Rows: `quadrant` (aliased, sorted).
   Columns: Measure Values = `focus_share`, `list_share` (side-by-side bars). Color: focus bars
   by quadrant, list bars `#c9c6bf` (calculated field
   `IF [Measure Names] = "list_share" THEN "On the list" ELSE [quadrant] END`). Labels at bar ends.
4. **Weekly share of focus time.** `weekly_focus_share`. Columns: `week_start` (exact date,
   continuous). Rows: `focus_share` (0–100%). Color: quadrant. Line, 2px, end-of-line labels.
   One axis only. Note in the caption that the first and last weeks are partial.
5. **How long "urgent" lasts.** `h2_urgent_tasks`, filter `downgraded = true`. Calculated field:
   `IF [hours_to_downgrade] < 24 THEN "Within a day" ELSEIF [hours_to_downgrade] < 48 THEN "Day 2"
   ELSEIF [hours_to_downgrade] < 72 THEN "Day 3" ELSE "Later" END` (sort in that order).
   Columns: that field. Rows: `CNT(task_id)`. One color (`#d4512f`).
6. **Pipeline health.** `data_quality_summary`, text table: `measure` | `value`.

## Layout

Fixed size 1200 × 1000 (add a phone layout: stack everything in one column).

```
┌───────────────────────── title + one-line subtitle ─────────── date-range tag ┐
│ HERO 3.6×           │ focus hours │ % urgent downgraded │ median days         │
├──────────────────────────────────┬────────────────────────────────────────────┤
│ Focus vs. the list (H1)          │ Weekly share of focus time (H1 over time)  │
├──────────────────────────────────┼────────────────────────────────────────────┤
│ How long "urgent" lasts (H2)     │ Pipeline health                            │
└──────────────────────────────────┴────────────────────────────────────────────┘
footer: "Synthetic data from my own estimates of how I work" + GitHub link
```

## Keep it fresh

The data is synthetic and deterministic, so the dashboard only changes when the persona or
the pipeline changes. After a pipeline run: Tableau Public → your workbook → **Data → Replace
Data Source / Refresh**, then republish. (For hands-off daily refresh, the export step could
write to a Google Sheet, which Tableau Public can refresh once a day; that needs a Google
service account and isn't set up here.)
