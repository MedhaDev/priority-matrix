import { useState } from "react";
import TaskRow from "./TaskRow";
import Icon from "./Icon";

export default function Quadrant({ q, tasks, meta, editable, onQuickAdd, menuId, onMenu, actions, onFocus, drag }) {
  const [adding, setAdding] = useState(false);
  const [val, setVal] = useState("");
  const done = tasks.filter((t) => t.done).length;

  const submit = () => {
    if (val.trim()) onQuickAdd(val.trim(), q.id);
    setVal("");
  };

  return (
    <section
      id={`q-${q.id}`}
      className={`q${drag.overQuadrant === q.id && drag.dragId ? " drag-over" : ""}`}
      aria-label={q.label}
      onDragOver={(e) => {
        e.preventDefault();
        drag.setOverQuadrant(q.id);
        if (e.target === e.currentTarget) drag.setOverId(null); // empty space → drop at the end
      }}
      onDrop={(e) => { e.preventDefault(); drag.drop(q.id); }}
    >
      <div className="q-head">
        <span className={`sq sq-${q.id}`} />
        <h3>{q.label}</h3>
        <span className="sub">{q.sub}</span>
        <span className="count">{done} / {tasks.length}</span>
        {editable && (
          <button className="icon-btn q-add" onClick={() => setAdding(true)} aria-label={`Add a task to ${q.label}`}>
            <Icon name="plus" />
          </button>
        )}
      </div>

      {tasks.length === 0 && !adding && <p className="empty">No tasks</p>}

      {tasks.map((task) => (
        <TaskRow
          key={task.id}
          task={task}
          meta={meta.get(task.id)}
          menuOpen={menuId === task.id}
          onMenu={onMenu}
          actions={actions}
          onFocus={() => onFocus(task)}
          drag={{
            isOver: drag.overId === task.id && drag.dragId !== task.id,
            onStart: () => drag.start(task.id),
            onOver: () => drag.setOverId(task.id),
            onEnd: drag.end,
          }}
        />
      ))}

      {adding && (
        <div className="task quick-add">
          <span className="chk ghost" />
          <input
            autoFocus value={val} placeholder={`Add to ${q.label}`} aria-label={`New task in ${q.label}`}
            onChange={(e) => setVal(e.target.value)}
            onBlur={() => { submit(); setAdding(false); }}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
              if (e.key === "Escape") { setVal(""); setAdding(false); }
            }}
          />
        </div>
      )}
    </section>
  );
}
