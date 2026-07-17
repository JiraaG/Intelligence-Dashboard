# Final Release — Fase 3 Chaos kill/restart

**Stato:** PASS (minimo C1–C3)  
**Data:** 2026-07-17  
**Precondizione:** Fase 1 backup PASS (`20260717T064518Z` + safety)

---

## Scenari

| # | Azione | Esito | Evidenza |
|---|--------|-------|----------|
| C1 | `docker compose restart radar-worker` | **PASS** | Leadership riacquisita; demone avviato; outbox invariata `completed=2025` |
| C2 | `kill` + `up -d` worker | **PASS** | Migrazioni allineate; leadership OK; poll ciclo; outbox `completed=2025` only |
| C3 | `restart radar-db` | **PASS*** | Transient `database system is starting up` su heartbeat/backend (atteso); dopo healthy: live OK, map-summary OK, articles **12897** (2893+10k seed), outbox solo `completed` |
| C4 | Stop Miniflux mid mark-read | **SKIP** | Nessun unread in coda / no mid-ack in corso |
| C5 | 429 provider | **SKIP** | Nessun 429 osservato in questa sessione |

\* Durante il boot DB: warning worker heartbeat + backend `CannotConnectNowError` — recovery automatica senza intervento; nessun outbox `pending`/`writing` residuo.

---

## Criteri PASS

- [x] Nessun articolo perso (count post-chaos = pre-chaos + seed)  
- [x] Nessun mark-read prematuro osservabile (outbox solo `completed`; Miniflux unread=0 nel ciclo)  
- [x] Worker riprende leadership; demone vivo  
- [x] Report C1–C3 con SKIP documentati per C4–C5  

## Note

- Sidebar freeze rispettato (zero edit UI).  
- Non eseguito `docker compose down -v`.

## Decisione

**Fase 3 PASS** — proseguire a Fase 4 (SAST / image scan / XSS spot).
