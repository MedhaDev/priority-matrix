import { useEffect } from "react";
import { quadrantLabel } from "../lib/events";
import { fmtTime } from "../lib/dates";
import Icon from "./Icon";

const pad = (n) => String(n).padStart(2, "0");
const split = (ms) => {
  const s = Math.ceil(ms / 1000);
  return [pad(Math.floor(s / 60)), pad(s % 60)];
};

export default function FocusOverlay({ focus, task, sessionsToday, onCompleteTask }) {
  const { active, status, remainingMs, progress, endsAt } = focus;
  const [mm, ss] = split(remainingMs);
  const quadrant = task?.quadrant ?? active.quadrant;
  const name = task?.text ?? active.text;

  // Countdown in the browser tab / app switcher.
  useEffect(() => {
    const original = "Priority Matrix";
    document.title = status === "running" ? `${mm}:${ss} · Focus` : status === "paused" ? `Paused · ${mm}:${ss}` : original;
    return () => { document.title = original; };
  }, [status, mm, ss]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") focus.close();
      if (e.key === " " && !["INPUT", "BUTTON"].includes(e.target.tagName)) {
        e.preventDefault();
        if (status === "running") focus.pause();
        else if (status === "ready" || status === "paused") focus.start();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [focus, status]);

  const chip = (
    <span className="chip">
      <span className={`sq sq-${quadrant}`} />
      {quadrantLabel(quadrant)} · session {status === "ready" ? sessionsToday + 1 : sessionsToday} today
    </span>
  );

  if (status === "ended") {
    const mins = Math.round(active.ended.focused_secs / 60);
    const finished = active.ended.type === "pomodoro_finished";
    return (
      <div className="focus" role="dialog" aria-modal="true" aria-label="Focus session">
        <div className="focus-inner">
          <div className="focus-top">{chip}<button className="icon-btn" onClick={focus.close} aria-label="Close"><Icon name="x" size={18} /></button></div>
          <div className="focus-mid">
            <span className="label">{finished ? "Session complete" : "Session ended"}</span>
            <p className="task-name">{name}</p>
            <div className="timer">{mins}<span className="unit">min</span></div>
            <p className="focus-note">{finished ? "Logged. Take a short break before the next one." : "Logged as abandoned. That's data too."}</p>
          </div>
          <div className="focus-actions">
            {task && !task.done
              ? <button className="btn btn-primary wide" onClick={() => { onCompleteTask(task.id); focus.close(); }}><Icon name="check" size={15} />Mark task done</button>
              : <button className="btn btn-primary wide" onClick={focus.close}>Back to matrix</button>}
            <button className="btn btn-secondary" onClick={focus.again}>Another round</button>
            <button className="btn btn-quiet" onClick={focus.close}>Close</button>
          </div>
        </div>
      </div>
    );
  }

  const started = active.started_at;

  return (
    <div className="focus" role="dialog" aria-modal="true" aria-label="Focus session">
      <div className="focus-inner">
        <div className="focus-top">
          {chip}
          <button className="icon-btn" onClick={focus.close} aria-label={status === "ready" ? "Close" : "Exit (counts as abandoned)"} title={status === "ready" ? "Close" : "Exit · counts as abandoned"}>
            <Icon name="x" size={18} />
          </button>
        </div>
        <div className="focus-mid">
          <span className="label">{status === "paused" ? "Paused" : status === "ready" ? "Ready to focus on" : "Focusing on"}</span>
          <p className="task-name">{name}</p>
          <div className={`timer${status === "paused" ? " paused" : ""}`}>{mm}<span className="colon">:</span>{ss}</div>
          <div className="bar"><i style={{ width: `${progress * 100}%` }} /></div>
          <div className="ticks">
            <span>{started ? `Started ${fmtTime(started)}` : "25 minutes"}</span>
            <span>{endsAt ? `Ends ${fmtTime(endsAt)}` : status === "paused" ? "Timer paused" : "Space to start"}</span>
          </div>
        </div>
        <div className="focus-actions">
          {status === "running" && <button className="btn btn-primary wide" onClick={focus.pause}><Icon name="pause" size={14} />Pause</button>}
          {status === "paused" && <button className="btn btn-primary wide" onClick={focus.start}><Icon name="play" size={13} />Resume</button>}
          {status === "ready" && <button className="btn btn-primary wide" onClick={focus.start}><Icon name="play" size={13} />Start</button>}
          {status !== "ready" && (
            <>
              <button className="btn btn-secondary" onClick={focus.finishEarly}>Finish early</button>
              <button className="btn btn-quiet" onClick={() => focus.abandon()}>Abandon</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
