# Plan prompt — Affinamento classificazione: tipologia, geo (anti-XX), archi multi-nazione

> **Stato: COMPLETE (implementato 2026-07-18)** — prompt anti-XX + categorie; soft-remap politico; docs star; requeue N=20.  
> **Uso:** storico; per rieseguire analisi aprire Plan mode sul blocco sotto.  
> **Contesto empirico recente:** run re-ingest 48h (2026-07-18) — soft-news → `XX`+`Tecnologia`; Spahn/Epstein → categoria discutibile; related bilaterali OK quando presenti; archi undirected `LEAST/GREATEST` × categoria.  
> **Post-fix (sample requeue 20):** Spahn→Geopolitica/DE; Epstein→Geopolitica/US; Laron→Salute/GB; %XX 48h 8.3→6.3; invarianti related OK.  
> **Prova da zero (2026-07-18):** purge-all vault+DB; unread Miniflux; ciclo 48 elaborati / 0 errori; %XX 4.5 (2/44); UE→Ambiente/BE; Dennis→Geopolitica/AU (soft-remap sport); 19 archi star.  
> **Vincoli:** sidebar freeze; Pydantic CSV `str`; `related_countries` max 5, no primary/XX; prompt system immutabile no-CoT (skill `llm-json-extraction`).

---

## PROMPT (incolla in Plan mode)

```text
Ruolo: analyst + architect pipeline LLM Radar Informativo Globale (classification + mappa relazioni).

Obiettivo
Produrre un’ANALISI RIGOROSA e un PIANO ESEGUIBILE (piano only — NESSUN codice finché non richiesto) per perfezionare tre aree:

1) TIPOLOGIA (`primary_category`): l’MLM deve capire il contesto reale dell’articolo e assegnare la categoria più appropriata tra le 10 dello schema — non default “comodi” o spillover errati (es. scandalo politico → Tecnologia; soft-news → Tecnologia per inerzia della regola off-topic).

2) GEOGRAFIA (`country_code`, anti-`XX`): ridurre al minimo `XX`. Preferire sempre una nazione ISO Alpha-2 primaria dedotta con ragionamento contestuale (attori, teatro, istituzioni, autori/affiliations, partecipanti, sede evento, nazionalità implicita). Solo se davvero non determinabile → `XX` (+ lat/lng 0,0). Esempi attesi: Epstein → US; articolo scientifico con autori MIT/Oxford → US o GB; accordo USA–Italia–Francia → primary una nazione + related le altre.

3) ARCHI / LINEE multi-nazione (comportamento AS-IS + gap): documentare e valutare cosa succede OGGI quando ci sono più nazioni (primary + `related_countries`), es. USA accordo con Italia e Francia; evidenziare limiti del modello undirected aggregato e cosa andrebbe perfezionato (prompt, validator, API map-relations, FE archi/click bilaterale).

────────────────────────────────────────
Contesto obbligatorio da leggere PRIMA di pianificare
────────────────────────────────────────
Backend / LLM
- radar/backend/app/classification/prompts.py (§ categorie + REQUISITI GEOGRAFICI + regola soft-news→Tecnologia/XX)
- radar/backend/app/classification/validator.py (ISO allowlist, XX, related_countries constraints, normalize)
- skill .agents/skills/llm-json-extraction/SKILL.md (+ mirror radar/.ecc/skills/)
- radar/backend/app/classification/complexity.py (solo se rileva impatto lane; non è il focus)

Persistenza / API / archi
- migration 011 related_countries; articles_query map-relations (LEAST/GREATEST × primary_category)
- docs/02_architecture_and_backend.md (endpoint GET /api/map-relations)
- docs/03_frontend_and_ui.md § Relazioni + plan-audit/complete/plan_archi_hatching_multicolor.md
- plan-audit/complete/master_plan_impl_phase_H_geospatial_graph.md (§ decisione undirected v1)
- FE: StateService.loadRelationArticles / isBilateralRelationArticle; radar-map drawMacro/Legacy + relationClicked

Evidenze recenti (usare come case study, non come unica verità)
- Soft-news / XX: Epstein, Laron, cambio cognome, orfanotrofio; pezzo UE emissioni → XX
- Categoria discutibile: Spahn (politica/surrogacy) → Tecnologia; soft → Tecnologia
- Related buoni quando presenti: CA↔US, IR↔{US,KW}, RU↔UA, PH↔CN, …
- Archi: zoom <5 multicolore aggregato per pair; zoom ≥5 1 linea per categoria; click bilaterale filtra related A↔B (± category)

Vincoli NON negoziabili
- Schema Pydantic strict: companies/tags/entities/related_countries = str CSV (non List)
- related_countries: max 5, no country_code primario, no XX, no duplicati
- Una sola country_code primaria (pin/hatching); secondari solo in related_countries
- System prompt: no Chain-of-Thought / no campo reasoning
- Sidebar freeze: non proporre refactor radar-sidebar/**
- No nuove dipendenze npm per archi; no cambiare contratto API a meno che il piano lo giustifichi esplicitamente come P0
- Sentinel geografico nel codice è `XX` (non “WW”); allineare linguaggio del piano a `XX`

────────────────────────────────────────
Domande di analisi obbligatorie (rispondi tutte)
────────────────────────────────────────

### A — Tipologia (`primary_category`)
A1. Mappa le 10 categorie con criteri disambiguazione (quando Geopolitica vs Sicurezza vs Economia vs Tecnologia vs Salute…).
A2. Individua conflitti AS-IS nel prompt (regola soft-news→Tecnologia/XX) vs casi reali (politica interna, scandali, scienza, sport) che oggi vengono mal-classificati.
A3. Proponi regole prompt + eventuali check post-normalize (senza CoT) per forzare coerenza contesto→categoria; elenca anti-pattern.
A4. Come verificare: seed/fixture minimi + assert su primary_category (pytest) e checklist manuale.

### B — Geografia anti-`XX` (`country_code` + related)
B1. Albero decisionale proposto per country_code (teatro evento → attore primario → istituzione → affiliation autori → sede → fallback XX).
B2. Casi tipologici: persona nota (Epstein), paper scientifico, org internazionale (UE/ONU/NATO — come mappare senza inventare ISO finti), disastro naturale, sport, corporate HQ vs paese operazione.
B3. related_countries: quando riempire, ordine/priorità, max 5; come trattare accordi trilaterali+ (US+IT+FR).
B4. Impatto su pin/hatching (`XX` non ha nazione), vault path, map-relations (XX escluso dalle query): cosa non deve rompersi.
B5. Misura successo: % XX su batch 48h prima/dopo; zero primary-in-related; zero XX-in-related.

### C — Linee / archi con più nazioni (comportamento attuale + perfezionamenti)
C1. Descrivi AS-IS end-to-end per un articolo primary=US, related=IT,FR, category=Economia:
    - quante righe map-relations? (US-IT, US-FR? IT-FR?)
    - a zoom <5 e ≥5 cosa si vede?
    - click su un arco: quali articoli entrano in loadRelationArticles (filtro bilaterale)?
C2. Evidenzia limiti: undirected pair-only (niente triangolo IT-FR se non c’è primary/related che li collega direttamente); aggregazione per categoria; click non apre “tutte le nazioni dell’accordo” ma solo la coppia cliccata.
C3. Valuta opzioni di prodotto (solo piano, con trade-off):
    - restare su modello v1 (primary + related → archi star dal primary) e migliorare solo prompt;
    - vs arricchimenti FE (tooltip multi-hop, highlight pair);
    - vs cambi API (fuori scope salvo P0 motivato).
C4. Allineamento docs/ECC se si cambia semantica archi.

────────────────────────────────────────
Output del Plan (formato obbligatorio)
────────────────────────────────────────
1. Verdetto AS-IS (prompt + validator + archi) — cosa funziona / cosa drift
2. Matrice problemi P0/P1/P2 con esempi reali (Epstein, Spahn, UE, trilaterale US-IT-FR)
3. Decisioni proposte (vincolanti) su: regole categoria; regole geo anti-XX; semantica archi multi-nazione
4. Piano di implementazione a wave (es. W1 prompt+test; W2 normalize/validator; W3 docs/ECC; FE solo se necessario)
5. File target precisi + gate di accettazione misurabili
6. Fuori scope esplicito
7. Rischi (over-geo su soft-news; false related; regressione quota LLM)

Regole di esecuzione di QUESTO piano
- Nessun codice in questa chat Plan
- Nessun commit/push
- Non inventare endpoint/colonne non presenti
- Preferisci fix prompt + test rispetto a schema breaking
- Se proponi cambio schema/API, motiva perché prompt-only non basta
```

---

## Note operative post-analisi

Dopo il piano approvato, implementazione tipica (altra chat Agent):
1. Edit `classification/prompts.py` (+ mirror skill `llm-json-extraction`)
2. Test validator/normalize + eventuali seed fixture
3. Requeue mirato (`radar-requeue-ops`) e confrontare % XX / categorie
4. Docs: `docs/02`–`03`, overview §H se cambia semantica archi; ECC rules/skills sync
