import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { Citation } from "./types";

/* ------------------------------------------------------------------ toasts */
type ToastKind = "ok" | "error" | "info";
interface Toast { id: number; kind: ToastKind; text: string }
const ToastCtx = createContext<(kind: ToastKind, text: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((kind: ToastKind, text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 9000 : 4500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`pointer-events-auto rise rounded-xl border px-4 py-3 text-sm shadow-lg ${
            t.kind === "error" ? "border-bad/60 bg-ink-900 text-bad" : t.kind === "ok" ? "border-ok/50 bg-ink-900 text-ok" : "border-ink-600 bg-ink-900 text-paper"}`}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------------------------------------------------------------- feedback */
export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-600 border-t-amber-400" aria-hidden />
      {label}…
    </span>
  );
}

export function ErrorNote({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-bad/50 bg-bad/10 p-4 text-sm text-bad">
      <p>{error}</p>
      {onRetry && <button className="btn mt-3" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Notice({ tone = "info", title, children }: { tone?: "info" | "warn" | "ok"; title?: string; children: ReactNode }) {
  const c = tone === "warn" ? "border-warn/50 bg-warn/10 text-warn" : tone === "ok" ? "border-ok/50 bg-ok/10 text-ok" : "border-mist/40 bg-mist/10 text-mist";
  return (
    <div className={`rounded-xl border p-3 text-sm ${c}`} role={tone === "warn" ? "alert" : undefined}>
      {title && <p className="mb-1 font-semibold">{title}</p>}
      <div className="text-paper/90">{children}</div>
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-3 py-12 text-center">
      <span className="ghost-float text-4xl" aria-hidden>👻</span>
      <h3 className="font-display text-xl">{title}</h3>
      {children && <p className="max-w-md text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="font-display text-3xl font-semibold sm:text-4xl">{title}</h1>
      </div>
      {children}
    </header>
  );
}

/* ------------------------------------------------------------------- forms */
export function Field({ label, children, hint }: { label: string; children: (id: string) => ReactNode; hint?: string }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      {children(id)}
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

/** Comma/Enter separated chip input (people, tags). */
export function ChipInput({ id, value, onChange, placeholder, suggestions = [] }: {
  id?: string; value: string[]; onChange: (v: string[]) => void; placeholder?: string; suggestions?: string[];
}) {
  const [draft, setDraft] = useState("");
  const listId = useId();
  const add = (raw: string) => {
    const items = raw.split(",").map((s) => s.trim()).filter(Boolean);
    if (items.length) onChange([...new Set([...value, ...items])]);
    setDraft("");
  };
  return (
    <div className="rounded-lg border border-ink-600 bg-ink-950 p-1.5 focus-within:border-amber-400">
      <div className="flex flex-wrap gap-1.5">
        {value.map((v) => (
          <span key={v} className="chip">
            {v}
            <button type="button" aria-label={`Remove ${v}`} className="text-muted hover:text-bad" onClick={() => onChange(value.filter((x) => x !== v))}>×</button>
          </span>
        ))}
        <input id={id} list={listId} className="min-w-[8rem] flex-1 bg-transparent px-1.5 py-1 text-sm outline-none placeholder:text-muted/70"
          value={draft} placeholder={value.length ? "" : placeholder}
          onChange={(e) => (e.target.value.endsWith(",") ? add(e.target.value) : setDraft(e.target.value))}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(draft); } if (e.key === "Backspace" && !draft && value.length) onChange(value.slice(0, -1)); }}
          onBlur={() => draft && add(draft)} />
        <datalist id={listId}>{suggestions.map((s) => <option key={s} value={s} />)}</datalist>
      </div>
    </div>
  );
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus(); };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-6" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby={titleId}
        className={`rise max-h-[92vh] w-full overflow-y-auto rounded-t-2xl border border-ink-600 bg-ink-900 p-5 shadow-2xl sm:rounded-2xl ${wide ? "sm:max-w-3xl" : "sm:max-w-xl"}`}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id={titleId} className="font-display text-2xl">{title}</h2>
          <button className="btn btn-ghost -mr-2 -mt-1 px-2" onClick={onClose} aria-label="Close dialog">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({ title, body, confirmLabel, onConfirm, onCancel, busy }: {
  title: string; body: ReactNode; confirmLabel: string; onConfirm: () => void; onCancel: () => void; busy?: boolean;
}) {
  return (
    <Modal title={title} onClose={onCancel}>
      <div className="space-y-4 text-sm text-paper/90">{body}</div>
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn btn-danger" onClick={onConfirm} disabled={busy}>{busy ? "Working…" : confirmLabel}</button>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------- AI-specific */
export function ConfidenceBadge({ level, score }: { level: "high" | "medium" | "low" | "none"; score?: number }) {
  const map = {
    high: ["Strong match", "border-ok/60 text-ok"], medium: ["Likely match", "border-warn/60 text-warn"],
    low: ["Weak match", "border-ink-600 text-muted"], none: ["Not relevant", "border-ink-600 text-muted"],
  } as const;
  const [label, cls] = map[level];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs ${cls}`} title={score !== undefined ? `similarity score ${score.toFixed(3)}` : undefined}>
      <span aria-hidden>●</span>{label}{score !== undefined && <span className="text-muted">· {score.toFixed(2)}</span>}
    </span>
  );
}

/** Renders text, turning [n] markers into links to the matching citation. */
export function CitedText({ text, citations, onCite }: { text: string; citations: Citation[]; onCite?: (c: Citation) => void }) {
  const byN = new Map(citations.map((c) => [c.n, c]));
  const parts = text.split(/(\[\d{1,2}\])/g);
  return (
    <>
      {parts.map((p, i) => {
        const m = /^\[(\d{1,2})\]$/.exec(p);
        const c = m ? byN.get(Number(m[1])) : undefined;
        if (!c) return <span key={i}>{p}</span>;
        return (
          <button key={i} type="button" onClick={() => onCite?.(c)} title={`Source ${c.n}: ${c.title}`}
            className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md border border-amber-400/60 bg-amber-400/10 px-1 align-baseline text-[0.7rem] font-semibold text-amber-300 hover:bg-amber-400/25">
            {c.n}
          </button>
        );
      })}
    </>
  );
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    fn().then((data) => alive && setState({ data, loading: false }), (e: Error) => alive && setState({ error: e.message, loading: false }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}

export function download(filename: string, content: BlobPart, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const CATEGORIES = ["general", "childhood", "family", "love", "work", "migration", "tradition", "recipe", "letter", "wisdom", "loss"];
