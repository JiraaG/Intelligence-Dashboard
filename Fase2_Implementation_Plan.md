# Fase 2 — Piano di implementazione riveduto (versione 2)

> [!WARNING]
> ## ARCHIVIO STORICO — NON ESEGUIRE
> Questo file è **materiale storico pre–enterprise consolidation**.  
> Contiene claim **falsi** rispetto al codice attuale (es. Python 3.11, Miniflux `latest`, CORS GET-only, ingest in `main.py` / `TaskGroup`, bootstrap DB senza migrazioni).  
> **Piani eseguibili:** [`Implementation_Plan.md`](Implementation_Plan.md) + [`Implementation_Plan_Execution.md`](Implementation_Plan_Execution.md) (Phase 0–5 DONE; Phase 6 governance).  
> Non usare V2 sotto come checklist di implementazione.

---

# (Archivio) Contenuto originale

La Fase 1 (README + 4 file docs/) ha costruito una base solida e funzionante. La Fase 2 aveva l'obiettivo di allineare la documentazione allo stato del codice di allora. Quanto segue resta solo come traccia storica.

---

> [!NOTE]
> ## V2 — storicizzato (non vincolante)
> Le sezioni V1 più sotto restano come storico dell'analisi iniziale. **Né V1 né V2 sono piani eseguibili** sul tree post Phase 0–5.

## V2 — Base fattuale, decisioni e perimetro

La documentazione resta in italiano ed è destinata a operatori, sviluppatori e DevOps. Le fonti di verità sono: `docker-compose.yml` per servizi, porte e volumi; i Dockerfile per build/runtime; `.env.example` e `core/config.py` per configurazione; `database.py`/`main.py` per DDL/API; backend per la pipeline; Angular e `angular.json` per la UI; `.agents/AGENTS.md` e `radar/.ecc/` per la governance. I link devono essere relativi e portabili, mai `file:///`; non includere segreti, credenziali o API key plausibili.

| Area | Stato verificato da documentare |
|---|---|
| Runtime | I Dockerfile usano `python:3.11-slim`; Python 3.12 è una regola ECC, non il runtime corrente. Node 22, Nginx 1.27 e PostgreSQL 15 sono tag; Miniflux è `latest`. npm usa `install`, pip usa `>=`: niente claim di versioni immutabili. |
| Rete | Sono esposti frontend `80:80` e Miniflux `8080:8080`. Backend e PostgreSQL sono interni. Il deployment è self-hosted, non offline: RSS, Google GenAI e tile Carto sono esterni. |
| Asset/licenza | `countries.geo.json` serve alla mappa ma è ignorato da Git e non ha provisioning; `LICENSE` non è tracciato nonostante badge/claim MIT. |
| Config | `GOOGLE_API_KEY` ha precedenza su `GEMINI_API_KEY`; `DEBUG` non è letto dal backend e va rimosso. I nomi corretti per login Miniflux sono `MINIFLUX_ADMIN_USERNAME` e `MINIFLUX_ADMIN_PASSWORD`. |
| Pipeline | Refresh Miniflux best effort all'avvio, polling ogni 900 s, articoli unread delle ultime 48 ore, RPD, `TaskGroup`, dedup URL, quattro tentativi LLM. |
| Dati/API | `reasoning` non è persistito/esposto. DB e Vault non sono una transazione distribuita. API: health, due GET con `date`/`sentiment`/`relevance_level`, PATCH read status. Il CORS autorizza oggi soltanto GET. |
| Mappa | Dieci cluster group monocategoria, `maxClusterRadius: 40`, coordinate mediate per paese, dummy/root marker e spiderfy custom a zoom 6; nessun anello multi-categoria o soglia zoom 12. |
| ECC | Rules, skill e hook richiedono un harness compatibile. Il post-hook è non bloccante e tenta Ruff/ESLint per file scritti; non esegue Prettier. |

### Decisioni P0 prima della redazione finale

| Decisione | Raccomandazione |
|---|---|
| Python | Allineare entrambi gli stage a Python 3.12 e testare, oppure documentare onestamente 3.11. |
| PATCH CORS | Aggiungere `PATCH` a `allow_methods` e coprire la preflight `OPTIONS` con test. |
| Cluster | Allineare AGENTS/rules/profile al design attuale; rifattorizzare soltanto se si desidera davvero il design ad anello. |
| GeoJSON | Tracciare l'asset (Git/LFS) oppure fornire script con provenienza, licenza e checksum prima della build. |
| Licenza | Aggiungere una `LICENSE` valida o rimuovere badge e dichiarazione MIT. |

Le seguenti modifiche runtime sono backlog separato dalla sola redazione: pin/digest immagini e `npm ci --legacy-peer-deps` per build riproducibili; audit/riparazione DB→Vault; associazione univoca tra prenotazione e risposta TPM; serializzazione/versionamento dei toggle read status rapidi. Nessuna di esse deve essere presentata nei documenti come già disponibile.

## V2 — Modifiche documentali obbligatorie

### `README.md`

1. Correggere la promessa iniziale: applicazione self-hosted/containerizzata con dipendenze RSS, Google e Carto; dichiarare porte 80 e 8080.
2. Aggiornare badge Python e licenza solo dopo P0; non lasciare MIT senza `LICENSE`.
3. Espandere l'albero reale: backend `core/extraction/classification/commit`; frontend `components/services/models/shared` e asset; Compose/Dockerfile/Nginx; `.agents` e `radar/.ecc/{agents,hooks,rules,skills}`.
4. Aggiungere Mermaid ridotto: browser → Nginx/Angular → `/api/` → FastAPI; FastAPI ↔ PostgreSQL/Miniflux/Gemini/Vault; browser → Carto. Conservare il dettaglio nel doc 02.
5. Inserire tabella stack «tag/dichiarazione» e «fonte», senza chiamare esatti i tag mobili; collegare i quattro manuali e `RSS.txt` senza copiarne il catalogo.

### `docs/01_getting_started.md`

1. Sostituire il blocco `.env` con tabella completa: chiavi Google e precedenza, modello, RPM/TPM/RPD, Miniflux, DB, `DATABASE_URL`, fallback locale `POSTGRES_HOST/PORT`, Vault. Rimuovere `DEBUG` e gli esempi di chiave realistici.
2. Chiarire default, `LLM_TPM=0`, password con `$`, `DATABASE_URL` sovrascritta da Compose e nomi admin Miniflux corretti.
3. Inserire il provisioning verificabile di `frontend/src/assets/data/countries.geo.json` prima della build, dopo la decisione P0.
4. Correggere build/boot: Python scelto, builder C per `asyncpg`, utente `radar`, `PYTHONPATH=/app`, multi-stage Angular, healthcheck e porte effettive. Non promettere build bit-a-bit fino a pin/`npm ci`.
5. Rendere le verifiche portabili: Nginx `/health`, API tramite `/api/articles?date=YYYY-MM-DD`, API/DB diretti con `docker compose exec`; in PowerShell usare `curl.exe` o l'equivalente nativo.
6. Aggiungere flusso Miniflux (login, Settings → API Keys, riavvio backend, feed), refresh best effort, polling, 48 ore/unread/RPD e link a `RSS.txt`.
7. Rifare troubleshooting: porte, password/DB, migrazioni Miniflux, limiti LLM, Vault, GeoJSON, build e backup/restore di `data/postgres` e `vault`. Il CORS PATCH non è una issue da normalizzare: va corretto a P0.

### `docs/02_architecture_and_backend.md`

1. Sostituire ASCII con Mermaid di topologia e sequenza articolo: unread → dedup → sanitize → limit/LLM → DB → Vault → mark read, con rami duplicato/retry/fallback/errore Vault.
2. Usare i moduli `core`, `extraction`, `classification`, `commit`, non «Layer C Commit». Aggiungere data dictionary delle cinque tabelle, tipi, nullability, default, PK/FK/UNIQUE/CHECK, `TEXT[]`, quattro indici e nota su bootstrap idempotente/ALTER `is_read`.
3. Documentare extraction (48 ore, dedup, tag con contenuto soppresso, strip normale di tag/attributi, entità e whitespace); classification come contratto CSV→liste, schema, fallback e `reasoning` non persistito.
4. Spiegare RPM/TPM su finestra 60 s, stima token, quattro tentativi/backoff e limite dell'attuale aggiornamento TPM concorrente; spiegare TaskGroup, RPD e resilienza loop/ciclo/articolo.
5. Documentare transazione DB, upsert/junction, Vault separato, lock 10 s e limite DB/Vault. L'esempio Vault deve contenere soltanto frontmatter realmente prodotti: title, location, country, category, tags, companies, sentiment, relevance, published, source.
6. Aggiungere API reference completa, status code e nota: filtri array/categoria sono client-side e `/api/countries` non è la fonte UI attuale. Inserire CORS reale, proxy same-origin, assenza auth applicativa e egress esterno.

### `docs/03_frontend_and_ui.md`

1. Correggere stack/SCSS e distinguere versioni dichiarate da compatibilità certificata; non ignorare il disallineamento di major tra core Angular e alcune dipendenze.
2. Inserire component tree e ruoli di `ArticleService`, `ArticleMockService`, `StateService`, modello, direttiva hatch e asset. Spiegare Signals: `rxResource` solo per data, `computed` per filtri/countries, signal UI in `App`.
3. Documentare fallback mock di sessione, PATCH ottimistico/rollback e assenza di protezione dalle risposte fuori ordine per toggle rapidi.
4. Spiegare il workaround Leaflet: script globali `angular.json`, `window.L`, CSS in `styles.scss`, plugin UMD non importato a runtime.
5. Riscrivere integralmente clustering: dieci gruppi, raggio 40, media per paese, offset, dummy marker, zoom 6, root marker e spiderfy custom. Rimuovere anello, raggio 100, zoom 12 e spiderfy automatico.
6. Documentare hatching, GeoJSON locale/batch, bounding box US/RU, limiti, tile Carto/attribuzioni e legenda; aggiungere Mermaid di interazione toolbar/paese/cluster/marker → App → sidebar/focus e dettagli carousel (`article-card-{id}`, pulizia `Feed:`).

### `docs/04_ecc_framework.md`

1. Documentare entrambi gli alberi: `.agents/AGENTS.md` e tre skill Codex, poi `radar/.ecc/` con CLAUDE, settings, agent profiles, rules, skills e hooks.
2. Distinguere istruzioni, path rules, agent profiles, skill e hook; dichiarare che trigger/caricamento dipendono dall'harness.
3. Riassumere skill Angular/JSON LLM/mock spaziale, rules e profile `pipeline-engineer`, `geo-data-architect`, `angular-map-expert`.
4. Correggere hook: pre bloccante a pattern; post non bloccante, placeholder scan e tentativi Ruff/ESLint. Rimuovere Prettier e l'idea di esecuzione automatica universale. Dopo P0 allineare le rules a Python e clustering scelti; sostituire l'esempio D3 con `spatial-data-mocking`.

## V2 — Ordine e verifica

1. Chiudere P0 e applicare solo le correzioni runtime approvate.
2. Redigere README e docs 01, poi docs 02, docs 03 e docs 04.
3. Verificare link relativi, assenza di path assoluti/segreti e terminologia coerente.
4. Eseguire `docker compose config` con ambiente di test, build/healthcheck, test backend pertinenti e smoke test da ambiente pulito: asset, login/API key Miniflux, feed, pipeline, DB, Vault e dashboard.
5. Per codice/configurazione modificati, eseguire gli hook ECC nei loro limiti reali e registrare warning non bloccanti.

---

## Archivio V1 — Decisioni iniziali non vincolanti

<details>
<summary>Apri soltanto per consultare lo storico V1; non contiene istruzioni da eseguire.</summary>

> [!IMPORTANT]
> ### Lingua della documentazione
> La Fase 1 è stata scritta interamente in **italiano**. Confermo che la Fase 2 mantiene lo stesso approccio monolingue italiano, con terminologia tecnica inglese dove appropriato (es. nomi di classe, endpoint). Se desideri un approccio bilingue o sezioni in inglese, segnalalo prima dell'esecuzione.

> [!IMPORTANT]
> ### Profondità e pubblico target
> L'analisi ha rivelato diversi livelli di dettaglio possibili. Il piano propone un tono da **manuale tecnico avanzato** (stile "engineering handbook") rivolto a sviluppatori e DevOps. Se preferisci un tono più accessibile o divulgativo per alcuni documenti, segnalalo.

---

## Archivio V1 — Analisi iniziale, non usare come fonte tecnica

L'analisi incrociata tra documentazione esistente e codice sorgente ha rilevato queste categorie di problemi:

### 1. Disallineamenti Factuali (Docs vs. Codice Reale)

| Problema | Dove | Dettaglio |
|----------|------|-----------|
| **Versione Python nel Dockerfile** | [Dockerfile backend](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/Dockerfile) vs [README](file:///c:/Users/lucag/Documents/Dashboard%20finance/README.md) | Il Dockerfile usa `python:3.11-slim`, il README dichiara Python 3.12. L'AGENTS.md cita 3.12-slim (Docker) / 3.14 (locale). Il Dockerfile è la fonte di verità. |
| **Configurazione Clustering Leaflet** | [radar-map.component.ts L160-164](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/app/components/radar-map/radar-map.component.ts#L160) | Le regole ECC in AGENTS.md impongono `maxClusterRadius: 100`, `disableClusteringAtZoom: 12`, ma il codice usa `maxClusterRadius: 40` e `spiderfyOnMaxZoom: false` con logica di spiderfy custom. |
| **Categoria Fallback nello schema** | [validator.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/classification/validator.py#L73) | Il fallback di `validate_category` restituisce `"Tecnologia"`, ma il `get_fallback_article` usa `"Infrastrutture"` come default. Il doc 02 non menziona questa discrepanza. |
| **TaskGroup concorrente** | [main.py L157](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/main.py#L157) | Il doc 02 descrive la pipeline come sequenziale. In realtà `run_pipeline_cycle` usa `asyncio.TaskGroup()` per elaborazione concorrente. Differenza architetturale significativa non documentata. |
| **Rate Limiting doppio binario** | [client.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/classification/client.py#L32) | Il AGENTS.md cita "almeno 4 secondi di sleep tra chiamate". Il codice reale implementa un sistema a doppio binario RPM+TPM con rolling window e lock asincrono. Molto più sofisticato di quanto documentato. |
| **Correction Loop a 4 tentativi** | [client.py L101-167](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/classification/client.py#L101) | Il doc 02 cita solo un generico "Fallback". Il codice ha un sistema di auto-correzione multi-turno con history injection e backoff esponenziale. Non documentato. |
| **RPD (Requests Per Day)** | [main.py L130-139](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/main.py#L130) | Il controllo soglia giornaliera RPD con query SQL (`SELECT count(*) ... WHERE date(created_at) = CURRENT_DATE`) non è documentato da nessuna parte. |
| **Endpoint PATCH** | [main.py L388-404](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/main.py#L388) | L'endpoint `PATCH /api/articles/{id}/read_status` non è citato nel doc 02 (che lista solo GET). |
| **`is_read` stato letto/non letto** | [database.py L50](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/core/database.py#L50), [state.service.ts L73-98](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/app/services/state.service.ts#L73) | Intero flusso letto/non-letto con update ottimistico e rollback. Non documentato. |
| **Refresh forzato feed all'avvio** | [main.py L179-182](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/main.py#L179) | `refresh_all_feeds()` al primo boot del demone. Non documentato. |
| **CORS configurazione** | [main.py L252-258](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/main.py#L252) | CORS con `allow_methods=["GET"]` — il PATCH non è nell'elenco (potenziale bug). Non documentato. |
| **rxResource e Signal State** | [state.service.ts](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/app/services/state.service.ts) | Il doc 03 cita `rxResource` genericamente. Il codice implementa un pattern completo: `rxResource` per HTTP, `computed` per filtri client-side real-time, e metodo `toggleReadStatus` con update ottimistico. |
| **Filtro multiscelta** | [article.model.ts L43-47](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/app/models/article.model.ts#L43) | Il modello supporta filtri multipli per sentiment E categorie (array). Il doc 03 descrive solo filtri singoli. |
| **Leaflet + ESBuild** | [angular.json L41-44](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/angular.json#L41) | Il workaround critico (scripts[] in angular.json) è documentato solo nel AGENTS.md, non nei docs utente. |

### 2. Contenuti Completamente Mancanti

| Argomento | Impatto |
|-----------|---------|
| **Schema DDL completo del database** | Il doc 02 non mostra mai le query CREATE TABLE reali. L'utente non sa quali vincoli CHECK, DEFAULT o indici esistono. |
| **Gestione `infrastructural_entities` come `TEXT[]`** | Il campo è un array PostgreSQL nativo, non una stringa CSV. Questa scelta non è documentata. |
| **Marker `isDummy` UX Feature** | Il frontend aggiunge marker invisibili ("dummy") al centro delle nazioni per forzare il layout spaziale dei cluster senza mostrare punti reali ridondanti. Innovazione UX non documentata. |
| **Feed RSS consigliati con lista pratica** | Il file [RSS.txt](file:///c:/Users/lucag/Documents/Dashboard%20finance/RSS.txt) contiene 30+ feed suggeriti con CSS selectors per Miniflux. Non referenziato nella docs. |
| **Flusso dettagliato "Vita di un Articolo"** | Manca un diagramma end-to-end che segua un articolo da Miniflux → Parser → Gemini → DB → Vault → Angular. |
| **Sezione API Reference** | Endpoint, parametri, risposte d'esempio. Nessun doc ha una reference API esplicita. |
| **Diagrama Mermaid del flusso dati** | Il doc 02 usa un diagramma ASCII. Un Mermaid renderizzabile sarebbe più chiaro e mantenibile. |
| **Configurazione Nginx in dettaglio** | Il doc 01 cita Nginx come proxy ma non spiega i blocchi `resolver`, `gzip`, `security headers`, cache policy, healthcheck. |
| **Sistema Frontmatter YAML dei file Vault** | Il doc 02 lo cita ma non mostra un esempio reale del formato generato da [factory.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/commit/factory.py). |
| **Albero directory completo e aggiornato** | Il README mostra un albero superficiale. Mancano `core/`, `classification/`, `commit/`, `extraction/`, `services/`, `components/`, `shared/`, `models/`, file Nginx, proxy.conf.json, etc. |

---

## Archivio V1 — Proposte iniziali superate da V2

La Fase 2 opera su **5 file esistenti** (README + 4 docs) senza crearne di nuovi, mantenendo la struttura della Fase 1.

---

### README.md (Hub centrale)

#### [MODIFY] [README.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/README.md)

1. **Correzione badge Python**: Allineare alla versione reale nel Dockerfile (3.11 o aggiornare il Dockerfile — da confermare).
2. **Albero directory espanso**: Sostituire l'albero superficiale con una struttura a 3 livelli che rifletta la realtà del codebase:
   - Backend: `core/`, `extraction/`, `classification/`, `commit/` con file principali
   - Frontend: `components/`, `services/`, `models/`, `shared/directives/`
   - Config: `nginx.conf`, `angular.json`, `proxy.conf.json`, `.env.example`
   - ECC: `.ecc/hooks/`, `.ecc/rules/`, `.agents/skills/`
3. **Sezione "Architettura a Colpo d'Occhio"**: Aggiungere un diagramma Mermaid (flowchart) che mostri il flusso RSS → Miniflux → Backend → Gemini → PostgreSQL / Vault → Angular.
4. **Tabella Stack Tecnologico**: Aggiungere una tabella compatta con versioni esatte di ogni componente (verificate dal codice: Python 3.11, Angular 21.2, PostgreSQL 15, Node 22, Nginx 1.27, Leaflet 1.9, PrimeNG 17, etc.).
5. **Sezione "Feed RSS Suggeriti"**: Breve paragrafo che referenzia il file `RSS.txt` con le fonti testate.
6. **Sezione Licenza**: Aggiungere nota di credito per le librerie open-source chiave (Leaflet, PrimeNG, Miniflux).

---

### docs/01_getting_started.md (Guida all'Avvio)

#### [MODIFY] [01_getting_started.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/docs/01_getting_started.md)

1. **Sezione 2.1 — Disamina `.env`**: Aggiungere i parametri mancanti:
   - `GOOGLE_API_KEY` (alternativa a `GEMINI_API_KEY`, come da [config.py L8](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/core/config.py#L8))
   - `POSTGRES_HOST` / `POSTGRES_PORT` (per sviluppo locale fuori Docker)
   - `DEBUG` con spiegazione dell'effetto reale
   - Tabella riassuntiva delle variabili: nome, obbligatoria/opzionale, default, descrizione
2. **Sezione 3.1 — Flusso di Build**: Correggere la descrizione del backend: il Dockerfile usa un builder `python:3.11-slim` (non 3.12). Aggiungere il dettaglio del `PYTHONPATH=/app` e dell'utente non-root `radar`.
3. **Sezione 3.3 — Verifiche**: Aggiungere una "Verifica D" per testare l'endpoint API direttamente:
   ```bash
   curl http://localhost/api/articles?date=2026-07-13
   ```
4. **Sezione 4 — Configurazione RSS**: Integrare i feed suggeriti dal file `RSS.txt` con una tabella organizzata per fonte e categoria tematica. Aggiungere la nota su User-Agent e "Fetch original content" per Miniflux.
5. **Sezione 4.1 — Dettaglio Refresh**: Documentare che il backend esegue un `refresh_all_feeds()` forzato ad ogni avvio del container.
6. **Nuova Sezione 4.2 — Generazione API Key Miniflux**: Step-by-step per generare la API Key dall'interfaccia Miniflux (Settings → API Keys → Create) e compilare `MINIFLUX_API_KEY` nel `.env`.
7. **Sezione 7 — Troubleshooting**: Aggiungere nuovi scenari:
   - 7.5: Errore `CORS policy` su richieste PATCH (bug noto: CORS `allow_methods=["GET"]` non include PATCH)
   - 7.6: `asyncpg.exceptions.InvalidPasswordError` — password con carattere `$`
   - 7.7: Container `radar-miniflux` in `Exited (1)` — migrazioni fallite per DB non pronto

---

### docs/02_architecture_and_backend.md (Architettura e Backend)

#### [MODIFY] [02_architecture_and_backend.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/docs/02_architecture_and_backend.md)

Questa è la sezione che richiede le modifiche più estese. L'analisi ha rivelato che il codice è **significativamente più sofisticato** di quanto documentato.

1. **Diagramma Mermaid**: Sostituire o affiancare il diagramma ASCII con un diagramma Mermaid a colori che mostri chiaramente i 4 servizi Docker, le connessioni interne, e il flusso dati.

2. **Nuova Sezione: Schema DDL del Database**: Inserire lo schema completo estratto da [database.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/core/database.py) come blocco SQL annotato, includendo:
   - Le 5 tabelle (articles, companies, tags, article_companies, article_tags)
   - I vincoli CHECK (10 categorie, 3 sentiment, relevance 1-5)
   - Gli indici di performance (4 indici)
   - Le colonne `infrastructural_entities TEXT[]` e `feed_title TEXT`
   - La colonna `is_read BOOLEAN` con l'idempotent ALTER TABLE

3. **Layer E (Extraction) — Espansione**: Aggiungere dettagli su:
   - Struttura del modulo (`client.py`, `parser.py`, `state.py`)
   - Snippet di `is_article_duplicate()` — verifica URL pre-LLM
   - Funzione `strip_html_tags()` con lista esplicita dei tag totalmente spurgati (script, style, iframe, svg, noscript, meta, video, audio, embed, object) e relativo contenuto interno.
   - `refresh_all_feeds()` al primo avvio

4. **Layer C (Classification) — Riscrittura sostanziale**:
   - **Rate Limiter doppio binario**: Documentare il sistema RPM + TPM con rolling window a 60 secondi e lock asincrono. Includere il diagramma di flusso del throttling.
   - **Correction Loop multi-turno**: Documentare il meccanismo a 4 tentativi con history injection (modello vede i propri errori) e backoff esponenziale (`attempt * 4 sec`).
   - **Update TPM post-risposta**: Spiegare come `_update_tpm()` sostituisce la stima token con il consumo reale dall'`usage_metadata`.
   - **System Prompt completo**: Includere il system prompt da [prompts.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/classification/prompts.py) con annotazioni per ogni sezione (CoT, categorizzazione, regole geografiche, lingua).

5. **Layer C (Commit) — Espansione**:
   - Documentare `parse_csv_list()` e la logica di conversione da stringa CSV a lista
   - Mostrare il pattern di percorso del Vault: `vault/{Categoria}/{Nazione}/{data}_{slug}_{hash8}.md`
   - Documentare `slugify_title()` e la sua sanitizzazione cross-platform (Windows NTFS + Linux ext4)
   - Documentare `write_file_with_lock()` dal modulo [lock.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/commit/lock.py) con meccanismo di file locking
   - Mostrare un esempio reale di file Markdown generato (frontmatter YAML + corpo)

6. **Nuova Sezione: API Reference**: Tabella con tutti gli endpoint REST:

   | Metodo | Endpoint | Parametri | Risposta |
   |--------|----------|-----------|----------|
   | GET | `/health` | — | `{"status": "ok"}` |
   | GET | `/api/articles` | `date` (req), `sentiment`, `relevance_level` | Array di articoli con JOIN |
   | GET | `/api/countries` | `date` (req), `sentiment`, `relevance_level` | Array di sommari nazionali |
   | PATCH | `/api/articles/{id}/read_status` | Body: `{"is_read": bool}` | `{"status": "success"}` |

7. **Nuova Sezione: Gestione RPD**: Documentare il meccanismo di "ibernazione" quando il conteggio giornaliero raggiunge `LLM_RPD`.

8. **Nuova Sezione: Elaborazione Concorrente (TaskGroup)**: Spiegare l'uso di `asyncio.TaskGroup()` per la parallelizzazione degli articoli nel ciclo e le implicazioni per il rate limiting.

9. **Sezione Resilienza — Espansione**: Ristrutturare con i 3 livelli espliciti:
   - Level 1: `run_pipeline_loop` (immortale, `while True`, catch-all)
   - Level 2: `run_pipeline_cycle` (ciclo singolo, RPD check, fetch + process)
   - Level 3: `process_single_entry` (singolo articolo, dedup → parse → LLM → commit → mark-read)

---

### docs/03_frontend_and_ui.md (Frontend e UI)

#### [MODIFY] [03_frontend_and_ui.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/docs/03_frontend_and_ui.md)

1. **Sezione Stack UI — Aggiornamento**: Correggere "SCSS (CSS nativo)" → "SCSS" e aggiungere dettagli reali: Angular `21.2.x`, PrimeNG `17.18.x`, Leaflet `1.9.4`, `leaflet.markercluster 1.5.3`, CDK `17.3.x`.

2. **Nuova Sezione: Architettura Angular (Component Tree)**: Documentare l'albero dei componenti:
   ```
   App (app.ts)
   ├── RadarToolbarComponent (filtri, date picker, country select)
   ├── RadarMapComponent (Leaflet, GeoJSON, clustering, hatching)
   │   └── leaflet-hatch.directive.ts (SVG pattern injection)
   └── RadarSidebarComponent (carosello PrimeNG, article cards)
   ```

3. **Nuova Sezione: State Management (Signal Architecture)**: Documentare il pattern di stato Angular basato su Signals:
   - `StateService` come single source of truth
   - `rxResource` per data fetching reattivo
   - `computed` per filtri client-side in tempo reale
   - `signal` per stato UI locale (sidebar, article selezionato)
   - Update ottimistico con rollback per `toggleReadStatus()`

4. **Nuova Sezione: Workaround ESBuild + Leaflet**: Documentare il pattern critico di caricamento Leaflet/MarkerCluster via `angular.json → scripts[]` e l'accesso via `window.L`. Spiegare perché `import * as L from 'leaflet'` non funziona con ESBuild.

5. **Sezione Clustering — Espansione**: Aggiungere dettagli su:
   - Icona composita ad anello (singola categoria = pallino 40×40, multi-categoria = anello 60×60)
   - Spiderfy a grafo (zoom ≥ 12, linee radiali dal centro)
   - `maxClusterRadius: 100`, `disableClusteringAtZoom: 12`, `spiderfyOnMaxZoom: true`

6. **Sezione Toolbar — Espansione**: Documentare i filtri multiscelta (arrays di sentiment e categorie), il date picker, il dropdown country con conteggio articoli.

7. **Nuova Sezione: Flusso Interazione Utente**: Diagramma Mermaid che mostri le interazioni utente → componente → stato → mappa:
   - Click nazione → `onCountryClick()` → sidebar + fitBounds
   - Click cluster → `onClusterClick()` → carosello articoli
   - Click marker → `onMarkerClick()` → sidebar singolo articolo
   - Cambio filtro → `onFiltersChange()` → `StateService.filters.set()` → re-render

8. **Nuova Sezione: Stato Letto/Non-Letto**: Documentare il flusso completo letto/non-letto con update ottimistico e rollback.

9. **Sezione Legenda Colori**: Aggiungere la descrizione della legenda glassmorphic orizzontale in basso alla mappa con cerchi luminosi e emoji per categoria.

---

### docs/04_ecc_framework.md (Framework ECC)

#### [MODIFY] [04_ecc_framework.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/docs/04_ecc_framework.md)

1. **Struttura Directory — Espansione**: Aggiungere l'albero completo con percorsi reali:
   ```
   radar/.ecc/
   ├── CLAUDE.md              # Configurazione master ECC
   ├── settings.json          # Impostazioni agente
   ├── hooks/
   │   ├── pre-tool-use.py    # Scan leak segreti e pattern vietati
   │   └── post-tool-use.py   # Linting (ruff/eslint) e check TODO
   ├── rules/
   │   ├── backend.md         # Guardrail Python/FastAPI
   │   ├── frontend.md        # Guardrail Angular/Leaflet
   │   └── docker.md          # Guardrail containerizzazione
   └── skills/                # (opzionali, scope .ecc)
   
   .agents/
   ├── AGENTS.md              # Magna Carta globale
   └── skills/
       ├── angular-developer/
       ├── llm-json-extraction/
       └── spatial-data-mocking/
   ```

2. **Nuova Sezione: Dettaglio delle 3 Skills**: Documentare ogni skill con:
   - `angular-developer`: trigger, scopo (codice Angular, Signal, routing, SSR, etc.)
   - `llm-json-extraction`: sistema prompt Gemini, schema Pydantic, logica di fallback
   - `spatial-data-mocking`: testing offline frontend con dati mock, isolamento dal backend

3. **Nuova Sezione: Dettaglio Rules Scoped**: Spiegare la separazione per scope-path:
   - `backend.md`: vincoli Python, asyncpg puro, type hints, logging centralizzato
   - `frontend.md`: vincoli Angular 21, Leaflet/ESBuild, clustering, glassmorphism
   - `docker.md`: nomi servizi, volumi, rete bridge, multi-stage build, Nginx resolver

4. **Nuova Sezione: Anatomia degli Hook**: Documentare cosa controlla ogni hook:
   - `pre-tool-use.py`: pattern regex per leak API keys, comandi distruttivi (`rm -rf`, `DROP TABLE`)
   - `post-tool-use.py`: check TODO/FIXME/HACK, invocazione ruff (Python), eslint (TS)

5. **Sezione "Espandere ECC" — Raffinamento**: Aggiornare l'esempio di skill con un caso reale dal progetto (es. `spatial-data-mocking`) invece dell'ipotetico D3.js.

---

## Archivio V1 — Questioni aperte superate da V2

Durante l'analisi sono emerse alcune discrepanze chiave tra codice, documentazione e regole ECC. Qui di seguito presento un'analisi approfondita per ciascun punto, esplorando le opzioni, le *best practice* del settore e una raccomandazione su come procedere in modo ottimale.

> [!IMPORTANT]
> ### 1. Disallineamento Versione Python (Dockerfile vs README vs Regole)
> **Contesto**: Il [Dockerfile backend](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/Dockerfile) utilizza l'immagine `python:3.11-slim`. Tuttavia, la documentazione attuale e le regole globali in [AGENTS.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/.agents/AGENTS.md) specificano l'uso di **Python 3.12-slim** (Docker) / 3.14 (locale).
>
> **Opzione A**: *Adeguare la Documentazione al Codice (Python 3.11)*
> - **Cosa comporta**: Modifichiamo il README per indicare Python 3.11. Il codice non viene toccato.
> - **Pro**: Nessun rischio di regressioni nel codice.
> - **Contro**: Viene ignorato il vincolo architetturale esplicito in `AGENTS.md`. Si rinuncia ai miglioramenti di performance (tier 2 optimizer) introdotti in Python 3.12.
>
> **Opzione B**: *Aggiornare il Dockerfile a Python 3.12-slim*
> - **Cosa comporta**: Modifichiamo il `Dockerfile` per usare `python:3.12-slim` e allineiamo la documentazione a questo nuovo stato.
> - **Pro**: Rispettiamo i guardrail ECC. Modernizziamo lo stack. Il passaggio da 3.11 a 3.12 in FastAPI/asyncpg è sicuro, retrocompatibile e migliora i tempi di esecuzione asincrona.
> - **Contro**: Richiederà la ricostruzione del container backend (ma essendo un'app Docker, è un'operazione banale).
>
> 💡 **Best Practice & Raccomandazione**:
> I guardrail ECC (`AGENTS.md`) rappresentano l'"intento progettuale" del sistema e devono prevalere quando possibile. Python 3.12 offre evidenti vantaggi nel runtime `asyncio` su cui si basa pesantemente il progetto.
> **Azione Consigliata**: Procedere con l'**Opzione B**. Modificherò il `Dockerfile` e aggiornerò tutta la documentazione per riflettere Python 3.12.

> [!WARNING]
> ### 2. Bug CORS Silenzioso sull'Endpoint PATCH
> **Contesto**: In [main.py L256](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/backend/app/main.py#L256), il middleware CORS dichiara esplicitamente `allow_methods=["GET"]`. Il sistema però include l'endpoint `PATCH /api/articles/{id}/read_status`.
> In produzione, tramite Nginx (proxy inverso sulla stessa rete docker), questo non crea problemi perché browser e frontend dialogano sullo stesso dominio (porta 80). In sviluppo locale (es. eseguendo Angular in locale su `localhost:4200` che chiama backend su `localhost:8000`), le preflight request OPTIONS per la PATCH falliranno con errore CORS.
>
> **Opzione A**: *Documentarlo come "Known Issue"*
> - **Cosa comporta**: Inseriamo una nota nel troubleshooting del README per chi sviluppa in locale.
> - **Pro**: Non si tocca il codice.
> - **Contro**: Lascia nel codice una configurazione tecnicamente errata (dichiara un endpoint PATCH ma non lo autorizza cross-origin). Causa frustrazione inutile ai futuri sviluppatori.
>
> **Opzione B**: *Correggere il Middleware CORS*
> - **Cosa comporta**: Aggiungere `"PATCH"` alla lista `allow_methods` nel file `main.py`.
> - **Pro**: Risolve il problema alla radice, allineando la configurazione di sicurezza all'effettiva API surface.
> - **Contro**: Modifica minima al codice backend.
>
> 💡 **Best Practice & Raccomandazione**:
> Nel design delle API REST, il middleware CORS deve sempre riflettere in modo accurato tutti i verbi HTTP effettivamente esposti e utilizzati dalle interfacce pubbliche. Lasciare "trappole" per l'ambiente di sviluppo locale è una pessima prassi.
> **Azione Consigliata**: Procedere con l'**Opzione B**. Aggiungerò `"PATCH"` al codice e documenterò le configurazioni in modo accurato.

> [!CAUTION]
> ### 3. Conflitto Regole di Clustering (AGENTS.md vs Frontend Reale)
> **Contesto**: Le regole ECC nel file `AGENTS.md` impongono per Leaflet le impostazioni `maxClusterRadius: 100`, `disableClusteringAtZoom: 12`, e `spiderfyOnMaxZoom: true`.
> Esaminando [radar-map.component.ts L160-164](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/app/components/radar-map/radar-map.component.ts#L160), emerge che il codice utilizza un raggio molto più stretto (`maxClusterRadius: 40`), disabilita lo spiderfy automatico (`spiderfyOnMaxZoom: false`), e implementa una **raffinatissima logica custom in TypeScript** (metodo `spiderfyAndCreateRoot`) per innescare lo spiderfy ad anello a un livello di zoom dinamico (flyTo zoom 6) e mantenere un marker radice persistente (root marker). 
> Inoltre, il frontend usa genialmente dei marker "invisibili" (`isDummy`) per forzare la renderizzazione dei cluster senza inquinare la UI.
>
> **Opzione A**: *Retrocedere il Codice alle Regole Base*
> - **Cosa comporta**: Modificare il componente Angular per conformarlo rigidamente a `AGENTS.md`.
> - **Pro**: Allineamento cieco alle direttive attuali.
> - **Contro**: Si distruggerebbe un'implementazione UX molto sofisticata (animazioni, root marker, cluster compatti e leggibili), peggiorando sensibilmente l'usabilità del cruscotto informativo.
>
> **Opzione B**: *Elevare l'Implementazione Attuale a Nuovo Standard*
> - **Cosa comporta**: Aggiornare le regole di progetto in `AGENTS.md` ed includere la logica attuale nel README/docs, validandola come la soluzione architetturale corretta.
> - **Pro**: Si valorizza il codice elegante già scritto, si documentano gli sforzi di UI/UX avanzata e si mantiene il sistema all'avanguardia tecnica.
> - **Contro**: Richiede la modifica del file di governance `.agents/AGENTS.md`.
>
> 💡 **Best Practice & Raccomandazione**:
> Le regole di governance (`AGENTS.md`) devono fungere da guida, ma quando un'implementazione tecnica evolve per superare i limiti previsti (es. migliorando la User Experience visiva su mappe dense), i documenti di architettura e le regole **devono essere aggiornati per riflettere il nuovo design consolidato**, evitando che futuri interventi degradino l'interfaccia.
> **Azione Consigliata**: Procedere con l'**Opzione B**. Modificherò `AGENTS.md` per istituzionalizzare questa logica di UX superiore, mantenendo intatto il magnifico codice frontend, e documenterò approfonditamente il sistema dei dummy-marker nel `03_frontend_and_ui.md`.

---

## Archivio V1 — Verifica sostituita dalla sezione V2

### Verifica Fattuale
- Cross-reference di ogni affermazione tecnica nei docs con il file sorgente corrispondente (percorso, numero di riga)
- Verifica che ogni snippet di codice inserito nei docs sia un estratto letterale dal codebase, non una riscrittura

### Verifica Strutturale
- Conferma che tutti i link interni tra i 4 docs e il README funzionino
- Conferma che l'indice del README rifletta accuratamente le sezioni di ciascun doc

### Verifica di Completezza
- Checklist dei 13 disallineamenti identificati nell'analisi → tutti risolti
- Checklist dei 9 contenuti mancanti → tutti integrati

</details>
