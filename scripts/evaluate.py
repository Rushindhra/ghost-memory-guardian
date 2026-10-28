#!/usr/bin/env python
"""Reproducible evaluation on the synthetic archive (demo/eval_questions.json).

Everything printed is measured by this run. Nothing is estimated or hard-coded.

    python scripts/evaluate.py                 # retrieval metrics (+ LLM metrics if Ollama is ready)
    python scripts/evaluate.py --calibrate     # also suggest score thresholds for the current embedder
    python scripts/evaluate.py --no-llm        # skip the answer-generation part
    python scripts/evaluate.py --out docs/EVAL_REPORT.md
"""
from __future__ import annotations

import argparse
import json
import platform
import resource
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.context import build_context  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--out", type=Path, default=None, help="write a Markdown report here")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    questions = json.loads((ROOT / "demo" / "eval_questions.json").read_text(encoding="utf-8"))["questions"]
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(data_dir=Path(tmp) / "data")  # honours GHOST_* env (models dir, embed backend, ...)
        ctx = build_context(settings)
        with TestClient(create_app(settings, ctx)) as c:
            c.post("/api/demo/load")
            health = c.get("/api/system/health").json()
            llm_ready = health["llm"]["ready"] and not args.no_llm

            sup_rows, uns_rows, retr_ms, answer_ms = [], [], [], []
            cited_ok = cited_total = 0
            rejected_ok = 0
            top_supported, top_unsupported = [], []
            for item in questions:
                t0 = time.perf_counter()
                r = c.post("/api/search", json={"query": item["q"], "k": args.k, "ask": False}).json()
                retr_ms.append((time.perf_counter() - t0) * 1000)
                ids = [x["memory"]["id"] for x in r["results"]][: args.k]
                top = r["results"][0]["score"] if r["results"] else 0.0
                rel = set(item["relevant"])
                if rel:
                    hit = len(rel & set(ids))
                    sup_rows.append({"q": item["q"], "precision": hit / max(len(ids), 1), "recall": hit / len(rel),
                                     "top_ids": ids[:3], "supported_flag": r["supported"]})
                    top_supported.append(top)
                else:
                    uns_rows.append({"q": item["q"], "rejected": not r["supported"], "top_score": top})
                    rejected_ok += (not r["supported"])
                    top_unsupported.append(top)
                if llm_ready:
                    t1 = time.perf_counter()
                    full = c.post("/api/search", json={"query": item["q"], "k": args.k, "ask": True}).json()
                    answer_ms.append((time.perf_counter() - t1) * 1000)
                    a = full["answer"]
                    if rel:
                        cited_total += 1
                        if a["status"] == "answered" and {x["memory_id"] for x in a["citations"]} & rel:
                            cited_ok += 1
                    elif a["status"] == "not_found":
                        pass

            n_sup, n_uns = len(sup_rows), len(uns_rows)
            # "Precision@5" over a 14-memory archive with 1-2 relevant items is naturally low; report both.
            p = statistics.mean(r["precision"] for r in sup_rows)
            rec = statistics.mean(r["recall"] for r in sup_rows)
            supported_detect = sum(r["supported_flag"] for r in sup_rows) / n_sup
            result = {
                "config": {"embedder": ctx.embedder.id, "neural": ctx.embedder.neural, "faiss": ctx.retriever.faiss_available,
                           "min_score": ctx.retriever.min_score, "strong_score": ctx.retriever.strong_score,
                           "llm": health["llm"].get("model") if llm_ready else None, "llm_ready": llm_ready,
                           "python": platform.python_version(), "platform": platform.platform(), "k": args.k},
                "retrieval": {f"precision@{args.k}": round(p, 3), f"recall@{args.k}": round(rec, 3),
                              "answerable_questions_recognised": f"{sum(r['supported_flag'] for r in sup_rows)}/{n_sup}",
                              "unsupported_rejected": f"{rejected_ok}/{n_uns}",
                              "avg_retrieval_ms": round(statistics.mean(retr_ms), 1)},
                "answers": ({"cited_a_relevant_memory": f"{cited_ok}/{cited_total}",
                             "avg_answer_ms": round(statistics.mean(answer_ms), 0)} if llm_ready else
                            "not measured: no ready local LLM (start Ollama and pull the model)"),
                "resources": {"peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 0)},
                "per_question_failures": [r for r in sup_rows if r["recall"] < 1] + [r for r in uns_rows if not r["rejected"]],
            }
            if args.calibrate:
                lo_sup, hi_uns = min(top_supported), max(top_unsupported)
                result["calibration"] = {
                    "min_score_of_answerable_top_hits": round(lo_sup, 3),
                    "max_score_of_unanswerable_top_hits": round(hi_uns, 3),
                    "separable": lo_sup > hi_uns,
                    "suggested_min_score": round((lo_sup + hi_uns) / 2, 3),
                    "how_to_apply": "set GHOST_MIN_SCORE in .env",
                }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.out:
        args.out.write_text(render_md(result), encoding="utf-8")
        print(f"\nReport written to {args.out}")
    return 0


def render_md(r: dict) -> str:
    c = r["config"]
    lines = ["# GHOST evaluation report (generated)", "",
             "_Produced by `python scripts/evaluate.py`; every number below was measured in that run on the synthetic archive._", "",
             "## Configuration", "", *[f"- **{k}**: {v}" for k, v in c.items()], "", "## Retrieval", "",
             *[f"- **{k}**: {v}" for k, v in r["retrieval"].items()], "", "## Answers", ""]
    a = r["answers"]
    lines += [f"- {a}"] if isinstance(a, str) else [f"- **{k}**: {v}" for k, v in a.items()]
    lines += ["", "## Resources", "", f"- peak RSS: {r['resources']['peak_rss_mb']} MB", ""]
    if r.get("calibration"):
        lines += ["## Threshold calibration", "", *[f"- **{k}**: {v}" for k, v in r["calibration"].items()], ""]
    if r["per_question_failures"]:
        lines += ["## Questions that did not fully pass", "", "```json", json.dumps(r["per_question_failures"], indent=2, ensure_ascii=False), "```"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
