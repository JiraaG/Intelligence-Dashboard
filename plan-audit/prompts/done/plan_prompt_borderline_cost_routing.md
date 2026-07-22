# Plan prompt — Analisi routing BORDERLINE (SIMPLE vs COMPLEX) per costi

> **Stato: DONE** — analisi chiusa 2026-07-22; PO ha confermato TO-BE effort-split.  
> **Esito:** BL resta su DeepSeek (non Gemini); target `LLM_BORDERLINE_REASONING_EFFORT=none` + escalate high.  
> **Impl SoT:** [`../../active/plan_impl_borderline_effort_split.md`](../../active/plan_impl_borderline_effort_split.md)  
> **Prompt Agent:** [`../active/agent_prompt_borderline_effort_split.md`](../active/agent_prompt_borderline_effort_split.md)  
> **Branch:** `feature/upgrades`

---

## Come usare

1. Nuova chat Cursor su `feature/upgrades`.
2. Preferisci **Plan mode**.
3. Incolla il blocco **PROMPT** sotto.
4. Output atteso: analisi quantitativa + raccomandazione unica + piano (niente codice finché non confermato).

---

## PROMPT (incolla in Plan mode)

```text
# Task — PIANO / ANALISI ONLY: BORDERLINE → SIMPLE vs COMPLEX (costi)

## Ruolo
Architect + FinOps pipeline Radar Informativo Globale.
Questa chat: **ANALISI RIGOROSA + raccomandazione unica + piano eseguibile**.
**Nessun codice** finché il PO non conferma il piano.
Se l’evidenza live manca, indica query SQL / log da raccogliere e procedi con stime esplicite.

## Obiettivo prodotto
Valutare se gli articoli classificati **BORDERLINE** debbano continuare sulla catena **COMPLEX** (oggi DeepSeek thinking/high, costo) oppure passare (in tutto o in parte) a **SIMPLE** (Gemini Flash Lite free / futuro LLM locale), principalmente per **ridurre costi**, senza peggiorare in modo inaccettabile qualità schema (geo/entity/XX/ValidationError).

Domanda centrale:
> Quanti BORDERLINE elaboriamo oggi, quanto costano su COMPLEX, e cosa cambierebbe (costo + qualità + quota free/local) se li spostassimo su SIMPLE?

## Contratto AS-IS (non reinterpretare senza evidenza)

### Complexity v2.2 (`classification/complexity.py`)
- Quorum famiglie {G, E, X} (+ L solo lunghezza):
  - 0 di {G,E,X} (anche solo L) → **SIMPLE**
  - esattamente 1 di {G,E,X} → **BORDERLINE**
  - ≥2 di {G,E,X} → **COMPLEX**
- Complessità = **rischio estrazione schema**, non “articolo lungo”.

### Routing client (`classification/client.py`) — v2.2
- `LLM_ROUTING_MODE=complexity`:
  - SIMPLE → `LLM_SIMPLE_*`
  - **BORDERLINE + COMPLEX** → `LLM_COMPLEX_*` (tipico DeepSeek `effort=high`)
- Escalate: BORDERLINE già su COMPLEX; dopo 1 correction fallita resta/escalate regole SoT.
- Shadow/off → forza catena SIMPLE (utile come strumento di misura).

### Quote (post per-model GATE)
- SIMPLE: contatori **per model** (3.5 e 3.1 pool separati); `0` = unmanaged.
- COMPLEX DeepSeek: tipicamente RPM/TPM/RPD=0 + eventuale BUDGET.
- Soft-trim: residuo catena SIMPLE; residual cross-lane se COMPLEX distinto.

### Ops live tipica
- Profilo A: SIMPLE Gemini Flash Lite free; COMPLEX DeepSeek paid.
- Metrics 013: denorm `classification_lane`, `classified_by_model`, ledger `purpose`/`lane`/`model`/`estimated_cost_usd` / token split.

## Contesto obbligatorio da leggere PRIMA

### SoT / piani
- `plan-audit/complete/sot_llm_multi_model_fallback.md` — § lane SIMPLE/BORDERLINE/COMPLEX v2.2 (BORDERLINE→COMPLEX intentional)
- `plan-audit/complete/plan_impl_per_model_quota.md` — quote per-model
- `plan-audit/complete/plan_impl_fase_metrics_013.md` — campi denorm/ledger per misurare
- `plan-audit/STATUS.md`
- `radar_overview_and_upgrades.md` se cita complexity routing

### Codice
- `radar/backend/app/classification/complexity.py` — quorum → lane
- `radar/backend/app/classification/client.py` — `_chain_for`, escalate BORDERLINE
- `radar/backend/app/core/llm_lanes.py` / `.env.example` — Profili A–F
- `radar/backend/app/classification/quota.py` — costi stimati ledger
- Worker denorm: `classification_lane` su `articles` (Metrics 013)

### Skills
- `.agents/skills/radar-quota-ledger/SKILL.md`
- `.agents/skills/llm-json-extraction/SKILL.md` (schema strict immutabile in questa analisi)
- `.agents/skills/radar-requeue-ops/SKILL.md` (solo se proponi shadow/requeue di misura)

## Domande di analisi (rispondi TUTTE)

### A — Volume BORDERLINE
A1. Come si osserva oggi un pezzo BORDERLINE nel DB/log? (`classification_lane` =? `complex` perché routato su COMPLEX; serve proxy: log `classify lane=BORDERLINE`, o ricostruire da famiglie, o aggiungere metrica — **decidere metodo AS-IS**).
A2. Volume ultime 24h / 7g: count BORDERLINE vs SIMPLE vs COMPLEX (heuristic), e share %.
A3. Di quelli BORDERLINE, quanti finiscono OK su DeepSeek vs escalate vs fallback article vs ValidationError.

### B — Costi AS-IS
B1. Costo stimato BORDERLINE su COMPLEX: da `llm_request_ledger` (`purpose=classify:complex`, model deepseek, `estimated_cost_usd` / token × USD_PER_1M) nella finestra.
B2. Costo marginale per articolo BORDERLINE (p50/p90 token + $).
B3. Quota free SIMPLE: impatto se N BORDERLINE/giorno migrassero su Gemini 3.5 (RPD 500 per-model) — rischio saturazione free tier vs DeepSeek bill.

### C — Alternative TO-BE (confronta, poi **una** raccomandazione)
C1. **Status quo:** BORDERLINE → COMPLEX (qualità-first).
C2. **BORDERLINE → SIMPLE** (Gemini free / locale): tutto il volume borderline su cheap.
C3. **Ibrido:** BORDERLINE → SIMPLE con escalate a COMPLEX dopo 1 ValidationError (o solo famiglie G/E/X specifiche).
C4. **Shadow mode:** 3–7 giorni `LLM_ROUTING_SHADOW` / dual-run campionario per KPI qualità prima del cutover.
Per ciascuna: costo $, rischio XX/ValidationError/rework, impatto quota Gemini/Ollama, complessità codice.

### D — Qualità / rischio
D1. Perché SoT v2.2 mise BORDERLINE su COMPLEX (rischio schema G/E/X)? Cosa si perde spostando a SIMPLE effort none / Flash Lite?
D2. KPI accettabili per un eventuale move: ValidationError/100, XX rate, escalate rate, human spot-check N articoli.
D3. Interazione con Profilo F (Ollama think su SIMPLE): BORDERLINE su locale cambia VRAM/latency?

### E — Piano (se si decide di cambiare)
E1. Cambio minimo codice (`_chain_for` only? env knob `LLM_BORDERLINE_LANE=simple|complex`?).
E2. Feature flag / shadow / rollback.
E3. Misura post: query metrics + ledger; soglia go/no-go.
E4. Fuori scope esplicito: UI, cambio schema Pydantic, Wave 2 mappa.

## Vincoli
- Schema `GeopoliticalArticleSchema` **immutabile** in questa fase.
- Sidebar freeze.
- Non implementare in questa chat.
- Preferire knob env a hardcode.
- Raccomandazione **unica** vincolante (no “option A or B” lasciate aperte).
- Se i BORDERLINE non sono denormalizzati su `articles.classification_lane` (oggi può risultare `complex` perché è la lane di esecuzione), **non** confondere lane heuristic vs lane di quota: proponi come misurare (log parse, colonna nuova `complexity_lane`, o recompute offline).

## Deliverable di questa chat Plan
1. Tabella volume/costo BORDERLINE (24h e 7g se dati) con metodo di misura.
2. Confronto C1–C4 + **raccomandazione unica** (keep / move-all / hybrid+shadow).
3. Stima $ risparmiati / mese e rischio qualità.
4. Piano impl corto (wave) SOLO se la raccomandazione non è status quo.
5. Query SQL / comandi docker da riusare per GATE futuro.

Inizia leggendo SoT §BORDERLINE e `complexity.py` / `_chain_for`, poi misura live (SQL/log) prima di concludere.
```

---

## Nota PO

- Oggi BORDERLINE **costa come COMPLEX** (by design v2.2). L’analisi deve separare “fascia heuristic” vs “lane di esecuzione/ledger”.
- Dopo l’analisi, se vuoi implementare, chiedi un Agent prompt dedicato (non riusare questo così com’è).
