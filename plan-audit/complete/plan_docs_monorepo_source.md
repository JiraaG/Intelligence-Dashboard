# SoT operativa — allineamento documentazione monorepo Radar

**Ruolo:** checklist eseguibile per aggiornare README / `docs/*` / ops / ECC.  
**Non** sostituisce: SoT LLM, Phase scoreboard, manuali prodotto (questi sono i *target*).  
**Data:** 2026-07-17 · **Stato:** ESEGUITO + remediation coerenza (porte/health/requeue)

**Product docs (target):** root `README.md`, `docs/01–04`, `radar/ops/README.md`, `radar/docs/runbook.md`, `radar/frontend/README.md`.  
**Design LLM:** [`sot_llm_multi_model_fallback.md`](sot_llm_multi_model_fallback.md) · knobs: `radar/.env.example`.  
**Phase GATE:** [`plan_impl_phase_0_6_execution.md`](plan_impl_phase_0_6_execution.md) · Final residui: [`../active/plan_release_final_gate.md`](../active/plan_release_final_gate.md).  
**Quadro:** [`../STATUS.md`](../STATUS.md).

Audit: passata 1–2 docs + passata coerenza (README→ECC) con fix P0–P2.

---

## 0. Stato AS-IS / TO-BE

| Tema | AS-IS (post-remediation) | Note |
|------|--------------------------|------|
| Phase 0–6 | DONE / GATE VERDE | Badge README + Final ≠ GATE |
| LLM product voice | Multi-provider + Profili A–E | Profilo B ops vs `MODE=off` codice chiarito |
| Migrazioni | Tabella 001–009 in docs/02 + tree README | OK |
| Cooldown / requeue | Pointer + comando worker canonico | Warning distruttivo in runbook |
| Spiderfy | docs/03 + FE README no hard-cap 24 | OK |
| Porte FE | `.env.example` `80:8080`; mermaid host/listen | OK |
| `/health` | FE host ≠ API live separati in README | OK |
| `claude` | stub nei product docs | OK |

**Fuori scope:** codice produzione, `.env` secrets, `radar-sidebar/**`, archive come SoT viva, Anthropic Messages, rewrite `ecc_deep_dive_analysis_v2.md`.

---

## 1. Inventario (sintesi) — gap *pre-fix* (storico 2026-07-17)

**Prodotto vivo:** solo `radar/` (5 servizi Compose: frontend, backend, worker, db, miniflux) su `radar-edge` + `radar-data`.

La colonna “Gap pre-fix” è lo **snapshot audit** prima della remediation docs; lo stato corrente è in §0 (OK). Non riaprire questi gap salvo regressione.

| Area | Path | Owner doc | Gap pre-fix (storico) |
|------|------|-----------|------------------------|
| Hub | `README.md` | sé | Gemini-only, tree 001–007 — **FIXED** |
| Avvio | `docs/01_getting_started.md` | README | prereq Gemini, no stub/requeue — **FIXED** |
| Architettura | `docs/02_architecture_and_backend.md` | README | migrazioni ≤007, no cooldown — **FIXED** |
| FE | `docs/03_frontend_and_ui.md` | README | ok |
| ECC | `docs/04_ecc_framework.md` | README | skill blurbs — **FIXED** |
| Ops | `radar/ops/README.md` | docs/01 | one-liner Gemini — **FIXED** |
| Runbook | `radar/docs/runbook.md` | ops | deploy Gemini strings — **FIXED** |
| FE README | `radar/frontend/README.md` | sé | hard-cap 24 — **FIXED** |
| SoT LLM | `plan-audit/active/sot_llm_*.md` | plan-audit | link prompt/canvas — **FIXED** |
| AGENTS/CLAUDE | `.agents/AGENTS.md`, `radar/.ecc/CLAUDE.md` | docs/04 | obiettivo Gemini; tree incompleto — **FIXED** |
| Nginx | `radar/frontend/nginx.conf` | docker.md | listen 8080, host 80 |
| Cooldown | `classification/cooldown.py` + `009_*.sql` | runbook | manca in 01/02 — **FIXED** |
| Requeue | `app/scripts/requeue_articles.py` | runbook | manca pointer hub — **FIXED** |
| Vendor | `ECC-GitHub/`, `.kilo/` | — | **omit** |

### Migrazioni 001–009 (copiare in docs/02)

| File | Scopo |
|------|--------|
| `001_initial.sql` | Schema base articles/companies/tags |
| `002_pipeline_outbox_and_quotas.sql` | article_outbox |
| `003_quota_ledger.sql` | llm_request_ledger |
| `004_worker_heartbeat.sql` | heartbeat leader |
| `005_quota_ledger_align.sql` | allinea ledger legacy |
| `006_quota_ledger_legacy_nulls.sql` | null legacy + request_type |
| `007_articles_query_indexes.sql` | indici Phase 5 |
| `008_outbox_miniflux_marked_at.sql` | mark-read retry / marked_at |
| `009_llm_model_cooldown.sql` | cooldown durable (provider, model) |

---

## 2. IA anti-duplicazione

| Tema | SoT unica | Altri = link |
|------|-----------|--------------|
| Onboarding | README | — |
| Avvio step-by-step | docs/01 | ops |
| Architettura/API/worker | docs/02 | skills |
| FE/mappa | docs/03 | sidebar-freeze skill |
| Harness ECC | docs/04 | AGENTS/CLAUDE |
| Incident/requeue | runbook | README/01/02/ops |
| Backup/overlay | ops README | runbook |
| Design LLM / Profili A–E | SoT LLM | `.env.example` ricette |
| Phase 0–6 | plan_impl_phase_0_6_execution | README badge |
| Final Release | plan_release_final_gate | README 1 riga |
| Knobs env | `.env.example` | mai tabelle lunghe duplicate |
| Docker/health | `radar/.ecc/rules/docker.md` | skill docker-ops |

---

## 3. Template LLM canonico (product docs)

```text
Routing v2.2: SIMPLE | BORDERLINE | COMPLEX.
SIMPLE → LLM_SIMPLE_*; BORDERLINE+COMPLEX → LLM_COMPLEX_* (purpose classify:complex).
Provider: gemini|deepseek|openai|glm|grok|claude (stub; Messages non implementata).
OpenAI-compat via httpx (no package openai): deepseek=thinking; openai|glm|grok=stock.
Limiti per lane; 0 = unmanaged. Soft-trim = LLM_SIMPLE.rpd se >0.
Free → RPM/RPD>0; paid → RPM/RPD=0 + BUDGET_USD_DAY.
Residual: se identity diversa, fallback cross-lane; fattura ref.quota_lane.
Ops tipico: Profilo B (.env.example). Default codice boot-safe: MODE=off, SHADOW=true — non confondere.
Cooldown durable (migrazione 009): vedi runbook. Requeue: python -m app.scripts.requeue_articles.
```

**Vietato nei product docs:** gate COMPLEX 20–40% come SLO; “default = DeepSeek complexity”; mermaid SoT AS-IS solo-Gemini; canvas inesistenti; Anthropic come supportato.

---

## 4. Gap → azione

| File | Azione |
|------|--------|
| `README.md` | rewrite hub multi-LLM + Final ≠ GATE + SoT + requeue + tree 001–009 |
| `docs/01_getting_started.md` | prereq multi; claude=stub; ciclo; requeue; routing note |
| `docs/02_architecture_and_backend.md` | GATE VERDE; tabella 001–009; cooldown; stub; requeue |
| `docs/03_frontend_and_ui.md` | leave (opz. 1 riga Phase 6) |
| `docs/04_ecc_framework.md` | skill one-liners + nota deep-dive stale |
| `radar/ops/README.md` | one-liner lane keys; pointer requeue/SoT; porte 80→8080 |
| `radar/docs/runbook.md` | solo stringhe deploy/escalation multi-provider |
| `radar/frontend/README.md` | spiderfy no hard cap 24 |
| `.agents/AGENTS.md` | obiettivo multi-LLM |
| `radar/.ecc/CLAUDE.md` | obiettivo + tree 009/complexity/cooldown/llm_lanes/requeue |
| `plan-audit/active/sot_llm_*.md` | fix link prompt/canvas |
| `plan-audit/README.md` | riga product docs + questo file |
| `radar/.ecc/rules/docker.md` | Miniflux→LLM→DB |

---

## 5. Checklist per file (heading / target / AC)

### 5.1 README.md
- [x] Tagline multi-provider
- [x] Dipendenze: RSS + LLM API + Carto
- [x] Stato: Phase GATE + Final Release link
- [x] Avvio: lane keys → `.env.example` + Profilo B vs `MODE=off`
- [x] Mermaid: nodo LLM + FE host:80 / listen:8080
- [x] Doc table: SoT LLM, requeue→runbook, Final Release, fork per ruolo
- [x] Tree: migrations 001–009; `app/scripts/requeue_articles.py`
- [x] `/health` FE host ≠ API live separati; branch volatile documentato
- **AC:** soddisfatto (remediation coerenza 2026-07-17)

### 5.2 docs/01
- [x] Requisiti multi-provider
- [x] claude=stub in tabella LLM
- [x] Ciclo QuotaLedger → lane → cooldown → commit
- [x] Troubleshooting multi-provider + requeue worker canonico
- [x] Nota Profilo B ops vs MODE=off default codice
- **AC:** soddisfatto

### 5.3 docs/02
- [x] Intro GATE VERDE
- [x] Classification: stub + dialect
- [x] Sezione Cooldown (009)
- [x] Tabella migrazioni 001–009
- [x] Ops scripts requeue comando worker
- [x] Layer: llm_lanes, complexity, cooldown
- **AC:** soddisfatto

### 5.4 docs/04
- [x] llm-json multi-provider
- [x] quota-ledger + claude=stub
- [x] Nota deep-dive / SoT LLM
- **AC:** soddisfatto

### 5.5 ops / runbook / FE README / AGENTS / CLAUDE / SoT
- [x] ops one-liner + pointers
- [x] runbook deploy multi-provider + warning requeue distruttivo
- [x] FE README no-cap-24
- [x] AGENTS obiettivo
- [x] CLAUDE obiettivo + tree
- [x] SoT link fix
- **AC:** soddisfatto

---

## 6. Ordine di edit

1. Questo file + `plan-audit/README.md`
2. `README.md`
3. `docs/01` → `docs/02` → `docs/04` (+ `docs/03` opz.)
4. `radar/ops/README.md` → `radar/docs/runbook.md` → `radar/frontend/README.md`
5. `.agents/AGENTS.md` → `radar/.ecc/CLAUDE.md`
6. SoT LLM link fix → `radar/.ecc/rules/docker.md`
7. Grep anti-drift

---

## 7. Grep anti-drift (Step 5)

```text
via Google Gemini
GEMINI_API_KEY   (come unico knob richiesto in avvio)
max **24** | hard cap 24
001–007
claude senza "stub" nel contesto provider
COMPLEX 20–40%   (non in product docs)
```

`git status`: niente `.env`; niente `radar-sidebar/**`.

---

## 8. File touch list

**Must:** README, docs/01, docs/02, docs/04, ops/README, runbook, FE README, AGENTS, CLAUDE, SoT LLM (link), plan-audit/README, questo file.  
**P1:** `radar/.ecc/rules/docker.md`, docs/03 opz.  
**Leave:** codice, compose, `.env*`, sidebar, archive, ecc_deep_dive body.
