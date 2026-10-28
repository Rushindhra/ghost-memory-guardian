import { useEffect, useState } from "react";
import { api, qs } from "../api";
import type { LifeDoc } from "../types";
import { ConfirmDialog, EmptyState, ErrorNote, Field, Modal, Notice, PageHeader, Spinner, useAsync, useToast } from "../ui";

const KINDS = [
  ["document", "Important document"], ["warranty", "Warranty"], ["recipe", "Recipe"], ["contact", "Emergency contact"],
  ["date", "Meaningful date"], ["task", "Task"], ["note", "Note"],
] as const;
const kindName = (k: string) => KINDS.find((x) => x[0] === k)?.[1] ?? k;
const today = () => new Date().toISOString().slice(0, 10);

function Due({ d }: { d: LifeDoc }) {
  const items = [["Reminder", d.remind_date], ["Expires", d.expiry_date]] as const;
  return <>{items.filter(([, v]) => v).map(([l, v]) => {
    const late = v! < today();
    return <span key={l} className={`chip ${late ? "border-bad/60 text-bad" : "border-amber-400/50 text-amber-300"}`}>{l}: {v}{late ? " (past)" : ""}</span>;
  })}</>;
}

export default function LifeDocs() {
  const toast = useToast();
  const [q, setQ] = useState(""); const [dq, setDq] = useState(""); const [kind, setKind] = useState("");
  const [editing, setEditing] = useState<LifeDoc | "new" | null>(null);
  const [deleting, setDeleting] = useState<LifeDoc | null>(null);
  useEffect(() => { const t = setTimeout(() => setDq(q), 250); return () => clearTimeout(t); }, [q]);
  const list = useAsync(() => api.get<{ items: LifeDoc[]; disclaimer: string }>(`/api/life-docs${qs({ q: dq, kind })}`), [dq, kind]);
  const items = list.data?.items ?? [];
  const hasDates = items.some((d) => d.remind_date || d.expiry_date);

  const remove = async () => {
    if (!deleting) return;
    try { await api.del(`/api/life-docs/${deleting.id}`); toast("ok", "Deleted."); list.reload(); }
    catch (e) { toast("error", (e as Error).message); }
    setDeleting(null);
  };

  return (
    <>
      <PageHeader eyebrow="Life Documents" title="The practical side of remembering">
        <span className="flex gap-2">
          {hasDates && <a className="btn" href="/api/life-docs/export.ics" download>Export all reminders (.ics)</a>}
          <button className="btn btn-primary" onClick={() => setEditing("new")}>＋ New entry</button>
        </span>
      </PageHeader>
      <Notice>{list.data?.disclaimer ?? "Personal notes for your own organisation. Not legal, medical or financial advice."} Everything here stays on this computer.</Notice>

      <div className="card my-5 grid gap-3 sm:grid-cols-3">
        <div className="sm:col-span-2"><label htmlFor="lq" className="label">Search titles, notes, kinds and dates</label>
          <input id="lq" type="search" className="input" placeholder="e.g. passport, 2027-03, boiler warranty" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div><label htmlFor="lk" className="label">Kind</label>
          <select id="lk" className="input" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">All kinds</option>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
      </div>

      {list.loading && !list.data && <Spinner />}
      {list.error && <ErrorNote error={list.error} onRetry={list.reload} />}
      {list.data && items.length === 0 && (dq || kind
        ? <EmptyState title="Nothing matches">Try other words or clear the kind filter.</EmptyState>
        : <EmptyState title="No entries yet" action={<button className="btn btn-primary" onClick={() => setEditing("new")}>Add the first one</button>}>Keep notes about warranties, recipes, emergency contacts and dates that matter, then export reminders to any calendar app.</EmptyState>)}
      <ul className="grid gap-4 md:grid-cols-2">
        {items.map((d) => (
          <li key={d.id} className="card flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2"><span className="chip">{kindName(d.kind)}</span>{d.is_demo && <span className="chip border-mist/50 text-mist">demo</span>}<Due d={d} /></div>
            <h2 className="font-display text-xl">{d.title}</h2>
            {d.notes && <p className="line-clamp-4 whitespace-pre-wrap text-sm text-muted">{d.notes}</p>}
            <div className="mt-auto flex flex-wrap gap-2 pt-2">
              <button className="btn px-3 py-1.5 text-xs" onClick={() => setEditing(d)}>Edit</button>
              {(d.remind_date || d.expiry_date) && <a className="btn px-3 py-1.5 text-xs" href={`/api/life-docs/${d.id}/ics`} download>Add to calendar (.ics)</a>}
              <button className="btn btn-danger px-3 py-1.5 text-xs" onClick={() => setDeleting(d)}>Delete</button>
            </div>
          </li>
        ))}
      </ul>
      {editing && <DocForm doc={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); list.reload(); }} />}
      {deleting && <ConfirmDialog title="Delete this entry?" confirmLabel="Delete" onCancel={() => setDeleting(null)} onConfirm={remove} body={<p>“{deleting.title}” will be removed from GHOST. This cannot be undone.</p>} />}
    </>
  );
}

function DocForm({ doc, onClose, onSaved }: { doc?: LifeDoc; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({ title: doc?.title ?? "", kind: doc?.kind ?? "note", notes: doc?.notes ?? "", expiry_date: doc?.expiry_date ?? "", remind_date: doc?.remind_date ?? "" });
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    const body = { ...f, expiry_date: f.expiry_date || null, remind_date: f.remind_date || null };
    try { await (doc ? api.put(`/api/life-docs/${doc.id}`, body) : api.post("/api/life-docs", body)); toast("ok", "Saved."); onSaved(); }
    catch (x) { setErr((x as Error).message); setBusy(false); }
  };
  return (
    <Modal title={doc ? "Edit entry" : "New entry"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Title">{(id) => <input id={id} required maxLength={200} className="input" value={f.title} onChange={set("title")} autoFocus />}</Field>
        <Field label="Kind">{(id) => <select id={id} className="input" value={f.kind} onChange={set("kind")}>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>}</Field>
        <Field label="Notes" hint="Where the original is kept, account references, steps. Avoid storing full card or password details.">{(id) => <textarea id={id} rows={5} className="input" maxLength={20000} value={f.notes} onChange={set("notes")} />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Expiry date">{(id) => <input id={id} type="date" className="input" value={f.expiry_date} onChange={set("expiry_date")} />}</Field>
          <Field label="Remind me on">{(id) => <input id={id} type="date" className="input" value={f.remind_date} onChange={set("remind_date")} />}</Field>
        </div>
        {err && <p role="alert" className="text-sm text-bad">{err}</p>}
        <div className="flex justify-end gap-2"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={busy || !f.title.trim()}>{busy ? "Saving…" : "Save"}</button></div>
      </form>
    </Modal>
  );
}
