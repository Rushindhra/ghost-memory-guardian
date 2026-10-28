import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import MemoryDetail from "../components/MemoryDetail";
import type { Facets, Transcript } from "../types";
import { ChipInput, ConfirmDialog, EmptyState, ErrorNote, Field, Notice, PageHeader, Spinner, useAsync, useToast, CATEGORIES } from "../ui";

function Recorder({ onDone, disabled }: { onDone: (blob: Blob, name: string) => void; disabled: boolean }) {
  const [state, setState] = useState<"idle" | "recording">("idle");
  const [secs, setSecs] = useState(0);
  const [err, setErr] = useState("");
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | undefined>(undefined);
  const supported = typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

  useEffect(() => () => { window.clearInterval(timer.current); rec.current?.stream.getTracks().forEach((t) => t.stop()); }, []);

  const start = async () => {
    setErr("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const type = mr.mimeType || "audio/webm";
        onDone(new Blob(chunks.current, { type }), `recording-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-")}.${type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm"}`);
      };
      mr.start(); rec.current = mr; setSecs(0); setState("recording");
      timer.current = window.setInterval(() => setSecs((s) => s + 1), 1000);
    } catch { setErr("Microphone access was blocked or no microphone was found. You can upload an audio file instead."); }
  };
  const stop = () => { window.clearInterval(timer.current); rec.current?.stop(); setState("idle"); };

  if (!supported) return <p className="text-sm text-muted">Recording isn't available in this browser; upload a file instead.</p>;
  return (
    <div className="flex flex-wrap items-center gap-3">
      {state === "idle" ? <button className="btn" onClick={start} disabled={disabled}>● Record</button>
        : <button className="btn btn-danger" onClick={stop}>■ Stop &amp; save ({Math.floor(secs / 60)}:{String(secs % 60).padStart(2, "0")})</button>}
      {state === "recording" && <span className="candle text-sm text-bad" role="status">Recording… speak naturally</span>}
      {err && <span role="alert" className="text-sm text-bad">{err}</span>}
    </div>
  );
}

export default function Oral() {
  const toast = useToast();
  const list = useAsync(() => api.get<{ items: Transcript[] }>("/api/oral"), []);
  const facets = useAsync(() => api.get<Facets>("/api/memories/facets"), []);
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [language, setLanguage] = useState("");
  const [text, setText] = useState(""); const [title, setTitle] = useState("");
  const [meta, setMeta] = useState({ date: "", category: "family", people: [] as string[], tags: [] as string[] });
  const [savedMemory, setSavedMemory] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const current = list.data?.items.find((t) => t.id === sel);

  useEffect(() => { if (current) { setText(current.text); setTitle(current.title); } }, [current?.id, current?.text]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!sel && list.data?.items.length) setSel(list.data.items[0].id); }, [list.data, sel]);

  const upload = async (file: Blob, name: string, transcribe = true) => {
    setBusy("upload");
    try {
      const r = await api.upload<{ transcript: Transcript; message: string | null }>("/api/oral", file, name, { language, transcribe: String(transcribe) });
      if (r.message) toast("info", `Recording saved. ${r.message}`); else toast("ok", "Recording transcribed. Please review it carefully.");
      setSel(r.transcript.id); list.reload();
    } catch (e) { toast("error", (e as Error).message); }
    finally { setBusy(""); }
  };
  const transcribe = async () => {
    if (!current) return;
    setBusy("transcribe");
    try { await api.post(`/api/oral/${current.id}/transcribe`, { language }); toast("ok", "Transcribed. Please review it."); list.reload(); }
    catch (e) { toast("error", (e as Error).message); }
    finally { setBusy(""); }
  };
  const saveDraft = async () => {
    if (!current) return;
    setBusy("draft");
    try { await api.put(`/api/oral/${current.id}`, { text, title, language: current.language }); toast("ok", "Transcript saved."); list.reload(); }
    catch (e) { toast("error", (e as Error).message); }
    finally { setBusy(""); }
  };
  const confirm = async () => {
    if (!current) return;
    setBusy("confirm");
    try {
      if (text !== current.text || title !== current.title) await api.put(`/api/oral/${current.id}`, { text, title, language: current.language });
      const m = await api.post<{ id: string }>(`/api/oral/${current.id}/confirm`, { title: title || current.original_name, memory_date: meta.date || null, category: meta.category, people: meta.people, tags: meta.tags });
      toast("ok", "Saved as a searchable memory. The original recording is kept with it.");
      list.reload(); setSavedMemory(m.id);
    } catch (e) { toast("error", (e as Error).message); }
    finally { setBusy(""); }
  };
  const remove = async () => {
    if (!current) return;
    try { await api.del(`/api/oral/${current.id}`); toast("ok", "Recording removed."); setSel(null); list.reload(); }
    catch (e) { toast("error", (e as Error).message); }
    setConfirmDelete(false);
  };

  return (
    <>
      <PageHeader eyebrow="Oral History Studio" title="Let the voices be heard" />
      <Notice tone="warn" title="Speech recognition makes mistakes">Names, accents, dialects and background noise are often misheard. Listen back, correct the transcript, and only then save it as a memory. Everything is transcribed on this computer.</Notice>

      <div className="mt-5 grid gap-6 lg:grid-cols-[20rem_1fr]">
        <section className="min-w-0 space-y-4" aria-label="Recordings">
          <div className="card space-y-3">
            <h2 className="font-display text-xl">New recording</h2>
            <Field label="Spoken language" hint="Leave on auto-detect unless the recording is mixed or short.">
              {(id) => <select id={id} className="input" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="">Auto-detect</option>{[["en", "English"], ["hi", "Hindi"], ["te", "Telugu"], ["ta", "Tamil"], ["es", "Spanish"], ["fr", "French"], ["de", "German"], ["pt", "Portuguese"], ["ar", "Arabic"], ["zh", "Chinese"], ["ja", "Japanese"]].map(([c, n]) => <option key={c} value={c}>{n}</option>)}
              </select>}
            </Field>
            <Recorder disabled={!!busy} onDone={(b, n) => void upload(b, n)} />
            <Field label="…or upload audio">{(id) => <input id={id} type="file" accept="audio/*" disabled={!!busy} className="input file:mr-3 file:rounded-md file:border-0 file:bg-ink-700 file:px-3 file:py-1 file:text-paper"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f, f.name); e.target.value = ""; }} />}</Field>
            {busy === "upload" && <Spinner label="Saving and transcribing (CPU transcription can take about as long as the recording)" />}
          </div>
          {list.loading && !list.data && <Spinner />}
          {list.error && <ErrorNote error={list.error} onRetry={list.reload} />}
          {list.data && list.data.items.length === 0 && <EmptyState title="No recordings yet">Record a relative telling a story, or upload an existing recording.</EmptyState>}
          <ul className="space-y-2">
            {list.data?.items.map((t) => (
              <li key={t.id}><button onClick={() => { setSel(t.id); setSavedMemory(null); }} aria-current={t.id === sel} className={`card card-hover w-full p-3 text-left ${t.id === sel ? "border-amber-400/70" : ""}`}>
                <p className="truncate font-medium">{t.title || t.original_name}</p>
                <p className="mt-1 flex flex-wrap gap-1.5 text-xs">
                  <span className={`chip ${t.status === "confirmed" ? "border-ok/60 text-ok" : "border-warn/60 text-warn"}`}>{t.status === "confirmed" ? "saved as memory" : "draft"}</span>
                  {t.is_demo && <span className="chip border-mist/50 text-mist">demo</span>}
                  <span className="chip text-muted">{t.text ? `${t.text.split(/\s+/).length} words` : "no transcript"}</span>
                </p></button></li>
            ))}
          </ul>
        </section>

        <section className="min-w-0" aria-label="Transcript editor">
          {!current ? <EmptyState title="Select or create a recording">The transcript editor appears here.</EmptyState> : (
            <div className="card space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-display text-xl">Review &amp; edit</h2>
                <span className="text-xs text-muted">Engine: {current.engine === "none" ? "not transcribed" : current.engine}{current.language ? ` · language: ${current.language}` : ""}</span>
              </div>
              {!current.is_demo && <audio controls src={current.audio_url} className="w-full" preload="metadata" />}
              {current.is_demo && <Notice>This is text-only synthetic demo data, so there is no audio to play. Upload or record a clip to try the full flow.</Notice>}
              {current.status === "confirmed" ? (
                <>
                  <p className="whitespace-pre-wrap rounded-lg border border-ink-700 bg-ink-950 p-3 text-sm">{current.text}</p>
                  {current.memory_id && <button className="btn" onClick={() => setSavedMemory(current.memory_id)}>Open the saved memory</button>}
                </>
              ) : (
                <>
                  <Field label="Title">{(id) => <input id={id} className="input" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />}</Field>
                  <Field label="Transcript" hint="Edit freely. Your corrections are what gets saved and searched.">{(id) => <textarea id={id} rows={10} className="input leading-relaxed" value={text} onChange={(e) => setText(e.target.value)} placeholder={current.engine === "none" ? "Not transcribed yet. Press “Transcribe”, or type what was said." : ""} />}</Field>
                  <div className="flex flex-wrap gap-2">
                    {!current.is_demo && <button className="btn" onClick={transcribe} disabled={!!busy}>{busy === "transcribe" ? "Transcribing…" : current.text ? "Transcribe again" : "Transcribe with Whisper"}</button>}
                    <button className="btn" onClick={saveDraft} disabled={!!busy}>Save draft</button>
                    <Link to="/settings" className="btn btn-ghost text-xs">Transcription setup</Link>
                  </div>
                  <fieldset className="grid gap-3 rounded-xl border border-ink-700 p-4 sm:grid-cols-2">
                    <legend className="eyebrow px-2">Save as a memory</legend>
                    <Field label="When was this told or lived?">{(id) => <input id={id} className="input" placeholder="YYYY-MM-DD" value={meta.date} onChange={(e) => setMeta({ ...meta, date: e.target.value.trim() })} />}</Field>
                    <Field label="Category">{(id) => <select id={id} className="input" value={meta.category} onChange={(e) => setMeta({ ...meta, category: e.target.value })}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select>}</Field>
                    <Field label="Who is speaking / mentioned?">{(id) => <ChipInput id={id} value={meta.people} onChange={(people) => setMeta({ ...meta, people })} suggestions={facets.data?.people.map((p) => p.name)} placeholder="Add a name" />}</Field>
                    <Field label="Tags">{(id) => <ChipInput id={id} value={meta.tags} onChange={(tags) => setMeta({ ...meta, tags })} placeholder="e.g. oral-history" />}</Field>
                    <div className="flex flex-wrap gap-2 sm:col-span-2">
                      <button className="btn btn-primary" onClick={confirm} disabled={!!busy || !text.trim()}>{busy === "confirm" ? "Saving…" : "I've reviewed it - save as memory"}</button>
                      <button className="btn btn-danger" onClick={() => setConfirmDelete(true)}>Delete recording</button>
                    </div>
                  </fieldset>
                </>
              )}
            </div>
          )}
        </section>
      </div>
      {savedMemory && <MemoryDetail id={savedMemory} onClose={() => setSavedMemory(null)} onOpen={setSavedMemory} onChanged={list.reload} />}
      {confirmDelete && current && <ConfirmDialog title="Delete this recording?" confirmLabel="Delete recording" onCancel={() => setConfirmDelete(false)} onConfirm={remove}
        body={<p>The audio file and this draft transcript will be removed from GHOST's storage. Copies in backups are not erased.</p>} />}
    </>
  );
}
