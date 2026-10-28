import { useState } from "react";
import { api, formatBytes } from "../api";
import type { PrivacyReport } from "../types";
import { ErrorNote, Field, Notice, PageHeader, Spinner, useAsync, useToast } from "../ui";

export default function Privacy({ onLockChange }: { onLockChange: () => void }) {
  const toast = useToast();
  const rep = useAsync(() => api.get<PrivacyReport>("/api/privacy/report"), []);
  const [pass, setPass] = useState(""); const [pass2, setPass2] = useState(""); const [busy, setBusy] = useState(false);
  const [dir, setDir] = useState(""); const [dirNote, setDirNote] = useState("");
  const r = rep.data;

  const enable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pass !== pass2) return toast("error", "The two passphrases do not match.");
    setBusy(true);
    try { await api.post("/api/privacy/lock/enable", { passphrase: pass }); toast("ok", "Passphrase lock enabled. It does not encrypt files on disk."); setPass(""); setPass2(""); rep.reload(); onLockChange(); }
    catch (x) { toast("error", (x as Error).message); } finally { setBusy(false); }
  };
  const disable = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true);
    try { await api.post("/api/privacy/lock/disable", { passphrase: pass }); toast("ok", "Passphrase lock removed."); setPass(""); rep.reload(); onLockChange(); }
    catch (x) { toast("error", (x as Error).message); } finally { setBusy(false); }
  };
  const lockNow = async () => { await api.post("/api/privacy/logout"); onLockChange(); };
  const saveDir = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true);
    try { const x = await api.post<{ data_dir: string; note: string }>("/api/privacy/storage", { data_dir: dir }); setDirNote(x.note); toast("ok", `Storage folder set to ${x.data_dir}. Restart the backend to apply.`); }
    catch (x) { toast("error", (x as Error).message); } finally { setBusy(false); }
  };

  return (
    <>
      <PageHeader eyebrow="Privacy Center" title="Yours alone" />
      {rep.loading && !r && <Spinner />}
      {rep.error && <ErrorNote error={rep.error} onRetry={rep.reload} />}
      {r && (
        <div className="space-y-6">
          <section className="card border-ok/40" aria-labelledby="local">
            <h2 id="local" className="font-display text-2xl text-ok">● Local-only operation</h2>
            <ul className="mt-3 space-y-2 text-sm text-paper/90">
              <li><strong>Telemetry:</strong> {r.telemetry}.</li>
              <li><strong>Logging:</strong> {r.logging}</li>
              {r.network_endpoints.map((n) => <li key={n.url}><strong>Only network address used:</strong> {n.purpose} at <code className="rounded bg-ink-950 px-1.5 py-0.5">{n.url}</code> — {n.loopback ? <span className="text-ok">loopback (this computer only)</span> : <span className="text-warn">NOT loopback{n.remote_allowed ? " (explicitly allowed)" : ""}</span>}</li>)}
              <li><strong>Offline:</strong> {r.offline_note}</li>
            </ul>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="card space-y-3" aria-labelledby="lock">
              <h2 id="lock" className="font-display text-2xl">Passphrase lock</h2>
              <p className="text-sm text-muted">Status: <strong className={r.lock_enabled ? "text-ok" : "text-warn"}>{r.lock_enabled ? "enabled" : "not set"}</strong>. The passphrase is stored only as a salted, slow hash — never in plaintext — and checked on this computer. There is no recovery: if you forget it, restore from a backup.</p>
              {!r.lock_enabled ? (
                <form onSubmit={enable} className="space-y-3">
                  <Field label="New passphrase (min. 8 characters)">{(id) => <input id={id} type="password" autoComplete="new-password" className="input" minLength={8} value={pass} onChange={(e) => setPass(e.target.value)} />}</Field>
                  <Field label="Repeat passphrase">{(id) => <input id={id} type="password" autoComplete="new-password" className="input" value={pass2} onChange={(e) => setPass2(e.target.value)} />}</Field>
                  <button className="btn btn-primary" disabled={busy || pass.length < 8}>Enable lock</button>
                </form>
              ) : (
                <form onSubmit={disable} className="space-y-3">
                  <Field label="Current passphrase">{(id) => <input id={id} type="password" autoComplete="current-password" className="input" value={pass} onChange={(e) => setPass(e.target.value)} />}</Field>
                  <div className="flex gap-2"><button type="button" className="btn" onClick={lockNow}>Lock now</button><button className="btn btn-danger" disabled={busy || !pass}>Remove lock</button></div>
                </form>
              )}
              <Notice tone="warn" title="What the lock does not do">{r.encryption_recommendation}</Notice>
            </section>

            <section className="card space-y-3" aria-labelledby="backup">
              <h2 id="backup" className="font-display text-2xl">Export & backup</h2>
              <p className="text-sm text-muted">Your archive is never trapped. Open formats, no account needed.</p>
              <div className="flex flex-wrap gap-2">
                <a className="btn btn-primary" href="/api/export/backup" download>Full backup (.zip)</a>
                <a className="btn" href="/api/export/json" download>JSON</a>
                <a className="btn" href="/api/export/markdown" download>Markdown</a>
              </div>
              <p className="text-xs text-muted">The .zip contains the database and every attached file, so it can be restored with <code>scripts/restore_backup.py</code> (see docs/BACKUP.md). It is <strong>not encrypted</strong>: encrypt it before storing it elsewhere.</p>
            </section>
          </div>

          <section className="card space-y-3" aria-labelledby="storage">
            <h2 id="storage" className="font-display text-2xl">Where your data lives</h2>
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[10rem_1fr]">
              <dt className="text-muted">Data folder</dt><dd className="break-all"><code>{r.storage.data_dir}</code></dd>
              <dt className="text-muted">Database</dt><dd>{formatBytes(r.storage.bytes.database)}</dd>
              <dt className="text-muted">Attached files</dt><dd>{formatBytes(r.storage.bytes.files)}</dd>
              <dt className="text-muted">Search index</dt><dd>{formatBytes(r.storage.bytes.index)}</dd>
              <dt className="text-muted">Models folder</dt><dd className="break-all"><code>{r.storage.models}</code></dd>
            </dl>
            <form onSubmit={saveDir} className="space-y-2 border-t border-ink-700 pt-3">
              <Field label="Change data folder (absolute path, applied after restart)" hint="Existing memories are not moved automatically. Download a backup first and restore it into the new folder.">
                {(id) => <input id={id} className="input" placeholder="/home/you/ghost-data  or  D:\GhostData" value={dir} onChange={(e) => setDir(e.target.value)} />}
              </Field>
              <button className="btn" disabled={busy || !dir.trim()}>Save folder choice</button>
              {dirNote && <p className="text-xs text-muted">{dirNote}</p>}
            </form>
          </section>

          <Notice tone="warn" title="About deleting">{r.deletion_notice}</Notice>
        </div>
      )}
    </>
  );
}
