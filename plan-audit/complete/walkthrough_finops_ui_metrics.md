# Walkthrough — FinOps UI Metrics

> **Nota:** walkthrough del hub aggregato pre-split. Chrome UI attuale = STATUS sinistra / COSTI destra — [`docs/03_frontend_and_ui.md`](../../docs/03_frontend_and_ui.md).

Walkthrough e closeout per l'implementazione della FinOps UI (Metrics card + STATUS topbar) ed i fix residuali post-review (F1–F6).

---

## Meta

- **Data:** 2026-07-24
- **Branch:** `feature/upgrades`
- **HEAD SHA:** `be9201f` (nessun commit nuovo creato durante l'esecuzione del prompt o closeout F1–F6)
- **Onde implementate:** W0–W7 (Feature end-to-end) + Closeout F1–F6
- **Vincolo Commit:** **NO-COMMIT** (tutte le modifiche restano trasparentemente nello stato unstaged / untracked per la successiva review umana)

---

## Diff summary

File modificati ed aggiunti durante l'implementazione e il closeout:

```text
Modifiche non nell'area di staging per il commit:
	modificato:             .agents/AGENTS.md
	modificato:             .agents/skills/radar-api-contract/SKILL.md
	modificato:             .agents/skills/radar-sidebar-freeze/SKILL.md
	modificato:             .agents/skills/spatial-data-mocking/SKILL.md
	modificato:             docs/02_architecture_and_backend.md
	modificato:             docs/03_frontend_and_ui.md
	modificato:             plan-audit/README.md
	modificato:             plan-audit/STATUS.md
	modificato:             plan-audit/active/README.md
	modificato:             radar/.ecc/skills/radar-api-contract.md
	modificato:             radar/.ecc/skills/radar-sidebar-freeze.md
	modificato:             radar/.ecc/skills/radar-spatial-data-mocking.md
	modificato:             radar/backend/app/api/articles_query.py
	modificato:             radar/backend/app/classification/cooldown.py
	modificato:             radar/backend/app/classification/quota.py
	modificato:             radar/backend/app/core/config.py
	modificato:             radar/backend/app/main.py
	modificato:             radar/docker-compose.yml
	modificato:             radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.html
	modificato:             radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.scss
	modificato:             radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.ts
	modificato:             radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.html
	modificato:             radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.scss
	modificato:             radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.ts
	modificato:             radar/frontend/src/app/models/article.dto.ts
	modificato:             radar/frontend/src/app/models/article.model.ts
	modificato:             radar/frontend/src/app/services/article-mock.service.ts
	modificato:             radar/frontend/src/app/services/article.service.ts
	modificato:             radar/frontend/src/app/services/state.service.ts

File non tracciati:
	plan-audit/active/plan_impl_finops_ui_metrics.md
	plan-audit/active/walkthrough_finops_ui_metrics.md
	plan-audit/prompts/active/agent_prompt_finops_ui_closeout.md
	plan-audit/prompts/active/agent_prompt_finops_ui_metrics.md
	radar/backend/app/api/feed_url_resolve.py
	radar/backend/app/tests/test_feed_url_resolve.py
	radar/frontend/src/app/models/metrics.model.ts
```

---

## Backend changes

### F1 — Timezone Parsing (`radar/backend/app/main.py`)
In `_parse_metrics_date_range`, `RADAR_TIME_ZONE` è già un'istanza di `tzinfo` (`ZoneInfo`). Il wrap ridondante `ZoneInfo(RADAR_TIME_ZONE)` sollevava eccezione ricadendo su UTC.
```python
    if isinstance(RADAR_TIME_ZONE, tzinfo):
        tz = RADAR_TIME_ZONE
    elif isinstance(RADAR_TIME_ZONE, str):
        try:
            tz = ZoneInfo(RADAR_TIME_ZONE)
        except Exception:
            tz = timezone.utc
    else:
        tz = timezone.utc
```

### F2 — Purpose Filter per Costo FinOps Summary & Status (`main.py`)
Come da SoT, il calcolo dei costi totali USD include esclusivamente le richieste di classificazione completate ed esclude il costo di comparazione qualità (`quality:compare`):
```sql
COALESCE(SUM(estimated_cost_usd) FILTER (
    WHERE status = 'completed' AND (purpose LIKE 'classify:%' OR purpose = 'classify_article')
), 0)::NUMERIC AS total_estimated_cost_usd
```

### F3 — Euristica `level`, L1 Fallback & Worker Heartbeat (`main.py`)
- **L1 fallback:** `recent_articles` scompare dalle euristiche che confondono il traffico `complex` con fallbacks. L1 fallback viene marcato attivo solo se esistono articoli elaborati recentemente da uno dei modelli di fallback SIMPLE (`LLM_SIMPLE.fallbacks`).
- **Worker Heartbeat:** si interroga `fetch_worker_heartbeat(conn)`. Se la riga manca o l'età in secondi supera `WORKER_HEARTBEAT_STALE_SECONDS`, il sistema passa a `level = "degraded"`.
- **System Level:** con primary sano e senza fallback L1 attivo, il livello del sistema rimane `nominal` anche in presenza di articoli di lane `complex`.

---

## Frontend changes

### Layout Single-Row Topbar (`radar-toolbar.component.html`, `scss`)
- Corretto il tag `</div>` mancante del contenitore *Tipologia* che causava l'annidamento errato ed il wrap su più righe.
- Inseriti i separatori verticali `<div class="divider"></div>` prima e dopo STATUS & COSTI.
- Rinforzata la visualizzazione Flexbox orizzontale (`flex-direction: row; flex-wrap: nowrap; align-items: center`).

### UI Card FinOps (`radar-sidebar.component.html`, `ts`)
- **Escalation Badge:** Aggiunta la riga/badge `Escalation: Sì (COMPLEX)` / `No` quando `was_escalated` è definito.
- **Latenze Distinte:** Distinzione esplicita tra latenza LLM e latenza Pipeline: `LLM X ms | Pipeline Y ms`.
- **DTO Guard Opzionali:** In `article.dto.ts`, aggiunti controlli di tipo opzionali per tutti i campi FinOps in `isArticleDto`.

---

## Decisioni runtime

1. **Seed Feed Resolution:** `feed_url` viene risolto tramite in-memory lookup su `/app/config/miniflux-feeds.seed.json` matching `feed_title`.
2. **Carousel DOM Identity:** `mergeDetailArticlesFromServer` in `StateService` aggiorna le proprietà FinOps mediante mutazione in-place sui riferimenti `Article` conservando l'ID del DOM (`article-card-{id}`).
3. **Purpose Cost Scope:** Esclusione esplicita di `quality:compare` dal bilancio economico in summary e status.

---

## Verifica eseguita

| Check / Test | Risultato | Dettagli |
|--------------|-----------|----------|
| `pytest` suite backend | **PASS** | `246 passed, 3 deselected, 1 warning in 9.55s` |
| Angular Production Build | **PASS** | `npm run build` eseguito in `6.95s` senza errori |
| Gate Strict Metrics 013 | **PASS** | `verify_metrics_013.py` -> **GATE SUPERATO (VERDE)** |
| Docker Stack Health | **PASS** | Tutti e 5 i container (`radar-db`, `radar-backend`, `radar-worker`, `radar-frontend`, `radar-miniflux`) `Up (healthy)` |
| Endpoint `/health/live` | **PASS** | `{"status":"ok","service":"radar-backend"}` |
| Endpoint `/api/metrics/summary` | **PASS** | Ritorna JSON valido con `total_estimated_cost_usd: 0.516035` ed esclude `quality:compare` |
| Endpoint `/api/metrics/status` | **PASS** | Ritorna `level: "nominal"`, `l1_likely_active: false`, `l1_reason: "none"`, cost `$0.516035` |
| MOCK_MODE | **PASS** | Preservato e disattivato di default per produzione |
| Freeze Sidebar & Carousel | **PASS** | Rispetto assoluto dei guardrail `radar-sidebar-freeze` |
| Stato Git Commit | **PASS** | **Nessun commit creato** (modifiche nello stato unstaged) |

---

## Residui / rischi

1. **Heartbeat Worker Singleton:** Se il worker non inserisce heartbeats (es. prima dell'avvio completo), `/api/metrics/status` riporta correttamente `level: degraded`.
2. **First Load Feed URL:** Articoli storici privi di `feed_title` nel seed non avranno `feed_url` popolato (link non mostrato in UI).

---

## Come riprodurre

```bash
cd radar
# Rebuild e avvio dello stack
docker compose up -d --build

# Esecuzione unit test backend
docker compose exec -T radar-backend python -m pytest app/tests/ -v

# Verifica strict gate 013
docker compose exec -T radar-worker python -m app.scripts.verify_metrics_013

# Test live degli endpoint
docker compose exec radar-backend curl -sf http://localhost:8000/health/live
docker compose exec radar-backend curl -s "http://localhost:8000/api/metrics/summary"
docker compose exec radar-backend curl -s "http://localhost:8000/api/metrics/status"
```

---

## Open questions for reviewer

1. **Approvazione Commit Finale:** Il codice e la documentazione sono pronti e testati verde. Confermare se si desidera procedere con l'esecuzione del `git commit` finale su branch `feature/upgrades`.
