# Agent prompt — FinOps LLM: Token Saving & Prompt Caching

> **Stato: DONE / GATE VERDE (condizionato)** — implementato ed archiviato (2026-07-22; Wave A = M1–M6 completata, N=272 elaborazioni post-cutover).  
> **Piano SoT:** [`../../complete/plan_impl_llm_finops_token_caching.md`](../../complete/plan_impl_llm_finops_token_caching.md)  
> **Verifica / GATE (twin):** [`../../complete/plan_impl_llm_finops_token_caching_verification.md`](../../complete/plan_impl_llm_finops_token_caching_verification.md)  
> **Branch:** `feature/upgrades`  
> **Prerequisiti:** Fase C + Metrics 013 + BORDERLINE effort split = GATE VERDE in `plan-audit/complete/`  
> **Origine Cursor:** `.cursor/plans/llm_finops_review_3c526d6a.plan.md`

---

## Come usare (orchestratore)

1. Apri una **nuova chat Agent** su branch `feature/upgrades` (repo root Intelligence-Dashboard).
2. Incolla il blocco **PROMPT** qui sotto **per intero**.
3. Wave A = **M1 → M2 → M4 → M3 → M5 → M6**, poi verifica twin (pytest + live **100–150** articoli).
4. **Non** implementare M7 boilerplate, M8 cap output, explicit Gemini cache, always-keep.
5. A GATE VERDE (twin §5): aggiorna `STATUS.md`; sposta piano+twin in `complete/` e questo file in `prompts/done/` solo a chiusura formale fase.

---

## PROMPT (incolla in Agent mode)

```text
# Task — IMPLEMENTAZIONE: FinOps LLM Token Saving & Prompt Caching (Wave A)

## Ruolo
Sei pipeline engineer sul modulo Radar Informativo Globale. Implementi Wave A (M1–M6) seguendo i due documenti SoT. Priorità assoluta: zero regressioni qualitative (estrazione geopolitica, dedup Fase C replace, ValidationError rate). Leggi le skill prima di toccare classification/.

## Obiettivo
Ridurre token e costo API (Prompt Caching + meno chiamate ridondanti) senza peggiorare qualità. Chiudi con verifica twin: pytest + campione live 100–150 articoli.

## Autorità (ordine di precedenza)
1. SoT: `plan-audit/complete/plan_impl_llm_finops_token_caching.md`
2. Twin verifica: `plan-audit/complete/plan_impl_llm_finops_token_caching_verification.md` (baseline SQL, pytest, live 100–150, go/no-go, rollback)
3. Questo prompt (override se un piano interno confligge)
4. Skills + `radar/.ecc/rules/backend.md` + `.agents/AGENTS.md`

## Decisioni chiuse (NON violare)
- NO always-keep su sim≥0.95 — solo M5 euristico (title + length)
- NO explicit Gemini `caches.create`
- NO riscrittura ampia SYSTEM — solo +2–4 frasi formato wire in M3
- NO abbassare max_output_tokens / max_tokens (M8 = HOLD)
- NO abbassare SEMANTIC_DEDUP_SIMILARITY_THRESHOLD sotto 0.80
- NO M7 boilerplate in Wave A
- NO package `openai`; NO tocchi `radar-sidebar/**`; NO cambio field names Pydantic
- Token unknown → NULL, mai inventare 0
- Ingest solo in radar-worker; main.py API-only
- “Molto più lungo” = `SEMANTIC_QUALITY_REPLACE_HINT_RATIO` default 1.25 (riusa env)

## Contesto obbligatorio (leggere PRIMA di codare)

### Quadro / SoT
- `plan-audit/STATUS.md`
- `plan-audit/complete/plan_impl_llm_finops_token_caching.md`
- `plan-audit/complete/plan_impl_llm_finops_token_caching_verification.md`
- `plan-audit/complete/plan_impl_fase_C_semantic_dedup.md`
- `plan-audit/complete/plan_impl_fase_metrics_013.md`
- `plan-audit/complete/plan_impl_borderline_effort_split.md`
- `plan-audit/complete/sot_llm_multi_model_fallback.md`
- `radar/docs/runbook.md`

### Skills
- `.agents/skills/llm-json-extraction/SKILL.md` (M3 / prompts; sync C-07)
- `.agents/skills/radar-quota-ledger/SKILL.md`
- `.agents/skills/radar-api-contract/SKILL.md` (M4)
- `.agents/skills/radar-docker-ops/SKILL.md`
- `.agents/skills/radar-requeue-ops/SKILL.md` (campione 100–150; dry-run; no purge-all senza ok)

### Codice AS-IS critico
- `radar/backend/app/classification/client.py` — `extract_usage_tokens` (manca DeepSeek `prompt_cache_hit_tokens`)
- `radar/backend/app/classification/deepseek.py` — suffix lungo ~179–203 = M3
- `radar/backend/app/classification/prompts.py` — SYSTEM_PROMPT SoT
- `radar/backend/app/classification/openai_compat_payload.py` — NON abbassare max_tokens
- `radar/backend/app/classification/quality_compare.py` — prefilter; riusa REPLACE_HINT_RATIO
- `radar/backend/app/worker.py` — M5 + M6 innesti
- `radar/backend/app/extraction/semantic_dedup.py`, `parser.py`
- `radar/backend/app/commit/db_commit.py` — persist `content_sha256`
- `radar/backend/app/main.py` — GET /api/metrics/*
- `radar/backend/migrations/` — nuova `014_*content_sha256*` (dopo 013)
- Tests: prompt_contract, classification, semantic_dedup, quality_replace, extraction + nuovi

### Bug metriche
DeepSeek: `usage.prompt_cache_hit_tokens`. Radar oggi non li mappa → M1 bloccante per FinOps vero.

## Wave A — ordine obbligatorio

### A1 = M1 Parse cache DeepSeek
- `extract_usage_tokens`: preferisci `prompt_cache_hit_tokens`; fallback `prompt_tokens_details.cached_tokens`; Gemini invariato
- Test fixture DeepSeek-shaped + OpenAI-shaped; assente → None (non 0)

### A2 = M2 Baseline SQL
- Esegui query twin §2; compila tabella baseline nel twin §2.2 e SoT “Baseline eseguita”
- Includi fail/ValidationError proxy e was_escalated % (servono al confronto post)

### A3 = M4 Metrics cache rate
- Estendi `/api/metrics/summary` e/o `/api/metrics/llm` con `cache_hit_rate_pct` + breakdown minimo utile
- Sync skill `radar-api-contract` (+ mirror ECC se richiesto)

### A4 = M3 Suffix de-dupe
1. `deepseek.py`: micro-suffisso JSON-only; TENERE CORREZIONE + THINKING MODE Ollama
2. `prompts.py`: SOLO 2–4 frasi wire (flat lat/lon, CSV non array, solo JSON/no markdown); NON riduplicare categorie/esempi
3. Contract tests + test “no long taxonomy suffix”
4. Sync skill llm-json-extraction se SYSTEM cambia
5. pytest mirati

### A5 = M5 Bypass high-sim
- Prima di `compare_articles_quality` in worker
- Gate: distance≤0.05 AND clean_words≥70 AND title Jaccard≥0.90
- Se len_inc > exist * SEMANTIC_QUALITY_REPLACE_HINT_RATIO (1.25) → replace (classify), skip compare
- Else → keep existing, 0 LLM
- Else gate fail → compare AS-IS
- Env distance/words/title/shadow; audit action_taken; pytest keep/replace/no-bypass

### A6 = M6 Content hash
- Dopo strip HTML: normalize title+body → SHA-256
- Lookup 24h su `articles.content_sha256`; hit → keep, 0 embed+LLM, audit `kept_existing_content_hash`
- Miss → pipeline normale; persist hash al commit
- Migration 014 + indice; env `CONTENT_HASH_DEDUP_ENABLED` default true
- Pytest hit/miss

### A7 = Verifica twin (obbligatoria per GATE)
Segui `plan_impl_llm_finops_token_caching_verification.md` alla lettera:
1. pytest suite Wave A (§3)
2. rebuild worker (compose up -d --build servizi toccati)
3. Campione live **≥100** articoli (target **150**): traffico naturale o requeue dry-run→run (no purge-all)
4. Compila checklist twin §4.3 + smoke qualitativo 10 pezzi §4.4
5. Decisione §5: GATE VERDE / ROLLBACK M3 / DISABLE M5 / DISABLE M6 / HOLD
6. Compila registro twin §7

Se ValidationError sale oltre soglia → rollback suffix in `deepseek.py` prima di altro.

## Wave B — NON in questa sessione salvo ok utente
- M7 boilerplate RSS (coda-only, allowlist frasi; NON keyword globali)
- M8 HOLD
- M9/M10 ops FinOps

## Anti-pattern
- Non “spostare tutta la tassonomia” nel SYSTEM
- Non abbassare cap output
- Non caches.create Gemini
- Non always winner=existing su high sim
- Non dichiarare GATE senza twin 100–150
- Non commitare `.env` / segreti
- Non commit git salvo richiesta esplicita utente

## Definition of Done — Wave A
- [ ] M1–M6 implementati + test unitari
- [ ] Baseline M2 compilata (SoT + twin)
- [ ] M4 API cache_hit_rate
- [ ] M3 suffix rimosso; contract tests verdi; skill sync se serve
- [ ] M5 pytest keep/replace/no-bypass; audit events
- [ ] M6 migration + hash keep path; pytest hit/miss
- [ ] Twin: pytest + live ≥100 (target 150) + registro §7 + decisione §5
- [ ] Nessun tocco M7/M8/sidebar/schema field names
- [ ] `plan-audit/STATUS.md` aggiornato con esito verifica

## Output atteso a fine sessione
1. Diff file toccati
2. Risultati pytest
3. Numeri baseline + post (twin)
4. N articoli campione + decisione GATE
5. Cosa resta a Wave B (M7+)
```

---

## Note ops

- Compose: `docker compose up -d --build` sui servizi toccati; evitare restart parallelo cieco.
- Requeue: dry-run prima; no `--purge-all` senza richiesta esplicita.
- Profilo tipico: verificare `radar/.env` locale (non committare).
