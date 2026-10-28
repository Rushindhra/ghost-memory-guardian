import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatMemoryDate } from "../api";
import MemoryDetail from "../components/MemoryDetail";
import type { Citation, SearchResponse } from "../types";
import { CitedText, ConfidenceBadge, ErrorNote, Notice, PageHeader, Spinner } from "../ui";

const EXAMPLES = [
  "Who taught Lily to knead bread dough?",
  "What happened during the flood at Alder Creek?",
  "Where did my grandfather work?",
  "How did Rosa and Elias meet?",
  "What is the capital of Australia?",
];

export default function Ask() {
  const [query, setQuery] = useState("");
  const [asked, setAsked] = useState("");
  const [res, setRes] = useState<SearchResponse>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [aiMode, setAiMode] = useState(true);
  const sourcesRef = useRef<HTMLElement>(null);

  const run = async (q: string, ask = aiMode) => {
    const text = q.trim();
    if (text.length < 2) return;
    setBusy(true); setError(""); setAsked(text); setRes(undefined);
    try { setRes(await api.post<SearchResponse>("/api/search", { query: text, k: 5, ask })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const jump = (c: Citation) => document.getElementById(`src-${c.memory_id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  const a = res?.answer;

  return (
    <>
      <PageHeader eyebrow="AI Memory Search" title="Ask your memories" />
      <form className="card mb-6 space-y-3" onSubmit={(e) => { e.preventDefault(); void run(query); }} role="search">
        <label htmlFor="ask" className="label">Ask in your own words, in any language you wrote in</label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input id="ask" className="input text-base" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. Who taught Lily to bake?" autoFocus />
          <button className="btn btn-primary sm:w-40" disabled={busy || query.trim().length < 2}>{busy ? "Searching…" : aiMode ? "Ask" : "Search"}</button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-1.5" aria-label="Example questions">
            {EXAMPLES.map((ex) => <button type="button" key={ex} className="chip hover:border-amber-400/60" onClick={() => { setQuery(ex); void run(ex); }}>{ex}</button>)}
          </div>
          <label className="flex items-center gap-2 text-sm text-muted"><input type="checkbox" checked={aiMode} onChange={(e) => setAiMode(e.target.checked)} /> Write a cited answer with the local AI</label>
        </div>
      </form>

      {busy && <Spinner label={aiMode ? "Searching your memories and asking the local model (CPU models can take a minute)" : "Searching"} />}
      {error && <ErrorNote error={error} onRetry={() => run(asked)} />}

      {res && (
        <div className="space-y-6">
          {a && (
            <section aria-labelledby="answer" className={`card rise ${a.status === "answered" ? "border-amber-400/40" : ""}`}>
              <h2 id="answer" className="eyebrow mb-2">Answer</h2>
              {a.status === "answered" && a.text && (
                <>
                  <p className="font-display text-xl leading-relaxed"><CitedText text={a.text} citations={a.citations} onCite={jump} /></p>
                  <p className="mt-3 text-xs text-muted">Written by a local model strictly from the sources below. Click a number to see the source. Always check important details against the original memory.</p>
                </>
              )}
              {a.status === "not_found" && (<>
                <p className="font-display text-xl">I couldn't find that in your saved memories.</p>
                <p className="mt-2 text-sm text-muted">Nothing in the archive is a close enough match, so GHOST will not guess. Try different words, or add the memory to your vault.</p>
              </>)}
              {a.status === "ai_unavailable" && (
                <Notice tone="warn" title="The local language model isn't available, so no written answer was produced">
                  <p>{a.message}</p>
                  <p className="mt-2">Your matching memories are still listed below. <Link className="text-amber-300 underline" to="/settings">Open model setup</Link></p>
                </Notice>
              )}
              {a.warnings.map((w) => <div key={w} className="mt-3"><Notice tone="warn">{w}</Notice></div>)}
            </section>
          )}

          <section ref={sourcesRef} aria-labelledby="sources">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
              <h2 id="sources" className="font-display text-2xl">{res.supported ? "Supporting memories" : "Closest memories (not strong enough to answer from)"}</h2>
              <p className="text-xs text-muted">{res.elapsed_ms} ms · {res.retrieval.neural ? "semantic search" : "keyword fallback search"} ({res.retrieval.embedder})</p>
            </div>
            {!res.retrieval.neural && <div className="mb-3"><Notice tone="info">Search is using the built-in keyword matcher because the neural embedding model isn't installed. It finds shared words, not shared meaning. See Settings for the one-time download.</Notice></div>}
            {res.results.length === 0 ? <p className="text-sm text-muted">The archive has no memories to search yet.</p> : (
              <ol className="space-y-3">
                {res.results.map((r, i) => {
                  const cite = a?.citations.find((c) => c.memory_id === r.memory.id);
                  return (
                    <li key={r.memory.id} id={`src-${r.memory.id}`} className={`card ${cite ? "border-amber-400/50" : ""} ${r.confidence === "none" || r.confidence === "low" ? "opacity-80" : ""}`}>
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        {cite && <span className="grid h-6 w-6 place-items-center rounded-md bg-amber-400 text-xs font-bold text-ink-950" title="Cited in the answer">{cite.n}</span>}
                        <span className="text-xs text-muted">#{i + 1}</span>
                        <ConfidenceBadge level={r.confidence} score={r.score} />
                        <span className="text-xs text-amber-300">{formatMemoryDate(r.memory.memory_date)}</span>
                        {r.memory.is_demo && <span className="chip border-mist/50 text-mist">demo</span>}
                      </div>
                      <button className="font-display text-xl hover:text-amber-300" onClick={() => setOpen(r.memory.id)}>{r.memory.title}</button>
                      {r.excerpts.map((ex, j) => <blockquote key={j} className="mt-2 border-l-2 border-amber-400/50 pl-3 text-sm italic text-paper/80">{ex.length > 380 ? ex.slice(0, 380) + "…" : ex}</blockquote>)}
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        </div>
      )}
      {open && <MemoryDetail id={open} onClose={() => setOpen(null)} onOpen={setOpen} onChanged={() => {}} />}
    </>
  );
}
