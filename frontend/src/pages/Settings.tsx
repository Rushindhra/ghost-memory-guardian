import { useEffect, useState } from "react";
import { api } from "../api";
import type { Health, SettingsView } from "../types";
import { ConfirmDialog, ErrorNote, Field, Notice, PageHeader, Spinner, useAsync, useToast } from "../ui";

function Row({ name, ok, mode, detail }: { name: string; ok: boolean; mode?: string; detail: string }) {
  return (
    <li className="flex flex-col gap-1 border-b border-ink-700 py-3 last:border-0 sm:flex-row sm:items-start sm:gap-4">
      <span className={`w-44 shrink-0 font-medium ${ok ? "text-ok" : "text-warn"}`}><span aria-hidden>{ok ? "●" : "○"}</span> {name}<span className="sr-only">{ok ? " ready" : " needs setup"}</span></span>
      <span className="text-sm text-paper/85">{mode && <strong className="mr-2">{mode}</strong>}{detail}</span>
    </li>
  );
}

export default function Settings({ health, refresh }: { health?: Health; refresh: () => void }) {
  const toast = useToast();
  const s = useAsync(() => api.get<SettingsView>("/api/system/settings"), []);
  const demo = useAsync(() => api.get<{ loaded: boolean; memories: number; label: string }>("/api/demo/status"), []);
  const [model, setModel] = useState(""); const [lang, setLang] = useState("");
  const [busy, setBusy] = useState(""); const [confirmDemo, setConfirmDemo] = useState(false);
  useEffect(() => { if (s.data) { setModel(s.data.llm_model); setLang(s.data.whisper_language); } }, [s.data]);

  const run = async (key: string, fn: () => Promise<string>) => {
    setBusy(key);
    try { toast("ok", await fn()); refresh(); s.reload(); demo.reload(); } catch (e) { toast("error", (e as Error).message); } finally { setBusy(""); }
  };
  const save = (e: React.FormEvent) => { e.preventDefault(); void run("save", async () => { await api.put("/api/system/settings", { llm_model: model, whisper_language: lang }); return "Settings saved."; }); };
  const h = health;

  return (
    <>
      <PageHeader eyebrow="Settings & model status" title="The machinery, in the open">
        <button className="btn" onClick={() => { refresh(); toast("info", "Re-checking local services…"); }}>Re-check</button>
      </PageHeader>
      <div className="space-y-6">
        <section className="card" aria-labelledby="status">
          <h2 id="status" className="font-display text-2xl">Component health</h2>
          {!h ? <Spinner /> : (
            <ul className="mt-2">
              <Row name="Backend" ok={h.backend.ok} detail={`FastAPI ${h.backend.version}`} />
              <Row name="Database" ok={h.database.ok} detail={`SQLite, schema v${h.database.schema_version}`} />
              <Row name="Semantic search" ok={h.embeddings.neural} mode={h.embeddings.mode} detail={h.embeddings.neural ? `${h.embeddings.embedder} · ${h.embeddings.chunks} indexed passages · index ${h.embeddings.index_status}` : `The multilingual embedding model is not installed, so search matches words rather than meaning. ${h.embeddings.note ?? ""}`} />
              <Row name="Transcription" ok={h.transcription.ready} detail={h.transcription.message} />
              <Row name="Local language model" ok={h.llm.ready} detail={h.llm.message} />
            </ul>
          )}
          {h && <Notice tone={h.offline.offline_ready ? "ok" : "info"} title={h.offline.offline_ready ? "Offline-ready" : "Not yet offline-ready"}>{h.offline.explanation}</Notice>}
        </section>

        <section className="card space-y-4" aria-labelledby="cfg">
          <h2 id="cfg" className="font-display text-2xl">Models</h2>
          {s.error && <ErrorNote error={s.error} onRetry={s.reload} />}
          {s.data && (
            <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
              <Field label="Language model (installed in Ollama)" hint="Any locally installed Ollama model. Default: qwen3:4b.">
                {(id) => (<>
                  <input id={id} list="models" className="input" value={model} onChange={(e) => setModel(e.target.value)} pattern="[\w.:\-/]+" required />
                  <datalist id="models">{s.data!.installed_models.map((m) => <option key={m} value={m} />)}</datalist>
                </>)}
              </Field>
              <Field label="Transcription language" hint="Blank = detect automatically. Use a code like en, hi, te, es.">{(id) => <input id={id} className="input" maxLength={10} pattern="[a-zA-Z\-]*" value={lang} onChange={(e) => setLang(e.target.value)} />}</Field>
              <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
                <button className="btn btn-primary" disabled={busy === "save"}>Save</button>
                <span className="text-xs text-muted">{s.data.note}</span>
              </div>
              <dl className="sm:col-span-2 grid gap-1 text-xs text-muted sm:grid-cols-[11rem_1fr]">
                <dt>Ollama address</dt><dd><code>{s.data.ollama_url}</code></dd>
                <dt>Embedding model folder</dt><dd className="break-all"><code>{s.data.embed_model_path}</code></dd>
                <dt>Whisper model folder</dt><dd className="break-all"><code>{s.data.whisper_model_path}</code></dd>
              </dl>
            </form>
          )}
          {h && !h.llm.ready && (
            <Notice tone="warn" title="Set up the local language model (one time)">
              <pre className="mt-2 overflow-x-auto rounded-lg bg-ink-950 p-3 text-xs">{`# install Ollama from https://ollama.com, then:\nollama pull ${model || "qwen3:4b"}\nollama serve   # if it is not already running`}</pre>
              <p className="mt-2">Until then, the vault, timeline, exports and life documents all work; AI answers, summaries and Ghost Mode stay off rather than guess.</p>
            </Notice>
          )}
        </section>

        <section className="card space-y-3" aria-labelledby="maint">
          <h2 id="maint" className="font-display text-2xl">Search index & demo data</h2>
          <p className="text-sm text-muted">The index is always rebuildable from your records. Rebuild it if search seems out of date or after changing the embedding model.</p>
          <button className="btn" disabled={busy === "reindex"} onClick={() => run("reindex", async () => { const r = await api.post<{ chunks: number }>("/api/system/reindex"); return `Index rebuilt: ${r.chunks} passages.`; })}>{busy === "reindex" ? "Rebuilding…" : "Rebuild search index"}</button>
          <div className="border-t border-ink-700 pt-3">
            <p className="text-sm text-muted">{demo.data?.label ?? "Synthetic demo archive"} {demo.data?.loaded && <strong className="text-paper">({demo.data.memories} demo memories loaded)</strong>}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button className="btn btn-primary" disabled={busy === "demo" || !!demo.data?.loaded} onClick={() => run("demo", async () => { const r = await api.post<{ memories_added: number }>("/api/demo/load"); return `Loaded ${r.memories_added} synthetic memories.`; })}>Load demo archive</button>
              <button className="btn btn-danger" disabled={!demo.data?.loaded} onClick={() => setConfirmDemo(true)}>Remove demo data</button>
            </div>
            <p className="mt-2 text-xs text-muted">Removing demo data only deletes items flagged as demo; your own memories are untouched.</p>
          </div>
        </section>
      </div>
      {confirmDemo && <ConfirmDialog title="Remove the demo archive?" confirmLabel="Remove demo data" busy={busy === "rm"} onCancel={() => setConfirmDemo(false)}
        onConfirm={() => { void run("rm", async () => { await api.del("/api/demo"); return "Demo data removed."; }); setConfirmDemo(false); }}
        body={<p>Only the synthetic Hartwell family records are removed. Your own memories stay.</p>} />}
    </>
  );
}
