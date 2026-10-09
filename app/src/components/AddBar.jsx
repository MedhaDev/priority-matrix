import { forwardRef, useState } from "react";
import { quadrantFor, quadrantLabel } from "../lib/events";
import Icon from "./Icon";

// The same form is an inline bar on desktop and a bottom sheet on phones.
const AddForm = forwardRef(function AddForm({ onAdd, onDone, sheet = false }, ref) {
  const [text, setText] = useState("");
  const [urgent, setUrgent] = useState(false);
  const [important, setImportant] = useState(false);
  const lands = quadrantFor(urgent, important);

  const submit = () => {
    if (!text.trim()) return;
    onAdd(text.trim(), lands);
    setText(""); setUrgent(false); setImportant(false);
    onDone?.();
  };

  return (
    <div className={sheet ? "add-sheet-form" : "add"}>
      {!sheet && <Icon name="plus" className="add-plus" />}
      <input
        ref={ref} autoFocus={sheet}
        aria-label="New task" placeholder="Add a task" value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
          if (e.key === "Escape") { e.currentTarget.blur(); onDone?.(); }
        }}
      />
      <div className="add-row">
        <div className="seg" role="group" aria-label="Priority">
          <button className={urgent ? "on" : ""} aria-pressed={urgent} onClick={() => setUrgent((u) => !u)}>Urgent</button>
          <button className={important ? "on" : ""} aria-pressed={important} onClick={() => setImportant((i) => !i)}>Important</button>
        </div>
        <span className="lands" aria-live="polite"><span className={`sq sq-${lands}`} />{quadrantLabel(lands)}</span>
        {sheet
          ? <button className="btn-primary" onClick={submit} disabled={!text.trim()}>Add task</button>
          : <kbd className="enter" title="Press Enter to add">↵</kbd>}
      </div>
    </div>
  );
});

export default AddForm;
