---
title: Piano commenti codice principiante — Radar
status: execute-p0-p1-p2-done
model: grok-4.5
pipeline: terra-audit → grok-refine → grok-execute
created: 2026-07-17
refined: 2026-07-17
executed_p0: 2026-07-17
executed_p1: 2026-07-17
executed_p2: 2026-07-17
scope: backend-app-prod + frontend-active + ecc-hooks-adapters-sync + ops-sh
exclude: tests, radar-sidebar, migrations-sql, node_modules, data, backups, vault
comment_language: it
behavior_change: false
next: none (campagne commenti P0–P2 chiuse; altri P2 inventario restano opt-in fuori batch)
---

# Piano commenti codice principiante — Radar

## 1. Executive summary
- Audit read-only consolidato su 58 file: 33 backend Python, 17 frontend attivi, 8 ECC/adapters/ops.
- Verdetto AS-IS: la documentazione è buona nei confini architetturali, ma disomogenea nei rami di durata, quote, fallback, lock e stato UI.
- Priorità inventario: 27 P0, 13 P1, 10 P2, 8 skip; nessun file `radar-sidebar/**` è pianificato.
- P0 concentra la spiegazione del perché: lane LLM, ledger, cooldown, outbox, advisory lock, API/worker split, map state e enforcement hook.
- Commenti futuri: soltanto italiano, docstring/JSDoc e commenti esplicativi; nessuna logica, firma, query, configurazione o comportamento cambia.
- I riferimenti SoT devono essere brevi e puntuali; non duplicare AGENTS, runbook o skill nel codice.
- Le discrepanze documento↔codice restano registrate qui: non vanno “risolte” attraverso commenti.
- `testing/leaflet.stub.ts` è escluso come supporto test, nonostante il glob frontend lo intercetti.
- **Refine Grok 4.5:** effort S/M/L definito in §4; P2 condensato in un solo batch opt-in `P2-01` (5 file); gli altri P2 restano in inventario senza batch obbligatorio.
- **Esecuzione P0 (2026-07-17):** `P0-01`…`P0-09` **DONE** (comment-only IT; gate §6 OK; sidebar freeze ok). Vedi §11.
- Residuo: `P1-01`…`P1-03` e `P2-01` solo su richiesta esplicita (§5/§10).

## 2. Matrice SoT → moduli codice e contraddizioni

### Matrice SoT

| SoT | Temi vincolanti da rendere comprensibili | Moduli che devono rifletterli nei commenti |
|---|---|---|
| [`README.md`](../../README.md), [`docs/01_getting_started.md`](../../docs/01_getting_started.md) | Topologia a cinque servizi, env, lifecycle worker, health live/ready | `core/config.py`, `core/llm_lanes.py`, `worker.py`, `main.py`, `core/heartbeat.py` |
| [`docs/02_architecture_and_backend.md`](../../docs/02_architecture_and_backend.md), [`sot_llm_multi_model_fallback.md`](sot_llm_multi_model_fallback.md) | Pipeline ingest, schema strict, lane v2.2, ledger durable, outbox | `extraction/**`, `classification/**`, `commit/**`, `worker.py`, `api/articles_query.py` |
| [`.agents/AGENTS.md`](../../.agents/AGENTS.md), [`radar/.ecc/rules/backend.md`](../../radar/.ecc/rules/backend.md) | Worker-only ingest, asyncpg, quote per lane, retry/cancel, no placeholder | `worker.py`, `main.py`, `classification/quota.py`, `classification/client.py`, `core/**` |
| [`docs/03_frontend_and_ui.md`](../../docs/03_frontend_and_ui.md), [`radar/.ecc/rules/frontend.md`](../../radar/.ecc/rules/frontend.md) | `MOCK_MODE` esplicito, API Phase 5, `detailError`, Leaflet globale, cluster/spiderfy | `app.ts`, `services/**`, `models/**`, `components/radar-map/**`, toolbar |
| Skill `radar-sidebar-freeze`, `radar-api-contract`, `spatial-data-mocking`, `angular-developer` | Freeze carousel/sidebar, DTO FE, map-summary/nation detail, Signals | `state.service.ts`, `app.ts`, `article.service.ts`, `article.dto.ts`, mappa; mai sidebar |
| [`docs/04_ecc_framework.md`](../../docs/04_ecc_framework.md), [`radar/.ecc/CLAUDE.md`](../../radar/.ecc/CLAUDE.md) | SoT/mirror, adapter sottili, hook e skill-map | `radar/.ecc/hooks/*.py`, `.cursor/hooks/*-adapter.py`, `sync_skills.py` |
| [`radar/docs/runbook.md`](../../radar/docs/runbook.md), [`radar/ops/README.md`](../../radar/ops/README.md) | Incident, requeue distruttivo, backup/restore, crash consistency | `scripts/requeue_articles.py`, `commit/outbox.py`, `restore-postgres.sh`, `backup-postgres.sh` |

### Vincoli non negoziabili da citare, non riscrivere

- Sidebar freeze: `radar-sidebar/**`, `p-carousel` e `updateCarouselHeight` restano intatti.
- Ingest solo in `worker.py`; `main.py` resta API-only.
- `MOCK_MODE` è esplicito; fallimento nation-fetch imposta `detailError` e mantiene il banner.
- MarkerCluster: `maxClusterRadius: 40`, `spiderfyOnMaxZoom: false`, runtime via `window.L`.
- Pydantic mantiene CSV `str`; il frontend usa `string[]` soltanto dopo la API.
- Le reti `radar-edge` e `radar-data`, e la differenza live/ready, non vanno reinterpretate.
- Quote: limiti per lane, RPM/TPM attendono la stessa lane, RPD solleva `QuotaDailyExceeded` e abilita residual.
- I nuovi commenti non contengono `TODO`, `FIXME`, `HACK`, placeholder, segreti o comportamenti inventati.

### Contraddizioni e regola di trattamento

#### C-01 — P0 docs/codice: post-hook “fail-closed” contro adapter Cursor advisory

- Fonte: `docs/04_ecc_framework.md:151-159` descrive il post-hook come fail-closed; `.cursor/hooks/post-tool-use-adapter.py:106-119` restituisce sempre exit code `0` e invia il fallimento in `additional_context`.
- Trattamento commenti: distinguere il comportamento del hook diretto (può fallire) da quello effettivo dell'adapter Cursor (avviso non bloccante).
- Azione proibita in questa campagna: modificare adapter, hook, documentazione o policy per renderli coerenti.

#### C-02 — P0 docs/codice: “redaction” dichiarata, blocco input implementato

- Fonte: `radar/.ecc/settings.json:63-78` usa il termine redaction; `radar/.ecc/hooks/pre-tool-use.py:72-77,142-149` rileva il pattern nel payload e termina con errore.
- Trattamento commenti: descrivere che lo scanner blocca l'invocazione con secret nell'input; non dichiarare che oscura output o risposte modello.

#### C-03 — P0 docs/codice: fallback lane e fallback Gemini legacy

- Fonte: `radar/docs/runbook.md:62-75` sintetizza la catena Gemini tramite `GEMINI_MODEL_FALLBACKS`; `core/llm_lanes.py:348-351` dà priorità a `LLM_SIMPLE_FALLBACKS`, anche quando è presente ma vuota.
- Trattamento commenti: spiegare la precedenza reale dei campi lane; non promettere fallback legacy se una variabile lane esplicita lo sopprime.

#### C-04 — P0 docs/codice: distinzione unset/blank delle variabili lane

- Fonte: il SoT dichiara legacy fill-gap quando la chiave lane è assente; `core/llm_lanes.py:107-117,142-156,244-250` tratta alcuni valori blank come default/fallback.
- Trattamento commenti: documentare il percorso concreto della funzione interessata e segnalare la discrepanza; non unificare artificialmente “vuoto” e “assente”.

#### C-05 — P1: lessico Gemini-only contro runtime multi-provider

- Fonte: esempi storici in `radar/.ecc/rules/backend.md:146-162` citano `GEMINI_API_KEY`; `.agents/AGENTS.md:12-18` e `core/llm_lanes.py:27-40` supportano provider per lane.
- Trattamento commenti: usare “chiave della lane configurata” e `LlmLaneConfig`; non trasformare un esempio Gemini in requisito universale.

#### C-06 — P1: inventario ECC V2 non aggiornato

- Fonte: `ecc_deep_dive_analysis_v2.md:375-382` presenta `testing.md` come da aggiungere, mentre `docs/04_ecc_framework.md:32-38` e le regole correnti lo trattano come esistente.
- Trattamento commenti: docs/04 e file correnti prevalgono; il V2 resta descrittivo e non va citato come backlog.

#### C-07 — P1: snapshot prompt e guida mock datati

- Fonte: lo snapshot immutabile in `llm-json-extraction/SKILL.md:153-202` non riporta tutte le istruzioni oggi presenti in `classification/prompts.py:28-29`; `spatial-data-mocking/SKILL.md:339-344` descrive una data mock che il servizio corrente ignora.
- Trattamento commenti: riferirsi al codice e al SoT operativo corrente, poi riportare il drift nel piano; non modificare prompt, mock o skill.

## 3. Standard commento

### Principi di densità

- Commentare invarianti, ordine di durata, motivazione di retry/lock, confini di input non fidato, unità e fallimenti fail-closed/fail-visible.
- Non commentare sintassi ovvia, assegnazioni autoesplicative, nomi di variabili o ogni riga di un ciclo.
- Per un simbolo pubblico, aggiungere o migliorare una docstring/JSDoc se scopo, parametri, return, side-effect o errori non sono già chiari.
- Usare `SoT:` solo per un vincolo significativo e con path breve; non copiare paragrafi dei manuali.
- Correggere un commento già falso solo quando il comportamento effettivo è verificato; non mascherare una contraddizione tra codice e manuale.

### Template Python

```python
"""Descrive lo scopo osservabile in una frase.

Args:
    nome: Significato del parametro e unità o formato, se non ovvi.
Returns:
    Risultato e condizione in cui può essere vuoto.
Raises/Side-effects:
    Eccezioni rilevanti, scritture, attese o mutazioni persistenti.
SoT:
    path/regola pertinente, solo quando l'invariante è vincolata.
"""
```

### Template TypeScript

```typescript
/**
 * Spiega il motivo dell'operazione e l'invariante preservata.
 *
 * @param nome Significato del valore al confine UI/API.
 * @returns Risultato osservabile, se diverso da void.
 * @throws Condizione di errore che il chiamante deve mantenere visibile.
 * @see SoT: path/regola pertinente, se necessario.
 */
```

### Esempi buono/cattivo

**Buono — Python**

```python
async def reserve(self, *, estimated_tokens: int, lane: str) -> int:
    """Riserva capacità sulla lane prima di una chiamata provider.

    Args:
        estimated_tokens: Stima prudente usata per il controllo TPM e budget.
        lane: Lane `simple` o `complex` che possiede i propri contatori.
    Returns:
        Identificatore da completare, fallire o rilasciare sullo stesso record.
    Raises/Side-effects:
        Attende per RPM/TPM o solleva QuotaDailyExceeded per lasciare al chiamante
        il residual cross-lane; inserisce una riga nel ledger.
    SoT:
        .agents/AGENTS.md §3; skill radar-quota-ledger.
    """
```

**Cattivo — Python**

```python
# Riserva i token.
reservation_id = await ledger.reserve(estimated_tokens=estimated_tokens, lane=lane)
```

Il commento cattivo ripete il nome dell'operazione e nasconde la differenza critica tra attesa RPM/TPM e residual RPD.

**Buono — TypeScript**

```typescript
/**
 * Aggiorna ottimisticamente lo stato letto senza rompere le reference detenute
 * dalla sidebar congelata; la sostituzione dell'array riattiva i signal derivati.
 *
 * @param articleId Articolo da sincronizzare con la PATCH API.
 * @param isRead Stato ottimistico richiesto dall'utente.
 * @see SoT: radar-sidebar-freeze; radar/.ecc/rules/frontend.md §2b.
 */
```

**Cattivo — TypeScript**

```typescript
// Imposta lo stato letto dell'articolo.
```

Il commento cattivo non spiega rollback versionato, reference condivise, contatore summary o limite sidebar freeze.

## 4. Inventario file completo

Totali verificati: **27 P0**, **13 P1**, **10 P2**, **8 skip** = **58 entry**.  
`LOC~` è una misura approssimata usata per dimensionare il batch; `—` indica nessun batch di default.

**Legenda effort (per file):**
- `S` ≈ 15–30 min — file corto o già denso; pochi simboli pubblici.
- `M` ≈ 30–90 min — file medio con rami non ovvi (retry, lock, filtri, adapter).
- `L` ≈ 2–4 h — file grande (`worker`, `classification/client`, `quota`, `validator`, `radar-map`).

| path | layer | LOC~ | P0/P1/P2/skip | effort | note SoT e gap da commentare | batch_id |
|---|---:|---:|---|---|---|---|
| `radar/backend/app/__init__.py` | backend root | 8 | P2 | S | Docstring breve già presente; verificare solo che non descriva il package come ingest-only. Prova: `:1-4`. | P2-01 |
| `radar/backend/app/worker.py` | worker/orchestrazione | 742 | P0 | L | Leadership advisory, lock per URL, semafori, dedup→outbox, soft-trim SIMPLE, heartbeat e shutdown. SoT: AGENTS §3, docs/02, quota-ledger. | P0-06 |
| `radar/backend/app/main.py` | API FastAPI | 249 | P0 | M | Lifespan API-only, live vs ready, cursor envelope e PATCH read-status. SoT: docs/02 §health, radar-api-contract. | P0-06 |
| `radar/backend/app/api/__init__.py` | package marker | 1 | skip | S | Marker senza logica pubblica. Prova: file di una riga. | — |
| `radar/backend/app/api/articles_query.py` | API query | 214 | P0 | M | Parametri SQL dinamici, keyset cursor, LATERAL anti-Cartesian e coordinate finite. SoT: radar-api-contract, docs/02 API. | P0-06 |
| `radar/backend/app/classification/__init__.py` | package marker | 1 | skip | S | Marker senza superficie da spiegare. Prova: file di una riga. | — |
| `radar/backend/app/classification/client.py` | classificazione/routing | 995 | P0 | L | Tassonomia errori, Retry-After, chain lane/residual, reserve/complete/fail per tentativo e cooldown. SoT: llm-json-extraction, radar-quota-ledger, SoT LLM. | P0-04 |
| `radar/backend/app/classification/complexity.py` | classificazione/heuristic | 372 | P0 | M | Famiglie G/E/L/X/N, L-sola→SIMPLE, quorum v2.2 e non-IQ. SoT: SoT LLM §4, AGENTS §3. | P0-03 |
| `radar/backend/app/classification/cooldown.py` | classificazione/cooldown | 126 | P1 | M | Storage SQL vs memoria test, UTC, expiry e accesso per provider/modello. SoT: SoT LLM §4.7. | P1-01 |
| `radar/backend/app/classification/deepseek.py` | provider OpenAI-compat | 291 | P0 | M | Payload dialect `deepseek`/`openai`, effort lane, risposta, token e error mapping. SoT: llm-json-extraction, SoT LLM §5. | P0-03 |
| `radar/backend/app/classification/prompts.py` | prompt LLM | 68 | P0 | S | System prompt immutabile, delimitatore `<untrusted_article>` e confine interpolazione. SoT: llm-json-extraction. | P0-03 |
| `radar/backend/app/classification/quota.py` | quota ledger | 529 | P0 | L | Giorno half-open, purpose per lane, spacing monotonic, lock transazionale, reserve/complete/release/fail e budget soft-cap. SoT: radar-quota-ledger. | P0-04 |
| `radar/backend/app/classification/validator.py` | schema/normalizzazione | 440 | P0 | L | Pydantic strict CSV `str`, normalizzazione quirks provider, JSON fence e override Miniflux. SoT: llm-json-extraction, radar-api-contract. | P0-03 |
| `radar/backend/app/commit/__init__.py` | package marker | 1 | skip | S | Marker senza logica. Prova: file di una riga. | — |
| `radar/backend/app/commit/db_commit.py` | commit DB | 128 | P0 | M | Una transazione per articoli/junction/outbox, recupero conflict URL e conversione CSV relazionale. SoT: docs/02 persistence. | P0-05 |
| `radar/backend/app/commit/factory.py` | markdown vault | 93 | P1 | S | YAML representer, truncamento sicuro e frontmatter stabile. SoT: router/outbox e vault. | P1-01 |
| `radar/backend/app/commit/lock.py` | filesystem/vault | 95 | P0 | M | Sidecar permanente, write temp→fsync→replace e chiamata sync da async. SoT: docs/02 persistence, runbook outbox. | P0-05 |
| `radar/backend/app/commit/outbox.py` | durability/outbox | 291 | P0 | L | Checksum, claim/recovery `writing`, vault prima di mark-read e retry Miniflux. SoT: docs/02, runbook outbox. | P0-05 |
| `radar/backend/app/commit/router.py` | vault routing | 119 | P0 | M | Allowlist category/country, filename hash e containment del path vault. SoT: AGENTS §6, docs/02. | P0-05 |
| `radar/backend/app/core/__init__.py` | package marker | 1 | skip | S | Marker senza logica. Prova: file di una riga. | — |
| `radar/backend/app/core/config.py` | configurazione | 346 | P0 | M | Env bounded, default/blank, alias lane, URL DB, limiti worker, CORS e fail-fast production. SoT: docs/01, AGENTS §3. | P0-01 |
| `radar/backend/app/core/database.py` | database bootstrap | 85 | P1 | M | Retry transienti del pool e handoff bootstrap/migrazioni. SoT: docs/01 startup, backend rule. | P1-01 |
| `radar/backend/app/core/heartbeat.py` | health | 140 | P1 | M | UPSERT singleton, freshness timezone-safe e outbox riportato ma non gating. SoT: runbook live/ready. | P1-01 |
| `radar/backend/app/core/llm_lanes.py` | configurazione LLM | 373 | P0 | M | Provider/dialect, env unset/blank, alias legacy, costruzione SIMPLE/COMPLEX e `0=unmanaged`. SoT: SoT LLM §5-6. | P0-01 |
| `radar/backend/app/core/logging.py` | logging | 56 | P2 | S | Già documentato: console-first e fallback se `logs/` non è scrivibile. Prova: docstring/commenti `:1-56`. | P2-01 |
| `radar/backend/app/core/migrations.py` | migrazioni runner | 167 | P1 | M | Discovery checksum, riparazione legacy e branch distruttivo; commentare il motivo, non SQL. SoT: docs/02 persistence. | P1-01 |
| `radar/backend/app/extraction/__init__.py` | package marker | 1 | skip | S | Marker senza logica. Prova: file di una riga. | — |
| `radar/backend/app/extraction/client.py` | Miniflux boundary | 270 | P0 | M | Byte ceiling stream, retry/backoff ownership, isolamento entry e mark-read/refresh. SoT: docs/01 ingest, llm-json-extraction. | P0-02 |
| `radar/backend/app/extraction/entry_validation.py` | input validation | 175 | P0 | M | URL canonico, data, fallback contenuto e entry normalizzata immutabile. SoT: backend rule dedup pre-LLM. | P0-02 |
| `radar/backend/app/extraction/parser.py` | sanitize HTML | 113 | P0 | M | Stack tag ignorati, media purge, byte cap prima del parse e normalizzazione. SoT: AGENTS §2 parser. | P0-02 |
| `radar/backend/app/extraction/state.py` | dedup pre-LLM | 25 | P0 | S | SELECT EXISTS prima della quota/LLM e propagazione errore DB. SoT: AGENTS §3 deduplicazione. | P0-02 |
| `radar/backend/app/scripts/__init__.py` | package marker | 1 | skip | S | Marker senza logica. Prova: file di una riga. | — |
| `radar/backend/app/scripts/requeue_articles.py` | ops/requeue | 158 | P1 | M | Dry-run, ordine distruttivo DB/vault/cooldown e boundary CLI. SoT: radar-requeue-ops, runbook requeue. | P1-03 |
| `radar/frontend/src/app/app.ts` | frontend shell | 181 | P0 | M | Generation token, category-specific carousel, `invalidateSize` prima spiderfy, close error-preserving e auto-read. SoT: frontend rule §2b/§7. | P0-07 |
| `radar/frontend/src/app/app.html` | frontend template | 33 | P2 | S | Struttura leggibile; opt-in fuori batch — solo se emerge un vincolo banner/overlay non ovvio. Prova: sezioni già etichettate `:1-33`. | — |
| `radar/frontend/src/app/app.scss` | frontend shell style | 21 | P2 | S | Layout autoesplicativo; opt-in fuori batch — evitare commenti cosmetici. Prova: `:1-21`. | — |
| `radar/frontend/src/app/app.config.ts` | frontend config | 14 | P1 | S | Rendere esplicito che `MOCK_MODE=false` è una scelta di produzione deliberata. SoT: docs/03 MOCK_MODE. | P1-02 |
| `radar/frontend/src/app/components/radar-map/radar-map.component.ts` | Leaflet/map | 1572 | P0 | L | `window.L`, fingerprint geometry/read state, cluster 40, spiderfy custom, GeoJSON/hatching, day/detail e teardown. SoT: AGENTS §5, frontend rule §7/§10. | P0-08 |
| `radar/frontend/src/app/components/radar-map/radar-map.component.html` | map template | 32 | P2 | S | Solo mount Leaflet imperativo merita contesto breve; non introdurre commenti di markup ovvio. | P2-01 |
| `radar/frontend/src/app/components/radar-map/radar-map.component.scss` | map style | 186 | P2 | S | Spiegare soltanto selettori duali read-state o hatching non deducibili. SoT: frontend rule cluster. | P2-01 |
| `radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.ts` | toolbar | 153 | P1 | M | Fallback paese/flag, normalizzazione date e `null` per filtro vuoto. SoT: docs/03 e API contract. | P1-02 |
| `radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.html` | toolbar template | 84 | P2 | S | Template già sezionato; opt-in fuori batch — non commentare label e binding ovvi. | — |
| `radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.scss` | toolbar style | 546 | P2 | S | Solo `::ng-deep`/overlay PrimeNG merita una motivazione; nessun restyle. | P2-01 |
| `radar/frontend/src/app/models/article.dto.ts` | DTO frontend | 140 | P1 | M | Guard runtime `string[]`, envelope paginato e legacy parser non attivo. SoT: radar-api-contract, docs/03. | P1-02 |
| `radar/frontend/src/app/models/article.model.ts` | modello frontend | 66 | P2 | S | Modello già commentato e tipizzato; opt-in fuori batch — evitare ridondanza. Prova: commenti `:1-66`. | — |
| `radar/frontend/src/app/models/map-summary.model.ts` | DTO summary | 11 | P2 | S | Interfaccia breve e leggibile; opt-in fuori batch. Prova: `:1-11`. | — |
| `radar/frontend/src/app/services/article.service.ts` | API/mock switch | 105 | P1 | M | Mock esplicito, assenza fallback silenzioso, page clamp e concatenazione keyset. SoT: frontend rule §2b, radar-api-contract. | P1-02 |
| `radar/frontend/src/app/services/article-mock.service.ts` | mock offline | 233 | P1 | M | Aggregazione, coordinate pesate, cursor mock e helper legacy. SoT: spatial-data-mocking. | P1-02 |
| `radar/frontend/src/app/services/mock-mode.token.ts` | injection token | 11 | skip | S | Già denso per dimensione e `false` esplicito. Prova: commenti `:3-10`. | — |
| `radar/frontend/src/app/services/state.service.ts` | state Signals | 216 | P0 | M | map-summary, filtri client-side, `detailError`, paginazione nazione, reference sidebar e rollback versionato. SoT: frontend rule §2b/§7. | P0-07 |
| `radar/.ecc/hooks/pre-tool-use.py` | ECC security hook | 155 | P0 | M | Input scan, secret/path/command, host normalizzato e exact/subdomain allowlist. SoT: docs/04 hooks, settings policy. | P0-09 |
| `radar/.ecc/hooks/post-tool-use.py` | ECC lint hook | 211 | P0 | M | Root resolution, write-tool detection, lint per linguaggio, placeholder soft warning e fail diretto. SoT: docs/04; C-01. | P0-09 |
| `radar/.ecc/scripts/sync_skills.py` | ECC sync | 107 | P1 | M | Sync unidirezionale SoT→mirror, overwrite, drift e orphan mirror. SoT: docs/04 sync mirror. | P1-03 |
| `.cursor/hooks/pre-tool-use-adapter.py` | Cursor adapter | 35 | P0 | S | Trasformazione payload e propagazione deny del pre-hook senza duplicare policy. SoT: docs/04 adapter sottile. | P0-09 |
| `.cursor/hooks/post-tool-use-adapter.py` | Cursor adapter | 143 | P0 | M | `additional_context`, timeout e exit `0` advisory nonostante lint fail; trattare C-01. SoT: docs/04 adapter sottile. | P0-09 |
| `radar/ops/_load_dotenv.sh` | ops helper | 28 | skip | S | Parser KEY=VALUE già commentato e limitato; nessun pass di default. Prova: commenti `:1-28`. | — |
| `radar/ops/backup-postgres.sh` | ops backup | 121 | P1 | M | Crash consistency, outbox warning, checksum e retention distruttiva. SoT: ops README backup. | P1-03 |
| `radar/ops/restore-postgres.sh` | ops restore | 138 | P0 | M | Conferma distruttiva, checksum opzionale, stop writer, `pg_restore` nonzero e safety vault. SoT: runbook restore, ops README. | P0-09 |

### Evidenza per P2 e skip

- I package marker sono file di una riga e non hanno API o invarianti da spiegare.
- `core/logging.py:1-56` documenta già console-first e fallback `OSError`; un nuovo pass deve evitare duplicazione.
- `services/mock-mode.token.ts:3-10` esplicita già il default mock e il token injection.
- `ops/_load_dotenv.sh:1-28` contiene commenti sulla lettura sicura di `KEY=VALUE`; il suo contratto non richiede ampliamento.
- **P2 condensato (refine):** solo `P2-01` (5 file) è batch opt-in eseguibile. Gli altri P2 restano in inventario con `batch_id: —` — editabili solo se emerge un gap reale, fuori sequenza obbligatoria.

## 5. Sequenza batch di esecuzione

Ogni batch è comment-only e contiene al massimo cinque file. I P0 rispettano l'ordine: core/config → extraction → classification → commit → worker/API → frontend → ECC/ops.

### P0 — esecuzione prioritaria — **DONE 2026-07-17**

1. **P0-01 — Configurazione lane (2 file, ~M+M):** `core/config.py`, `core/llm_lanes.py`. Stabilire il lessico env e le invarianti per-lane prima dei consumer. ✅
2. **P0-02 — Ingress Miniflux (4 file, ~M+M+M+S):** `extraction/entry_validation.py`, `extraction/parser.py`, `extraction/state.py`, `extraction/client.py`. Documentare confine input, sanitizzazione e dedup prima LLM. ✅
3. **P0-03 — Contratto classificazione (4 file, ~M+S+L+M):** `classification/complexity.py`, `prompts.py`, `validator.py`, `deepseek.py`. Spiegare v2.2, prompt/schema immutabili e dialect provider. ✅
4. **P0-04 — Routing e quota (2 file, ~L+L):** `classification/quota.py`, `classification/client.py`. Esplicitare reservation lifecycle, attesa stessa lane e residual. ✅
5. **P0-05 — Durabilità commit (4 file, ~M+M+L+M):** `commit/db_commit.py`, `lock.py`, `outbox.py`, `router.py`. Rendere leggibile l'ordine DB→vault→mark-read. ✅
6. **P0-06 — Worker e API (3 file, ~L+M+M):** `worker.py`, `main.py`, `api/articles_query.py`. Conservare ownership worker/API e health semantics. ✅
7. **P0-07 — Stato e shell UI (2 file, ~M+M):** `services/state.service.ts`, `app.ts`. Spiegare error visibility, mutazione reference sidebar e sequenza resize/spiderfy. ✅
8. **P0-08 — Mappa Leaflet (1 file, ~L):** `components/radar-map/radar-map.component.ts`. Un file isolato per il volume e le invarianti MarkerCluster. ✅
9. **P0-09 — Enforcement e restore (5 file, ~M+M+S+M+M):** hook pre/post, entrambi gli adapter Cursor, `ops/restore-postgres.sh`. Distinguere il contratto hook diretto dal comportamento adapter advisory. ✅

### P1 — solo dopo i P0 pertinenti

1. **P1-01 — Supporto backend (5 file, ~M+S+M+M+M):** `classification/cooldown.py`, `commit/factory.py`, `core/database.py`, `core/heartbeat.py`, `core/migrations.py`. ✅ (2026-07-17)
2. **P1-02 — Confine dati frontend (5 file, ~S+M+M+M+M):** `app.config.ts`, toolbar TS, `article.dto.ts`, `article.service.ts`, `article-mock.service.ts`. ✅ (2026-07-17)
3. **P1-03 — Ops e sync (3 file, ~M+M+M):** `scripts/requeue_articles.py`, `radar/.ecc/scripts/sync_skills.py`, `ops/backup-postgres.sh`. ✅ (2026-07-17)

### P2 — opt-in, nessun obbligo di edit

1. **P2-01 — Basso valore prioritario (5 file, ~S×5):** `__init__.py` (root app), `core/logging.py`, `radar-map.component.html`, `radar-map.component.scss`, `radar-toolbar.component.scss`. Unico batch P2 eseguibile; solo se serve chiudere gap minimi. ✅ (2026-07-17; `logging.py` skipped — già chiaro)
2. Gli altri P2 (`app.html`, `app.scss`, toolbar HTML, `article.model.ts`, `map-summary.model.ts`) restano in inventario con `batch_id: —` — fuori sequenza obbligatoria.

Le entry skip non ricevono batch salvo errore fattuale dimostrato; anche allora il cambio deve restare comment-only e rientrare nel file già classificato.

## 6. Gate di accettazione per batch e finali

### Gate per ogni batch

1. **Scope:** il batch modifica soltanto i path elencati, con diff limitato a commenti, docstring, JSDoc o whitespace innocuo.
2. **Freeze sidebar:** il comando seguente non deve produrre output:

   ```text
   git diff --stat -- radar/frontend/src/app/components/radar-sidebar/
   ```

3. **No placeholder introdotti:** l'ispezione del diff non deve mostrare nuove righe con `TODO`, `FIXME` o `HACK`.

   ```powershell
   git diff --unified=0 | Select-String '^\+.*\b(TODO|FIXME|HACK)\b'
   ```

   Output atteso: nessuna riga.

4. **Qualità del diff:** `git diff --check` deve terminare senza errori; ogni public `def`/`async def` o metodo/export TypeScript non ovvio del batch ha docstring o JSDoc utile.
5. **Verità dei commenti:** ogni affermazione su quote, provider, retry, health, mock, sidebar o Spiderfy è verificata contro codice e SoT; C-01…C-07 non vengono “corrette” nel codice.

### Gate finali obbligatori

**Backend — cmd.exe**

```cmd
cd /d radar && set "PYTHONPATH=backend" && python -m pytest -m "not live" -q
```

**Backend — PowerShell**

```powershell
Push-Location radar
try {
  $env:PYTHONPATH = 'backend'
  python -m pytest -m "not live" -q
} finally {
  Pop-Location
}
```

**Frontend — cmd.exe**

```cmd
cd /d radar\frontend && npm run typecheck
```

**Frontend — PowerShell**

```powershell
Push-Location radar/frontend
try {
  npm run typecheck
} finally {
  Pop-Location
}
```

**Diff finale**

```text
git diff --check
git diff --stat -- radar/frontend/src/app/components/radar-sidebar/
```

Il secondo comando deve restare vuoto. In caso di failure test/typecheck preesistente, distinguere esplicitamente failure preesistente da regressione del batch e non allargare lo scope per correggerla.

## 7. Rischi e mitigazioni

- **Rumore in review:** molte docstring possono rendere il diff difficile da leggere. Mitigazione: batch piccoli, un obiettivo per batch, P2 opt-in.
- **Drift commento≠codice:** il rischio è massimo in LLM routing, retry, outbox e hook. Mitigazione: commentare solo dopo la lettura del ramo attuale e citare una SoT breve.
- **Manuali in conflitto:** C-01…C-07 possono produrre affermazioni contraddittorie. Mitigazione: registrare il conflitto nel piano e descrivere l'implementazione reale senza cambiare né codice né manuale.
- **Token/context e file grandi:** `classification/client.py`, `worker.py` e `radar-map.component.ts` sono voluminosi. Mitigazione: un file P0 grande per batch dove necessario, checklist della funzione pubblica e diff review immediata.
- **Commenti ridondanti:** template applicato meccanicamente può ripetere nomi e sintassi. Mitigazione: saltare P2/skip e usare il test “spiega perché, non cosa”.
- **Ambiente Windows:** `set PYTHONPATH=...` è sintassi cmd, non PowerShell. Mitigazione: usare le due varianti di gate riportate sopra.
- **Freeze sidebar:** una modifica indiretta alla sidebar invaliderebbe il piano. Mitigazione: comando `git diff --stat` obbligatorio per ogni batch e finale.

## 8. Fuori scope esplicito

- Qualsiasi file in `radar/frontend/src/app/components/radar-sidebar/**`, incluso TS/HTML/SCSS/spec e il comportamento `p-carousel`.
- Test backend, `*.spec.ts` e `radar/frontend/src/app/testing/leaflet.stub.ts`; quest'ultimo è supporto test escluso anche se matcha il glob frontend.
- Migrazioni SQL, schema database, `node_modules`, `dist`, dati PostgreSQL, `radar/backups/`, vault e asset generati.
- Modifiche a comportamento, firme, query SQL, env, dipendenze, Docker/Compose, hook policy, skill, AGENTS, rules, docs SoT, settings o prompt LLM.
- Clone/installazione ECC upstream, uso di CodeWiki come fonte SoT, commit, push, riformattazioni di massa e refactor.
- Qualunque “fix” delle contraddizioni C-01…C-07: sono ticket/documentazione o decisioni funzionali separati.

## 9. Istruzioni per fase 2 — Grok 4.5 refine

**Refine completato (2026-07-17) — non rieseguire.**

- Frontmatter attuale: `status: execute-p0-done` (dopo P0 §11).
- Non avviare un secondo pass di refine salvo richiesta esplicita dell'utente.
- Per l'esecuzione dei commenti residui (P1/P2), usare §10 e i `batch_id` esatti della tabella §4 / sequenza §5.
- Vincoli ancora immutabili: freeze sidebar, C-01…C-07, gate §6, fuori scope §8, esclusione `leaflet.stub.ts`.

## 10. Istruzioni per fase 3 — Grok 4.5 Agent execute

**Esegui solo batch Px; no scope creep.** Usa il `batch_id` esatto dalla tabella §4 (es. `P1-01`, non “tutto il backend”).  
**P0 chiusi** — non rieseguire `P0-01`…`P0-09` salvo richiesta esplicita di ripasso.

1. Prima del batch, rileggi le righe SoT citate nella sua entry e il codice corrente del batch; verifica che nessun cambiamento esterno abbia reso il piano obsoleto.
2. Modifica soltanto i file del batch e soltanto commenti, docstring, JSDoc o whitespace innocuo. Nessuna firma, espressione, query, import, template, stile o configurazione cambia.
3. Commenta in italiano i rami non ovvi: perché esistono, quale invariante preservano, quale side-effect producono e quale SoT li vincola.
4. Non editare mai `radar-sidebar/**`; non introdurre `TODO`, `FIXME`, `HACK`, segreti o placeholder.
5. Se trovi C-01…C-07 o una nuova divergenza codice↔manuale, ferma il relativo commento, riportala all'utente e non risolverla attraverso il batch.
6. Esegui i gate del batch; dopo l'ultimo batch richiesto esegui tutti i gate finali. Un failure preesistente va riportato con evidenza, non corretto fuori scope.
7. Chiudi il batch con un riepilogo: file toccati, funzioni/metodi documentati, gate eseguiti, risultato e conferma esplicita che il diff sidebar è vuoto.

## 11. Log esecuzione P0 (2026-07-17)

| Batch | Esito | Note gate / drift |
|-------|--------|-------------------|
| P0-01 | DONE | pytest `not live` OK; C-03/C-04 documentati (FALLBACKS empty vs legacy; blank≠unset) |
| P0-02 | DONE | pytest OK; nessun C-xx nuovo |
| P0-03 | DONE | pytest OK; C-07 (skill snapshot vs `prompts.py`) segnalato, skill non editata |
| P0-04 | DONE | pytest OK; drift: primo 5xx DeepSeek → `HARD_COOLDOWN` (SoT parlava di 5xx×N); C-03/C-05/C-07 rilevanti |
| P0-05 | DONE | pytest OK |
| P0-06 | DONE | pytest OK; C-05 lessico log «GEMINI» vs gate `LLM_API_KEY` |
| P0-07 | DONE | typecheck OK; sidebar diff vuoto |
| P0-08 | DONE | typecheck OK; drift interno zoom in-place **6** (`clusterclick`) vs **≥5** (`focusAndSpiderfyCategory`); commento stale «cluster balls» corretto |
| P0-09 | DONE | AST equal hook/adapter; C-01 (post fail-closed vs adapter advisory) e C-02 (redaction vs deny) documentati |

**Freeze:** ogni batch ha confermato `git diff --stat -- radar/frontend/src/app/components/radar-sidebar/` vuoto.  
**Working tree:** i file prodotto restano modificati (comment-only) finché l’utente non chiede commit.

## 12. Log esecuzione P1 (parziale)

| Batch | Esito | Note |
|-------|--------|------|
| P1-01 | DONE 2026-07-17 | 5 file supporto; AST equal; pytest `not live` 151 passed; nessun C-xx nuovo |
| P1-02 | DONE 2026-07-17 | typecheck OK; C-07 mock `date` ignorato documentato (skill «data passata→0» ≠ codice) |
| P1-03 | DONE 2026-07-17 | requeue dry-run, sync SoT→mirror, backup crash-consistency; pytest 151; nessun C-xx nuovo |
| P2-01 | DONE 2026-07-17 | minimi: `__init__` non ingest-only; map mount; dual `.marker-read`; toolbar `::ng-deep`. **Skip** `logging.py` |
