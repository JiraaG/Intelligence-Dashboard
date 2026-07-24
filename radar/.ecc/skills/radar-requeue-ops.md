---
name: radar-requeue-ops
description: >
  Re-ingest Miniflux: dry-run then requeue_articles inside radar-worker,
  then restart worker for an immediate poll cycle. Destructive to DB/vault/cooldown.
when_to_use:
  - Incident re-classify / re-classify after prompt or schema change
  - Runbook "requeue" / app.scripts.requeue_articles
version: 1.1.0
---

## Quando attivare

Devi far riprocessare gli ultimi N entry Miniflux già *read* (dopo fix prompt/schema/quota), senza inventare un altro path di ingest.

**Profilo F / Fase A:** stesso protocollo per il gate qualità 48h (Local-Hybrid Ollama host + COMPLEX cloud) — dry-run → requeue / `--purge-all` → restart worker; log attesi `route lane=SIMPLE … openai` + COMPLEX. Vedi runbook § Local-Hybrid.

## Protocollo obbligatorio

1. **Dry-run prima** (nessuna mutazione):
   ```bash
   cd radar
   docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20 --dry-run
   ```
2. Solo se l’anteprima è corretta, esegui senza `--dry-run`:
   ```bash
   docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20
   ```
2b. **Prova da zero** (wipe vault + DELETE tutte le `articles` + unread ultime N):
   ```bash
   docker compose exec -T radar-worker python -m app.scripts.requeue_articles 100 --purge-all --dry-run
   docker compose exec -T radar-worker python -m app.scripts.requeue_articles 100 --purge-all
   ```
   Lo script pagina Miniflux (≤50 entry/pagina). Il worker processa solo unread entro ~48h.
3. Forza un ciclo immediato (restart → eager drain; 900s = solo safety a coda vuota):
   ```bash
   docker compose restart radar-worker
   ```
4. Verifica log worker: route lane SIMPLE/COMPLEX e assenza di errori vault/Miniflux.

- Requeue 48h / `--purge-all` dopo Profilo F: dry-run → write → `restart radar-worker` (skill `radar-requeue-ops`); host `OLLAMA_NUM_PARALLEL=1` consigliato. Post-ciclo: verificare `ollama_unload` / `ops/verify-ollama-vram.sh`.

## Cosa fa lo script (non reinventare)

SoT: `radar/backend/app/scripts/requeue_articles.py` + runbook `radar/docs/runbook.md`.

- Marca unread le ultime N entry *read* su Miniflux
- Cancella righe PostgreSQL `articles` / `article_outbox` e markdown vault correlati (URL SHA-256 hex[:16])
- Pulisce `llm_model_cooldown`
- **Deve** girare dentro `radar-worker` (mount vault + env Miniflux/DB)

## Anti-pattern

- Requeue “alla cieca” senza `--dry-run`
- Eseguire lo script sull’host senza container (manca vault/env)
- Toccare `worker.py` / inventare DELETE ad-hoc invece dello script
- N enorme (centinaia) senza conferma ops
- Commit di dump/backup generati durante l’incident

## SoT

- Script: `radar/backend/app/scripts/requeue_articles.py`
- Runbook: `radar/docs/runbook.md` (sezione requeue + Local-Hybrid / Profilo F)
- Ops compose: skill `radar-docker-ops`
