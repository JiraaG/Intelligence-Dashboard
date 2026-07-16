# Audit Report — Ticket T-P0-02: Script Diagnostici / ClassificationClient

> **Stato ticket:** **DONE** (2026-07-16) — codice/gate **PASS**; drift SoT manuale chiuso in riverifica Cursor  
> **Repo:** `c:\Users\lucag\Documents\Dashboard finance` · app `radar/`  
> **SoT ticket:** `plan-audit/active/audit_problemi_documentazione_risoluzione.md` §3 / §4 / §5  
> **Playbook:** `plan-audit/active/audit_problemi_documentazione.md` §3.2 / §4.5 / Script I / App. F §F.2  
> **Skills di riferimento:** `.agents/skills/llm-json-extraction`, `.agents/skills/radar-quota-ledger`

---

## A. Verdetto analisi
**`CONFIRMED`** — È stato confermato che il costruttore di `ClassificationClient` fallisce immediatamente con `ValueError` se istanziato senza parametri (cosa che avviene in tre script diagnostici/test di produzione) e che le chiamate al vecchio metodo `_wait_for_rate_limit` (ora rimosso in favore di `QuotaLedger.reserve`) sollevano `AttributeError` bloccando sia gli script standalone che i test di integrazione live (`test_live_rate_limiter_throttling`).

---

## B. Evidenze FASE 3 (Riproduzione)

### 1. Eccezione esatta sul Costruttore Vuoto (`ValueError`)
Eseguendo da `radar/`:
```powershell
$env:PYTHONPATH="backend"
python -c "from app.classification.client import ClassificationClient; ClassificationClient()"
```
Si ottiene il seguente traceback:
```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from app.classification.client import ClassificationClient; ClassificationClient()
                                                                ~~~~~~~~~~~~~~~~~~~~^^
  File "C:\Users\lucag\Documents\Dashboard finance\radar\backend\app\classification\client.py", line 254, in __init__
    raise ValueError("ClassificationClient richiede pool (asyncpg) o un QuotaLedger iniettato.")
ValueError: ClassificationClient richiede pool (asyncpg) o un QuotaLedger iniettato.
```

### 2. Match di codice individuati (File:Line Match)
Tramite scansione ricorsiva su `backend/scripts`, sono stati isolati i seguenti utilizzi del costruttore vuoto `ClassificationClient()` o dell'API rimossa `_wait_for_rate_limit()`:

1. **[test_production_pipeline.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/scripts/test_production_pipeline.py)**
   * **Linea 297:** `await classification._wait_for_rate_limit()` in `limiter_worker` -> solleva `AttributeError` (non esiste su `ClassificationClient`).
   * **Linea 327:** `classification = ClassificationClient()` -> solleva `ValueError` (costruttore privo di `pool` o `quota`).
2. **[test_500.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/scripts/diagnostics/test_500.py)**
   * **Linea 11:** `client = ClassificationClient()` -> solleva `ValueError`.
3. **[test_rate_limiter.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/scripts/diagnostics/test_rate_limiter.py)**
   * **Linea 12:** `await client._wait_for_rate_limit()` -> solleva `AttributeError`.
   * **Linea 17:** `client = ClassificationClient()` -> solleva `ValueError`.

---

## C. Inventario impatto

| Path File | Uso (ops/CI/live/orphaned) | Bug Rilevati | Impatto se Deprecato |
| :--- | :--- | :--- | :--- |
| `backend/scripts/test_production_pipeline.py` | **Live & Ops** (Importato in `test_integration_live.py`, documentato in `pipeline-engineer.md` per audit manuali) | Costruttore vuoto (L327) + API rimossa (L297) | **Alto:** Blocca i test live pytest (`test_live_rate_limiter_throttling`) e gli audit manuali di produzione. |
| `backend/scripts/diagnostics/test_500.py` | **Orphaned** (Non importato né in CI né in altri script. Utile solo storicamente per testare risposte 500 nemiche) | Costruttore vuoto (L11) | **Nullo:** Logica duplicata da unit test `test_classification.py`. Spostabile in obsolete. |
| `backend/scripts/diagnostics/test_rate_limiter.py` | **Orphaned** (Non usato in CI. Logica in-memory legacy) | Costruttore vuoto (L17) + API rimossa (L12) | **Nullo:** Il throttling della quota è testato estesamente offline in `test_quota_concurrency.py`. Spostabile in obsolete. |

---

## D. Raccomandazione
> **STORICO ANALISI (pre-decisione).** Implementato in §I: **Ibrido + path b1** (delete orfani; smoke mock; stress rimosso; live skip). Non usare più le opzioni sotto come TODO.

Si raccomandava un approccio **Ibrido** (Riparare + Deprecare):

* **Deprecare gli script orfani:** Spostare `test_500.py` e `test_rate_limiter.py` in `backend/scripts/diagnostics/_obsolete/` per ripulire il path di scansione, poiché la loro logica è interamente coperta da `test_classification.py` e `test_quota_concurrency.py`.
* **Riparare lo script di produzione `test_production_pipeline.py`:**
  * Istanziare `ClassificationClient` in `main()` passando un `QuotaLedger` con un mock o un pool DB se disponibile.
  * Modificare lo `stress_test_rate_limiter` affinché non usi più la vecchia API privata rimossa `_wait_for_rate_limit()` ma usi il flusso `quota.reserve()` / `quota.release()`.
* **Adattare `test_integration_live.py`:**
  * Il test live `test_live_rate_limiter_throttling` (che usa un mock no-op di quota) non può misurare il distanziamento reale temporale. La raccomandazione è di riscrivere la logica del test o, più semplicemente, marcarlo con skip esplicito documentando che il throttling reale è coperto al 100% da `test_quota_concurrency.py` e non richiede finti test live su mock.

---

## E. Design sketch (Opzione Ibrida)
> **STORICO ANALISI.** Il design sketch sotto (reserve/release su stress + mock) è **superseded** da path **b1** (§I): stress eliminato; timing = `test_quota_concurrency.py`.

1. **Spostamento File:**
   * Creare la directory `backend/scripts/diagnostics/_obsolete/` (se non esiste).
   * Spostare `test_500.py` e `test_rate_limiter.py` al suo interno.
2. **Aggiornamento di `test_production_pipeline.py`:**
   * In `main()`, istanziare `ClassificationClient` iniettando una quota di fallback o mockando il ledger per permettere l'esecuzione degli smoke test di connessione Gemini (Step 1) anche in assenza di DB.
     ```python
     # Nel main di test_production_pipeline.py
     from unittest.mock import AsyncMock
     mock_quota = AsyncMock()
     mock_quota.reserve = AsyncMock(return_value=1)
     classification = ClassificationClient(quota=mock_quota)
     ```
   * Nello `stress_test_rate_limiter(classification)`:
     Sostituire `await classification._wait_for_rate_limit()` con:
     ```python
     reservation_id = await classification.quota.reserve(
         estimated_tokens=classification._estimated_tokens,
         model=classification.model,
         purpose="stress_test"
     )
     await classification.quota.release(reservation_id)
     ```
3. **Gestione del Live Test Throttling in `test_integration_live.py`:**
   * Poiché `test_live_rate_limiter_throttling` usa un `_live_classification_client()` con un `quota` mockato (AsyncMock) che non implementa ritardi temporali reali (quindi `assert diff >= 3.9` fallisce), il test deve:
     * O essere disabilitato/skippato con `pytest.skip("Throttling live non testabile con mock no-op; coperto da test_quota_concurrency.py")`.
     * O implementare un mock di `reserve` che inserisce un delay artificiale di `3.9` secondi per validare la sequenza, ma questo sarebbe un test che valida se stesso (inutile).
     * Raccomandazione: **Skip esplicito** in `test_integration_live.py::test_live_rate_limiter_throttling`.

---

## F. Rischi / decisioni umane
* **Abbassamento Priorità a P1:** Se deprecato e skippato nei live test, la severità del ticket può scendere da P0 a P1, poiché non blocca più alcuna funzionalità di produzione né il Gate Verde. Questa decisione spetta al project manager o al lead developer.
* **Overlap con T-P2-04:** `test_500.py` ha un blocco `except Exception` nudo. Spostando il file in `_obsolete/`, si mitiga l'accumulo di debito tecnico e si evita di dover manutenere/correggere la gestione delle eccezioni in file deprecati.
* **Variabili d'ambiente per test live:** L'esecuzione dei test live richiede configurazioni reali (`GOOGLE_API_KEY`, `MINIFLUX_API_KEY`, `RADAR_LIVE_TEST_DATABASE_URL`), pertanto il corretto funzionamento dei test live deve sempre prevedere meccanismi robusti di skip in caso di mancanza di credenziali/rete.

---

## G. Prompt remediation (canonico)

Decisione umana: **ibrido + stress path (b)**.  
Prompt multi-agente completo: **`plan-audit/prompts/done/audit_prompt_T-P0-02_remediation.md`** (orchestratore + agenti A/B/C).

Sintesi:
1. Eliminare (o stub puliti) `diagnostics/test_500.py` + `test_rate_limiter.py` — no `_obsolete/` con pattern ancora matchati.
2. Riparare `test_production_pipeline.py` con `ClassificationClient(quota=mock)`; rimuovere/neutralizzare stress timing.
3. Skip `test_live_rate_limiter_throttling`; Script I su `*.py`; SoT DONE; handoff T-P1-04.
4. T-P2-04 fuori scope. No commit senza richiesta.

---

## H. Verifica aggiuntiva Cursor (2026-07-16) — PASS_WITH_GAPS

| Check | Esito |
|-------|--------|
| `ClassificationClient()` → `ValueError` L254 | **PASS** (riprodotto) |
| `_wait_for_rate_limit` assente su client | **PASS** (`hasattr` False) |
| Match source Script I (3 file `.py`) | **PASS** (L297/327, L11, L12/17) |
| Live `test_live_rate_limiter_throttling` | **PASS** fail atteso: `AttributeError` → `pytest.fail` |
| Offline `pytest -m "not live"` | **PASS** 115 passed |
| `pipeline-engineer.md` cita script | **PASS** |
| Orphan diagnostics (no import CI) | **PASS** |
| Raccomandazione ibrida ad alto livello | **PASS** (direzione OK) |

### Gap da correggere prima/durante remediation

1. **`_obsolete/` ≠ Script I pulito** — Select-String ricorsivo su `backend/scripts` continua a matchare file spostati sotto `_obsolete/`. Serve strip/delete/esclusione documentata su `*.py` (e ignorare `__pycache__`: i `.pyc` generano falsi positivi oggi).
2. **Contraddizione design stress + mock** — `reserve`/`release` su `AsyncMock` istantaneo fa fallire `assert diff >= 3.9` in `stress_test_rate_limiter`. Skip live e “riparare stress con mock” non possono coesistere senza togliere gli assert timing o usare un `QuotaLedger` reale.
3. **Overlap T-P2-04 errato** — T-P2-04 = bare `except:` in `test_500_bot.py` / `test_500_debug.py` / `test_string_lists.py`. `test_500.py` ha `except Exception as e:` → spostarlo **non** chiude T-P2-04.
4. **Priorità P0→P1** — offline Gate già verde (115); P0 era ops/live. Declassamento solo con decisione umana dopo fix/skip documentato.
5. **Nota pytest** — `addopts = -m "not live"`; per forzare live serve `-m live -o addopts=` (o equivalente) + `RUN_LIVE_TESTS=1`.

**Verdetto verifica:** analisi **CONFIRMED** nel nucleo. Decisione umana successiva: **ibrido + path (b)** → prompt remediation multi-agente in `audit_prompt_T-P0-02_remediation.md`.

---

## I. Remediation eseguita (2026-07-16)

La remediation è stata completata con successo seguendo la decisione del design path ibrido (opzione stress path **b**):

1. **Rimozione script obsoleti**:
   - `backend/scripts/diagnostics/test_500.py` è stato rimosso per pulire il path di scansione.
   - `backend/scripts/diagnostics/test_rate_limiter.py` è stato rimosso.
   Questo garantisce che il comando **Script I** ricorsivo produca **ZERO match**.

2. **Riparazione di `test_production_pipeline.py`**:
   - Rimosso lo stress test basato sulla vecchia API privata rimossa `_wait_for_rate_limit()`.
   - Modificato `_local_classification_client()` per istanziare `ClassificationClient(quota=quota)` iniettando un mock asincrono (`AsyncMock`) della quota.
   - Corretto l'import non utilizzato in testa al file (rimossi `time` e `List` inutilizzati che facevano fallire Ruff).

3. **Allineamento dei test live in `test_integration_live.py`**:
   - Configurato `test_live_rate_limiter_throttling` per essere esplicitamente skippato con una spiegazione chiara (`pytest.skip`), in quanto il throttling reale della quota è testato offline al 100% da `test_quota_concurrency.py`.

4. **Verifiche di Gate superate**:
   - **Script I**: 0 match rilevati su `backend/scripts` per `ClassificationClient\(\)` e `_wait_for_rate_limit`.
   - **Ruff check**: superato con successo su `backend/scripts/test_production_pipeline.py` e `backend/app/tests/test_integration_live.py`.
   - **Pytest offline**: 115 test passati con successo (`pytest -m "not live" -q`).
   - **Pytest live skip**: il test `test_live_rate_limiter_throttling` viene correttamente skippato come previsto.

5. **Riverifica Cursor (post-orchestratore):** codice/gate riconfermati **PASS**. Drift docs residuo (pie FASE 2, App. D, prompt F.8, spot-check) allineato → SoT coerente. Handoff **T-P1-04**.

---

## J. Correzioni ops post-DONE (2026-07-16) — segnalate

Durante il riavvio Docker di verifica T-P0-02:

| Problema | Severità | Correzione |
|----------|----------|------------|
| `docker compose restart` parallelo → `CannotConnectNowError` (DB starting up) su backend/worker/miniflux | Ops / boot | `init_pool` ritenta errori transienti; nota in `radar/.ecc/rules/docker.md` Regola 4; commenti in `docker-compose.yml`. Preferire `up -d` o restart ordinato. |
| Warning `Permission denied: 'logs'` RotatingFileHandler | Nota nota (già T-P0-01) | Solo console logging — non bloccante; nessuna nuova azione. |
| Gemini HTTP 500 retryable in worker | Esterno | Già gestito da client retry; ingest ripreso OK. |
| Doc stale spiderfy «cap 24» in `Implementation_Plan*.md` | Docs drift | Allineato al fix map `5a0a599` (tutte le icone; no `SPIDERFY_MAX_ICONS`). |

Gate test aggiunti: `test_init_pool_retries_cannot_connect_now` in `test_database.py`.

### J.1 Riverifica restart ordinato (2026-07-16 ~06:33 UTC)

Procedura: `restart radar-db` → wait healthy → `restart` backend/worker/miniflux/frontend (DB già healthy).

| Check | Esito |
|-------|--------|
| `CannotConnectNowError` al boot | **Assente** (pool OK al primo tentativo) |
| backend `/health/live` + `/ready` | **200** ready (pool, migrations, heartbeat) |
| frontend / miniflux / db | **healthy** |
| Warning `Permission denied: 'logs'` | Presente, non bloccante (console only) |
| Worker fetch Miniflux | **ERROR** `Corpo risposta Miniflux supera MAX_MINIFLUX_RESPONSE_BYTES=5000000` → ciclo trattato come “nessun unread”; **non** causato dal fix `init_pool`; backlog unread troppo grande per il cap 5MB. Prossimo poll tra 900s. |

Azione consigliata (fuori OPS-FIX docker): ridurre unread Miniflux oppure alzare/paginare `MAX_MINIFLUX_RESPONSE_BYTES` in ticket dedicato — non mescolare con T-P0-02.

