# Agent prompt — Fase Metrics 013 (FinOps / diagnostica)

> **Stato: ACTIVE** — pronto per chat Agent di implementazione (documenti 2026-07-22; **patch review C1–C8** 2026-07-22).  
> **Piano SoT:** [`../../active/plan_impl_fase_metrics_013.md`](../../active/plan_impl_fase_metrics_013.md)  
> **Branch:** `feature/upgrades`  
> **Prerequisito:** Fase C `012` GATE — [`../../complete/plan_impl_fase_C_semantic_dedup.md`](../../complete/plan_impl_fase_C_semantic_dedup.md)  
> **W0 docs:** DONE. **W1–W4 codice:** da eseguire in chat Agent.

---

## Come usare

1. Apri una **nuova chat Agent** su branch `feature/upgrades`.
2. Incolla il blocco **PROMPT** qui sotto.
3. Non rieseguire W0 (piani/prompt già scritti). Parti da **W1** migrazione.
4. Se l’agent ha già un “Implementation Plan” interno, **C1–C8 sotto override** dove confligge.
5. A GATE: sposta questo file in `prompts/done/`, il piano in `complete/`, aggiorna `STATUS.md`.

---

## PROMPT (incolla in Agent mode)

```text
# Task — IMPLEMENTAZIONE: Fase Metrics 013 (FinOps / diagnostica)

## Ruolo
Pipeline engineer + backend Radar Informativo Globale. Implementa la fondazione metriche end-to-end seguendo il piano SoT + correzioni review C1–C8 (obbligatorie). Chiudi il GATE con pytest + Docker + live articles + verify script. Commit dettagliato a GATE (o se richiesto esplicitamente).

## Obiettivo
Migrazione `013_metrics_and_feed_tracking.sql` + strumentazione worker/ledger/dedup + `GET /api/metrics/*` read-only + test/script + verifica live che i dati metriche siano popolati, corretti, allineati e compatibili con le API.

## Autorità (ordine di precedenza)
1. SoT: `plan-audit/active/plan_impl_fase_metrics_013.md` (decisioni chiuse, DDL, GATE §8)
2. Correzioni **C1–C8** in questo prompt (override se un Implementation Plan interno confligge)
3. Skills / AGENTS.md vincoli runtime

In particolare dal SoT:
- Check metriche MUST/DEFER (§2) — non `article_type` LLM; non UI; non tabella `feeds`
- DDL §4 (articles denorm, dedup_events, ledger FinOps, embeddings.embedding_time_ms)
- Innesti §5 e API §6
- Wave W1→W4 e GATE §8

## Contesto obbligatorio (leggere PRIMA di codare)

### Quadro / SoT
- `plan-audit/STATUS.md`
- `plan-audit/complete/plan_impl_fase_C_semantic_dedup.md` (prerequisito 012)
- `plan-audit/complete/sot_llm_multi_model_fallback.md` (lane/quota; Profilo A)
- `docs/02_architecture_and_backend.md`, `radar/docs/runbook.md`
- `radar/.env.example` (non commitare `radar/.env`)

### Skills / ECC
- `.agents/skills/radar-quota-ledger/SKILL.md` (+ mirror `radar/.ecc/skills/`)
- `.agents/skills/radar-docker-ops/SKILL.md`
- `.agents/skills/radar-requeue-ops/SKILL.md`
- `.agents/skills/radar-api-contract/SKILL.md` (estendere contratto metrics; sync mirror `.ecc`)
- `.agents/skills/llm-json-extraction/SKILL.md` (non cambiare schema classify)
- `.agents/AGENTS.md` — ingest solo worker; asyncpg; no package `openai`
- Sidebar freeze: **zero** tocchi `radar-sidebar/**`

### Codice AS-IS da toccare
- `radar/backend/migrations/` → nuovo `013_metrics_and_feed_tracking.sql` (dopo 012; applicata da `run_migrations` al bootstrap)
- `radar/backend/app/extraction/entry_validation.py` — oggi solo `feed_title`; aggiungere `feed_id`, `feed_domain`
- `radar/backend/app/classification/client.py` — oggi `classify_article` → `GeopoliticalArticleSchema` (BREAKING → ClassificationResult)
- `radar/backend/app/classification/quota.py` — reserve/complete/fail; INSERT ledger senza article_id a classify-time
- `radar/backend/app/classification/quality_compare.py` — stesso helper usage split + miniflux_entry_id
- `radar/backend/app/worker.py` — timers; URL dedup (SELECT oggi senza `a.id`); post-commit link article_id; pass denorm a commit
- `radar/backend/app/commit/db_commit.py` — INSERT/UPDATE denorm + `article_embeddings` (già scrive embedding)
- `radar/backend/app/extraction/semantic_dedup.py` — `record_dedup_event` (cosine_distance oggi NOT NULL float)
- `radar/backend/app/extraction/state.py` — `is_article_duplicate` resta bool; id dal SELECT worker
- `radar/backend/app/main.py` — GET /api/metrics/summary|by-feed|dedup
- Nuovo: `radar/backend/app/scripts/verify_metrics_013.py`
- Test blast: `test_metrics_013.py` + aggiornare test_commit, test_semantic_dedup, test_quality_replace, test_classification, test_worker_gate, test_quota_concurrency

### Ops live note
- SIMPLE primary: `gemini-3.5-flash-lite`; L1: `gemini-3.1-flash-lite`; limiti tipici RPM≤12 / TPM 250K / RPD 500
- Soft-trim / RPD: se SIMPLE esausta → residual COMPLEX; denorm = modello **vincente**
- Compose: `docker compose up -d --build` (no restart parallelo cieco)
- Requeue: dry-run prima; **no** `--purge-all` salvo richiesta esplicita

## Decisioni NON negoziabili
1. Nessuna UI dashboard / toolbar FinOps in 013
2. Nessun campo LLM `article_type` / cambio `GeopoliticalArticleSchema` (strict)
3. Token unknown → NULL (mai inventare 0)
4. URL dedup scrive `article_dedup_events` con `dedup_kind='url_exact'`
5. `main.py` API-only; ingest solo `radar-worker`
6. Non stageare secrets / `.env`
7. Non mescolare Wave 2 mappa / sidebar / Fase D

## Correzioni review C1–C8 (OBBLIGATORIE — override plan interno)

### C1 — ClassificationResult (breaking)
- Introdurre dataclass `ClassificationResult` con:
  - `article: GeopoliticalArticleSchema`
  - meta: `classification_lane`, `classified_by_model`, `classified_by_provider`, `was_escalated`,
    usage `(prompt_tokens, completion_tokens, cached_prompt_tokens)` nullable,
    `execution_time_ms`, `http_status`, `error_code`
- `classify_article` ritorna `ClassificationResult` (non più solo schema).
- Aggiornare **tutti** i call site: worker (path classify + path replace semantic), test_classification, test_quota_concurrency, seed se serve.
- Worker: `result.article` per vault/commit; meta → denorm.

### C2 — article_id timing
- `reserve(..., miniflux_entry_id=)` quando entry_id noto (classify + quality:compare).
- `complete`/`fail`: FinOps token split + timing + http/error; **non** settare `article_id` a classify-time.
- Post `commit_article_to_db` / `replace_article_in_place`:
  `UPDATE llm_request_ledger SET article_id=$1 WHERE miniflux_entry_id=$2 AND article_id IS NULL`
  (tutte le righe dello stesso entry: retry, L1, residual, quality:compare).

### C3 — URL dedup events
- Nel ramo `is_dup` di `worker.py`, estendere SELECT con `a.id`.
- Prima di mark-read/return: `record_dedup_event(..., dedup_kind='url_exact', action_taken='kept_existing', winner='existing', cosine_distance=None, existing_article_id=a.id, feed_id=..., incoming_miniflux_entry_id=entry_id)`.
- Firma: `cosine_distance: float | None` (DDL DROP NOT NULL).

### C4 — Enum geo_resolution_method (SoT)
Valori ammessi: `llm_extracted` | `centroid_fallback` | `unchanged`.
Euristica: lat/lng ≈ centroide paese noto → `centroid_fallback`; altrimenti `llm_extracted`; path senza geo utile → `unchanged`.
**Vietato** inventare: `extracted_coordinates` / `country_centroid`.

### C5 — Denorm completa su commit/replace
Passare a commit/replace: feed_id, feed_domain, classification_*, was_escalated, clean_text_chars/words, embedding_time_ms, pipeline_latency_ms, geo_resolution_method, dedup_kind/action/match_article_id.
- Happy path insert: `dedup_kind≈none`, `dedup_action≈inserted_new`.
- Replace semantic: denorm coerente.
- `embedding_time_ms` su **sia** `articles` sia `article_embeddings` (INSERT già in db_commit).

### C6 — Token accounting
- Unknown → NULL (mai 0 finti).
- `actual_tokens` = prompt+completion se noti, else total provider.
- `estimated_cost_usd` resta basato su `actual_tokens`.
- Helper usage condiviso client + quality_compare (Gemini `usage_metadata` + OpenAI-compat `usage`).

### C7 — API / docs
- `GET /api/metrics/summary|by-feed|dedup?from=&to=` con tz `RADAR_TIME_ZONE`, range validation, empty OK (non 500).
- Docs: `docs/02_architecture_and_backend.md`, `radar/docs/runbook.md`, **entrambi** mirror `radar-api-contract`.
- Nessun FE / MOCK_MODE metrics.

### C8 — Test blast radius
Oltre `test_metrics_013.py`, aggiorna: test_commit, test_semantic_dedup, test_quality_replace, test_classification, test_worker_gate (URL event), mock return type classify.
`pytest -m "not live"` deve passare.

## Ordine di lavoro (W1–W4)

### W1 — Migrazione
- Creare `013_metrics_and_feed_tracking.sql` come da piano §4
- Nessun apply manuale: `run_migrations` al bootstrap Compose

### W2 — Strumentazione (con C1–C6)
- entry_validation: feed_id + feed_domain
- ClassificationResult + meta → quota complete/fail FinOps
- reserve con miniflux_entry_id; post-commit link article_id
- worker timers + URL event (C3) + denorm pass (C5) + geo enum (C4)
- db_commit + replace denorm; semantic_dedup firme estese
- quality_compare: helper usage + miniflux_entry_id

### W3 — API + test + script
- GET /api/metrics/summary|by-feed|dedup
- pytest `-m "not live"` (C8)
- Script `python -m app.scripts.verify_metrics_013`

### W4 — GATE live + docs + commit
1. `cd radar && docker compose up -d --build` — health OK, 013 in schema_migrations
2. Dry-run poi: `docker compose exec -T radar-worker python -m app.scripts.requeue_articles 15`
3. ≥12 articoli: feed_id/domain, lane/model/provider, pipeline_latency_ms>0, ledger.article_id linkato
4. Secondo requeue → ≥1–2 eventi `url_exact`
5. Semantic keep/replace: opportunistico; se 0 live → pytest + nota GATE
6. API totals == SQL (tolleranza 0); NULL-rate denorm post-013 tipicamente <~5%
7. `verify_metrics_013` live PASS
8. Docs/ECC (C7); commit dettagliato (no `.env`); checklist piano §10; move plan→complete/, prompt→prompts/done/; STATUS.md

## Soglia PASS (GATE)
- [ ] pytest `-m "not live"` verde
- [ ] Docker healthy + migrazione 013
- [ ] ≥12 articoli nuovi: feed_id/domain, lane/model/provider, pipeline_latency_ms, ledger link
- [ ] ≥1 evento URL dedup
- [ ] API summary/by-feed/dedup = SQL
- [ ] verify_metrics_013 live PASS
- [ ] docs/ECC aggiornati (entrambi mirror api-contract)
- [ ] commit senza secrets
- [ ] C1–C8 rispettati (ClassificationResult, article_id post-commit, geo enum SoT)

## Deliverable chat
- Diff codice + migration
- Output pytest + verify + evidence SQL/API (senza secrets)
- Commit hash se richiesto
- Aggiornamento plan-audit STATUS / move complete

Inizia da W1. Non riscrivere i documenti W0 salvo fix minori di coerenza. Se un punto del tuo plan precedente confligge con C1–C8, vincono C1–C8 + SoT.
```

---

## Note per l’orchestratore

- W0 (piano + questo prompt + STATUS) è **già fatto** — non chiedere di “pianificare da zero”.
- Un Implementation Plan generato in chat è utile solo se incorpora **C1–C8**; altrimenti trattarlo come bozza e applicare gli override.
- RPD SIMPLE piena non blocca il GATE metrics se il denorm riflette residual COMPLEX; preferire pezzi SIMPLE quando la quota giornaliera lo consente.
- `is_article_duplicate` resta bool: l’`articles.id` per URL events viene dal SELECT già presente nel ramo dup (esteso con `a.id`).
