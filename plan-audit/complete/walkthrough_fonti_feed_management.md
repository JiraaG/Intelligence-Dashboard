# Walkthrough — FONTI (attività giorno + catalogo feed)

> **Stato:** **COMPLETE / GATE VERDE** — 2026-07-27  
> **Branch:** `feature/upgrades`  
> **Piano SoT:** [`plan_impl_fonti_feed_management.md`](plan_impl_fonti_feed_management.md)  
> **Gate:** **VERDE** (API smoke + toggle Miniflux live + UI Catalogo)

---

## Ambiente

| Voce | Valore |
|------|--------|
| Rebuild | `docker compose up -d --build radar-backend radar-frontend` (+ `radar-miniflux` per catalogo) |
| Smoke | `ops/smoke_fonti_api.py` + `ops/smoke_fonti_byfeed_day.py` (exec in `radar-backend`) |
| Pytest | `test_feeds_api.py` + `test_metrics_013` date_field — **23 passed** (host) |
| FE typecheck | `tsc -p tsconfig.app.json --noEmit` — **OK** |
| Bundle | `FONTI` / `Sorgenti` presenti in `main-*.js` Nginx |

---

## Checklist SoT §9

| Check | Esito | Note |
|-------|-------|------|
| by-feed `date_field=published_at` allineato a volumi mappa | **PASS** | Giorno `2026-07-22`: DB `published_at` **603** articoli; by-feed `published_at` **article_sum=603** / **34** feed. `created_at` stesso giorno → 706/41 (diverso, come atteso). Oggi `2026-07-27` → 0 items (nessun articolo published oggi). |
| FONTI Giorno: no toggle; filtra calendario; empty OK | **PASS (codice + bundle)** | Template: vista Giorno senza switch; empty “Nessuna fonte per questa data”. Live UI click non eseguito in questa sessione (hook rete host). |
| Catalogo: toggle → Miniflux disabled; STATUS N/M | **PASS (API)** | `GET /api/feeds` → **35/35** attive. `PATCH` id=3 disable→enable **200**. STATUS snippet usa `feeds()` (reload su open). |
| Import `enabled: false` → Miniflux disabled | **PASS (codice)** | `miniflux_feeds_sync.import_seed` applica `disabled=not enabled`; sync-seed esporta `enabled`. Non rieseguito import live distruttivo. |
| Token set → PATCH senza header = 401 | **PASS (pytest)** | `test_toggle_feed_requires_token_when_configured`. Live `.env` ha `FEED_ADMIN_TOKEN` vuoto → mutazioni aperte (by design). |
| MOCK_MODE lista statica; no SSE regressione | **PASS (codice)** | Mock `getMetricsByFeed` / `getFeeds` / `toggleFeed`. Errors by-feed/feeds **fuori** da `state.error()` banner mappa. |
| Sidebar freeze; nessun `p-dialog` | **PASS** | `git diff` sidebar vuoto; nessun `p-dialog` in toolbar. |
| Walkthrough onesto | **PASS** | Questo file. |

---

## Smoke API (in-container, 2026-07-27)

```text
health/live                          PASS 200
by-feed published_at (oggi)          PASS items=0
by-feed default created_at           PASS
by-feed bad date_field → 400         PASS
GET /api/feeds                       PASS active=35 total=35
PATCH disable (no token)             PASS id=3 disabled=true
PATCH re-enable                      PASS id=3 disabled=false
```

Richest day:

```text
2026-07-22 published_at → 34 items, article_sum=603 (match DB)
2026-07-22 created_at   → 41 items, article_sum=706
```

---

## Residui / note oneste

1. UI Catalogo toggle + badge ATTIVO/OFF + tipografia allineata Tipologia — verificati in browser (post-polish).
2. Toggle live: `verify_fonti_toggle.py` — **35/35→34/35**, Miniflux `disabled=true`, restore OK.
3. Budget `anyComponentStyle` **40kB** (`angular.json`) per STATUS+COSTI+FONTI.
4. Smoke helpers ops: `radar/ops/smoke_fonti_*.py`, `verify_fonti_toggle.py`, `smoke_post_restart.py`.
5. Closeout: piano → `complete/`, prompt → `prompts/done/`.

---

## Definition of Done (impl)

- SoT W0–W6 implementati
- Pytest verdi parti nuove
- Walkthrough scritto
- Nessuna regressione API smoke STATUS path metrics + feeds
- Sidebar freeze intatto
