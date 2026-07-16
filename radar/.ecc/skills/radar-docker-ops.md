---
name: radar-docker-ops
description: >
  Compose/Dockerfile Radar: reti edge/data, health live vs ready, verify-geojson,
  volume ./data/postgres, no latest, npm ci, digest pin deferred.
when_to_use:
  - docker-compose.yml, Dockerfile, nginx.conf, runbook ops
  - Healthcheck, reti, rebuild frontend, GeoJSON in build
version: 1.0.0
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

## Deferred (non inventare come fatto)

- Drop `--legacy-peer-deps` solo con matrix allineata
- Digest pin immagini = opzionale prodotto post–Phase 6

## Comandi utili

```bash
# Preferire up -d (rispetta depends_on healthy). Evitare restart parallelo di tutto lo stack:
# compose restart non ri-applica depends_on → race CannotConnectNowError su DB starting up.
docker compose up -d
docker compose up --build -d radar-frontend
# Restart ordinato se necessario: radar-db → wait healthy → altri
# da radar/: verificare GeoJSON
node frontend/scripts/verify-geojson.mjs
```

## Knobs ops frequenti

- `MINIFLUX_LIMIT`: default/tipico **50** (`.env.example`). Con molti unread, `100` può superare `MAX_MINIFLUX_RESPONSE_BYTES=5MB`.
- `GEMINI_MODEL`: default `gemma-4-31b-it`; se il provider risponde HTTP 500, fallback ops in `.env` (es. `gemini-3.1-flash-lite`) + restart `radar-worker`. Non commitare `.env`.

## SoT

Dettaglio: `radar/.ecc/rules/docker.md` (Regola 4: restart vs `up -d`) + runbook `radar/docs/runbook.md`.
