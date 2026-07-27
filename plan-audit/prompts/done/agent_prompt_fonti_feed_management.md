# Agent prompt — FONTI (attività giorno + catalogo feed) — FULL GATE

> **Stato: DONE / GATE VERDE** — 2026-07-27 (archiviato).  
> **Piano SoT:** [`../../complete/plan_impl_fonti_feed_management.md`](../../complete/plan_impl_fonti_feed_management.md)  
> **Branch:** `feature/upgrades`  
> **Prerequisiti:** Metrics 013 GATE; FinOps UI STATUS/COSTI GATE  
> **No Commit:** nessun `git commit` / `git push` senza conferma esplicita dell’utente

---

## Come usare (orchestratore / umano)

1. Nuova chat **Agent** (non Ask/Plan) su branch `feature/upgrades`.
2. Leggere prima [`plan-audit/STATUS.md`](../../STATUS.md) e il piano SoT sopra.
3. Incollare **tutto** il blocco PROMPT sotto.
4. L’agent esegue W0→W6 (impl + rebuild Docker mirato + smoke + Walkthrough).
5. Closeout: aggiornare `plan-audit/STATUS.md` e spostare questo prompt in `prompts/done/` solo a GATE.

---

## PROMPT (incolla in Agent mode)

```text
# Task — IMPLEMENTAZIONE END-TO-END: FONTI topbar (Giorno + Catalogo) + API feeds + by-feed published_at + Walkthrough

## Ruolo
Full-stack engineer Radar Informativo Globale (FastAPI + Angular 21 Standalone + Docker Compose).
Implementi la feature FONTI secondo il SoT plan-audit, poi porti BE/FE a funzionare: rebuild servizi toccati, health, smoke API, UI MOCK + live, Walkthrough onesto.

## Obiettivo prodotto
1. Topbar: nuovo pulsante **FONTI** (stile glass identico a STATUS/COSTI) con due viste:
   - **Giorno** (default): fonti che hanno articoli nella data del calendario toolbar; **nessun toggle**.
   - **Catalogo**: gerarchia publisher → sotto-feed; toggle enable/disable su Miniflux.
2. STATUS: sezione compatta read-only `Sorgenti N/M attive` (+ errori se presenti).
3. Estendere `GET /api/metrics/by-feed` con `date_field=published_at|created_at` (FE Giorno passa sempre `published_at`; default API resta `created_at` per script esistenti).
4. Nuovi endpoint: `GET /api/feeds`, `PATCH /api/feeds/{id}/toggle` (token opzionale).
5. Seed: `enabled` opzionale default true; import/sync rispettano disabled Miniflux.
6. Add nuovi feed: **NON** da UI — resta seed + `./ops/import-miniflux-feeds.sh`; aggiornare docs.
7. Default catalogo: tutti abilitati.

## Autorità (SoT vince)
1. `plan-audit/complete/plan_impl_fonti_feed_management.md`
2. Skills: `radar-api-contract`, `radar-docker-ops`, `radar-sidebar-freeze`, `spatial-data-mocking` (+ mirror `radar/.ecc/skills/` se presente)
3. `.agents/AGENTS.md`, `docs/01_getting_started.md` §6, `docs/02_*`, `docs/03_*`, `radar/ops/README.md`, `radar/docs/runbook.md`

Se un Implementation Plan interno Cursor confligge → **SoT plan-audit vince**.

## Contesto da leggere PRIMA di codare
- `plan-audit/STATUS.md`
- `plan-audit/complete/plan_impl_fonti_feed_management.md`
- `plan-audit/complete/plan_impl_fase_metrics_013.md` (by-feed origin)
- `plan-audit/complete/plan_impl_finops_ui_metrics.md` + `docs/03_frontend_and_ui.md` (pattern STATUS/COSTI)
- `radar/config/miniflux-feeds.seed.json`, `RSS.txt`
- `radar/ops/miniflux_feeds_sync.py`, `radar/ops/import-miniflux-feeds.sh`
- `radar/backend/app/extraction/client.py`, `radar/backend/app/main.py` (`/api/metrics/by-feed`)
- `radar/backend/app/api/feed_url_resolve.py`
- `radar/frontend/src/app/components/radar-toolbar/*`
- `radar/docker-compose.yml` (confermare `./config:/app/config:ro` — NON passare a RW)

## Decisioni vincolanti
- Nome UI: **FONTI** (non RSS/FEED)
- Posizione: `.toolbar-left` **dopo STATUS**, prima del divider verso calendario
- Pattern popover: glass STATUS/COSTI (`role="dialog"`, closeAllPanelsExcept('fonti')); **VIETATO** introdurre `p-dialog`
- Vista Giorno: solo `article_count > 0`; data = `StateService.filters.date`; `date_field=published_at`
- Vista Catalogo: toggle → solo Miniflux `disabled`; **NON** scrivere seed.json; config resta **:ro**
- `FEED_ADMIN_TOKEN` opzionale: se valorizzato, PATCH richiede `X-Feed-Admin-Token`; se vuoto, mutazioni aperte (LAN)
- Seed `enabled` assente = true
- `MOCK_MODE` esplicito; no fallback silenzioso su errore API
- **NO-TOUCH:** `radar-sidebar/**` (freeze), worker classify/LLM lanes, map legend bottom, volume config RW
- **VIETATO** `docker compose restart` sull’intero stack; usare `docker compose up -d --build` sui servizi toccati
- Commit git: SOLO se l’utente lo chiede esplicitamente
- Nessun placeholder TODO/FIXME/pass in codice produzione

## Onde (ordine obbligatorio)

### W0 — Docs / skills / env
- Aggiornare `radar-api-contract` (+ mirror): by-feed `date_field`; GET/PATCH feeds
- `docs/02_architecture_and_backend.md`, `docs/03_frontend_and_ui.md` (FONTI layout)
- `docs/01_getting_started.md` §6 + `radar/ops/README.md`: tabella UI FONTI vs CLI add-feed; FEED_ADMIN_TOKEN; default enabled
- `.env.example`: `FEED_ADMIN_TOKEN=` (commento)

### W1 — by-feed date_field
- `GET /api/metrics/by-feed`: query `date_field`; SQL su `published_at` o `created_at` (finestra half-open TZ come oggi)
- Default API se omesso = `created_at`
- Pytest

### W2 — Miniflux client + /api/feeds
- `MinifluxClient.list_feeds()`, `update_feed(feed_id, *, disabled: bool)` (httpx async, stessi header/retry)
- NEW `radar/backend/app/api/feeds.py`: merge seed RO + live; normalizzazione URL (Guardian); groups by category
- PATCH toggle + gate token
- Register in `main.py` (API-only; no ingest in main)
- Pytest merge/toggle/token

### W3 — Ops enabled sync
- `miniflux_feeds_sync.py`: import applica `disabled=not enabled`; sync live→seed scrive `enabled`
- Non rompere import senza campo `enabled`

### W4 — FE data layer
- Models/DTO parse per FeedsResponse + ByFeed (se manca)
- `article.service` + `article-mock`: `getMetricsByFeed`, `getFeeds`, `toggleFeed`
- `state.service`: resource by-feed legata a `filters.date`; load feeds on FONTI/STATUS need; errori metrics/feeds NON nel banner mappa (stesso pattern COSTI/STATUS)

### W5 — FE UI
- `radar-toolbar`: bottone FONTI + popover Giorno|Catalogo; badge; toggle Catalogo; empty state Giorno
- STATUS: blocco Sorgenti N/M (+ error_count)
- SCSS: riuso token/classi esistenti; JetBrains Mono per URL se mostrati; niente card hero
- Accessibile: header, close, role=dialog, stopPropagation come STATUS

### W6 — Rebuild + verify + Walkthrough
- `docker compose up -d --build` su `radar-backend` e `radar-frontend` (e worker solo se serve client condiviso — di solito no)
- Smoke:
  - `GET /api/metrics/by-feed?from=DATE&to=DATE&date_field=published_at`
  - `GET /api/feeds`
  - `PATCH /api/feeds/{id}/toggle` (con e senza token se testabile)
- UI live: apri FONTI Giorno su data con articoli; Catalogo toggle un feed; verifica Miniflux admin se lan overlay; STATUS N/M
- Scrivi `plan-audit/complete/walkthrough_fonti_feed_management.md` (pass/fail onesto)
- Aggiorna riga in `plan-audit/STATUS.md` (In corso → note impl); NON spostare a complete finché l’utente non chiude il gate

## Fuori scope (non implementare)
- POST create / discover / DELETE feed
- Scrittura seed dal backend / mount RW
- Nuovi publisher oltre seed
- Refactor sidebar / map legend
- Helper `ops/add-feed.sh` (solo se tempo residuo e utente chiede)

## Definition of Done
- SoT §9 checklist soddisfatta
- Pytest verdi sulle parti nuove
- Walkthrough scritto
- Nessuna regressione STATUS/COSTI/mappa
- Sidebar freeze intatto
```

---

## Post-esecuzione (orchestratore)

| Step | Azione |
|------|--------|
| Review | Leggere Walkthrough; smoke manuale FONTI Giorno vs Catalogo |
| Gate | Se verde: spostare piano in `plan-audit/complete/`, prompt in `prompts/done/`, aggiornare `STATUS.md` + `plan-audit/README.md` |
| Restore | Annotare SHA pre-feature su `feature/upgrades` prima del merge se richiesto |
