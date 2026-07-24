# Piano impl — FinOps UI (Metrics card + STATUS topbar)

> **Stato: ACTIVE** — pronto per implementazione (documento 2026-07-24)  
> **Branch:** `feature/upgrades`  
> **Prompt Agent:** [`../prompts/active/agent_prompt_finops_ui_metrics.md`](../prompts/active/agent_prompt_finops_ui_metrics.md)  
> **Origine analisi:** `.cursor/plans/finops_handoff_review_3859bfae.plan.md`  
> **Prerequisito:** Metrics 013 **GATE VERDE** — [`../complete/plan_impl_fase_metrics_013.md`](../complete/plan_impl_fase_metrics_013.md)  
> **Ops LLM:** SIMPLE primary `gemini-3.5-flash-lite`, L1 `gemini-3.1-flash-lite`, COMPLEX `deepseek-v4-flash` (Profilo A)

---

## 1. Obiettivo prodotto

Chiudere il gap **M15** deferito in Metrics 013: UI FinOps sulla dashboard senza distruggere la mappa 3D-primary.

1. **Card articolo (sidebar):** blocco *ANALISI FINOPS & FONTE RSS* (modello, lane, token, latenza, costo, link XML feed).
2. **Topbar:** hub *STATUS & COSTI* con popover (aggregate giorno + in Fase 2 pallino 🟢/🟡/🔴 da quota/cooldown).
3. **Bottom bar:** resta **solo** legenda categorie (già AS-IS — NO-TOUCH).

---

## 2. Verità AS-IS (correzioni handoff)

| Claim handoff | Realtà codice |
|---------------|---------------|
| Campi denorm su `articles` | **Sì** (013) — ma **non** nel SELECT di `build_articles_page_query` |
| Token/costo sull’articolo | Su `llm_request_ledger` (`estimated_cost_usd` da 012) — serve LATERAL |
| `feed_url` su articles | **No** — risolvere da seed `title` ↔ `feed_title` |
| `/api/metrics/summary` = topbar completa | Solo token/cache/latenza/dedup — **manca** USD e quota/cooldown |
| DeepSeek V3 | **Falso** — COMPLEX = `deepseek-v4-flash` |
| Sidebar FinOps “solo HTML” | Bloccato da **radar-sidebar-freeze** finché non si amplia il carve-out |
| Status “live” = SSE come letto/non letto | **No** — snapshot REST + reload su SSE `article_processed` / open popover |

---

## 3. Decisioni chiuse

1. **Fase 1** = valore UI (articles FinOps + summary cost + topbar aggregate + card). **Fase 2** = `GET /api/metrics/status` + tricolore.
2. Costo card = `SUM` ledger `status='completed'` AND (`purpose LIKE 'classify:%'` OR `purpose='classify_article'`). Escludere `quality:compare`.
3. Modello/lane vincente = denorm `articles.classified_by_*` / `classification_lane` (non “best ledger row”).
4. `feed_url` = match esatto seed `title` → `articles.feed_title`; unresolved → `null`. Seed montato/copiato nell’API container (`MINIFLUX_FEEDS_SEED_PATH`).
5. Refresh status FE = `rxResource` su data calendario + `reload()` su SSE `article_processed` + refresh on popover open. **Niente `setInterval`.**
6. L1 “attivo” = euristica (`primary_cooldown` | `primary_rpd_exhausted` | `recent_articles`) — documentare `l1_reason`.
7. Errori metrics **non** entrano nel banner errore mappa.
8. Soft-refresh: **mutare** campi FinOps sulla stessa ref `Article` in `mergeDetailArticlesFromServer`.
9. Worker / migrazioni nuove / map legend = **NO-TOUCH**.
10. Free tier (`usd_per_1m=0`) → UI mostra `$0` / gratis, non “N/D”.

---

## 4. Contratto API target

### 4.1 `GET /api/articles` (envelope invariato)

Nuovi campi **opzionali** per item (null se assenti):

- Denorm: `feed_id`, `feed_domain`, `classification_lane`, `classified_by_model`, `classified_by_provider`, `was_escalated`, `pipeline_latency_ms`, `embedding_time_ms`, `clean_text_chars`, `clean_text_words`
- Ledger LATERAL: `prompt_tokens`, `completion_tokens`, `cached_prompt_tokens`, `estimated_cost_usd`, `llm_execution_time_ms`, `llm_request_count`
- Risolto: `feed_url`

COUNT query **senza** join ledger.

### 4.2 `GET /api/metrics/summary`

Aggiungere `llm.total_estimated_cost_usd` = SUM `estimated_cost_usd` dove `status='completed'` nella finestra.

Fix collaterale: import `RADAR_TIME_ZONE` in `main.py` se ancora mancante.

### 4.3 `GET /api/metrics/status` (Fase 2)

Snapshot giorno corrente (`RADAR_TIME_ZONE`):

```json
{
  "as_of": "...",
  "timezone": "...",
  "level": "nominal|fallback_or_escalation|degraded",
  "estimated_cost_usd_today": 0.0,
  "l1_likely_active": false,
  "l1_reason": "none|primary_cooldown|primary_rpd_exhausted|recent_articles",
  "models": [
    {
      "role": "primary|fallback|complex",
      "lane": "simple|complex",
      "provider": "gemini",
      "model": "gemini-3.5-flash-lite",
      "rpd_used": 0,
      "rpd_limit": 500,
      "cooling_down": false,
      "cooldown_until": null
    }
  ],
  "llm": { "/* aggregate day come summary */": true }
}
```

**Colori:**

- **nominal:** heartbeat fresco; primary non cooling; residual primary sopra banda gialla (`max(50, 0.20*rpd)` se `rpd>0`; `rpd=0` unmanaged = ok)
- **fallback_or_escalation:** primary cooling / residual ≤ banda / L1 likely / soft-trim shrink / COMPLEX residual-only bypass
- **degraded:** hibernate worker (`¬simple_ok ∧ ¬complex_bypass`) / tutta catena cooling / heartbeat stale

Riuso: `compute_day_window`, SQL RPD come `_ledger_model_rpd_used` (helper in `quota.py`, **non** import worker), `limits_for_model`, `ModelCooldownStore.list_active()`.

---

## 5. Matrice file

### Backend

| Path | Azione |
|------|--------|
| `radar/backend/app/api/articles_query.py` | MODIFY — denorm + LATERAL ledger |
| `radar/backend/app/main.py` | MODIFY — cost summary; `/api/metrics/status`; fix TZ import |
| `radar/backend/app/api/feed_url_resolve.py` | CREATE |
| `radar/backend/app/classification/cooldown.py` | MODIFY — `list_active()` |
| `radar/backend/app/classification/quota.py` | MODIFY — helper day-usage pubblico |
| `radar/backend/app/core/config.py` | MODIFY — `MINIFLUX_FEEDS_SEED_PATH` |
| `radar/backend/Dockerfile` / compose | MODIFY — mount/COPY seed |
| `radar/backend/app/worker.py`, `llm_lanes.py`, migrations | NO-TOUCH |
| `radar/backend/app/tests/test_articles_pagination.py` | MODIFY |
| `radar/backend/app/tests/test_metrics_013.py` | MODIFY |
| `radar/backend/app/tests/test_feed_url_resolve.py` | CREATE |
| `radar/backend/app/tests/test_metrics_status.py` | CREATE (o fold) |

### Frontend

| Path | Azione |
|------|--------|
| `radar/frontend/src/app/models/article.model.ts` | MODIFY — campi FinOps opzionali |
| `radar/frontend/src/app/models/metrics.model.ts` | CREATE (alt. nello stesso model) |
| `radar/frontend/src/app/models/article.dto.ts` | MODIFY — guard opzionali + parse metrics |
| `radar/frontend/src/app/services/article.service.ts` | MODIFY — getMetricsSummary/Status |
| `radar/frontend/src/app/services/article-mock.service.ts` | MODIFY — fixture + mock |
| `radar/frontend/src/app/services/state.service.ts` | MODIFY — rxResource + SSE reload + merge |
| `radar/frontend/src/app/components/radar-toolbar/*` | MODIFY — STATUS&COSTI |
| `radar/frontend/src/app/components/radar-sidebar/*` | MODIFY **carve-out** — sezione dopo Tag ×2 |
| `radar/frontend/src/app/components/radar-map/**` | NO-TOUCH |

### Docs / skill

| Path | Azione |
|------|--------|
| `.agents/skills/radar-sidebar-freeze/SKILL.md` (+ mirror `.ecc`) | Carve-out FinOps dopo Tag |
| `.agents/skills/radar-api-contract/SKILL.md` (+ mirror) | Articles FinOps + cost + status |
| `.agents/skills/spatial-data-mocking/SKILL.md` | Checklist STATUS + card |
| `.agents/AGENTS.md` freeze section | Stessa eccezione |
| `docs/02_architecture_and_backend.md`, `docs/03_frontend_and_ui.md` | Documentare |

---

## 6. UX placement

```text
TOPBAR: [Date] [Sentiment] [Tipologia] | [STATUS & COSTI: $x.xx 🟢▾] | [LETTE] [SALVATE] [RELAZIONI]
MAP: full-bleed
SIDEBAR card: … Paesi correlati → Tag → [FINOPS BLOCK] → (carousel chrome)
BOTTOM: category legend only @ bottom:20px
```

Card FinOps: pattern `.badge-section`; link **XML Feed** (non riduplicare “Leggi fonte”).  
Toolbar: riuso `.article-count-container` + `.countries-tooltip.filter-tooltip`; estendere `closeAllPanelsExcept('status')`.

---

## 7. SQL LATERAL (sketch)

```sql
LEFT JOIN LATERAL (
  SELECT
    COALESCE(SUM(l.prompt_tokens), 0)::BIGINT AS prompt_tokens,
    COALESCE(SUM(l.completion_tokens), 0)::BIGINT AS completion_tokens,
    COALESCE(SUM(l.cached_prompt_tokens), 0)::BIGINT AS cached_prompt_tokens,
    COALESCE(SUM(l.estimated_cost_usd), 0)::NUMERIC AS estimated_cost_usd,
    AVG(l.execution_time_ms)::FLOAT AS llm_execution_time_ms,
    COUNT(*)::INT AS llm_request_count
  FROM llm_request_ledger l
  WHERE l.article_id = a.id
    AND l.status = 'completed'
    AND (l.purpose LIKE 'classify:%' OR l.purpose = 'classify_article')
) llm ON TRUE
```

---

## 8. Onde di lavoro

| Wave | Contenuto | Gate |
|------|-----------|------|
| **W0** | Carve-out freeze + api-contract + spatial-mocking notes | Skill aggiornate; nessun codice FE freeze-illegal |
| **W1** | BE: TZ fix + `total_estimated_cost_usd` summary | curl summary ha costo; pytest metrics |
| **W2** | BE: articles denorm + LATERAL + feed_url + Docker seed | GET articles ha campi; test pagination |
| **W3** | FE: model/DTO/mock + StateService resource + SSE reload + merge | MOCK_MODE OK; soft-refresh non rompe identity |
| **W4** | FE: toolbar STATUS (summary) + sidebar FinOps block | UI visibile; legend invariata |
| **W5** | BE+FE: `/api/metrics/status` + tricolore + barre RPD | level coerente con cooldown/RPD test |

Commit: solo se richiesto esplicitamente dall’utente.

---

## 9. Rischi / attenzioni

1. Sidebar freeze — diff minimo, solo dopo Tag.
2. N+1 — una LATERAL per pagina, mai loop Python.
3. COUNT senza ledger.
4. DTO FinOps **opzionali** finché BE+FE non shippano insieme.
5. Seed assente nel container → `feed_url` sempre null.
6. Soft-refresh replace di tutte le ref Article = anti-pattern (api-contract).
7. Non importare `worker` da `main.py`.
8. RPM spacing in-process non è esponibile come “sleeping now”.
9. `article_id` NULL su ledger vecchio → card senza token (ok).
10. Bottom legend — regression only, zero feature.

---

## 10. GATE chiusura

- [ ] W0–W5 done (o W0–W4 se Fase 2 deferita esplicitamente)
- [ ] pytest BE rilevanti verdi
- [ ] MOCK_MODE: STATUS + FinOps card da fixture
- [ ] Live: articolo reale con denorm + costo; summary con USD; (F2) status level
- [ ] Legenda bottom invariata
- [ ] Walkthrough scritto (vedi prompt Agent § Walkthrough)
- [ ] Piano → `complete/`; prompt → `prompts/done/`; aggiornare `STATUS.md`

---

## 11. Fuori scope

Tabella `feeds` normalizzata; pricing prompt/completion multi-tier; nuovo canale SSE solo-status; polling interval; restyle carousel; nuove categorie geopolitiche; tocchi worker classify.
