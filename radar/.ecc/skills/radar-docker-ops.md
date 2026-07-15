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
docker compose up -d
docker compose up --build -d radar-frontend
# da radar/: verificare GeoJSON
node frontend/scripts/verify-geojson.mjs
```

## SoT

Dettaglio: `radar/.ecc/rules/docker.md` + runbook `radar/docs/runbook.md`.
