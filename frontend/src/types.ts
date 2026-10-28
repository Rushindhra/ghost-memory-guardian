export interface Attachment {
  id: string; kind: "photo" | "audio" | "document"; original_name: string; mime: string; size: number;
  created_at: string; url: string; has_ocr?: number | boolean;
}
export interface Memory {
  id: string; title: string; body: string; memory_date: string | null; sort_date: string | null; category: string;
  source: string; is_demo: boolean; created_at: string; updated_at: string; people: string[]; tags: string[];
  attachments: Attachment[];
}
export interface MemoryCompact {
  id: string; title: string; memory_date: string | null; category: string; people: string[]; tags: string[];
  is_demo: boolean; source: string; excerpt: string; attachment_kinds: string[];
}
export interface MemoryInput {
  title: string; body: string; memory_date: string | null; category: string; people: string[]; tags: string[];
}
export interface Facets {
  people: { name: string; count: number }[]; categories: { name: string; count: number }[]; tags: { name: string; count: number }[];
}
export interface Citation { n: number; memory_id: string; title: string; date: string | null; excerpt: string }
export interface Answer {
  status: "answered" | "not_found" | "ai_unavailable"; text: string | null; message?: string; citations: Citation[]; warnings: string[];
}
export interface SearchResult {
  memory: MemoryCompact; score: number; confidence: "high" | "medium" | "low" | "none"; excerpts: string[];
}
export interface SearchResponse {
  query: string; supported: boolean; results: SearchResult[]; answer: Answer | null; elapsed_ms: number;
  retrieval: { embedder: string; neural: boolean; min_score: number; strong_score: number };
}
export interface Transcript {
  id: string; original_name: string; mime: string; size: number; title: string; language: string; text: string;
  engine: string; status: "draft" | "confirmed"; memory_id: string | null; is_demo: boolean; created_at: string;
  audio_url: string; disclaimer: string;
}
export interface TimelineData {
  total: number; years: { year: string; items: MemoryCompact[] }[]; undated: MemoryCompact[];
}
export interface RelatedItem extends MemoryCompact { reason: string; score: number }
export interface SummaryResponse {
  summary: string; records: Citation[]; cited: number[]; warnings: string[]; model: string;
}
export interface GhostResponse {
  title: string; story: string; intensity: string; fiction: boolean; notice: string; model: string; cited: number[];
  warnings: string[]; invented_elements: string[];
  verified_facts: { n: number; memory_id: string; title: string; date: string | null; people: string[]; excerpt: string }[];
}
export interface LifeDoc {
  id: string; title: string; kind: string; notes: string; expiry_date: string | null; remind_date: string | null; is_demo: boolean;
}
export interface Overview {
  total_memories: number; audio_stories: number; demo_memories: number; life_documents: number;
  recent: MemoryCompact[]; timeline_preview: MemoryCompact[];
  upcoming_reminders: { id: string; title: string; kind: string; expiry_date: string | null; remind_date: string | null }[];
  storage: { database_bytes: number; files_bytes: number; data_dir: string };
  ai: { llm_ready: boolean; llm_model: string | null; search_mode: string; transcription_ready: boolean };
}
export interface Health {
  backend: { ok: boolean; version: string };
  database: { ok: boolean; schema_version: number; path: string };
  embeddings: { embedder: string; neural: boolean; mode: string; chunks: number; index_status: string; model_present: boolean; note: string | null; faiss: boolean };
  transcription: { engine: string; ready: boolean; package_installed: boolean; model_present: boolean; model_path: string; message: string };
  llm: { engine: string; model: string; url: string; reachable: boolean; model_installed: boolean; ready: boolean; message: string };
  offline: { core_archive_ready: boolean; semantic_search_ready: boolean; transcription_ready: boolean; llm_ready: boolean; offline_ready: boolean; explanation: string };
  telemetry: boolean;
}
export interface PrivacyReport {
  local_only: boolean; telemetry: string; lock_enabled: boolean; encryption_at_rest: boolean; logging: string;
  deletion_notice: string; encryption_recommendation: string; offline_note: string;
  network_endpoints: { purpose: string; url: string; loopback: boolean; remote_allowed: boolean }[];
  storage: { data_dir: string; database: string; files: string; index: string; models: string; bytes: { database: number; files: number; index: number } };
}
export interface SettingsView {
  llm_model: string; installed_models: string[]; whisper_language: string; ollama_url: string;
  embed_model_path: string; whisper_model_path: string; note: string;
}
