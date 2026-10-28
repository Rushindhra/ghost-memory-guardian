"""AI endpoints: cited search/Q&A, family-history summaries and Ghost Mode.

Rules enforced here (not left to the model):
  * answers are only attempted when retrieval found credible evidence;
  * citations that do not point at a supplied source are removed;
  * an answer that cites nothing is discarded and reported as "not found";
  * if the LLM is unavailable the response says so and never fabricates text.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..core.context import AppContext
from ..schemas.schemas import GhostIn, SearchIn, SummaryIn
from ..services import memory_service as ms
from ..services.llm_service import (NOT_FOUND_ANSWER, LLMUnavailable, Source, build_answer_messages,
                                    build_ghost_messages, build_summary_messages, parse_json_object,
                                    ungrounded_terms, validate_citations)
from .deps import get_conn, get_ctx, require_unlocked
from .memories import compact

router = APIRouter(prefix="/api", dependencies=[Depends(require_unlocked)])

MAX_ANSWER_SOURCES = 4
GHOST_CHARS_PER_MEMORY, GHOST_TOTAL_CHARS = 1500, 7000


def _clip(text: str, n: int) -> str:
    """Shorten at a word boundary and say so, instead of cutting mid-word."""
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def _citation(src: Source) -> dict[str, Any]:
    return {"n": src.n, "memory_id": src.memory_id, "title": src.title, "date": src.date,
            "excerpt": src.text[:400] + ("…" if len(src.text) > 400 else "")}


def _answer_with_llm(ctx: AppContext, question: str, sources: list[Source]) -> dict[str, Any]:
    try:
        raw = ctx.llm.chat(build_answer_messages(question, sources))
    except LLMUnavailable as exc:
        return {"status": "ai_unavailable", "text": None, "message": str(exc), "citations": [], "warnings": []}
    clean, cited, removed = validate_citations(raw, {s.n for s in sources})
    warnings: list[str] = []
    if removed:
        warnings.append(f"Removed {len(removed)} citation(s) that did not match any supplied source.")
    if NOT_FOUND_ANSWER.rstrip(".").lower() in clean.lower() or not cited:
        if not cited and NOT_FOUND_ANSWER.rstrip(".").lower() not in clean.lower():
            warnings.append("The model's reply cited no source, so it was discarded rather than shown as fact.")
        return {"status": "not_found", "text": NOT_FOUND_ANSWER, "citations": [], "warnings": warnings}
    by_n = {s.n: s for s in sources}
    unverified = ungrounded_terms(clean, " ".join(s.text + " " + s.title for s in sources))
    if unverified:
        warnings.append("These terms in the answer were not found in the cited sources - double-check them: "
                        + ", ".join(unverified))
    return {"status": "answered", "text": clean, "citations": [_citation(by_n[n]) for n in cited],
            "warnings": warnings}


@router.post("/search")
def search(body: SearchIn, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    started = time.perf_counter()
    hits = ctx.retriever.search(conn, body.query, k=body.k)
    results, sources = [], []
    for hit in hits:
        mem = ms.get_memory(conn, hit.memory_id)
        conf = ctx.retriever.confidence(hit)
        results.append({"memory": compact(mem), "score": round(hit.score, 4), "confidence": conf,
                        "excerpts": hit.excerpts})
        if conf in ("high", "medium") and len(sources) < MAX_ANSWER_SOURCES:
            sources.append(Source(len(sources) + 1, mem["id"], mem["title"], mem["memory_date"], mem["people"],
                                  "\n".join(hit.excerpts)))
    supported = bool(sources)
    answer: dict[str, Any] | None = None
    if body.ask:
        if not supported:
            answer = {"status": "not_found", "text": NOT_FOUND_ANSWER, "citations": [], "warnings": []}
        else:
            answer = _answer_with_llm(ctx, body.query, sources)
    return {"query": body.query, "supported": supported, "results": results, "answer": answer,
            "retrieval": {"embedder": ctx.embedder.id, "neural": ctx.embedder.neural,
                          "min_score": ctx.retriever.min_score, "strong_score": ctx.retriever.strong_score},
            "elapsed_ms": int((time.perf_counter() - started) * 1000)}


def _load_sources(conn: sqlite3.Connection, ids: list[str], per_memory_chars: int,
                  total_chars: int) -> tuple[list[dict[str, Any]], list[Source]]:
    try:
        mems = ms.get_many(conn, ids)
    except ms.NotFound:
        raise HTTPException(404, "One of the selected memories no longer exists.")
    mems.sort(key=lambda m: m["sort_date"] or "9999")
    budget, sources = total_chars, []
    for i, m in enumerate(mems, start=1):
        text = (m["body"] or "")[: min(per_memory_chars, max(budget, 300))]
        budget -= len(text)
        sources.append(Source(i, m["id"], m["title"], m["memory_date"], m["people"], text))
    return mems, sources


@router.post("/timeline/summary")
def family_summary(body: SummaryIn, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    """Summarise ONLY the selected memories."""
    mems, sources = _load_sources(conn, body.memory_ids, 2500, 9000)
    try:
        raw = ctx.llm.chat(build_summary_messages(body.focus, sources))
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc))
    clean, cited, removed = validate_citations(raw, {s.n for s in sources})
    warnings = ([f"Removed {len(removed)} citation(s) that did not match a selected record."] if removed else [])
    unverified = ungrounded_terms(clean, " ".join(s.text + " " + s.title for s in sources))
    if unverified:
        warnings.append("Not found in the selected records - verify: " + ", ".join(unverified))
    if not cited:
        warnings.append("The summary cites no records; treat it with caution.")
    return {"summary": clean, "records": [_citation(s) for s in sources], "cited": cited, "warnings": warnings,
            "model": getattr(ctx.llm, "model", "unknown")}


@router.post("/ghost/generate")
def ghost(body: GhostIn, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)):
    """Create a clearly fictional story from selected memories. Never writes to the archive."""
    mems, sources = _load_sources(conn, body.memory_ids, GHOST_CHARS_PER_MEMORY, GHOST_TOTAL_CHARS)
    try:
        raw = ctx.llm.chat(build_ghost_messages(sources, body.intensity, body.language), json_mode=True,
                           temperature=0.8)
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc))
    obj = parse_json_object(raw)
    parse_ok = bool(obj and isinstance(obj.get("story"), str) and obj["story"].strip())
    story = (obj or {}).get("story") if parse_ok else raw
    title = (obj or {}).get("title") if parse_ok and isinstance((obj or {}).get("title"), str) else "An untitled tale"
    invented = [str(x) for x in (obj or {}).get("invented_elements", []) if isinstance(x, (str, int))][:30] if parse_ok else []
    story, cited, removed = validate_citations(story, {s.n for s in sources})
    # Verified facts are taken straight from the archive, not from the model.
    facts = [{"n": s.n, "memory_id": s.memory_id, "title": s.title, "date": s.date, "people": s.people,
              "excerpt": _clip(" ".join(s.text.split()), 260)} for s in sources]
    return {
        "title": title, "story": story, "intensity": body.intensity, "fiction": True,
        "notice": ("This is a work of fiction written by a local AI model. Only the 'Verified facts' panel reflects "
                   "your archive. Nothing here is a message from, or the voice of, anyone who has died."),
        "verified_facts": facts, "invented_elements": invented, "cited": cited,
        "warnings": ([] if parse_ok else ["The model did not return the structured format, so its list of "
                                          "invented details is unavailable. Treat everything unmarked as fiction."]),
        "model": getattr(ctx.llm, "model", "unknown"),
    }
