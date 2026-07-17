# SoT operativa — allineamento documentazione monorepo Radar

**Ruolo:** checklist eseguibile per aggiornare README / `docs/*` / ops / ECC.  
**Non** sostituisce: SoT LLM, Phase scoreboard, manuali prodotto (questi sono i *target*).  
**Data:** 2026-07-17 · **Stato:** ESEGUITO (rewrite product docs + puntatori)

**Product docs (target):** root `README.md`, `docs/01–04`, `radar/ops/README.md`, `radar/docs/runbook.md`, `radar/frontend/README.md`.  
**Design LLM:** [`sot_llm_multi_model_fallback.md`](sot_llm_multi_model_fallback.md) · knobs: `radar/.env.example`.  
**Phase GATE:** [`plan_impl_phase_0_6_execution.md`](plan_impl_phase_0_6_execution.md) · Final residui: [`plan_release_final_gate.md`](plan_release_final_gate.md).

Audit: passata 1 (inventario/gap/SoT) + passata 2 (markdown/codice/piano/SoT↔code).

---

## 0. Stato AS-IS / TO-BE

| Tema | AS-IS | TO-BE |
|------|-------|-------|
| Phase 0–6 | DONE / GATE VERDE (`56c2eff`) | Invariato; badge README chiaro |
| Final Release | Premesse chiuse; gate residui **aperto** | README distingue ≠ Phase GATE |
| LLM product voice | Tagline/ops ancora Gemini-only | Multi-provider + Profili A–E (link) |
| Migrazioni | Disco 001–009; docs spesso ≤007 | Tabella 001–009 in docs/02 + tree README |
| Cooldown | Codice + runbook + mig 009 | Pointer in README/01/02 |
| Requeue | Solo runbook | Pointer README/01/02/ops |
| Spiderfy | docs/03 no-cap-24; FE README max 24 | FE README allineato |
| `claude` | Stub in codice/SoT/runbook | Sempre “stub” nei product docs |

**Fuori scope:** codice produzione, `.env`, `radar-sidebar/**`, archive come SoT viva, Anthropic Messages, rewrite `ecc_deep_dive_analysis_v2.md`.

---

## 1. Inventario (sintesi)

**Prodotto vivo:** solo `radar/` (5 servizi Compose: frontend, backend, worker, db, miniflux) su `radar-edge` + `radar-data`.

| Area | Path | Owner doc | Gap tipico |
|------|------|-----------|------------|
| Hub | `README.md` | sé | Gemini-only, tree 001–007 |
| Avvio | `docs/01_getting_started.md` | README | prereq Gemini, no stub/requeue |
| Architettura | `docs/02_architecture_and_backend.md` | README | migrazioni ≤007, no cooldown |
| FE | `docs/03_frontend_and_ui.md` | README | ok |
| ECC | `docs/04_ecc_framework.md` | README | skill blurbs |
| Ops | `radar/ops/README.md` | docs/01 | one-liner Gemini |
| Runbook | `radar/docs/runbook.md` | ops | deploy Gemini strings |
| FE README | `radar/frontend/README.md` | sé | hard-cap 24 |
| SoT LLM | `plan-audit/active/sot_llm_*.md` | plan-audit | link prompt/canvas |
| AGENTS/CLAUDE | `.agents/AGENTS.md`, `radar/.ecc/CLAUDE.md` | docs/04 | obiettivo Gemini; tree CLAUDE incompleto |
| Nginx | `radar/frontend/nginx.conf` | docker.md | listen 8080, host 80 |
| Cooldown | `classification/cooldown.py` + `009_*.sql` | runbook | manca in 01/02 |
| Requeue | `app/scripts/requeue_articles.py` | runbook | manca pointer hub |
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
- [ ] Tagline multi-provider
- [ ] Dipendenze: RSS + LLM API + Carto
- [ ] Stato: Phase GATE + Final Release link
- [ ] Avvio: lane keys → `.env.example`
- [ ] Mermaid: nodo LLM (non solo Gemini)
- [ ] Doc table: SoT LLM, requeue→runbook, Final Release, questo source
- [ ] Tree: migrations 001–009; `app/scripts/`
- [ ] Mappa codice: llm_lanes, complexity, cooldown, requeue
- **AC:** no “arricchisce via Google Gemini” come unica path; link SoT+Final+requeue; tree 001–009

### 5.2 docs/01
- [ ] Requisiti multi-provider
- [ ] claude=stub in tabella LLM
- [ ] Ciclo QuotaLedger → lane → cooldown → commit
- [ ] Troubleshooting multi-provider + requeue→runbook
- [ ] Nota Profilo B ops vs MODE=off default codice
- **AC:** stub + requeue + prereq non Gemini-only

### 5.3 docs/02
- [ ] Intro GATE VERDE
- [ ] Classification: stub + dialect
- [ ] Sezione Cooldown (009)
- [ ] Tabella migrazioni 001–009
- [ ] Ops scripts requeue pointer
- [ ] Layer: llm_lanes, complexity, cooldown
- **AC:** 9 migrazioni + stub + cooldown + requeue

### 5.4 docs/04
- [ ] llm-json multi-provider
- [ ] quota-ledger + claude=stub
- [ ] Nota deep-dive / SoT LLM
- **AC:** nessuno “solo Gemini SDK” come unica path skill

### 5.5 ops / runbook / FE README / AGENTS / CLAUDE / SoT
- [ ] ops one-liner + pointers
- [ ] runbook deploy multi-provider
- [ ] FE README no-cap-24
- [ ] AGENTS obiettivo
- [ ] CLAUDE obiettivo + tree
- [ ] SoT link fix
- **AC:** FE senza max 24; CLAUDE con 009; SoT senza canvas fantasma

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
