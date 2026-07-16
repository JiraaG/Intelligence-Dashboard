# Audit Problemi Documentazione — Risoluzione

## Metadati di Stato
* **Data di creazione:** 2026-07-15
* **Data chiusura FASE 0:** 2026-07-15 (verifica aggiuntiva + riparazione handoff)
* **Manuale operativo di riferimento:** `audit_problemi_documentazione.md` (v2.2 · FASI 0–2 + APPENDICE F)
* **Gate Progetto:** Phase 6 / Gate Verde (Stato post-branch restore)
* **Stato Fase 0:** **FASE 0 DONE DEFINITIVA**
* **Remediation codice:** T-P0-01 **DONE**, T-P1-03 **DONE**, T-P1-01 **DONE**, T-P1-02 **DONE**, T-P0-02 **DONE**, T-P1-04 **DONE** (2026-07-16); resto OPEN; prossimo **T-P1-05**
* **Follow-up ops (non ticket SoT):** OPS-FIX `init_pool` retry + doc Docker — codice/docs in working tree (commit su richiesta); pytest not live **116** post-fix.* **SoT stato ticket:** questo file §3 (stati `OPEN` / `DONE` / `CLOSED`). Playbook riprodurre/fix/gate = manuale FASI 3–5. Dopo ogni fix aggiornare §3 qui e la matrice FASE 2 del manuale.

### Definition of Done FASE 0 (firmata)
1. Manuale v2.2 + App. F letti; conteggio OPEN codice **all’epoca FASE 0** = 2 P0 + 5 P1 + 8 P2; docs OPEN residui = 0 (T-DOC-01 CLOSED). **Oggi (post T-P1-04):** P0=0, P1=1, P2=8 → 9 OPEN (SoT §3).
2. Invarianti §1.3 (Sidebar Freeze + read/unread separati) documentate senza contraddizioni.
3. Matrice ticket con ID, finding scratch, priorità, file, dipendenze, stato `OPEN`/`CLOSED`.
4. Elevazioni T-P0-02 / T-P1-05 e dipendenza T-P0-01→T-P1-03 esplicite.
5. Ordine remediation = FASE 4 manuale (T-DOC-01 rimosso dalla coda: già CLOSED).
6. 14 aree PASS elencate e vietate.
7. Happy path distingue **AS-IS** vs **POST-FIX**.
8. Contratto LLM (prompt F.8) e definizioni P0/P1/P2 congelati in questo log.
9. Zero modifiche remediation a `radar/backend/**`, `radar/frontend/**`, Dockerfile o migrazioni in FASE 0.
10. Metadati: DONE DEFINITIVA FASE 0; remediation codice **poi avviata** (header: T-P1-04 DONE; prossimo T-P1-05).

---

## 0. Contratto FASE 0 (esito lettura obbligatoria)

### 0.1 Priorità (da manuale §0.3)

| Pri | Significato | Quando blocca il merge |
|-----|-------------|------------------------|
| **P0** | Perdita dati, sicurezza, crash operativo, script CI inutilizzabili critici | Sì |
| **P1** | Race, config fragile, UX errore silenzioso, privilegio container | Sì se in path produzione |
| **P2** | Igiene, difesa in profondità, allineamento cosmetico docs | No (backlog) |

Le elevazioni T-P0-02 / T-P1-05 sono intenzionali (App. F §F.2). Un LLM **non** le riabbassa senza decisione umana.

### 0.2 Contratto LLM adottato (manuale F.8 — sostituisce §0.2 post-v2.1)

```text
Sei un agente di remediation sul repo Radar Informativo Globale.
SoT: audit_problemi_documentazione.md v2.2 + APPENDICE F.
Stato ticket operativo: audit_problemi_documentazione_risoluzione.md §3.
radar/.ecc/CLAUDE.md è allineato Gate Verde (T-DOC-01 CLOSED); preferisci comunque .agents/AGENTS.md + radar/.ecc/rules/*.md come guardrail.
Vincoli: sidebar freeze; main.py API-only; asyncpg; window.L; no commit senza richiesta.
Ticket OPEN in ordine FASE 4 (T-P0-01..T-P1-04 DONE; prossimo T-P1-05 → P2).
Ticket per turno: riproduci → fix → gate FASE 5 → marca DONE in risoluzione §3 e aggiorna manuale FASE 2.
Priorità elevate storiche: T-P0-02 chiuso; T-P1-05 resta P1 (App. F §F.2).
```

### 0.3 Artefatti correlati (letture FASE 0)

| Path | Ruolo | Letto |
|------|--------|:-----:|
| `scratch/backend_rules.md` | Checklist governance BE (81 item) | ✓ |
| `scratch/frontend_rules.md` | Checklist governance FE (88 item) | ✓ |
| `scratch/infra_rules.md` | Checklist Docker/DB (83 item) | ✓ |
| `scratch/backend_audit.md` | Audit codice BE grezzo | ✓ |
| `scratch/frontend_audit.md` | Audit codice FE grezzo | ✓ |
| `scratch/infra_audit.md` | Audit infra grezzo | ✓ |
| `.agents/AGENTS.md` | Guardrail globali | ✓ |
| `radar/.ecc/rules/{backend,frontend,docker}.md` | SoT path-scoped | ✓ |
| `radar/docs/runbook.md` | Deploy / health / incident | ✓ |
| `radar/.ecc/CLAUDE.md` | Linee guida ECC (T-DOC-01 CLOSED) | ✓ |

---

## 1. Esito lettura FASE 1 — Sintesi Contesto Applicativo

Il **Radar Informativo Globale** è un'applicazione web containerizzata self-hosted e plug-and-play per l'aggregazione e l'arricchimento semantico di feed RSS geopolitici tramite le API di Google Gemini, visualizzati su una mappa 2D interattiva.

### Stack Tecnologico
* **Frontend:** Angular 21 (Standalone Components) con PrimeNG 17+ (per il carosello/calendario) e Leaflet/MarkerCluster per la visualizzazione cartografica.
* **Backend:** FastAPI (Python 3.12-slim) asincrono, adibito esclusivamente a servire le API di lettura (`main.py` API-only).
* **Worker Daemon:** Daemon asincrono Python (`worker.py`) isolato in esecuzione in un loop continuo (polling ogni 15 minuti) per l'ingestione, la sanitizzazione, la classificazione LLM e la scrittura nel Vault.
* **Database:** PostgreSQL 15 (`radar-db`). Tutte le interazioni avvengono tramite il driver asincrono puro `asyncpg` con query SQL raw (senza ORM).
* **Feed RSS Manager:** Miniflux `2.3.2` (pin Compose: `miniflux/miniflux:2.3.2`).

### Isolamento di Rete (Phase 3)
* **`radar-edge`:** `radar-frontend` + `radar-backend`. Il frontend non ha visibilità diretta sul database o su Miniflux.
* **`radar-data`:** `radar-backend`, `radar-worker`, `radar-db`, `radar-miniflux`.

### Contratto API Phase 5 (FASE 1 §1.4)
| Endpoint | Uso FE | Envelope / shape |
|----------|--------|------------------|
| `GET /api/map-summary` | Day view | `MapSummaryRow[]` (aggregato paese×categoria) |
| `GET /api/articles` | Nation open | `{ items, next_cursor, total }` · `limit ≤ 100` |
| FE concat | `getAllArticlesForCountry` | Loop finché `next_cursor == null` |

`MOCK_MODE` deve essere **esplicito** (stesse firme). Nessun fallback silenzioso mock↔live.

### Ordine di autorità SoT (FASE 1 §1.5)
1. Codice Gate Verde in `radar/` (comportamento runtime)
2. `.agents/AGENTS.md` + skill `.agents/skills/**`
3. `radar/.ecc/rules/*.md` + `radar/.ecc/agents/*.md`
4. Mirror `radar/.ecc/skills/*.md` (devono coincidere con `.agents`)
5. Manuale remediation + `scratch/*_audit.md` (evidenza) + questo log (stato ticket)

### Flusso Dati — AS-IS (bug noto T-P0-01) vs target POST-FIX

**Happy path entry nuove (AS-IS = corretto, da non rompere):**
```
[Miniflux] → [radar-worker]
  dedup SQL → sanitize HTML (strip tag; gap img/picture/source = T-P2-02 OPEN)
  → QuotaLedger reserve → Gemini → complete/fail ledger
  → TX article + outbox → vault atomic → outbox completed → mark-read Miniflux
```

**Ramo duplicato — POST-FIX (T-P0-01 DONE, implementato in `worker.py`):**
```
Se già nel DB (Duplicato)
  → leggi article_outbox.status (LEFT JOIN su source_url)
  → completed            → mark-read Miniflux
  → pending/failed/writing → skip + warning; attendi reconcile_outbox
  → NULL (no riga)       → mark-read SOLO se file vault esiste (Path.is_file via to_thread)
  → VIETATO: mark-read se status is None senza vault-check
```

> Design: `audit_remediation_T-P0-01.md` — ADJUST `completed|None` = **REJECT**.  
> Verifica workspace 2026-07-15: codice + `test_worker_gate.py` + pytest 111 + ruff PASS; worker rebuild.

---

## 2. Esito lettura FASE 1 — Invarianti Hard-Stop

1. **Sidebar Freeze:** Divieto di modificare `radar/frontend/src/app/components/radar-sidebar/**` (TS/HTML/SCSS/spec). Conservare `p-carousel` e `document.getElementById('article-card-' + id)`. Vietato `app-article-list`.
2. **Read/unread:** fix solo in `state.service.ts` + `radar-map.component.ts` (`.marker-read`).
3. **API-only Backend Main:** nessun polling ingest in `main.py`; ingest solo in `worker.py`.
4. **No ORM:** solo `asyncpg` / SQL `$n`.
5. **Leaflet:** `angular.json` → `scripts[]` + `window.L` / `getLeaflet()`; solo `import type`.
6. **XSS:** titoli untrusted → `textContent` / DOM API, mai `innerHTML`.
7. **10 Categorie Primarie:** `Nucleare`, `Energia`, `Infrastrutture`, `Geopolitica`, `Economia`, `Tecnologia`, `Spazio`, `Ambiente`, `Salute`, `Sicurezza`.
8. **Reti:** FE mai su `radar-data`; nomi servizio immutabili.
9. **Vault default:** `/app/vault`.
10. **CancelledError:** sempre re-raise; sleep polling **mai** in `finally` di shutdown.

---

## 3. Esito lettura FASE 2 — Tabella Ticket (stato operativo)

### 3.0 Conteggi (post chiusura T-DOC-01 in FASE 0)

| Classe | Count |
|--------|------:|
| P0 OPEN codice | 0 |
| P1 OPEN codice | 1 (T-P1-03, T-P1-01, T-P1-02, T-P1-04 DONE; resta T-P1-05) |
| P2 OPEN codice | 8 |
| Docs OPEN residui | 0 |
| Docs FIXED / non riaprire | 12 (11 storici + T-DOC-01) |
| Aree PASS | 14 |

**Lessico stati:** `OPEN` = da remediation (FASE 3–5); `DONE` = fix+gate ok; `CLOSED` = chiuso senza fix codice (es. docs già allineati). Non usare `TODO`.

### 3.1 Ticket codice / docs

| Ticket ID | Finding | Priorità | File Chiave | Stato | Dipendenze | Sommario |
| :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| **T-P0-01** | BE-AUD-001 | P0 | `backend/app/worker.py` (ramo `is_dup`) | **DONE** | — | Gate outbox completed + vault-check NULL. Test `test_worker_gate.py`. Vedi §8.1 + `audit_remediation_T-P0-01.md`. |
| **T-P0-02** | BE-AUD-005/006 | P0 | `backend/scripts/**` | **DONE** | — | `ClassificationClient()` vuoto + `_wait_for_rate_limit` rimosso. Vedi §14 + `audit_remediation_T-P0-02.md`. |
| **T-P1-01** | BE-AUD-002, INF-AUD-01 | P1 | `core/config.py` (`quote_plus`) + Compose `POSTGRES_HOST` | **DONE** | — | Credenziali encoded via `quote_plus`; niente `DATABASE_URL` grezzo su backend/worker. Vedi §12 + `audit_remediation_T-P1-01.md`. |
| **T-P1-02** | BE-AUD-003 | P1 | `worker.py` | **DONE** | — | Race TOCTOU multi-consumer; pg_advisory_lock per-URL. Vedi §13 + `audit_remediation_T-P1-02.md`. |
| **T-P1-03** | BE-AUD-004 | P1 | `commit/outbox.py` (`reconcile_outbox` + `_update_miniflux_marked_at`) | **DONE** | **T-P0-01** | Mark-read post-`completed` ritentabile via `miniflux_marked_at` (migrazione 008). Vedi §8.2 + `audit_remediation_T-P1-03.md`. |
| **T-P1-04** | FE-AUD-001 | P1 | `state.service.ts`, `app.ts` | **DONE** | — | `detailError` + `error()` merge; catch `closeSidebar(false)` preserva banner. Vedi §15 + `audit_remediation_T-P1-04.md`. |
| **T-P1-05** | INF-AUD-02 | P1 | `frontend/Dockerfile`, `nginx.conf` | OPEN | — | Nginx root / porta 80. Path: USER nginx+8080 **oppure** eccezione SoT in `docker.md`. |
| **T-DOC-01** | Check docs v2.1 | P1 Docs | `radar/.ecc/CLAUDE.md` | **CLOSED** | — | Sintomi legacy (Phase 0–2 / `radar-network`) **non più presenti** su disco (verifica FASE 0). File allineato Gate Verde. |
| **T-P2-01** | BE-AUD-007 | P2 | `classification/validator.py#L227-L231` | OPEN | — | Fallback `'Nessuna'` → `'Nessuno'`. |
| **T-P2-02** | BE-AUD-008 | P2 | `extraction/parser.py#L22-L25` | OPEN | — | Aggiungere `img`/`picture`/`source` a `content_ignored_tags`. |
| **T-P2-03** | BE-AUD-009 | P2 | `classification/validator.py` | OPEN | — | `@model_validator` primo tag == `primary_category`. |
| **T-P2-04** | BE-AUD-010 | P2 | `scripts/diagnostics/test_500_*.py` | OPEN | — | `except:` nudo → `except OSError`. |
| **T-P2-05** | FE-AUD-002 | P2 | `radar-map.component.ts#L148+` | OPEN | — | Rimuovere `UI_OFFSETS` dead. |
| **T-P2-06** | FE-AUD-003 | P2 | `radar-map.component.ts#L456-L494` | OPEN | — | Filtro esplicito `primary_category === cat` su clusterclick. |
| **T-P2-07** | FE-AUD-004 | P2 | `radar-map.component.ts` style | OPEN | — | Stroke GeoJSON via `--color-map-stroke`. |
| **T-P2-08** | FE-AUD-005 | P2 | path FE `shared/directives/` | OPEN | — | Rimuovere dir residua (verificare vuota prima del delete). |

### 3.2 Docs FIXED (non riaprire salvo regressione)

| Ex-ID / Ticket | Nota | Stato |
|----------------|------|--------|
| 1.1–1.3, 2.1–2.4, 3.1–3.5 | Vedi manuale §2.5 | FIXED |
| **T-DOC-01** | `CLAUDE.md` allineato Phase 6 / Gate Verde; grep `radar-network\|Phase 0-2` = 0 match | **CLOSED** (FASE 0 verify 2026-07-15) |

---

## 4. Decisioni su Priorità Elevate (Appendix F §F.2)

* **T-P0-02 (Elevato da P1 a P0 — storico; ticket DONE 2026-07-16):** elevazione motivata da script/live bloccati; chiuso con ibrido+b1. Non riaprire senza regressione.
*   **T-P1-05 (Elevato da P2 a P1):** Hardening produzione (UID 0). Alternativa ammessa: documentare eccezione SoT in `docker.md` → chiusura P2/DONE docs.

---

## 5. Ordine Remediation Previsto

Ordine FASE 4 (T-DOC-01 escluso: già CLOSED):

1. **`T-P0-01`** — Gate duplicato — **DONE**
2. **`T-P1-03`** — Retry mark-read — **DONE**
3. **`T-P1-01`** — `DATABASE_URL` `quote_plus` (+ Compose/`.env`) — **DONE**
4. **`T-P1-02`** — Advisory lock per-URL — **DONE**
5. **`T-P0-02`** — Script diagnostici. — **DONE**
6. **`T-P1-04`** — Banner nation-open / `detailError`.
7. **`T-P1-05`** — Nginx non-root **oppure** eccezione SoT.
8. **P2 in blocco** (`T-P2-01` → `T-P2-08`).

---

## 6. Aree PASS — Non toccare (14/14 da manuale §2.6)

| Area | Verdetto | Evidenza breve |
|------|----------|----------------|
| Sidebar freeze | PASS | `p-carousel`, no `article-list` |
| Leaflet `window.L` | PASS | `getLeaflet()` |
| XSS icons | PASS | `createSafeMarkerIcon` + `textContent` |
| API FE concat cursor | PASS | `getAllArticlesForCountry` |
| Overlay + `invalidateSize` | PASS | App shell 100vw |
| Worker CancelledError / sleep | PASS | `worker.py` |
| QuotaLedger | PASS | reserve/complete/fail |
| Outbox happy path | PASS | TX + vault atomic |
| API Phase 5 BE | PASS | map-summary + envelope |
| Reti edge/data | PASS | Compose |
| Migrazioni 001–007 + indici | PASS | SQL + runner |
| GeoJSON verify in Docker | PASS | Dockerfile FE |
| CMD `app.main:app` | PASS | Dockerfile BE |
| Volume `./data/postgres` | PASS | Compose |

Deferred infra (digest pin, `--legacy-peer-deps`) ≠ FAIL — non aprire ticket (App. F §F.4).

---

## 7. Log FASE 0

### 7.1 Letture e evidenze
* Manuale v2.1→v2.2, scratch×6, AGENTS.md, `.ecc/rules/*`, `runbook.md`, `CLAUDE.md`.
* Spot-check codice (FASE 0 + verifica aggiuntiva): `worker.py` gate T-P0-01 DONE; `config.py` `quote_plus` + Compose `POSTGRES_HOST` (T-P1-01 DONE); `outbox.py` retry `miniflux_marked_at` (T-P1-03 DONE); script diagnostici T-P0-02 DONE; `state.service.ts` / `app.ts` (`detailError`, T-P1-04 **DONE**); Dockerfile/nginx (T-P1-05 OPEN); `CLAUDE.md` Gate Verde (T-DOC-01 CLOSED).
* P2 spot-check: T-P2-01/02/05 CONFIRMED; T-P2-06 WEAK (difesa in profondità); T-P2-08 path residuo da verificare prima del delete.

### 7.2 Multi-agente (FASE 0 iniziale + verifica chiusura)
Sintesi iniziale via tre context mapper (BE / FE / Infra-Docs). UUID storici non usati come audit trail verificabile.

Verifica chiusura FASE 0 (2026-07-15) via tre sotto-agenti readonly dedicati:
1. **Docs consistency** — gap handoff / as-is vs to-be / obblighi §0.x.
2. **Code evidence** — spot-check ticket vs `radar/`; T-DOC-01 DRIFT → CLOSED.
3. **QA processo** — DoD FASE 0, lessico OPEN, checklist.

### 7.3 Chiusura T-DOC-01 (evidenza)
```powershell
Select-String -Path "radar\.ecc\CLAUDE.md" -Pattern "radar-network|Phase 0–2|Phase 0-2|asyncio.sleep\(900\) loop in main"
# Atteso: 0 match — OBSERVED 2026-07-15: 0 match
# File riporta: Phase 0–5 DONE; Phase 6 DONE / GATE VERDE; radar-edge/radar-data; migrazioni 001–007; MOCK_MODE esplicito
```

---

## 8. Log Remediation

### 8.1 T-P0-01 — Gate mark-read duplicato

| Campo | Valore |
|-------|--------|
| Stato | **DONE** — FASE 3/4/5 completate. |
| Report | `audit_remediation_T-P0-01.md` |
| Codice | Gate + vault-check in `radar/backend/app/worker.py` (workspace principale, non solo worktree Antigravity); `tests/test_worker_gate.py` |

**FASE 3 (riproduzione):** CONFIRMED su staging — Miniflux entry `6072` / article `2885` senza outbox → mark-read cieco (log 2026-07-15 18:00:08).

**FASE 4 (design & implementazione):**
- Diff minimo con gate `== "completed"` **IMPLEMENTATO**.
- ADJUST cieco `in ("completed", None)` **RIFIUTATO** (prevenzione silent gaps).
- Implementato Vault-Check per articoli legacy (NULL outbox status): il worker recupera i metadati dell'articolo dal DB, ricostruisce il percorso atteso del Vault tramite `get_article_file_path()` ed esegue `mark_as_read` solo se il file esiste fisicamente sul disco (`asyncio.to_thread` per `Path.is_file()`).
- In caso di outbox `pending`, `failed` o `writing`, il mark-read viene saltato (`skip`) stampando un warning, in attesa che la riconciliazione dell'outbox (`reconcile_outbox`) ne completi l'elaborazione.
- **Handoff T-P1-03:** **SODDISFATTO** — vedi §8.2 / §11 (retry `miniflux_marked_at` + migrazione 008).

**FASE 5 (validazione) — riverifica workspace principale 2026-07-15 ~20:23:**
- `radar/backend/app/tests/test_worker_gate.py` presente in-repo (non solo worktree Antigravity).
- `ruff check` PASS su `worker.py` + `test_worker_gate.py`.
- `pytest backend/app/tests/test_worker_gate.py -v` → **4/4 PASS**.
- `pytest -m "not live" -q` → **111 passed**.
- `docker compose build/up radar-worker` → gate presente nel container (`outbox_status` / vault-check).
- Script G: molte righe `articles` senza outbox (`status` NULL) — atteso legacy; gate le gestisce con vault-check.
- Nota ops: fetch Miniflux può fallire con `MAX_MINIFLUX_RESPONSE_BYTES` (fuori scope T-P0-01).

### 8.2 T-P1-03 — Retry mark-read post-completed

| Campo | Valore |
|-------|--------|
| Stato | **DONE** — FASE 3/4/5 completate. |
| Report | `audit_remediation_T-P1-03.md` |
| Codice | Migrazione 008, helper e query in `radar/backend/app/commit/outbox.py`, test in `tests/test_outbox_mark_read_retry.py` |

**FASE 3 (riproduzione):** CONFIRMED — In caso di errore Miniflux dopo Vault scritto con successo, la riga outbox passava a completed, ma senza retry la riga veniva esclusa dai successivi reconcile (poiché status IN ('pending', 'failed')).

**FASE 4 (design & implementazione):**
- Creata migrazione 008 con aggiunta colonna `miniflux_marked_at` e backfill integrato per gli articoli completed storici.
- Aggiornato `enqueue_outbox_row` per preservare/azzerare `miniflux_marked_at` on conflict.
- Aggiornato `process_outbox_row` per impostare `miniflux_marked_at = NOW()` su successo di mark-read.
- Aggiornato `reconcile_outbox` per effettuare una seconda SELECT che recupera solo le righe completed non marcate in Miniflux ed effettua solo il retry mark-read, senza mai riscrivere il Vault.

**FASE 5 (validazione):**
- Creato `tests/test_outbox_mark_read_retry.py` che valida l'isolamento del Vault durante i retry e la corretta marcatura del timestamp.
- Ruff e pytest not live 113/113 passed.
- Eseguito rebuild di `radar-worker` ed esecuzione migrazione 008 sul DB PostgreSQL verificata con successo.

---

## 9. Checklist FASE 0 (DoD)

- [x] Contesto applicativo + API Phase 5 + ordine autorità SoT documentati
- [x] Invarianti hard-stop (10) con Sidebar Freeze e read/unread separati
- [x] Conteggi pie / matrice FASE 0: 2+5+8 OPEN codice (snapshot storico); **oggi** P0=0 P1=1 P2=8 (post T-P1-04); 0 docs OPEN; 12 FIXED; 14 PASS
- [x] Tabella ticket con finding ID, stato `OPEN`/`CLOSED` (no `TODO`)
- [x] T-DOC-01 CLOSED con evidenza grep su `CLAUDE.md`
- [x] Docs FIXED elencati; regola «non riaprire» esplicita
- [x] Elevazioni T-P0-02 / T-P1-05 motivate (+ path alternativi)
- [x] Dipendenza T-P0-01→T-P1-03 e ordine FASE 4 (senza T-DOC-01)
- [x] Happy path AS-IS vs POST-FIX (niente gate duplicato presentato come attuale)
- [x] Sanitize HTML: gap `img`/`picture`/`source` → T-P2-02 (non come già fatto)
- [x] Contratto LLM F.8 + definizioni P0/P1/P2 congelati
- [x] Artefatti §0.4 inclusi `runbook.md`
- [x] Aree PASS 14/14
- [x] SoT stato ticket dichiarato (questo file §3)
- [x] Log remediation pronto (poi popolato da T-P0-01)
- [x] Nessuna modifica remediation a `radar/**` *durante FASE 0* (remediation codice iniziata dopo)
- [x] Manuale aggiornato a v2.2 per chiusura T-DOC-01 e conteggi

---

## 10. Esito Remediation Ticket T-P0-01

**T-P0-01 DONE — PASS** (verificato nel workspace `Dashboard finance`, non solo nel worktree Antigravity).

- Walkthrough iniziale: **falso positivo** sul tree principale (fix assente); portato qui, testati, worker rebuild.
- Gate: `completed` → mark-read; `pending|failed|writing` → skip; `NULL` → vault `Path.is_file`.
- Gate FASE 5: ruff OK; `test_worker_gate` 4/4; pytest not live 111; container `GATE_PRESENT_IN_CONTAINER=OK`.
- **Handoff (storico):** T-P1-03 — poi chiuso in §11.

---

## 11. Esito Remediation Ticket T-P1-03

**T-P1-03 DONE — PASS_WITH_GAPS chiusi in docs** (verificato nel workspace `Dashboard finance`, non solo nel worktree Antigravity).

- Walkthrough: implementazione migrazione 008, logica `outbox.py` con colonna `miniflux_marked_at` e backfill, test dedicati completati con successo.
- Gate FASE 5 (riverifica Cursor): ruff OK; `test_outbox_mark_read_retry` 2/2; pytest not live 113/113; DB 937/937 completed marked; worker container sync OK.
- Drift docs (conteggi P1, handoff §10, cite linee) allineati post-verifica.
- **Handoff (storico):** **T-P1-01** — poi chiuso in §12.

---

## 12. Esito Remediation Ticket T-P1-01

**T-P1-01 DONE — PASS** (verificato nel workspace `Dashboard finance` e nei container).

- Configurazione: aggiunto `quote_plus` per Postgres user e password in `config.py` per supportare credenziali speciali (es. `@`, `:`, `/`, `#`).
- Compose: rimosso `DATABASE_URL` da `radar-backend` e `radar-worker`, sostituendolo con `POSTGRES_HOST: radar-db`.
- .env.example: rimosso `DATABASE_URL` di default e aggiunta nota di avviso per manual override e Miniflux.
- Gate FASE 5: ruff OK; test `test_database_url.py` 1/1; pytest not live 114/114; Script F superato; container build/up ed esecuzione di printenv confermano che il bypass dell'URL grezzo è rimosso e `POSTGRES_HOST` è configurato.
- Riverifica Cursor: codice/Docker confermati; drift manuale (pie P1, App. D, §4.2) allineato.
- **Handoff:** **T-P1-02** (storico) — poi chiuso in §13.

---

## 13. Esito Remediation Ticket T-P1-02

**T-P1-02 DONE — PASS_WITH_GAPS** (verificato Cursor nel workspace `Dashboard finance`; Docker daemon assente).

- Lock: `pg_advisory_lock` a due argomenti (namespace `777666555` + hash SHA-256 32-bit URL) in `process_single_entry`.
- CancelledError: unlock in `finally` sulla stessa connessione; poi re-raise.
- Concorrenza: `test_worker_concurrency.py` serializza 2 task stesso URL → 1 classify + 1 commit.
- Gate FASE 5 (riverifica): ruff OK; concurrency 1/1; gate 4/4; pytest not live **115/115**.
- Gap: Docker Desktop spento → rebuild/`grep` container **non** riverificabili finché il daemon non riparte.
- Nota design accettata: connessione (+ `db_sem`) tenuta per tutta la classify Gemini (session lock); pool `max_size=10`, entry/db concurrency default 4.
- **Handoff (storico):** T-P0-02 — poi **DONE** in §14. **Prossimo:** T-P1-04.

---

## 14. Esito Remediation Ticket T-P0-02

**T-P0-02 DONE — PASS** (codice/gate orchestratore; SoT drift chiuso in riverifica Cursor 2026-07-16).

- Walkthrough: eliminati gli script diagnostici orfani `test_500.py` e `test_rate_limiter.py` per non interferire con Script I; riparato `test_production_pipeline.py` istanziando `ClassificationClient(quota=quota)` con un `AsyncMock` della quota e rimuovendo lo stress test basato sul vecchio metodo `_wait_for_rate_limit`; configurato skip esplicito per `test_live_rate_limiter_throttling` in `test_integration_live.py`.
- Gate FASE 5 (riverifica Cursor): ruff OK; pytest offline **115 passed** (al close T-P0-02); live throttling **SKIPPED**; Script I **ZERO match**.
- Docs: pie FASE 2 / App. D / prompt F.8 / spot-check allineati post drift.
- **Ops post-verify (2026-07-16):** race `compose restart` → follow-up OPS-FIX `init_pool` retry (+1 test → **116** not live). Vedi App. D + `audit_remediation_T-P0-02.md` §J/J.1. Non parte del diff scripts T-P0-02.
- **Handoff (storico):** **T-P1-04** — poi **DONE** in §15. **Prossimo:** T-P1-05.

---

## 15. Esito Remediation Ticket T-P1-04

**T-P1-04 DONE — PASS** (verificato nel workspace `Dashboard finance`).

- Walkthrough: aggiunto il segnale `detailError` e aggiornato `error` computed in `StateService` per propagare correttamente gli errori di caricamento articoli nazione alla toolbar (banner `apiError`). Aggiornato `App.closeSidebar` per accettare un flag opzionale `clearError` (default `true`) che controlla se ripulire o meno `detailError`.
- Catch `onCountryClick`: modificato per invocare `closeSidebar(false)`, chiudendo e riallineando l'UI senza eliminare l'errore dallo stato (così il banner rosso di errore rimane visibile in toolbar).
- Test: esteso `app.spec.ts` (reject + clear) e **`state.service.spec.ts`** (4 test sul catch reale / `clearError`).
- Gate FASE 5: typecheck verde; unit test **30/30** passed; Script J superato; sidebar freeze rispettato; Docker FE rebuild + smoke re-ingest 5 articoli Miniflux OK.
- **Handoff:** **T-P1-05** (Nginx frontend root).
- Commit: `51225b5` su `refactor/testing`.

