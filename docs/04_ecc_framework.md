# 🧠 Il Framework ECC (Everything Claude Code)

Questo progetto implementa una delle architetture di "Agent Harnessing" più avanzate attualmente disponibili per il lavoro delegato all'IA: il framework **ECC (Everything Claude Code)**.

## Che cos'è ECC?
ECC si definisce come un "Harness-native operator system for agentic work". In altre parole, non è un semplice set di file di configurazione, ma una vera e propria infrastruttura (compatibile con IDE e CLI come Cursor, Antigravity, OpenCode, Zed) pensata per istruire l'AI e forzarla a comportarsi in modo deterministico, sicuro e conforme alle regole di un progetto di produzione.

Tramite ECC, l'agente AI che scrive il codice viene dotato di:
- **Skills (Competenze)**: Playbook che gli spiegano passo-passo *come* realizzare task complessi senza inventare la ruota.
- **Rules (Regole)**: Un recinto normativo inviolabile (es. vincoli di framework, divieti assoluti, estetica di base).
- **Hooks (Controlli)**: Script eseguiti in background prima o dopo che l'agente modifichi i file.

---

## Struttura delle Directory ECC

Se esplori la root del progetto, noterai alcune cartelle e file vitali per ECC.

### 1. `.agents/skills/`
Qui risiedono le competenze (Skills) specifiche apprese o definite per questo progetto.
Ad esempio, la cartella `.agents/skills/llm-json-extraction/` contiene il file `SKILL.md`. Quando all'agente AI viene chiesto di "modificare la pipeline Gemini", il sistema analizza questo file e inietta le direttive nel cervello dell'agente prima che scriva il codice.
*Una skill dice all'agente "Usa sempre il parser e purga i tag multimediali per risparmiare token"*.

### 2. `.ecc/rules/` e `AGENTS.md`
Questi sono i Guardrail (le recinzioni di sicurezza).
- `AGENTS.md` (nella radice del progetto o in configurazione globale) agisce come Magna Carta. Contiene i **Vincoli di Produzione Cruciali** (es. divieto di uso di SQLAlchemy, obbligo asincrono puro).
- Le regole possono essere ulteriormente ripartite (es. `frontend.md` o `backend.md`) per circoscrivere i contesti (Scope-Path).

### 3. `.ecc/hooks/`
Questi sono script di esecuzione reali, solitamente scritti in Python o JavaScript/Node, come `pre-tool-use.py` o `post-tool-use.py`. 
Funzionano similmente ai Git Hooks, ma scattano ogni volta che un Agente AI usa uno strumento (es. cerca sul web o scrive un file).
Assicurano che:
- Non vi siano *leak* di chiavi segrete nelle shell create dall'agente.
- L'output dell'agente non contenga commenti temporanei ("TODO", "FIXME").
- Il codice compilato passi i controlli di Linting (es. ESlint o Ruff) *prima* di essere consolidato.

---

## Come Espandere o Modificare l'Architettura ECC

Il vantaggio di ECC è che la conoscenza cresce assieme al progetto. Come sviluppatore umano o supervisore, puoi modificare il comportamento del tuo Agente AI.

### Aggiungere una nuova Skill (Competenza)
Vuoi che l'agente impari a generare automaticamente dei grafici usando D3.js seguendo il tuo stile aziendale?
1. Crea una cartella `.agents/skills/d3-chart-generator/`.
2. All'interno crea un file `SKILL.md`.
3. In cima al file inserisci un Frontmatter YAML con i trigger semantici:
   ```yaml
   ---
   name: d3-chart-generator
   description: Genera grafici D3.js per la dashboard usando scale logaritmiche e stile Palantir. Usa questa skill quando ti viene richiesto di plottare serie temporali.
   ---
   ```
4. Sotto il YAML, scrivi in formato Markdown le istruzioni esatte, gli snippet di codice di base da copiare e i vincoli.
5. Dal turno di chat successivo, l'agente leggerà automaticamente questo manuale ogni volta che capirà di dover creare un grafico!

### Modificare le Regole Globali
Se ti accorgi che l'agente commette ripetutamente un errore (es. usa `ng serve` invece del webserver di produzione), apri il file `AGENTS.md` nella radice.
Aggiungi un nuovo blocco di regola, possibilmente in un alert di avviso:
```markdown
> [!CRITICAL]
> ### ⛔ Divieto di uso di ng serve
> È severamente vietato suggerire o lanciare `ng serve` in produzione. Il frontend deve sempre essere servito compilato staticamente dietro Nginx.
```
Questo diventerà *legge assoluta* per le invocazioni future.

### Esecuzione degli Hook
Prima di confermare modifiche drastiche, assicurati che la toolchain di validazione sia pulita.
Se modifichi le regole di sicurezza, puoi lanciare lo script manualmente:
```bash
python .ecc/hooks/post-tool-use.py
```
Questo garantirà che le protezioni base contro placeholder e codice rotto siano attive e funzionanti.
