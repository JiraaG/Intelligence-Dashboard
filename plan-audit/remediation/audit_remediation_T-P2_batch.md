# Report Remediation P2 — Batch (T-P2-01 … T-P2-08)

Questo documento riassume gli interventi eseguiti per risolvere i ticket di priorità P2 (Igiene, Difesa in profondità, allineamento diagnostiche) sul repository del **Radar Informativo Globale**.

Tutte le modifiche sono state implementate in modo isolato tramite due sotto-agenti dedicati (`P2-BE` e `P2-FE`), integrate con successo e validate contro la suite di test offline (pytest + npm/Vitest).

---

## 🚀 Verdetto: **PASS**

Tutti gli 8 ticket sono stati chiusi e convalidati positivamente senza alcuna regressione sulle funzionalità di produzione e rispettando rigorosamente il **Sidebar Freeze**.

---

## 📋 Tabella Dettaglio Ticket

| ID | Finding | Stato | Evidenza della Risoluzione |
|:---|:---|:---:|:---|
| **T-P2-01** | BE-AUD-007 | **DONE** | Fallback `"Nessuna"` → `"Nessuno"` nei campi `companies_involved` e `infrastructural_entities` in `get_fallback_article` di `validator.py`. |
| **T-P2-02** | BE-AUD-008 | **DONE** | Aggiunti `"img"`, `"picture"` e `"source"` a `content_ignored_tags` in `parser.py`. Test di estrazione estesi. Vedere dettagli in § "Focus Tecnico: Gap G1 & G2". |
| **T-P2-03** | BE-AUD-009 | **DONE** | `@model_validator(mode="after")` implementato per forzare che il primo tag coincida con `primary_category`. Aggiunti unit test specifici in `test_classification.py`. |
| **T-P2-04** | BE-AUD-010 | **DONE** | Bare `except:` → `except OSError:` per i lettori di prompt in `test_500_bot.py`, `test_500_debug.py` e `test_string_lists.py`. |
| **T-P2-05** | FE-AUD-002 | **DONE** | Rimozione della proprietà `UI_OFFSETS` morta in `radar-map.component.ts` e rimozione dell'asserzione corrispondente in `radar-map.component.spec.ts`. |
| **T-P2-06** | FE-AUD-003 | **DONE** | Nel gestore `clusterclick` del frontend, aggiunto filtro esplicito: `.filter((a): a is Article => !!a && a.primary_category === cat)`. |
| **T-P2-07** | FE-AUD-004 | **DONE** | Definita variabile `--color-map-stroke` in `:root` di `styles.scss`. In `radar-map.component.ts`, la proprietà `color` del GeoJSON viene letta a runtime tramite `getComputedStyle(...)`. |
| **T-P2-08** | FE-AUD-005 | **DONE** | Rimozione filesystem della cartella vuota non tracciata `shared/directives/`. |

---

## 🔍 Focus Tecnico: Gap G1, G2, G3 & Nit FE

### G1 — Gestione dei Void Tag ed Evitamento dello "Swallow" del Testo
Durante l'analisi del parser HTML (`parser.py`), è stata introdotta la funzione `_has_matching_close_tag(tag_lower)` per evitare il rischio che un void tag (come `<img>`, `<source>`, `<meta>`, `<embed>`) sprovvisto di tag di chiusura possa causare l'inghiottimento (swallow) di tutto il testo successivo nel documento.
- **Funzionamento di `_has_matching_close_tag`**: la funzione analizza l'HTML grezzo a partire dalla posizione corrente del parser. Cerca la presenza del tag di chiusura corrispondente (`</tag_lower>`) e verifica che non ci sia un altro tag di apertura della stessa tipologia prima di esso. Se non viene trovato alcun tag di chiusura valido, la funzione ritorna `False`.
- **Ramo dei Void Tag (Void-tag Branch)**: nel metodo `handle_starttag`, quando viene incontrato un tag appartenente alla allowlist dei void tag (`{"img", "source", "meta", "embed"}`), esso viene inserito in `ignored_stack` solo se `_has_matching_close_tag` restituisce `True`. Se restituisce `False` (caso tipico dei void tag auto-chiudenti o singoli), il tag non viene inserito nello stack di ignorati, impedendo così che tutto il testo successivo venga erroneamente scartato.

### G2 — Allineamento Fallback e Validazione CSV (Script M)
Per allineare la logica del validatore all'happy path e alle specifiche operative del backend:
- **Rimozione di "Nessuna" dai Fallback**: in `validator.py`, la funzione `get_fallback_article` restituisce ora esplicitamente la stringa `"Nessuno"` per i campi `companies_involved` e `infrastructural_entities`. La stringa `"Nessuna"` è stata rimossa come valore di fallback predefinito per garantire uniformità e coerenza semantica con la lingua italiana e con le definizioni delle schede.
- **Corrispondenza di Descrizione e Parsing**: le descrizioni dei campi schema (`companies_involved`, `infrastructural_entities`) istruiscono esplicitamente l'LLM o il validatore a inserire `"Nessuno"` in assenza di entità. L'helper `parse_csv_list(val)` è stato configurato per intercettare ed escludere tutti i possibili sinonimi di assenza (`["nessuno", "nessuna", "nessun", "none", "n/a", ""]`), i quali sono attesi e corretti come sinonimi e vengono convertiti in liste vuote `[]` anziché in liste contenenti stringhe fittizie.

### G3 — Gestione Eccezioni Ristrette nel Parser
Per blindare la funzione `_has_matching_close_tag` contro fallimenti inattesi e potenzialmente distruttivi (dovuti a rawdata, getpos, slices o tipi errati), è stato adottato un blocco try-except con eccezioni ristrette.
- **Narrow Exception Catch**: viene catturata esclusivamente la tupla di eccezioni `(AttributeError, TypeError, IndexError, ValueError)` ritornando immediatamente `False`.
- **Zero `except Exception:`**: per ragioni di sicurezza e pulizia del codice, è stato esplicitamente evitato qualsiasi catch generico che possa nascondere bug architetturali più gravi.

### Nit FE — Ottimizzazione della Lettura di Stili in Mappa
Nel frontend, all'interno del componente `radar-map.component.ts`, è stata ottimizzata la gestione del rendering GeoJSON incrementale.
- **Hoist `getComputedStyle`**: la lettura della variabile CSS `--color-map-stroke` tramite `getComputedStyle(...)` è stata spostata (hoisted) all'inizio di `parseGeoJsonIncremental`, venendo eseguita una sola volta prima dell'avvio del loop RAF (Request Animation Frame) e del batch processing. Questo elimina letture ridondanti del DOM ad ogni batch RAF, salvaguardando le prestazioni di rendering. La funzione `refreshHatchingStyles` mantiene le proprie letture locali in quanto adibita ad un percorso di esecuzione differente.

---

## 📂 File Modificati (Touched Files)

### Backend (BE)
- [validator.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/classification/validator.py)
- [parser.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/extraction/parser.py)
- [test_extraction.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/tests/test_extraction.py)
- [test_classification.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/tests/test_classification.py)
- [test_commit.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/tests/test_commit.py)
- [test_500_bot.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/scripts/diagnostics/test_500_bot.py)
- [test_500_debug.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/scripts/diagnostics/test_500_debug.py)
- [test_string_lists.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/scripts/diagnostics/test_string_lists.py)

### Frontend (FE)
- [radar-map.component.ts](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/app/components/radar-map/radar-map.component.ts)
- [radar-map.component.spec.ts](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/app/components/radar-map/radar-map.component.spec.ts)
- [styles.scss](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/styles.scss)
- **Cancellata directory**: `radar/frontend/src/app/shared/directives/` (rimossa dal disco poichè vuota).

---

## 🧪 Esiti del Gate di Verifica (DoD)

1. **Test Backend (not live)**:
   - `python -m pytest -m "not live" -q`
   - **Risultato**: **117 superati** su 117 offline unit/integration test.
2. **Script M (Validator/Parser check)**:
   - Controllata l'assenza di `"Nessuna"` come fallback e la presenza di `model_validator` in `validator.py` -> **OK**.
   - Controllata l'inclusione di `"img"`, `"picture"`, `"source"` in `parser.py` -> **OK**.
3. **Spot T-P2-04 (Bare except check)**:
   - `Select-String` per `except:` sui file diagnostici ha prodotto **0 risultati** (sostituiti con `except OSError:`).
4. **Typecheck Frontend**:
   - `npm run typecheck` in `radar/frontend` -> **SUCCESSO (0 errori)**.
5. **Test Unitari Frontend**:
   - `npm run test:ci` in `radar/frontend` -> **SUCCESSO (30 superati su 30)**.
6. **Sidebar Freeze**:
   - `git diff --stat -- radar/frontend/src/app/components/radar-sidebar` -> **Completamente vuoto (0 modifiche)**.

---

## 📈 Tabella di Stato (SoT) & Scoreboard

### Modifiche dei Conteggi SoT
- **P2 OPEN**: 8 prima della remediation → **0 OPEN** (100% DONE).
- **P0/P1 OPEN**: Rimangono a **0 OPEN** (nessuna regressione introdotta).

### Prossimo Passaggio (Handoff)
Tutti i ticket correttivi del codice sono ora contrassegnati come **DONE**. 
La prossima fase prevede la **Final Release** (merge PR del ramo `refactor/testing` su `develop` o `main`, e opzionalmente l'avvio della chaos suite, seed 10k e controlli SAST se richiesto dall'utente).

> **Aggiornamento 2026-07-18:** Final Release **F0–F4 COMPLETE** (PR #1 merged; F1–F4 PASS). Fase 5 hardening resta deferred accettato. Vedi [`STATUS.md`](../STATUS.md).
