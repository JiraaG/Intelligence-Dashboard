# ECC Architecture Audit & Remediation Handoff

**Progetto:** Radar Informativo Globale  
**Workspace:** `c:\Users\lucag\Documents\Dashboard finance`  
**Branch:** `refactor/enterprise-consolidation`  
**Data audit:** 2026-07-15  
**Contesto fasi:** Phase **0–5 DONE**; Phase **6 DONE / GATE VERDE** (working tree **uncommitted** — nessun commit/push finché non richiesto).  
**Restore Phase 5:** `1dfdf60`  
**Sidebar freeze:** `radar/frontend/src/app/components/radar-sidebar/**` — **zero touch** (non negoziabile).

Questo file è la fonte di lavoro per la remediation ECC. Non è un piano prodotto; è un handoff operativo post-audit.

---

## 1. Perché questo audit

Dopo Phase 6 (docs/CI/GeoJSON/runbook) è stata fatta un’analisi completa della struttura ECC (`.agents/` + `radar/.ecc/`) contro il codice deployabile. L’obiettivo è **una sola verità architetturale**: rules, agents, skills, hooks e `settings.json` devono descrivere lo stesso sistema di `worker.py`, Compose edge/data, API Phase 5 e FE Phase 4–5.

**Vincoli permanenti (non riaprire):**

- Sidebar freeze + `p-carousel` (no `article-list`)
- Ingest solo in `radar-worker` / `worker.py`; `main.py` = API-only
- Pydantic Gemini: campi multi-valore `str` CSV (non `List[str]`); no CoT/`reasoning`
- Cluster: `maxClusterRadius: 40`, `spiderfyOnMaxZoom: false`
- `MOCK_MODE` esplicito (no silent fallback)
- 10 categorie: Nucleare, Energia, Infrastrutture, Geopolitica, Economia, Tecnologia, Spazio, Ambiente, Salute, Sicurezza
- Commit/push solo su richiesta esplicita

---

## 2. Inventario struttura ECC (as-is)

### 2.1 Globale — `.agents/`

| Path | Ruolo |
|------|--------|
| `AGENTS.md` | Magna Carta (Cursor / harness global) |
| `skills/angular-developer/SKILL.md` + `references/*` | Pattern Angular 21 (tree references completo) |
| `skills/llm-json-extraction/SKILL.md` | Playbook Gemini / Pydantic / outbox |
| `skills/spatial-data-mocking/SKILL.md` | Mock FE offline |

### 2.2 Locale — `radar/.ecc/`

| Path | Ruolo |
|------|--------|
| `CLAUDE.md` | Entry-point sessione locale |
| `settings.json` | Allowlist tool/domini, path-scoping rules, agentProfiles, secret redaction |
| `rules/backend.md` | Path-scoped backend |
| `rules/frontend.md` | Path-scoped frontend (include Regola 7 map-summary Phase 5) |
| `rules/docker.md` | Path-scoped Compose/Dockerfile |
| `agents/pipeline-engineer.md` | Profilo ingest/pipeline |
| `agents/angular-map-expert.md` | Profilo mappa/Leaflet |
| `agents/geo-data-architect.md` | Profilo DB/migrazioni/commit |
| `skills/llm-json-extraction.md` | Mirror flat della skill LLM |
| `skills/spatial-data-mocking.md` | Mirror flat mock spaziale |
| `skills/angular-developer.md` | Mirror flat (link a `references/` **assenti** sotto `.ecc`) |
| `hooks/pre-tool-use.py` | Pre gate (path/secret/domain) |
| `hooks/post-tool-use.py` | Post gate (ruff / prettier fail-closed) |

**Nota strutturale:** non esiste directory `agent_profiles/`; i profili sono in `settings.json` → `agentProfiles` → file sotto `agents/`. Va bene se intenzionale.

**Doppia SoT:** skill duplicate tra `.agents/skills/*/SKILL.md` e `radar/.ecc/skills/*.md` senza sync automatico → drift già osservato.

---

## 3. Cosa è già allineato (non rompere)

Verificato vs codice post-`1dfdf60` + Phase 6:

| Area | Stato |
|------|--------|
| Sidebar freeze + no `article-list` | OK in AGENTS, CLAUDE, frontend.md, map expert header |
| Ingest `worker.py` / API `main.py` | OK in CLAUDE, pipeline-engineer, AGENTS (header) |
| Reti `radar-edge` / `radar-data` | OK |
| `/health/live` vs `/health/ready` | OK in AGENTS / docker (parziale) |
| MOCK_MODE token | OK frontend.md, CLAUDE, spatial header Phase 4 |
| Cluster radius 40 / spiderfy false | OK frontend.md Regola 7, map expert (sezioni cluster aggiornate) |
| Pydantic `str` CSV / no reasoning | OK CLAUDE, llm skill, pipeline-engineer |
| frontend.md Regola 7 map-summary + envelope | OK |
| Hooks Phase 6: domain `==` / `.endswith('.'+allowed)`; prettier fail-closed | OK nel codice hook |
| CLAUDE header Phase 0–6 GATE VERDE | OK |

---

## 4. Ground truth (estratto codice — usare come SoT)

### 4.1 Categorie (10)

```text
Nucleare, Energia, Infrastrutture, Geopolitica, Economia,
Tecnologia, Spazio, Ambiente, Salute, Sicurezza
```

Sorgente: `radar/backend/app/classification/validator.py` → `PRIMARY_CATEGORIES`  
FE: `radar-map.component.ts` → `CATEGORY_CSS_VARS` / `CATEGORY_ICONS`  
CSS: `radar/frontend/src/styles.scss`

**Vietato nei mock/docs ECC:** `Chip`, `Acqua`, `Elettronica` come `primary_category`.

### 4.2 Cluster

```typescript
maxClusterRadius: 40,
spiderfyOnMaxZoom: false,
zoomToBoundsOnClick: false,
```

File: `radar/frontend/src/app/components/radar-map/radar-map.component.ts`

### 4.3 Layout FE (Phase 4)

- Overlay full-bleed: mappa resta `100vw` con sidebar sopra  
- **Non** split 70%/30% che restringe la mappa  
- `invalidateSize()` dopo open/close sidebar

### 4.4 API FE (Phase 5)

- Day: `GET /api/map-summary`  
- Nation: `GET /api/articles` → `{ items, next_cursor, total }`, page ≤ 100, FE concatena  
- Mock solo via `MOCK_MODE`  
File: `article.service.ts`, `article-mock.service.ts`, `state.service.ts`

### 4.5 Worker loop

- Sleep polling **dopo** try/except del ciclo, **non** in `finally` di shutdown  
- File: `radar/backend/app/worker.py` → `run_pipeline_loop`

### 4.6 Docker backend (reale)

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
HEALTHCHECK ... curl -f http://localhost:8000/health/live
```

Multi-stage; `PYTHONPATH=/app`; worker override Compose: `python -m app.worker`

### 4.7 Docker frontend (reale)

- `npm ci --legacy-peer-deps`  
- `RUN node scripts/verify-geojson.mjs --fetch` **prima** di `npm run build`  
- `FROM nginx:1.27-alpine`  
- GeoJSON gitignored; pin in `ASSET_LICENSE.md`

### 4.8 Compose DB volume

```yaml
- ./data/postgres:/var/lib/postgresql/data
```

Niente named volume `radar-postgres-data` + `driver_opts` nel compose attuale.

### 4.9 FE lint

```json
"lint": "prettier --check \"src/**/*.{ts,html,scss,css,json}\""
```

Post-hook usa **prettier**, non eslint.

### 4.10 Migrazioni

`001` … `007_articles_query_indexes.sql` (geo-data-architect spesso ferma a `006`).

---

## 5. Tabella incongruenze completa

Severità: **A** = può far scrivere codice/architettura sbagliata; **M** = claim falso o desync serio; **B** = stale/minor.

### 5.1 Critiche (A)

| ID | File | Claim errato | Realtà | Azione |
|----|------|--------------|--------|--------|
| A1 | `spatial-data-mocking` (**.agents + .ecc**, byte-sync ma entrambi sbagliati) | `primary_category: 'Chip'/'Acqua'`; checklist Elettronica/Chip/Acqua | 10 categorie chiuse | Remap mock + checklist a categorie valide (es. Tecnologia, Ambiente) |
| A2 | Stesso | Split-screen 70%/30% restringe mappa | Overlay full-bleed Phase 4 | Riscrivere step checklist |
| A3 | Stesso | DI/`getArticles`/`getCountries` only | Phase 5: `getMapSummary` + `getArticlesPage` envelope | Allineare a servizi reali |
| A4 | `angular-map-expert.md` | Sample mock `Chip`; `npx eslint` | Categorie 10; lint = prettier | Fix sample + `npm run lint` |
| A5 | `rules/backend.md` Regola 3 ~L121–130 | Snippet **OBBLIGATORIO** con `finally: await asyncio.sleep(900)` | Contradice Regola 1 + `worker.py` | Sleep **fuori** dal `finally` di shutdown |

### 5.2 Alte (M)

| ID | File | Claim errato | Realtà | Azione |
|----|------|--------------|--------|--------|
| M1 | `rules/docker.md` | `CMD … uvicorn main:app` | `uvicorn app.main:app --workers 1` + HEALTHCHECK live | Sostituire snippet con Dockerfile reale (multi-stage) |
| M2 | `rules/docker.md` | Builder solo `npm run build` | Prima `verify-geojson.mjs --fetch` | Documentare step GeoJSON |
| M3 | `rules/docker.md` | `nginx:alpine-slim` | `nginx:1.27-alpine` | Pin corretto |
| M4 | `rules/docker.md` | Named volume + `driver_opts` | Bind `./data/postgres` | Allineare a compose |
| M5 | `docker.md` / `AGENTS.md` | Digest pin / drop `--legacy-peer-deps` “restano Phase 6” | Phase 6 **DONE**; item **deferred** | Wording “deferred post–Phase 6” |
| M6 | `settings.json` domains | Manca `raw.githubusercontent.com`, `registry.npmjs.org`, `opendatacommons.org` | Hook `ALLOWED_DOMAINS` li ha | Sync settings ↔ hook |
| M7 | `settings.json` tools | Solo nomi ECC | Cursor: Write/Shell/…; hook già dual | Estendere allowlist + note mapping |
| M8 | `settings.json` secrets | Pattern incompleti | Hook ha GEMINI/GOOGLE/POSTGRES | Allineare |
| M9 | `llm-json-extraction` mirrors | Drift flusso: `.agents` ha advisory lock + `complete(reservation_id)`; `.ecc` lista 12 step senza | Due SoT | **SoT = `.agents`**; copiare flusso in `.ecc` |
| M10 | `angular-developer` `.ecc` | Link `references/*.md` | Tree solo sotto `.agents/.../references/` | Path assoluti relativi a `.agents` o nota “usa Cursor skill folder” |

### 5.3 Medie / basse (B)

| ID | File | Gap | Azione |
|----|------|-----|--------|
| B1 | `geo-data-architect.md` | Migrazioni fino a `006` | Aggiungere `007_articles_query_indexes.sql` |
| B2 | `AGENTS.md` §5 / `backend.md` | Poca menzione map-summary / envelope / `articles_query` | Aggiungere 1–2 bullet (frontend.md già completo) |
| B3 | `frontend.md` bounds US/RU | Literal leggermente arrotondati vs codice | Copiare literal esatti da `radar-map` |
| B4 | Hooks registration | Nessuna chiave `hooks` in `settings.json`; AGENTS dice esecuzione **manuale** | Dichiarare esplicitamente in `settings.notes` + `docs/04` che auto-hook dipende dall’harness; default = manuale |
| B5 | `CLAUDE` / `AGENTS` comandi | Manca citazione `verify-geojson`, `radar/docs/runbook.md`, `.github/workflows/ci.yml` | Aggiungere alle sezioni comandi |
| B6 | Optional domain | CartoCDN non in allowlist | Valutare `*.basemaps.cartocdn.com` se tool agente fetchano tile URL |

---

## 6. Drift skill mirrors (dettaglio)

### 6.1 `llm-json-extraction`

| | `.agents/.../SKILL.md` | `radar/.ecc/skills/llm-json-extraction.md` |
|--|------------------------|--------------------------------------------|
| Frontmatter path Gemini | `worker.py` / classification | Allineato |
| Flusso | Compact: advisory lock → reserve → Gemini → `complete(reservation_id)` → outbox | 12 step granulari; **manca** advisory lock e `complete()` |
| Decisione | **Sorgente di verità = `.agents`** | Riscrivere sezione flusso come copia di `.agents` |

### 6.2 `spatial-data-mocking`

| | Stato |
|--|--------|
| Sync tra mirror | **Identici** |
| Correttezza | **Entrambi sbagliati** vs Phase 4/5 (categorie, layout, API) |
| Decisione | Riscrivere **una** volta, poi copiare byte-uguale sull’altro mirror |

### 6.3 `angular-developer`

| | Stato |
|--|--------|
| Body skill | Essenzialmente allineato |
| References | Solo in `.agents/skills/angular-developer/references/` |
| Fix `.ecc` | Cambiare link o aggiungere nota “references vivono in `.agents/...`” |

---

## 7. `settings.json` — gap vs hooks

### Domini in hook ma non in settings

- `raw.githubusercontent.com` (verify-geojson / asset docs)  
- `registry.npmjs.org`  
- `opendatacommons.org`  

### Domini in settings ma policy incompleta

- Presenti: github, miniflux API, googleapis, fonts, docker hub, pypi, npmjs.com  
- Assente prodotto: Carto basemaps (opzionale)

### Tools

Allowlist ECC-only:

```text
view_file, write_to_file, list_dir, grep_search, run_command,
read_url_content, replace_file_content, multi_replace_file_content
```

Hook post/pre già accettano anche: `Write`, `StrReplace`, `Shell`, `WebFetch`, …

### Secrets

Settings: AIza, sk-, ghp_, postgres URL, MINIFLUX_API_KEY  
Hook in più: GEMINI_API_KEY, GOOGLE_API_KEY, POSTGRES_PASSWORD  

**Regola remediation:** `settings.json` e `pre-tool-use.py` devono elencare lo **stesso** set (domains + secrets); tool allowlist documenta mapping Cursor↔ECC.

---

## 8. Piano remediation ordinato

Eseguire in ordine; dopo ogni blocco: nessun touch `radar-sidebar/**`; aggiornare questo file o `Implementation_Plan_Execution.md` con checkbox.

### P0 — Critico (obbligatorio prima di chiudere ECC)

1. Riscrivere `spatial-data-mocking` (entrambe le copie) su:
   - 10 categorie valide  
   - overlay full-bleed  
   - `MOCK_MODE` + `getMapSummary` / `getArticlesPage`  
   - checklist visiva aggiornata (no Chip/Acqua/70%)  
2. Fix sample `Chip` + eslint→prettier in `angular-map-expert.md`  
3. Fix `backend.md` Regola 3: sleep fuori da `finally` (allineare a Regola 1 / `worker.py`)

### P1 — Alto (Docker + settings + SoT skill)

4. Allineare `docker.md` a Dockerfile backend/frontend + compose volume + verify-geojson  
5. Wording “deferred post–Phase 6” per digest / drop legacy-peer-deps (`docker.md`, `AGENTS.md`)  
6. Sync `settings.json` ↔ hooks (domains, secrets, tool aliases + notes)  
7. Unificare flusso `llm-json-extraction` (`.ecc` ← `.agents`)  
8. Fix path references `angular-developer` in `.ecc`

### P2 — Completamento

9. `geo-data-architect.md`: migrazione `007`  
10. AGENTS / backend.md: bullet map-summary + envelope + `articles_query.py`  
11. Bounds US/RU esatti in `frontend.md` se divergenza  
12. Note hooks manuali in `settings.json` + eventuale riga in `docs/04_ecc_framework.md`  
13. Comandi Phase 6 in CLAUDE/AGENTS: `verify-geojson`, runbook, CI workflow  

### Fuori scope (non fare in remediation ECC)

- Commit/push (solo se utente chiede)  
- Refactor prodotto mappa/API/worker  
- Image digest pin / drop `--legacy-peer-deps` (deferred prodotto)  
- Seed 10k / chaos drill Final Release Gate  

---

## 9. Checklist accettazione remediation ECC

```text
# Nessuna categoria illegale nei mock ECC
rg -n "primary_category: '(Chip|Acqua|Elettronica)'" .agents/skills radar/.ecc

# Nessun eslint come linter FE obbligatorio negli agent Radar
rg -n "eslint" radar/.ecc/agents/angular-map-expert.md

# backend Regola 3: nessuno sleep in finally come OBBLIGATORIO
# (leggere rules/backend.md Regola 1 vs 3 — devono concordare)

# settings domains include almeno raw.githubusercontent.com
rg -n "raw.githubusercontent.com" radar/.ecc/settings.json radar/.ecc/hooks/pre-tool-use.py

# Sidebar freeze
git diff --stat -- radar/frontend/src/app/components/radar-sidebar
# → vuoto
```

Gate soft (opzionale): rilettura umana di `CLAUDE.md` + `AGENTS.md` + tre rules dopo le patch.

---

## 10. Riferimenti utili

| Doc / path | Uso |
|------------|-----|
| `Implementation_Plan.md` | Piano master; Phase 6 DONE / GATE VERDE |
| `Implementation_Plan_Execution.md` | Scoreboard; commit Phase 6 pending |
| `docs/04_ecc_framework.md` | Panoramica ECC per operatori |
| `README.md` | Indice docs + mappa piani→codice |
| `radar/docs/runbook.md` | Ops |
| `radar/frontend/src/assets/data/ASSET_LICENSE.md` | Pin GeoJSON |
| Chat audit precedente | Sottoagenti rules + agents/skills/hooks |

**Git tip attuale (prima di commit Phase 6):** working tree sporco con patch Phase 6 docs/CI/ECC parziale; **non** confondere con tip `1dfdf60` (Phase 5).

---

## 11. Prompt pronto per nuova chat

Copiare il blocco seguente in una nuova conversazione Agent:

```text
# Handoff — Remediation ECC (post Phase 6 GATE VERDE)

## Contesto
- Workspace: `c:\Users\lucag\Documents\Dashboard finance`
- Branch: `refactor/enterprise-consolidation`
- Phase 0–5 DONE; Phase 6 DONE / GATE VERDE (docs/CI/GeoJSON/runbook) — **working tree uncommitted**
- Restore Phase 5: `1dfdf60`
- **Sorgente remediation:** `ECC_Architecture_Audit_Handoff.md` in root (leggerlo per intero PRIMA di patchare)
- Piani: `Implementation_Plan.md`, `Implementation_Plan_Execution.md`
- **Sidebar freeze NON negoziabile:** zero touch a `radar/frontend/src/app/components/radar-sidebar/**`
- Niente commit/push finché non lo chiedo esplicitamente
- Non rifattorizzare prodotto Phase 0–5 salvo blocco reale; scope = **solo ECC** (`.agents/`, `radar/.ecc/`, eventualmente `docs/04_ecc_framework.md` se serve una nota hooks)

## Obiettivo
Chiudere tutte le incongruenze elencate in `ECC_Architecture_Audit_Handoff.md` §§5–8, in ordine P0 → P1 → P2.
Una sola verità: rules/agents/skills/hooks/settings = codice reale (worker, Compose, API Phase 5, FE Phase 4–5).

## Ordine di lavoro obbligatorio
1. Leggere `ECC_Architecture_Audit_Handoff.md` (ground truth §4 + tabelle §5)
2. **P0:** spatial-data-mocking (entrambe le copie) + angular-map-expert Chip/eslint + backend.md Regola 3 sleep
3. **P1:** docker.md reale + wording deferred post–Phase 6 + settings.json sync hooks + llm-json-extraction unify + angular-developer references path
4. **P2:** geo-data 007, AGENTS/backend map-summary bullets, hooks note, comandi verify/runbook/CI in CLAUDE/AGENTS
5. Eseguire checklist accettazione §9 del handoff
6. Aggiornare `Implementation_Plan_Execution.md` con voce “ECC remediation DONE” (senza inventare commit SHA)

## Ground truth rapido (non inventare)
- 10 categorie (no Chip/Acqua/Elettronica come primary_category)
- Cluster 40 / spiderfyOnMaxZoom false
- Overlay full-bleed (no 70/30)
- map-summary + articles envelope {items,next_cursor,total}
- MOCK_MODE token
- worker.py ingest; uvicorn app.main:app
- FE lint = prettier; post-hook prettier
- verify-geojson --fetch in Docker FE
- Postgres bind ./data/postgres
- SoT skill LLM = `.agents/skills/llm-json-extraction/SKILL.md` → sync mirror `.ecc`

## Metodo
- Sii scrupoloso; patch minime; niente big-bang rewrite di AGENTS se non necessario
- Dopo ogni blocco: `git diff -- radar/frontend/src/app/components/radar-sidebar` vuoto
- Preferisci allineare docs ECC al codice, non il contrario
- Usa sottoagenti se utile per verify parallelo, ma applica tu le patch

Parti da P0. Non commitare.
```

---

## 12. Cronologia audit

| Quando | Cosa |
|--------|------|
| 2026-07-15 | Phase 6 docs/CI/GeoJSON/runbook GATE VERDE |
| 2026-07-15 | Audit ECC completo (rules + agents/skills/hooks/settings) |
| 2026-07-15 | Questo handoff scritto in root per remediation in nuova chat |

**Fine handoff.**
