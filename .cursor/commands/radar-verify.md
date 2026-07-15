# radar-verify

Run the standard local verify suite from the repo (adjust cwd as needed):

```bash
# Frontend (from radar/frontend)
npm run typecheck && npm run test:ci && npm run build:ci

# Backend (from radar/)
python -m pytest -m "not live" -q

# GeoJSON
node frontend/scripts/verify-geojson.mjs
```

Do not touch `radar/frontend/src/app/components/radar-sidebar/**`.
