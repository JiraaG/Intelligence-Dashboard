# Prompt — T-P0-02 (DONE — archivio)

> **Stato:** **DONE** (2026-07-16).  
> Report: `plan-audit/audit_remediation_T-P0-02.md`.  
> **Remediation:** completata con successo tramite design path ibrido (opzione stress path **b**).  
>
> Blocco sotto = storico FASE 3 only (non usare per implementare).

```text
/goal Analizza il ticket T-P0-02 (script diagnostici / ClassificationClient) nel workspace
`c:\Users\lucag\Documents\Dashboard finance`. Solo analisi e raccomandazione — NON implementare
il fix, NON deprecare file, NON commitare, NON pushare.

---

## Contesto progetto

- Repo: `c:\Users\lucag\Documents\Dashboard finance` · app `radar/`
- Branch tipico: `refactor/testing` (tracking `origin/refactor/testing`)
- Gate progetto: Phase 6 / Gate Verde
- SoT ticket: `plan-audit/audit_problemi_documentazione_risoluzione.md` §3 / §4 / §5
- Playbook: `plan-audit/audit_problemi_documentazione.md` §3.2 / §4.5 / Script I / App. F §F.2
- Skills utili: `.agents/skills/llm-json-extraction`, `.agents/skills/radar-quota-ledger`
- Constraint: `main.py` API-only; asyncpg; non toccare `radar-sidebar/**`

## Stato coda remediation

DONE (non riaprire): T-P0-01, T-P1-03, T-P1-01, T-P1-02, T-DOC-01.
OPEN prossimo: **T-P0-02** → poi T-P1-04 → T-P1-05 → P2.

Handoff one-liner: *Script diagnostici: `ClassificationClient()` senza pool + `_wait_for_rate_limit` rimosso — riparare o deprecare.*

Priorità: scratch P1 elevato a **P0** (App. F §F.2). Se si depreca invece di riparare, si può ridiscendere a P1 — solo con decisione umana esplicita.

---

## Ticket T-P0-02 — cosa verificare

Finding: BE-AUD-005/006 merge.
Sintomi attesi AS-IS:

1. `ClassificationClient()` senza `pool=` / `quota=` → `ValueError: ClassificationClient richiede pool (asyncpg) o un QuotaLedger iniettato.`
2. Chiamate a `client._wait_for_rate_limit()` / `classification._wait_for_rate_limit()` su API **rimossa** → `AttributeError` (il gate live è `QuotaLedger.reserve`).
3. Cascata: `app/tests/test_integration_live.py` (marker `live`) importa `stress_test_rate_limiter` da `scripts/test_production_pipeline.py` → live rate-limiter inutilizzabile anche se il client live è costruito correttamente con mock quota.

File sospetti (conferma con grep, non assumere lista completa):

- `radar/backend/scripts/test_production_pipeline.py` — `ClassificationClient()` + `_wait_for_rate_limit` in `stress_test_rate_limiter` / `main`
- `radar/backend/scripts/diagnostics/test_rate_limiter.py` — stesso pattern
- `radar/backend/scripts/diagnostics/test_500.py` — `ClassificationClient()` vuoto
- `radar/backend/app/tests/test_integration_live.py` — import stress + helper `_live_classification_client()` (già corretto con `quota=`)

Contratto corretto (produzione / test):

- Worker: `ClassificationClient(pool=state.db_pool)` in `worker.py`
- Unit/live helper: `ClassificationClient(quota=...)` (vedi `test_classification.py`, `test_integration_live.py`)
- Quota: `reserve` / `complete` / `fail` / `release` — **non** `_wait_for_rate_limit`

Playbook §4.5 Opzioni (solo raccomandare, non applicare):

- **Opzione A (riparare):** pool/QuotaLedger + stress basato su `quota.reserve`/`release` (o allineamento a helper live).
- **Opzione B (deprecare):** spostare sotto `scripts/diagnostics/_obsolete/` + skip chiaro nei live test, oppure eliminare path morto.

---

## Compito (FASE 3 only)

1. **Riproduzione Script I** (PowerShell, da `radar/`):

```powershell
cd radar
$env:PYTHONPATH = "backend"
python -c "from app.classification.client import ClassificationClient; ClassificationClient()"
Select-String -Path backend/scripts -Pattern "ClassificationClient\(\)|_wait_for_rate_limit" -Recurse
```

Registra: eccezione esatta, file:line match, eventuali falsi positivi.

2. **Mappa dipendenze:**
   - Chi importa gli script rotti? (`test_integration_live`, CI, docs, ECC?)
   - Quali path live falliscono oggi e perché (`AttributeError` vs `ValueError` vs altro)?
   - Esiste già un pattern riparato in `test_integration_live._live_classification_client` / `test_quota_concurrency` da riusare?

3. **Inventario file:**
   - Tabella: path | uso (ops/CI/live/orphaned) | bug (ctor vuoto / API rimossa / entrambi) | impatto se deprecato.

4. **Raccomandazione A vs B** con criteri espliciti:
   - Valore operativo residuo degli script
   - Costo allineamento a QuotaLedger durable
   - Impatto su `pytest -m live` / Gate Verde
   - Se B: cosa fare di `test_live_rate_limiter_throttling` (skip? riscrivere su reserve? cancellare?)

5. **DoD proposto** (checklist, non eseguita):
   - Nessun `ClassificationClient()` senza argomenti sotto `backend/scripts`
   - Nessun `_wait_for_rate_limit`
   - Script I pulito post-fix
   - Live path coerente o skip esplicito documentato
   - Docs SoT: §3 T-P0-02 + App. D + conteggi OPEN

6. **Fuori scope (non toccare in analisi né in fix successivo senza nuovo ticket):**
   - T-P1-04 / T-P1-05 / P2
   - `radar-sidebar/**`
   - Logica worker/outbox già DONE
   - Commit/push

---

## Output obbligatorio

Rispondi in italiano, strutturato:

### A. Verdetto analisi
`CONFIRMED` / `PARTIAL` / `NOT_REPRO` + una frase.

### B. Evidenze FASE 3
Comandi eseguiti, traceback/match, file:line.

### C. Inventario impatto
Tabella file × bug × consumatori.

### D. Raccomandazione
**A riparare** | **B deprecare** | **Ibrido** — motivazione in ≤5 bullet.  
Se ibrido: quali file riparare, quali deprecare.

### E. Design sketch (non codice completo)
Passi concreti per l’opzione scelta (API da usare, dove iniettare pool/quota, cosa cambia in live test).

### F. Rischi / decisioni umane
Es. abbassare a P1 se solo deprecazione; bisogno di `GOOGLE_API_KEY` / DB per gate live; overlap con T-P2-04 (`test_500_*` except nudo).

### G. Prompt remediation (bozza 5–10 righe)
Blocco pronto da incollare nel turno successivo per implementare FASE 4+5.

Non creare commit. Se scrivi un report file, usa `plan-audit/audit_remediation_T-P0-02.md` con header **ANALISI ONLY — remediation pending**.
```
