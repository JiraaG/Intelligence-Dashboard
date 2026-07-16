# Piano Operativo — Final Release Gate

> **Stato premesse (2026-07-16):** remediation codice P0–P2 **CLOSED**; Phase 6 GATE VERDE; smoke UI manuale **fatto**; commit/push su `refactor/testing` @ `7bb8ed8`.  
> **Scopo di questo documento:** piano definitivo per i residui Final Release + deferred, con procedure, file, pro/contro e scelta raccomandata.  
> **SoT correlati:** `plan_impl_phase_0_6.md` §Final Release Gate · `audit_remediation_final_release_handoff.md` · `radar/ops/README.md` · `radar/docs/runbook.md` · `radar/.ecc/rules/docker.md`

---

## 0. Cosa è già chiuso (non rifare)

| Area | Evidenza |
|------|----------|
| Ticket SoT P0/P1/P2 | 0 OPEN — `plan_docs_audit_ticket_status.md` §3 |
| Unit/integration offline | pytest `not live` ~117; FE typecheck + test:ci 30 |
| Docs/ECC vs deploy | Phase 6 + remediation docs CLOSED |
| Smoke UI letta + spiderfy | Eseguito dall’utente post-rebuild |
| Commit + push branch | `refactor/testing` → `origin` @ `7bb8ed8` |

**Non in scope di questo piano:** nuove feature prodotto; touch `radar-sidebar/**`; riaprire ticket remediation.

---

## 1. Mappa fasi (ordine raccomandato)

```text
Fase 0  PR (senza merge automatico)
   ↓
Fase 1  Backup / restore drill          ← valore ops più alto, script pronti
   ↓
Fase 2  Seed 10k + misura budget        ← DB isolato / data dedicata
   ↓
Fase 3  Chaos kill/restart pipeline     ← dopo backup fresco
   ↓
Fase 4  SAST / image scan / XSS spot    ← security release
   ↓
Fase 5  Deferred: digest pin + legacy-peer-deps  ← decisione prodotto (default: TENERE deferred)
```

**Perché questo ordine**

1. **PR prima** — rende reviewabile lo stato già green senza mischiare drill ops.  
2. **Backup/restore subito** — protegge i dati prima di chaos/seed aggressivi.  
3. **Seed 10k** — misura perf su volume; meglio su data dedicata o stack usa-e-getta.  
4. **Chaos dopo backup** — se qualcosa va storto, restore è già dimostrato.  
5. **SAST/scan** — indipendente, può parallelizzarsi con 2–3 se l’orchestratore ha capacità.  
6. **Deferred** — non bloccano release; chiudere solo con decisione esplicita.

| Parallelizzabile? | Note |
|-------------------|------|
| Fase 4 ∥ Fase 2 | Sì, se seed non satura CPU/IO sulla stessa macchina dello scan |
| Fase 3 vs 2 | No sullo stesso DB: chaos + seed 10k insieme confondono i risultati |
| Fase 5 | Solo dopo decisione umana; non “di default” nello stesso turno |

---

## 2. Fase 0 — Pull Request (processo)

### Obiettivo
Aprire PR `refactor/testing` → `develop` (o base scelta) **senza merge** finché non richiesto.

### File / tool
- Branch: `refactor/testing` @ `7bb8ed8+`
- Tool: `gh pr create`
- Handoff: `plan-audit/remediation/audit_remediation_final_release_handoff.md` §D voce 2

### Procedura
```powershell
cd "c:\Users\lucag\Documents\Dashboard finance"
git status -sb   # working tree clean
git push -u origin HEAD
gh pr create --base develop --head refactor/testing --title "…" --body "…"
```

### Body PR suggerito
- Summary: chiusura remediation P2 + handoff Final Release; P0–P2 DONE  
- Test plan: pytest not live; FE test:ci; smoke UI; Compose healthy  
- Non-goals: merge; chaos/SAST/seed (follow-up)

### Pro / contro

| Pro | Contro |
|-----|--------|
| Review umana prima di fondere in `develop` | `develop` può essere molto indietro → PR grande |
| Traccia CI GitHub se attiva | Merge conflict possibili vs `develop` |

### Scelta migliore
**Aprire PR senza merge.** Risolvere eventuali conflitti in branch dedicato solo se `gh` li segnala.

---

## 3. Fase 1 — Backup / restore drill

### Obiettivo
Dimostrare che backup e restore funzionano end-to-end (criterio Final Release ancora `[ ]` in `plan_impl_phase_0_6.md`).

### File e codice
| Path | Ruolo |
|------|--------|
| `radar/ops/backup-postgres.sh` | `pg_dump -Fc` + `vault.tar.gz` + `SHA256SUMS` + retention |
| `radar/ops/restore-postgres.sh` | Verifica checksum → stop worker/backend → `pg_restore --clean` → opz. vault → restart |
| `radar/ops/README.md` | Manuale EN ops |
| `radar/docs/runbook.md` §Backup/restore | Manuale IT incident/upgrade |
| `radar/docker-compose.yml` | Volume `./data/postgres`, bind `./vault` |
| Output | `radar/backups/<UTC-stamp>/` (**gitignored** — non commitare dump) |

### Best practice
- Eseguire script da **Git Bash o WSL**, non PowerShell raw (`ops/README.md`).  
- Preferire drill su **stack usa-e-getta** o almeno backup fresco **prima** di restore.  
- Controllare warning outbox `pending`/`writing` nel backup (crash-consistent, non cross-FS atomico).  
- Post-restore: attendere reconcile worker; verificare `/health/live` e un `GET /api/map-summary`.  
- Se CRLF sui `.sh`: `sed -i 's/\r$//' ops/*.sh`.

### Procedura (happy path Windows)

```bash
# Git Bash, da radar/
cd "/c/Users/lucag/Documents/Dashboard finance/radar"
docker compose ps
./ops/backup-postgres.sh
# Annotare STAMP stampato a video → DEST=./backups/<STAMP>

# Opzione A (consigliata): restore sulla stessa stack SOLO dopo secondo backup di sicurezza
./ops/backup-postgres.sh   # safety net
./ops/restore-postgres.sh ./backups/<STAMP>
# oppure con vault:
# ./ops/restore-postgres.sh ./backups/<STAMP> --with-vault

docker compose ps
docker compose exec radar-backend curl -sf http://127.0.0.1:8000/health/live
# Smoke: UI http://localhost/ + map-summary
```

### Criteri di PASS
- [ ] Directory backup con `.dump`, `SHA256SUMS`, (opz.) `vault.tar.gz`  
- [ ] Restore completa senza errore fatale  
- [ ] Servizi: db/backend/frontend/miniflux **healthy**; worker **running**  
- [ ] API live OK; UI carica; dati attesi presenti (o documentare delta outbox)

### Pro / contro

| Pro | Contro |
|-----|--------|
| Script già production-ready | Restore **distruttivo** sul DB live |
| Copre il rischio P3 “corruzione dati” del runbook | Su Windows richiede Bash/WSL |
| Abilita chaos successivo in sicurezza | Vault replace (`--with-vault`) sovrascrive file Obsidian locali |

### Scelta migliore
**Eseguire backup + restore drill sulla stack di sviluppo corrente**, con doppio backup (pre-restore safety). Usare `--with-vault` solo se si vuole validare anche il vault; altrimenti restore DB-only è sufficiente per il gate minimo.  
**Non** usare il DB di “produzione personale” senza safety backup.

### Report
Aggiornare `plan-audit/remediation/audit_remediation_final_release_F1_backup.md` (nuovo) + spuntare item in `plan_impl_phase_0_6.md` Final Release Gate se PASS.

---

## 4. Fase 2 — Seed 10k + misura budget

### Obiettivo
Caricare ~10 000 articoli sintetici per **una** `published_at` e misurare tempi query / UX mappa (criterio Phase 5 / Final Release).

### File e codice
| Path | Ruolo |
|------|--------|
| `radar/backend/scripts/seed_perf_articles.py` | Seed idempotente SQL (DELETE date + INSERT); **non** tocca vault/Miniflux |
| Migrazione indici | `radar/backend/migrations/007_*.sql` (già applicata in Phase 5) |
| API sotto test | `GET /api/map-summary?date=…`, `GET /api/articles?date=&country=` |
| Manuale | `plan_impl_phase_0_6.md` D8 / Phase 5 residuals |

### Best practice
- Usare una **data dedicata** (es. `2099-01-01` o giorno non usato in UI) per non inquinare la day-view “oggi”.  
- Preferibile DB isolato / volume usa-e-getta se i dati reali contano.  
- Misurare **prima** e **dopo** indici (già presenti): almeno `EXPLAIN (ANALYZE, BUFFERS)` su aggregazioni map-summary.  
- Non lanciare seed mentre chaos è in corso.  
- Dopo la misura: opzionale delete della data seed o lasciare documentato.

### Procedura

```powershell
cd "c:\Users\lucag\Documents\Dashboard finance\radar"
# Opzione: eseguire nello stesso network del compose
# DATABASE_URL verso postgres esposto o via docker compose exec

# Esempio via container backend (adatta env già presenti):
docker compose exec -T radar-backend python -m scripts.seed_perf_articles --date 2099-01-01 --count 10000
# Se lo script è invocato come file path, seguire docstring in seed_perf_articles.py
```

**Misura minima (documentare numeri):**

```sql
-- Via: docker compose exec radar-db psql -U radar_user -d radar_db
EXPLAIN (ANALYZE, BUFFERS)
SELECT country_code, primary_category, count(*)
FROM articles
WHERE published_at = DATE '2099-01-01'
GROUP BY 1, 2;

EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) FROM articles WHERE published_at = DATE '2099-01-01';
```

**UX smoke (FE):** aprire UI con date picker sulla data seed; verificare day-view pin nazione (non 10k marker); aprire una nazione (pagination articles ≤100/page).

### Budget / criteri PASS (pragmatici)
Il piano master non fissa ms assoluti nel testo Final Release; usare soglie **ragionevoli locali** e documentarle:

| Check | Atteso indicativo |
|-------|-------------------|
| Seed completa | < ~2–5 min su laptop tipico |
| EXPLAIN aggregazione map-summary | usa indici `idx_articles*`; niente seq scan full table se evitabile |
| Day-view FE | UI usabile; marker = summary pins, non 10k Leaflet markers |
| Nation open | pagine concatenate; nessuna unbounded explosion DOM mappa |

### Pro / contro

| Pro | Contro |
|-----|--------|
| Script pronto e idempotente per data | Cancella **tutti** gli articoli di quella data prima del seed |
| Valida indici Phase 5 sotto carico | Su DB “reale” può far crescere il volume disco |
| Non consuma quota Gemini | Non simula carico Miniflux/LLM |

### Scelta migliore
**Seed su data dedicata `2099-01-01` sul DB di sviluppo**, misurare EXPLAIN + smoke FE, documentare in `plan-audit/remediation/audit_remediation_final_release_F2_seed10k.md`.  
Non cancellare i dati di produzione/giornalieri. Opzionale: dopo PASS, `DELETE FROM articles WHERE published_at = '2099-01-01'` per liberare spazio.

---

## 5. Fase 3 — Chaos kill/restart pipeline

### Obiettivo
Verificare che kill/restart in punti critici non causino **perdita articoli** né **mark-read prematuro** (gate Final Release).

### Codice / invarianti da rispettare (già implementati)
| Area | File | Invariante |
|------|------|------------|
| Mark-read gate | `radar/backend/app/worker.py` | Dup: mark-read solo se outbox `completed` o vault file esiste (T-P0-01) |
| Outbox retry | `radar/backend/app/commit/outbox.py` | Retry `miniflux_marked_at` (T-P1-03) |
| Leadership | `worker.py` | `pg_try_advisory_lock` — un solo leader |
| Quota 429 | `classification/client.py` + `quota.py` | Rispetta Retry-After; ledger durable |
| Cancel | worker loop | `CancelledError` re-raise |

### Scenario matrix (minimo viable chaos)

| # | Azione | Quando | Atteso |
|---|--------|--------|--------|
| C1 | `docker compose restart radar-worker` | Durante poll / classify | Riparte; lock ripreso; no mark-read su pending |
| C2 | `docker compose kill radar-worker` + `up -d` | Mid-ciclo | Outbox `pending`/`writing` riconciliati; warning ok |
| C3 | `docker compose restart radar-db` | Breve | Backend `init_pool` retry (OPS-FIX); servizi healthy |
| C4 | Stop Miniflux breve | Durante mark-read | Outbox resta retryable; no ack fantasma |
| C5 | Observare 429 Gemini | Naturale sotto quota | Attesa Retry-After; nessun crash demone |

### Best practice
- **Backup fresco (Fase 1) obbligatorio prima di C2–C4.**  
- Un scenario alla volta; annotare `article_outbox.status` e `last_error`.  
- Non interpretare 429 come FAIL chaos (è comportamento corretto).  
- Sidebar freeze: nessun fix UI in questa fase.

### Procedura esempio C1

```powershell
cd "c:\Users\lucag\Documents\Dashboard finance\radar"
docker compose logs -f --tail 20 radar-worker
# in un altro terminale, mentre classifica:
docker compose restart radar-worker
docker compose logs --tail 40 radar-worker
docker compose exec radar-db psql -U radar_user -d radar_db -c "SELECT status, count(*) FROM article_outbox GROUP BY 1;"
```

### Criteri PASS
- [ ] Nessun articolo “perso” (URL in DB senza percorso di recovery)  
- [ ] Nessun mark-read Miniflux senza vault/`completed` (spot-check log + outbox)  
- [ ] Worker riprende leadership; demone vivo  
- [ ] Report con esito per C1–C5 (SKIP ammesso se precondizione assente, es. no Miniflux entries)

### Pro / contro

| Pro | Contro |
|-----|--------|
| Valida il cuore del design crash-safe | Può lasciare outbox sporca temporaneamente |
| Usa solo Compose — zero codice nuovo | Difficile da automatizzare al 100% senza harness |
| Alta fiducia pre-merge | Tempo umano + attenzione |

### Scelta migliore
Eseguire **C1 + C2 + C3** come minimo; C4 se Miniflux ha traffico; C5 opportunistico. Documentare in `plan-audit/remediation/audit_remediation_final_release_F3_chaos.md`.  
**Non** fare `docker compose down -v` (distrugge volume DB).

---

## 6. Fase 4 — SAST / image scan / XSS spot

### Obiettivo
Chiudere il criterio security Final Release in modo **pragmatico** (CSP e secret-grep CI già parziali).

### Cosa c’è già
| Controllo | Dove |
|-----------|------|
| CSP headers | Nginx / Phase 3 |
| Secret grep CI | `.github/workflows/ci.yml` (se presente) |
| XSS marker | FE `createSafeMarkerIcon` / test map (Phase 4) |

### Cosa manca tipicamente
| Controllo | Tool consigliato | Target |
|-----------|------------------|--------|
| Image CVE scan | **Trivy** (o Docker Scout) | `postgres:15-alpine`, `miniflux/miniflux:2.3.2`, immagini build `radar-radar-*`, `nginx:1.27-alpine`, `python:3.12-slim`, `node:22-alpine` |
| Dependency scan BE | `pip-audit` o `safety` nel venv | `radar/backend/app/requirements.txt` |
| Dependency scan FE | `npm audit --omit=dev` (informativo) | `radar/frontend/package-lock.json` |
| SAST Python light | `ruff` / bandit (se disponibile) | `radar/backend/app` |
| XSS manual spot | Browser | Marker title/summary con `<script>`, banner errori |

### Best practice
- Trivy in modalità **report**, fail policy: bloccare solo **CRITICAL** fixabili; documentare HIGH accettati.  
- Non committare report enormi binari; salvare summary markdown in `plan-audit/`.  
- `npm audit` su Angular legacy peer può essere rumoroso — non elevare a P0 senza exploit path.  
- XSS: input via mock/DB di test, non dipendere da Gemini.

### Procedura minima

```powershell
# Esempio Trivy (se installato)
trivy image postgres:15-alpine
trivy image miniflux/miniflux:2.3.2
trivy image radar-radar-backend:latest
trivy image radar-radar-frontend:latest

# pip-audit (venv backend)
cd radar/backend
.\.venv\Scripts\Activate.ps1
pip-audit -r app/requirements.txt

# XSS spot: UI con articolo dal titolo contenente <img onerror=...>
# Atteso: testo escaped / textContent — nessuno script eseguito
```

### Pro / contro

| Pro | Contro |
|-----|--------|
| Riduce sorprese CVE pre-release | False positive / backlog vulnerabilità base image |
| Allinea a “release hygiene” | Richiede tool installati (Trivy non è nel repo) |
| XSS spot valida path FE reale | Non sostituisce pentest |

### Scelta migliore
**Trivy sulle 4–6 immagini chiave + pip-audit + XSS spot manuale (15 min).**  
Non bloccare la PR su HIGH di immagini Alpine non sfruttabili; documentare accettazione.  
Report: `plan-audit/remediation/audit_remediation_final_release_F4_security.md`.

---

## 7. Fase 5 — Deferred prodotto (digest pin & `--legacy-peer-deps`)

Questi **non** sono FAIL e **non** sono ticket SoT. Sono scelte di riproducibilità build.

### 5.A Digest pin immagini SHA

**Cosa:** sostituire `image: postgres:15-alpine` / `miniflux/miniflux:2.3.2` (e `FROM` nei Dockerfile) con `image@sha256:…`.

**File toccati (se si fa):**
- `radar/docker-compose.yml`
- `radar/frontend/Dockerfile`, `radar/backend/Dockerfile`
- `radar/.ecc/rules/docker.md`, skill `radar-docker-ops`, `.agents/AGENTS.md`

| Pro | Contro |
|-----|--------|
| Rebuild bit-identici; niente drift silenzioso del tag | Manutenzione: ogni patch Alpine richiede bump digest |
| Audit supply-chain più forte | Compose meno leggibile; onboarding più pesante |

**Scelta migliore oggi:** **TENERE DEFERRED.** Tag major/minor pinnati (`15-alpine`, `2.3.2`, `1.27-alpine`) bastano post–Phase 6. Attivare digest solo se requisiti compliance/supply-chain espliciti.

---

### 5.B Drop `--legacy-peer-deps`

**Cosa:** far passare `npm ci` **senza** flag nel Dockerfile FE e in locale.

**Perché oggi serve:** matrix disallineata — es. `@angular/*` ^21 vs `@angular/cdk` ^17 vs `primeng` ^17 (`package.json`).

**File:**
- `radar/frontend/Dockerfile` (`RUN npm ci --legacy-peer-deps`)
- `radar/frontend/package.json` / lockfile
- `radar/.ecc/rules/frontend.md` Regola 9, `docker.md`, skill docker-ops

| Pro | Contro |
|-----|--------|
| Peer tree “pulito”; meno warning npm | Richiede upgrade coordinato CDK/PrimeNG → Angular 21 |
| Allinea a best practice npm moderne | Alto rischio regressione UI (carousel PrimeNG) |

**Scelta migliore oggi:** **NON droppare.** Piano futuro dedicato:
1. Allineare `@angular/cdk` e `primeng` a major compatibile con Angular 21  
2. `npm ci` senza flag in branch di prova  
3. suite FE + smoke carousel (sidebar freeze: solo osservazione)  
4. poi aggiornare Dockerfile + rules

---

## 8. Matrice decisioni (executive)

| Item | Fare ora? | Scelta raccomandata |
|------|-----------|---------------------|
| PR → develop | **Sì** | Aprire, **non** merge auto |
| Backup/restore | **Sì** | Drill DB (+ vault opz.) su stack dev con safety backup |
| Seed 10k | **Sì** (o subito dopo backup) | Data `2099-01-01` + EXPLAIN + smoke FE |
| Chaos | **Sì** dopo backup | C1–C3 minimi |
| SAST/scan | **Sì** (anche //) | Trivy + pip-audit + XSS spot |
| Digest pin | **No** | Deferred fino a requisito compliance |
| Drop legacy-peer-deps | **No** | Deferred fino ad allineamento matrix |

---

## 9. Deliverable per fase

| Fase | Artefatto |
|------|-----------|
| 0 | URL PR GitHub |
| 1 | `plan-audit/remediation/audit_remediation_final_release_F1_backup.md` |
| 2 | `plan-audit/remediation/audit_remediation_final_release_F2_seed10k.md` |
| 3 | `plan-audit/remediation/audit_remediation_final_release_F3_chaos.md` |
| 4 | `plan-audit/remediation/audit_remediation_final_release_F4_security.md` |
| 5 | Nota decisione in handoff / `docker.md` (se si conferma deferred) |
| Fine | Aggiornare `plan_impl_phase_0_6.md` Final Release checkbox + `audit_remediation_final_release_handoff.md` |

---

## 10. Vincoli operativi (tutte le fasi)

- Sidebar freeze: zero edit `radar/frontend/src/app/components/radar-sidebar/**`  
- `main.py` API-only; ingest solo `worker.py`  
- No commit di `backups/`, `.env`, dump, vault content  
- Commit/push solo su richiesta utente (tranne se il prompt di fase lo autorizza esplicitamente)  
- Worker: `healthy` non atteso — stato corretto = **running** (`healthcheck: disable: true`)

---

## 11. Definizione di “Final Release COMPLETE”

**Minimum viable release (consigliato):**
- Fase 0 PR aperta  
- Fase 1 PASS  
- Fase 2 PASS (misure documentate)  
- Smoke UI già fatto  

**Full gate (piano master):**
- Minimum + Fase 3 PASS + Fase 4 PASS  
- Fase 5 esplicitamente **DEFERRED accettato** (o eseguita)

---

*Documento creato 2026-07-16 — post smoke UI e push `7bb8ed8`.*
