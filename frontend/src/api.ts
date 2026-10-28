/** Thin fetch wrapper. All requests go to the local backend through the same origin (/api). */

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export const LOCKED_EVENT = "ghost:locked";

function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation errors: [{loc, msg}]
    return detail.map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg ?? ""}`.replace(/^: /, "")).join("; ");
  }
  return fallback;
}

async function parse(res: Response): Promise<unknown> {
  const type = res.headers.get("content-type") ?? "";
  return type.includes("application/json") ? res.json() : res.text();
}

export async function request<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      credentials: "include",
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the GHOST backend. Is it running on this computer? (see docs/INSTALL.md)");
  }
  const data = await parse(res);
  if (!res.ok) {
    const detail = typeof data === "object" && data !== null ? (data as { detail?: unknown }).detail : data;
    if (res.status === 401 && detail === "locked") window.dispatchEvent(new Event(LOCKED_EVENT));
    throw new ApiError(res.status, detailToMessage(detail, `Request failed (${res.status})`));
  }
  return data as T;
}

export const api = {
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T,>(path: string, body: unknown) => request<T>("PUT", path, body),
  del: <T,>(path: string) => request<T>("DELETE", path),
  upload: <T,>(path: string, file: File | Blob, filename: string, fields: Record<string, string> = {}) => {
    const form = new FormData();
    form.append("file", file, filename);
    Object.entries(fields).forEach(([k, v]) => form.append(k, v));
    return request<T>("POST", path, undefined, form);
  },
};

export function qs(params: Record<string, string | number | undefined | null>): string {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && p.set(k, String(v)));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

/** Display a partial date (1984, 1984-06, 1984-06-15) in a friendly way without timezone surprises. */
export function formatMemoryDate(d: string | null): string {
  if (!d) return "Undated";
  const [y, m, day] = d.split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  if (!m) return String(y);
  if (!day) return `${months[m - 1]} ${y}`;
  return `${day} ${months[m - 1]} ${y}`;
}
