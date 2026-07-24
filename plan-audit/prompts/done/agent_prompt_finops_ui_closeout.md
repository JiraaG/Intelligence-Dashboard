# Agent prompt — FinOps UI closeout (fix residuali + Walkthrough)

> **Stato: ACTIVE** — closeout post-review walkthrough (2026-07-24).  
> **SoT:** [`../../active/plan_impl_finops_ui_metrics.md`](../../active/plan_impl_finops_ui_metrics.md)  
> **Walkthrough da correggere:** [`../../active/walkthrough_finops_ui_metrics.md`](../../active/walkthrough_finops_ui_metrics.md)  
> **Branch:** `feature/upgrades`  
> **Commit:** **VIETATO** (nessun `git commit` / `git push`)

---

## Come usare

1. Nuova chat **Agent** su `feature/upgrades`.
2. Incolla il blocco **PROMPT** sotto.
3. Scope = solo residui review (non rifare W0–W5).
4. A fine: aggiornare il Walkthrough in formato obbligatorio; **non** commitare.

---

## PROMPT (incolla in Agent mode)

```text
# Task — CLOSEOUT FinOps UI: fix residuali review + Walkthrough conforme (NO COMMIT)

## Ruolo
Full-stack Radar (FastAPI + Angular 21). Chiudi i gap emersi dalla review del walkthrough FinOps UI. Non rifare l’intera feature. Nessun git commit / push.

## Contesto (già implementato — NON riscrivere da zero)
L’impl W0–W5 esiste: articles LATERAL, feed_url, summary cost, /api/metrics/status, sidebar FinOps, toolbar STATUS, skills carve-out, Docker mount config, verify_metrics_013 VERDE live.

Reviewer ha dichiarato: GATE sostanzialmente VERDE con riserve. Devi chiudere le riserve sotto.

## Autorità
1. `plan-audit/active/plan_impl_finops_ui_metrics.md`
2. Review findings (obbligatori da fixare — elenco sotto)
3. Skills freeze / api-contract (già aggiornate; tocca solo se il fix cambia contratto)

## VIETATO
- `git commit`, `git push`, amend, `--no-verify`
- `docker compose restart` sull’intero stack (usa `up -d --build` solo se serve rebuild FE/BE)
- `--purge-all` / requeue distruttivo
- Refactor sidebar oltre tweak minimi display-only nel blocco FinOps
- Toccare map legend / worker classify / nuove migrazioni

---

## Fix obbligatori (in ordine)

### F1 — Bug timezone metrics summary
File: `radar/backend/app/main.py` → `_parse_metrics_date_range`

Problema: `RADAR_TIME_ZONE` da config è già un `ZoneInfo`, ma il codice fa `ZoneInfo(RADAR_TIME_ZONE)` → eccezione → fallback silenzioso a `timezone.utc`. Con TZ ≠ UTC la finestra summary è sbagliata.

Fix: usare direttamente `RADAR_TIME_ZONE` (oggetto ZoneInfo) come fa `/api/metrics/status` via `compute_day_window`. Niente doppio wrap. Aggiungi/aggiorna test se esiste coverage date-range.

### F2 — Allineare costo summary al SoT (purpose filter)
File: `radar/backend/app/main.py` → `GET /api/metrics/summary` (e allinea lo SUM costo in `/api/metrics/status` se oggi somma tutto completed)

SoT: costo = completed AND (`purpose LIKE 'classify:%' OR purpose = 'classify_article'`).
Escludere `quality:compare` dal totale USD.

Applica FILTER/WHERE coerente su `total_estimated_cost_usd` / `estimated_cost_usd_today`.
Aggiorna test metrics se presenti.

### F3 — Euristica `level` / `recent_articles` troppo aggressiva
File: `radar/backend/app/main.py` → `GET /api/metrics/status`

Oggi: qualsiasi articolo del giorno con `classified_by_model ≠ primary` OR `was_escalated` → `l1_likely_active` + level giallo. Con COMPLEX attivo resta quasi sempre yellow anche se primary è sano (live: 344/500, non cooling, ma level=fallback_or_escalation per `recent_articles`).

Fix vincolante:
1. `l1_reason=recent_articles` solo se esiste evidenza di **fallback L1** recente (es. `classified_by_model` = primo fallback SIMPLE nella catena), NON per soli articoli COMPLEX/DeepSeek.
2. Escalation COMPLEX può contribuire al giallo solo con segnale dedicato più stretto, es.:
   - primary residual ≤ yellow_band, OPPURE
   - primary cooling / RPD exhausted, OPPURE
   - L1 effettivamente usato (punto 1), OPPURE
   - (opzionale documentato) soft-trim / hibernate path
3. Aggiungi check **heartbeat worker stale** → spingere verso `degraded` (riusa pattern già usato in `/health/ready` / `evaluate_readiness` — senza importare worker). Se heartbeat non leggibile, documenta SKIP nel walkthrough invece di fingere.

Non inventare stato “mid-cascade”; resta euristica DB+env.

### F4 — UI card FinOps (minimo)
File: `radar-sidebar` (html/scss/ts solo carve-out)

1. Mostra badge/riga `was_escalated` (Sì/No) quando il campo è definito.
2. Distingui latenza: `LLM: X ms` vs `Pipeline: Y ms` se entrambi presenti (non un unico numero ambiguo).
3. Niente refactor carousel / ResizeObserver / updateCarouselHeight algorithm.

### F5 — Product docs + DTO opzionale
1. `docs/02_architecture_and_backend.md`: documentare `total_estimated_cost_usd` su summary e endpoint `GET /api/metrics/status` (shape sintetica).
2. `docs/03_frontend_and_ui.md`: nota breve STATUS&COSTI + blocco FinOps sidebar (freeze carve-out).
3. `article.dto.ts`: aggiungere type-guard **opzionali** per i campi FinOps (pattern `is_read`) — non renderli required.
4. Sync mirror skill/api-contract solo se la shape status cambia in modo materialmente diverso da quanto già scritto.

### F6 — Verifica (obbligatoria, onesta)
```bash
cd radar
# pytest mirati
docker compose exec -T radar-backend python -m pytest \
  app/tests/test_metrics_013.py \
  app/tests/test_metrics_status.py \
  app/tests/test_articles_pagination.py \
  app/tests/test_feed_url_resolve.py -q
# oppure pytest host se equivalente

# se hai cambiato BE/FE: rebuild (NO restart-all)
docker compose up -d --build

docker compose exec radar-backend curl -sf http://localhost:8000/health/live
docker compose exec radar-backend curl -s "http://localhost:8000/api/metrics/summary" | head -c 2500
docker compose exec radar-backend curl -s "http://localhost:8000/api/metrics/status" | head -c 2500
```
Assert post-fix:
- summary cost non include (idealmente) quality:compare — o documenta query
- status: con primary sano e senza L1 recente, `level` può essere `nominal` anche se esistono articoli COMPLEX
- nessun commit creato

---

## Deliverable — riscrivi Walkthrough (formato obbligatorio)

Sovrascrivi:
`plan-audit/active/walkthrough_finops_ui_metrics.md`

Usa ESATTAMENTE questi heading:

1. `# Walkthrough — FinOps UI Metrics`
2. `## Meta` — data, branch, HEAD sha (no commit nuovo), onde originali + closeout F1–F6, NO-COMMIT
3. `## Diff summary` — file toccati in questo closeout (+ eventuale `git diff --stat` unstaged)
4. `## Backend changes` — F1 TZ, F2 purpose filter, F3 level/heartbeat; snippet/query reali
5. `## Frontend changes` — was_escalated + latenze separate; DTO opzionali
6. `## Decisioni runtime` — scostamenti SoT residui (max 10)
7. `## Verifica eseguita` — tabella PASS/FAIL/SKIP: pytest, health, summary, status (prima/dopo level se possibile), articles smoke, docs, MOCK_MODE, legend, carousel, commit=nessuno
8. `## Residui / rischi`
9. `## Come riprodurre`
10. `## Open questions for reviewer`

Regole: onesto; no secret .env; in chat finale stampa solo path Walkthrough + 5 bullet esito closeout.

## Output chat finale
- F1–F6 done/skip
- Path Walkthrough
- Conferma esplicita: **nessun commit creato**
```

---

## Post (umano / reviewer)

1. Analizzare il Walkthrough aggiornato.
2. Solo dopo OK esplicito: commit (separato) e eventuale move piano → `complete/`.
