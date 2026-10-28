import { useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { LOCKED_EVENT, api } from "./api";
import type { Health } from "./types";
import { Spinner } from "./ui";
import LockScreen from "./components/LockScreen";
import Overview from "./pages/Overview";
import Vault from "./pages/Vault";
import Ask from "./pages/Ask";
import Oral from "./pages/Oral";
import Timeline from "./pages/Timeline";
import GhostMode from "./pages/GhostMode";
import LifeDocs from "./pages/LifeDocs";
import Privacy from "./pages/Privacy";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/", label: "Overview", icon: "⌂" },
  { to: "/vault", label: "Memory Vault", icon: "▤" },
  { to: "/ask", label: "Ask your memories", icon: "⌕" },
  { to: "/oral", label: "Oral History Studio", icon: "◉" },
  { to: "/timeline", label: "Timeline", icon: "⏳" },
  { to: "/ghost", label: "Ghost Mode", icon: "☾" },
  { to: "/documents", label: "Life Documents", icon: "✦" },
  { to: "/privacy", label: "Privacy Center", icon: "⚿" },
  { to: "/settings", label: "Settings & models", icon: "⚙" },
];

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true), off = () => setOnline(false);
    window.addEventListener("online", on); window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  return online;
}

export function StatusPill({ health, error }: { health?: Health; error?: string }) {
  if (error) return <span className="chip border-bad/60 text-bad" role="status">Backend unreachable</span>;
  if (!health) return <span className="chip"><Spinner label="Checking AI" /></span>;
  const llm = health.llm.ready, search = health.embeddings.neural;
  const text = llm && search ? "Local AI ready" : llm ? "AI ready · keyword search" : "AI setup needed";
  const cls = llm && search ? "border-ok/60 text-ok" : llm ? "border-warn/60 text-warn" : "border-warn/60 text-warn";
  return <NavLink to="/settings" className={`chip ${cls}`} title="Open model status"><span aria-hidden>●</span> {text}</NavLink>;
}

export default function App() {
  const [lock, setLock] = useState<"checking" | "locked" | "open">("checking");
  const [health, setHealth] = useState<Health>();
  const [healthError, setHealthError] = useState<string>();
  const [menu, setMenu] = useState(false);
  const online = useOnline();
  const loc = useLocation();

  const checkLock = useCallback(async () => {
    try {
      const s = await api.get<{ enabled: boolean; unlocked: boolean }>("/api/privacy/lock-status");
      setLock(s.enabled && !s.unlocked ? "locked" : "open");
    } catch (e) { setHealthError((e as Error).message); setLock("open"); }
  }, []);
  useEffect(() => { void checkLock(); }, [checkLock]);
  useEffect(() => {
    const onLocked = () => setLock("locked");
    window.addEventListener(LOCKED_EVENT, onLocked);
    return () => window.removeEventListener(LOCKED_EVENT, onLocked);
  }, []);
  useEffect(() => setMenu(false), [loc.pathname]);

  const refreshHealth = useCallback(() => {
    api.get<Health>("/api/system/health").then((h) => { setHealth(h); setHealthError(undefined); }, (e: Error) => setHealthError(e.message));
  }, []);
  useEffect(() => {
    refreshHealth();
    const t = setInterval(refreshHealth, 30_000);
    window.addEventListener("focus", refreshHealth);
    return () => { clearInterval(t); window.removeEventListener("focus", refreshHealth); };
  }, [refreshHealth]);

  if (lock === "checking") return <div className="grid min-h-screen place-items-center"><Spinner label="Opening archive" /></div>;
  if (lock === "locked") return <LockScreen onUnlocked={() => { setLock("open"); refreshHealth(); }} />;

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[17rem_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-amber-400 focus:px-3 focus:py-2 focus:text-ink-950">Skip to content</a>

      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-700 bg-ink-950/90 px-4 py-3 backdrop-blur lg:hidden">
        <button className="btn px-3" aria-expanded={menu} aria-controls="sidebar" onClick={() => setMenu((m) => !m)}>☰ Menu</button>
        <span className="font-display text-lg tracking-wide">GHOST</span>
        <StatusPill health={health} error={healthError} />
      </header>

      <aside id="sidebar" className={`${menu ? "block" : "hidden"} fixed inset-x-0 top-[3.4rem] bottom-0 z-20 overflow-y-auto border-r border-ink-700 bg-ink-950 p-4 lg:static lg:block lg:min-h-screen lg:bg-ink-950/60`}>
        <div className="hidden items-center gap-3 px-2 pb-6 pt-2 lg:flex">
          <span className="candle grid h-10 w-10 place-items-center rounded-xl bg-amber-400 text-xl text-ink-950" aria-hidden>👻</span>
          <div>
            <p className="font-display text-xl leading-none tracking-wide">GHOST</p>
            <p className="mt-1 text-[0.68rem] uppercase tracking-[0.16em] text-muted">Private memory guardian</p>
          </div>
        </div>
        <nav aria-label="Main">
          <ul className="space-y-1">
            {NAV.map((n) => (
              <li key={n.to}>
                <NavLink to={n.to} end={n.to === "/"} className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${isActive ? "bg-amber-400/15 text-amber-300" : "text-paper/85 hover:bg-ink-800"}`}>
                  <span className="w-5 text-center text-base" aria-hidden>{n.icon}</span>{n.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="mt-8 space-y-2 rounded-xl border border-ink-700 bg-ink-900/70 p-3 text-xs text-muted">
          <p><span className="text-ok" aria-hidden>●</span> Local-only · no telemetry</p>
          <p>Network: <strong className={online ? "text-warn" : "text-ok"}>{online ? "online" : "offline"}</strong>. GHOST works either way once models are downloaded.</p>
        </div>
      </aside>

      <div className="min-w-0">
        <div className="hidden items-center justify-end gap-3 border-b border-ink-700/60 px-8 py-3 lg:flex">
          <StatusPill health={health} error={healthError} />
        </div>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {healthError && <div role="alert" className="mb-5 rounded-xl border border-bad/50 bg-bad/10 p-3 text-sm text-bad">{healthError}</div>}
          <Routes>
            <Route path="/" element={<Overview health={health} />} />
            <Route path="/vault" element={<Vault />} />
            <Route path="/ask" element={<Ask />} />
            <Route path="/oral" element={<Oral />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/ghost" element={<GhostMode />} />
            <Route path="/documents" element={<LifeDocs />} />
            <Route path="/privacy" element={<Privacy onLockChange={checkLock} />} />
            <Route path="/settings" element={<Settings health={health} refresh={refreshHealth} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
