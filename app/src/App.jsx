import { useEffect, useMemo, useRef, useState } from "react";
import { QUADRANTS } from "./lib/events";
import { addDays, localDate } from "./lib/dates";
import { useStore } from "./lib/useStore";
import { useFocus } from "./lib/useFocus";
import { daySummary, taskMeta } from "./lib/stats";
import { backupBeforeImport, carryAskedOn, clearDemo, loadMode, markCarryAsked, saveData, saveMode } from "./lib/storage";
import { generateDemo } from "./lib/demo";
import Quadrant from "./components/Quadrant";
import AddForm from "./components/AddBar";
import FocusOverlay from "./components/FocusOverlay";
import Patterns from "./components/Patterns";
import Icon, { Logo } from "./components/Icon";
import { AboutModal, AddSheet, CarryOverModal, ExportModal } from "./components/Modals";

// Real data and demo data live under separate storage keys. Switching
// remounts the whole app (via `key`), so the two can never mix.
export default function Root() {
  const [mode, setMode] = useState(loadMode);
  const switchMode = (next) => {
    if (next === "demo") saveData("demo", generateDemo());
    else clearDemo();
    saveMode(next);
    setMode(next);
  };
  return <App key={mode} mode={mode} onSwitchMode={switchMode} />;
}

// Re-check the time every minute and whenever the app comes back to the
// foreground, so "today" rolls over at midnight on an open phone.
function useClock() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = () => setNow(Date.now());
    const iv = setInterval(tick, 60000);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(iv); document.removeEventListener("visibilitychange", tick); };
  }, []);
  return now;
}

function useView() {
  const read = () => (window.location.hash === "#patterns" ? "patterns" : "matrix");
  const [view, setView] = useState(read);
  useEffect(() => {
    const sync = () => setView(read());
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  const go = (v) => {
    if (v === view) return;
    history.pushState(null, "", v === "patterns" ? "#patterns" : window.location.pathname);
    setView(v);
    window.scrollTo(0, 0);
  };
  return [view, go];
}

const isPhone = () => window.matchMedia("(max-width: 760px)").matches;
const NO_DRAG = { dragId: null, overId: null, overQuadrant: null };

function DateNav({ date, today, setDate, className }) {
  const d = new Date(date + "T12:00:00");
  const weekday = d.toLocaleDateString("en-US", { weekday: "long" });
  const short = d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return (
    <div className={`date ${className}`}>
      <button className="icon-btn" onClick={() => setDate(addDays(date, -1))} aria-label="Previous day"><Icon name="left" /></button>
      <span className="d"><b>{weekday}</b> <span>{short}</span></span>
      <button className="icon-btn" onClick={() => setDate(addDays(date, 1))} aria-label="Next day"><Icon name="right" /></button>
      {date !== today && <button className="today-btn" onClick={() => setDate(today)}>Today</button>}
    </div>
  );
}

function App({ mode, onSwitchMode }) {
  const isDemo = mode === "demo";
  const { tasks, events, actions } = useStore(mode);
  const focus = useFocus({ mode, tasks, log: actions.log });
  const now = useClock();
  const today = localDate(new Date(now));
  const addRef = useRef(null);

  const [date, setDate] = useState(today);
  const [view, setView] = useView();
  const [menuId, setMenuId] = useState(null);
  const [modal, setModal] = useState(null); // "export" | "about" | "add"
  const [drag, setDrag] = useState(NO_DRAG);
  const [carryIds, setCarryIds] = useState(() => {
    if (isDemo || carryAskedOn(mode) === today) return null;
    const ids = tasks.filter((t) => !t.done && t.date < today).map((t) => t.id);
    return ids.length ? ids : null;
  });

  const isToday = date === today;
  const canAdd = date >= today;
  const viewTasks = useMemo(() => tasks.filter((t) => t.date === date), [tasks, date]);
  const meta = useMemo(() => taskMeta(events), [events]);
  const summary = useMemo(() => daySummary({ tasks: viewTasks, events, date, isToday, now }), [viewTasks, events, date, isToday, now]);

  const todayTasks = tasks.filter((t) => t.date === today);
  const topTask = todayTasks.find((t) => t.quadrant === "do" && !t.done) || todayTasks.find((t) => !t.done);
  const sessionsToday = events.filter((e) => e.event_type === "pomodoro_started" && e.local_date === today).length;
  const focusTask = focus.active ? tasks.find((t) => t.id === focus.active.task_id) : null;

  const openFocus = (task) => { setMenuId(null); focus.open(task); };
  const addTask = (text, quadrant) => actions.add(text, quadrant, date);

  // Desktop popover: close on outside click. (On phones the sheet's scrim handles it.)
  useEffect(() => {
    if (!menuId) return;
    const onDown = (e) => { if (!e.target.closest(".task-menu, .more")) setMenuId(null); };
    const onKey = (e) => e.key === "Escape" && setMenuId(null);
    document.addEventListener("pointerdown", onDown);
    window.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("pointerdown", onDown); window.removeEventListener("keydown", onKey); };
  }, [menuId]);

  // Shortcuts: N = new task, F = focus on the top task.
  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey || focus.active || modal) return;
      if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) return;
      if (e.key === "n" && view === "matrix" && canAdd) {
        e.preventDefault();
        if (isPhone()) setModal("add"); else addRef.current?.focus();
      }
      if (e.key === "f" && topTask) { e.preventDefault(); openFocus(topTask); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const dragApi = {
    ...drag,
    start: (id) => setDrag({ ...NO_DRAG, dragId: id }),
    setOverId: (id) => setDrag((d) => (d.overId === id ? d : { ...d, overId: id })),
    setOverQuadrant: (q) => setDrag((d) => (d.overQuadrant === q ? d : { ...d, overQuadrant: q })),
    end: () => setDrag(NO_DRAG),
    drop: (q) => {
      if (drag.dragId) {
        const before = viewTasks.find((t) => t.id === drag.overId && t.quadrant === q);
        actions.move(drag.dragId, q, before?.id ?? null);
      }
      setDrag(NO_DRAG);
    },
  };

  const finishCarry = (carry) => {
    if (carry) { actions.carry(carryIds, today); setDate(today); }
    markCarryAsked(mode, today);
    setCarryIds(null);
  };

  return (
    <>
      <div id="confetti-root" aria-hidden />

      {isDemo && (
        <div className="demo-banner">
          <span>Demo data from a simulated person.</span>
          <button onClick={() => onSwitchMode("real")}>Exit demo</button>
        </div>
      )}

      <div className="wrap">
        <header className="top">
          <button className="brand" onClick={() => setView("matrix")}><Logo />Priority</button>
          {view === "matrix" ? <DateNav className="date-top" date={date} today={today} setDate={setDate} /> : <span />}
          <div className="top-right">
            <div className="tabs" role="tablist" aria-label="View">
              <button role="tab" aria-selected={view === "matrix"} className={view === "matrix" ? "on" : ""} onClick={() => setView("matrix")}>Matrix</button>
              <button role="tab" aria-selected={view === "patterns"} className={view === "patterns" ? "on" : ""} onClick={() => setView("patterns")}>Patterns</button>
            </div>
            <button
              className="btn-focus" disabled={!topTask} onClick={() => topTask && openFocus(topTask)}
              title={topTask ? `Focus on: ${topTask.text}` : "Nothing left to focus on today"}
            >
              <Icon name="play" size={12} />Focus<kbd>F</kbd>
            </button>
          </div>
        </header>

        {view === "patterns" ? (
          <Patterns tasks={tasks} events={events} isDemo={isDemo} onLoadDemo={() => onSwitchMode("demo")} />
        ) : (
          <main>
            <DateNav className="date-row" date={date} today={today} setDate={setDate} />

            <section className="intro">
              <p className="summary">
                {summary.lead}{summary.soft ? <>, <span className="soft">{summary.soft}</span></> : "."}
              </p>
              {summary.nudge && <p className="nudge"><span className="sq sq-schedule" />{summary.nudge}</p>}
            </section>

            {canAdd && <AddForm ref={addRef} onAdd={addTask} />}

            <nav className="map" aria-label="Jump to quadrant">
              {QUADRANTS.map((q) => {
                const qs = viewTasks.filter((t) => t.quadrant === q.id);
                const warn = q.id === "schedule" && summary.nudge;
                return (
                  <a key={q.id} href={`#q-${q.id}`} className={warn ? "warn" : ""}
                    onClick={(e) => { e.preventDefault(); document.getElementById(`q-${q.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>
                    <span className={`sq sq-${q.id}`} />{q.label}<span className="n">{qs.filter((t) => t.done).length}/{qs.length}</span>
                  </a>
                );
              })}
            </nav>

            <div className="matrix">
              <div className="axis-top" aria-hidden><span>Urgent</span><span>Not urgent</span></div>
              <div className="axis-left" aria-hidden><span>Important</span><span>Not important</span></div>
              <div className="sheet">
                {QUADRANTS.map((q) => (
                  <Quadrant
                    key={q.id}
                    q={q}
                    tasks={viewTasks.filter((t) => t.quadrant === q.id)}
                    meta={meta}
                    editable={canAdd}
                    onQuickAdd={addTask}
                    menuId={menuId}
                    onMenu={setMenuId}
                    actions={actions}
                    onFocus={openFocus}
                    drag={dragApi}
                  />
                ))}
              </div>
            </div>
          </main>
        )}

        <footer className="foot">
          <span>{isDemo ? "Simulated data" : "Saved on this device"} · {events.length.toLocaleString()} events</span>
          <nav>
            <button onClick={() => setModal("export")}>Export</button>
            <button onClick={() => onSwitchMode(isDemo ? "real" : "demo")}>{isDemo ? "Exit demo" : "Demo data"}</button>
            <button onClick={() => setModal("about")}>How it works</button>
            <a href="https://medhadev.github.io/" target="_blank" rel="noreferrer">Medha Devalraj</a>
          </nav>
        </footer>
      </div>

      {view === "matrix" && (
        <div className="dock">
          {canAdd && <button className="dock-add" onClick={() => setModal("add")}><Icon name="plus" size={18} />Add a task</button>}
          <button className="dock-focus" disabled={!topTask} onClick={() => topTask && openFocus(topTask)} aria-label="Start focus">
            <Icon name="play" size={16} />
          </button>
        </div>
      )}

      {modal === "add" && (
        <AddSheet onClose={() => setModal(null)}>
          <AddForm sheet onAdd={addTask} onDone={() => setModal(null)} />
        </AddSheet>
      )}
      {focus.active && (
        <FocusOverlay focus={focus} task={focusTask} sessionsToday={sessionsToday} onCompleteTask={actions.toggle} />
      )}
      {carryIds && !focus.active && (
        <CarryOverModal
          count={carryIds.length}
          onCarry={() => finishCarry(true)}
          onLeave={() => finishCarry(false)}
          onDismiss={() => setCarryIds(null)}
        />
      )}
      {modal === "export" && (
        <ExportModal
          data={{ tasks, events }}
          isDemo={isDemo}
          onImport={(backup) => { backupBeforeImport({ tasks, events }); actions.replace(backup); }}
          onClose={() => setModal(null)}
        />
      )}
      {modal === "about" && <AboutModal onClose={() => setModal(null)} />}
    </>
  );
}
