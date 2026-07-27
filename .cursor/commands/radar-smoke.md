# radar-smoke

Follow the operational smoke path in `radar/docs/runbook.md` (compose up, health, sample API).

### Smoke check curls:
```bash
# FE Nginx health (host :80) — static "ok"; NOT backend /health/live
curl -s http://localhost/health
# Backend liveness (in-container :8000)
docker compose exec radar-backend curl -sf http://localhost:8000/health/live
curl -s "http://localhost/api/map-summary?date=$(date -I)"
curl -s "http://localhost/api/map-relations?date=$(date -I)"
curl -s http://localhost/api/saved-summary
curl -s "http://localhost/api/articles?saved=true&limit=10"
```

Prefer documenting outcomes over inventing new health endpoints. Distinguish **live** vs **ready** where the runbook does.
