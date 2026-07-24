# Agent prompt — FinOps UI (Metrics card + STATUS topbar) — FULL GATE

> **Stato: ACTIVE** — prompt supersede 2026-07-24 (include rebuild Docker + verify live + Walkthrough).  
> **Piano SoT:** [`../../active/plan_impl_finops_ui_metrics.md`](../../active/plan_impl_finops_ui_metrics.md)  
> **Branch:** `feature/upgrades`  
> **Prerequisito:** Metrics 013 GATE — [`../../complete/plan_impl_fase_metrics_013.md`](../../complete/plan_impl_fase_metrics_013.md)

---

## Come usare

1. Nuova chat **Agent** (non Ask/Plan) su `feature/upgrades`.
2. Incolla **tutto** il blocco PROMPT sotto.
3. L’agent esegue W0→W5, poi rebuild stack, verify API/articoli, Walkthrough.
4. Poi un reviewer analizza `plan-audit/active/walkthrough_finops_ui_metrics.md`.

---

## Verifica del piano interno Cursor (per umano)

Il piano “Implementation Plan — FinOps UI” proposto è **sostanzialmente corretto** vs SoT. Correzioni da rispettare nel prompt:

| Piano interno | Correzione |
|---------------|------------|
| Solo compose mount seed | OK; **solo `radar-backend` è obbligatorio** per `feed_url` (worker opzionale). Path host: `radar/config` → `/app/config` |
| Skill solo `.agents/` | Sync anche mirror `radar/.ecc/skills/` (+ AGENTS freeze) |
| `compose restart` stack | **Vietato** per full refresh — usare `docker compose up -d --build` (depends_on healthy) |
| Requeue implicito | **Non** `--purge-all` di default. Prima verificare articoli già in DB; requeue piccolo solo se denorm/ledger vuoti |
| Sidebar solo html/scss | Consentito helper minimo in `.ts` (`hasFinOps`) — niente logica stato |
| Docs product | Aggiornare anche `docs/02_*` / `docs/03_*` se il contratto cambia |

---

## PROMPT (incolla in Agent mode)

```text
# Task — IMPLEMENTAZIONE END-TO-END: FinOps UI (W0–W5) + Docker rebuild + verify live + Walkthrough

## Ruolo
Full-stack engineer Radar Informativo Globale (FastAPI + Angular 21 + Docker Compose).
Implementa FinOps UI e API di supporto secondo il SoT, poi porta lo stack a funzionare al 100%: rebuild servizi, health, smoke API, verifica campi FinOps su articoli reali, UI MOCK + live, Walkthrough onesto.

## Obiettivo prodotto
1. GET /api/articles espone denorm 013 + LATERAL ledger (classify completed) + feed_url (seed title↔feed_title).
2. GET /api/metrics/summary include llm.total_estimated_cost_usd (completed only).
3. GET /api/metrics/status (Fase 2): level nominal|fallback_or_escalation|degraded, models RPD, cooldowns, l1_reason.
4. FE: blocco FinOps dopo Tag (sidebar carve-out) + STATUS & COSTI in toolbar (costo + tricolore + popover).
5. Bottom legend categorie: ZERO modifiche strutturali.
6. Stack Docker rebuild + verify live che i dati FinOps arrivino agli articoli già elaborati (e, se necessario, a un piccolo requeue NON distruttivo).

## Autorità (SoT vince)
1. `plan-audit/active/plan_impl_finops_ui_metrics.md`
2. Skills: radar-sidebar-freeze, radar-api-contract, radar-quota-ledger, radar-docker-ops, radar-requeue-ops, spatial-data-mocking
3. `.agents/AGENTS.md`, `radar/docs/runbook.md`, `docs/02_*`, `docs/03_*`

Se un Implementation Plan interno Cursor confligge → **SoT vince**.

## Contesto da leggere PRIMA di codare
- `plan-audit/STATUS.md`
- `plan-audit/active/plan_impl_finops_ui_metrics.md`
- `plan-audit/complete/plan_impl_fase_metrics_013.md`
- `plan-audit/complete/plan_impl_per_model_quota.md`
- `plan-audit/complete/sot_llm_multi_model_fallback.md`
- Skills elencate + mirror `radar/.ecc/skills/` dove esistono
- `radar/docker-compose.yml`, `radar/backend/Dockerfile`, `radar/docs/runbook.md`

## Decisioni vincolanti
- Costo card = SUM ledger status=completed AND (purpose LIKE 'classify:%' OR purpose='classify_article'); ESCLUDERE quality:compare
- Modello vincente = articles.classified_by_* / classification_lane
- feed_url = exact match seed.title == articles.feed_title; unresolved → null
- MINIFLUX_FEEDS_SEED_PATH default `/app/config/miniflux-feeds.seed.json`
- Compose: montare `./config:/app/config:ro` su **radar-backend** (worker opzionale)
- Refresh FE metrics = rxResource(date) + reload su SSE article_processed + on popover open; NIENTE setInterval
- Errori metrics NON nel banner errore mappa
- Soft-refresh: MUTARE campi FinOps sulla stessa ref Article in mergeDetailArticlesFromServer
- COMPLEX display: deepseek-v4-flash (non V3)
- Free tier $0 → mostrare $0/gratis
- NO nuove migrazioni; NO tocchi worker classify / llm_lanes (solo lettura) / map legend
- Commit git: SOLO se l’utente lo chiede esplicitamente
- VIETATO `docker compose restart` sull’intero stack (race DB). Usare `up -d --build`. Restart singolo `radar-worker` ok solo post-requeue.

## Onde di implementazione (ordine obbligatorio)

### W0 — Docs/skills
- Ampliare carve-out FinOps in:
  - `.agents/skills/radar-sidebar-freeze/SKILL.md`
  - mirror `radar/.ecc/skills/` se presente
  - `.agents/AGENTS.md` sezione freeze
- Aggiornare `radar-api-contract` (+ mirror): articles FinOps fields, summary cost, /metrics/status
- Aggiornare `spatial-data-mocking` checklist STATUS + FinOps card
- Aggiornare `docs/02_architecture_and_backend.md` e `docs/03_frontend_and_ui.md` in modo minimale

### W1 — BE summary cost
- Fix import RADAR_TIME_ZONE in main.py
- llm.total_estimated_cost_usd su GET /api/metrics/summary (SUM estimated_cost_usd WHERE status=completed nella finestra)

### W2 — BE articles + feed_url
- articles_query: SELECT denorm + LEFT JOIN LATERAL ledger (come SoT §7)
- COUNT query SENZA ledger
- CREATE feed_url_resolve.py; applicare feed_url in get_articles post-fetch
- config.MINIFLUX_FEEDS_SEED_PATH
- docker-compose.yml volume `./config:/app/config:ro` su radar-backend

### W3 — FE models/state
- Article campi FinOps opzionali + metrics.model.ts (MetricsSummary, MetricsStatus)
- article.dto guards opzionali + parseMetrics*
- article.service + article-mock: getMetricsSummary, getMetricsStatus + fixture
- state.service: metricsSummaryResource + metricsStatusResource; SSE reload entrambi; merge FinOps fields

### W4 — FE UI
- radar-toolbar: STATUS & COSTI dopo Tipologia / prima divider NOTIZIE; closeAllPanelsExcept('status'); popover glass esistente
- radar-sidebar: SOLO dopo Tag, single + carousel; SCSS minimo; helper TS display-only ok
- NON toccare p-carousel / updateCarouselHeight algorithm / ResizeObserver

### W5 — Status tricolore
- cooldown.list_active()
- quota helper day-usage pubblico (NO import worker)
- GET /api/metrics/status (algoritmo colori SoT §4.3)
- FE: pallino 🟢🟡🔴 da level + barre RPD nel popover

### Test automatici (dopo codice)
Da `radar/backend` (host venv o `docker compose exec radar-backend`):
```bash
python -m pytest app/tests/test_articles_pagination.py app/tests/test_metrics_013.py app/tests/test_feed_url_resolve.py app/tests/test_metrics_status.py -q
```
Aggiorna/crea i test come da SoT. Tutti PASS prima del rebuild.

---

## W6 — Rebuild Docker stack (obbligatorio per GATE 100%)

Working directory: `radar/`

### 6.1 Rebuild ordinato (NO restart-all)
```bash
cd radar
docker compose up -d --build
docker compose ps
```
Attendi healthy su radar-db, radar-backend, radar-miniflux, radar-frontend.

### 6.2 Health
```bash
docker compose exec radar-backend curl -sf http://localhost:8000/health/live
docker compose exec radar-backend curl -s http://localhost:8000/health/ready || true
```
- live DEVE essere 200.
- ready può essere 503 per 30–90s al boot (heartbeat worker) — NON restartare l’API per questo; ritenta fino a 200 o documenta SKIP con motivo.

### 6.3 Seed path dentro container
```bash
docker compose exec radar-backend ls -la /app/config/miniflux-feeds.seed.json
docker compose exec radar-backend printenv MINIFLUX_FEEDS_SEED_PATH || true
```
Se il file manca → fix volume/path prima di dichiarare GATE.

---

## W7 — Verifica elaborazione articoli + FinOps dati (obbligatorio)

### 7.1 Metrics summary (costo)
```bash
docker compose exec radar-backend curl -s "http://localhost:8000/api/metrics/summary" | head -c 4000
```
Assert: JSON contiene `llm.total_estimated_cost_usd` (number).

### 7.2 Metrics status
```bash
docker compose exec radar-backend curl -s "http://localhost:8000/api/metrics/status" | head -c 4000
```
Assert: `level` ∈ {nominal, fallback_or_escalation, degraded}; `models` array; niente secret.

### 7.3 Articles FinOps fields (dati già elaborati)
Scegli una data con articoli (oggi o da map-summary). Esempio:
```bash
# Adatta DATE e COUNTRY a dati reali presenti
DATE=$(date -u +%F)
docker compose exec radar-backend curl -s "http://localhost:8000/api/map-summary?date=${DATE}" | head -c 2000
# Poi articles per un country presente:
docker compose exec radar-backend curl -s "http://localhost:8000/api/articles?date=${DATE}&country=US&limit=5" | head -c 8000
```
Per almeno 1 item con classificazione, verifica presenza (valore o null esplicito ok se storico pre-linkage):
- classified_by_model, classification_lane, was_escalated
- prompt_tokens / completion_tokens / estimated_cost_usd / llm_execution_time_ms (se ledger linked)
- feed_title e, se title matcha seed, feed_url non null

### 7.4 verify_metrics_013 (sanity pipeline dati)
```bash
docker compose exec -T radar-worker python -m app.scripts.verify_metrics_013
```
Documenta PASS/FAIL.

### 7.5 Requeue — SOLO SE necessario
Se gli articles non hanno denorm/ledger (campi sempre null) E serve prova end-to-end:

1. Skill radar-requeue-ops: **dry-run prima**
```bash
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 10 --dry-run
```
2. Se anteprima OK (e utente non ha vietato mutazioni):
```bash
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 10
docker compose restart radar-worker
```
3. Segui log worker finché processa (eager drain). Poi ripeti 7.3 sugli articoli nuovi.

**VIETATO di default:** `--purge-all` (distruttivo). Usalo SOLO se l’utente lo chiede esplicitamente.

### 7.6 Frontend live
- FE su host `:80` (Nginx). Dopo rebuild, hard refresh browser.
- Apri nazione con articoli → card mostra blocco FinOps sotto Tag.
- Topbar STATUS & COSTI mostra costo + pallino; popover con aggregate + (W5) modelli/RPD.
- Legend bottom invariata; carousel next/prev + altezza ok.

### 7.7 MOCK_MODE (se praticabile senza rompere live)
Se puoi toggle MOCK_MODE in app.config / token senza lasciare il repo rotto: verifica fixture FinOps + STATUS. Altrimenti SKIP con motivo e affidati ai unit/mock service tests.

---

## Anti-pattern (vietati)
- Refactor sidebar oltre carve-out; ResizeObserver; sostituire p-carousel
- Import worker da main.py
- N+1 ledger; ledger nella COUNT
- Soft-refresh replace di tutte le Article ref
- Fallback silenzioso HTTP→mock
- Metriche in bottom legend
- `docker compose restart` su tutto lo stack
- `--purge-all` non richiesto
- Commit non richiesto
- Inventare PASS nel Walkthrough

---

## Deliverable obbligatorio — WALKTHROUGH

Crea:
`plan-audit/active/walkthrough_finops_ui_metrics.md`

Heading obbligatori (esatti):
1. `# Walkthrough — FinOps UI Metrics`
2. `## Meta`
3. `## Diff summary`
4. `## Backend changes`
5. `## Frontend changes`
6. `## Decisioni runtime`
7. `## Verifica eseguita`  ← includi W6/W7 con PASS/FAIL/SKIP per: pytest, compose build, health live/ready, seed path, summary cost, status, articles FinOps fields, verify_metrics_013, requeue (se fatto), UI live, MOCK_MODE, legend, carousel
8. `## Residui / rischi`
9. `## Come riprodurre`
10. `## Open questions for reviewer`

Regole: onesto; path reali; no secret .env; dopo il file, in chat stampa solo path Walkthrough + 5 bullet GATE.

## Output chat finale
- Onde W0–W7 chiuse
- Scostamenti SoT (se esistono)
- Path Walkthrough
- Cosa lasciare al reviewer (me) per analisi walkthrough
```

---

## Post-esecuzione (tu / reviewer)

1. Analizzare `plan-audit/active/walkthrough_finops_ui_metrics.md`.
2. Se GATE verde: spostare piano → `complete/`, prompt → `prompts/done/`, aggiornare STATUS (su richiesta).
3. Commit solo su richiesta esplicita.
