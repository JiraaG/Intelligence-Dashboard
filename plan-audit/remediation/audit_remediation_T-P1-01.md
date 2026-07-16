# Audit Report — Ticket T-P1-01: DATABASE_URL quote_plus and Compose configuration

> **Stato ticket:** **DONE** (verificato nel workspace principale 2026-07-15)  
> **SoT stato:** `plan_docs_audit_ticket_status.md` §3 / §12  
> **Playbook:** `plan_docs_audit_playbook.md` §3.3 / §4.2 / Script F

---

## 0. Verdetto verifica workspace (post remediation)

| Check | Esito |
|-------|--------|
| Modifiche applicate al workspace principale? | **Sì** — `config.py`, `docker-compose.yml`, `.env.example` |
| quote_plus applicato in config.py? | **Sì** — per `POSTGRES_USER` e `POSTGRES_PASSWORD` |
| DATABASE_URL rimosso da Compose? | **Sì** — rimosso sia per `radar-backend` che per `radar-worker` |
| POSTGRES_HOST impostato a radar-db? | **Sì** — impostato correttamente per backend/worker |
| ruff | PASS |
| pytest `test_database_url.py` | **1/1 PASS** |
| pytest `-m "not live"` | **114 passed** |
| Run Script F localmente | **PASS** (password speciale URL-encoded) |
| Container rebuild & restart | **PASS** (boot pulito, migrazioni allineate, leadership worker OK) |
| printenv nel container backend | **PASS** (`DATABASE_URL` assente, `POSTGRES_HOST=radar-db` presente) |
| Docs coerenti con codice? | Sì dopo riverifica Cursor (FASE 2 pie/App. D/§4.2 allineati; §3 risoluzione già DONE) |

**Verdetto complessivo dopo remediation in-workspace:** **PASS** (credenziali speciali encoded via `quote_plus`; nessun bypass Compose/`DATABASE_URL` su backend/worker; trappola `.env` assente nel runtime verificato).

---

## 1. Fasi

| Fase | Stato |
|------|--------|
| FASE 3 Riproduzione | DONE (confermato che l'URL originale conteneva la password non codificata) |
| FASE 4 Design + implementazione | DONE (quote_plus in config.py, rimosso DATABASE_URL grezzo da Compose, aggiornato .env.example) |
| FASE 5 Gate | DONE (pytest, ruff, Script F, Docker checks) |

---

## 2. FASE 3 — Evidenze (storico)

AS-IS pre-fix:
In `config.py`, `_default_db_url` veniva formattato senza `quote_plus`:
```python
_default_db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
```
Se la password conteneva caratteri come `@`, `:`, `/`, `#`, l'URL risultante mandava in crash il parser `asyncpg`. Inoltre, in `docker-compose.yml` veniva impostato `DATABASE_URL` con stringhe interpolate grezze, bypassando completamente le regole interne dell'app.

---

## 3. FASE 4 — Policy implementata

- `config.py`: importato `quote_plus` da `urllib.parse` e applicato a `pg_user` e `pg_pass`.
- `docker-compose.yml`: rimosso `DATABASE_URL` da `radar-backend` e `radar-worker`, inserendo `POSTGRES_HOST: radar-db`.
- `.env.example`: rimosso `DATABASE_URL` di default e documentata la nota di limitazione per Miniflux e per gli override manuali.
- `test_database_url.py`: aggiunto test unitario per verificare la codifica.

---

## 4. FASE 5 — Esiti (workspace principale)

```text
ruff check app/core/config.py app/tests/test_database_url.py  → All checks passed
pytest app/tests/test_database_url.py                        → 1 passed
pytest -m "not live"                                         → 114 passed
Script F (Powershell)                                        → postgresql://radar_user:p%40ss%3Aw%2Frd%231@localhost:5432/radar_db
docker compose build radar-backend radar-worker              → OK
docker compose up -d                                         → OK
docker compose exec radar-backend printenv DATABASE_URL      → [Vuoto, bypass evitato]
docker compose exec radar-backend printenv POSTGRES_HOST     → radar-db
docker compose exec radar-backend curl -f .../health/live    → {"status":"ok","service":"radar-backend"}
```

---

## 5. Gap residui / handoff

| Item | Severità | Note |
|------|----------|------|
| Miniflux DATABASE_URL | Info/Ops | Miniflux non usa config.py; password speciali → pre-encoding o alfanumerica. Documentato in `.env.example`. |
| T-P1-02 TOCTOU / advisory lock per-URL | **DONE** | Vedi `audit_remediation_T-P1-02.md` |
| T-P0-02 Script diagnostici | **DONE** | Chiuso 2026-07-16 — vedi `audit_remediation_T-P0-02.md`. Next: T-P1-04 |

**Handoff (storico→chiuso):** T-P0-02 DONE. **Prossimo:** T-P1-04.

---

## 6. Criteri DoD (firmati)

- [x] Password con caratteri speciali (@, :, /, #) codificate correttamente con quote_plus
- [x] DATABASE_URL grezzo rimosso da Compose (backend/worker) e sostituito con POSTGRES_HOST
- [x] .env.example aggiornato con nota di avviso per Miniflux e override
- [x] Test unitario per database URL encoding implementato e passante
- [x] 114/114 pytest passed
- [x] ruff allineato e passante
- [x] Rebuild Docker e restart OK (nessun bypass grezzo nel container)
- [x] Aggiornato stato in `plan_docs_audit_ticket_status.md`
- [x] Appendice D / FASE 2 manuale allineati (riverifica Cursor)
- [x] Handoff T-P1-02 annotato (`audit_prompt_T-P1-02.md`)
