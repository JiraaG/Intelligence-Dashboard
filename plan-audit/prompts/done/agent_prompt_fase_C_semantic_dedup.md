# Agent prompt — Fase C: Dedup semantica + quality balanced

> **Stato: DONE / GATE VERDE** — Implementato 2026-07-22; audit correttivo Grok 4.5 (prefilter D15, import `genai`, `model_id`, torch CPU, dialect `LLM_COMPLEX.api_dialect`).  
> **Piano SoT:** [`../../complete/plan_impl_fase_C_semantic_dedup.md`](../../complete/plan_impl_fase_C_semantic_dedup.md)  
> **Branch:** `feature/upgrades`  

---

## Esito GATE

- Threshold: similarity **0.80** (distanza `<=>` ≤ **0.20**) — calibrata live MiniLM cross-feed
- Live: keep / prefilter / **replace (article id 1783)** / keep_new; `quality:compare` su deepseek complex OK
- Dialect fix: `api_dialect=LLM_COMPLEX.api_dialect` + `extract_assistant_json_text`
- pytest `-m "not live"`: **224 passed**
- Docker rebuild backend/worker + `verify_semantic_dedup` live/dry-run: OK
- Schema: pgvector 0.8.0, `article_embeddings`, `article_dedup_events`, `body_excerpt`
