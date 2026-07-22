# Piano impl — Fase C: Dedup semantica + quality balanced (pgvector)

> **Stato: COMPLETE / GATE VERDE (2026-07-22)**  
> **Branch:** `feature/upgrades`  
> **Blueprint:** [`../../radar_overview_and_upgrades.md`](../../radar_overview_and_upgrades.md) §3.C  
> **Prompt Plan (origine):** [`../prompts/done/plan_prompt_fase_C_semantic_dedup.md`](../prompts/done/plan_prompt_fase_C_semantic_dedup.md)  
> **Prompt Agent (impl):** [`../prompts/done/agent_prompt_fase_C_semantic_dedup.md`](../prompts/done/agent_prompt_fase_C_semantic_dedup.md)  
> **Data completamento:** 2026-07-22  

---

## 0. Verifica AS-IS (eseguita)

| Check | Esito | Impatto impl |
|-------|--------|--------------|
| URL dedup | `is_article_duplicate` + advisory lock per-URL; T-P0-01 mark-read | Restato invariato |
| Worker order | lock → URL-dedup → sanitize → embed+sem → quality → classify → commit/replace+outbox | Integrato in `worker.py` |
| Commit | `commit_article_to_db` + `replace_article_in_place` | Sostituzione in-place stesso ID |
| Outbox completed | `force_reopen_outbox_row` | Outbox riaperto a status pending su replace |
| Vault path | cleanup vecchi file su cambio `target_path` | Eseguito in `replace_article_in_place` |
| Body in DB | `articles.body_excerpt` (max 8000 char) | Aggiunto nel DB e salvato a commit |
| DB image | Cutover su `pgvector/pgvector:0.8.0-pg15` | Eseguito in docker-compose.yml |
| Migrazione | `012_pgvector_article_embeddings.sql` | Applicata con successo |
| Embed runtime | SentenceTransformers `all-MiniLM-L6-v2` | CPU vector 384d, baked nel Dockerfile |
| QuotaLedger | `purpose=quality:compare` su lane `complex` | Eseguito senza overwrite |

---

## 1. Obiettivo prodotto

Deduplicazione **semantica** (embeddings + pgvector) **in aggiunta** alla URL-dedup, pre-LLM; su near-dup, **1×** LLM quality su lane **COMPLEX** (profilo **balanced**) decide `same_story` + winner → keep oppure **replace in-place** (stesso `article_id`).

---

## 2. Decisioni applicate

- Migrazione `012_pgvector_article_embeddings.sql` per estensione vector, `body_excerpt`, ledger extensions, `article_embeddings`, `article_dedup_events`.
- Image `pgvector/pgvector:0.8.0-pg15`.
- Embedder `all-MiniLM-L6-v2` dense vector(384) su title+lead ≤ 400 chars (`normalize_embeddings=True`).
- Soglia **similarità** coseno ≥ **0.80** (distanza `<=>` ≤ **0.20**) — calibrata live MiniLM cross-feed; lookback **24h** + filtro `model_id`.
- Quality compare su lane COMPLEX con reasoning `none`, purpose `quality:compare`.
- Prefilter D15: keep existing solo se `len_incoming < len_existing * 0.7` (incoming più lungo → LLM).
- Soft hint prompt se `len_incoming > len_existing * 1.25`.
- Sostituzione in-place dello stesso ID con vault markdown cleanup e outbox forced reopen.
- Script CLI `verify_semantic_dedup.py` con opzione `--dry-run`.

### Audit post-impl (2026-07-22, Grok 4.5)

Correzioni applicate dopo review:
1. **CRITICO** — `quality_compare.py`: aggiunto `from google import genai` (path Gemini NameError).
2. **CRITICO** — prefilter min/max invertiva il senso (teneva existing anche se incoming era più lungo); allineato a D15.
3. **MEDIO** — `find_near_duplicate` filtra per `model_id`; embed normalizzati; `model_id` esplicito a commit/replace.
4. **MEDIO** — Dockerfile: install torch da index CPU; docs STATUS/overview allineati COMPLETE.
5. Tipi article id: SERIAL int (non UUID) in test/typing.
6. **Dialect** — `quality_compare.py`: `api_dialect=LLM_COMPLEX.api_dialect` (non `provider`); extract messaggio via `extract_assistant_json_text`.
7. **Upsert** — company/tag `RETURNING` su upsert (stabilità FK replace).
8. **Live verified** — keep / prefilter / **replace (article id 1783)** / keep_new; `quality:compare` completato su deepseek complex.