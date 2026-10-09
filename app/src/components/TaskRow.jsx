import { useState } from "react";
import { QUADRANTS, quadrantLabel, newId, isUrgent } from "../lib/events";
import { addDays, fmtTime, localDate } from "../lib/dates";
import { fmtDuration } from "../lib/stats";
import Icon from "./Icon";
import { confettiAt } from "./confetti";

// down = lost urgency, up = gained urgency, right = same urgency
const moveIcon = (from, to) => (isUrgent(from) === isUrgent(to) ? "right" : isUrgent(from) ? "down" : "up");

const EMPTY_META = { sessions: 0, focusSecs: 0, carried: 0, lastMoveFrom: null };

export default function TaskRow({ task, meta = EMPTY_META, menuOpen, onMenu, actions, onFocus, drag }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(task.text);
  const [expanded, setExpanded] = useState(false);
  const [menuUp, setMenuUp] = useState(false);

  const focusMins = Math.round(meta.focusSecs / 60);
  const subsDone = task.subtasks.filter((s) => s.done).length;

  const toggle = (e) => {
    if (!task.done) confettiAt(e.currentTarget);
    actions.toggle(task.id);
  };
  const saveEdit = () => {
    if (draft.trim()) actions.edit(task.id, draft.trim());
    else setDraft(task.text);
    setEditing(false);
  };
  const startEdit = () => { setDraft(task.text); setEditing(true); onMenu(null); };

  return (
    <>
      {drag.isOver && <div className="drop-line" />}
      <div
        className={`task${task.done ? " done" : ""}${menuOpen ? " menu-open" : ""}`}
        id={`task-${task.id}`}
        draggable={!editing}
        onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; drag.onStart(); }}
        onDragEnd={drag.onEnd}
        onDragOver={(e) => { e.preventDefault(); drag.onOver(); }}
      >
        <button className="chk" onClick={toggle} aria-label={task.done ? "Mark not done" : "Mark done"}>
          {task.done && <Icon name="check" size={11} />}
        </button>

        <div className="t">
          {editing ? (
            <input
              className="edit-input" autoFocus value={draft} aria-label="Task name"
              onChange={(e) => setDraft(e.target.value)}
              onBlur={saveEdit}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveEdit();
                if (e.key === "Escape") { setDraft(task.text); setEditing(false); }
              }}
            />
          ) : (
            <span className="text" onDoubleClick={startEdit}>{task.text}</span>
          )}
          <span className="meta">
            {task.subtasks.length > 0 && (
              <button className="meta-btn" onClick={() => setExpanded((x) => !x)} aria-expanded={expanded}>
                <Icon name="list" size={13} />{subsDone}/{task.subtasks.length}
              </button>
            )}
            {focusMins > 0 && <span><Icon name="timer" size={13} />{fmtDuration(focusMins)}</span>}
            {!task.done && meta.carried > 0 && <span className="warn"><Icon name="carry" size={13} />{meta.carried + 1}d</span>}
            {!task.done && meta.lastMoveFrom && (
              <span><Icon name={moveIcon(meta.lastMoveFrom, task.quadrant)} size={13} />from {quadrantLabel(meta.lastMoveFrom)}</span>
            )}
            {task.done && task.completed_at && <span>{task.quadrant === "eliminate" ? "dropped" : fmtTime(task.completed_at)}</span>}
          </span>
        </div>

        <span className="actions">
          {!task.done && (
            <button className="icon-btn play" onClick={onFocus} aria-label="Focus on this task" title="Focus">
              <Icon name="play" size={12} />
            </button>
          )}
          <button
            className="icon-btn more"
            onClick={(e) => {
              // Open upward when there isn't room below (desktop popover).
              setMenuUp(e.currentTarget.getBoundingClientRect().bottom > window.innerHeight - 440);
              onMenu(menuOpen ? null : task.id);
            }}
            aria-label="Task options" aria-expanded={menuOpen} aria-haspopup="menu"
          >
            <Icon name="more" size={16} />
          </button>
        </span>

        {menuOpen && (
          <TaskMenu
            task={task} meta={meta} actions={actions} up={menuUp}
            onClose={() => onMenu(null)}
            onFocus={() => { onMenu(null); onFocus(); }}
            onEdit={startEdit}
            onSubtasks={() => { setExpanded(true); onMenu(null); }}
          />
        )}
      </div>

      {expanded && <Subtasks task={task} onChange={(subs) => actions.setSubtasks(task.id, subs)} />}
    </>
  );
}

function history(task, meta) {
  const created = new Date(task.created_at);
  const day = localDate(created) === localDate() ? `today ${fmtTime(task.created_at)}` : created.toLocaleDateString("en-US", { weekday: "long" });
  const parts = [`Added ${day}`];
  if (meta.carried > 0) parts.push(`carried ${meta.carried} day${meta.carried === 1 ? "" : "s"}`);
  if (meta.lastMoveFrom) parts.push(`moved from ${quadrantLabel(meta.lastMoveFrom)}`);
  return parts.join(" · ");
}

// Popover on desktop, bottom sheet on phones (same markup, CSS decides).
function TaskMenu({ task, meta, actions, up, onClose, onFocus, onEdit, onSubtasks }) {
  const run = (fn) => () => { fn(); onClose(); };
  return (
    <>
      <div className="scrim menu-scrim" onClick={onClose} />
      <div className={`task-menu${up ? " up" : ""}`} role="menu" aria-label={`Options for ${task.text}`}>
        <div className="grab" />
        <div className="tm-title">
          <b>{task.text}</b>
          <span>{history(task, meta)}</span>
        </div>
        <div className="tm-label">Move to</div>
        <div className="moves">
          {QUADRANTS.map((q) => (
            <button
              key={q.id} role="menuitem" className={q.id === task.quadrant ? "current" : ""}
              disabled={q.id === task.quadrant}
              onClick={run(() => actions.move(task.id, q.id))}
            >
              <span className={`sq sq-${q.id}`} />
              <span className="mv-name">{q.label}</span>
              <small>{q.id === task.quadrant ? "Current" : q.sub}</small>
            </button>
          ))}
        </div>
        <div className="tm-list">
          {!task.done && <button role="menuitem" onClick={onFocus}><Icon name="play" size={14} />Start focus</button>}
          {!task.done && (
            <button role="menuitem" onClick={run(() => actions.carry([task.id], addDays(task.date, 1)))}><Icon name="cal" />Move to next day</button>
          )}
          {task.done && <button role="menuitem" onClick={run(() => actions.toggle(task.id))}><Icon name="undo" />Mark not done</button>}
          <button role="menuitem" onClick={onSubtasks}><Icon name="list" />{task.subtasks.length ? "Subtasks" : "Add subtasks"}</button>
          <button role="menuitem" onClick={onEdit}><Icon name="edit" />Rename</button>
          <button role="menuitem" className="danger" onClick={run(() => actions.remove(task.id))}><Icon name="trash" />Delete</button>
        </div>
      </div>
    </>
  );
}

function Subtasks({ task, onChange }) {
  const [val, setVal] = useState("");
  const subs = task.subtasks;
  const add = () => {
    if (!val.trim()) return;
    onChange([...subs, { id: newId(), text: val.trim(), done: false }]);
    setVal("");
  };
  const toggle = (st) => {
    const next = subs.map((s) => (s.id === st.id ? { ...s, done: !s.done } : s));
    if (!st.done && next.every((s) => s.done)) confettiAt(document.querySelector(`#task-${task.id} .chk`));
    onChange(next);
  };
  return (
    <div className="subtasks">
      {subs.map((st) => (
        <div key={st.id} className={`subtask${st.done ? " done" : ""}`}>
          <button className="chk small" onClick={() => toggle(st)} aria-label={st.done ? "Mark subtask not done" : "Mark subtask done"}>
            {st.done && <Icon name="check" size={9} />}
          </button>
          <span className="text">{st.text}</span>
          <button className="icon-btn x" onClick={() => onChange(subs.filter((s) => s.id !== st.id))} aria-label="Remove subtask">
            <Icon name="x" size={12} />
          </button>
        </div>
      ))}
      <div className="subtask add-sub">
        <Icon name="plus" size={13} />
        <input
          value={val} placeholder="Add subtask" aria-label="New subtask"
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
      </div>
    </div>
  );
}
