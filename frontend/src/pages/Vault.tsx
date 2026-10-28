import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, formatMemoryDate, qs } from "../api";
import MemoryDetail from "../components/MemoryDetail";
import MemoryForm from "../components/MemoryForm";
import type { Facets, Memory, MemoryCompact } from "../types";
import { EmptyState, ErrorNote, PageHeader, Spinner, useAsync } from "../ui";

export default function Vault() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [person, setPerson] = useState(""); const [category, setCategory] = useState(""); const [tag, setTag] = useState("");
  const [order, setOrder] = useState("recent");
  const [creating, setCreating] = useState(false);
  const open = params.get("m");
  useEffect(() => { const t = setTimeout(() => setDebounced(q), 250); return () => clearTimeout(t); }, [q]);

  const facets = useAsync(() => api.get<Facets>("/api/memories/facets"), []);
  const list = useAsync(() => api.get<{ total: number; items: Memory[] }>(`/api/memories${qs({ q: debounced, person, category, tag, order, limit: 100 })}`),
    [debounced, person, category, tag, order]);
  const setOpen = (id: string | null) => setParams(id ? { m: id } : {}, { replace: false });
  const filtered = !!(debounced || person || category || tag);
  const refresh = () => { list.reload(); facets.reload(); };

  return (
    <>
      <PageHeader eyebrow="Memory Vault" title="Everything worth keeping">
        <button className="btn btn-primary" onClick={() => setCreating(true)}>＋ New memory</button>
      </PageHeader>

      <div className="card mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-2"><label htmlFor="vq" className="label">Find in vault</label>
          <input id="vq" type="search" className="input" placeholder="Words, names, tags…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div><label htmlFor="vp" className="label">Person</label>
          <select id="vp" className="input" value={person} onChange={(e) => setPerson(e.target.value)}><option value="">Anyone</option>{facets.data?.people.map((p) => <option key={p.name} value={p.name}>{p.name} ({p.count})</option>)}</select></div>
        <div><label htmlFor="vc" className="label">Category</label>
          <select id="vc" className="input" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">All</option>{facets.data?.categories.map((p) => <option key={p.name} value={p.name}>{p.name} ({p.count})</option>)}</select></div>
        <div><label htmlFor="vo" className="label">Order</label>
          <select id="vo" className="input" value={order} onChange={(e) => setOrder(e.target.value)}><option value="recent">Recently added</option><option value="oldest">Oldest first</option><option value="newest">Newest first</option></select></div>
        {facets.data && facets.data.tags.length > 0 && (
          <div className="sm:col-span-2 lg:col-span-5" role="group" aria-label="Filter by tag">
            <span className="label">Tags</span>
            <div className="flex flex-wrap gap-1.5">
              {facets.data.tags.slice(0, 24).map((t) => (
                <button key={t.name} aria-pressed={tag === t.name} onClick={() => setTag(tag === t.name ? "" : t.name)}
                  className={`chip ${tag === t.name ? "border-amber-400 bg-amber-400/20 text-amber-200" : "hover:border-amber-400/50"}`}>#{t.name} <span className="text-muted">{t.count}</span></button>
              ))}
            </div>
          </div>
        )}
      </div>

      {list.loading && !list.data && <Spinner label="Opening the vault" />}
      {list.error && <ErrorNote error={list.error} onRetry={list.reload} />}
      {list.data && list.data.items.length === 0 && (
        filtered ? <EmptyState title="No memory matches those filters" action={<button className="btn" onClick={() => { setQ(""); setPerson(""); setCategory(""); setTag(""); }}>Clear filters</button>}>Try fewer words, or search by meaning in “Ask your memories”.</EmptyState>
          : <EmptyState title="Your vault is empty" action={<button className="btn btn-primary" onClick={() => setCreating(true)}>Preserve the first memory</button>}>Stories, letters, photographs and recordings you add here never leave this computer.</EmptyState>
      )}
      {list.data && list.data.items.length > 0 && (
        <>
          <p className="mb-3 text-sm text-muted" aria-live="polite">{list.data.total} {list.data.total === 1 ? "memory" : "memories"}{filtered ? " match" : ""}</p>
          <ul className="grid gap-4 md:grid-cols-2">
            {list.data.items.map((m) => <MemoryCard key={m.id} m={m} onOpen={() => setOpen(m.id)} />)}
          </ul>
        </>
      )}
      {creating && <MemoryForm onClose={() => setCreating(false)} onSaved={(m) => { setCreating(false); refresh(); setOpen(m.id); }} />}
      {open && <MemoryDetail id={open} onClose={() => setOpen(null)} onOpen={setOpen} onChanged={refresh} />}
    </>
  );
}

function MemoryCard({ m, onOpen }: { m: Memory; onOpen: () => void }) {
  const excerpt = m.body.replace(/\s+/g, " ").slice(0, 190);
  const kinds = [...new Set(m.attachments.map((a) => a.kind))];
  return (
    <li>
      <button onClick={onOpen} className="card card-hover h-full w-full text-left">
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-amber-300">{formatMemoryDate(m.memory_date)}</span>
          <span className="chip">{m.category}</span>
          {m.is_demo && <span className="chip border-mist/50 text-mist">demo</span>}
          {kinds.map((k) => <span key={k} className="chip" aria-label={`has ${k}`}>{k === "photo" ? "🖼" : k === "audio" ? "🎙" : "📄"}</span>)}
        </div>
        <h2 className="font-display text-xl leading-snug">{m.title}</h2>
        <p className="mt-1.5 line-clamp-3 text-sm text-muted">{excerpt}{m.body.length > 190 ? "…" : ""}</p>
        {m.people.length > 0 && <p className="mt-3 text-xs text-paper/70">👤 {m.people.join(", ")}</p>}
      </button>
    </li>
  );
}

export type { MemoryCompact };
