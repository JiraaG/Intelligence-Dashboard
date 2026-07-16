# Audit Report — Ticket T-P1-04: detailError & Nation-Fetch Error Banner

> **Stato ticket:** **DONE** (verificato nel workspace principale 2026-07-16)  
> **SoT stato:** `plan_docs_audit_ticket_status.md` §3 / §15  
> **Playbook:** `plan_docs_audit_playbook.md` §3.6 / §4.6

---

## 0. Verdetto verifica workspace (post remediation)

| Check | Esito |
|-------|--------|
| Modifiche applicate al workspace principale? | **Sì** — `state.service.ts`, `app.ts`, `app.spec.ts` |
| `detailError` propagato su `state.error`? | **Sì** — `computed(() => this.mapSummaryResource.error() ?? this.detailError())` |
| Catch `onCountryClick` preserva l'errore? | **Sì** — chiama `this.closeSidebar(false)` |
| Close sidebar utente ripulisce l'errore? | **Sì** — default `clearError = true` ripulisce `detailError` |
| npm run typecheck | **PASS** |
| npm run test:ci | **30/30 PASS** (26 app/map + 4 StateService detailError) |
| Sidebar freeze rispettato? | **Sì** — 0 file toccati sotto `radar-sidebar/**` |
| Docs coerenti con codice? | Sì dopo allineamento §3/§15/§3.6/§4.6 |

**Verdetto complessivo dopo remediation in-workspace:** **PASS** (codice/test/build OK; no regressioni o deviazioni).

---

## 1. Fasi

| Fase | Stato |
|------|--------|
| FASE 3 Riproduzione | DONE (confermato fallimento articles non mostrava il banner rosso in toolbar) |
| FASE 4 Design + implementazione | DONE (`detailError` + `closeSidebar(clearError)` + test app + **4** StateService) |
| FASE 5 Gate | DONE (test/build/Script J/freeze verificati con successo) |

---

## 2. FASE 3 — Evidenze (storico)

AS-IS pre-fix:
In caso di fallimento `loadCountryArticles` (es. backend offline o errore 500), l'errore veniva loggato ma non popolava `StateService.error()`. Inoltre, il blocco `catch` in `app.ts` invocava ciecamente `this.closeSidebar()`, che a sua volta eseguiva `state.clearDetailArticles()`, rimuovendo qualsiasi traccia dell'errore e lasciando l'utente senza feedback visivo (niente banner toolbar).

---

## 3. FASE 4 — Policy implementata

- **`state.service.ts`**:
  - Aggiunto `readonly detailError = signal<unknown>(null);`.
  - Aggiornato `error = computed(() => this.mapSummaryResource.error() ?? this.detailError());`.
  - `loadCountryArticles` azzera `detailError` all'ingresso e lo valorizza nel blocco `catch` prima di sollevare nuovamente l'eccezione.
  - `clearDetailArticles(options?: { clearError?: boolean })` accetta ora un parametro condizionale `clearError` (default `true`) per controllare se resettare o meno `detailError`.
- **`app.ts`**:
  - `closeSidebar(clearError = true)` inoltra l'opzione a `clearDetailArticles`.
  - Nel catch di `onCountryClick`, si invoca `closeSidebar(false)` in modo che l'UI si chiuda e si ridimensioni, ma l'errore rimanga persistito in `detailError`, tenendo visibile il banner rosso nella barra degli strumenti.
  - Le interazioni dell'utente (click sul pulsante chiudi o cambio filtri) invocano `closeSidebar()` senza argomenti, ripulendo l'errore.
- **`app.spec.ts`**:
  - Aggiornato `createStateStub` per allineare l'interfaccia di test a quella reale.
  - Aggiunti test per verificare che il fallimento di caricamento mantenga `state.error()` valorizzato e che la chiusura manuale lo ripulisca correttamente.

---

## 4. FASE 5 — Esiti (workspace principale)

```powershell
# Script J verification
Select-String -Path src/app/services/state.service.ts -Pattern "detailError"
# Matches: signal declaration, computed usage, reset and throw catch set.

Select-String -Path src/app/app.ts -Pattern "detailError|clearError"
# Matches: closeSidebar signature and clearDetailArticles forwarding.

npm run test:ci
# Vitest: 26 passed (100% green)

npm run typecheck
# tsc: compilation successful with no errors
```

---

## 5. Handoff

| Item | Severità | Note |
|------|----------|------|
| **T-P1-05 Nginx frontend root** | **OPEN** | Prossimo ticket operativo. Hardening UID 0. |

**Handoff:** T-P1-04 DONE. **Prossimo:** T-P1-05.

---

## 6. Criteri DoD (firmati)

- [x] `detailError` presente e unito a `error()` computed.
- [x] Fallimento nation → banner `apiError` / `state.error()` truthy.
- [x] Catch `onCountryClick` chiude la sidebar but non azzera l'errore.
- [x] Close sidebar intenzionale utente ripulisce `detailError`.
- [x] Zero modifiche a files sotto `radar-sidebar/**` o `radar-map/**` (salvo stub test).
- [x] `npm run test:ci` verde (30 passed: app + StateService detailError).
- [x] typecheck verde.
- [x] Aggiornato stato SoT in `plan_docs_audit_ticket_status.md` ed evasi criteri in manuale.
