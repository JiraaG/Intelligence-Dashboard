# Plan prompt — Mappa 3D (globe) + archi: switch 2D/3D vs 3D-only

> **Stato: ACTIVE (non eseguito)** — incollare in **Plan mode** in una chat nuova.  
> **Output atteso:** analisi + piano (e draft blueprint da inserire in `radar_overview_and_upgrades.md` §3 nuova lettera, es. **I**). **Nessun codice** finché non approvato.  
> **Roadmap:** A/B/H DONE; C `pgvector` BACKLOG; questo upgrade è **indipendente** da C.  
> **Data prompt:** 2026-07-20.

---

## PROMPT (incolla in Plan mode)

```text
Ruolo: analyst + architect frontend geospaziale — Radar Informativo Globale (Intelligence Dashboard).
Modalità: SOLO ANALISI + PIANO (nessun codice finché non richiesto).
Output: verdetto AS-IS vs TO-BE, decisione vincolante 2D↔3D vs 3D-only, blueprint per overview §3, piano a wave.

════════════════════════════════════════
OBIETTIVO
════════════════════════════════════════
Valutare l’introduzione di una mappa **3D** (globe / terrain) al posto o accanto all’attuale mappa **2D Leaflet**, includendo le **linee di relazione** (archi bilaterali già in Fase H).

Domanda di prodotto da chiudere con **una** raccomandazione vincolante:
1) **Switch 2D ↔ 3D** (stesso giorno-view: pin/hatching/archi/spiderfy/sidebar) — pro/contro complessità + peso browser.
2) **Solo 3D** (deprecare Leaflet day-view come path primario) — pro/contro funzionalità e “alla fine tutti scelgono 3D”.
3) Ibrido soft (es. 3D default + fallback 2D automatico su device deboli) — solo se (1) o (2) non bastano; motivare.

Ambito minimo da coprire nel blueprint (poi da scrivere in radar_overview_and_upgrades.md):
- Globe/mappa 3D: nazioni (GeoJSON o equivalente), day-view summary, zoom/rotazione.
- Archi relazioni in 3D (geodesiche / great-circle / tube) parity con AS-IS: macro multicolore zoom basso, tratteggio/fan per categoria a zoom alto, hover/click → carosello bilaterale.
- Pin / hub / spiderfy / marker-read / Notizie Salvate: cosa resta 2D-overlay, cosa va riscritto.
- Performance browser (GPU WebGL, mobile, air-gapped tiles §3.D).
- Impatto Angular 21 + ESBuild (oggi Leaflet via angular.json scripts[] → window.L).
- Fuori scope esplicito di QUESTA analisi: implementazione codice, Fase C pgvector, sidebar freeze refactor, cambio API backend salvo gap 3D documentati.

════════════════════════════════════════
CONTESTO APPLICATIVO (obbligatorio)
════════════════════════════════════════
Radar = webapp self-hosted:
- Ingest: Miniflux → radar-worker → LLM → PostgreSQL + vault Obsidian.
- FE: Angular 21, mappa full-bleed, sidebar overlay (p-carousel — SIDEBAR FREEZE).
- Day-view: GET /api/map-summary → hatching + pin nazione (conic categorie) su centroide.
- Nation open: GET /api/articles envelope; hub + spiderfy emoji per categoria.
- Relazioni: GET /api/map-relations → archi Leaflet pane relationsPane (z 550), click → loadRelationArticles.
- Tile: CartoDB/OSM via rete; §3.D overview = mappe offline FUTURE (air-gap).
- Stack mappa AS-IS: Leaflet 1.9.4 + leaflet.markercluster 1.5.3 (UMD global, NON import ESBuild nei componenti).

Vincoli non negoziabili da rispettare nel piano:
- Sidebar freeze: non refactorare radar-sidebar/** oltre eccezioni mirate (save + related_countries chips).
- MOCK_MODE esplicito; niente fallback silenzioso a mock.
- Overlay full-bleed: mappa 100vw; sidebar sopra.
- Contratto API Phase 5+ invariato se possibile (map-summary / map-relations / articles / saved).
- Nessun package che rompa la policy monorepo senza motivazione (valutare Cesium / Mapbox GL / deck.gl / globe.gl / three-globe — scegliere max 2–3 candidati, non elencare 20 librerie).

Preferenza product owner (da pesare, non da assumere come decisione):
- Interessato allo **switch** 2D/3D per mappa E linee.
- Dubbio su “leggerezza” browser se dual-mode.
- Alternativa: **solo 3D** per non complicare lo sviluppo — “alla fine 3D lo scelgono tutti”.
- Deliverable docs: introdurre il cambio in radar_overview_and_upgrades.md (nuova sezione upgrade, es. §3.I).

════════════════════════════════════════
LETTURE OBBLIGATORIE PRIMA DI CONCLUDERE
════════════════════════════════════════
Product / FE
- radar_overview_and_upgrades.md §1–2 AS-IS FE mappa; §3 tabella stati (A/B/H DONE, C BACKLOG, D/G future); §3.H archi AS-IS GATE; §3.D tiles offline (vincolo air-gap su scelta 3D)
- docs/03_frontend_and_ui.md (Leaflet, day-view, spiderfy, relationsPane, saved parity)
- README.md (stack FE, porte)
- plan-audit/STATUS.md (restore rilevanti: archi UI, map anchors a240b3c)

Codice (solo lettura per AS-IS — non modificare in questa chat)
- radar/frontend/src/app/components/radar-map/ (o path equivalente radar-map.component.*)
- state.service.ts (mapSummary / relations / sidebar coupling)
- angular.json scripts[] Leaflet/MarkerCluster
- stilizzazione archi / hatching (SCSS + geometric dash)

Skills / rules
- .agents/skills/radar-api-contract/SKILL.md (map-summary, map-relations)
- .agents/skills/radar-sidebar-freeze/SKILL.md
- .agents/skills/spatial-data-mocking/SKILL.md (checklist visiva 2D da preservare in parity 3D)
- .agents/AGENTS.md §5 regole mappa (cluster radius 40, spiderfy custom, US/RU mainland bounds, overlay)

════════════════════════════════════════
DOMANDE DI ANALISI (rispondi TUTTE)
════════════════════════════════════════

### A — AS-IS
A1. Cosa fa oggi Leaflet che un globe 3D deve preservare (parity checklist)?
A2. Dove sono gli hot-path performance (GeoJSON countries, cluster, canvas relations, invalidateSize)?
A3. Cosa NON è portabile 1:1 in 3D (spiderfy DOM markers, conic-gradient pin CSS, geometric dash polylines)?

### B — Opzioni architetturali
B1. Confronta 2–3 stack 3D realistici per Angular 21 (es. CesiumJS, MapLibre/Mapbox GL + terrain, globe.gl/three). Tabella: licenza, offline tiles, bundle size, maturità archi, effort FE.
B2. Per ciascuna opzione: come si disegnano gli archi relazioni (parity H) e i pin nazione.
B3. Impatto air-gapped (§3.D): serve terrain/imagery online? Fallback?

### C — Switch vs 3D-only (decisione vincolante)
C1. Costo engineering dual-renderer (due code path) vs rewrite unico 3D.
C2. Costo runtime: memoria GPU, mobile, laptop integrati; soglia “device troppo debole”.
C3. UX: quando l’utente preferirebbe ancora 2D (hatching globale, ops dense, accessibilità)?
C4. Scegli **UNA** strategia: Switch | 3D-only | 3D-default+fallback2D. Motivazione ops + prodotto + rischio.

### D — Blueprint overview
D1. Bozza sezione `### I. Mappa 3D …` per radar_overview_and_upgrades.md (stato BACKLOG, requisiti, diagramma mermaid, knobs, out of scope).
D2. Aggiornamento tabella stati in §3 (I = BACKLOG).
D3. Criteri di accettazione testabili (parity H + day-view + saved + performance budget).

### E — Piano implementativo (solo se raccomandazione ≠ “non fare”)
E1. Wave corte (W1 spike/PoC → W2 parity day-view → W3 archi → W4 spiderfy/sidebar → W5 docs/ECC).
E2. File toccati previsti; cosa non toccare (sidebar freeze, API).
E3. Rollback: come tornare a Leaflet-only.
E4. Relazione con Fase C pgvector: indipendente; non bloccare C.

════════════════════════════════════════
FORMATO OUTPUT RICHIESTO
════════════════════════════════════════
1) Executive summary (≤12 righe): raccomandazione unica + perché.
2) Matrice parity AS-IS → 3D (feature / gap / mitigation).
3) Tabella stack 3D candidati + scelta.
4) Decisione Switch vs 3D-only (vincolante).
5) Draft markdown pronto da incollare in radar_overview_and_upgrades.md §3.I (e riga tabella stati).
6) Piano wave + accettazione + fuori scope.
7) Domande aperte residue (max 5, solo bloccanti).

Salva l’analisi in plan-audit/active/ (es. plan_impl_map_3d_globe.md) e aggiorna STATUS solo se l’utente lo chiede dopo approvazione.
```

---

## Note per l’orchestratore

- Modalità consigliata: **Plan** (read-only) finché non si approva il blueprint.
- Non confondere con Fase C (`pgvector`) né con tile offline §3.D (citare solo come vincolo).
- Dopo approvazione: patch overview §3 + eventuale piano in `plan-audit/active/` → poi impl a wave.
