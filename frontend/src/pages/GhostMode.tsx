import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatMemoryDate } from "../api";
import type { GhostResponse, Memory } from "../types";
import { CitedText, EmptyState, Notice, PageHeader, Spinner, useAsync } from "../ui";

type Level = "gentle" | "mysterious" | "spooky" | "remembrance";
const LEVELS: { id: Level; name: string; blurb: string }[] = [
  { id: "gentle", name: "Gentle", blurb: "A soft, wistful tale. Nothing frightening." },
  { id: "mysterious", name: "Mysterious", blurb: "Quiet unease and unanswered questions." },
  { id: "spooky", name: "Spooky", blurb: "Atmospheric chills, never cruel to real people." },
  { id: "remembrance", name: "Remembrance", blurb: "Warm and respectful. No horror at all." },
];
const MAX = 8;

export default function GhostMode() {
  const list = useAsync(() => api.get<{ items: Memory[] }>("/api/memories?order=oldest&limit=200"), []);
  const [picked, setPicked] = useState<string[]>([]);
  const [level, setLevel] = useState<Level>("mysterious");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [story, setStory] = useState<GhostResponse>();

  const items = useMemo(() => (list.data?.items ?? []).filter((m) => !filter || (m.title + m.people.join(" ")).toLowerCase().includes(filter.toLowerCase())), [list.data, filter]);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < MAX ? [...p, id] : p));

  const generate = async () => {
    setBusy(true); setError(""); setStory(undefined);
    try { setStory(await api.post<GhostResponse>("/api/ghost/generate", { memory_ids: picked, intensity: level })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const stage = !story ? "" : story.intensity === "remembrance" ? "stage-remembrance" : story.intensity === "spooky" ? "stage-spooky" : "stage-ghost";
  const paragraphs = story?.story.split(/\n{2,}/).filter(Boolean) ?? [];

  return (
    <>
      <PageHeader eyebrow="Ghost Mode" title="Turn memories into a tale" />
      <Notice title="Always fiction, always optional">
        Ghost Mode asks the local AI to write an invented story <em>inspired by</em> memories you choose. It cannot contact, channel or speak for anyone who has died, and it never changes your archive. Choose Remembrance for a warm, respectful version with no horror.
      </Notice>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-labelledby="pick">
          <h2 id="pick" className="font-display text-2xl">1. Choose source memories <span className="text-base text-muted">({picked.length}/{MAX})</span></h2>
          <input className="input mt-3" type="search" aria-label="Filter memories" placeholder="Filter by title or person" value={filter} onChange={(e) => setFilter(e.target.value)} />
          {list.loading && <div className="mt-4"><Spinner /></div>}
          {list.error && <p role="alert" className="mt-3 text-bad">{list.error}</p>}
          {list.data && list.data.items.length === 0 && <div className="mt-4"><EmptyState title="No memories to draw from">Add a few memories first, or load the demo archive in <Link className="text-amber-300 underline" to="/settings">Settings</Link>.</EmptyState></div>}
          <ul className="mt-3 max-h-[28rem] space-y-1.5 overflow-y-auto pr-1">
            {items.map((m) => {
              const on = picked.includes(m.id), full = !on && picked.length >= MAX;
              return (
                <li key={m.id}>
                  <label className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 ${on ? "border-amber-400/60 bg-amber-400/10" : "border-ink-700 bg-ink-900/60 hover:border-ink-600"} ${full ? "opacity-50" : ""}`}>
                    <input type="checkbox" className="mt-1 h-4 w-4 accent-amber-400" checked={on} disabled={full} onChange={() => toggle(m.id)} />
                    <span><span className="block font-medium">{m.title}</span><span className="text-xs text-muted">{formatMemoryDate(m.memory_date)}{m.people.length ? ` · ${m.people.join(", ")}` : ""}</span></span>
                  </label>
                </li>
              );
            })}
          </ul>
        </section>

        <aside aria-labelledby="mood" className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <h2 id="mood" className="font-display text-2xl">2. Pick the mood</h2>
          <div role="radiogroup" aria-label="Story intensity" className="space-y-2">
            {LEVELS.map((l) => (
              <label key={l.id} className={`block cursor-pointer rounded-xl border p-3 ${level === l.id ? "border-amber-400 bg-amber-400/10" : "border-ink-700 hover:border-ink-600"}`}>
                <input type="radio" name="level" className="sr-only" checked={level === l.id} onChange={() => setLevel(l.id)} />
                <span className="font-medium">{l.name}</span><span className="block text-xs text-muted">{l.blurb}</span>
              </label>
            ))}
          </div>
          <button className="btn btn-primary w-full" disabled={busy || picked.length === 0} onClick={generate}>{busy ? "Summoning…" : "☾ Write the story"}</button>
          {picked.length === 0 && <p className="text-xs text-muted">Select at least one memory.</p>}
        </aside>
      </div>

      {busy && <div className="mt-6"><Spinner label="The local model is writing (CPU models can take a minute or two)" /></div>}
      {error && <div className="mt-6"><Notice tone="warn" title="No story was written">{error} <Link to="/settings" className="text-amber-300 underline">Open model setup</Link></Notice></div>}

      {story && (
        <div className="mt-8 space-y-5">
          <article className={`stage ${stage} px-5 py-8 sm:px-10 sm:py-12`} aria-label="Fictional story">
            <p className="eyebrow">Fiction · {story.intensity}</p>
            <h2 className="mt-2 font-display text-3xl sm:text-4xl">{story.title}</h2>
            <div className="paragraph-reveal prose-ghost mt-6 max-w-prose font-display text-lg leading-relaxed">
              {paragraphs.map((p, i) => <p key={i}><CitedText text={p} citations={story!.verified_facts.map((f) => ({ n: f.n, memory_id: f.memory_id, title: f.title, date: f.date, excerpt: f.excerpt }))} onCite={(c) => document.getElementById(`fact-${c.n}`)?.scrollIntoView({ behavior: "smooth", block: "center" })} /></p>)}
            </div>
            <p className="mt-6 max-w-prose text-xs text-muted">{story.notice} Written by {story.model}.</p>
          </article>
          {story.warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
          <div className="grid gap-4 md:grid-cols-2">
            <section className="card" aria-labelledby="facts">
              <h3 id="facts" className="eyebrow mb-3 text-ok">Verified facts from your archive</h3>
              <ul className="space-y-3 text-sm">
                {story.verified_facts.map((f) => (
                  <li key={f.n} id={`fact-${f.n}`}><span className="font-semibold text-amber-300">[{f.n}] {f.title}</span> <span className="text-muted">{formatMemoryDate(f.date)}</span>
                    <p className="mt-0.5 text-paper/80">{f.excerpt}</p></li>
                ))}
              </ul>
            </section>
            <section className="card" aria-labelledby="fiction">
              <h3 id="fiction" className="eyebrow mb-3 text-warn">Invented by the AI</h3>
              {story.invented_elements.length ? <ul className="list-disc space-y-1 pl-5 text-sm text-paper/90">{story.invented_elements.map((x) => <li key={x}>{x}</li>)}</ul>
                : <p className="text-sm text-muted">The model gave no list. Treat every detail not shown under “Verified facts” as invented.</p>}
            </section>
          </div>
        </div>
      )}
    </>
  );
}
