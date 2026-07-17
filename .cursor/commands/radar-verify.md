# radar-verify

Run the standard local verify suite. Use the cwd shown for each block (monorepo root = `Dashboard finance`).

```bash
# Frontend — from radar/frontend
cd radar/frontend
npm run typecheck && npm run test:ci && npm run build:ci

# Backend — from radar/ (PYTHONPATH required on host)
cd radar
set PYTHONPATH=backend
python -m pytest -m "not live" -q
# Unix: PYTHONPATH=backend python -m pytest -m "not live" -q

# GeoJSON — from radar/
cd radar
node frontend/scripts/verify-geojson.mjs
```

Do not touch `radar/frontend/src/app/components/radar-sidebar/**`.
