---
name: radar-geojson-assets
description: >
  GeoJSON countries in assets/data: gitignored, fetch+verify in Docker build,
  ASSET_LICENSE pin, script verify-geojson.mjs --fetch.
when_to_use:
  - assets/data, frontend Dockerfile builder, verify-geojson, licenze asset
version: 1.0.0
---

## Quando attivare

Lavori su confini mappa, script verify, o stage builder FE.

## Policy

1. `countries.geo.json` (o equivalente) è **gitignored** — non committare dump enormi.
2. Build Docker **deve** eseguire `node scripts/verify-geojson.mjs --fetch` prima di `npm run build`.
3. Rispettare pin/licenza documentati (`ASSET_LICENSE` / note in repo) — non scaricare CDN arbitrarie a runtime nel browser.
4. Offline FE: asset locale sotto `frontend/src/assets/data/`.

## Anti-pattern

- Fetch GeoJSON da CDN nel componente mappa a runtime
- Saltare verify in CI/Docker “per velocità”
- Committare GeoJSON pesante bypassando gitignore
