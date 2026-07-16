# Prompt — T-P1-04 REMEDIATION (ARCHIVIO — ticket DONE)

> **Stato:** T-P1-04 **DONE** (2026-07-16) — commit `51225b5`.  
> Report: `plan-audit/remediation/audit_remediation_T-P1-04.md`.  
> **Non rieseguire** questo prompt. Prossimo SoT: **T-P1-05**.  
> Blocco sotto = storico orchestratore multi-agente (congelato).

# Prompt — T-P1-04 REMEDIATION (orchestratore multi-agente)

> **Uso:** copia il blocco `text` sotto in un nuovo chat Agent (orchestratore).  
> **Scope:** solo T-P1-04 FE — `detailError` + banner nation-open.  
> **Non** commit/push salvo richiesta esplicita. **Non** toccare `radar-sidebar/**`. **Non** aprire T-P1-05/P2.  
> **Precondizioni:** T-P0-02 DONE; docs/ECC align DONE (`c358391`). Branch tipico: `refactor/testing`.

```text
/goal Implementa T-P1-04 (banner nation-fetch / detailError) nel workspace
`c:\Users\lucag\Documents\Dashboard finance` secondo la policy sotto.
Usa sotto-agenti specializzati (Task tool) in parallelo dove indipendenti; tu resti
orchestratore: integri, risolvi conflitti, esegui gate finale, aggiorni SoT.
NON commitare / NON pushare. NON toccare radar-sidebar/**. NON aprire T-P1-05/P2.
NON modificare radar-map salvo necessità zero dimostrata.

========================================================================
## 0. Contesto SoT (vincolante)
========================================================================

Ticket: **T-P1-04** · ID scratch **FE-AUD-001** · checklist **FE-MK-02**
Sintomo: fallimento `loadCountryArticles` → log + `closeSidebar()` senza banner toolbar.
Wiring già presente: `app.html` `[apiError]="!!state.error()"` → toolbar `@if (apiError())`.
Oggi `error` = solo `mapSummaryResource.error()` → nation-fetch non arriva al banner.

SoT: `plan-audit/active/plan_docs_audit_ticket_status.md` §3
Playbook: `plan-audit/active/plan_docs_audit_playbook.md` §3.6 / §4.6 / Script J / U5
Evidenza: `plan-audit/archive/scratch/scratch_frontend_audit.md` FE-AUD-001
Skills: `.agents/skills/radar-sidebar-freeze`, `.agents/skills/angular-developer`
ECC: `radar/.ecc/rules/frontend.md` (Regola MOCK/error → banner; no fallback mock)
Report nuovo: `plan-audit/remediation/audit_remediation_T-P1-04.md`
Branch: `refactor/testing`. Gate: Phase 6 / Gate Verde.

========================================================================
## 0.1 Policy prodotto (VINCOLANTE — non rinegoziare)
========================================================================

| Area | Azione |
|------|--------|
| `state.service.ts` | Aggiungere `detailError = signal<unknown>(null)`. `error` computed = `mapSummaryResource.error() ?? detailError()`. In `loadCountryArticles`: clear `detailError` all’ingresso; in catch `detailError.set(err)` poi rethrow. |
| `app.ts` `onCountryClick` catch | **Non** chiudere silenziosamente azzerando l’errore. Chiudi sidebar/UI se serve, ma **lascia `detailError` valorizzato** finché dismiss/clear intenzionale. |
| Clear errore | Reset `detailError` su: (a) inizio nuovo `loadCountryArticles` OK-path start; (b) close sidebar **intenzionale utente** / cambio contesto che chiama clear; (c) **non** nel catch di fallimento nation subito dopo `set(err)`. |
| Implementazione consigliata | `clearDetailArticles(options?: { clearError?: boolean })` default `clearError: true`. Dal catch di `onCountryClick`: chiudi UI chiamando clear con `{ clearError: false }` **oppure** closeSidebar path che non wipe l’errore. Documenta la scelta nel report. |
| Banner | Nessuna modifica HTML toolbar se `[apiError]="!!state.error()"` già basta. |
| MOCK_MODE | Vietato fallback silenzioso a mock su errore API. |
| Sidebar freeze | **Zero** edit sotto `radar/frontend/src/app/components/radar-sidebar/**`. |
| Test | Estendere `app.spec.ts` e/o spec state: nation-fetch fail → `error()` truthy / `apiError`; close intenzionale → clear. Preferire TestBed esistente. |
| Fuori scope | T-P1-05 nginx; P2 FE-AUD-002+; spiderfy/map; backend; commit. |

========================================================================
## 1. Orchestratore — protocollo sotto-agenti
========================================================================

Lancia **tre** sotto-agenti. Preferisci A∥B in parallelo; C dopo merge A+B
(oppure C in sola lettura docs in parallelo, scrittura SoT solo post-gate).

| ID | Tipo Task | Ruolo | Touch allowlist | Vietato |
|----|-----------|-------|-----------------|---------|
| **A** | `generalPurpose` | **State detailError** | `radar/frontend/src/app/services/state.service.ts` (+ spec state se esiste) | `app.ts`, `radar-sidebar/**`, `radar-map/**`, SoT DONE |
| **B** | `generalPurpose` | **App catch + clear policy** | `radar/frontend/src/app/app.ts`, `radar/frontend/src/app/app.spec.ts` (e `app.html` solo se wiring apiError manca — oggi non dovrebbe) | `state.service.ts` (A), `radar-sidebar/**`, backend |
| **C** | `generalPurpose` | **Docs + Script J + gate** | `plan-audit/remediation/audit_remediation_T-P1-04.md` (crea), `plan-audit/active/plan_docs_audit_ticket_status.md` (§3 + conteggi + § esito), pezzi `plan_docs_audit_playbook.md` (§3.6/§4.6 criteri), App. D se presente. Esegue Script J / `npm run test:ci`. | logica prodotto oltre verify; commit |

**Regola conflitti:** A e B non editano lo stesso file. Se serve firma `clearDetailArticles`, A la introduce; B la consuma.
**Skills da caricare nei prompt A/B:** radar-sidebar-freeze + angular-developer.

Dopo A+B: orchestratore review diff unificata (attenzione: catch non deve wipe `detailError`), poi avvia/completa C.

========================================================================
## 2. Prompt sotto-agente A — State detailError
========================================================================

Copia nel Task A:

```
Obiettivo T-P1-04-A: propagare errore nation-fetch in StateService.error via detailError.

Workspace: c:\Users\lucag\Documents\Dashboard finance
File: radar/frontend/src/app/services/state.service.ts
(e spec dedicata se esiste; altrimenti lascia test ad B/orchestratore)

Leggi skill: .agents/skills/radar-sidebar-freeze/SKILL.md
Leggi playbook §4.6 e scratch FE-AUD-001.

Implementa:
1. readonly detailError = signal<unknown>(null);
2. readonly error = computed(() => this.mapSummaryResource.error() ?? this.detailError());
3. loadCountryArticles: detailError.set(null) all'inizio; in catch detailError.set(err) prima di throw;
4. clearDetailArticles(options?: { clearError?: boolean }): di default clearError true → detailError.set(null); se clearError===false non toccare detailError. Continua a clearare detailArticles + detailLoading.

NON toccare app.ts, radar-sidebar, radar-map, MOCK_MODE token.
NON commitare.

Restituisci: diff summary, firma clearDetailArticles, note per B.
```

========================================================================
## 3. Prompt sotto-agente B — App catch + tests
========================================================================

Copia nel Task B (dopo A, o in parallelo se assume la firma options di A):

```
Obiettivo T-P1-04-B: nation-fetch fail → banner visibile; niente chiusura silenziosa che wipe error.

Workspace: c:\Users\lucag\Documents\Dashboard finance
File: radar/frontend/src/app/app.ts
      radar/frontend/src/app/app.spec.ts
Opzionale read-only: app.html (verifica [apiError]="!!state.error()")

Leggi skill: .agents/skills/radar-sidebar-freeze/SKILL.md
Prerequisito A: StateService ha detailError + clearDetailArticles({ clearError?: boolean }).

Policy catch onCountryClick:
- se generation stale → return
- chiudi sidebar/UI (isSidebarOpen false, selected/cluster/focus reset, collapse graphs, invalidateSize)
- chiama clearDetailArticles({ clearError: false }) OPPURE path equivalente che NON azzera detailError
- NON lasciare l'utente senza feedback: state.error() deve restare truthy → toolbar apiError true

closeSidebar() intenzionale utente: deve azzerare detailError (clearError true / clearDetailArticles default).

Test (app.spec.ts):
1. mock loadCountryArticles reject → dopo onCountryClick, state.error() truthy (o apiError toolbar true)
2. closeSidebar dopo errore → detailError/error cleared (se policy dismiss = close)
3. non toccare radar-sidebar

NON modificare state.service.ts (A). NON commitare.

Restituisci: diff summary, come hai risolto wipe-on-close, esito test locali se eseguiti.
```

========================================================================
## 4. Prompt sotto-agente C — Docs + Script J + gate
========================================================================

Copia nel Task C (dopo merge A+B):

```
Obiettivo T-P1-04-C: verificare gate FE e chiudere SoT ticket.

Workspace: c:\Users\lucag\Documents\Dashboard finance
NON implementare altro codice salvo typo docs.

### C1 — Script J
cd radar/frontend
Select-String -Path src/app/services/state.service.ts -Pattern "detailError"
# Atteso: match su signal + uso in error computed / loadCountryArticles / clear

Select-String -Path src/app/app.ts -Pattern "detailError|clearError"
# Atteso: catch non wipe cieco; close intenzionale clear

### C2 — Test FE
cd radar/frontend
npm run test:ci
# Atteso: verde. Riporta N passed/failed.
Opzionale: npm run typecheck se usato in CI.

### C3 — Freeze check
git diff --name-only | Select-String "radar-sidebar"
# Atteso: ZERO path sidebar.

### C4 — Docs SoT
Crea/aggiorna:
- plan-audit/remediation/audit_remediation_T-P1-04.md → DONE + policy clearError + gate table + handoff T-P1-05
- plan-audit/active/plan_docs_audit_ticket_status.md §3: T-P1-04 DONE; P1 OPEN resta T-P1-05 (=1); totali OPEN coerenti; § esito
- plan-audit/active/plan_docs_audit_playbook.md: §3.6/§4.6 criteri spuntati; App. D riga log se presente

NON commit. Restituisci tabella gate PASS/FAIL + conteggi SoT.
```

========================================================================
## 5. DoD orchestratore (firma prima di dichiarare DONE)
========================================================================

- [ ] `detailError` presente; `error()` unisce map-summary + detail
- [ ] Fallimento nation → `error()` truthy → banner toolbar (U5)
- [ ] Catch `onCountryClick` non wipe immediato di `detailError`
- [ ] Close intenzionale / clear path resetta `detailError`
- [ ] Zero file sotto `radar-sidebar/**` nel diff
- [ ] `npm run test:ci` verde (riportare N)
- [ ] Script J match attesi
- [ ] SoT §3 T-P1-04 = DONE; report remediation; handoff **T-P1-05**
- [ ] Nessun commit/push

### Output finale orchestratore (italiano)
1. Verdetto: PASS / PASS_WITH_GAPS / FAIL
2. Tabella file touched (A/B/C)
3. Scelta API clearDetailArticles / preserve-on-error
4. Esiti gate (Script J, test:ci N, freeze)
5. Diff conteggi OPEN SoT
6. Handoff one-liner T-P1-05
```
