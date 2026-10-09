import { useMemo } from "react";
import { fmtDuration, patterns } from "../lib/stats";

const pct = (x) => `${Math.round(x * 100)}%`;
const HOURS = Array.from({ length: 17 }, (_, i) => i + 6); // 6am – 10pm
const hourLabel = (h) => (h === 12 ? "12p" : h > 12 ? `${h - 12}p` : `${h}a`);

export default function Patterns({ tasks, events, onLoadDemo, isDemo }) {
  const p = useMemo(() => patterns(tasks, events), [tasks, events]);

  if (p.totalFocusMins === 0 && p.urgent.created === 0) {
    return (
      <main className="patterns">
        <section className="intro">
          <p className="summary">Not enough data yet. <span className="soft">Use the app for a few days and patterns appear here.</span></p>
        </section>
        {!isDemo && <button className="btn btn-secondary" onClick={onLoadDemo}>Explore with demo data</button>}
      </main>
    );
  }

  const doShare = p.focusShare.find((q) => q.id === "do").share;
  const schedShare = p.focusShare.find((q) => q.id === "schedule").share;
  const ratio = schedShare > 0 ? doShare / schedShare : null;
  const maxHour = Math.max(1, ...p.byHour);
  const sessions = p.sessions.finished + p.sessions.abandoned;

  return (
    <main className="patterns">
      <section className="intro">
        <p className="summary">
          {fmtDuration(p.totalFocusMins)} focused over {p.activeDays} days.{" "}
          <span className="soft">{p.sessions.abandoned} of {sessions} sessions abandoned.</span>
        </p>
      </section>

      <div className="p-grid">
        <article className="card">
          <header><h2>Focus by quadrant</h2><span className="tag">Hypothesis 1</span></header>
          <p className="headline">
            {ratio && ratio >= 1.5 ? <>Do first gets <b>{ratio.toFixed(1)}×</b> the focus of Schedule.</> : "Focus is fairly balanced across quadrants."}
          </p>
          <div className="stack" role="img" aria-label="Share of focus time by quadrant">
            {p.focusShare.filter((q) => q.share > 0).map((q) => <i key={q.id} className={`bg-${q.id}`} style={{ width: pct(q.share) }} />)}
          </div>
          <ul className="legend">
            {p.focusShare.map((q) => (
              <li key={q.id}><span className={`sq sq-${q.id}`} /><span>{q.label}</span><b>{pct(q.share)}</b><span className="muted">{fmtDuration(q.mins)}</span></li>
            ))}
          </ul>
        </article>

        <article className="card">
          <header><h2>Urgency that doesn't last</h2><span className="tag">Hypothesis 2</span></header>
          {p.urgent.created === 0 ? (
            <p className="headline">No urgent tasks tracked yet.</p>
          ) : (
            <>
              <div className="big">{pct(p.urgent.downgraded / p.urgent.created)}</div>
              <p className="headline">of tasks marked urgent later lost their urgency.</p>
              <p className="muted small">
                {p.urgent.within3} of {p.urgent.created} within 3 days
                {p.urgent.medianDays != null && <> · median {p.urgent.medianDays.toFixed(1)} days</>}
              </p>
            </>
          )}
        </article>

        <article className="card">
          <header><h2>When you focus</h2></header>
          <div className="hours" role="img" aria-label="Focus minutes by hour of day">
            {HOURS.map((h) => (
              <div key={h} className="hour" title={`${hourLabel(h)}: ${p.byHour[h]} min`}>
                <i style={{ height: `${(p.byHour[h] / maxHour) * 100}%` }} />
                <span>{h % 3 === 0 ? hourLabel(h) : ""}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="card">
          <header><h2>Finish rate by quadrant</h2></header>
          <div className="rows">
            {p.completion.map((q) => (
              <div key={q.id} className="row">
                <span className={`sq sq-${q.id}`} />
                <span className="row-label">{q.label}</span>
                <div className="meter"><i style={{ width: q.total ? pct(q.done / q.total) : "0%" }} /></div>
                <span className="muted">{q.done}/{q.total}</span>
              </div>
            ))}
          </div>
        </article>
      </div>

      <p className="footnote">
        An in-app preview. The full analysis runs as a data pipeline (Postgres → dbt → Airflow → Tableau) on synthetic data.
      </p>
    </main>
  );
}
