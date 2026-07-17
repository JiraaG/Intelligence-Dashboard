# Prompt — T-P0-02 REMEDIATION (ARCHIVIO — ticket DONE)

> **Stato:** T-P0-02 **DONE** (2026-07-16) — ibrido + stress path **b1**.  
> Report: `plan-audit/remediation/audit_remediation_T-P0-02.md`.  
> **Non rieseguire** questo prompt. Prossimo SoT: **T-P1-05** (T-P1-04 DONE).  
> Blocco sotto = storico orchestratore multi-agente (congelato).

> Analisi pregressa: `plan-audit/remediation/audit_remediation_T-P0-02.md` (§A–H, verifica Cursor PASS_WITH_GAPS).

```text
/goal Implementa T-P0-02 (script diagnostici / ClassificationClient) nel workspace
`c:\Users\lucag\Documents\Dashboard finance` secondo la decisione umana sotto.
Usa sotto-agenti specializzati (Task tool) in parallelo dove indipendenti; tu resti
orchestratore: integri, risolvi conflitti, esegui gate finale, aggiorni SoT.
NON commitare / NON pushare. NON toccare radar-sidebar/**. NON aprire T-P1-04/05/P2.
NON “chiudere” T-P2-04 in questo ticket.

========================================================================
## 0. Decisione umana (VINCOLANTE — non rinegoziare)
========================================================================

Policy: **Ibrido + path stress (b)**

| Area | Azione |
|------|--------|
| `scripts/diagnostics/test_500.py` | **Eliminare** (preferito) oppure lasciare stub senza `ClassificationClient()` / `_wait_for_rate_limit`. Solo spostare in `_obsolete/` **NON basta** se resta sotto `backend/scripts/**` e Script I è ricorsivo. |
| `scripts/diagnostics/test_rate_limiter.py` | Stesso trattamento di `test_500.py`. |
| `scripts/test_production_pipeline.py` | **Riparare** smoke: `ClassificationClient(quota=AsyncMock…)` in `main()`. **Rimuovere o neutralizzare** `stress_test_rate_limiter` (niente assert wall-clock `>= 3.9`, niente `_wait_for_rate_limit`, non chiamarlo da `main`). Timing RPM = `test_quota_concurrency.py`. |
| `app/tests/test_integration_live.py` | `test_live_rate_limiter_throttling` → `pytest.skip(...)` chiaro (motivo: stress path (b); throttling coperto offline). Rimuovere import morti se non più usati. |
| T-P2-04 (`test_500_bot.py` / `test_500_debug.py` bare `except:`) | **Fuori scope** — non modificare. |
| Priorità P0→P1 | **Non** declassare in SoT in questo turno (opzionale post-DONE, decisione umana separata). |

Skills: `.agents/skills/radar-quota-ledger` (anti-pattern: non reintrodurre sleep-only come unico gate).
SoT: `plan-audit/complete/plan_docs_audit_ticket_status.md`
Playbook: `plan-audit/complete/plan_docs_audit_playbook.md` §3.2 / §4.5 / Script I / App. F §F.2
Report: aggiorna `plan-audit/remediation/audit_remediation_T-P0-02.md` (passa da ANALISI ONLY a DONE + gate).

Branch tipico: `refactor/testing`. Gate: Phase 6 / Gate Verde.
Constraint: `main.py` API-only; asyncpg; non toccare worker/outbox/FE map salvo necessità zero.

========================================================================
## 1. Orchestratore — protocollo sotto-agenti
========================================================================

Lancia **tre** sotto-agenti specializzati. Preferisci parallelo A∥B; C solo dopo merge A+B
(oppure C in parallelo in sola lettura docs, poi scrittura dopo gate).

| ID | Tipo | Ruolo | Touch allowlist | Vietato |
|----|------|-------|-----------------|---------|
| **A** | `generalPurpose` o `shell` | **Diagnostics cleaner** | `radar/backend/scripts/diagnostics/test_500.py`, `…/test_rate_limiter.py` (+ delete/stub). Opzionale README `_obsolete` solo se serve. | `test_production_pipeline.py`, live tests, SoT DONE, `test_500_bot.py`, `test_500_debug.py` |
| **B** | `generalPurpose` | **Pipeline + live adapter** | `radar/backend/scripts/test_production_pipeline.py`, `radar/backend/app/tests/test_integration_live.py`. Opzionale nota in `radar/.ecc/agents/pipeline-engineer.md` se il comando manuale resta valido. | diagnostics orfani (A), SoT conteggi (C), client.py/quota.py produzione |
| **C** | `generalPurpose` | **Docs + Script I + gate** | `plan-audit/remediation/audit_remediation_T-P0-02.md`, `plan-audit/complete/plan_docs_audit_ticket_status.md` (§3 ticket + pie OPEN counts + § esito se esiste pattern §10–13), pezzi rilevanti di `plan-audit/complete/plan_docs_audit_playbook.md` (§3.2/§4.5 criteri spuntati / App. D se presente). Esegue gate comandi. | logica prodotto fuori script/test; commit |

**Regola conflitti:** se A e B toccano lo stesso file → FAIL orchestratore; non deve succedere.
**Regola Script I:** verifica solo su `*.py`; escludi `__pycache__` e `.pyc`.

Dopo A+B: orchestratore fa review diff unificata, poi avvia/completa C.

========================================================================
## 2. Prompt sotto-agente A — Diagnostics cleaner
========================================================================

Copia questo blocco nel Task A:

```
Obiettivo T-P0-02-A: rimuovere i pattern rotti dagli script diagnostici orfani.

Workspace: c:\Users\lucag\Documents\Dashboard finance
File target:
- radar/backend/scripts/diagnostics/test_500.py
- radar/backend/scripts/diagnostics/test_rate_limiter.py

Policy: ELIMINA i due file (preferito). Se per qualche motivo non puoi delete,
sostituisci il contenuto con uno stub che:
  - non importa ClassificationClient
  - non chiama _wait_for_rate_limit
  - stampa/logga "OBSOLETE: use test_classification.py / test_quota_concurrency.py"
  - exit 0 o SystemExit con messaggio chiaro

NON creare _obsolete/ con gli stessi pattern dentro backend/scripts (Script I
ricorsivo li ritroverebbe). NON toccare test_500_bot.py / test_500_debug.py (T-P2-04).

Verifica locale A:
Get-ChildItem radar/backend/scripts/diagnostics -Filter *.py -Recurse |
  Where-Object { $_.FullName -notmatch '__pycache__' } |
  Select-String -Pattern 'ClassificationClient\(\)|_wait_for_rate_limit'

Atteso: zero match nei due file target (file assenti o stub puliti).
Restituisci all’orchestratore: lista file deleted/edited + output grep.
No commit.
```

========================================================================
## 3. Prompt sotto-agente B — Pipeline + live adapter (path b)
========================================================================

Copia questo blocco nel Task B:

```
Obiettivo T-P0-02-B: riparare smoke pipeline e allineare live test a path stress (b).

Workspace: c:\Users\lucag\Documents\Dashboard finance
Skills: .agents/skills/radar-quota-ledger (non reintrodurre _wait_for_rate_limit).

### B1 — test_production_pipeline.py
1. In main(): sostituire ClassificationClient() con helper locale, es.:
   - AsyncMock quota con reserve → id int; complete/release/fail no-op
   - ClassificationClient(quota=mock_quota)
   Pattern di riferimento: app/tests/test_integration_live.py::_live_classification_client
2. Path stress (b) — SCEGLI UNA implementazione coerente (preferita nell’ordine):
   (b1) Eliminare stress_test_rate_limiter e la chiamata da main(); aggiornare docstring/log STEP.
   (b2) Lasciare la funzione ma farla pytest.skip/raise RuntimeError("obsolete") /
        oppure no-op documentato SENZA assert timing e SENZA _wait_for_rate_limit;
        main() NON la chiama.
3. Nessun ClassificationClient() senza argomenti. Nessun _wait_for_rate_limit.
4. test_external_connections / e2e restano; non rompere require_live_tests_enabled().

### B2 — test_integration_live.py
1. test_live_rate_limiter_throttling: primo statement utile = pytest.skip(
   "T-P0-02 path b: throttling coperto da test_quota_concurrency; stress pipeline rimosso/neutralizzato"
   )
2. Rimuovere import di stress_test_rate_limiter se inutilizzato.
3. Non cambiare _live_classification_client per gli altri test live (connections/e2e).

### B3 — Opzionale
Se pipeline-engineer.md dice ancora di lanciare lo script: lascia il comando;
aggiungi una riga che lo smoke non include più stress RPM (coperto da test_quota_concurrency).

Verifica locale B (statica):
Select-String su quei due file per ClassificationClient() e _wait_for_rate_limit → 0 match.
Restituisci: diff summary + scelta b1/b2. No commit. Non toccare diagnostics (agente A).
```

========================================================================
## 4. Prompt sotto-agente C — Docs + Script I + gate
========================================================================

Copia questo blocco nel Task C (dopo merge A+B, o in due fasi: gate poi docs):

```
Obiettivo T-P0-02-C: gate FASE 5 + allineamento SoT. Workspace come sopra.

### C1 — Script I (obbligatorio, solo *.py)
cd radar
$env:PYTHONPATH = "backend"
# ctor vuoto: post-fix deve ancora fallire se qualcuno lo chiama così (API corretta);
# non è un fail del ticket. Il gate ticket è l’assenza di call sites rotti negli script.
Get-ChildItem -Path backend/scripts -Recurse -Filter *.py |
  Where-Object { $_.FullName -notmatch '__pycache__' } |
  Select-String -Pattern 'ClassificationClient\(\)|_wait_for_rate_limit'
# Atteso: ZERO match.

### C2 — Lint + pytest offline
cd radar
ruff check backend/scripts/test_production_pipeline.py backend/app/tests/test_integration_live.py
# + path toccati da A se stub rimasti
$env:PYTHONPATH = "backend"
pytest -m "not live" -q
# Atteso: stesso ordine di grandezza di prima (115+; non regressione). Conta esatto e riportalo.

### C3 — Live throttling (opzionale smoke)
$env:RUN_LIVE_TESTS = "1"
pytest backend/app/tests/test_integration_live.py::test_live_rate_limiter_throttling -m live -o addopts= -v
# Atteso: SKIPPED (non FAILED AttributeError).

### C4 — Docs SoT
Aggiorna:
- plan-audit/remediation/audit_remediation_T-P0-02.md → stato DONE, policy ibrido+(b), gate table, handoff T-P1-04
- plan-audit/complete/plan_docs_audit_ticket_status.md §3: T-P0-02 DONE; pie P0 OPEN=0;
  OPEN totali coerenti; §5 ordine; nuova § esito tipo §14 se il doc segue quel pattern
- plan-audit/complete/plan_docs_audit_playbook.md: §3.2/§4.5 come AS-IS storico + criteri spuntati;
  App. D / handoff log se presenti
- plan-audit/prompts/done/audit_prompt_T-P0-02.md: marca ANALISI archiviata; punta a questo remediation DONE

Non declassare P0→P1. Non commit. Restituisci tabella gate PASS/FAIL + conteggio pytest.
```

========================================================================
## 5. DoD orchestratore (firma prima di dichiarare DONE)
========================================================================

- [ ] Zero match Script I su `backend/scripts/**/*.py` (no pycache)
- [ ] Nessun `ClassificationClient()` senza args nei path riparati
- [ ] Nessun `_wait_for_rate_limit` nel tree scripts + test_integration_live
- [ ] `stress_test_rate_limiter` assente da `main()` oppure obsolete senza timing assert
- [ ] `test_live_rate_limiter_throttling` → skipped
- [ ] `pytest -m "not live"` verde (riportare N passed)
- [ ] ruff OK sui file toccati
- [ ] SoT §3 T-P0-02 = DONE; report remediation aggiornato; handoff **T-P1-04**
- [ ] T-P2-04 file non modificati
- [ ] Nessun commit/push

### Output finale orchestratore (italiano)
1. Verdetto: PASS / PASS_WITH_GAPS / FAIL
2. Tabella file touched (A/B/C)
3. Scelta b1 vs b2
4. Esiti gate (Script I, ruff, pytest N, live skip)
5. Diff conteggi OPEN SoT
6. Handoff one-liner T-P1-04
7. Eventuali gap residui (senza inventare work)

Se FAIL: non marcare DONE; elenca fix mancanti.
```
