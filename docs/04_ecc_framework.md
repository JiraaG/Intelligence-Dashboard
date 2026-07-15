# Framework ECC (Everything Claude Code)

Harness per vincolare l’agente alle regole di produzione. Trigger e caricamento dipendono dal client (Cursor, Claude Code, ecc.).

---

## Due namespace

### Globale — `.agents/`

| Path | Ruolo |
|------|--------|
| `AGENTS.md` | Magna Carta: stack, freeze sidebar, Docker, cluster, health |
| `skills/*/SKILL.md` | Playbook attivabili (`angular-developer`, `llm-json-extraction`, `spatial-data-mocking`) |

### Locale — `radar/.ecc/`

| Path | Ruolo |
|------|--------|
| `CLAUDE.md` | Entry-point sessione + stato Phase 0–6 |
| `settings.json` | Tool/domain whitelist |
| `rules/` | Path-scoped: `backend.md`, `frontend.md`, `docker.md` |
| `agents/` | Profili: `pipeline-engineer`, `angular-map-expert`, `geo-data-architect` |
| `hooks/` | `pre-tool-use.py`, `post-tool-use.py` |
| `skills/` | Mirror locale delle skill |

Piani eseguibili: [`Implementation_Plan.md`](../Implementation_Plan.md) + [`Implementation_Plan_Execution.md`](../Implementation_Plan_Execution.md).  
Non usare come piano vivo: `Fase2_Implementation_Plan.md`, `plan*.md`, `ecc_deep_dive_analysis.md`.

---

## Skills (sintesi)

1. **angular-developer** — Signals, standalone, pattern Angular 21
2. **llm-json-extraction** — Gemini SDK, schema Pydantic **strict**, CSV `str`, no CoT; path codice: `classification/` + `worker.py` (non ingest in `main.py`)
3. **spatial-data-mocking** — offline FE via `MOCK_MODE` esplicito; sidebar freeze

---

## Hooks

| Hook | Comportamento (Phase 6) |
|------|-------------------------|
| `pre-tool-use.py` | Blocca path vietati, secret pattern, comandi pericolosi; domini solo `==` o `.endswith('.'+allowed)` |
| `post-tool-use.py` | Da root `radar/`: ruff su `.py`, prettier su FE; **fail** se linter assente; placeholder = soft warn |

**Registrazione:** `settings.json` **non** auto-registra gli hook nell’harness. Default operativo = esecuzione **manuale** (vedi `AGENTS.md` §6 e `settings.json` → `hooks.notes`). Auto-hook solo se l’harness esterno lo configura esplicitamente.

---

## Vincoli da non contraddire

- Sidebar freeze: `radar-sidebar/**` + `p-carousel`
- Ingest solo `worker.py`; API in `main.py`
- Reti `radar-edge` / `radar-data`; health live vs ready
- Cluster: radius **40**, `spiderfyOnMaxZoom: false`
- Pydantic CSV `str`; FE `string[]` solo post-API
- `MOCK_MODE` esplicito; no fallback silenzioso
- Docker: no tag `latest`; FE `npm ci --legacy-peer-deps`

Dettaglio operativo: [`.agents/AGENTS.md`](../.agents/AGENTS.md), [`radar/.ecc/CLAUDE.md`](../radar/.ecc/CLAUDE.md).
