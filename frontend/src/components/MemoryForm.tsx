import { useState } from "react";
import { api } from "../api";
import type { Facets, Memory, MemoryInput } from "../types";
import { CATEGORIES, ChipInput, Field, Modal, useAsync, useToast } from "../ui";

const DATE_RE = /^\d{4}(-\d{2}(-\d{2})?)?$/;

export default function MemoryForm({ existing, onSaved, onClose }: { existing?: Memory; onSaved: (m: Memory) => void; onClose: () => void }) {
  const toast = useToast();
  const facets = useAsync(() => api.get<Facets>("/api/memories/facets"), []);
  const [f, setF] = useState<MemoryInput>({
    title: existing?.title ?? "", body: existing?.body ?? "", memory_date: existing?.memory_date ?? "",
    category: existing?.category ?? "family", people: existing?.people ?? [], tags: existing?.tags ?? [],
  });
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dateBad = !!f.memory_date && !DATE_RE.test(f.memory_date);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const payload = { ...f, memory_date: f.memory_date || null };
      let saved = existing ? await api.put<Memory>(`/api/memories/${existing.id}`, payload) : await api.post<Memory>("/api/memories", payload);
      const failed: string[] = [];
      for (const file of files) {
        try { await api.upload(`/api/memories/${saved.id}/attachments`, file, file.name); }
        catch (err) { failed.push(`${file.name}: ${(err as Error).message}`); }
      }
      if (files.length) saved = await api.get<Memory>(`/api/memories/${saved.id}`);
      if (failed.length) toast("error", `Memory saved, but some files were not added - ${failed.join("; ")}`);
      else toast("ok", existing ? "Memory updated." : "Memory preserved.");
      onSaved(saved);
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <Modal title={existing ? "Edit memory" : "Preserve a memory"} onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Title">{(id) => <input id={id} required maxLength={200} autoFocus className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Grandma's Sunday bread" />}</Field>
        <Field label="The story" hint="Write it the way you would tell it. Names, places and little details make memories easier to find later.">
          {(id) => <textarea id={id} rows={8} className="input resize-y leading-relaxed" value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} />}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="When" hint="1984, 1984-06 or 1984-06-15. Leave empty if unknown.">
            {(id) => <input id={id} className="input" inputMode="numeric" aria-invalid={dateBad} value={f.memory_date ?? ""} placeholder="YYYY-MM-DD" onChange={(e) => setF({ ...f, memory_date: e.target.value.trim() })} />}
          </Field>
          <Field label="Category">
            {(id) => (
              <select id={id} className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
                {[...new Set([...CATEGORIES, f.category])].map((c) => <option key={c}>{c}</option>)}
              </select>
            )}
          </Field>
          <Field label="People">{(id) => <ChipInput id={id} value={f.people} onChange={(people) => setF({ ...f, people })} placeholder="Type a name, press Enter" suggestions={facets.data?.people.map((p) => p.name)} />}</Field>
          <Field label="Tags">{(id) => <ChipInput id={id} value={f.tags} onChange={(tags) => setF({ ...f, tags })} placeholder="e.g. summer, recipe" suggestions={facets.data?.tags.map((p) => p.name)} />}</Field>
        </div>
        <Field label={existing ? "Add more files" : "Photos, recordings or documents"} hint="Photos (PNG/JPEG/GIF/WebP), audio (WAV/MP3/M4A/OGG/FLAC/WebM), PDF or .txt. Files stay on this computer.">
          {(id) => <input id={id} type="file" multiple accept="image/*,audio/*,.pdf,.txt" className="input file:mr-3 file:rounded-md file:border-0 file:bg-ink-700 file:px-3 file:py-1 file:text-paper" onChange={(e) => setFiles([...(e.target.files ?? [])])} />}
        </Field>
        {error && <p role="alert" className="text-sm text-bad">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !f.title.trim() || dateBad}>{busy ? "Saving…" : existing ? "Save changes" : "Preserve memory"}</button>
        </div>
      </form>
    </Modal>
  );
}
