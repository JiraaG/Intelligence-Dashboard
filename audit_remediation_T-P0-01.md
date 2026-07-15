# Audit Report — Ticket T-P0-01: Gate Mark-Read su Duplicato

> **Stato ticket:** **DONE** (verificato nel workspace principale 2026-07-15)  
> **SoT stato:** `audit_problemi_documentazione_risoluzione.md` §3 / §8.1  
> **Playbook:** `audit_problemi_documentazione.md` §3.1 / §4.1 / Script G

---

## 0. Verdetto verifica workspace (post walkthrough Antigravity)

| Check | Esito |
|-------|--------|
| Walkthrough applicato *solo* al worktree Antigravity? | **Sì inizialmente** — codice assente nel workspace principale |
| Fix portato + verificato qui? | **Sì** — `worker.py` + `test_worker_gate.py` |
| ADJUST cieco `completed\|None`? | **Assente** (REJECT rispettato) |
| ruff | PASS |
| pytest `test_worker_gate.py` | **4/4 PASS** |
| pytest `-m "not live"` | **111 passed** |
| Worker container rebuild | Gate presente (`outbox_status` / vault-check) |
| Docs coerenti con codice? | Sì dopo allineamento §1/§3/§8/App. D |

**Verdetto complessivo dopo remediation in-workspace:** **PASS** (con gap ops Miniflux payload size fuori scope).

---

## 1. Fasi

| Fase | Stato |
|------|--------|
| FASE 3 Riproduzione | DONE (staging entry 6072 / article 2885) |
| FASE 4 Design + implementazione | DONE (vault-check NULL; ADJUST REJECT) |
| FASE 5 Gate | DONE in questo workspace |

---

## 2. FASE 3 — Evidenze (storico)

AS-IS pre-fix: mark-read cieco su `is_dup` (`worker.py`).

Repro: article `2885` senza outbox → mark-read immediato (log 2026-07-15 18:00:08).

---

## 3. FASE 4 — Policy implementata

| Outbox | Azione |
|--------|--------|
| `completed` | mark-read |
| `pending` / `failed` / `writing` | skip + warning → `reconcile_outbox` |
| `NULL` | mark-read **solo se** `asyncio.to_thread(Path(vault_path).is_file)` dopo `get_article_file_path` |
| — | **VIETATO** `in ("completed", None)` senza vault-check |

Codice: `radar/backend/app/worker.py` ramo `if is_dup:`.

---

## 4. FASE 5 — Esiti (workspace principale)

```text
ruff check backend/app/worker.py backend/app/tests/test_worker_gate.py  → All checks passed
pytest backend/app/tests/test_worker_gate.py -v                         → 4 passed
pytest -m "not live" -q                                                 → 111 passed
docker compose build/up radar-worker                                    → GATE_PRESENT_IN_CONTAINER=OK
```

Test in-repo: `radar/backend/app/tests/test_worker_gate.py`  
(non fare affidamento solo al path worktree Antigravity).

Script G: numerosi `articles` con outbox NULL (legacy) — gestiti dal vault-check.

---

## 5. Gap residui / handoff

| Item | Severità | Note |
|------|----------|------|
| T-P1-03 retry mark-read post-completed | **P1 next** | Dipendenza soddisfatta; implementare subito |
| Miniflux `MAX_MINIFLUX_RESPONSE_BYTES` | Ops | Worker log: corpo risposta > 5MB → fetch fallisce; fuori T-P0-01 |
| Permission denied `logs/` in container | Ops | Solo console logging; non blocca gate |
| Backfill outbox completed per legacy | Perfect | Riduce dipendenza da vault-check path reconstruction |

**Handoff one-liner T-P1-03:** *Dopo T-P0-01, implementare retry mark-read per outbox `completed` con mark-read fallito (`outbox.py` reconcile oggi ignora completed).*

---

## 6. Criteri DoD (firmati)

- [x] Gate `== "completed"`
- [x] Skip pending/failed/writing
- [x] NULL: no mark-read cieco (vault-check)
- [x] `test_worker_gate.py` 4/4
- [x] pytest not live verde
- [x] Nessun ADJUST cieco
- [x] Codice nel workspace principale + worker rebuild
- [x] Risoluzione §3 DONE + §8.1 aggiornato
- [x] Handoff T-P1-03 annotato
