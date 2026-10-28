import { useState } from "react";
import { ApiError, api, formatBytes, formatMemoryDate } from "../api";
import type { Memory, RelatedItem } from "../types";
import { ConfirmDialog, ErrorNote, Modal, Spinner, useAsync, useToast } from "../ui";
import MemoryForm from "./MemoryForm";

export default function MemoryDetail({ id, onClose, onOpen, onChanged }: {
  id: string; onClose: () => void; onOpen: (id: string) => void; onChanged: () => void;
}) {
  const toast = useToast();
  const mem = useAsync(() => api.get<Memory>(`/api/memories/${id}`), [id]);
  const related = useAsync(() => api.get<{ items: RelatedItem[] }>(`/api/memories/${id}/related`), [id]);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState("");
  const m = mem.data;

  const del = async () => {
    setBusy("delete");
    try {
      const r = await api.del<{ files_removed: number; note: string }>(`/api/memories/${id}`);
      toast("ok", `Deleted. ${r.files_removed} attached file(s) removed from GHOST's storage.`);
      onChanged(); onClose();
    } catch (e) { toast("error", (e as Error).message); setBusy(""); setConfirming(false); }
  };
  const ocr = async (attId: string) => {
    setBusy(attId);
    try {
      const r = await api.post<{ characters: number }>(`/api/attachments/${attId}/ocr`);
      toast("ok", `Read ${r.characters} characters from the image. Review them - OCR can misread.`);
      mem.reload(); onChanged();
    } catch (e) { toast(e instanceof ApiError && e.status === 503 ? "info" : "error", (e as Error).message); }
    finally { setBusy(""); }
  };
  const addFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy("upload");
    try { await api.upload(`/api/memories/${id}/attachments`, file, file.name); toast("ok", "File added."); mem.reload(); onChanged(); }
    catch (e) { toast("error", (e as Error).message); }
    finally { setBusy(""); }
  };
  const removeAtt = async (attId: string) => {
    try { await api.del(`/api/attachments/${attId}`); toast("ok", "Attachment removed."); mem.reload(); onChanged(); }
    catch (e) { toast("error", (e as Error).message); }
  };

  if (editing && m) return <MemoryForm existing={m} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); mem.reload(); related.reload(); onChanged(); }} />;

  return (
    <Modal title={m?.title ?? "Memory"} onClose={onClose} wide>
      {mem.loading && !m && <Spinner />}
      {mem.error && <ErrorNote error={mem.error} onRetry={mem.reload} />}
      {m && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="chip border-amber-400/50 text-amber-300">{formatMemoryDate(m.memory_date)}</span>
            <span className="chip">{m.category}</span>
            {m.is_demo && <span className="chip border-mist/50 text-mist">Synthetic demo data</span>}
            {m.source === "oral_history" && <span className="chip">From oral history</span>}
            {m.people.map((p) => <span key={p} className="chip">👤 {p}</span>)}
            {m.tags.map((t) => <span key={t} className="chip text-muted">#{t}</span>)}
          </div>
          <article className="prose-ghost whitespace-pre-wrap text-[0.95rem] leading-relaxed">{m.body || <span className="text-muted">No text written yet.</span>}</article>

          {m.attachments.length > 0 && (
            <section aria-label="Attachments" className="space-y-3">
              <h3 className="eyebrow">Attachments</h3>
              {m.attachments.map((a) => (
                <div key={a.id} className="rounded-xl border border-ink-700 bg-ink-950/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span className="truncate">{a.kind === "photo" ? "🖼" : a.kind === "audio" ? "🎙" : "📄"} {a.original_name} <span className="text-muted">· {formatBytes(a.size)}</span></span>
                    <span className="flex gap-2">
                      {a.kind === "photo" && <button className="btn px-2 py-1 text-xs" disabled={busy === a.id} onClick={() => ocr(a.id)}>{busy === a.id ? "Reading…" : a.has_ocr ? "Re-run OCR" : "Read text (OCR)"}</button>}
                      <a className="btn px-2 py-1 text-xs" href={a.url} target="_blank" rel="noreferrer">Open</a>
                      <button className="btn btn-danger px-2 py-1 text-xs" onClick={() => removeAtt(a.id)} aria-label={`Remove ${a.original_name}`}>Remove</button>
                    </span>
                  </div>
                  {a.kind === "photo" && <img src={a.url} alt={a.original_name} className="mt-3 max-h-80 rounded-lg object-contain" />}
                  {a.kind === "audio" && <audio controls src={a.url} className="mt-3 w-full" preload="none" />}
                </div>
              ))}
            </section>
          )}

          <section aria-label="Related memories">
            <h3 className="eyebrow mb-2">Related memories</h3>
            {related.loading ? <Spinner /> : related.data?.items.length ? (
              <ul className="grid gap-2 sm:grid-cols-2">
                {related.data.items.map((r) => (
                  <li key={r.id}>
                    <button className="card card-hover w-full p-3 text-left" onClick={() => onOpen(r.id)}>
                      <p className="font-medium">{r.title}</p>
                      <p className="text-xs text-muted">{formatMemoryDate(r.memory_date)} · {r.reason}</p>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">Nothing closely related yet. As your archive grows, connections will appear.</p>}
          </section>

          <p className="text-xs text-muted">Saved {new Date(m.created_at).toLocaleDateString()} · last edited {new Date(m.updated_at).toLocaleDateString()}</p>
          <div className="flex flex-wrap justify-between gap-2 border-t border-ink-700 pt-4">
            <label className="btn cursor-pointer">
              {busy === "upload" ? "Uploading…" : "＋ Add file"}
              <input type="file" className="sr-only" onChange={(e) => { void addFile(e.target.files?.[0]); e.target.value = ""; }} />
            </label>
            <span className="flex gap-2">
              <button className="btn" onClick={() => setEditing(true)}>Edit</button>
              <button className="btn btn-danger" onClick={() => setConfirming(true)}>Delete</button>
            </span>
          </div>
        </div>
      )}
      {confirming && m && (
        <ConfirmDialog title="Delete this memory?" confirmLabel="Delete permanently" busy={busy === "delete"} onCancel={() => setConfirming(false)} onConfirm={del}
          body={<>
            <p><strong>“{m.title}”</strong> and its {m.attachments.length} attached file(s) will be removed from GHOST, including its search index entries.</p>
            <p className="text-muted">This cannot be undone. Copies in backups or exports you made earlier are <em>not</em> erased, and on SSDs traces can remain until overwritten.</p>
          </>} />
      )}
    </Modal>
  );
}
