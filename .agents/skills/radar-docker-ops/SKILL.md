---
name: radar-docker-ops
description: >
  Compose/Dockerfile Radar: reti edge/data, health live vs ready, verify-geojson,
  volume ./data/postgres, no latest, npm ci, digest pin deferred.
when_to_use:
  - docker-compose.yml, Dockerfile, nginx.conf, runbook ops
  - Healthcheck, reti, rebuild frontend, GeoJSON in build
version: 1.1.0
---

## Quando attivare

Modifiche a containerizzazione, reti, health, o build FE in Docker.

## Vincoli

1. Servizi immutabili: `radar-db`, `radar-backend`, `radar-worker`, `radar-frontend`, `radar-miniflux`.
2. Reti Phase 3+: `radar-edge` (frontend ↔ backend) e `radar-data` (backend, worker, db, miniflux).
3. Persistenza DB: bind `./data/postgres` (non volume anonimo “usa e getta”).
4. Health: distinguere **live** vs **ready** dove documentato; FE Alpine → `wget` non `curl`.
5. FE Dockerfile: multi-stage; builder `npm ci --legacy-peer-deps`; **obbligatorio** `node scripts/verify-geojson.mjs --fetch` prima del build (GeoJSON gitignored).
6. No tag `latest` su immagini base; versioni pinnate.
7. Nginx: resolver `127.0.0.11` + variabile per `proxy_pass` (anti-502).
8. Frontend runs as unprivileged nginx user listening on port 8080 (host mapped 80:8080).
9. **Profilo F / Ollama host:** overlay `docker-compose.ollama-host.yml` aggiunge `extra_hosts: host.docker.internal:host-gateway` su `radar-worker` — non inventare un servizio `radar-ollama` ROCm di default.

## Deferred (non inventare come fatto; non trattare come backlog obbligatorio)

- Drop `--legacy-peer-deps` solo con matrix allineata (decisione esplicita)
- Digest pin immagini = opzionale prodotto (Final Release Fase 5 **DEFERRED ACCETTATO** 2026-07-17; confermato non richiesto 2026-07-18)
- Final Release F0–F4 **COMPLETE** (PR #1 merged); tip = `develop` — vedi `plan-audit/STATUS.md`

## Ops .env / backup Windows

`ops/backup-postgres.sh` / `restore-postgres.sh` usano `ops/_load_dotenv.sh` (KEY=VALUE), non `source .env` grezzo.  
Backup/restore su host Windows: seguire `radar/ops/README.md` §Windows (Git Bash/WSL, non PowerShell raw; `MSYS_NO_PATHCONV=1`). Non committare `radar/backups/` né dump sotto `data/postgres`.

## Comandi utili

```bash
# Preferire up -d (rispetta depends_on healthy). Evitare restart parallelo di tutto lo stack:
# compose restart non ri-applica depends_on → race CannotConnectNowError su DB starting up.
docker compose up -d
docker compose up --build -d radar-frontend
# Local-Hybrid (Profilo F): bridge host Ollama
# docker compose -f docker-compose.yml -f docker-compose.ollama-host.yml up -d radar-worker
# Restart ordinato se necessario: radar-db → wait healthy → altri
# da radar/: verificare GeoJSON
node frontend/scripts/verify-geojson.mjs
```

## Knobs ops frequenti

- `MINIFLUX_LIMIT`: default/tipico **50** (`.env.example`). Con molti unread, `100` può superare `MAX_MINIFLUX_RESPONSE_BYTES=5MB`.
- Profilo A hybrid: `LLM_SIMPLE_MODEL=gemini-3.5-flash-lite`, `LLM_SIMPLE_FALLBACKS=gemini-3.1-flash-lite` (L1 same-provider; L2 residual COMPLEX). `GEMINI_MODEL` legacy allineato al primary SIMPLE. HTTP 500 su Gemma legacy → flash-lite in `.env` + restart `radar-worker`. Non commitare `.env`.
- Profilo F: `LLM_SIMPLE_BASE_URL=http://host.docker.internal:11434/v1` + modello host tipico `gemma4-radar` (base `gemma4:12b`); runbook § Local-Hybrid; `WORKER_*_CONCURRENCY=1` + `OLLAMA_NUM_PARALLEL=1` consigliati. VRAM unload: `OLLAMA_AUTO_UNLOAD` + `ops/verify-ollama-vram.sh`.

## SoT

Dettaglio: `radar/.ecc/rules/docker.md` (Regola 4: restart vs `up -d`; overlay `ollama-host`) + runbook `radar/docs/runbook.md`.
