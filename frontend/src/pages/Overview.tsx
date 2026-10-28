import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatBytes, formatMemoryDate } from "../api";
import MemoryDetail from "../components/MemoryDetail";
import type { Health, Memory, Overview as OverviewData } from "../types";
import { EmptyState, ErrorNote, PageHeader, Spinner, useAsync, useToast } from "../ui";

// Writing prompts are suggestions for the user, not data; one is picked per day.
const PROMPTS = [
  "What was the kitchen like in the house you grew up in? Who was usually in it?",
  "Describe a song someone in your family always hummed. Who was it, and when did you hear it?",
  "What is the oldest object in your home, and who owned it before you?",
  "Tell the story of a journey someone in your family made that changed where they lived.",
  "What did your grandparents say that you still hear in their voice?",
  "Describe a family meal that was always cooked the same way. What would be lost if nobody wrote it down?",
  "Write about a winter, flood, festival or celebration that your whole street remembers.",
];

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="card">
      <p className="label mb-2">{label}</p>
      <p className="font-display text-4xl font-semibold text-amber-300">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export default function Overview({ health }: { health?: Health }) {
  const toast = useToast();
  const nav = useNavigate();
  const data = useAsync(() => api.get<OverviewData>("/api/system/overview"), []);
  const [open, setOpen] = useState<string | null>(null);
  const [draft, setDraft] = useState({ title: "", body: "" });
  const [saving, setSaving] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const prompt = PROMPTS[Math.floor(Date.now() / 86_400_000) % PROMPTS.length];
  const d = data.data;

  const capture = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post<Memory>("/api/memories", { ...draft, memory_date: null, category: "general", people: [], tags: ["quick-capture"] });
      toast("ok", "Saved. Add a date and people later from the Memory Vault.");
      setDraft({ title: "", body: "" }); data.reload();
    } catch (err) { toast("error", (err as Error).message); }
    finally { setSaving(false); }
  };
  const loadDemo = async () => {
    setLoadingDemo(true);
    try { const r = await api.post<{ memories_added: number }>("/api/demo/load"); toast("ok", `Loaded ${r.memories_added} synthetic memories (the fictional Hartwell family).`); data.reload(); }
    catch (err) { toast("error", (err as Error).message); }
    finally { setLoadingDemo(false); }
  };

  return (
    <>
      <PageHeader eyebrow="Overview" title="Your family archive, kept close">
        <button className="btn btn-primary" onClick={() => document.getElementById("quick-title")?.focus()}>＋ Quick capture</button>
      </PageHeader>
      {data.loading && !d && <Spinner label="Reading your archive" />}
      {data.error && <ErrorNote error={data.error} onRetry={data.reload} />}
      {d && d.total_memories === 0 && (
        <div className="mb-6">
          <EmptyState title="The archive is empty - for now" action={
            <div className="flex flex-wrap justify-center gap-2">
              <button className="btn btn-primary" onClick={() => document.getElementById("quick-title")?.focus()}>Write the first memory</button>
              <button className="btn" onClick={loadDemo} disabled={loadingDemo}>{loadingDemo ? "Loading…" : "Explore the synthetic demo archive"}</button>
            </div>}>
            Preserve a story, a recipe, a letter or a voice. Everything stays on this computer. Or look around first with clearly labelled synthetic demo data.
          </EmptyState>
        </div>
      )}
      {d && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Memories" value={d.total_memories} hint={d.demo_memories ? `${d.demo_memories} are synthetic demo data` : undefined} />
            <Stat label="Audio stories" value={d.audio_stories} hint="recordings saved as memories" />
            <Stat label="Life documents" value={d.life_documents} />
            <Stat label="Storage used" value={formatBytes(d.storage.database_bytes + d.storage.files_bytes)} hint={`${formatBytes(d.storage.files_bytes)} files · ${formatBytes(d.storage.database_bytes)} database`} />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <section className="card min-w-0 lg:col-span-2" aria-labelledby="qc">
              <h2 id="qc" className="font-display text-xl">Quick capture</h2>
              <p className="mb-3 mt-1 rounded-lg border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-100/90">
                <span className="eyebrow mr-2">Today's prompt</span>{prompt}
              </p>
              <form onSubmit={capture} className="space-y-3">
                <div><label htmlFor="quick-title" className="label">Title</label>
                  <input id="quick-title" required maxLength={200} className="input" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></div>
                <div><label htmlFor="quick-body" className="label">Story</label>
                  <textarea id="quick-body" rows={4} className="input" value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} /></div>
                <button className="btn btn-primary" disabled={saving || !draft.title.trim()}>{saving ? "Saving…" : "Preserve it"}</button>
              </form>
            </section>

            <section className="card min-w-0 space-y-3" aria-labelledby="ai">
              <h2 id="ai" className="font-display text-xl">Local AI</h2>
              <ul className="space-y-2 text-sm">
                <li className="flex justify-between gap-2"><span>Language model</span>
                  <strong className={d.ai.llm_ready ? "text-ok" : "text-warn"}>{d.ai.llm_ready ? d.ai.llm_model : "setup needed"}</strong></li>
                <li className="flex justify-between gap-2"><span>Search</span><strong className={health?.embeddings.neural ? "text-ok" : "text-warn"}>{d.ai.search_mode}</strong></li>
                <li className="flex justify-between gap-2"><span>Transcription</span><strong className={d.ai.transcription_ready ? "text-ok" : "text-warn"}>{d.ai.transcription_ready ? "ready" : "setup needed"}</strong></li>
              </ul>
              {(!d.ai.llm_ready || !d.ai.transcription_ready || !health?.embeddings.neural) && (
                <p className="text-xs text-muted">The archive works without AI. {health?.llm.message || "Open Settings for setup steps."}</p>
              )}
              <Link to="/settings" className="btn w-full">Model status &amp; setup</Link>
            </section>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <section aria-labelledby="recent" className="card min-w-0">
              <h2 id="recent" className="mb-3 font-display text-xl">Recently added</h2>
              {d.recent.length ? (
                <ul className="divide-y divide-ink-700">
                  {d.recent.map((m) => (
                    <li key={m.id}><button className="w-full py-2.5 text-left hover:text-amber-300" onClick={() => setOpen(m.id)}>
                      <span className="block font-medium">{m.title}</span>
                      <span className="block truncate text-xs text-muted">{formatMemoryDate(m.memory_date)} · {m.excerpt || "No text yet"}</span>
                    </button></li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted">Nothing here yet.</p>}
            </section>

            <section aria-labelledby="tl" className="card min-w-0">
              <div className="mb-3 flex items-center justify-between"><h2 id="tl" className="font-display text-xl">Timeline preview</h2><Link to="/timeline" className="text-sm text-amber-300 hover:underline">Open timeline →</Link></div>
              {d.timeline_preview.length ? (
                <ol className="relative ml-2 space-y-4 border-l border-amber-400/40 pl-5">
                  {d.timeline_preview.map((m) => (
                    <li key={m.id} className="relative">
                      <span className="absolute -left-[1.62rem] top-1.5 h-2.5 w-2.5 rounded-full bg-amber-400 shadow-[0_0_10px_rgb(242_180_90/0.8)]" aria-hidden />
                      <button className="text-left hover:text-amber-300" onClick={() => setOpen(m.id)}>
                        <span className="block text-xs text-amber-300">{formatMemoryDate(m.memory_date)}</span><span className="font-medium">{m.title}</span>
                      </button>
                    </li>
                  ))}
                </ol>
              ) : <p className="text-sm text-muted">Dated memories will appear here in order.</p>}
            </section>
          </div>

          {d.upcoming_reminders.length > 0 && (
            <section className="card min-w-0" aria-labelledby="up">
              <h2 id="up" className="mb-3 font-display text-xl">Coming up (next 90 days)</h2>
              <ul className="grid gap-2 sm:grid-cols-2">
                {d.upcoming_reminders.map((r) => (
                  <li key={r.id} className="rounded-lg border border-ink-700 p-3 text-sm"><strong>{r.title}</strong>
                    <span className="block text-xs text-muted">{r.remind_date ? `Reminder ${r.remind_date}` : ""} {r.expiry_date ? `· Expires ${r.expiry_date}` : ""}</span></li>
                ))}
              </ul>
            </section>
          )}
          {d.total_memories > 0 && (
            <div className="flex flex-wrap gap-2">
              <button className="btn" onClick={() => nav("/ask")}>Ask a question about your memories →</button>
              {d.demo_memories === 0 && <button className="btn btn-ghost" onClick={loadDemo} disabled={loadingDemo}>Add synthetic demo archive</button>}
            </div>
          )}
        </div>
      )}
      {open && <MemoryDetail id={open} onClose={() => setOpen(null)} onOpen={setOpen} onChanged={data.reload} />}
    </>
  );
}
