# Agent prompt — Metrics 013 GATE closeout (YELLOW → GREEN)

> **Stato: ACTIVE** — remediation post-audit 2026-07-22.  
> **Contesto:** impl Metrics 013 già shipped ma GATE **YELLOW** (non 100%).  
> **SoT:** [`../../active/plan_impl_fase_metrics_013.md`](../../active/plan_impl_fase_metrics_013.md)  
> **Prompt impl originale:** [`agent_prompt_fase_metrics_013.md`](agent_prompt_fase_metrics_013.md)  
> **Branch:** `feature/upgrades`

---

## Come usare

1. Nuova chat **Agent** su `feature/upgrades`.
2. Incolla il blocco **PROMPT** sotto.
3. Non rifare W1–W3 da zero: codice base c’è; chiudi gap + prova live + stringi verify.

---

## PROMPT (incolla in Agent mode)

```text
# Task — Metrics 013 GATE closeout (YELLOW → GREEN)

## Ruolo
Pipeline engineer Radar. L’impl Metrics 013 esiste già ma l’audit Grok ha dichiarato **GATE YELLOW**, non verde. Chiudi i gap, esegui test scripting + elaborazione articoli live, dimostra evidenza SQL/API, poi commit + chiusura plan-audit.

## Verdetto audit (punto di partenza — non contestare senza nuova evidenza)

FUNZIONA (non rifare):
- Migration `013_metrics_and_feed_tracking.sql` applicata
- `ClassificationResult`, reserve `miniflux_entry_id`, FinOps token split, link post-commit `article_id`
- Path URL `record_dedup_event(url_exact)` presente in codice
- API `/api/metrics/summary|by-feed|dedup`
- ~50 articoli post-013 con denorm + ledger linkati; Docker healthy; worker senza ERROR recenti
- pytest collection ~229 `not live` (ri-eseguire per conferma)

GAP da chiudere (obbligatori):
1. **BLOCKER:** live `url_exact_count = 0` — SoT richiede ≥1 (meglio ≥2). Codice OK, prova live mancante.
2. **ALTO:** `verify_metrics_013.py` troppo soft (schema + lane>0 = “GATE VERDE”). Allineare a SoT §8.
3. **MEDIO:** happy path commit lascia `dedup_kind`/`dedup_action` = NULL invece di `none` / `inserted_new` (C5). Vedi `worker.py` ~650–652.
4. **MEDIO:** C8 test incompleti — `test_worker_gate` non asserta URL event; commit tests non lockano denorm.
5. **BASSO (opz. in questo closeout):** `resolve_geo_method` non emette `unchanged`; euristica semplificata. Fix se banale, altrimenti nota GATE.
6. **PROCESSO:** plan-audit ancora ACTIVE; checklist §10 non chiusa; walkthrough “GATE green” era overclaim.

## Autorità
1. `plan-audit/active/plan_impl_fase_metrics_013.md` §5–§8–§10
2. C1–C8 in `plan-audit/prompts/active/agent_prompt_fase_metrics_013.md`
3. Questo prompt = delta remediation (priorità sui gap sopra)
4. Skills: `radar-requeue-ops`, `radar-docker-ops`, `radar-api-contract`, `radar-quota-ledger`
5. Sidebar freeze; no UI FinOps; no `--purge-all` salvo richiesta esplicita; non stageare `.env`

## Lavoro codice (prima dei live test)

### Fix A — happy path denorm dedup (C5)
In `worker.py` path insert normale (no semantic candidate):
- `dedup_kind = "none"` (non None)
- `dedup_action = "inserted_new"` (non None)
- `dedup_match_article_id = None`
Allinea anche eventuali path keep_new se serve coerenza enum.

### Fix B — stringere `verify_metrics_013.py`
Deve FALLIRE (exit 1) se manca uno di:
- ≥12 articoli con `classification_lane` NOT NULL **e** `pipeline_latency_ms` > 0 **e** `classified_by_model` NOT NULL (finestra recente o post-013: documenta criterio, es. `created_at` ultime 24h o da start migrazione)
- NULL-rate su quel subset: `feed_id` / `classified_by_model` / ledger link via `article_id` tipicamente <~5% (o soglia documentata)
- ≥1 `article_dedup_events` con `dedup_kind='url_exact'` e `action_taken='kept_existing'` e `cosine_distance IS NULL`
- Opz. forte: curl/httpx interno summary vs SQL counts (tolleranza 0) su `from=today&to=today` (tz RADAR_TIME_ZONE)
- Schema checks già presenti restano
Non stampare “GATE SUPERATO (VERDE)” se url_exact=0.

### Fix C — pytest C8
- Test worker URL-dup: mock `is_article_duplicate=True` + SELECT row con id → assert `record_dedup_event` chiamato con `url_exact` / `kept_existing` / `cosine_distance=None`
- Test commit: INSERT denorm include `dedup_kind='none'`, `dedup_action='inserted_new'`, feed_id, classification_* 
- Estendi `test_metrics_013.py` se utile (API empty + validation già ok)
- `pytest -m "not live"` deve restare verde

### Fix D (opz.)
- `resolve_geo_method`: documenta o aggiungi ramo `unchanged` se applicabile senza over-engineer
- Semantic events post-013 devono popolare `action_taken`/`feed_id`/`incoming_miniflux_entry_id` (verifica path già strumentati)

## Test scripting + elaborazione articoli (obbligatorio, in ordine)

Usa `required_permissions: ["all"]` per docker. Preferisci `docker compose up -d --build` se hai cambiato codice; altrimenti recreate worker.

### T0 — baseline
```bash
cd radar
docker compose ps
docker compose exec -T radar-worker python -m app.scripts.verify_metrics_013   # può essere ROSSO finché url_exact=0 — ok pre-fix
curl -sS "http://localhost/api/metrics/summary" | head -c 2000
curl -sS "http://localhost/api/metrics/dedup" | head -c 2000
```
Registra `url_exact_count` attuale (atteso 0).

### T1 — unit
```bash
cd radar/backend   # o via container se è il modo SoT del repo
# preferisci: docker compose exec -T radar-worker pytest -m "not live" -q
# oppure .venv locale se allineato
```
PASS richiesto prima del live.

### T2 — rebuild se codice cambiato
```bash
cd radar && docker compose up -d --build
# attendi healthy; conferma 013 in schema_migrations
```

### T3 — batch classify / denorm (≥12)
```bash
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 15 --dry-run
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 15
```
Attendi ciclo worker (log: classify OK / commit). Poi SQL:
```sql
-- articoli recenti con denorm
SELECT COUNT(*) FILTER (WHERE classification_lane IS NOT NULL) AS with_lane,
       COUNT(*) FILTER (WHERE classification_lane IS NOT NULL AND pipeline_latency_ms > 0) AS with_latency,
       COUNT(*) FILTER (WHERE classification_lane IS NOT NULL AND dedup_kind = 'none') AS with_dedup_none
FROM articles
WHERE created_at > NOW() - INTERVAL '6 hours';

SELECT id, feed_id, feed_domain, classification_lane, classified_by_model,
       classified_by_provider, was_escalated, dedup_kind, dedup_action,
       pipeline_latency_ms, embedding_time_ms, geo_resolution_method
FROM articles
WHERE classification_lane IS NOT NULL
ORDER BY created_at DESC LIMIT 5;

-- ledger link + FinOps
SELECT COUNT(*) AS linked
FROM llm_request_ledger
WHERE article_id IS NOT NULL AND created_at > NOW() - INTERVAL '6 hours';

SELECT id, purpose, model, article_id, miniflux_entry_id,
       prompt_tokens, completion_tokens, cached_prompt_tokens,
       execution_time_ms, http_status, status
FROM llm_request_ledger
ORDER BY created_at DESC LIMIT 5;
```
Assert: ≥12 pezzi denorm completi; dedup_kind=`none` sui insert; ledger linkato; token NULL solo se provider non espone (non zeri finti).

### T4 — prova URL exact (BLOCKER)
Secondo requeue sugli **stessi** entry (o altri già in DB) per forzare URL dup:
```bash
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 15 --dry-run
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 15
```
Attendi. Poi:
```sql
SELECT dedup_kind, action_taken, COUNT(*),
       COUNT(*) FILTER (WHERE cosine_distance IS NULL) AS null_dist
FROM article_dedup_events
GROUP BY 1, 2
ORDER BY 3 DESC;

SELECT id, incoming_url, existing_article_id, winner, dedup_kind, action_taken,
       cosine_distance, feed_id, incoming_miniflux_entry_id, created_at
FROM article_dedup_events
WHERE dedup_kind = 'url_exact'
ORDER BY created_at DESC LIMIT 5;
```
```bash
curl -sS "http://localhost/api/metrics/summary"
curl -sS "http://localhost/api/metrics/dedup"
```
**PASS solo se** `url_exact` ≥ 1 e API `url_exact_count` ≥ 1.

Se dopo 2 requeue ancora 0: diagnostica (mark-read troppo presto? lock? event non chiamato? entry diverse?). Non dichiarare GREEN.

### T5 — verify script stretto + API parity
```bash
docker compose exec -T radar-worker python -m app.scripts.verify_metrics_013
```
Deve uscire 0 **solo** con url_exact e soglie SoT.

Confronta a mano summary API vs SQL (totali token/eventi nella stessa finestra date).

### T6 — log Docker
```bash
docker compose logs radar-worker --tail 400 | grep -E 'ERROR|Traceback|url_exact|Semantic dedup|ClassificationResult' || true
docker compose logs radar-backend --tail 100 | grep -E 'ERROR|Traceback|/api/metrics' || true
```
Zero Traceback su path metrics; eventuali ERROR spiegati.

## Soglia PASS (GATE GREEN)
- [ ] Fix A dedup none/inserted_new live sui nuovi insert
- [ ] Fix B verify fallisce senza url_exact; passa con evidenza
- [ ] Fix C pytest `-m "not live"` verde con assert URL+denorm
- [ ] ≥12 articoli recenti denorm+ledger OK
- [ ] ≥1 (meglio ≥2) eventi `url_exact` live + API allineata
- [ ] API summary/by-feed/dedup coerenti con SQL
- [ ] Nessun ERROR worker bloccante
- [ ] Docs/skills solo se cambi contratto verify/API
- [ ] Commit dettagliato (no `.env`)
- [ ] Sposta `plan_impl_fase_metrics_013.md` → `plan-audit/complete/`
- [ ] Sposta questo prompt + agent_prompt metrics → `prompts/done/` (o aggiorna stato DONE)
- [ ] Aggiorna `plan-audit/STATUS.md` (Metrics 013 COMPLETE / GATE VERDE) + checklist §10

## Deliverable chat
1. Diff fix A/B/C (+D se fatto)
2. Output pytest
3. Evidence SQL + curl (url_exact ≥1, sample denorm, ledger)
4. Output verify_metrics_013 exit 0
5. Commit hash
6. plan-audit chiuso

## Fuori scope
UI FinOps, article_type LLM, sidebar, Wave 2 mappa, --purge-all, backfill storico massivo.

Inizia da Fix A → Fix B → Fix C → T1 → T2 → T3 → T4 → T5 → T6 → chiusura plan-audit.
Se T4 fallisce dopo diagnosi onesta, fermati a YELLOW con report — non forzare GREEN.
```

---

## Nota orchestratore

- Non rieseguire l’intera Fase 013 da zero.
- Il walkthrough precedente che dichiara GATE verde è **non autoritativo**; questo closeout lo è.
- RPD SIMPLE piena → residual DeepSeek è OK purché denorm = modello vincente.
