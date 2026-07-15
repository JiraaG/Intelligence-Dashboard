# Audit Report — Ticket T-P1-03: Retry Mark-Read Miniflux post-completed

> **Stato ticket:** **DONE** (verificato nel workspace principale 2026-07-15)  
> **SoT stato:** `audit_problemi_documentazione_risoluzione.md` §3 / §8.2  
> **Playbook:** `audit_problemi_documentazione.md` §3.5 / §4.4

---

## 0. Verdetto verifica workspace (post remediation)

| Check | Esito |
|-------|--------|
| Modifiche applicate al workspace principale? | **Sì** — `outbox.py`, migrazione 008, `test_outbox_mark_read_retry.py` |
| Migrazione 008 presente in-repo? | **Sì** — `008_outbox_miniflux_marked_at.sql` |
| Backfill storico completed eseguito? | **Sì** — `UPDATE ... SET miniflux_marked_at = NOW()` per evitare storm storico |
| ruff | PASS |
| pytest `test_outbox_mark_read_retry.py` | **2/2 PASS** |
| pytest `-m "not live"` | **113 passed** |
| Worker container rebuild | Eseguito + confermata presenza della colonna e del codice |
| Docs coerenti con codice? | Sì dopo allineamento §3/§8.2/§11/App. D + conteggi post PASS_WITH_GAPS |

**Verdetto complessivo dopo remediation in-workspace:** **PASS** (codice/test/Docker OK; drift docs conteggi/handoff chiusi in follow-up Cursor).

---

## 1. Fasi

| Fase | Stato |
|------|--------|
| FASE 3 Riproduzione | DONE (confermato isolamento completed dal reconcile SELECT) |
| FASE 4 Design + implementazione | DONE (schema 008 + backfill; helper per marked_at; query addizionale in reconcile) |
| FASE 5 Gate | DONE in questo workspace |

---

## 2. FASE 3 — Evidenze (storico)

AS-IS pre-fix:
In caso di fallimento `miniflux_client.mark_as_read` in `process_outbox_row`, l'outbox passava a completed, ma `reconcile_outbox` selezionava solo `status IN ('pending', 'failed')`. Miniflux rimaneva non letto senza retry.

---

## 3. FASE 4 — Policy implementata

- Migrazione `008_outbox_miniflux_marked_at.sql` aggiunge la colonna `miniflux_marked_at TIMESTAMPTZ NULL` e aggiorna le righe storiche completed a `NOW()`.
- `enqueue_outbox_row` aggiorna/resetta `miniflux_marked_at` on conflict.
- `process_outbox_row` aggiorna `miniflux_marked_at` a `NOW()` dopo che `mark_as_read` ha successo.
- `reconcile_outbox` seleziona separatamente le righe con `status = 'completed' AND miniflux_marked_at IS NULL` ed effettua il retry di `mark_as_read` senza riscrivere il Vault o modificare lo stato/attempt_count.

---

## 4. FASE 5 — Esiti (workspace principale)

```text
ruff check backend/app/commit/outbox.py backend/app/tests/test_outbox_mark_read_retry.py  → All checks passed
pytest backend/app/tests/test_outbox_mark_read_retry.py -v                             → 2 passed
pytest -m "not live" -q                                                                → 113 passed
docker compose build radar-worker && docker compose up -d radar-worker                → Rebuild & Restart OK
docker compose exec radar-db psql ... -c "\d article_outbox"                           → Colonna miniflux_marked_at OK
docker compose exec radar-worker grep -n "miniflux_marked_at" app/commit/outbox.py     → Sync container OK
```

---

## 5. Gap residui / handoff

| Item | Severità | Note |
|------|----------|------|
| T-P1-01 DATABASE_URL quote_plus | **DONE** | Vedi `audit_remediation_T-P1-01.md` |
| T-P1-02 TOCTOU / advisory lock per-URL | **DONE** | Vedi `audit_remediation_T-P1-02.md` |
| T-P0-02 Script diagnostici | **P0 next** | Riparare/deprecare `ClassificationClient` negli script |

**Handoff one-liner T-P0-02:** *Script diagnostici: `ClassificationClient()` senza pool + `_wait_for_rate_limit` rimosso — riparare o deprecare.*

---

## 6. Criteri DoD (firmati)

- [x] Fallimento mark-read non lascia forever-unread
- [x] Vault non riscritto sul retry
- [x] Migrazione 008 applicata nel DB con backfill storico
- [x] Test outbox/reconcile nuovi passati (2/2)
- [x] pytest not live 113/113 passed
- [x] Worker container allineato (rebuild)
- [x] Risoluzione §3 DONE + §8.2 + §11 aggiornati
- [x] Appendice D manuale aggiornata
