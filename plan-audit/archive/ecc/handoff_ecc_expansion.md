# ECC Expansion Handoff — Wiring + Skills (post V2)

**Progetto:** Radar Informativo Globale  
**Workspace:** `c:\Users\lucag\Documents\Dashboard finance`  
**Branch:** `refactor/enterprise-consolidation`  
**Tip noto (al momento della stesura):** Phase 6 `56c2eff` · ECC remediation `526c856`  
**Manuale SoT:** [`ecc_deep_dive_analysis_v2.md`](ecc_deep_dive_analysis_v2.md) §5–6  
**Skill Cursor hooks:** `C:\Users\lucag\.cursor\skills-cursor\create-hook\SKILL.md`  
**Sidebar freeze:** `radar/frontend/src/app/components/radar-sidebar/**` — **zero touch**

Questo file è l’**handoff eseguibile**. Non serve una nuova Phase nel piano prodotto: i contenuti ECC sono già allineati al codice; qui si chiude il gap di **wiring harness** + espansione **selettiva** skills-first (logica ECC upstream).

---

## 1. Verdetto: si esegue (con questo ordine)

| Domanda | Risposta |
|---------|----------|
| Serve un nuovo Implementation_Plan Phase? | **No** — non è lavoro prodotto Phase 0–6 |
| Si può eseguire subito? | **Sì**, in blocchi P0 → P1 → P2 con gate |
| Cosa NON fare | Clonare repo ECC; 67 agent; memory/instincts; toccare sidebar; commit/push senza richiesta |

---

## 2. Obiettivo

Rendere l’overlay Radar **enforced in Cursor** dove oggi è solo documentale, e aggiungere **skill di dominio** solo se chiudono gap ripetuti — senza reinventare l’OS ECC.

**Done quando:**
1. Hook Python Radar girano via `.cursor/hooks.json` (pre/post o equivalent)
2. Rules path-scoped caricate da Cursor via globs (o `.cursor/rules`)
3. Almeno le skill P1 prioritizzate esistono sotto `.agents/skills/` + mirror `.ecc` + skill map CLAUDE
4. Checklist §7 verde; sidebar diff vuoto
5. Voce in `plan_impl_phase_0_6_execution.md`: “ECC expansion wiring DONE” (senza inventare SHA)

---

## 3. Ground truth (non reinventare)

- SoT skill Cursor = `.agents/skills/*/SKILL.md` → mirror `radar/.ecc/skills/`
- Hook logica = `radar/.ecc/hooks/pre-tool-use.py` + `post-tool-use.py` (già Phase 6 + dual tool names)
- Rules SoT = `radar/.ecc/rules/{backend,frontend,docker}.md`
- Cursor hooks nativi: `.cursor/hooks.json` + opz. wrapper in `.cursor/hooks/`
- Upstream ECC: skills-first; adapter sottili; non paste raw `hooks.json` upstream
- Vincoli prodotto immutabili: worker-only ingest, 10 categorie, overlay full-bleed, cluster 40/spiderfy false, MOCK_MODE, prettier FE

---

## 4. Piano ordinato

### P0 — Wiring Cursor (obbligatorio, primo)

| ID | Task | Note |
|----|------|------|
| W1 | Leggere create-hook skill + stub stdin degli hook Radar | Capire JSON Cursor vs JSON ECC hook |
| W2 | Creare `.cursor/hooks.json` | Eventi minimi: `preToolUse` + `postToolUse` e/o `afterFileEdit` |
| W3 | Wrapper `.cursor/hooks/*.ps1` o `.cmd`/`.sh` se serve | Windows: `python` path; cwd progetto; failClosed dove ha senso (pre) |
| W4 | Adattare stdin/stdout se il contratto Cursor ≠ exit 1 Radar | Preferire **adapter sottile** che chiama gli script esistenti; non riscrivere la logica security/lint |
| W5 | Smoke test locale | Echo JSON → pre (block secret) ; post su file `.py`/`.ts` (ruff/prettier) |
| W6 | Aggiornare `AGENTS.md` §6 + `settings.hooks.notes` + `docs/04` | Default non più “solo manuale” se auto-wiring attivo; tenere fallback manuale documentato |
| W7 | `.cursor/rules/` con globs | Puntano o includono truth da `radar/.ecc/rules/*` (backend/frontend/docker); non duplicare testo lungo |

**Gate P0:**
```text
# Esiste wiring
Test-Path .cursor/hooks.json

# Sidebar freeze
git diff --stat -- radar/frontend/src/app/components/radar-sidebar
# → vuoto

# Pre-hook ancora blocca pattern secret (via adapter o diretto)
```

### P1 — Skills dominio + sync (selettivo)

Creare **solo** queste skill (ordine raccomandato). Formato ECC: `.agents/skills/<name>/SKILL.md`.

| ID | Skill | Trigger | Contenuto obbligatorio |
|----|-------|---------|------------------------|
| S1 | `radar-sidebar-freeze` | Qualsiasi UI laterale / carousel | **BLOCCA** edit `radar-sidebar/**`; p-carousel only; read-unread solo state+map |
| S2 | `radar-api-contract` | `main.py`, `articles_query`, FE `article.service` | map-summary; envelope `{items,next_cursor,total}`; DTO; MOCK_MODE |
| S3 | `radar-docker-ops` | Compose, Dockerfile, runbook | edge/data; live vs ready; verify-geojson; `./data/postgres`; deferred digest |
| S4 | (opz.) `radar-geojson-assets` | `assets/data`, Dockerfile FE | ASSET_LICENSE pin; `--fetch`; gitignore |
| S5 | (opz.) `radar-quota-ledger` | `quota.py`, ledger SQL | reserve/complete/fail; 429; RPD |

Poi:
- Mirror flat in `radar/.ecc/skills/`
- Righe in skill map `radar/.ecc/CLAUDE.md`
- Script o doc sync: una riga in V2 / CLAUDE su “SoT = `.agents`”

**Gate P1:** skill appaiono come playbook leggibili; nessuna contraddizione con `AGENTS.md` / rules.

### P2 — Commands minimi + profili (opzionale stesso sprint)

| ID | Task |
|----|------|
| C1 | Documentare 2–3 shortcut in `CLAUDE.md` o `.cursor/commands/` se supportato: verify / smoke runbook / lint |
| C2 | Nota in CLAUDE: quando spawnare Task con prompt `angular-map-expert` / `pipeline-engineer` / `geo-data-architect` |
| C3 | (opz.) rule sottile `testing.md` path-scoped tests |

**Fuori scope P2:** MCP pack, AgentShield, memory-persistence, clonare commands ECC.

---

## 5. Vincoli di esecuzione

- Patch minime; niente big-bang rewrite di AGENTS
- Preferire adapter Cursor → script `.ecc/hooks` esistenti
- Dopo ogni blocco: sidebar diff vuoto
- Allineare docs ECC al wiring reale
- Commit/push **solo** su richiesta esplicita utente
- Non modificare prodotto Phase 0–5 salvo blocco reale del wiring

---

## 6. File toccati (previsti)

```text
.cursor/hooks.json
.cursor/hooks/*                    # wrapper se necessari
.cursor/rules/*                    # globs → .ecc/rules
.agents/AGENTS.md                  # § hooks
.agents/skills/radar-*/SKILL.md    # P1
radar/.ecc/skills/*.md             # mirror
radar/.ecc/CLAUDE.md               # skill map
radar/.ecc/settings.json           # hooks.notes
docs/04_ecc_framework.md
ecc_deep_dive_analysis_v2.md       # stato “wiring DONE” breve
plan_impl_phase_0_6_execution.md   # voce expansion DONE
```

Possibile touch minimo a `pre/post-tool-use.py` **solo** se serve compat JSON Cursor (preferire wrapper).

---

## 7. Checklist accettazione

```text
Test-Path .cursor/hooks.json
# → True

rg -n "hooks\.json|auto" docs/04_ecc_framework.md .agents/AGENTS.md radar/.ecc/settings.json

# Skill freeze esiste
Test-Path .agents/skills/radar-sidebar-freeze/SKILL.md

git diff --stat -- radar/frontend/src/app/components/radar-sidebar
# → vuoto

# Nessuna regressione categorie illegali nei mock ECC
rg -n "primary_category: '(Chip|Acqua|Elettronica)'" .agents/skills radar/.ecc
```

---

## 8. Prompt pronto per nuova chat

Copiare il blocco in Agent mode:

```text
# Handoff — ECC Expansion (wiring Cursor + skills selettive)

## Contesto
- Workspace: `c:\Users\lucag\Documents\Dashboard finance`
- Branch: `refactor/enterprise-consolidation`
- Tip: Phase 6 `56c2eff` · ECC remediation `526c856` (verifica con `git log -3`)
- **Sorgente eseguibile:** `handoff_ecc_expansion.md` (leggerlo per intero PRIMA di patchare)
- Manuale: `ecc_deep_dive_analysis_v2.md` §5–6
- Skill Cursor hooks: leggere `C:\Users\lucag\.cursor\skills-cursor\create-hook\SKILL.md` prima di W2
- Sidebar freeze NON negoziabile: zero touch `radar/frontend/src/app/components/radar-sidebar/**`
- Niente commit/push finché non lo chiedo esplicitamente
- Non clonare repo ECC upstream; non inventare Phase prodotto

## Obiettivo
Chiudere gap harness: hooks auto in Cursor + rules path-scoped native + skill dominio Radar selettive (skills-first).
Una sola verità: adapter Cursor sottili; logica security/lint resta in `radar/.ecc/hooks/*.py`.

## Ordine obbligatorio
1. Leggere `handoff_ecc_expansion.md` + create-hook skill
2. **P0:** `.cursor/hooks.json` (+ wrapper) che invoca pre/post Radar; smoke test; aggiornare AGENTS/docs/04/settings.hooks.notes; `.cursor/rules` globs → `.ecc/rules`
3. **P1:** skill `radar-sidebar-freeze`, `radar-api-contract`, `radar-docker-ops` (+ opz. geojson/quota); mirror `.ecc`; skill map CLAUDE
4. **P2:** solo se P0–P1 verdi — commands/note spawn profili (minimo)
5. Checklist §7 handoff
6. Aggiornare `plan_impl_phase_0_6_execution.md` con “ECC expansion wiring DONE” (no SHA inventato)

## Metodo
- Patch minime; adapter > rewrite hook
- Dopo ogni blocco: `git diff -- radar/frontend/src/app/components/radar-sidebar` vuoto
- Preferisci allineare docs al wiring, non il contrario
- Usa sottoagenti per verify parallelo se utile; patch le applichi tu

Parti da P0. Non commitare.
```

---

## 9. Cronologia

| Quando | Cosa |
|--------|------|
| 2026-07-15 | Phase 6 `56c2eff` + remediation `526c856` |
| 2026-07-15 | Manuale V2 `ecc_deep_dive_analysis_v2.md` |
| 2026-07-15 | Questo handoff expansion scritto per esecuzione in nuova chat |

**Fine handoff.**
