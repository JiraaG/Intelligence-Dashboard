# Prompt — FASE P2 BATCH (T-P2-01 … T-P2-08) — orchestratore multi-agente

> **Uso:** copia il blocco `text` sotto in un **nuovo** chat Agent (orchestratore).  
> **Scope:** batch remediation **P2** (`T-P2-01` → `T-P2-08`) dopo chiusura P0/P1.  
> **Non** commit/push salvo richiesta esplicita. **Non** toccare `radar-sidebar/**`.  
> **Precondizioni:** Phase 6 GATE VERDE; T-P0-01…T-P1-05 **DONE**. Branch: `refactor/testing` @ `f439508+`.

```text
/goal Esegui la FASE SUCCESSIVA post–Gate Verde: batch remediation P2
(T-P2-01 … T-P2-08) nel workspace
`c:\Users\lucag\Documents\Dashboard finance`.
Tu sei l’ORCHESTRATORE: pianifica, spawn sotto-agenti (Task tool), integra,
esegui gate, aggiorna SoT. NON commitare / NON pushare finché l’utente non lo chiede.
NON toccare radar/frontend/src/app/components/radar-sidebar/**.
NON riaprire ticket P0/P1 DONE salvo regressione dimostrata.
NON avviare Final Release Gate (chaos/SAST/seed 10k) in questo turno salvo richiesta.
NON regressare map UX spider-dezoom (`ed3d88f`) oltre i touch P2 elencati.

========================================================================
## 0. Contesto (leggi PRIMA di qualsiasi edit)
========================================================================

### Dove siamo
- Consolidation Phase 0–6: DONE / GATE VERDE (restore Phase 6: `56c2eff`).
- Branch operativo: `refactor/testing` (tip `f439508` — docs pin spider-dezoom).
- Remediation codice: P0=0 OPEN, P1=0 OPEN, P2=8 OPEN.
- Prossimo SoT: batch P2 (§4.8 + risoluzione §3).
- Map UX recente (già pushato, non rifare): spider dezoom `ed3d88f` /
  docs pin `f439508` — vedi `plan-audit/audit_remediation_spider_dezoom.md`.

### SoT obbligatori (ordine autorità)
1. `plan-audit/audit_problemi_documentazione_risoluzione.md` §3 (stati OPEN/DONE)
2. `plan-audit/audit_problemi_documentazione.md` §4.8 (fix P2) + FASE 5 §5.0 + **Script M**
3. Scratch findings: `plan-audit/scratch/backend_audit.md` (BE-AUD-007…010),
   `plan-audit/scratch/frontend_audit.md` (FE-AUD-002…005)
4. Guardrail: `.agents/AGENTS.md` + `radar/.ecc/rules/{backend,frontend}.md`
5. Scoreboard: `plan-audit/Implementation_Plan_Execution.md` §C (riga P2)
6. Checklist: `plan-audit/scratch/backend_rules.md`, `frontend_rules.md`

### Skills / ECC da leggere (per area)
| Area | Skill / agent |
|------|----------------|
| BE schema/validator (T-P2-01, T-P2-03) | `.agents/skills/llm-json-extraction/SKILL.md` + `radar/.ecc/skills/llm-json-extraction.md` |
| FE map (T-P2-05…07) | `.agents/skills/radar-sidebar-freeze/SKILL.md` (ZERO touch) + `radar/.ecc/agents/angular-map-expert.md` (osservazione) + `.agents/skills/angular-developer/SKILL.md` |
| FE mock/test osservazione | `.agents/skills/spatial-data-mocking/SKILL.md` (solo checklist; no sidebar edit) |
| BE rules | `radar/.ecc/rules/backend.md` |
| FE rules | `radar/.ecc/rules/frontend.md` |

### Ticket OPEN da chiudere (blocco) — AS-IS confermato 2026-07-16

| ID | Finding | File chiave | Fix SoT (non inventare) |
|----|---------|-------------|-------------------------|
| T-P2-01 | BE-AUD-007 | `classification/validator.py` `get_fallback_article` | `'Nessuna'` → `'Nessuno'` su `companies_involved` + `infrastructural_entities` |
| T-P2-02 | BE-AUD-008 | `extraction/parser.py` | Aggiungere `"img"`, `"picture"`, `"source"` a `content_ignored_tags` |
| T-P2-03 | BE-AUD-009 | `classification/validator.py` | `@model_validator(mode="after")`: primo tag CSV == `primary_category` (vedi diff scratch BE-AUD-009) |
| T-P2-04 | BE-AUD-010 | `scripts/diagnostics/test_500_bot.py`, `test_500_debug.py`, `test_string_lists.py` | bare `except:` → `except OSError` (prompt loader) |
| T-P2-05 | FE-AUD-002 | `radar-map.component.ts` + `.spec.ts` | Rimuovere `UI_OFFSETS` + assertion spec L510–513 |
| T-P2-06 | FE-AUD-003 | `radar-map.component.ts` clusterclick | Filtro su **arts**: `.filter((a): a is Article => !!a && a.primary_category === cat)` |
| T-P2-07 | FE-AUD-004 | `styles.scss` + `radar-map.component.ts` | Definire `--color-map-stroke` in `:root`; in TS usare `getComputedStyle(...).getPropertyValue('--color-map-stroke')` (Leaflet non risolve `var()` nello style object) |
| T-P2-08 | FE-AUD-005 | `frontend/src/app/shared/directives/` | Dir locale **vuota e non tracked in git** → `Remove-Item -Recurse`; se già assente = SKIP DONE |

Playbook: manuale §4.8. Gate BE: **Script M** (non Script I/J — quelli sono T-P0-02 / T-P1-04).

========================================================================
## 1. Policy vincolante
========================================================================

- Sidebar freeze: zero edit sotto `radar-sidebar/**`.
- `main.py` resta API-only; ingest solo in `worker.py`.
- asyncpg puro; Leaflet via `window.L` / `angular.json` scripts[].
- Un report batch: crea `plan-audit/audit_remediation_T-P2_batch.md`.
- Aggiorna SoT §3: ogni ticket → DONE con nota + file touched.
- Aggiorna header handoff in `audit_problemi_documentazione_risoluzione.md`
  (prossimo: Final Release residuali OPPURE “P2 chiusi → merge/PR”).
- Allinea `Implementation_Plan_Execution.md` riga “P2 (8) OPEN” → DONE/0.
- Non espandere scope a chaos / image scan / seed 10k / spiderfy redesign.
- Fuori scope intenzionale: `test_string_lists.py` Field description `'Nessuna'`
  (diagnostica isolata ≠ contratto produzione) — non è T-P2-01.

========================================================================
## 2. Sotto-agenti (Task tool) — parallelizza BE ∥ FE
========================================================================

Spawn **due** sotto-agenti in parallelo (un messaggio, due Task `generalPurpose`,
`run_in_background: true` se Multitask Mode). Tu NON implementi tutto da solo;
poi integri e fai gate. Opzionale terzo Task docs-only **dopo** BE∥FE.

### Agente BE — `generalPurpose`
**ID:** P2-BE  
**Prompt da passare:**
```
Workspace: c:\Users\lucag\Documents\Dashboard finance
Branch: refactor/testing @ f439508+
Implementa SOLO T-P2-01, T-P2-02, T-P2-03, T-P2-04.

SoT: plan-audit/audit_problemi_documentazione_risoluzione.md §3
Playbook: plan-audit/audit_problemi_documentazione.md §4.8 + Script M
Scratch: plan-audit/scratch/backend_audit.md BE-AUD-007…010 (segui i diff)
Rules: radar/.ecc/rules/backend.md
Skill: .agents/skills/llm-json-extraction/SKILL.md (T-P2-03 schema)

Allowlist:
- radar/backend/app/classification/validator.py
- radar/backend/app/extraction/parser.py
- radar/backend/scripts/diagnostics/test_500_bot.py
- radar/backend/scripts/diagnostics/test_500_debug.py
- radar/backend/scripts/diagnostics/test_string_lists.py  (solo except OSError)
- radar/backend/app/tests/** (aggiungi/aggiorna test mirati)

Vietato: radar-sidebar/**, frontend/**, docker, commit/push, Final Release.

Per-ticket AS-IS → fix → test:
1) T-P2-01: get_fallback_article Nessuna→Nessuno (2 campi).
2) T-P2-02: content_ignored_tags += img/picture/source; estendi
   test_extraction.test_strip_html_tags_media_tags con caso
   <img>fallback interno</img> se manca.
3) T-P2-03: @model_validator(mode="after") come BE-AUD-009; import
   model_validator + Self; unit test: mismatch primo tag REJECT;
   match OK; fallback get_fallback_article ancora valido (tags=primary).
4) T-P2-04: solo bare except: → except OSError (tre file).

Output obbligatorio: file touched, diff summary, comandi pytest eseguiti, gap.
```

### Agente FE — `generalPurpose`
**ID:** P2-FE  
**Prompt da passare:**
```
Workspace: c:\Users\lucag\Documents\Dashboard finance
Branch: refactor/testing @ f439508+
Implementa SOLO T-P2-05, T-P2-06, T-P2-07, T-P2-08.

SoT: plan-audit/audit_problemi_documentazione_risoluzione.md §3
Playbook: plan-audit/audit_problemi_documentazione.md §4.8
Scratch: plan-audit/scratch/frontend_audit.md FE-AUD-002…005 (segui i diff)
Rules: radar/.ecc/rules/frontend.md
Skills: .agents/skills/radar-sidebar-freeze/SKILL.md (ZERO touch sidebar);
  radar/.ecc/agents/angular-map-expert.md (solo lettura pattern);
  .agents/skills/angular-developer/SKILL.md

Allowlist:
- radar/frontend/src/app/components/radar-map/radar-map.component.ts
- radar/frontend/src/app/components/radar-map/radar-map.component.spec.ts
- radar/frontend/src/styles.scss  (solo --color-map-stroke[+active se utile])
- rimozione path shared/directives/ se vuota

Vietato: radar-sidebar/**, backend/**, docker, commit/push,
  redesign spiderfy/hub/hatch oltre i 4 ticket.

Per-ticket:
5) T-P2-05: elimina UI_OFFSETS + blocco spec che lo legge (expect offsets Nucleare).
6) T-P2-06: nel clusterclick, filtro ESPLICITO su arts:
   .filter((a): a is Article => !!a && a.primary_category === cat)
   (difesa in profondità; non basta il closure sul gruppo categoria).
7) T-P2-07: in styles.scss :root aggiungi
   --color-map-stroke: rgba(0, 212, 255, 0.15);
   (opz. --color-map-stroke-active). In load GeoJSON:
   const stroke = getComputedStyle(document.documentElement)
     .getPropertyValue('--color-map-stroke').trim()
     || 'rgba(0, 212, 255, 0.15)';
   poi style color: stroke.
   NON passare 'var(--color-map-stroke)' crudo a L.geoJSON style
   (Leaflet non risolve CSS vars). Evita !important CSS path salvo
   necessità dimostrata.
8) T-P2-08: se dir shared/directives esiste e è vuota → Remove-Item -Recurse;
   git ls-files deve restare vuoto (già non tracked). Se assente → SKIP DONE.

Output: file touched, diff summary, npm typecheck/test se eseguiti, gap.
```

### Dopo ritorno BE∥FE — orchestratore
1. Review overlap (nessuno atteso: BE vs FE).
2. Esegui gate §3.
3. Scrivi `plan-audit/audit_remediation_T-P2_batch.md`.
4. Marca T-P2-01…08 DONE in risoluzione §3; P2 OPEN → 0; aggiorna header handoff.
5. Allinea `Implementation_Plan_Execution.md` riga P2.
6. Output italiano all’utente (template §4).

Se un sotto-agente fallisce un ticket: marca PASS_WITH_GAPS, lascia quel ID OPEN,
non bloccare gli altri DONE.

========================================================================
## 3. Gate (DoD) — mirato P2 + Script M
========================================================================

```powershell
cd "c:\Users\lucag\Documents\Dashboard finance\radar"

# --- Backend ---
$env:PYTHONPATH = "backend"
# Se venv presente: .\backend\.venv\Scripts\Activate.ps1
python -m pytest -m "not live" -q

# Script M (validator / parser P2)
Select-String -Path backend/app/classification/validator.py -Pattern "Nessuna|model_validator"
# Atteso: Nessuna ASSENTE (o solo commenti storici); model_validator PRESENTE
Select-String -Path backend/app/extraction/parser.py -Pattern '"img"|"picture"|"source"'
# Atteso: match su content_ignored_tags

# Spot T-P2-04
Select-String -Path backend/scripts/diagnostics/test_500_bot.py,
  backend/scripts/diagnostics/test_500_debug.py,
  backend/scripts/diagnostics/test_string_lists.py -Pattern "except:"
# Atteso: 0 bare except: (solo except OSError)

# --- Frontend ---
cd frontend
npm run typecheck
npm run test:ci
# build:ci consigliato ma non bloccante se solo cleanup

# Freeze
cd ../..
git diff --stat -- radar/frontend/src/app/components/radar-sidebar
# → deve restare vuoto
```

**NON** richiedere Script I / Script J in questo batch (già chiusi con T-P0-02 / T-P1-04).
Suite §5.0 completa (geojson fetch + docker health) = opzionale post-PASS, non DoD di questo turno.

Checklist:
- [ ] T-P2-01…08 DONE in SoT §3 (o gap espliciti)
- [ ] pytest `not live` PASS
- [ ] Script M coerente (no Nessuna fallback; model_validator; img in parser)
- [ ] FE typecheck + test:ci PASS
- [ ] sidebar diff vuoto
- [ ] Report `audit_remediation_T-P2_batch.md` scritto
- [ ] Nessun commit/push

========================================================================
## 4. Output orchestratore (italiano, obbligatorio)
========================================================================

1. Verdetto: PASS / PASS_WITH_GAPS / FAIL
2. Tabella ticket → DONE|OPEN|SKIP + 1 riga evidenza ciascuno
3. File touched (BE / FE)
4. Esiti gate (pytest / Script M / npm / sidebar diff)
5. Diff conteggi SoT (P2 OPEN 8 → 0)
6. Handoff one-liner: cosa resta (Final Release residuali: seed 10k, chaos,
   SAST/image scan, smoke toggle letta+spiderfy; oppure merge PR
   refactor/testing → develop)
```

---

## Note per chi lancia

- **Verdetto sul piano Cursor grezzo:** allineato al SoT §4.8 e agli 8 ticket OPEN; correggere però:
  1. Gate = **Script M**, non Script I/J.
  2. T-P2-06 filtra su **`arts`** (`a.primary_category === cat`), non solo sui marker.
  3. T-P2-07: `getComputedStyle` + CSS var (non `color: 'var(--…)'` crudo in Leaflet).
  4. T-P2-08: dir locale vuota **non in git** — delete filesystem, non aspettarsi diff git.
  5. T-P2-03 richiede **unit test** (strict schema); non solo edit.
- Se preferisci **un ticket per turno**: cambia `/goal` in “solo T-P2-0N” e usa
  `plan-audit/audit_prompt_T-P1-05_remediation.md` come template mono-ticket.
- Merge/PR e Final Release Gate **non** sono in questo prompt: chiedili dopo PASS P2.
- Restore map UX (non regressione): `ed3d88f` — `plan-audit/audit_remediation_spider_dezoom.md`.
