# Framework ECC (Everything Claude Code)

Harness per vincolare l’agente alle regole di produzione. Overlay Radar a **tre superfici**: policy/SoT in `.agents/` + `radar/.ecc/`, enforcement Cursor in `.cursor/`.

---

## Tre superfici

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
| `rules/` | Path-scoped SoT: `backend.md`, `frontend.md`, `docker.md` |
| `agents/` | Profili prompt: `pipeline-engineer`, `angular-map-expert`, `geo-data-architect` |
| `hooks/` | Logica security/lint: `pre-tool-use.py`, `post-tool-use.py` |
| `skills/` | Mirror flat delle skill (sync da `.agents`) |

### Adapter Cursor — `.cursor/`

| Path | Ruolo |
|------|--------|
| `hooks.json` | Eventi `preToolUse` / `postToolUse` / `afterFileEdit` |
| `hooks/*-adapter.py` | Adapter sottili → delegano a `radar/.ecc/hooks/*.py` |
| `rules/radar-*.mdc` | Globs nativi → puntano al SoT in `.ecc/rules` (no testo duplicato) |
| `commands/` | Shortcut: `radar-verify`, `radar-smoke`, `radar-lint` |

Piani Phase 0–6 (**DONE / GATE VERDE**, riferimento — non backlog): [`plan_impl_phase_0_6.md`](../plan-audit/complete/plan_impl_phase_0_6.md) + [`plan_impl_phase_0_6_execution.md`](../plan-audit/complete/plan_impl_phase_0_6_execution.md) (voce **ECC expansion wiring — DONE**).  
Final Release (residui, **≠** GATE): [`plan_release_final_gate.md`](../plan-audit/active/plan_release_final_gate.md).  
Checklist docs: [`plan_docs_monorepo_source.md`](../plan-audit/complete/plan_docs_monorepo_source.md).  
Manuale ECC: [`ecc_deep_dive_analysis_v2.md`](../ecc_deep_dive_analysis_v2.md) — descrittivo; per LLM multi-model / skill map aggiornata preferire SoT LLM + `.agents/skills/` (deep-dive può essere stale).  
Handoff expansion (eseguito): [`handoff_ecc_expansion.md`](../plan-audit/archive/ecc/handoff_ecc_expansion.md).  
Non usare come piano vivo: `Fase2_Implementation_Plan.md`, `plan*.md` in archive, `ecc_deep_dive_analysis.md` (V1 assente).

---

## Skills (sintesi)

**Core**

1. **angular-developer** — Signals, standalone, pattern Angular 21  
2. **llm-json-extraction** — Gemini SDK (`google-genai`) + OpenAI-compat httpx (`deepseek`/`openai`/`glm`/`grok`; dialect); schema Pydantic **strict**, CSV `str`, no CoT; path: `classification/` + `worker.py`  
3. **spatial-data-mocking** — offline FE via `MOCK_MODE` esplicito; sidebar freeze  

**Dominio Radar** (SoT `.agents/skills/radar-*/SKILL.md`)

4. **radar-sidebar-freeze** — zero touch `radar-sidebar/**`; `p-carousel` only  
5. **radar-api-contract** — map-summary + envelope `{items,next_cursor,total}`; `MOCK_MODE`  
6. **radar-docker-ops** — edge/data, live/ready, verify-geojson, `./data/postgres`  
7. **radar-geojson-assets** — gitignore + `--fetch` in Docker build; `ASSET_LICENSE`  
8. **radar-quota-ledger** — reserve/complete/fail; limiti per-lane `LLM_SIMPLE_*`/`LLM_COMPLEX_*`; soft-trim = `LLM_SIMPLE.rpd`; 429; free vs paid budget; provider `gemini`\|`deepseek`\|`openai`\|`glm`\|`grok`\|`claude` (**stub**)

---

## Hooks

| Hook (logica) | Comportamento (Phase 6) |
|---------------|-------------------------|
| `pre-tool-use.py` | Blocca path vietati, secret pattern, comandi pericolosi; domini solo `==` o `.endswith('.'+allowed)` |
| `post-tool-use.py` | Da root `radar/`: ruff su `.py`, prettier su FE; **fail** se linter assente; placeholder = soft warn |

**Registrazione Cursor (DONE):** `.cursor/hooks.json` → `.cursor/hooks/*-adapter.py` → `radar/.ecc/hooks/*.py`.  
Rules path-scoped native: `.cursor/rules/radar-*.mdc` (globs → SoT `radar/.ecc/rules/*`).  
`settings.json` **non** duplica la registrazione; documenta policy + **fallback manuale** (`AGENTS.md` §6, `hooks.notes`).  
Prerequisito host per post-hook Python: `ruff` sul `PATH`.

---

## Vincoli da non contraddire

- Sidebar freeze: `radar-sidebar/**` + `p-carousel`
- Ingest solo `worker.py`; API in `main.py`
- Reti `radar-edge` / `radar-data`; health live vs ready
- Cluster: radius **40**, `spiderfyOnMaxZoom: false`; nation hub disco + fan tutte le icone (no hard cap 24; size/distanza adattivi)
- Pydantic CSV `str`; FE `string[]` solo post-API
- `MOCK_MODE` esplicito; no fallback silenzioso; nation-fetch `detailError` → banner (T-P1-04)
- Docker: no tag `latest`; FE `npm ci --legacy-peer-deps`

Dettaglio operativo: [`.agents/AGENTS.md`](../.agents/AGENTS.md), [`radar/.ecc/CLAUDE.md`](../radar/.ecc/CLAUDE.md).
