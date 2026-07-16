# Prompt — Allineamento docs MD + architettura ECC (ARCHIVIO — eseguito)

> **Stato:** eseguito 2026-07-16 (commit `c358391` + follow-up post T-P1-04).  
> **Non rieseguire** come remediation codice. Prossimo ticket codice SoT: **T-P1-05**.  
> Blocco sotto = storico (post T-P0-02 / OPS-FIX).

> **Uso storico:** copia il blocco `text` sotto in un nuovo chat Agent (read-only prima, poi edit mirati).  
> **Scope:** solo documentazione / regole ECC / skill — **non** remediation ticket codice.  
> **Non** commit/push salvo richiesta esplicita. **Non** toccare `radar-sidebar/**`. **Non** commitare `.env`.

```text
/goal Allinea la documentazione Markdown e l’architettura ECC al runtime reale del repo
`c:\Users\lucag\Documents\Dashboard finance` dopo T-P0-02 DONE + OPS-FIX init_pool + ops Gemini/Miniflux.
Prima fai un audit di drift (sola lettura), poi applica fix docs minimi. Non implementare T-P1-04/05/P2.

---

## Contesto (SoT runtime)

- Branch tipico: `refactor/testing`
- Gate: Phase 6 / Gate Verde
- Ticket codice DONE recenti: T-P0-01, T-P1-03, T-P1-01, T-P1-02, T-P0-02
- Prossimo ticket codice: **T-P1-04** (`detailError` / banner nation-open)
- OPS-FIX committato: `init_pool` retry su `CannotConnectNowError` (compose restart parallelo)
- Ops locali (possono essere solo `.env`, non in git):
  - `MINIFLUX_LIMIT=50` (limit=100 → payload ~6.8MB > `MAX_MINIFLUX_RESPONSE_BYTES=5MB`)
  - `GEMINI_MODEL=gemini-3.1-flash-lite` (`gemma-4-31b-it` restituiva HTTP 500 → fallback summary)
- Spiderfy map: **niente hard cap 24**; tutte le icone categoria; restore hub on failure
- Scripts: niente `ClassificationClient()` vuoto / `_wait_for_rate_limit` sotto `backend/scripts/**/*.py`

## Alberi da controllare (allowlist)

### Audit / plan
- `plan-audit/active/plan_docs_audit_playbook.md`
- `plan-audit/active/plan_docs_audit_ticket_status.md`
- `plan-audit/audit_remediation_*.md`
- `plan-audit/audit_prompt_*.md`
- `plan-audit/active/plan_impl_phase_0_6.md`
- `plan-audit/active/plan_impl_phase_0_6_execution.md`
- `plan-audit/scratch/*` (solo nota “storico” se drift; non riscrivere audit grezzi salvo citazioni false operative)

### ECC / agents / skills
- `radar/.ecc/CLAUDE.md`
- `radar/.ecc/rules/docker.md` (già aggiornato Regola 4 — verificare coerenza)
- `radar/.ecc/rules/backend.md`
- `radar/.ecc/rules/frontend.md`  ← sospetto stale spiderfy ≤24 / SPIDERFY_MAX_ICONS
- `radar/.ecc/agents/*.md` (pipeline-engineer, angular-map-expert, …)
- `radar/.ecc/skills/*.md` + mirror `.agents/skills/**` (quota-ledger, docker-ops, llm-json-extraction, …)
- `.agents/AGENTS.md`
- `docs/01_getting_started.md`

## Pattern di drift da cercare (grep)

- `SPIDERFY_MAX_ICONS`, `≤24`, `max 24`, `cap 24`
- `ClassificationClient()`, `_wait_for_rate_limit`, `stress_test_rate_limiter`
- `T-P0-02` ancora OPEN / `P0 next` / `prossimo T-P0-02`
- `gemma-4-31b` come unico modello obbligatorio senza nota fallback ops
- `compose restart` senza caveat depends_on / `CannotConnectNowError`
- `MINIFLUX_LIMIT=100` come default consigliato senza warning payload
- Path SoT root `audit_problemi_*.md` invece di `plan-audit/`
- Migrazioni “≤003” / “001–007” se il tree ha 008+
- `radar-network`, `Phase 0-2` legacy

## Compito

### Fase A — Audit (sola lettura)
Tabella: path | claim stale | verità runtime (file:line o comando) | severità (P0 docs / P1 / nota)

### Fase B — Fix docs (solo se confermato)
- Aggiorna ECC frontend / angular-map-expert sullo spiderfy senza cap 24
- Allinea CLAUDE.md / AGENTS se migrazioni, reti, modello LLM, Script I post-fix
- Documenta in docker-ops / getting started: preferire `up -d` o restart ordinato; `MINIFLUX_LIMIT` tipico 50 sotto cap 5MB
- Nota ops (non ticket): modello `gemini-3.1-flash-lite` se Gemma 31b 500; non hardcodare segreti
- Chiudi incongruenze audit residue se ancora presenti
- **Non** cambiare codice prodotto salvo typo commento in docs

### Fase C — Verifica
- Grep dei pattern sopra → 0 claim operativi falsi nei path allowlist (scratch può restare storico se marcato)
- Elenco file toccati + diff summary
- Handoff: T-P1-04 ancora prossimo per codice

## Output obbligatorio (italiano)
1. Verdetto: `CLEAN` / `DRIFT_FIXED` / `DRIFT_REMAINING`
2. Tabella drift trovati
3. File modificati
4. Residui consapevoli (es. scratch audit storici)
5. Prompt one-liner per T-P1-04 se docs OK
```
