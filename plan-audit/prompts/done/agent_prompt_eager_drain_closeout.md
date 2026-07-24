# Agent prompt — Eager drain closeout (verify + stack restart)

> **Stato: DONE / eseguito** 2026-07-24 — closeout post-impl completato.  
> **SoT:** [`../../complete/plan_impl_eager_drain_startup.md`](../../complete/plan_impl_eager_drain_startup.md)  
> **Review parent:** GATE GIALLO (condizionato) — codice/test OK; evidenza log gate incompleta; drift diagramma `CLAUDE.md`.  
> **PO:** nessun `git commit` / `git push` finché non richiesto.

---

## Come usare

1. Chat **Agent** sul branch di lavoro (tipico `feature/upgrades`).
2. Incolla il blocco **PROMPT** sotto per intero.
3. A fine GATE: aggiorna `STATUS.md`; sposta piano/prompt in `complete/` / `done/` **solo** con OK PO.

---

## PROMPT (incolla in Agent mode)

```text
# Task — CLOSEOUT: Eager drain (verify log + polish + riavvio TUTTO lo stack Docker)

## Ruolo
Pipeline / ops engineer Radar. Completa la fase eager-drain: fix residui review, riavvio **completo** Compose, ricattura log gate, aggiorna STATUS.
Sidebar freeze. **Nessun git commit / push**.

## Contesto (già fatto — NON rifare da zero)
Working tree già contiene R1–R6 in:
- `radar/backend/app/worker.py` (`_drain_unread`, `run_pipeline_cycle -> bool`, settle selettivo, wake mid-drain)
- `radar/backend/app/core/config.py` (`WORKER_REFRESH_SETTLE_SECONDS`)
- `radar/backend/app/tests/test_worker_shutdown.py` (12 test)
- docs principali + `.env.example`
Review: codice/test OK; GATE GIALLO perché `/tmp/eager-drain-gate.log` era corto/sovrascritto (mancano Demone/settle/Drain/Attesa wake) e `radar/.ecc/CLAUDE.md` L236 ha ancora `asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)`.

## Autorità
1. `plan-audit/complete/plan_impl_eager_drain_startup.md`
2. Questo prompt (closeout)
3. Skill `radar-docker-ops` (reti, health, no `latest` inventati)
4. Vietato: `radar-sidebar/**`; cambiare default `WORKER_POLL_INTERVAL_SECONDS=900`; busy-poll; requeue `--purge-all`; commit `.env`/secret

## Lavoro obbligatorio

### A) Polish docs (minimo)
In `radar/.ecc/CLAUDE.md`, sezione “Architettura della Pipeline Dati”:
- Sostituisci il claim `asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS) loop` con messaggio canonico:
  webhook/NOTIFY wake → eager drain-until-empty; settle `WORKER_REFRESH_SETTLE_SECONDS` su boot/timeout; `_wait_interval(WORKER_POLL_INTERVAL_SECONDS)` = safety a coda vuota.
- Allinea eventuali altre menzioni sleep-only nello stesso file se ancora presenti.

### B) Guard anti tight-loop (consigliato, piccolo, in scope)
In `_drain_unread` / `run_pipeline_cycle`: se un ciclo ha preso unread ma **nessun progresso utile** (es. `results["success"] == 0` e nessun mark-read effettivo — usa il segnale più semplice già disponibile: dopo ciclo con entries, se `results["success"] == 0` allora **break** dal drain e vai al safety wait, con log warning).
Obiettivo: evitare ritentare all’infinito gli stessi unread falliti senza i 900s.
Aggiungi/estendi 1 test unitario che simula cycle True poi… meglio: cycle che ritorna un sentinel o patch interno — se troppo invasivo, fai ritornare `False` da `run_pipeline_cycle` quando ha processato un lotto con `success==0` (documenta in docstring). Preferisci: **`return False` se dopo il join `results["success"] == 0`** (anche se c’erano entries), così il drain esce e aspetta 900s. Casi skip/ok restano `success` incrementato come oggi.

### C) Test
```bash
cd radar
python -m pytest backend/app/tests/test_worker_shutdown.py -q --tb=short
# oppure dalla root backend:
# cd backend && python -m pytest app/tests/test_worker_shutdown.py -q
```
Deve restare tutto verde. Se tocchi la semantica `success==0` → aggiorna/aggiungi assert.

### D) Riavvio TUTTI i servizi Docker (obbligatorio)
Da `radar/` (skill docker-ops: preferisci `up -d --build` sull’intero stack, non solo worker; rispetta `depends_on`/health):

```bash
cd radar
# Stack completo (tutti i servizi del compose attivo; includi overlay solo se già in uso ops, es. ollama-host)
docker compose down
docker compose up -d --build
# Attendi healthy: db → backend/worker/miniflux/frontend secondo compose
docker compose ps
docker compose logs radar-worker --since 3m 2>&1 | tee /tmp/eager-drain-gate.log
```

Se usate overlay abituali (es. `-f docker-compose.yml -f docker-compose.ollama-host.yml`), riusali **uguali** all’ambiente ops — non inventare file.

**NON** usare solo `docker compose restart radar-worker`. Serve **down + up -d --build** (o equivalente che ricrea tutto lo stack).

### E) Assert log (GATE)
Nel file `/tmp/eager-drain-gate.log` (e/o `docker compose logs`) devono comparire, in ordine sensato:

1. `Demone pipeline avviato (poll=900s, settle=…`
2. Refresh feed (`PUT` … `/v1/feeds/refresh` o log refresh completato)
3. Se settle>0: `Attesa assestamento scraping Miniflux`
4. Uno o più cicli; se arretrato: `Drain batch N` **senza** `Attesa wake NOTIFY` tra un batch e il successivo
5. A coda vuota (o dopo drain): `Attesa wake NOTIFY o timeout poll (900s)...`
6. Nessun `Traceback` bloccante nel tratto di verify

Se al momento del verify c’è ancora arretrato lungo, non aspettare lo svuotamento totale: basta dimostrare **≥2 batch consecutivi senza wait in mezzo** OPPURE (se unread≤50) un ciclo + subito attesa wake. Documenta quale caso hai osservato.

Opzionale: se `MINIFLUX_WEBHOOK_SECRET` è configurato, smoke webhook → `Risveglio da radar_worker_trigger` + nuovo drain con settle=False (no sleep 15s).

### F) plan-audit
Aggiorna `plan-audit/STATUS.md` riga Eager drain:
- Se assert log OK → **GATE VERDE** + path log + data
- Se log incompleti → lascia **GIALLO** con gap esplicito
Non spostare piano/prompt in `complete/`/`done/` senza OK PO.
Aggiorna `plan-audit/README.md` solo se serve chiarezza sullo stato.

## Deliverable (report al PO, senza commit)
1. File toccati in questo closeout
2. Esito pytest
3. Conferma `docker compose ps` (tutti i servizi up/healthy)
4. Citazione righe chiave da `/tmp/eager-drain-gate.log` (non solo “OK”)
5. Esito GATE VERDE o GIALLO motivato
6. NESSUN git commit/push

## Fuori scope
- Cambiare 900s default
- Sidebar / FE
- Modelli LLM / quote
- Archiviazione formal complete/ senza OK PO
```

---

## Checklist PO

- [ ] Stack intero ripartito (`down` + `up -d --build`)
- [ ] Log gate con Demone / settle / drain o attesa wake
- [ ] Diagramma CLAUDE senza sleep-only
- [ ] Guard `success==0` (o motivazione se saltata)
- [ ] Commit solo su richiesta esplicita
