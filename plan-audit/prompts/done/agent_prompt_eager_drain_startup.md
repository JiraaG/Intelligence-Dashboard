# Agent prompt — Eager drain all’avvio worker (Miniflux)

> **Stato: DONE / eseguito** 2026-07-24  
> **Piano SoT (obbligatorio):** [`../../complete/plan_impl_eager_drain_startup.md`](../../complete/plan_impl_eager_drain_startup.md)  
> **Branch tipico:** `feature/upgrades`  
> **PO:** nessun `git commit` / `git push` in questa wave.

---

## Come usare

1. Apri una nuova chat in **Agent mode** sul branch di lavoro.
2. Incolla per intero il blocco **PROMPT** sotto.
3. A fine lavoro: aggiorna `plan-audit/STATUS.md` e indici; **non** spostare il piano in `complete/` finché il PO non chiude esplicitamente.
4. Sposta **questo** file in `prompts/done/` solo dopo GATE + conferma PO.

---

## PROMPT (incolla in Agent mode)

```text
# Task — IMPLEMENTAZIONE + VERIFY: Eager drain all’avvio (Miniflux / radar-worker)

## Ruolo
Pipeline engineer Radar. Implementa drain-until-empty sul worker, allinea docs/ECC/plan-audit, riavvia Docker e verifica sui log. Sidebar freeze. **Nessun git commit / push**.

## Autorità (ordine)
1. `plan-audit/complete/plan_impl_eager_drain_startup.md` (SoT) — obbligatorio
2. Questo prompt (chiusure operative)
3. Skills: `radar-docker-ops`, `radar-api-contract` (webhook), `radar-requeue-ops` solo se serve smoke ingest
4. `radar/.ecc/rules/backend.md` + `.agents/AGENTS.md` (dopo averli aggiornati, non prima come SoT obsoleti sul loop)
5. Vietato: `radar-sidebar/**`; cambiare default `WORKER_POLL_INTERVAL_SECONDS`; busy-loop; modifiche quote LLM / modelli; migration DB; commit `.env` / secret

## Contesto (non reinventare)
- Phase B già DONE: webhook HMAC → `POST /api/webhooks/miniflux` → `NOTIFY radar_worker_trigger` → `wake_event` in `worker.py`.
- `_wait_interval` = wake OR timeout 900s (non è un hang).
- Bug UX: dopo OGNI `run_pipeline_cycle` si fa wait, anche se restano unread (batch `MINIFLUX_LIMIT=50`).
- `refresh_all_feeds` oggi solo una volta all’avvio e fire-and-forget.
- Requisito PO: accendendo Docker, scaricare/processare subito tutto senza sembrare bloccato a 900s.

## Design chiuso (eseguire così)
1. `run_pipeline_cycle(...) -> bool` (`had_entries`).
2. Helper drain (es. `_drain_unread`):
   - `refresh_all_feeds()` (warning su errore, non abort)
   - `asyncio.sleep(WORKER_REFRESH_SETTLE_SECONDS)` se > 0 (default 15)
   - loop: finché `await run_pipeline_cycle(state)` è True → continua SENZA `_wait_interval`
   - log: drain batch N / unread drained
3. `run_pipeline_loop`:
   - while True: drain → clear wake → `maybe_unload_ollama_after_cycle` → log attesa → `_wait_interval(900)`
4. Config: `WORKER_REFRESH_SETTLE_SECONDS` in `radar/backend/app/core/config.py` + `radar/.env.example` (0..120, default 15).
5. Non abbassare 900. Non cambiare Compose entrypoint.

## Test
Aggiorna/estendi `radar/backend/app/tests/test_worker_shutdown.py` (o file dedicato se più chiaro):
- Mock: 2+ cicli con entries poi empty → assert `_wait_interval` chiamato solo DOPO il drain (non tra batch).
- Empty subito → un wait.
- Cancel durante drain e durante wait: task termina (comportamento attuale).
Esegui:
```bash
cd radar
docker compose exec -T radar-worker pytest app/tests/test_worker_shutdown.py -q
# oppure, se stack giù, pytest nel venv/container coerente col progetto — preferisci container.
```

## Docs / ECC / plan-audit (sweep obbligatorio, in place)
Messaggio canonico da propagare ovunque:
  webhook/NOTIFY = wake primario; drain-until-empty all’avvio e post-wake; 900s = safety net a coda vuota.

Aggiorna TUTTI questi se citano sleep-only / poll-only:
- `docs/01_getting_started.md`
- `docs/02_architecture_and_backend.md`
- `radar/docs/runbook.md` (drain, settle, webhook `http://radar-backend:8000/api/webhooks/miniflux`, “900s ≠ hang”)
- `radar/.env.example`
- `.agents/AGENTS.md` (rimuovi claim che il loop è solo `asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)`)
- `radar/.ecc/CLAUDE.md` (tabella + diagramma ingest)
- `radar/.ecc/rules/backend.md` (snippet loop + env table + `WORKER_REFRESH_SETTLE_SECONDS`)
- `radar/.ecc/agents/pipeline-engineer.md`
- `plan-audit/STATUS.md` (riga In corso → poi note verify)
- `plan-audit/README.md` (link piano + questo prompt)
- Nota breve in `plan-audit/complete/master_plan_impl_phase_B.md`: refinement drain post–Phase B; webhook resta

## Riavvio Docker + verifica funzionale (obbligatorio)
```bash
cd radar
docker compose up -d --build radar-worker
# se worker dipende da migrazioni/API già up, ok; altrimenti `docker compose up -d --build`
docker compose logs radar-worker --since 10m 2>&1 | tee /tmp/eager-drain-gate.log
```
Assert sui log:
1. All’avvio: refresh (e settle se >0) poi elaborazione continua; se c’è arretrato unread, N batch SENZA “Attesa wake NOTIFY o timeout poll” tra di essi.
2. A coda vuota: compare il log di attesa wake/timeout 900s (atteso, non errore).
3. Nessun Traceback nel ciclo.
4. Opzionale se `MINIFLUX_WEBHOOK_SECRET` settato: simula webhook (`python -m app.scripts.simulate_miniflux_webhook` da dentro rete/container come da script) → “Risveglio da radar_worker_trigger” + nuovo drain.

Skill `radar-docker-ops`: health live/ready; non usare `latest` tag inventati.

## Deliverable di chiusura (senza commit)
1. Codice + test verdi
2. Docs/ECC aggiornati
3. `/tmp/eager-drain-gate.log` (o path equivalente) citato nel report
4. Aggiorna `plan-audit/STATUS.md` con esito verify (GREEN/YELLOW + evidenza log)
5. Report breve al PO: file toccati, assert passati, eventuali gap (es. webhook Miniflux UI non configurato = ops, non codice)
6. NON spostare piano in `complete/` e NON spostare questo prompt in `done/` senza OK PO
7. NESSUN git commit / push

## Fuori scope
- Ridurre 900s di default
- Busy-poll
- Requeue distruttivo `--purge-all` (evitare; non necessario per questo GATE)
- Sidebar / FE
```

---

## Checklist PO (post-agente)

- [ ] Drain eager verificato su restart reale
- [ ] Docs/ECC senza drift sleep-only
- [ ] Prompt → `prompts/done/` + piano → `complete/` (solo su OK)
- [ ] Commit esplicito se/quando richiesto
