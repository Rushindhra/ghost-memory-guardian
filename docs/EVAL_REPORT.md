# GHOST evaluation report (generated)

_Produced by `python scripts/evaluate.py`; every number below was measured in that run on the synthetic archive._

## Configuration

- **embedder**: lexical-hash-v1
- **neural**: False
- **faiss**: True
- **min_score**: 0.22
- **strong_score**: 0.38
- **llm**: None
- **llm_ready**: False
- **python**: 3.13.17
- **platform**: Linux-6.18.44-fc-v165-x86_64-with-glibc2.39
- **k**: 5

## Retrieval

- **precision@5**: 0.229
- **recall@5**: 1.0
- **answerable_questions_recognised**: 13/14
- **unsupported_rejected**: 5/5
- **avg_retrieval_ms**: 6.8

## Answers

- not measured: no ready local LLM (start Ollama and pull the model)

## Resources

- peak RSS: 128.0 MB

## Threshold calibration

- **min_score_of_answerable_top_hits**: 0.196
- **max_score_of_unanswerable_top_hits**: 0.164
- **separable**: True
- **suggested_min_score**: 0.18
- **how_to_apply**: set GHOST_MIN_SCORE in .env


## How to read this run (added by hand; the numbers above are generated)

* **Configuration measured:** keyword (lexical) fallback only. The neural embedding model and a real local LLM could not be downloaded in the build sandbox, so **no neural-retrieval or answer-quality numbers exist yet**. Re-run `python scripts/evaluate.py --out docs/EVAL_REPORT.md` on a machine with the models installed to produce them.
* **Precision@5 ceiling:** each answerable question has only 1-2 relevant memories, so with k=5 the best achievable precision@5 is about 0.29. 0.229 is therefore not "23% accuracy"; Recall@5 = 1.0 means every relevant memory appeared in the top five.
* **13/14 recognised:** one answerable question scored just under the default `min_score` (0.22) and would be answered "not found". Calibration suggests 0.18, but the margin to the highest unanswerable score (0.164) is thin and rests on 19 questions, so the default was **not** changed. Tune `GHOST_MIN_SCORE` on your own archive.
* **5/5 unsupported questions rejected** without calling an LLM.
* Dataset: `demo/synthetic_archive.json` (fictional) and `demo/eval_questions.json` (ground truth written by hand). Small by design; it demonstrates the method, not state-of-the-art performance.
