import { useEffect, useState } from "react";
import { api, formatMemoryDate, qs } from "../api";
import MemoryDetail from "../components/MemoryDetail";
import type { Facets, MemoryCompact, SummaryResponse, TimelineData } from "../types";
import { CitedText, EmptyState, ErrorNote, Notice, PageHeader, Spinner, useAsync, useToast } from "../ui";

export default function Timeline() {
  const toast = useToast();
  const [person, setPerson] = useState(""); const [category, setCategory] = useState(""); const [tag, setTag] = useState("");
  const [from, setFrom] = useState(""); const [to, setTo] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<string | null>(null);
  const [focus, setFocus] = useState("");
  const [summary, setSummary] = useState<SummaryResponse>();
  const [summaryError, setSummaryError] = useState("");
  const [busy, setBusy] = useState(false);

  const facets = useAsync(() => api.get<Facets>("/api/memories/facets"), []);
  const data = useAsync(() => api.get<TimelineData>(`/api/timeline${qs({ person, category, tag, date_from: from, date_to: to })}`), [person, category, tag, from, to]);
  const yearOk = (v: string) => v === "" || /^\d{4}$/.test(v);
  useEffect(() => { setSelected(new Set()); setSummary(undefined); }, [person, category, tag, from, to]);

  const toggle = (id: string) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const all = [...(data.data?.years.flatMap((y) => y.items) ?? []), ...(data.data?.undated ?? [])];

  const summarise = async () => {
    setBusy(true); setSummary(undefined); setSummaryError("");
    try { setSummary(await api.post<SummaryResponse>("/api/timeline/summary", { memory_ids: [...selected], focus })); }
    catch (e) { setSummaryError((e as Error).message); }
    finally { setBusy(false); }
  };
  const copy = async () => { if (summary) { await navigator.clipboard.writeText(summary.summary).then(() => toast("ok", "Summary copied."), () => toast("error", "Could not copy.")); } };

  return (
    <>
      <PageHeader eyebrow="Timeline" title="A life in order" />
      <div className="card mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div><label htmlFor="tp" className="label">Person</label>
          <select id="tp" className="input" value={person} onChange={(e) => setPerson(e.target.value)}><option value="">Anyone</option>{facets.data?.people.map((p) => <option key={p.name}>{p.name}</option>)}</select></div>
        <div><label htmlFor="tc" className="label">Category</label>
          <select id="tc" className="input" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">All</option>{facets.data?.categories.map((p) => <option key={p.name}>{p.name}</option>)}</select></div>
        <div><label htmlFor="tt" className="label">Tag</label>
          <select id="tt" className="input" value={tag} onChange={(e) => setTag(e.target.value)}><option value="">Any</option>{facets.data?.tags.map((p) => <option key={p.name}>{p.name}</option>)}</select></div>
        <div><label htmlFor="tf" className="label">From year</label>
          <input id="tf" inputMode="numeric" maxLength={4} placeholder="1950" className="input" value={from} onChange={(e) => yearOk(e.target.value) && setFrom(e.target.value)} /></div>
        <div><label htmlFor="tto" className="label">To year</label>
          <input id="tto" inputMode="numeric" maxLength={4} placeholder="2020" className="input" value={to} onChange={(e) => yearOk(e.target.value) && setTo(e.target.value)} /></div>
      </div>

      {selected.size > 0 && (
        <section className="card sticky top-14 z-10 mb-5 space-y-3 border-amber-400/40 lg:top-2" aria-label="Family history summary">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm"><strong>{selected.size}</strong> {selected.size === 1 ? "memory" : "memories"} selected. The summary uses <em>only</em> these records.</p>
            <button className="btn btn-ghost" onClick={() => setSelected(new Set())}>Clear</button>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input aria-label="Optional focus for the summary" className="input" placeholder="Optional focus, e.g. “how the family settled in Alder Creek”" value={focus} maxLength={300} onChange={(e) => setFocus(e.target.value)} />
            <button className="btn btn-primary sm:w-56" disabled={busy || selected.size > 40} onClick={summarise}>{busy ? "Writing…" : "Write family history"}</button>
          </div>
          {busy && <Spinner label="The local model is reading your selected memories (CPU models can take a minute)" />}
          {summaryError && <Notice tone="warn" title="No summary was produced">{summaryError}</Notice>}
          {summary && (
            <div className="rise space-y-3 border-t border-ink-700 pt-3">
              <div className="prose-ghost whitespace-pre-wrap font-display text-lg leading-relaxed"><CitedText text={summary.summary} citations={summary.records} onCite={(c) => setOpen(c.memory_id)} /></div>
              {summary.warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
              <p className="text-xs text-muted">Written by {summary.model} on this computer from your {summary.records.length} selected records. Numbers link to the originals. Check names and dates before sharing.</p>
              <button className="btn" onClick={copy}>Copy text</button>
            </div>
          )}
        </section>
      )}

      {data.loading && !data.data && <Spinner label="Gathering the years" />}
      {data.error && <ErrorNote error={data.error} onRetry={data.reload} />}
      {data.data && all.length === 0 && <EmptyState title="Nothing on the timeline yet">Add memories with dates in the vault, or load the synthetic demo archive from Settings. Adjust the filters if you expected results.</EmptyState>}
      {data.data && all.length > 0 && (
        <>
          <p className="mb-3 text-sm text-muted" aria-live="polite">{data.data.total} memories · tick the boxes to build a summary from chosen records</p>
          <ol className="relative space-y-8 border-l border-amber-400/30 pl-5 sm:pl-8">
            {data.data.years.map((y) => <YearBlock key={y.year} label={y.year} items={y.items} selected={selected} toggle={toggle} open={setOpen} />)}
            {data.data.undated.length > 0 && <YearBlock label="Undated" items={data.data.undated} selected={selected} toggle={toggle} open={setOpen} />}
          </ol>
        </>
      )}
      {open && <MemoryDetail id={open} onClose={() => setOpen(null)} onOpen={setOpen} onChanged={data.reload} />}
    </>
  );
}

function YearBlock({ label, items, selected, toggle, open }: { label: string; items: MemoryCompact[]; selected: Set<string>; toggle: (id: string) => void; open: (id: string) => void }) {
  return (
    <li className="relative">
      <span className="absolute -left-[1.62rem] top-1.5 h-3 w-3 rounded-full bg-amber-400 shadow-[0_0_12px_rgb(242_180_90/0.7)] sm:-left-[2.12rem]" aria-hidden />
      <h2 className="font-display text-2xl text-amber-300">{label}</h2>
      <ul className="mt-3 space-y-2">
        {items.map((m) => (
          <li key={m.id} className={`card flex items-start gap-3 p-3 ${selected.has(m.id) ? "border-amber-400/60" : ""}`}>
            <input type="checkbox" className="mt-1.5 h-4 w-4 accent-amber-400" checked={selected.has(m.id)} onChange={() => toggle(m.id)} aria-label={`Select ${m.title}`} />
            <button className="min-w-0 flex-1 text-left" onClick={() => open(m.id)}>
              <p className="text-xs text-amber-300/90">{formatMemoryDate(m.memory_date)} <span className="text-muted">· {m.category}{m.is_demo ? " · demo" : ""}</span></p>
              <p className="font-display text-lg leading-snug">{m.title}</p>
              <p className="line-clamp-2 text-sm text-muted">{m.excerpt}</p>
              {m.people.length > 0 && <p className="mt-1 text-xs text-paper/70">👤 {m.people.join(", ")}</p>}
            </button>
          </li>
        ))}
      </ul>
    </li>
  );
}
