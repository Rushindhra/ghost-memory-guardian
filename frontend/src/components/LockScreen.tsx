import { useState } from "react";
import { api } from "../api";

export default function LockScreen({ onUnlocked }: { onUnlocked: () => void }) {
  const [pass, setPass] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try { await api.post("/api/privacy/unlock", { passphrase: pass }); onUnlocked(); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); setPass(""); }
  };
  return (
    <div className="grid min-h-screen place-items-center px-4">
      <form onSubmit={submit} className="card rise w-full max-w-sm space-y-4 text-center" aria-labelledby="lock-title">
        <span className="candle mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-amber-400 text-3xl text-ink-950" aria-hidden>👻</span>
        <h1 id="lock-title" className="font-display text-2xl">Your archive is locked</h1>
        <p className="text-sm text-muted">Enter the passphrase you chose in the Privacy Center. It is checked on this computer only.</p>
        <div className="text-left">
          <label htmlFor="pp" className="label">Passphrase</label>
          <input id="pp" type="password" autoFocus autoComplete="current-password" className="input" value={pass} onChange={(e) => setPass(e.target.value)} />
        </div>
        {error && <p role="alert" className="text-sm text-bad">{error}</p>}
        <button className="btn btn-primary w-full" disabled={busy || !pass}>{busy ? "Checking…" : "Unlock"}</button>
      </form>
    </div>
  );
}
