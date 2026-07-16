# Prompt — Chiusura 100% (residui docs post P2 close)

> **Uso:** copia il blocco `text` sotto in un **nuovo** chat Agent.  
> **Scope:** solo i 5 residui che impediscono il verdetto **100% conforme** (docs/report/handoff).  
> **Non** commit/push salvo richiesta. **Non** toccare `radar-sidebar/**` né codice BE/FE salvo evidenza di regressione.  
> **Precondizioni:** G1–G5 codice già fatti; gate verdi (117 / 30 / typecheck); Compose up. Branch: `refactor/testing`.

```text
/goal Porta la chiusura P2 + Final Release Handoff al **100% conforme**.
Workspace: `c:\Users\lucag\Documents\Dashboard finance`.
Tu sei l’ORCHESTRATORE: fixa SOLO i residui documentali sotto, verifica, emetti PASS.
NON commitare / NON pushare. NON toccare radar-sidebar/**.
NON riaprire ticket P*. NON eseguire chaos/SAST/seed. NON rifare rebuild Docker
salvo necessità di citare stato AS-IS dei container.

========================================================================
## 0. Perché non siamo al 100% (verifica Cursor 2026-07-16)
========================================================================

Codice + gate = OK. Mancano solo questi residui:

| ID | Residuo | File | Fix obbligatorio |
|----|---------|------|------------------|
| R1 | Manuale §2.4 stale | `plan-audit/active/audit_problemi_documentazione.md` | Titolo `## 2.4 P2 — OPEN (backlog)` → `## 2.4 P2 — DONE (chiusi)`; ogni riga tabella con ~~strike~~ o suffisso **DONE**; allineare a pie P2=0 |
| R2 | Report G2 sovrastima | `plan-audit/remediation/audit_remediation_T-P2_batch.md` | Non dire che `"Nessuna"` è “completamente rimossa”. Scrivere: fallback non usa `"Nessuna"`; match in description/`parse_csv_list` (sinonimi) = **attesi e corretti** |
| R3 | Report senza G3 + Nit FE | stesso report | Aggiungere sezione Focus Tecnico: G3 narrow except `(AttributeError, TypeError, IndexError, ValueError)`; Nit hoist `getComputedStyle` una volta in `parseGeoJsonIncremental` |
| R4 | Handoff §C overclaim | `plan-audit/remediation/audit_remediation_final_release_handoff.md` | Compose health: db/backend/frontend/miniflux = healthy; **worker = running** (`healthcheck: disable: true` by design, no HTTP). Backup-restore = **residuale / non validato in questo turno** (non “validati”) |
| R5 | Wording Docker coerente | handoff (+ report se cita Compose) | Mai “all services healthy”. Usa tabella stato servizi. |

Contesto già OK (non rifare):
- parser except ristretto; hoist stroke; §3 ticket DONE; header remediation CLOSED
- pytest 117; FE 30; typecheck; sidebar diff vuoto
- handoff menu D presente

SoT: risoluzione §3 + manuale FASE 2 + report P2 + handoff.
Guardrail: `.agents/AGENTS.md` (sidebar freeze).

========================================================================
## 1. Policy
========================================================================

- Allowlist **solo** `plan-audit/**` (docs). Zero edit `radar/backend/**`, `radar/frontend/**`
  salvo regressione dimostrata (non attesa).
- Nessun nuovo ticket. Nessun commit.
- Dopo fix: gate leggero §3 (grep stale + opz. pytest/npm solo se hai toccato codice = no).

========================================================================
## 2. Esecuzione (un agente docs basta; opz. parallelo verify)
========================================================================

### Agente DOCS — `generalPurpose` · ID: P2-100
```
Workspace: c:\Users\lucag\Documents\Dashboard finance
Chiudi R1–R5. Solo plan-audit/**.

1) audit_problemi_documentazione.md §2.4:
   - retitle DONE
   - tabella P2 tutte DONE (stesso stile di §2.2/§2.3)
2) audit_remediation_T-P2_batch.md:
   - correggi paragrafo G2 (no “completamente rimossa”)
   - aggiungi G3 + Nit FE in Focus Tecnico
   - se citi Docker: wording R4/R5
3) audit_remediation_final_release_handoff.md:
   - §B o §C: tabella servizi Compose (healthy vs worker running)
   - backup-restore = residuale non validato qui
   - menu D invariato
4) Spot grep anti-regressione:
   Select-String -Path plan-audit/active/audit_problemi_documentazione.md -Pattern "P2 — OPEN|P2 OPEN codice\" : 8|prossimo T-P2-01"
   Select-String -Path plan-audit/active/audit_problemi_documentazione_risoluzione.md -Pattern "prossimo T-P2-01|T-P2-02 OPEN|T-P2-06 WEAK|P2 OPEN codice \| 8"
   Select-String -Path plan-audit/remediation/audit_remediation_T-P2_batch.md -Pattern "completamente rimossa"
   # Atteso: 0 match sullo stato corrente (match storici in scratch/prompt OK)

Output: diff summary per R1–R5 + esito grep.
```

### Orchestratore (dopo)
1. Conferma grep R1–R5 puliti.
2. Opz. conferma AS-IS Docker (no rebuild):
   `docker compose ps` → worker senza Health; altri healthy.
3. Verdetto **PASS 100%**.
4. Domanda menu D (commit / PR / Final Release gate / stop).

========================================================================
## 3. Gate DoD (docs-only)
========================================================================

```powershell
cd "c:\Users\lucag\Documents\Dashboard finance"

# Anti-stale (stato corrente)
Select-String -Path plan-audit/active/audit_problemi_documentazione.md `
  -Pattern 'P2 — OPEN \(backlog\)|"P2 OPEN codice" : 8|prossimo T-P2-01'
# Atteso: 0

Select-String -Path plan-audit/remediation/audit_remediation_T-P2_batch.md `
  -Pattern "completamente rimossa"
# Atteso: 0

Select-String -Path plan-audit/remediation/audit_remediation_T-P2_batch.md `
  -Pattern "AttributeError|_has_matching_close_tag|getComputedStyle|parseGeoJsonIncremental"
# Atteso: match (G1/G3/Nit documentati)

Select-String -Path plan-audit/remediation/audit_remediation_final_release_handoff.md `
  -Pattern "healthcheck: disable|running|backup-restore|residuale"
# Atteso: worker wording + backup residuale presenti

# Sidebar freeze (sanity)
git diff --stat -- radar/frontend/src/app/components/radar-sidebar
# → vuoto

# Opz. se dubbi codice (non obbligatorio docs-only):
# cd radar; $env:PYTHONPATH="backend"; python -m pytest -m "not live" -q
```

Checklist:
- [ ] R1–R5 DONE
- [ ] Nessun “P2 OPEN backlog” / “completamente rimossa” / “all services healthy”
- [ ] Handoff Docker + backup wording precisi
- [ ] Report cita G3 + Nit
- [ ] Nessun commit/push
- [ ] Verdetto: **PASS 100%**

========================================================================
## 4. Output orchestratore (italiano)
========================================================================

1. Verdetto: **PASS 100%** / PASS_WITH_GAPS / FAIL
2. Tabella R1–R5 → DONE
3. File touched (solo plan-audit)
4. Esiti grep DoD
5. Handoff one-liner + domanda menu D:
   1 commit locale · 2 PR · 3 Final Release gate · 4 stop
```

---

## Note

- Questo prompt **non** rifà il batch P2 né G1–G5 codice: solo igiene docs per chiudere il gap al 100%.
- Se §2.4 va allineato anche in FASE 2 altre sezioni che ripetono “OPEN backlog”, fixa coerentemente senza riscrivere lo storico FASE 0.
- Commit/PR restano **fuori** finché non scegli la voce del menu.
