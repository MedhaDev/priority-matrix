import { useEffect, useRef, useState } from "react";
import { exportJSON, exportEventsCSV, readBackupFile } from "../lib/exportData";
import Icon from "./Icon";

// Centered dialog on desktop, bottom sheet on phones.
export function Dialog({ title, onClose, children, className = "" }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="dialog-wrap">
      <div className="scrim" onClick={onClose} />
      <div className={`dialog ${className}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="grab" />
        <div className="dialog-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

// Clicking outside / Escape only hides it for now; only the buttons count as a decision.
export function CarryOverModal({ count, onCarry, onLeave, onDismiss }) {
  return (
    <Dialog title="Good morning" onClose={onDismiss}>
      <p>{count} unfinished task{count === 1 ? "" : "s"} from earlier days. Bring {count === 1 ? "it" : "them"} to today?</p>
      <div className="dialog-actions">
        <button className="btn btn-secondary" onClick={onLeave}>Leave {count === 1 ? "it" : "them"}</button>
        <button className="btn btn-primary" onClick={onCarry}>Carry over</button>
      </div>
    </Dialog>
  );
}

export function AddSheet({ onClose, children }) {
  return <Dialog title="New task" onClose={onClose} className="add-dialog">{children}</Dialog>;
}

export function ExportModal({ data, isDemo, onImport, onClose }) {
  const fileRef = useRef(null);
  const [error, setError] = useState(null);

  const pickFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      const backup = await readBackupFile(file);
      const ok = window.confirm(
        `Replace the data on this device with this backup (${backup.tasks.length} tasks, ${backup.events.length} events)?\n\nYour current data is kept as a backup copy first.`,
      );
      if (ok) { onImport(backup); onClose(); }
    } catch (err) {
      setError(err.message || "Couldn't read that file.");
    }
  };

  return (
    <Dialog title="Your data" onClose={onClose}>
      <p className="muted">
        {isDemo ? "Demo mode: this exports the simulated data." : "Everything lives in this browser."}{" "}
        {data.tasks.length} tasks · {data.events.length} events.
      </p>
      <div className="option-list">
        <button onClick={() => exportEventsCSV(data.events)}>
          <Icon name="download" /><span><b>Event log (.csv)</b><small>One row per action, for spreadsheets, pandas or a database</small></span>
        </button>
        <button onClick={() => exportJSON(data)}>
          <Icon name="download" /><span><b>Full backup (.json)</b><small>Tasks and events, to restore here or on another device</small></span>
        </button>
        {!isDemo && (
          <button onClick={() => fileRef.current?.click()}>
            <Icon name="upload" /><span><b>Import a backup</b><small>Move your data from another device, e.g. laptop to phone</small></span>
          </button>
        )}
      </div>
      <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={pickFile} />
      {error && <p className="error">{error}</p>}
    </Dialog>
  );
}

export function AboutModal({ onClose }) {
  return (
    <Dialog title="How it works" onClose={onClose}>
      <p>
        Sort tasks by <b>urgent</b> and <b>important</b>, focus on them in 25-minute sessions, and the app records
        every action as an event: created, moved, completed, focus started, paused, finished, abandoned.
      </p>
      <p><b>Private by design.</b> No account, no server. Everything stays in this browser until you export it.</p>
      <p>
        The event log feeds a data pipeline (Python → Postgres → dbt → Airflow → Tableau) that runs on a{" "}
        <b>synthetic</b> person, so the public dashboard never shows anyone's real life.
      </p>
      <p className="muted small">
        Shortcuts: <kbd>N</kbd> new task · <kbd>F</kbd> focus · <kbd>Space</kbd> start/pause · <kbd>Esc</kbd> close
      </p>
      <p className="muted small"><a href="https://github.com/MedhaDev/priority-matrix" target="_blank" rel="noreferrer">Source on GitHub ↗</a></p>
    </Dialog>
  );
}
