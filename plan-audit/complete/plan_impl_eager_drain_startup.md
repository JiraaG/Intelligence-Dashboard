# Piano — Eager drain all’avvio worker (Miniflux)

> **Stato: COMPLETE / GATE VERDE** 2026-07-24  
> **Data:** 2026-07-24  
> **Branch tipico:** `feature/upgrades`  
> **Prompt Agent:** [`../prompts/done/agent_prompt_eager_drain_startup.md`](../prompts/done/agent_prompt_eager_drain_startup.md)  
> **PO:** nessun `git commit` / `git push` finché non richiesto esplicitamente.

---

## 1. Problema

Al `docker compose up` / restart di `radar-worker` il sistema **sembra bloccato** dopo un ciclo: log tipo *Attesa wake NOTIFY o timeout poll (900s)*.

Non è un hang in errore: Phase B già attende **webhook NOTIFY oppure** timeout `WORKER_POLL_INTERVAL_SECONDS` (default 900).

Gap reale:

1. Tra batch da `MINIFLUX_LIMIT` (50) il loop chiama **sempre** `_wait_interval` → con arretrato grande si aspetta fino a 15 min tra un lotto e il successivo (salvo webhook).
2. `refresh_all_feeds()` è chiamato **solo una volta** all’avvio e è fire-and-forget: il primo fetch unread può arrivare prima che Miniflux finisca lo scraping.
3. Docs/ECC ancora parlano di `asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)` come modello unico — drift rispetto a wake event-driven.

Requisito utente: **accendendo i servizi Docker, scaricare/processare subito tutto**, senza pause da 900s finché c’è lavoro.

---

## 2. Design chiuso

| Decisione | Valore |
|-----------|--------|
| Event-driven | Invariato: webhook → `NOTIFY radar_worker_trigger` → wake |
| Safety poll | `WORKER_POLL_INTERVAL_SECONDS=900` invariato |
| Drain | **Drain-until-empty** prima di ogni long-wait (boot + post-wake/timeout) |
| Refresh | `refresh_all_feeds` all’inizio di **ogni** fase di drain |
| Settle | `WORKER_REFRESH_SETTLE_SECONDS=15` (default; `0` = off) |
| Ollama unload | Solo prima del long-wait, non tra batch del drain |
| Commit | Nessuno in questa wave |

```text
boot / wake / timeout
  → refresh_all_feeds
  → sleep settle (se > 0)
  → while run_pipeline_cycle() returns had_entries:
        (no _wait_interval)
  → maybe_unload_ollama_after_cycle
  → _wait_interval(900)   # wake OR timeout
```

---

## 3. File codice

### 3.1 [`radar/backend/app/worker.py`](../../radar/backend/app/worker.py)

- `run_pipeline_cycle` → ritorna `bool` (`True` se ha preso unread e ha lavorato / tentato il lotto; `False` se nessun unread o early-exit senza lotto utile).
- Nuovo helper `_drain_unread(state)` (nome libero se coerente): refresh + settle + loop cicli.
- `run_pipeline_loop`: sostituire “ciclo → wait sempre” con “drain → wait → drain…”.
- Log chiari: `drain batch N`, `unread drained`, `entering safety poll wait`.

### 3.2 Config

- [`radar/backend/app/core/config.py`](../../radar/backend/app/core/config.py): `WORKER_REFRESH_SETTLE_SECONDS` (default 15, min 0, max 120).
- [`radar/.env.example`](../../radar/.env.example): knob + commento drain eager / 900s safety / webhook.

### 3.3 Test

- [`radar/backend/app/tests/test_worker_shutdown.py`](../../radar/backend/app/tests/test_worker_shutdown.py) (+ test drain dedicato se più leggibile):
  - 2+ batch finti → N cicli **senza** `_wait_interval` tra di essi; un wait a coda vuota.
  - Unread vuoto → wait dopo primo drain.
  - Cancel durante drain / durante wait resta rapido.

---

## 4. Docs / ECC / plan-audit (obbligatorio)

Aggiornare in place — messaggio canonico: **webhook/NOTIFY = wake primario; drain-until-empty all’avvio e post-wake; 900s = safety a coda vuota**.

| File | Cosa sistemare |
|------|----------------|
| [`docs/01_getting_started.md`](../../docs/01_getting_started.md) | Polling + refresh avvio → drain eager + settle + safety 900 |
| [`docs/02_architecture_and_backend.md`](../../docs/02_architecture_and_backend.md) | Periodicità ingest: non solo “ogni 900s” |
| [`radar/docs/runbook.md`](../../radar/docs/runbook.md) | Drain, settle, webhook URL, “900s ≠ hang” |
| [`.agents/AGENTS.md`](../../.agents/AGENTS.md) | Sostituire claim `asyncio.sleep` unico con wake OR timeout + drain |
| [`radar/.ecc/CLAUDE.md`](../../radar/.ecc/CLAUDE.md) | Tabella backend + diagramma loop (non `sleep` solo) |
| [`radar/.ecc/rules/backend.md`](../../radar/.ecc/rules/backend.md) | Snippet loop + tabella env (`WORKER_REFRESH_SETTLE_SECONDS`) |
| [`radar/.ecc/agents/pipeline-engineer.md`](../../radar/.ecc/agents/pipeline-engineer.md) | Snippet loop allineato |
| [`plan-audit/STATUS.md`](../STATUS.md) | Riga **In corso** per questo piano |
| [`plan-audit/README.md`](../README.md) | Link active + prompt |
| [`plan-audit/complete/master_plan_impl_phase_B.md`](../complete/master_plan_impl_phase_B.md) | Nota breve: refinement post–Phase B (drain), webhook resta |

Non toccare: `radar-sidebar/**`, quota ledger, LLM models, Compose `command` del worker.

---

## 5. Riavvio Docker + verifica

```bash
cd radar
docker compose up -d --build radar-worker
docker compose logs -f radar-worker --since 5m
```

### Assert

1. Avvio: refresh (+ settle) → batch continui senza `Attesa wake NOTIFY…` tra batch se ci sono unread.
2. Coda vuota: log wait 900s / wake.
3. Pytest:

```bash
docker compose exec -T radar-worker pytest app/tests/test_worker_shutdown.py -q
```

4. Opzionale webhook: script `app.scripts.simulate_miniflux_webhook` (secret allineato) → log `Risveglio da radar_worker_trigger` + nuovo drain.

---

## 6. Criteri GATE

- [ ] Codice drain-until-empty + settle + refresh per fase
- [ ] Test worker verdi
- [ ] Docs/ECC/plan-audit allineati
- [ ] Restart Docker verificato sui log
- [ ] Nessun commit non richiesto

---

## 7. Fuori scope

- Ridurre default 900 → 60–180
- Busy-poll continuo
- Cambiare `MINIFLUX_LIMIT` o limiti LLM
- Configurare Miniflux UI webhook (ops manuale; documentare solo)
