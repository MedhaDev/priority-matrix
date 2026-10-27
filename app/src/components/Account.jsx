import { useState } from "react";
import { Dialog } from "./Modals";
import { statusLine } from "../lib/cloudSync";

// Sign in to sync tasks across devices (and to the database Claude reads).
export function AccountModal({ cloud, onClose }) {
  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  if (cloud.user) {
    return (
      <Dialog title="Sync" onClose={onClose}>
        <p>Signed in as <b>{cloud.user.email}</b>. Your tasks are saved to your account and on this device.</p>
        <p className="muted small">{statusLine(cloud)}</p>
        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={async () => { await cloud.signOut(); onClose(); }}>Sign out</button>
          <button className="btn btn-primary" onClick={onClose}>Done</button>
        </div>
      </Dialog>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    const { data, error: err } = mode === "signin" ? await cloud.signIn(email, password) : await cloud.signUp(email, password);
    setBusy(false);
    if (err) return setError(err.message);
    if (mode === "signup" && !data.session) {
      setMessage("Check your email and confirm your address, then sign in here.");
      setMode("signin");
      return;
    }
    onClose();
  };

  return (
    <Dialog title={mode === "signin" ? "Sign in to sync" : "Create an account"} onClose={onClose}>
      <p className="muted">
        Keeps your tasks in your own account, so they're on every device. This device keeps a copy and works offline.
      </p>
      <form className="account-form" onSubmit={submit}>
        <label>
          <span>Email</span>
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          <span>Password</span>
          <input
            type="password" required minLength={8}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password} onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {message && <p className="notice">{message}</p>}
        {error && <p className="error">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="btn btn-quiet" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(null); }}>
            {mode === "signin" ? "Create an account" : "I have an account"}
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "One moment…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

// Shown whenever changes haven't reached the cloud. Never silent.
export function SyncBanner({ cloud }) {
  if (!cloud.active || !["error", "offline"].includes(cloud.status) || !cloud.pending) return null;
  const n = `${cloud.pending} change${cloud.pending === 1 ? "" : "s"}`;
  return (
    <div className="sync-banner" role="alert">
      <span>
        {cloud.status === "offline"
          ? `You're offline. ${n} saved on this device will sync when you're back online.`
          : `Couldn't save ${n} to your account (${cloud.error}). They're safe on this device; retrying.`}
      </span>
      {cloud.status === "error" && <button onClick={cloud.retryNow}>Retry now</button>}
    </div>
  );
}
