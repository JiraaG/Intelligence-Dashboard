# Prompt — Multi-model LLM fallback + cooldown 24h (ricerca free-tier)

> **Stato 2026-07-16:** Fase A+B+C **implementate** (lane env v2.2). Questo file resta come **storico orchestratore**.  
> **SoT operativo:** [`../../active/LLM_Multi_Model_Fallback_Phase_AB.md`](../../active/LLM_Multi_Model_Fallback_Phase_AB.md).  
> **Remediation:** [`../../remediation/audit_remediation_llm_multi_model_fallback.md`](../../remediation/audit_remediation_llm_multi_model_fallback.md).  
> Non rieseguire Fase C da zero: estendere solo gap residui (es. soft-cap `DEEPSEEK_BUDGET_USD_DAY`).

> **Uso (storico):** copia il blocco `text` sotto in un **nuovo** chat Agent (orchestratore).  
> **Scope:** ricerca modelli free-tier adatti al Radar + design/implementazione fallback multi-modello con **cooldown 24h** prima del riutilizzo.  
> **Non** commit/push salvo richiesta. **Non** toccare `radar-sidebar/**`.  
> **Skills obbligatorie:** `llm-json-extraction`, `radar-quota-ledger`.  
> **Branch tipico:** `refactor/testing`.

```text
/goal Progetta e implementa (dopo ricerca live) un fallback multi-modello Gemini
per la classificazione articoli del Radar, con cooldown 24 ore sul modello
esaurito/guasto prima di poterlo riusare.
Workspace: `c:\Users\lucag\Documents\Dashboard finance`.
Tu sei l’ORCHESTRATORE: prima RICERCA+report, poi piano approvabile, poi
implementazione a fasi. NON commitare / NON pushare finché non chiesto.
NON toccare radar/frontend/src/app/components/radar-sidebar/**.
NON abbassare qualità sotto Gemma-4-31B-class se esistono alternative free
compatibili. NON inventare quote: verifica fonti ufficiali + AI Studio.

========================================================================
## 0. Contesto Radar (AS-IS — leggi prima)
========================================================================

### Esigenza operativa (utente)
- Throughput: **~10–15 RPM**
- Contesto: **≥ 100k token** (preferibile 1M se free)
- Volume giorno: **1000–2000 RPD**
- Qualità: **≥ Gemma 4 31B**, preferibilmente superiore
- Budget: **free tier** (Google Gemini API / AI Studio) — paid solo se ricerca
  dimostra che free non regge i vincoli
- Comportamento: **più modelli in cascata**; se un modello “scade”
  (quota giorno, 429 persistenti, 5xx modello, NOT_FOUND), metterlo in
  **cooldown 24h** e passare al successivo; dopo 24h può tornare eleggibile

### AS-IS codice (post-Fase C / v2.2)
| Pezzo | Path | Nota |
|-------|------|------|
| Model env | `radar/backend/app/core/config.py` | `GEMINI_*` + `DEEPSEEK_*` + `LLM_ROUTING_*` + **`LLM_SIMPLE_*` / `LLM_COMPLEX_*`** |
| Client | `radar/backend/app/classification/client.py` | Lane SIMPLE/BORDERLINE/COMPLEX; cascade; escalate; dual provider |
| Complexity | `classification/complexity.py` | Quorum famiglie G/E/L/X/N |
| DeepSeek | `classification/deepseek.py` | httpx; `classify_json(model=)` da lane |
| Cooldown | `classification/cooldown.py` + `009` | 24h durable |
| Quote | `classification/quota.py` | `QuotaLedger` RPM/TPM/RPD; `reserve(..., model=)` |
| Env example | `radar/.env.example` | Lane + DeepSeek + routing documentati |
| Worker soft-trim | `radar/backend/app/worker.py` | taglia lotto se RPD ledger vicino al cap |

### Skills / rules
- `.agents/skills/llm-json-extraction/SKILL.md`
- `.agents/skills/radar-quota-ledger/SKILL.md`
- `radar/.ecc/rules/backend.md` (quota durable, no sleep-only limiter)
- System prompt + schema: **immutabili** salvo necessità dimostrata

### Vincoli architetturali
- `main.py` API-only; ingest solo `worker.py`
- Reserve **prima** di ogni tentativo provider (anche dopo switch modello)
- Rispettare **Retry-After** (cooldown 24h è **oltre** il retry breve)
- Structured output obbligatorio (`response_schema` / JSON mime)
- Quote free spesso sono **per project**, non per API key — più chiavi stesso
  progetto **non** moltiplicano RPD (da verificare in ricerca)

========================================================================
## 1. FASE A — Ricerca modelli (OBBLIGATORIA, prima di codice)
========================================================================

### Obiettivo
Produrre `plan-audit/archive/llm-stubs/audit_llm_model_research.SUPERSEDED.md` con tabella comparativa
**verificata oggi** (WebSearch + fetch AI Google docs pricing/rate-limits).

### Criteri di ammissibilità (tutti)
1. Free tier (o free row sulla pricing page) per Developer API
2. Context window ≥ **100k** (idealmente 1M)
3. RPM free ≥ **10** (target 10–15)
4. RPD free ≥ **1000** (target 1000–2000; idealmente ≥1500)
5. Qualità percepita / posizionamento: Flash “pieno” o superiore a Flash-Lite;
   esplicitare se Flash-Lite è solo throughput e **non** soddisfa “≥ Gemma 31b”
6. Supporto **structured output / JSON schema** via `google-genai` SDK
7. Stabilità ops: note su 500, preview, deprecazioni

### Candidati da valutare (minimo — espandi se la ricerca ne trova altri free)
- `gemini-3-flash` / `gemini-3.0-flash` (nome esatto da docs)
- `gemini-3.1-flash-lite` (attuale ops — baseline throughput)
- `gemini-2.5-flash` / `gemini-2.5-flash-lite`
- `gemini-2.0-flash`
- `gemma-4-31b-it` / varianti Gemma su API (context spesso **piccolo** — può FALLIRE criterio 100k)
- Eventuali altri free su stesso provider **solo se** structured output ok

### Tabella obbligatoria nel report
| model_id | Free? | Context | RPM | TPM | RPD | Structured out | Qualità vs Gemma31b | Note | Rank |
| Fonte colonne: URL ufficiale + data check. Se quote divergono tra blog e
  docs Google, **prevale AI Studio / docs ufficiali**; marca “VERIFY_IN_STUDIO”.

### Output Fase A (stop se utente vuole approvare prima del codice)
1. Ranked shortlist **3–5 modelli** per la catena di fallback
2. Proposta ordine cascata (qualità prima vs throughput prima) con raccomandazione
3. Impatto su `LLM_RPM` / `LLM_RPD` env (valori consigliati per restare sotto free)
4. Rischio: RPD **condiviso** tra modelli vs bucket **per-modello** (da chiarire)

**Raccomandazione di design attesa (da confermare con dati):**
- Primary: miglior Flash free con qualità alta (es. Gemini 3 Flash se free e ≥10 RPM / ≥1k RPD)
- Secondary: altro Flash generazione precedente ancora free
- Tertiary: Flash-Lite per assorbire burst quando i “pieni” sono in cooldown
- Gemma 31b: solo se context ≥100k **e** free; altrimenti fuori catena o “legacy opt-in”

========================================================================
## 2. FASE B — Design fallback + cooldown 24h
========================================================================

Scrivi `plan-audit/archive/llm-stubs/plan_llm_multi_model_fallback.SUPERSEDED.md` prima di implementare.

### Comportamento richiesto
```
active = first model in chain not in cooldown
on classify attempt:
  reserve(model=active)
  call provider(active)
  on success → complete; keep active
  on retryable 429 with Retry-After short → wait; same model (existing path)
  on “model exhausted / hard fail” → mark cooldown(active, until=now+24h);
       switch to next eligible; reserve+retry on new model (new reservation)
  if all in cooldown → fail soft / fallback article (existing get_fallback_article)
```

### Definizione “scadenza” che attiva cooldown 24h (precisa nel design)
Includere almeno:
- RPD provider esaurito (429 con messaggio daily / resource exhausted day)
- Serie di 5xx/500 specifiche modello dopo N tentativi
- Model not found / not supported for free tier
- Opz. circuit: N fail consecutivi sullo stesso model_id in finestra breve

**NON** mettere in cooldown 24h per:
- 429 con Retry-After di secondi/minuti (gestito dal client attuale)
- ValidationError schema (correction loop, stesso modello)
- Timeout singolo isolato (retry classificato)

### Persistenza cooldown
Scelta da valutare (pro/contro nel design; raccomandare una):

| Opzione | Pro | Contro |
|---------|-----|--------|
| **A. Tabella SQL** `llm_model_cooldown(model, until_ts)` | Survive restart worker; multi-replica safe | Migrazione nuova |
| B. Solo env/memoria processo | Semplice | Si perde al restart; 2 worker = stato divergente |
| C. Riuso `llm_request_ledger` aggregati | No nuova tabella | Query fragili; semantica ambigua |

**Scelta raccomandata da adottare salvo controindicazioni:** **A (SQL durable)**.

### Config proposta (env) — SoT v2.2
```
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_MODEL_FALLBACKS=
LLM_SIMPLE_PROVIDER=gemini
LLM_SIMPLE_MODEL=gemini-3.1-flash-lite
LLM_COMPLEX_PROVIDER=deepseek
LLM_COMPLEX_MODEL=deepseek-v4-flash
LLM_ROUTING_MODE=complexity
LLM_ROUTING_SHADOW=false
DEEPSEEK_REASONING_EFFORT=high
LLM_MODEL_COOLDOWN_HOURS=24
LLM_RPM=10
LLM_RPD=1400
```
Lane = provider+model per fascia; Gemini fallbacks solo se `*_PROVIDER=gemini`.
Vedi SoT §5 per elenco completo.
### Quote ledger
- Ogni tentativo (anche post-switch) → **nuovo** `reserve` con `model=` corretto
- Soft-trim worker: considerare se RPD è globale o per-modello (allineare a ricerca)
- Se bucket free è per-modello: cooldown 24h su modello A permette di usare B
  sullo stesso giorno → grande vantaggio ops
- Se bucket è shared project-wide: fallback aiuta su 500/qualità, **non** su RPD

### Test da prevedere
- Unit: selezione next model skippa cooldown attivi
- Unit: after 24h model torna eleggibile (clock fake)
- Unit: 429 short Retry-After NON scrive cooldown 24h
- Unit: hard exhaust scrive cooldown e switcha
- Integration smoke: ClassificationClient con mock quota + mock provider

========================================================================
## 3. FASE C — Implementazione (dopo design)
========================================================================

### Allowlist tipica
- `radar/backend/app/core/config.py` — parse lista modelli + cooldown hours
- `radar/backend/app/classification/client.py` — model router + switch
- `radar/backend/app/classification/quota.py` — solo se serve per-model windows
- `radar/backend/migrations/00N_llm_model_cooldown.sql` — se Opzione A
- `radar/backend/app/tests/test_*.py` — nuovi test
- `radar/.env.example` — documentare vars
- Docs: `radar/docs/runbook.md` (ops modello), skill mirrors se necessario
- Report: `plan-audit/remediation/audit_remediation_llm_multi_model_fallback.md`

### Vietato
- Sidebar / frontend map
- Rimuovere QuotaLedger o tornare a sleep-only limiter
- Hardcodare API key
- Cambiare system prompt / schema senza necessità
- Commit di `.env` reale

### Gate
```powershell
cd "c:\Users\lucag\Documents\Dashboard finance\radar"
$env:PYTHONPATH = "backend"
python -m pytest -m "not live" -q
# test mirati model router + cooldown
python -m pytest backend/app/tests/test_classification.py backend/app/tests/test_quota_concurrency.py -q
```

Rebuild worker dopo merge locale:
`docker compose up -d --build radar-worker` (no-cache se layer app cached).

========================================================================
## 4. Sotto-agenti suggeriti
========================================================================

| ID | Ruolo | Quando |
|----|-------|--------|
| R1 | `generalPurpose` — WebSearch/fetch pricing+rate-limits; scrive research md | Fase A |
| R2 | `generalPurpose` — design md + schema migrazione | Fase B |
| R3 | `generalPurpose` — implement client+config+tests | Fase C |
| R4 | `shell` — pytest + compose rebuild worker | Gate |

A → stop per conferma utente sulla shortlist **se** qualità/quote incerte.
Poi B → C → gate.

========================================================================
## 5. Output orchestratore (italiano)
========================================================================

1. Fase corrente (A/B/C) + verdetto
2. Tabella shortlist modelli (da research) con rank
3. Catena fallback proposta + perché
4. Scelta persistenza cooldown (A/B/C)
5. File touched (se C)
6. Esiti pytest / note Docker worker
7. Handoff: valori `.env` da impostare + come verificare cooldown in SQL
8. Domanda: commit? rebuild? smoke classificazione live (1 articolo)?
```

---

## Note per te (operatore)

- **Prima** lancia solo Fase A se vuoi approvare i modelli a mano: aggiungi  
  `/goal … Esegui SOLO Fase A (ricerca). STOP prima del codice.`
- Le quote free cambiano spesso: il report deve citare **data + URL** ufficiali.
- Con `LLM_RPM=10–15` e `LLM_RPD=1400–2000` resti dentro i vincoli che hai indicato; il ledger Radar è già allineato.
- Qualità “≥ Gemma 31b”: su free tier tipicamente punta a **Flash pieno** (3 / 2.5), non a Flash-Lite come primary; Lite resta tertiary di throughput.
