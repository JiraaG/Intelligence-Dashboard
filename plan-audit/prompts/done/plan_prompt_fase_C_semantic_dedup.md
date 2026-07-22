# Plan prompt — Fase C: Deduplicazione semantica (pgvector / embeddings)

> **Stato: DONE / historical** — piano eseguito; GATE VERDE 2026-07-22.  
> **Blueprint:** [`../../../radar_overview_and_upgrades.md`](../../../radar_overview_and_upgrades.md) §3.C  
> **Quadro:** [`../../STATUS.md`](../../STATUS.md) (C = COMPLETE)  
> **Piano SoT:** [`../../complete/plan_impl_fase_C_semantic_dedup.md`](../../complete/plan_impl_fase_C_semantic_dedup.md)  
> **Data prompt:** 2026-07-21 (archiviato 2026-07-22)  
> **Branch:** `feature/upgrades`  
> **Nota stale blueprint:** overview citava `011_pgvector_dedup.sql` — shipped come `012_pgvector_article_embeddings.sql`.  
> **Parallelo non bloccante:** Wave 2 archi elevate (spike); non mescolare in questo piano.

---

## PROMPT (incolla in Plan mode)

```text
# Task — PIANO ONLY (poi impl): Fase C — Deduplicazione semantica (pgvector / embeddings)

## Ruolo
Architect + pipeline engineer del monorepo Radar Informativo Globale.
Fase 1 (questa chat Plan): ANALISI RIGOROSA + PIANO ESEGUIBILE — **nessun codice** finché il PO non conferma il piano.
Fase 2 (chat Agent successiva, solo dopo ok): implementazione + **chiusura GATE** con verifica/test/Docker/docs come sotto.

## Obiettivo prodotto
Progettare (e poi implementare) la **Fase C** di `radar_overview_and_upgrades.md` §3.C: deduplicazione **semantica** via embeddings + `pgvector`, in **aggiunta** (non sostituzione) alla dedup URL già presente, **prima** della classificazione LLM, per evitare costi/token su pezzi sostanzialmente uguali da feed diversi (UTM, mirror, titoli quasi-identici).

Ambito minimo:
1) Estensione DB `pgvector` + tabella embeddings + indice similarità (HNSW o alternativa giustificata).
2) Innesto worker (dopo URL-dedup / sanitize, prima di classify).
3) Runtime embedding: trade-off sentence-transformers vs Ollama embeddings vs API cloud — **una raccomandazione unica** (Profilo A/B tipico + Profilo F Local-Hybrid).
4) Soglia, finestra temporale (blueprint 48h), testo embedded (titolo vs titolo+summary), comportamento su hit.
5) Backfill opzionale vs solo nuovi; ops Docker (Postgres+vector); test; docs.
6) Fuori scope: Wave 2 archi 3D, Fase D tiles, restyle FE/mappa, sidebar.

## Decisioni bloccate (non riaprire senza evidenza)
- Ingest **solo** in `radar-worker`; `main.py` API-only.
- Dedup URL (`is_article_duplicate` / gate T-P0-01) **resta**; semantica = gate **aggiuntivo** pre-LLM.
- asyncpg puro; **no** ORM/SQLAlchemy.
- Package Python `openai` **vietato** (HTTP embeddings solo via httpx se serve).
- Sidebar freeze: zero tocchi `radar-sidebar/**`.
- Migrazione **dopo** `011_articles_related_countries.sql` → `012_…` (overview `011_pgvector` = **stale**).
- Immagine DB: oggi `postgres:15-alpine` senza vector — decidere path ufficiale pinnato (es. `pgvector/pgvector:pg15`, no `latest`) + impatto volume/backup.
- Indipendente da Phase I map / Wave 2; nessun tocco MapLibre salvo “nessun impatto UI”.

## Contesto obbligatorio (leggere PRIMA)

### Blueprint / quadro / manuale base
- `radar_overview_and_upgrades.md` §3.C (intero) + §1–2 AS-IS + tabella stati §3 (**manuale di partenza** — aggiornare a GATE)
- `plan-audit/STATUS.md`
- `plan-audit/complete/sot_llm_multi_model_fallback.md`
- `plan-audit/complete/plan_impl_fase_A_local_amd_ollama.md` (Ollama host / embed models VERIFY)
- `docs/01_getting_started.md`, `docs/02_architecture_and_backend.md`, `docs/04_ecc_framework.md`
- `README.md` (root) — tabella piani/restore + mappa path
- `radar/docs/runbook.md`, `radar/ops/README.md`, `radar/.env.example`

### Skills / ECC
- `.agents/skills/llm-json-extraction/SKILL.md`
- `.agents/skills/radar-quota-ledger/SKILL.md` (dedup pre-LLM = meno reserve)
- `.agents/skills/radar-docker-ops/SKILL.md` (`up -d` non restart parallelo cieco)
- `.agents/skills/radar-requeue-ops/SKILL.md`
- `.agents/AGENTS.md` §3 dedup pre-LLM + asyncpg
- `radar/.ecc/rules/backend.md`, `docker.md`; `radar/.ecc/CLAUDE.md` skill map
- Default: **no** nuova skill/hook salvo gap enforcement reale; preferire docs + knobs + sync mirror se si tocca skill SoT

### Codice AS-IS
- `radar/backend/app/extraction/state.py` — `is_article_duplicate`
- `radar/backend/app/extraction/entry_validation.py` — URL canonico
- `radar/backend/app/worker.py` — lock URL → dedup → sanitize → classify → commit+outbox
- `radar/backend/app/commit/db_commit.py`, `outbox.py`
- `radar/backend/app/tests/test_worker_gate.py`, `test_database.py`
- `radar/backend/migrations/001`…`011_articles_related_countries.sql`
- `radar/docker-compose.yml` (`radar-db`)
- `radar/backend/app/requirements.txt` (`>=`, non `==`)
- Script ops esistenti: `radar/backend/app/scripts/requeue_articles.py`, `radar/ops/*`

## Domande di analisi (Plan — rispondi tutte)

### A — Problema & metriche
A1. Fallimenti della sola dedup URL (feed seed / RSS.txt).
A2. Definizione duplicato semantico accettabile; rischio FP/FN.
A3. KPI: % skip pre-LLM; latenza embed p95; recall su fixture.

### B — Modello & runtime
B1. sentence-transformers vs Ollama embed vs API cloud.
B2. Dimensione vettore ↔ `vector(N)` SQL.
B3. CPU/VRAM Profilo B vs F.
B4. Raccomandazione unica + fail-open/closed se embed down.

### C — Schema & query
C1. DDL `012_…`, FK, indici, metadata (model_id, text_hash).
C2. Distanza coseno / soglia / env-knob.
C3. Finestra su `embeddings.created_at` vs `articles.published_at`.
C4. Race con `entry_concurrency` + advisory lock URL.

### D — Worker
D1. Sequenza vs sanitize / soft-trim quota.
D2. Su hit: mark-read Miniflux? no outbox? log `near_article_id` + distance?
D3. Persistenza embedding in TX commit vs after-commit.
D4. Interazione requeue / `--purge-all` / vault.

### E — Docker / ops
E1. Immagine pgvector + volume `./data/postgres` + health.
E2. Env `SEMANTIC_DEDUP_*` (enable, threshold, window, model).
E3. Backup/restore con estensione vector.

### F — Test / docs / ECC (piano deve elencare file target)
F1. Fixture near-dup / non-dup; pytest.
F2. Manuali da aggiornare a GATE (lista sotto § Chiusura).
F3. Skill nuova? default no.

## Deliverable Plan (formato)
1. Verdetto AS-IS + stale `011_pgvector`
2. Decisioni prodotto bloccate (tabella)
3. Design schema + flusso worker (mermaid)
4. Scelta runtime embed unica
5. Wave W0–W3 + file target
6. Gate accettazione + rischi FP/FN
7. Fuori scope
8. Path: `plan-audit/active/plan_impl_fase_C_semantic_dedup.md` (+ questo prompt già in `prompts/active/`)
9. **Sezione obbligatoria nel piano:** checklist “Chiusura GATE / verifica / docs” (copia adattata del blocco sotto)

Chiedi conferma PO prima di Agent/implementazione.

────────────────────────────────────────
## Chiusura GATE (obbligatoria in Agent DOPO impl — il piano deve già prevederla)
────────────────────────────────────────

Dopo il codice, **non** dichiarare DONE senza questa sequenza. Preferire `docker compose up -d --build` (depends_on healthy); evitare `compose restart` parallelo su tutto lo stack.

### 1) Verifica & test (script / comandi)
Eseguire e registrare esito nel piano/STATUS:
```bash
# Backend (da radar/)
PYTHONPATH=backend python -m pytest -m "not live" -q
# Se aggiungi test dedicati dedup semantica, includerli esplicitamente (path *.py)

# Opzionale smoke script se il piano ne introduce uno, es.:
# docker compose exec -T radar-worker python -m app.scripts.verify_semantic_dedup --dry-run
# (solo se creato dal piano — non inventare path senza implementarlo)
```
- Unit/integration: near-duplicate → skip classify; non-duplicate → classify+commit.
- Regressione: gate URL-dedup (`test_worker_gate` / `is_article_duplicate`) ancora verde.
- Se migrazione/estensione vector: verifica `CREATE EXTENSION` applicata (`schema_migrations` + `\dx` o query equivalente).

### 2) Docker — rebuild / riavvio servizi
```bash
cd radar
# Se cambia immagine DB (pgvector): pianificare migrazione volume / backup prima
./ops/backup-postgres.sh   # se il piano lo richiede prima del cutover immagine
docker compose up -d --build
docker compose ps
# Health: radar-db / radar-backend / radar-frontend / radar-miniflux healthy; worker running + heartbeat
# Miniflux UI host: solo con overlay lan/hardened (base compose NON pubblica :8080)
```
- Se solo worker/backend cambiano: `up -d --build radar-backend radar-worker` (e db se immagine nuova).
- Log: `docker compose logs --since=5m radar-worker radar-db radar-backend` — no traceback; warning attesi documentati (logs/ permission, scrape 403, quota sleep).

### 3) Verifica elaborazione dati (pipeline OK)
- Worker: ciclo ingest → classify → commit → outbox `completed` → mark-read Miniflux.
- DB: nuovi `articles` + righe `article_embeddings` per gli elaborati (se design lo prevede).
- API: `GET /health/live`, `GET /health/ready`; day-view `GET /api/map-summary?date=…` coerente.
- Contatori: ledger LLM (`llm_request_ledger`) — i near-dup **non** devono generare reserve/complete classify.

### 4) Verifica anti-duplicato semantico (obbligatoria)
Prova controllata (fixture o due entry Miniflux / inject test) con titoli/summary near-duplicate:
1. Primo pezzo → elaborato (LLM + commit + embedding stored).
2. Secondo pezzo (URL diverso, testo semanticamente uguale sopra soglia) → **NON** classify LLM; log chiaro (distance / near_article_id); comportamento Miniflux/outbox come da decisioni piano.
3. Terzo pezzo (testo distinto sotto soglia) → elaborato normalmente.
Documentare comandi usati (pytest e/o script ops e/o insert controllato). **Vietato** dichiarare GATE solo su “typecheck verde”.

### 5) Script ops da prevedere nel piano (creare solo se servono)
Valutare esplicitamente (sì/no + path):
- Smoke verify semantic dedup (dry-run / report ultimi hit)
- Eventuale backfill embeddings su articoli recenti
- Estensione runbook requeue: cosa succede agli embedding su `--purge-all`
Non duplicare `requeue_articles` — estendere docs/skill se il comportamento cambia.

### 6) Aggiornamento manuali / struttura / plan-audit / ECC (obbligatorio a GATE)
Aggiornare **tutti** i SoT rilevanti (lista minima):

| Area | Path |
|------|------|
| Manuale base / blueprint | `radar_overview_and_upgrades.md` §3.C → stato DONE + decisioni finali (soglia, modello, immagine DB); correggere stale `011`→`012` |
| Quadro piani | `plan-audit/STATUS.md` (C COMPLETE + restore SHA); `plan-audit/active/README.md`; `plan-audit/complete/README.md` |
| Piano | spostare `plan_impl_fase_C_semantic_dedup.md` → `plan-audit/complete/`; questo prompt → `prompts/done/` |
| README root | tabella restore + mappa path (embeddings / migrazione 012); nota Miniflux porte se toccata ops |
| Docs operatori | `docs/01_getting_started.md`, `docs/02_architecture_and_backend.md` (dedup URL+semantica, env knobs) |
| Runbook / ops | `radar/docs/runbook.md`, `radar/ops/README.md`, `.env.example` (`SEMANTIC_DEDUP_*`) |
| ECC | `.agents/AGENTS.md` (riga dedup pre-LLM se cambia comportamento); `radar/.ecc/CLAUDE.md` skill map se serve; rules `backend.md`/`docker.md` se immagine DB/knobs; **sync** `.agents/skills` ↔ `radar/.ecc/skills` se si edita SoT skill (`python radar/.ecc/scripts/sync_skills.py --check`) |
| Skill | aggiornare `radar-requeue-ops` / `radar-docker-ops` / `radar-quota-ledger` solo se il comportamento ops cambia; **no** skill nuova di default |

### 7) Commit restore-friendly (solo su richiesta utente)
Messaggio stile:
`feat(worker): semantic dedup via pgvector before LLM classify`
Body: restore-friendly GATE, decisioni chiave (threshold, model, db image), chiude piano Fase C.
Poi commit docs: `docs(plan-audit): record Fase C restore SHA <short>`
Registrare SHA in STATUS + README restore table + overview.

## Repo / branch
- Workspace: Intelligence-Dashboard root
- Branch: `feature/upgrades`
- Plan first; Agent solo dopo conferma; commit/push solo su richiesta esplicita
```

---

## Uso

1. Chat nuova → **Plan mode** → incolla il blocco `PROMPT`.
2. A piano approvato → Agent implementa wave del piano.
3. GATE solo dopo § Chiusura (test + Docker + anti-dup + docs/ECC/plan-audit/overview).
4. Archiviare piano in `complete/`, questo file in `prompts/done/`, aggiornare `STATUS.md`.
