# Prompt — Closing P2 Gaps & Final Release Handoff (G1–G5)

> **Uso:** copia il blocco `text` sotto in un **nuovo** chat Agent (orchestratore).  
> **Scope:** chiudere gap G1–G5 + nit FE; allineare SoT; creare handoff Final Release.  
> **Non** commit/push salvo richiesta esplicita. **Non** toccare `radar-sidebar/**`.  
> **Precondizioni:** T-P2-01…08 DONE in codice; working tree già con batch P2. Branch: `refactor/testing`.

```text
/goal Esegui il piano “Closing P2 Gaps & Final Release Handoff” (G1–G5)
nel workspace `c:\Users\lucag\Documents\Dashboard finance`.
Tu sei l’ORCHESTRATORE: spawn sotto-agenti, integra, gate, handoff.
NON commitare / NON pushare finché l’utente non lo chiede.
NON toccare radar/frontend/src/app/components/radar-sidebar/**.
NON riaprire ticket P0/P1/P2 DONE. NON eseguire chaos/SAST/seed 10k qui.
Al termine: chiedi quale voce del menu Final Release (commit / PR / gate / stop).

========================================================================
## 0. Contesto & verdetto piano (già verificato)
========================================================================

Il piano Cursor è **APPROVATO** con 2 precisazioni tecniche:

1. **G3 except:** non limitarti a `(ValueError, IndexError)` — in
   `_has_matching_close_tag` i fallimenti reali sono tipicamente
   `AttributeError` / `TypeError` / `IndexError` (rawdata/getpos/slice).
   Usa: `except (AttributeError, TypeError, IndexError, ValueError):`
   return False. Zero `except Exception:`.

2. **Hoist getComputedStyle:** non “una volta per batch RAF”, ma
   **una volta per invocazione** di `parseGeoJsonIncremental` (prima di
   definire/`requestAnimationFrame(processBatch)`). `refreshHatchingStyles`
   può tenere le sue letture (è un altro path).

Stato: Phase 6 GATE VERDE; §3 ticket P2 DONE; verifica precedente =
PASS_WITH_GAPS. Obiettivo turno = **PASS** rigoroso + handoff.

### SoT
1. `plan-audit/complete/plan_docs_audit_ticket_status.md`
2. `plan-audit/complete/plan_docs_audit_playbook.md` (FASE 2 + F.8)
3. `plan-audit/remediation/audit_remediation_T-P2_batch.md`
4. `plan-audit/complete/plan_impl_phase_0_6_execution.md` §C
5. `plan-audit/complete/plan_impl_phase_0_6.md` → Final Release Gate
6. `.agents/AGENTS.md` + `radar/.ecc/rules/{backend,frontend}.md`

### Gap (DoD)
| ID | Fix |
|----|-----|
| G1 | Report: documentare `_has_matching_close_tag` + void-tag branch (perché evita swallow testo su `<img>` void) |
| G2 | Report Script M: fallback senza `"Nessuna"`; match description/`parse_csv_list` = attesi |
| G3 | `parser.py`: narrow except come sopra |
| G4 | SoT/manuale: niente “P2 OPEN=8”, “prossimo T-P2-01”, “T-P2-02 OPEN”, “T-P2-06 WEAK” come stato corrente |
| G5 | NEW `plan-audit/remediation/audit_remediation_final_release_handoff.md` |
| Nit | Hoist `--color-map-stroke` fuori dal loop/RAF in `parseGeoJsonIncremental` |

Frasi stale confermate da riparare (almeno):
- risoluzione §0.2 L46 “prossimo T-P2-01”
- risoluzione happy-path L104 “T-P2-02 OPEN”
- risoluzione conteggi L147 `P2 OPEN | 8`
- risoluzione spot-check L234 “T-P2-06 WEAK”
- manuale pie L148 `"P2 OPEN codice" : 8` + nota post-remediation
- manuale F.8 / coda L1083 “prossimo T-P2-01”
Header risoluzione: remediation codice **CLOSED** · prossimo Final Release.

========================================================================
## 1. Policy
========================================================================

- Sidebar freeze.
- Solo allowlist sotto; no redesign map/spiderfy (`ed3d88f`).
- Nessun Final Release Gate completo in questo turno.
- Report P2 → verdetto **PASS** solo dopo G1–G4 + gate verdi.

========================================================================
## 2. Sotto-agenti (parallelo)
========================================================================

### A — `generalPurpose` · P2-CLOSE-CODE
```
Workspace: c:\Users\lucag\Documents\Dashboard finance
Implementa G3 + Nit FE.

Allowlist:
- radar/backend/app/extraction/parser.py
  → except (AttributeError, TypeError, IndexError, ValueError): return False
  → zero except Exception
- radar/backend/app/tests/test_extraction.py (solo se regressione)
- radar/frontend/src/app/components/radar-map/radar-map.component.ts
  → in parseGeoJsonIncremental: leggi stroke UNA volta prima del RAF loop;
    riusa nel for delle feature. Non toccare clusterclick/spiderfy/UI oltre questo.

Vietato: radar-sidebar/**, altri file BE/FE, commit/push.
DoD locale: pytest app/tests/test_extraction.py + smoke void/closed img.
Output: diff summary + comandi.
```

### B — `generalPurpose` · P2-CLOSE-DOCS
```
Workspace: c:\Users\lucag\Documents\Dashboard finance
Implementa G1, G2, G4, G5.

Allowlist SOLO plan-audit/**:
- audit_remediation_T-P2_batch.md (G1+G2+verdetto PASS)
- plan_docs_audit_ticket_status.md (G4 + header CLOSED)
- plan_docs_audit_playbook.md (conteggi/pie/F.8/coda)
- plan_impl_phase_0_6_execution.md (conferma P2 DONE)
- NEW audit_remediation_final_release_handoff.md (template §4 del prompt padre)

Vietato: radar/** codice; commit/push.
Output: elenco stringhe stale riparate + path handoff.
```

### Dopo A∥B
1. Gate §3.
2. Marca G1–G5 DONE.
3. Output italiano §5 + domanda menu D.

========================================================================
## 3. Gate
========================================================================

```powershell
cd "c:\Users\lucag\Documents\Dashboard finance\radar"
$env:PYTHONPATH = "backend"
# opz: .\backend\.venv\Scripts\Activate.ps1
python -m pytest -m "not live" -q

# Script M — interpretazione corretta
Select-String -Path backend/app/classification/validator.py `
  -Pattern 'companies_involved="Nessuna"|infrastructural_entities="Nessuna"'
# Atteso: 0 (fallback)
Select-String -Path backend/app/classification/validator.py -Pattern "model_validator"
Select-String -Path backend/app/extraction/parser.py -Pattern '"img"|"picture"|"source"'
Select-String -Path backend/app/extraction/parser.py -Pattern "except Exception:"
# Atteso: 0

cd frontend
npm run typecheck
npm run test:ci

cd ../..
git diff --stat -- radar/frontend/src/app/components/radar-sidebar
# → vuoto
```

Checklist:
- [ ] G1–G5 + Nit DONE
- [ ] Report P2 = PASS
- [ ] Handoff creato
- [ ] pytest / typecheck / test:ci / sidebar OK
- [ ] Nessun commit/push

========================================================================
## 4. Template handoff (`audit_remediation_final_release_handoff.md`)
========================================================================

### A. Stato codice
- SoT OPEN codice: **0** (P0/P1/P2 DONE; remediation **CLOSED**)
- Branch `refactor/testing`; working tree: batch P2 + close gaps (uncommitted)
- Map restore: `ed3d88f` / pin `f439508`

### B. Gate già verdi
- pytest not live (~117)
- FE typecheck + test:ci (30)
- Phase 6 GATE VERDE (`56c2eff`)

### C. Residui Final Release (`plan_impl_phase_0_6.md`)
| Residuo | Azione |
|---------|--------|
| Compose health / backup-restore | ops manuale |
| Chaos kill/restart pipeline | su richiesta |
| SAST / image scan | deferred / su richiesta |
| Seed 10k budget | su richiesta |
| Smoke UI letta+spiderfy | consigliato pre-merge |

### D. Menu (NON eseguire qui)
1. Commit locale batch P2 + close docs
2. PR `refactor/testing` → develop (o base scelta)
3. Final Release Gate item-per-item
4. Stop (handoff only)

### E. Fuori scope
- Sidebar freeze; digest pin; drop `--legacy-peer-deps`

========================================================================
## 5. Output orchestratore (italiano)
========================================================================

1. Verdetto: PASS / PASS_WITH_GAPS / FAIL
2. Tabella G1–G5 + Nit → DONE|DEFERRED
3. File touched (BE / FE / plan-audit)
4. Esiti gate
5. SoT: remediation **CLOSED**; prossimo = Final Release
6. Path handoff
7. Domanda: menu D voce 1–4?
```

---

## Verifica piano Cursor (sintesi)

| Voce piano | Esito |
|------------|-------|
| G3 `ValueError, IndexError` only | **Correggere** → includere anche `AttributeError`, `TypeError` |
| Hoist “once per batch” | **OK se** = una volta per `parseGeoJsonIncremental`, non per ogni RAF |
| Docs G1/G2/G4 + NEW handoff G5 | **Allineato** SoT |
| Gate pytest + typecheck + test:ci + Script M + sidebar | **Allineato**; usa Script M con pattern fallback esplicito |
| Sidebar freeze / no commit | **Vincolante** (aggiungi esplicitamente nel run) |

Pronto all’uso: questo file. Il piano Cursor grezzo va bene dopo le 2 precisazioni sopra.
