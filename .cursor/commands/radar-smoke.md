# radar-smoke

Follow the operational smoke path in `radar/docs/runbook.md` (compose up, health, sample API).

### Smoke check curls:
```bash
curl -s http://localhost/health/live
curl -s "http://localhost/api/map-summary?date=$(date -I)"
curl -s "http://localhost/api/map-relations?date=$(date -I)"
curl -s http://localhost/api/saved-summary
curl -s "http://localhost/api/articles?saved=true&limit=10"
```

Prefer documenting outcomes over inventing new health endpoints. Distinguish **live** vs **ready** where the runbook does.
