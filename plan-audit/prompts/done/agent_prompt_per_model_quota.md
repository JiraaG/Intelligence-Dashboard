# Agent prompt — Quote per-modello (SIMPLE/COMPLEX FALLBACKS)

> **Stato: ACTIVE** — pronto per chat Agent (docs 2026-07-22; **review R1–R8** sull’Implementation Plan orchestratore).  
> **Piano SoT:** [`../../active/plan_impl_per_model_quota.md`](../../active/plan_impl_per_model_quota.md)  
> **Branch:** `feature/upgrades`  
> **W0 docs:** DONE. **Impl:** questa chat Agent.

---

## Come usare

1. Nuova chat **Agent** su `feature/upgrades`.
2. Incolla il blocco **PROMPT** sotto.
3. Se hai già un Implementation Plan interno, **R1–R8 override** dove confligge.
4. A GATE: piano → `complete/`, prompt → `prompts/done/`, `STATUS.md`.

---

## PROMPT (incolla in Agent mode)

```text
# Task — IMPLEMENTAZIONE: Quote per-modello (con correzioni review R1–R8)

## Ruolo
Pipeline engineer Radar. Implementa RPM/TPM/RPD **per model** su catena SIMPLE/COMPLEX (FALLBACKS), default lane facili (`0`=unmanaged) + override CSV. GATE con pytest + requeue 24h reale. Scenario prova: Studio 3.1 alto/esausto, 3.5 con residuo — **senza** bump `LLM_SIMPLE_RPD` di lane.

## Autorità (ordine)
1. SoT `plan-audit/active/plan_impl_per_model_quota.md` (incluso §9 Review R1–R8)
2. Correzioni R1–R8 in questo prompt (override sul tuo Implementation Plan)
3. Skills: radar-quota-ledger, radar-requeue-ops, radar-docker-ops
4. Sidebar freeze; no UI; no `--purge-all` salvo richiesta esplicita; non stageare `.env`

## Il tuo plan orchestratore è OK su
- Default lane + MODEL_LIMITS CSV + pool separati 3.5/3.1
- quota.py filter `model=`; legacy NULL esclusi
- Soft-trim hibernate solo se tutta catena SIMPLE managed esausta (+ bypass COMPLEX)
- test_quota_concurrency + verify_per_model_quota.py
- Docs ritirano “lane-shared by design”
- Live requeue senza purge-all + verify_metrics_013

## Correzioni OBBLIGATORIE (R1–R8)

### R1 — Spacing in-process RESTA per-lane
NON tracciare `_last_reserve_mono` per `(lane, model)`.
Motivo: stessa API key Gemini; spacing per-model raddoppierebbe il burst RPM effettivo.
Solo i **contatori durable** RPM/TPM/RPD nel ledger sono per-model.
`min_interval_seconds(lane)` invariato a livello lane.

### R2 — Soft-trim: hibernate E riduzione lotto
In `run_pipeline_cycle` oggi c’è anche `entries = entries[:remaining_rpd]` basato su `simple_rpd - processed_today` (lane-wide).
Riscrivere:
- residuale catena = per ogni model in `LLM_SIMPLE.models` con rpd_cap>0: max(0, cap - used_today[model])
- `simple_has_residual` = esiste model con residuale > 0  OR  nessun model managed (soft-trim off)
- hibernate solo se not simple_has_residual AND not has_complex_residual
- riduzione lotto: usa somma (o max documentato) dei residuali managed — **non** il vecchio conteggio lane-wide
Log: menzionare per-model used/cap, non solo “LANE SIMPLE”.

### R3 — Unmanaged semantics
- Lane default `RPD=0` (e nessun override rpd>0) → soft-trim off, nessun QuotaDailyExceeded da RPD.
- Override `model:…:0` su una dimensione → unmanaged solo quella dimensione per quel model.
- Fail-fast: documenta comportamento mix managed/unmanaged in runbook.

### R4 — Parse MODEL_LIMITS fail-fast
`model:rpm:tpm:rpd` malformato → raise chiaro a `load_lanes` / startup (non silent skip). Test dedicato.

### R5 — Budget USD resta per-lane
Non spezzare `*_BUDGET_USD_DAY` per model in questa fase.

### R6 — quality:compare
Nessun lavoro speciale: usa già reserve(model=…) su COMPLEX; eredita contatori per-model.

### R7 — GATE live (reale)
Pre-check SQL ledger oggi per model.
**VIETATO** alzare `LLM_SIMPLE_RPD` di lane per far passare il test 3.5.
```bash
cd radar && docker compose up -d --build
# dry-run poi:
docker compose exec -T radar-worker python -m app.scripts.requeue_articles $N --dry-run
docker compose exec -T radar-worker python -m app.scripts.requeue_articles $N
# N ≈ created_today (cap 500); NO --purge-all
```
Assert:
- Log/SQL: `gemini-3.5-flash-lite` reserved/completed anche se 3.1 near-cap/cooldown
- Se 3.5 esaurisce → cooldown 3.5 → prova 3.1 o residual DeepSeek
- Embeddings + `verify_metrics_013` exit 0 + `verify_per_model_quota` (used/cap/residual)
- Zero Traceback bloccanti
Se Studio 3.5 è a 0 a runtime: documenta; prova comunque failover; non inventare successo 3.5.

### R8 — Docs
Oltre runbook / .env.example / quota-ledger skill (entrambi mirror) / CLAUDE / SoT C8:
- `docs/02_architecture_and_backend.md`
- `.agents/AGENTS.md` se cita RPD lane-shared
Ritirare “Studio ≠ Radar perché lane shared” come *contratto*; sostituire con per-model counters + default/override + 0 unmanaged.

## Design chiuso (riassunto)
```
LLM_SIMPLE_RPM/TPM/RPD     # default per ogni model della catena; 0=unmanaged
LLM_SIMPLE_MODEL_LIMITS=gemini-3.5-flash-lite:12:250000:500,gemini-3.1-flash-lite:12:250000:500
LLM_COMPLEX_MODEL_LIMITS=
```
Contatori ledger: `AND model = $model`. Cascade client già OK su hard_cooldown → next.

## Wave
W1 llm_lanes parse + limits_for_model + .env.example  
W2 quota.py per-model counts (spacing lane — R1)  
W3 worker soft-trim + lot size (R2)  
W4 pytest + verify_per_model_quota.py  
W5 docs (R8)  
W6 GATE live (R7) + commit + move plan-audit

## Test unitari minimi
1. A RPD=1 esausto → B stessa lane ancora reserve OK  
2. MODEL_LIMITS override + default fallback + fail-fast malformato  
3. rpd=0 unmanaged: no QuotaDailyExceeded  
4. soft-trim: A esausto + B residuale → no hibernate; lot reduction usa residuale catena  

`pytest -m "not live"` verde.

## Done when
- [ ] R1–R8 rispettati
- [ ] pytest verde
- [ ] Live 3.5 lavora con 3.1 alto **senza** bump RPD lane
- [ ] requeue vault+unread OK; metrics 013 OK; verify_per_model_quota OK
- [ ] docs/ECC/SoT; commit no `.env`; STATUS/plan move complete

## Fuori scope
UI, article_type, sidebar, Wave 2, per-model BUDGET_USD, --purge-all globale.

Inizia da W1. Override R1–R8 sul plan orchestratore dove confligge.
```

---

## Verdetto review (per PO)

| Area | Score |
|------|-------|
| Allineamento SoT complessivo | **~90%** |
| Scelte core (default + override + per-model count) | **Corrette** |
| Gap critici | **R1 spacing**, **R2 lot reduction**, **R4 fail-fast**, **R7 no-bump** |
| Pronto ad impl con questo prompt | **Sì** |
