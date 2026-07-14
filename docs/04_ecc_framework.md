# 🧠 Il Framework ECC (Everything Claude Code)

Questo progetto implementa un'architettura avanzata di "Agent Harnessing": il framework **ECC (Everything Claude Code)**.

## Che cos'è ECC?
ECC è un "Harness-native operator system for agentic work". Fornisce un'infrastruttura per istruire l'AI, vincolandola in modo deterministico e sicuro alle regole di produzione del progetto. L'effettivo caricamento e i trigger logici di questi artefatti dipendono dall'harness del client in uso (es. Antigravity, OpenCode, Cursor, o CLI native).

Il sistema è composto da due namespace di directory:

### 1. Spazio di Governance Globale (`.agents/`)
Questa cartella (situata spesso nella root del progetto o globalmente nell'host) contiene:
- `AGENTS.md`: La "Magna Carta" globale. Definisce l'identità dell'agente, i divieti assoluti (no placeholders, obbligo `asyncpg` puro) e i vincoli incrociati.
- `skills/`: Competenze globalmente disponibili, attivabili tramite semantic matching sui frontmatter YAML dei file `SKILL.md`.

### 2. Spazio Operativo di Workspace (`radar/.ecc/`)
Questo namespace isolato definisce le regole di contesto e il profilo di esecuzione locale:
- `CLAUDE.md`: Entry-point legacy o configurazione master dell'harness.
- `settings.json`: Impostazioni base dell'agente.
- `rules/`: Istruzioni Scope-Path. File come `backend.md` o `frontend.md` che agiscono solo su specifiche path (es. `radar/backend/**`).
- `agent_profiles/`: Profili comportamentali assunti dall'AI (`pipeline-engineer`, `geo-data-architect`, `angular-map-expert`).
- `hooks/`: Script di validazione pre e post esecuzione.
- `skills/`: (Opzionale) Competenze circoscritte al solo microservizio.

---

## Mappatura delle Competenze (Skills)

L'agente apprende dinamicamente a risolvere task complessi leggendo i file `SKILL.md`. Le 3 skill documentate nel progetto sono:

1. **`angular-developer`**: Fornisce pattern architetturali reattivi per Angular 21 (uso esclusivo di Signals, Standalone Components, e workaround ESBuild per librerie UMD come Leaflet).
2. **`llm-json-extraction`**: Playbook per l'integrazione con Google Gemini API. Definisce il System Prompt immutabile, lo schema Pydantic per i JSON Strutturati, e il contratto CSV→List per proteggere il token-buffer.
3. **`spatial-data-mocking`**: Guida per il testing offline del frontend in isolamento dal backend. Insegna all'agente a innescare e governare i dati mockati geografici senza dipendere da FastAPI/Miniflux.

---

## Architettura degli Hooks di Validazione

Gli script in `radar/.ecc/hooks/` funzionano similmente ai Git Hooks, ma scattano attorno alle modifiche prodotte dall'AI. **L'agente deve eseguirli manualmente** a chiusura delle operazioni sui file sorgenti codificati, dato che l'esecuzione automatica universale varia per harness.

- **`pre-tool-use.py` (Bloccante, basato a pattern)**:
  Esegue uno scan regex in memoria dell'input del tool. Blocca l'esecuzione se rileva leak di API Keys nel prompt, o se intercetta pattern distruttivi vietati (es. `rm -rf /` o `DROP TABLE`).
  
- **`post-tool-use.py` (Non Bloccante / Tentativo)**:
  Eseguito sui file sorgente appena modificati. Tenta una scansione per Placeholder dimenticati (`TODO`, `FIXME`, `HACK`, `pass`). Lancia il linting (Ruff per Python, ESLint per TypeScript/JS) per validare la sintassi prima del commit. *Non* esegue formattazioni Prettier.

---

## Come Espandere l'Architettura ECC

Il vantaggio di ECC è che la conoscenza cresce assieme al progetto. Puoi alterare il comportamento dell'Agente creando una nuova Skill.

### Esempio Reale: Creare la skill `spatial-data-mocking`
1. Crea una cartella `.agents/skills/spatial-data-mocking/`.
2. All'interno crea un file `SKILL.md`.
3. In cima al file inserisci un Frontmatter YAML (necessario all'harness per il trigger):
   ```yaml
   ---
   name: spatial-data-mocking
   description: Playbook per il testing offline del frontend Angular 21 in totale isolamento dal backend Python. Definisce dati mockati spaziali.
   ---
   ```
4. Sotto il YAML, scrivi in formato Markdown le istruzioni esatte, gli step da seguire nel servizio Angular (es. intercettazione token, iniettore stub).
5. Dal momento in cui salvi il file, l'agente "si ricorderà" di consultare questa guida tecnica ogni volta che gli chiederai di testare la UI in locale.
