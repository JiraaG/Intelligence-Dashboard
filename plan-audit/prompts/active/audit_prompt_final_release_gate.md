# Prompt — Final Release Gate (orchestratore multi-fase)

> **Stato 2026-07-17:** Fasi **1–4 PASS** (report in `plan-audit/remediation/audit_remediation_final_release_F*.md`). Fase 5 = **DEFERRED ACCETTATO**.  
> **Uso residuo:** solo **Fase 0 PR** (senza merge) se ancora aperta — non rieseguire backup/seed/chaos/SAST.  
> **Piano SoT:** `plan-audit/active/plan_release_final_gate.md` + [`STATUS.md`](../../STATUS.md).  
> **Precondizioni:** P0–P2 CLOSED; smoke UI fatto; branch `refactor/testing` pushed.

```text
/goal Chiudi il residuo Final Release Gate del Radar: Fase 0 PR
`refactor/testing` → `develop` SENZA merge, secondo
`plan-audit/active/plan_release_final_gate.md` nel workspace
`c:\Users\lucag\Documents\Dashboard finance`.
F1–F4 sono già PASS — NON rieseguire. Fase 5 resta DEFERRED ACCETTATO.
NON fare merge di PR. NON toccare radar-sidebar/**.
NON commitare dump in backups/ né .env.

========================================================================
## 0. Contesto
========================================================================

- Remediation codice CLOSED; handoff: `audit_remediation_final_release_handoff.md`
- Piano dettagliato: `plan-audit/active/plan_release_final_gate.md` (procedure, pro/contro, scelta best)
- Ops: `radar/ops/README.md`, `radar/docs/runbook.md`
- Docker rules: `radar/.ecc/rules/docker.md` (deferred espliciti)
- Branch: `refactor/testing`. Worker = running (no healthcheck HTTP).

### Ordine fasi (scelta migliore del piano)
0 PR (no merge) → 1 Backup/restore → 2 Seed 10k → 3 Chaos → 4 SAST/scan → 5 Deferred (solo nota)

Se l’utente non specifica la fase: inizia da **Fase 0** se non esiste PR;
altrimenti dalla prima fase senza report `audit_remediation_final_release_F*.md`.

========================================================================
## 1. Policy
========================================================================

- Sidebar freeze.
- Restore/chaos: safety backup obbligatorio prima di operazioni distruttive.
- Seed: data dedicata `2099-01-01` (non cancellare dati “oggi”).
- Script ops `*.sh`: Git Bash/WSL, non PowerShell raw.
- Report obbligatorio per ogni fase PASS/FAIL/SKIP.
- Aggiorna checkbox in `plan_impl_phase_0_6.md` §Final Release Gate solo su PASS.
- Aggiorna `audit_remediation_final_release_handoff.md` stato residui.

========================================================================
## 2. Sotto-agenti per fase
========================================================================

### Fase 0 — PR
Task `shell` o `generalPurpose`:
- Verifica working tree clean; `gh pr create --base develop --head refactor/testing`
- Title/body da piano §2; NO merge
- Output: URL PR

### Fase 1 — Backup/restore
Task `shell` (Git Bash se disponibile) + docs:
Allowlist: esecuzione `radar/ops/backup-postgres.sh`, `restore-postgres.sh`;
report `plan-audit/remediation/audit_remediation_final_release_F1_backup.md`
Vietato: `down -v`; commit backups/
DoD: backup dir + restore + health live + UI/API smoke breve
Scelta best: DB restore; `--with-vault` solo se utente ok

### Fase 2 — Seed 10k
Allowlist: `seed_perf_articles.py` via compose exec; psql EXPLAIN;
report `…_F2_seed10k.md`
Data: `2099-01-01`, count 10000
DoD: seed ok + EXPLAIN documentato + smoke FE day-view/nation (browser o istruzioni precise)
Vietato: seed su CURRENT_DATE produzione senza consenso

### Fase 3 — Chaos
Solo dopo Fase 1 PASS (o backup fresco dimostrato)
Scenari minimi C1–C3 da piano §5; C4/C5 se fattibili
Report `…_F3_chaos.md`
Vietato: `docker compose down -v`; edit codice “per far passare”
Query outbox status pre/post

### Fase 4 — Security
Trivy (se assente: installa o SKIP con istruzioni) su immagini chiave;
pip-audit su requirements; XSS spot (browser MCP se utile)
Report `…_F4_security.md`
Policy fail: solo CRITICAL fixabili bloccanti; HIGH documentati

### Fase 5 — Deferred
DEFAULT: scrivere in handoff “DEFERRED ACCETTATO” per digest pin e legacy-peer-deps
con pro/contro dal piano §7. ZERO edit Dockerfile/compose salvo ordine esplicito.

========================================================================
## 3. Gate cross-fase
========================================================================

```powershell
cd "c:\Users\lucag\Documents\Dashboard finance\radar"
docker compose ps
# db/backend/frontend/miniflux healthy; worker running
docker compose exec -T radar-backend curl -sf http://127.0.0.1:8000/health/live
git diff --stat -- radar/frontend/src/app/components/radar-sidebar
# → vuoto
```

========================================================================
## 4. Output orchestratore (italiano, ogni turno)
========================================================================

1. Fase eseguita + verdetto PASS|FAIL|SKIP|DEFERRED
2. Comandi e evidenze (path report)
3. Checkbox Final Release aggiornate?
4. Prossima fase raccomandata
5. Domanda: procedere / fermarsi / commit report?
```

---

## Note per chi lancia

- Per **una sola fase**: aggiungi in cima `/goal … Esegui SOLO Fase N`.
- Per **minimum viable release** (consigliato): Fasi **0 + 1 + 2**, poi stop; 3–4 opzionali; 5 deferred.
- Merge PR: **mai** in questo prompt — chiedilo in un turno dedicato dopo review.
