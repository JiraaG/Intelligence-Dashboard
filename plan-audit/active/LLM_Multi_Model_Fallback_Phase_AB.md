# LLM Multi-Model Fallback — Documento unico Fase A+B

> **Stato:** SoT design A+B + **Fase C implementata** + **lane env v2.2** + **heuristic complexity v2.2** (2026-07-16).  
> **Skills:** `llm-json-extraction`, `radar-quota-ledger`.  
> **Sostituisce come riferimento operativo:** stub in `archive/llm-stubs/`.  
> **Canvas:** `article-complexity-routing.canvas.tsx` + `complexity-routing-audit.canvas.tsx`.  
> **Prompt:** `../prompts/active/audit_prompt_llm_multi_model_fallback.md` (storico; SoT = questo file).  
> **Remediation:** `../remediation/audit_remediation_llm_multi_model_fallback.md`.  
> **Indice cartelle:** [`../README.md`](../README.md).

---

## 0. Executive summary

| Domanda | Verdetto |
|---------|----------|
| Cascata Gemini free ha senso? | **Sì** — ops tipico: Lite bulk; Flash pieni solo se RPD Studio ≥~500 |
| Paid DeepSeek ha senso? | **Sì** — `deepseek-v4-flash` + `reasoning_effort=high` (~$0.001/art.), non Max |
| Routing per complessità? | **Sì, a tre fasce** (SIMPLE / BORDERLINE / COMPLEX). Complessità = **rischio estrazione schema** (G/E/X), non lunghezza sola |
| Provider/model per lane? | **Env** — `LLM_SIMPLE_*` (solo SIMPLE) + `LLM_COMPLEX_*` (**BORDERLINE + COMPLEX** + escalate) |
| Free o paid come “path primario”? | **Vietato** — SLO mix + quorum famiglie + shadow ≥3g |
| Cooldown 24h? | **SQL durable** `(provider, model, until_ts, reason)` |
| Fase C? | **DONE** — vedi remediation; default codice `LLM_ROUTING_MODE=off` |

**Catena ops attuale (2026-07-16)**

```text
LLM_ROUTING_MODE=complexity
LLM_ROUTING_SHADOW=false
# Bulk economico (thinking off)
LLM_SIMPLE_PROVIDER=deepseek
LLM_SIMPLE_MODEL=deepseek-v4-flash
LLM_SIMPLE_REASONING_EFFORT=none
# BORDERLINE + COMPLEX + escalate (thinking on)
LLM_COMPLEX_PROVIDER=deepseek
LLM_COMPLEX_MODEL=deepseek-v4-flash
LLM_COMPLEX_REASONING_EFFORT=high
# Legacy Gemini ancora supportato se si ripunta SIMPLE/COMPLEX a gemini
GEMINI_MODEL_FALLBACKS=

# Swap COMPLEX → Google senza codice:
#   LLM_COMPLEX_PROVIDER=gemini
#   LLM_COMPLEX_MODEL=gemini-3.5-flash
```

---

## 1. Analisi complessiva della fase

### 1.1 Cosa è stato fatto

| Step | Contenuto | Esito |
|------|-----------|-------|
| Fase A Google | Pricing/rate-limits/models ufficiali + VERIFY_IN_STUDIO | Shortlist Flash 3.5 / 2.5 / 3.1-Lite |
| Fase A esterni free | Groq, Cerebras, OpenRouter, GitHub, … | Nessuno batte Gemini su 1M+~1500 RPD+TPM insieme |
| Fase A paid-cheap | DeepSeek V4 Flash High vs Max + AA Index | High scelto (37 vs Gemma 29; Max overkill) |
| Design B lineare | Cascata + cooldown 24h | Base valida ma insufficiente da sola |
| Design B complexity | Lane SIMPLE/COMPLEX + T=40 | **Respinto** dalla verifica anti-skew |
| Verifica anti-skew | Corpus vault 2492 + failure modes F1–F6 | Design **v2.1** (tre fasce, quorum) |
| Consolidamento | Questo file | Unica SoT + correzioni §2 |

### 1.2 Allineamento al sistema Radar (AS-IS)

| Componente | Path | Vincolo per Fase C |
|------------|------|--------------------|
| Config modello | `core/config.py` | **TO-BE fatto:** Gemini + DeepSeek + routing + `LLM_SIMPLE_*` / `LLM_COMPLEX_*` |
| Client | `classification/client.py` | Lane chain + escalate; `content[:4000]`; `_MAX_ATTEMPTS=4`; QuotaLedger; fallback |
| Parser | `extraction/parser.py` | Score complessità **dopo** `strip_html_tags` |
| Schema | `validator.py` | `GeopoliticalArticleSchema` strict — **immutabile** |
| Worker | `worker.py` | sanitize → classify → commit/outbox; soft-trim RPD |
| Ledger | `quota.py` + migrations | `reserve(model=)` già esiste; cooldown = tabella nuova |
| API | `main.py` | API-only — **non** spostare ingest |

### 1.3 Evidenza empirica (vault, 2026-07-16)

Probe su **2492** articoli post-classificazione (`radar/vault/**/*.md`):

| Metrica | Valore | Lettura |
|---------|-------:|---------|
| `country_code=XX` | **24.8%** | ~1/4 geo “undetermined” con Gemini-only — **non tutti sono errori** (pezzi davvero internazionali) |
| Top `US` | **45.9%** | Bulk mono-paese → deve restare free se euristica sana |
| Multi-nazione solo titolo | **~4.6%** | Titolo-only → free-primary di fatto (F1) |
| Body vault p50/p90 | 851 / 1854 | Vault = riassunti → **non** calibrare lunghezza qui |

**Implicazione:** calibrare shadow su **content Miniflux live**, non sul vault. Usare XX come KPI *secondario*; primari = share lane, escalate rate, ValidationError/100.

### 1.4 Cosa funzionava / cosa no nella v1

| Elemento | Valutazione |
|----------|-------------|
| Cascata qualità-prima Gemini | Solida |
| DeepSeek High (non Max) | Solida |
| Cooldown SQL 24h | Solida |
| Binario `score ≥ 40` | **Fragile** → F1/F2 |
| “~70–90% free” come obiettivo | **Skew verso free-primary**; contraddice XX~25% |
| Score mid-band + quorum sovrapposti | Ambiguo (corretto in §2) |
| “Alzare char su COMPLEX” | Conflitto con invariante `[:4000]` (corretto in §2) |

---

## 2. Correzioni applicate in questa revisione (v2.1)

| # | Problema | Correzione |
|---|----------|------------|
| C1 | Precedenza lane ambigua (0 famiglie vs mid-band score) | **Lane = quorum famiglie** (0/1/≥2). Score solo log + override soft futuro |
| C2 | `G∧E` ridondante con “≥2 famiglie” | Rimosso |
| C3 | `T_high=55` morto (max 1 famiglia ≈30 punti) | Lane non dipende da T_high oggi; env tenuto per soft-signal futuri; **non** usare come driver v1 |
| C4 | `force linear` vs `force off` | Unificato: **`LLM_ROUTING_MODE=off` + WARNING** (o fail startup se `strict`) |
| C5 | “Alzare budget char” su DeepSeek | **Vietato in v1** — stesso `content[:4000]` su tutte le lane |
| C6 | Escalate BORDERLINE al *primo* ValidationError | **Dopo 1 correction fallita** (evita pagare glitch JSON transienti) |
| C7 | XX=fallimento assoluto | XX KPI secondario; pezzi internazionali legittimi restano XX |
| C8 | `LLM_RPD` globale vs Lite~1000 | v1: globale **1400**; soft-trim non deve spingere Lite oltre RPD Studio VERIFY; fase 2: cap per-model |
| C9 | Groq in shortlist esterna | **Fuori catena v1** (TPM 6–30K stretto); opzionale fase 2 |
| C10 | Documenti multipli divergenti | Questo file = SoT unica |

---

## 3. Ricerca modelli (Fase A — sintesi)

### 3.1 Fonti (check 2026-07-16)

- [Google pricing](https://ai.google.dev/gemini-api/docs/pricing) · [rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits) · [models](https://ai.google.dev/gemini-api/docs/models)
- [Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash) · [structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing) · [thinking](https://api-docs.deepseek.com/guides/thinking_mode) · [JSON](https://api-docs.deepseek.com/guides/json_mode)
- [Artificial Analysis](https://artificialanalysis.ai/) · Groq/OpenRouter docs per esclusione free esterni

Quote RPM/RPD Google: **VERIFY_IN_STUDIO** sul progetto della `GOOGLE_API_KEY` (non hardcodare community).

### 3.2 Google — shortlist

| Rank | model_id | Ruolo | Note |
|------|----------|-------|------|
| 1 | `gemini-3.5-flash` | Primary free | Free, stable, 1M, structured, qualità max free |
| 2 | `gemini-2.5-flash` | Secondary | Free, stable, Flash pieno |
| 3 | `gemini-3.1-flash-lite` | Tertiary | Throughput; AA **25 &lt; Gemma 29** → mai primary |
| L | `gemma-4-31b-it` | Legacy opt-in | 256K OK; ops HTTP 500 → fuori default |
| OUT | `gemini-2.0-*` | — | Shut down 2026-06-01 |
| OUT | Pro free tipico | — | RPD ≪1000 |

**Env consigliati (Profilo A / Gemini free, VERIFY_IN_STUDIO):**  
`LLM_SIMPLE_RPM` / `LLM_SIMPLE_RPD` (non i legacy `LLM_RPM`/`LLM_RPD` se i campi lane sono già settati).  
Esempio di partenza storico: RPM≈10, RPD≈1000–1400 — **ricalibrare in AI Studio**.

**Quote:** per **project**, non per API key; limiti tipicamente **per model variation** → switch modello può dare RPD fresco lo stesso giorno (VERIFY).

### 3.3 Esterni free — esito

| Provider | Fit | Motivo OUT / bordo |
|----------|-----|-------------------|
| Groq Llama-4 Scout | Bordo | 30 RPM / 1K RPD / 30K TPM — tight vs articoli lunghi |
| Cerebras free | OUT | RPM 5; context free spesso 8K |
| OpenRouter `:free` | OUT volume | 50 RPD (1000 solo dopo $10 lifetime) |
| GitHub Models | OUT | RPD 50–150; cap token/request |

### 3.4 DeepSeek V4 Flash High

| Campo | Valore |
|-------|--------|
| Model | `deepseek-v4-flash` |
| Effort | **`high`** (mai `max` di default) |
| Context | 1M |
| Concurrency | 2500 |
| Pricing /1M | cache hit $0.0028 / miss $0.14 / out $0.28 |
| Structured | `json_object` + Pydantic Radar (scartare `reasoning_content`) |
| AA Index | High **~37** · Max **40** · Gemma 31B **29** · Gemini 3.5 Flash **~55** · Flash-Lite **25** |
| Costo Radar | ~$0.001/art. → ~$0.5–3/giorno se *tutto* paid; con mix 25% COMPLEX ≈ **~$0.25–0.75/giorno** |

High vs Max: stesso $/token; Max più verboso (reasoning) → costo↑ per +3 Index. **Scelta: High.**

---

## 4. Design routing (anti-skew) — algoritmo live **v2.2**

> Storico: design iniziale “v2.1” (BORDERLINE=catena SIMPLE; L sola→BORDERLINE) è **superseded**.
> Codice live = heuristic + chain **v2.2** sotto.

### 4.1 Definizione di “complesso”

**Non** IQ del pezzo. **Sì** rischio di fallire lo schema Radar:

`country_code` (XX / paese sbagliato) · lat/lon · `companies_involved` · category/tags · title/summary IT.

Misura: dopo `strip_html_tags`, su title+body sanitizzato **intero**.  
Call LLM: sempre `content[:4000]` (tutte le lane).

### 4.2 Failure modes da non reintrodurre

| ID | Nome | Effetto |
|----|------|---------|
| F1 | Free-primary | COMPLEX &lt;15% → DeepSeek accessorio; XX non migliora |
| F2 | Paid-primary | COMPLEX &gt;50% → credito = default |
| F3 | Single-signal | Un feature domina lo skew |
| F4 | Silent paid-off | Key assente → tutto Gemini senza alert |
| F5 | Escalation-only | Paid solo post-fail raro |
| F6 | Vault overfitting | Soglie lunghezze calibrate su riassunti |

### 4.3 Famiglie di segnale

| Famiglia | Attivazione (codice live) | Campo a rischio |
|----------|---------------------------|-----------------|
| **G** Geo | ≥2 nazioni lexicon EN/IT **oppure** `geo_marker` con `body_len ≥ 1500` | country_code, lat/lon |
| **E** Entità | ≥3 org suffix (`Inc\|Ltd\|LLC\|GmbH\|SpA\|AG\|Corp\|PLC\|SA`) | companies_involved |
| **L** Lunghezza | `len(body) ≥ 6000` (+30 log se ≥12000) | trim 4000 |
| **X** Lingua | ratio non-latino ≥0.15 su sample 4k | title/summary IT |
| **N** Negative | title&lt;40 ∧ body&lt;800 ∧ nessuna famiglia positiva | forza SIMPLE |

Punti (solo logging): L +20/+30 · G +25 · E +15 · X +20 · N −15.

Implementazione: lexicon paesi; ISO allowlist; no `langdetect` in v1.

### 4.4 Algoritmo lane (deterministico) — heuristic **v2.2**

Complessità = **rischio estrazione schema** (geo ambigua, multi-entità, script), **non** IQ e **non** lunghezza sola.

```text
families = {G,E,L,X} attive  # N gestito a parte
strong = families ∩ {G,E,X}

# G: ≥2 country names → sempre; geo_marker da solo solo se body_len ≥ 1500
if N and not families:
    lane = SIMPLE
elif families == {L}:
    lane = SIMPLE          # L sola non eleva (v2.2)
elif len(families) >= 2:
    lane = COMPLEX         # L conta solo in combo
elif len(strong) == 1:
    lane = BORDERLINE
else:
    lane = SIMPLE
```

| Lane | Catena (via env) | Escalation validation |
|------|------------------|------------------------|
| **SIMPLE** | `LLM_SIMPLE_*` (tipico `effort=none`) | Dopo `_MAX_ATTEMPTS` → **1×** `LLM_COMPLEX_*` |
| **BORDERLINE** | **`LLM_COMPLEX_*`** (tipico `effort=high`) — v2.2 | Dopo **1 correction fallita** resta su COMPLEX (già high); escalate legacy se identity diversa |
| **COMPLEX** | `LLM_COMPLEX_*` → residuale SIMPLE | Se COMPLEX down / no key → SIMPLE; poi fallback article |

Provider ammessi: `gemini` \| `deepseek` \| `openai` \| `claude` (claude stub). DeepSeek riceve `model=` + effort dalla lane (`LLM_*_REASONING_EFFORT`; `none` = thinking disabled).

### 4.5 SLO mix (anti “path primario”)

| KPI | Banda | Fuori banda |
|-----|-------|-------------|
| Share COMPLEX (pre-call) | monitor | Con ops DeepSeek none/high tipicamente &lt;20% (G+L rari) |
| Share BORDERLINE | monitor | Ora costa come COMPLEX (high); L-sola non gonfia più questa fascia |
| Escalate / giorno | monitor | Spike → G debole o JSON fragile |
| XX su lane SIMPLE | trend vs baseline | Se peggiora → rafforzare G |
| USD DeepSeek / giorno | ≤ budget soft-cap | Soft-cap in `QuotaLedger` (`0` = off) |

**Gate go-live:** shadow ≥**3 giorni** su Miniflux live (`LLM_ROUTING_SHADOW=true`: logga lane, call ancora Gemini-only) con COMPLEX share in 20–40%. Poi `SHADOW=false`.

### 4.6 Guardrail

| Regola | Comportamento |
|--------|----------------|
| `LLM_COMPLEX_PROVIDER=deepseek` senza key | WARNING + COMPLEX usa SIMPLE; `LLM_ROUTING_STRICT=1` → fail startup |
| Crediti / 402 | Cooldown DeepSeek + log `complex_lane deepseek cooldown` |
| No length-only → COMPLEX | Solo L → **SIMPLE** (v2.2; non BORDERLINE) |
| No length-only → BORDERLINE | Idem — L sola non è rischio schema |
| geo_marker corto | Ignorato se `body_len < 1500` (anti FP pitch HN) |
| No title-only | G dal body |
| Stesso truncate | `[:4000]` ovunque in v1 |

### 4.7 Flusso unificato + cooldown

```text
sanitize → heuristic(families) → lane → chain_for(lane) filtrata da cooldown/key/budget
for model in chain:
  reserve(model)          # SEMPRE prima del provider
  call → validate
  short_429 → wait Retry-After; stesso modello (NO cooldown 24h)
  ValidationError → correction / escalate per regola lane
  hard_fail (RPD day, 402, 5xx×N, NOT_FOUND, context×2) → cooldown 24h; next
exhausted → get_fallback_article
```

**Cooldown 24h sì:** RPD daily esausto, 402/crediti, 5xx×N, NOT_FOUND, context overflow dopo re-trim.  
**No:** 429 breve, ValidationError, timeout isolato.

Persistenza: SQL `llm_model_cooldown(provider, model, until_ts, reason)` — **Opzione A**.  
Chiave: `provider`+`model` (+ opz. effort). Cooldown condiviso tra tutte le lane.

```mermaid
flowchart TD
  A[Sanitize] --> H[Famiglie G/E/L/X/N]
  H -->|0 o solo L| S[SIMPLE]
  H -->|1 di G/E/X| B[BORDERLINE]
  H -->|≥2 famiglie| C[COMPLEX]
  S --> P1[LLM_SIMPLE effort none]
  B --> P2[LLM_COMPLEX effort high]
  C --> P2
  P1 -->|ok| OK[Commit]
  P2 -->|ok| OK
  S -->|validation×N| P2
  P2 -->|down| R[SIMPLE residual]
  R -->|fail| FB[fallback article]
```

---

## 5. Config env (SoT ops)

Limiti e provider sono **per lane** (`LLM_SIMPLE_*` / `LLM_COMPLEX_*`).  
Legacy `LLM_RPM` / `DEEPSEEK_*` = fill-gap se il campo lane è assente — **non** un tetto globale.

### Profilo B — DeepSeek-only (ops tipico / `.env.example` attivo)

```text
LLM_ROUTING_MODE=complexity          # off | complexity  (default codice: off)
LLM_ROUTING_SHADOW=false             # true = log lane, call sempre SIMPLE
LLM_ROUTING_STRICT=0
LLM_COMPLEXITY_ESCALATE_ON_VALIDATION=1
LLM_MODEL_COOLDOWN_HOURS=24

# SIMPLE = Flash non-thinking; COMPLEX = stesso modello, effort high
LLM_SIMPLE_PROVIDER=deepseek
LLM_SIMPLE_MODEL=deepseek-v4-flash
LLM_SIMPLE_REASONING_EFFORT=none
LLM_SIMPLE_RPM=0                     # paid: 0 = unmanaged
LLM_SIMPLE_TPM=0
LLM_SIMPLE_RPD=0                     # soft-trim worker off se 0
LLM_SIMPLE_BUDGET_USD_DAY=0

LLM_COMPLEX_PROVIDER=deepseek
LLM_COMPLEX_MODEL=deepseek-v4-flash
LLM_COMPLEX_REASONING_EFFORT=high
LLM_COMPLEX_RPM=0
LLM_COMPLEX_TPM=0
LLM_COMPLEX_RPD=0
LLM_COMPLEX_BUDGET_USD_DAY=0

DEEPSEEK_API_KEY=...                 # non commitare
DEEPSEEK_BUDGET_USD_DAY=0            # legacy alias → COMPLEX budget se lane unset
```

### Profilo A — Hybrid free Gemini + paid DeepSeek (commentato in `.env.example`)

```text
# Free Gemini → RPM/RPD > 0 (VERIFY_IN_STUDIO); paid DeepSeek → RPM/RPD=0 + BUDGET
LLM_SIMPLE_PROVIDER=gemini
LLM_SIMPLE_MODEL=gemini-3.1-flash-lite
LLM_SIMPLE_RPM=10                    # VERIFY_IN_STUDIO
LLM_SIMPLE_RPD=1000                  # VERIFY_IN_STUDIO — soft-trim usa questo se > 0
LLM_COMPLEX_PROVIDER=deepseek
LLM_COMPLEX_MODEL=deepseek-v4-flash
LLM_COMPLEX_RPM=0
LLM_COMPLEX_RPD=0
LLM_COMPLEX_BUDGET_USD_DAY=5         # soft-cap USD/giorno (esempio)
```

Legacy opzionale (solo fill-gap): `GEMINI_*`, `LLM_RPM`/`LLM_TPM`/`LLM_RPD`, `DEEPSEEK_*`.  
`off` / `shadow` = solo catena SIMPLE.  
Default codice senza env: `LLM_ROUTING_MODE=off`, `LLM_ROUTING_SHADOW=true` (boot sicuro).  
Periodicità ciclo: `WORKER_POLL_INTERVAL_SECONDS` (default **900**).  
Env `T_LOW`/`T_HIGH` **non** richiesti (lane = heuristic famiglie v2.2).

---

## 6. Quote ledger (invarianti)

1. `reserve(model=…, lane=…, provider=…)` prima di **ogni** tentativo (anche switch lane/escalate).  
2. `complete` / `fail` sulla stessa `reservation_id`.  
3. Limiti **per lane**: `LLM_SIMPLE_RPM/TPM/RPD` e `LLM_COMPLEX_*` (`0` = dimensione unmanaged su quella lane).  
4. Legacy `LLM_RPM` / `DEEPSEEK_RPM` = **alias fill-gap**, non tetto globale shared.  
5. Soft-trim worker: solo `LLM_SIMPLE.rpd` se `> 0` (indipendente dal provider della lane SIMPLE).  
6. Free tier → RPM/RPD `> 0`; paid → RPM/RPD `= 0` + `*_BUDGET_USD_DAY` / 402.  
7. Residual cross-lane SIMPLE↔COMPLEX se identity diversa (fattura `ref.quota_lane`).  
8. Retry-After breve ≠ cooldown 24h.  
9. System prompt + schema Pydantic **immutabili**.

---

## 7. Impatto atteso

| Metrica | Attesa |
|---------|--------|
| Latenza p50 (Profilo B DeepSeek none) | Tipicamente bassa (non-thinking) |
| Latenza p95 COMPLEX / BORDERLINE | +0.5–3s (`effort=high`) — ok worker async |
| Costo @ 25% COMPLEX / 1500 art (paid DeepSeek) | **~$0.25–0.75/giorno** |
| Mix | COMPLEX 20–40%, BORDERLINE 15–35% (osservabile con shadow 3g) |
| Qualità | Meno ValidationError / meno XX “sbagliati” su pezzi multi-paese |

---

## 8. Allowlist Fase C + test

### 8.1 File toccabili

- `radar/backend/app/core/config.py`
- `radar/backend/app/classification/complexity.py` (**nuovo**)
- `radar/backend/app/classification/client.py` — router + dual provider
- `radar/backend/app/classification/quota.py` — solo se budget/per-model
- `radar/backend/migrations/00N_llm_model_cooldown.sql`
- `radar/backend/app/tests/test_*.py`
- `radar/.env.example`, `radar/docs/runbook.md`
- Report post-ship: `plan-audit/remediation/audit_remediation_llm_multi_model_fallback.md`

**Vietato:** sidebar; rimuovere QuotaLedger; hardcodare key; cambiare prompt/schema senza necessità; DeepSeek Max default; commit `.env`.

### 8.2 Test minimi

- 0 famiglie → SIMPLE  
- solo G (corto multi-paese ≥2 country) → BORDERLINE  
- G+E o ≥2 → COMPLEX  
- solo L lungo mono-US → **SIMPLE** (v2.2; non BORDERLINE/COMPLEX)  
- geo_marker su body corto (&lt;1500) → **non** G  
- titolo mono + body multi → G dal body  
- `_chain_for(BORDERLINE)` → refs `LLM_COMPLEX` effort high  
- BORDERLINE/SIMPLE escalate rules; SIMPLE dopo N validation fail  
- `complexity` + no key → off+WARN o fail se strict  
- 402 → cooldown; 429 short → no cooldown  
- Shadow: lane loggata, catena sempre SIMPLE  
- `LLM_COMPLEX_MODEL` passato a DeepSeek `classify_json(model=)` (+ effort lane)  

### 8.3 Gate

```powershell
cd "c:\Users\lucag\Documents\Dashboard finance\radar"
$env:PYTHONPATH = "backend"
python -m pytest -m "not live" -q
python -m pytest backend/app/tests/test_classification.py backend/app/tests/test_quota_concurrency.py -q
```

Poi: `docker compose up -d --build radar-worker` · VERIFY_IN_STUDIO · shadow 3g.

---

## 9. Considerazioni residue (non bloccanti Fase C)

| Tema | Nota | Quando |
|------|------|--------|
| Soft-signal / T_high | Se lexicon G under-trigger, aggiungere punti soft senza nuova famiglia | Post-shadow |
| Cap escalate/giorno | Se BORDERLINE spende troppo | Soft-cap env |
| Groq tertiary | Solo se TPM VERIFY regge prompt Radar | Fase 2 |
| RPD per-model ledger | Evita di sforare Lite~1000 | Fase 2 |
| XX labeling | Distinguere XX “corretto” vs “fallimento” (difficile) | Analytics |
| Content &gt;4000 | Eventuale densify/summary pre-call — **non** alzare truncate alla cieca | Fase 2+ |

---

## 10. Checklist best practise

- [x] Complessità = rischio schema, non IQ  
- [x] Multi-feature + quorum (no single-signal)  
- [x] BORDERLINE anti lock-in free/paid  
- [x] SLO mix 20–40% COMPLEX  
- [x] Fail-loud / visible se paid down  
- [x] Stesso `[:4000]` / stesso schema  
- [x] QuotaLedger reserve prima di ogni call  
- [x] Cooldown SQL 24h  
- [x] High non Max  
- [ ] Shadow 3g Miniflux live (gate go-live)  
- [ ] VERIFY_IN_STUDIO RPM/RPD shortlist  

---

## 11. Raccomandazione finale

Adottare design **complexity + lane env v2.2** (implementato; vedi remediation):

1. Cascata provider/model **per lane** via env (`LLM_SIMPLE_*` / `LLM_COMPLEX_*`).  
2. DeepSeek Flash via **httpx** (no package `openai`): SIMPLE tipico `effort=none`; BORDERLINE/COMPLEX tipico `high`.  
3. Lane = heuristic v2.2: L-sola→SIMPLE; 1 di {G,E,X}→BORDERLINE→**catena COMPLEX**; ≥2→COMPLEX.  
4. Shadow opzionale per calibrazione; KPI mix monitorati (non forzare 20–40% se feed corti).  
5. Cooldown SQL `009`; ledger per `purpose=classify:{simple|complex}`.  
6. Soft-cap budget USD se `BUDGET_USD_DAY` > 0; RPM/TPM/RPD tipicamente `0` su paid.

---

## 12. Gap analysis AS-IS → TO-BE & Fase C blueprint

### 12.1 Pipeline AS-IS (non rompere)

```mermaid
flowchart LR
  MF[Miniflux] --> W[worker.py]
  W --> Strip[strip_html_tags]
  Strip --> Cl[ClassificationClient]
  Cl --> Res[QuotaLedger.reserve]
  Res --> Gen[google-genai]
  Gen --> Val[GeopoliticalArticleSchema]
  Val -->|ok| Commit[commit+outbox]
  Val -->|fail x4| FB[get_fallback_article]
```

| Pezzo | Path | Stato post-Fase C / v2.2 |
|-------|------|-------------------------|
| Client | `classification/client.py` | Cascade + lane + escalate + dual provider |
| Quota | `classification/quota.py` | `reserve(model=)` OK; cap **globali** |
| Config | `core/config.py` | Gemini + DeepSeek + routing + lane env |
| Worker | `worker.py` | Soft-trim RPD Gemini; heuristic nel client |
| Schema/prompt | `validator.py`, `prompts.py` | **Immutabili** |
| Cooldown | `cooldown.py` + `009_…sql` | Durable 24h |
| DeepSeek | `deepseek.py` | httpx; `model=` da lane |
| FE/API | DTO articles/map | Nessun `model_id` — out of scope |

### 12.2 Decisione ECC: DeepSeek via httpx

`radar/.ecc/rules/backend.md` vieta `openai` / `anthropic` / `langchain`.  
**Locked:** `httpx` async → `https://api.deepseek.com` (API OpenAI-compatible). Package `openai` resta VIETATO. Skills aggiornate di conseguenza.

### 12.3 Extension points

| File | Funzione / area | Cambio |
|------|-----------------|--------|
| `core/config.py` | LLM section | Chain, DeepSeek, routing, `LLM_SIMPLE_*` / `LLM_COMPLEX_*`, cooldown |
| `classification/complexity.py` | **nuovo** | Famiglie G/E/L/X/N → lane **v2.2** (L-sola→SIMPLE; G marker body≥1500) |
| `classification/cooldown.py` | **nuovo** | SQL + memory fallback test |
| `classification/deepseek.py` | **nuovo** | httpx; thinking none\|high via `LLM_*_REASONING_EFFORT` |
| `classification/client.py` | `classify_article` | Outer loop; BORDERLINE→COMPLEX chain; escalate; shadow |
| `migrations/009_llm_model_cooldown.sql` | **nuovo** | PK (provider, model) |
| `tests/test_complexity.py` | **nuovo** | Quorum lane |
| `tests/test_cooldown.py` | **nuovo** | set/skip/expire |
| `tests/test_classification.py` | esteso | cascade / escalate / shadow |
| `.env.example`, `docs/runbook.md`, ECC/skills | docs | Ops dual-provider |

### 12.4 TO-BE (runtime)

```text
sanitize → families → lane (v2.2)
if SHADOW or mode=off: log lane; chain = simple_chain (LLM_SIMPLE_*)
else: chain = chain_for(lane)
  # SIMPLE → LLM_SIMPLE_*; BORDERLINE|COMPLEX → LLM_COMPLEX_* (+ residual SIMPLE)
for ref in filter_cooldown(chain):
  for attempt in validation_loop:
    reserve(model=ref.model, lane=ref.quota_lane)
    call provider (gemini|deepseek)  # deepseek: classify_json(model=) + thinking per effort
    …
```

### 12.5 Attenzioni ops

- RPD ledger globale 1400 vs Lite tipico ~1000 (VERIFY_IN_STUDIO).  
- Budget USD DeepSeek: env presente, **enforcement post-v1**; 402 → cooldown SQL.  
- Mai alzare `content[:4000]`.  
- Default codice: `LLM_ROUTING_SHADOW=true` / `MODE=off` finché mix calibrato; ops live può forzare `SHADOW=false`.  
- Swap COMPLEX→Google: solo `LLM_COMPLEX_PROVIDER=gemini` + `LLM_COMPLEX_MODEL=…`.

---

## Appendice A — Archivio ricerca

Vedi `../archive/llm-stubs/audit_llm_model_research.SUPERSEDED.md` (redirect). Rank: §3.2.

## Appendice B — File correlati

| File | Ruolo |
|------|--------|
| **Questo file** | SoT Fase A+B + blueprint C |
| `../archive/llm-stubs/*.SUPERSEDED.md` | Stub superseduti |
| `../prompts/active/audit_prompt_llm_multi_model_fallback.md` | Prompt orchestratore |
| `../remediation/audit_remediation_llm_multi_model_fallback.md` | Report post-ship |
| `canvases/article-complexity-routing.canvas.tsx` | Deep-dive UX |
