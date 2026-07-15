# Audit Report — Ticket T-P1-02: Race TOCTOU multi-consumer / advisory lock per-URL

> **Stato ticket:** **DONE** (verificato nel workspace principale 2026-07-15)  
> **SoT stato:** `plan-audit/audit_problemi_documentazione_risoluzione.md` §3 / §13  
> **Playbook:** `plan-audit/audit_problemi_documentazione.md` §3.4 / §4.3 / Script H

---

## 0. Verdetto verifica workspace (post remediation)

| Check | Esito |
|-------|--------|
| Modifiche applicate al workspace principale? | **Sì** — `worker.py` (hash SHA-256 e `pg_advisory_lock` a 2 argomenti), `test_worker_concurrency.py` |
| Key advisory lock ≠ leadership worker key? | **Sì** — Usata chiave a due argomenti con namespace `777666555` e intero a 32 bit hash dell'URL, evitando collisioni con `WORKER_ADVISORY_LOCK_KEY`. |
| Lock rilasciato anche su exception / `CancelledError`? | **Sì** — Lock rilasciato nel blocco `finally` della connessione. |
| ruff | PASS |
| pytest `test_worker_concurrency.py` | **1/1 PASS** |
| pytest `-m "not live"` | **115 passed** |
| Worker container rebuild | **PASS** (riverifica Cursor: daemon riavviato; build/up OK; `get_url_lock_keys` + `quote_plus` + `miniflux_marked_at` in image; ingest attivo) |
| Docs coerenti con codice? | Sì dopo riverifica Cursor (pie P1=2, §3.4/§4.3, App. D) |

**Verdetto complessivo dopo remediation in-workspace:** **PASS_WITH_GAPS** — codice/test/docs OK; gap residuo = Docker Desktop spento (rebuild worker non riverificato in container).

---

## 1. Fasi

| Fase | Stato |
|------|--------|
| FASE 3 Riproduzione | DONE (confermato che con `WORKER_ENTRY_CONCURRENCY >= 2` due entry con stesso URL potevano superare contemporaneamente il dedup richiamando Gemini) |
| FASE 4 Design + implementazione | DONE (introdotto `pg_advisory_lock(namespace, hash)` a livello di sessione all'interno di `process_single_entry`) |
| FASE 5 Gate | DONE in questo workspace (115/115 test passati) |

---

## 2. FASE 3 — Evidenze (storico)

**AS-IS pre-fix:**
Sotto concorrenza, due worker `_entry_consumer` prelevavano dalla coda bounded lo stesso `source_url`.
Il controllo `is_article_duplicate` eseguito in parallelo restituiva `False` per entrambi perché l'articolo non era ancora stato inserito.
Questo causava una doppia chiamata Gemini API per lo stesso articolo e tentativi multipli di scrittura a DB (con crash di unicità o record duplicati).

---

## 3. FASE 4 — Policy implementata

- Aggiunto helper deterministico `get_url_lock_keys(url)` che genera una chiave a 2 argomenti:
  - `namespace`: `777666555`
  - `key`: primi 4 byte di SHA-256 dell'URL interpretati come intero a 32 bit con segno.
- `process_single_entry` acquisisce la connessione tramite `async with state.db_pool.acquire() as conn:`.
- Esegue `SELECT pg_advisory_lock($1, $2)` prima di fare qualsiasi controllo di duplicazione.
- In `finally` esegue `SELECT pg_advisory_unlock($1, $2)` se il lock è stato acquisito. In questo modo si garantisce che il lock venga rilasciato anche in caso di errori imprevisti o `asyncio.CancelledError`.
- La concorrenza per lo stesso URL viene serializzata: il secondo worker attende che il primo completi il ciclo e committi a database. Alla fine, il secondo worker acquisisce il lock, esegue `is_article_duplicate`, lo trova già inserito, marca come letto su Miniflux e ritorna bypassando la chiamata a Gemini.

---

## 4. FASE 5 — Esiti (workspace principale)

```text
ruff check backend/app/worker.py backend/app/tests/test_worker_concurrency.py → All checks passed
pytest backend/app/tests/test_worker_concurrency.py -v                       → 1 passed (1.88s)
pytest -m "not live" -q                                                       → 115 passed
docker compose build radar-worker                                             → FAILED (Docker Desktop daemon not running)
```

---

## 5. Gap residui / handoff

| Item | Severità | Note |
|------|----------|------|
| Docker Daemon non attivo | Bassa / Ops | Docker Desktop non era attivo durante l'esecuzione dell'audit, impedendo il build dell'immagine Docker aggiornata per il worker. |
| T-P0-02 Script diagnostici | **P0 next** | Prossimo ticket in coda di remediation. |

**Handoff one-liner T-P0-02:** *Riparazione / deprecazione di `ClassificationClient` e `_wait_for_rate_limit` negli script diagnostici/live.*

---

## 6. Criteri DoD (firmati)

- [x] Due consumer stesso URL → una sola chiamata Gemini (serializzazione provata con `test_worker_concurrency.py`)
- [x] Lock rilasciato anche su exception / CancelledError (tramite `finally` block in `conn.acquire()`)
- [x] Non usare la stessa advisory lock key del leadership worker
- [x] Test di concorrenza aggiunti e superati
- [x] pytest not live 115/115 passed
- [x] Risoluzione §3 DONE + §8.3 + §13 aggiornati
