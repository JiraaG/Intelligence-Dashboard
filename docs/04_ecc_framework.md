# Framework ECC (Everything Claude Code)

Harness per vincolare l’agente alle regole di produzione. Overlay Radar a **tre superfici**: policy/SoT in `.agents/` + `radar/.ecc/`, enforcement Cursor in `.cursor/`.

**Manuale operativo SoT** per agenti e operatori. Deep-dive descrittivo: [`ecc_deep_dive_analysis_v2.md`](../ecc_deep_dive_analysis_v2.md) (può restare dietro sull’inventario — preferire questo file + skill map).

**Fonti upstream:** GitHub [affaan-m/ECC](https://github.com/affaan-m/ECC) + [cross-harness.md](https://raw.githubusercontent.com/affaan-m/ECC/main/docs/architecture/cross-harness.md) + Mintlify. **CodeWiki** ([codewiki.google/…/ecc](https://codewiki.google/github.com/affaan-m/ecc)) è spesso shell vuota — **non** usarla come SoT.

**Prompt base sempre-on:** **NO**. [`.agents/AGENTS.md`](../.agents/AGENTS.md) è già Magna Carta iniettata ogni turno. Nessun slash `/radar-preamble`. Aggiungere in chat *“usa skill X”* solo se il path non è in skill map o il workflow ops non è path-triggered.

---

## Tre superfici (enforce vs guida)

| Superficie | Guida (soft) | Enforce (hard) |
|------------|--------------|----------------|
| `.agents/` | `AGENTS.md` + skill playbook | — (Cursor carica AGENTS; skill on trigger) |
| `radar/.ecc/` | `CLAUDE.md`, agents, mirror skill, `settings.json` | Logica hook in `hooks/*.py`; rules SoT |
| `.cursor/` | `commands/` shortcut | `hooks.json` + adapters; `rules/*.mdc` globs |

### Globale — `.agents/`

| Path | Ruolo |
|------|--------|
| `AGENTS.md` | Magna Carta: stack, freeze sidebar, Docker, cluster, health, hook auto + fallback |
| `skills/*/SKILL.md` | **SoT playbook** Cursor (`angular-developer`, `llm-json-extraction`, `spatial-data-mocking`, `radar-*`) |

### Locale — `radar/.ecc/`

| Path | Ruolo |
|------|--------|
| `CLAUDE.md` | Entry-point sessione + skill map + nota spawn profili |
| `settings.json` | Tool/domain whitelist; `hooks.notes` (non registra Cursor) |
| `rules/` | Path-scoped SoT: `backend.md`, `frontend.md`, `docker.md`, `testing.md` |
| `agents/` | Profili prompt: `pipeline-engineer`, `angular-map-expert` (MapLibre 3D-primary + facade; Leaflet legacy freeze), `geo-data-architect` |
| `hooks/` | Logica security/lint: `pre-tool-use.py`, `post-tool-use.py` |
| `skills/` | Mirror flat delle skill (sync da `.agents`) |
| `scripts/sync_skills.py` | `--check` / `--write` SoT → mirror — **dopo ogni edit** a `.agents/skills/*/SKILL.md` |

### Adapter Cursor — `.cursor/`

| Path | Ruolo |
|------|--------|
| `hooks.json` | Eventi `preToolUse` / `postToolUse` / `afterFileEdit` |
| `hooks/*-adapter.py` | Adapter sottili → delegano a `radar/.ecc/hooks/*.py` |
| `rules/radar-*.mdc` | Globs nativi → puntano al SoT in `.ecc/rules` (no testo lungo duplicato) |
| `commands/` | Shortcut: `radar-verify`, `radar-smoke`, `radar-lint` |

Piani Phase 0–6 (**DONE / GATE VERDE**, riferimento — non backlog): [`plan_impl_phase_0_6.md`](../plan-audit/complete/plan_impl_phase_0_6.md) + [`plan_impl_phase_0_6_execution.md`](../plan-audit/complete/plan_impl_phase_0_6_execution.md) (voce **ECC expansion wiring — DONE**).  
Final Release (**F0–F4 COMPLETE** 2026-07-18; PR #1 merged; Fase 5 deferred accettato, non richiesto): [`STATUS.md`](../plan-audit/STATUS.md) · [`plan_release_final_gate.md`](../plan-audit/complete/plan_release_final_gate.md) · handoff [`audit_remediation_final_release_handoff.md`](../plan-audit/remediation/audit_remediation_final_release_handoff.md).  
FONTI feed management (**COMPLETE / GATE VERDE** 2026-07-27): [`plan_impl_fonti_feed_management.md`](../plan-audit/complete/plan_impl_fonti_feed_management.md) · walkthrough [`walkthrough_fonti_feed_management.md`](../plan-audit/complete/walkthrough_fonti_feed_management.md).  
Checklist docs: [`plan_docs_monorepo_source.md`](../plan-audit/complete/plan_docs_monorepo_source.md).  
Handoff expansion (eseguito): [`handoff_ecc_expansion.md`](../plan-audit/archive/ecc/handoff_ecc_expansion.md).  
Non usare come piano vivo: `Fase2_Implementation_Plan.md`, `plan*.md` in archive, `ecc_deep_dive_analysis.md` (V1 assente).

---

## Strumento → quando usare

| Strumento | Quando | Non usare per |
|-----------|--------|---------------|
| **AGENTS.md** | Vincoli immutabili globali (sidebar freeze, worker vs API, cluster 40, MOCK_MODE) | Tutorial lunghi / how-to |
| **Skill** | Workflow ripetuto ≥2–3×, anti-pattern costosi, `when_to_use` chiaro | One-shot, copia di AGENTS, Angular/Python generici già in `angular-developer` |
| **Rule** (`.ecc/rules` + `.mdc`) | “Non violare” path-scoped | Playbook passo-passo |
| **Hook** | Enforcement HARD (secret, path vietati, lint fail-closed, allowlist dominio) | “Ricorda di leggere skill X”; memory/SessionStart upstream |
| **Agent** (`radar/.ecc/agents/*`) | Task specialista scope ristretto | Auto-dispatch di massa |
| **Command** | Shortcut 1–5 comandi | Sostituire una skill lunga |

Regola d’oro (upstream cross-harness): comportamento durevole in skill/rules/hooks; adapter sottili. Se per cambiare un workflow editi tre copie harness, la SoT è nel posto sbagliato.

---

## Skills (sintesi)

**Core**

1. **angular-developer** — Signals, standalone, pattern Angular 21  
2. **llm-json-extraction** — Gemini SDK (`google-genai`) + OpenAI-compat httpx (`deepseek`/`openai`/`glm`/`grok`; dialect); schema Pydantic **strict**, CSV `str`, no CoT; path: `classification/` + `worker.py`  
3. **spatial-data-mocking** — offline FE via `MOCK_MODE` esplicito; sidebar freeze; checklist FinOps STATUS/COSTI (Test 8) + **FONTI** Giorno/Catalogo (Test 9)

**Dominio Radar** (SoT `.agents/skills/radar-*/SKILL.md`)

4. **radar-sidebar-freeze** — freeze `radar-sidebar/**` + eccezione mirata (toggle Salva e chip `related_countries`); `p-carousel` only  
5. **radar-api-contract** — map-summary + saved-summary + envelope `{items,next_cursor,total}` (+ `saved=true`); PATCH read/save; metrics FinOps; **FONTI** `GET/PATCH /api/feeds` + by-feed `date_field`; `MOCK_MODE`  
6. **radar-docker-ops** — edge/data, live/ready, verify-geojson, `./data/postgres`; Miniflux `dns:` + `verify_miniflux_egress`; ops backup → [`ops/README.md`](../radar/ops/README.md) §Windows
7. **radar-geojson-assets** — gitignore + `--fetch` in Docker build; `ASSET_LICENSE`  
8. **radar-quota-ledger** — reserve/complete/fail; limiti per-lane `LLM_SIMPLE_*`/`LLM_COMPLEX_*`; BORDERLINE → `purpose=classify:complex` con effort da `LLM_BORDERLINE_REASONING_EFFORT`; soft-trim = `LLM_SIMPLE.rpd`; RPM/TPM attesa stessa lane; RPD esaurita → `QuotaDailyExceeded` + residual cross-lane; 429 Retry-After; free vs paid budget; provider `gemini`\|`deepseek`\|`openai`\|`glm`\|`grok`\|`claude` (**stub**)  
9. **radar-requeue-ops** — re-ingest Miniflux: dry-run → exec → `restart radar-worker`

Skill map path → skill: [`radar/.ecc/CLAUDE.md`](../radar/.ecc/CLAUDE.md).

---

## Checklist nuova skill

```text
1. Gate: workflow ≥2–3× OR anti-pattern costoso OR conoscenza non ovvia dal codice
2. Creare .agents/skills/<name>/SKILL.md
   - frontmatter: name, description, when_to_use, version
   - Quando usare / Vincoli / Anti-pattern / SoT path reali
3. Aggiornare skill map in radar/.ecc/CLAUDE.md
4. python radar/.ecc/scripts/sync_skills.py --write
5. Non contraddire AGENTS.md / rules
6. Non creare skill per: one-shot, tutorial generici, copia di AGENTS
```

---

## Checklist nuovo / esteso hook

```text
1. Solo enforcement HARD (secret, path vietati, linter fail-closed, allowlist)
2. Estendere logica in radar/.ecc/hooks/pre|post-tool-use.py (SoT)
3. Tenere settings.json domains/secrets in sync con i pattern hook
4. Adapter .cursor/hooks/*-adapter.py: toccare solo se cambia contratto JSON Cursor
5. Smoke: echo JSON | python .cursor/hooks/pre-tool-use-adapter.py → permission allow/deny
6. NON usare hook per “ricordare di leggere una skill”
7. NON paste raw hooks.json upstream / memory-persistence
```

---

## Sync mirror

SoT playbook = `.agents/skills/<name>/SKILL.md`.  
Mirror flat = `radar/.ecc/skills/<name>.md` (non è nel catalogo Cursor).

```bash
# Da root monorepo
python radar/.ecc/scripts/sync_skills.py --check   # exit 0 se allineati
python radar/.ecc/scripts/sync_skills.py --write   # copia SoT → mirror
```

Dopo ogni edit a una skill SoT: `--write` poi `--check` (exit 0). In CI/locale un `--check` fallito = mirror stale.

---

## Anti-pattern

- Clonare il catalogo ECC upstream (~67 agents / ~200+ skills) nel monorepo  
- Duplicare testo lungo nelle `.mdc` (devono restare pointer + globs)  
- Hook-as-reminder (“leggi skill X”)  
- Skill one-shot o copia di `AGENTS.md`  
- Paste raw `hooks.json` / installer ECC massivo  
- Usare CodeWiki vuota come SoT  
- Editare tre copie dello stesso playbook (`.agents` + `.ecc` + `.mdc`) invece dello SoT + sync  

---

## Hooks

| Hook (logica) | Comportamento (Phase 6) |
|---------------|-------------------------|
| `pre-tool-use.py` | Blocca path vietati, secret pattern, comandi pericolosi; domini solo `==` o `.endswith('.'+allowed)` |
| `post-tool-use.py` | Da root `radar/`: ruff su `.py`, prettier su FE; **fail** se linter assente; placeholder = soft warn |

**Registrazione Cursor (DONE):** `.cursor/hooks.json` → `.cursor/hooks/*-adapter.py` → `radar/.ecc/hooks/*.py`.  
**Distinzione enforcement:** logica Radar in `radar/.ecc/hooks/post-tool-use.py` è **fail-closed** se eseguita direttamente. L’adapter Cursor (`.cursor/hooks/post-tool-use-adapter.py`) converte i fallimenti in **advisory** (`additional_context`, `exit 0`) per non interrompere la sessione IDE. Pre-hook resta **deny** anche via adapter.  
Rules path-scoped native: `.cursor/rules/radar-*.mdc` (globs → SoT `radar/.ecc/rules/*`).  
`settings.json` **non** duplica la registrazione; documenta policy + **fallback manuale** (`AGENTS.md` §6, `hooks.notes`).  
Prerequisito host per post-hook Python: `ruff` sul `PATH`.

---

## Vincoli da non contraddire

- Sidebar freeze: `radar-sidebar/**` + `p-carousel` (eccezione mirata: toggle Salva e chip `related_countries`)
- Ingest solo `worker.py`; API in `main.py`
- Reti `radar-edge` / `radar-data`; health live vs ready
- Spiderfy: path MapLibre = fan custom (no MC); path Leaflet legacy = radius **40**, `spiderfyOnMaxZoom: false`; nation hub disco + fan tutte le icone (no hard cap 24; size/distanza adattivi)
- Overlay resize: `map.resize()` (MapLibre) / `invalidateSize()` (Leaflet)
- Notizie Salvate: `saved-summary` + `?saved=true`; click nazione = zoom/spiderfy parity LETTE/TROVATE; save⇒read, unread⇒unsave
- Pydantic CSV `str`; FE `string[]` solo post-API
- `MOCK_MODE` esplicito; no fallback silenzioso; nation/saved-fetch `detailError` → banner (T-P1-04)
- Docker: no tag `latest`; FE `npm ci --legacy-peer-deps`

Dettaglio operativo: [`.agents/AGENTS.md`](../.agents/AGENTS.md), [`radar/.ecc/CLAUDE.md`](../radar/.ecc/CLAUDE.md).
