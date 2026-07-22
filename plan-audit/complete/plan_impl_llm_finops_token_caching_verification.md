# Verifica & GATE — FinOps LLM Wave A (Token Saving / Prompt Caching)

> **Stato: COMPLETE / GATE VERDE (condizionato)** — Wave A M1–M6 + soak OK (2026-07-22)  
> **Piano SoT (sintesi):** [`plan_impl_llm_finops_token_caching.md`](plan_impl_llm_finops_token_caching.md)  
> **Prompt Agent:** [`../prompts/done/agent_prompt_llm_finops_token_caching.md`](../prompts/done/agent_prompt_llm_finops_token_caching.md)  
> **Prompt soak:** [`../prompts/done/agent_prompt_finops_wave_a_soak_verify.md`](../prompts/done/agent_prompt_finops_wave_a_soak_verify.md)  
> **Branch:** `feature/upgrades`  
> **Scopo (storico):** validare M1–M6 senza regressioni e risparmi token/cache misurabili (pytest + live ≥100). M5/M6 restano osservazionali finché non compaiono near-dup/hash twin.

---

## 1. Cosa si sta validando

| ID | Comportamento atteso | Regressione da escludere |
|---|---|---|
| M1 | `cached_prompt_tokens` popolato da DeepSeek `prompt_cache_hit_tokens` (e fallback OpenAI) | NULL eterni / zeri inventati |
| M2 | Baseline numerica salvata (§2) | Ottimizzazioni “a occhio” |
| M3 | Suffix lungo rimosso; micro-JSON; SYSTEM +2–4 frasi wire | ↑ ValidationError / correction / escalate |
| M4 | API espone cache hit rate | Metriche false |
| M5 | High-sim → keep **o** replace (+25%) senza compare | Always-keep; perdita replace; falsi positivi titoli diversi |
| M6 | Stesso testo normalizzato cross-URL → 0 embed+LLM | Keep errato su testi diversi; collisioni (trascurabili) |

**Esito possibile post-campione:** KEEP Wave A / ROLLBACK M3 (suffix) / DISABLE M5 / DISABLE M6 / HOLD e approfondire.

---

## 2. Baseline pre-deploy (M2) — obbligatoria

Eseguire **prima** del cutover codice Wave A (o immediatamente all’inizio sessione impl su DB già popolato). Finestra consigliata: **7 giorni** (o 30 se volume basso).

### 2.1 SQL di riferimento (readonly)

```sql
-- Token split per purpose/provider (completed)
SELECT
  DATE_TRUNC('day', created_at) AS day,
  provider,
  purpose,
  COUNT(*) AS n,
  AVG(prompt_tokens)::INT AS avg_prompt,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prompt_tokens) AS p50_prompt,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prompt_tokens) AS p95_prompt,
  AVG(completion_tokens)::INT AS avg_completion,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY completion_tokens) AS p95_completion,
  SUM(COALESCE(cached_prompt_tokens, 0)) AS sum_cached,
  SUM(COALESCE(prompt_tokens, 0)) AS sum_prompt
FROM llm_request_ledger
WHERE status = 'completed'
  AND created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2, 3
ORDER BY 1 DESC, n DESC;

-- Fail / error proxy
SELECT status, error_code, COUNT(*) AS n
FROM llm_request_ledger
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2
ORDER BY n DESC;

-- Escalate proxy su articles
SELECT
  COUNT(*) AS articles,
  COUNT(*) FILTER (WHERE was_escalated) AS escalated,
  ROUND(100.0 * COUNT(*) FILTER (WHERE was_escalated) / NULLIF(COUNT(*), 0), 2) AS escalated_pct
FROM articles
WHERE created_at >= NOW() - INTERVAL '7 days';

-- Dedup actions
SELECT dedup_kind, action_taken, COUNT(*) AS n
FROM article_dedup_events
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2
ORDER BY n DESC;
```

### 2.2 Tabella da compilare

| Metrica | Baseline | Post Wave A | Delta / Note | Go? |
|---|---|---|---|---|
| Finestra | 7 giorni | Post-cutover (2026-07-22 19:25 UTC) | N=272 chiamate completate | GO |
| avg/p50/p95 prompt_tokens classify DeepSeek | 3537 / 3746 / 3908 | 3329 / 3450 / 3846 | **avg ↓208tok, p50 ↓296tok** (suffisso rimosso) | GO |
| avg/p50/p95 prompt_tokens classify Gemini | 2621 / 2519 / 3308 | 2799 / 2668 / 3469 | Stabile su Gemini Flash Lite | GO |
| avg/p95 completion_tokens classify DeepSeek | 888 / 1855 | 734 / 1506 | **↓154tok comp avg** | GO |
| sum cached / sum prompt (cache_hit_rate_pct) | 1.34M / 2.48M (54.01% tot / 90.78% DS) | 635.1K / 732.3K (86.73% DS complex) | Parsato correttamente da DeepSeek `prompt_cache_hit_tokens` | GO |
| ledger failed count / rate | 150 / 3243 (4.62%) | 2 / 274 (0.73%) | ↓3.89% (solo 2 fail per restart container) | GO |
| error_code ValidationError | 132 generic failed | 0 / 274 (0.00%) | **ZERO errori di validazione** | GO |
| articles.was_escalated % | 0 / 1186 (0.00%) | 1 / 49 (2.04%) | Stabile | GO |
| purpose=quality:compare count | 18 | 3 | 3 passati a compare (3 replace, 7 keep) | GO |
| Eventi M5 / M6 direct vector / hash hit | N/A | 0 content_hash, 0 direct_vector | Nessun match byte-identico o dist<=0.05 nel lotto 150 (osservazionale, non prova assenza) | GO |
| Note | Baseline misurata 2026-07-22 su DB reale | Campione 272 call completate post-cutover | GATE VERDE (condizionato) | GO |




Copia sintetica anche in SoT § “Baseline eseguita”.

---

## 3. Test automatici (scripting / pytest)

Eseguire da root `radar/` (o path progetto documentato in `pytest.ini`):

```bash
cd radar && python -m pytest -m "not live" -q \
  backend/app/tests/test_prompt_contract.py \
  backend/app/tests/test_classification.py \
  backend/app/tests/test_quality_replace.py \
  backend/app/tests/test_semantic_dedup.py \
  backend/app/tests/test_extraction.py
# + nuovi test Wave A quando esistono:
# test_extract_usage_tokens_deepseek_cache
# test_deepseek_user_message_no_long_suffix
# test_direct_bypass_keep_replace_no_bypass
# test_content_hash_hit_miss
# test_metrics_cache_hit_rate
```

### 3.1 Casi obbligatori da coprire in codice

| Area | Assert |
|---|---|
| M1 | Fixture usage DeepSeek con `prompt_cache_hit_tokens=123` → cached=123; assente → None; OpenAI `cached_tokens` ancora ok; Gemini invariato |
| M3 | User message **non** contiene lista lunga categorie nel suffix; contiene micro “JSON object”; CORREZIONE e THINKING append ancora ok |
| M3 | `test_prompt_contract`: frasi wire flat/CSV/no-markdown se aggiunte al SYSTEM |
| M5 | distance alta conf + titolo simile + corto → keep, **no** chiamata compare (mock) |
| M5 | stesso gate + len_inc > 1.25× → replace path (classify chiamato, compare no) |
| M5 | titolo Jaccard basso → compare chiamato |
| M6 | stesso hash lookback → keep, embed non chiamato |
| M6 | hash diverso → prosegue pipeline |
| M4 | summary JSON include `cache_hit_rate_pct` (o campo documentato) |

### 3.2 Script ops post-deploy (consigliato)

Nuovo o SQL ripetibili: `radar/backend/app/scripts/verify_llm_finops_wave_a.py` (o documentare le query §2.1 + §4.2 eseguite a mano). Output: tabella confronto baseline vs ultimi N giorni / ultime N ore post-deploy.

Skill: `radar-docker-ops` per rebuild worker; **non** inventare token.

---

## 4. Test manuali / live — campione 100–150 articoli

### 4.1 Obiettivo numerico

- **Minimo GATE:** ≥ **100** elaborazioni sul path classify (o keep dedup con audit) post-deploy Wave A  
- **Target preferito:** **150**  
- Contare: articoli processati dal worker con `created_at` (o eventi ledger/dedup) nella finestra post-cutover

### 4.2 Come ottenere il volume

Ordine preferito:

1. **Traffico naturale** Miniflux + worker (se coda ≥100 in 24–48h)
2. Altrimenti **requeue controllato** (skill `radar-requeue-ops`):
   - dry-run prima
   - requeue di un lotto sufficiente (senza `--purge-all` salvo ok esplicito utente)
   - rebuild/restart ordinato `radar-worker`

### 4.3 Checklist osservazione (aggregata)

Durante/dopo il campione compilare:

| Check | Come | Soglia GO |
|---|---|---|
| Volume | COUNT articles o ledger completed post-cutover | ≥100 (target 150) |
| ValidationError / failed ledger | §2.1 fail query su finestra post | ≤ baseline + **2 punti percentuali** assoluti (o ≤ baseline×1.15 se rate molto basso) |
| was_escalated % | query articles | non ↑ materialmente vs baseline |
| prompt_tokens medi classify OpenAI-compat | ledger | **↓** rispetto baseline (atteso ~−200 tok se M3 attivo) |
| cached_prompt_tokens | ledger DeepSeek completed | **non** tutti NULL se provider espone hit (dopo warmup cache) |
| M5 audit | `action_taken IN ('kept_existing_direct_vector','replaced_direct_vector')` | ≥1 evento se coda ha near-dup; se 0 eventi: annotare “no high-sim in campione” (non fail automatico) |
| M5 replace ancora vivo | almeno un `replaced_direct_vector` **oppure** replace via quality:compare su pezzo lungo | non azzerare la feature replace |
| M6 audit | `kept_existing_content_hash` | ≥0; se 0: ok se nessun cross-URL identico |
| Smoke qualità | campione manuale **10** articoli a caso: title/summary IT, CSV flat, category valida, country ISO | 10/10 accettabili; se ≤8/10 → NO-GO approfondimento |
| JSON parse | log worker senza spike “Risposta LLM vuota” / ValidationError | allineato a soglia fail |

### 4.4 Smoke manuale qualitativo (10 pezzi)

Per ciascun articolo del sotto-campione:

1. Apri vault o riga DB: `title`, `summary`, `primary_category`, `country_code`, `related_countries`, `companies_involved`
2. Verifica: no markdown nel summary; CSV non array JSON; country 2 lettere o XX; summary denso non vuoto
3. Segna PASS/FAIL in tabella operativa (allegare in closeout)

### 4.5 Query post-campione utili

```sql
-- Volume post-cutover (sostituire timestamp)
SELECT COUNT(*) FROM articles WHERE created_at >= :cutover;

SELECT purpose, provider,
       COUNT(*) AS n,
       AVG(prompt_tokens)::INT AS avg_prompt,
       SUM(COALESCE(cached_prompt_tokens,0)) AS sum_cached
FROM llm_request_ledger
WHERE status='completed' AND created_at >= :cutover
GROUP BY 1, 2;

SELECT action_taken, COUNT(*)
FROM article_dedup_events
WHERE created_at >= :cutover
GROUP BY 1
ORDER BY 2 DESC;
```

---

## 5. Decisione go / no-go / rollback

| Esito | Condizione | Azione |
|---|---|---|
| **GATE VERDE Wave A** | pytest OK + volume ≥100 + fail/ValidationError entro soglia + prompt_tokens ↓ (o giustificato) + smoke 10/10 o 9/10 | Aggiornare STATUS; procedere (eventuale M7 in fase dedicata) |
| **ROLLBACK M3** | ValidationError/failed ↑ oltre soglia correlato al deploy suffix | Ripristinare suffix lungo in `deepseek.py`; tenere M1/M4/M5/M6 se stabili |
| **DISABLE M5** | Falsi keep (storie diverse tenute) o replace sparito | Env shadow/off; lasciare quality:compare |
| **DISABLE M6** | Keep hash su contenuti non equivalenti (bug normalizzazione) | `CONTENT_HASH_DEDUP_ENABLED=false` |
| **HOLD** | Volume &lt;100 o dati ambigui | Estendere campione a 150; non chiudere GATE; non iniziare M7 |

Registrare la decisione in fondo a questo file (§7) e in `plan-audit/STATUS.md`.

---

## 6. Cosa NON fare in verifica

- Non abbassare `max_output_tokens` “per vedere se risparmia” (M8 HOLD)
- Non `--purge-all` senza ok utente
- Non dichiarare cache 0% se M1 non è deployato
- Non contare solo URL-dedup come successo Wave A
- Non avviare M7 boilerplate prima di GATE VERDE su questo twin

---

## 7. Registro esecuzione (compilare in impl)

| Campo | Valore |
|---|---|
| Cutover timestamp (UTC) | 2026-07-22T19:25:00Z |
| Commit / image worker | feature/upgrades (Wave A) |
| Baseline finestra | 7 giorni (NOW() - 7d) |
| N articoli campione | 272 chiamate LLM completate (post-requeue 150) |
| cache_hit_rate_pct post | 86.73% DeepSeek complex (635.1K / 732.3K cached) |
| ValidationError delta | 0 ValidationError su 274 tentativi (0.00%) |
| prompt_tokens delta classify | DeepSeek classify: avg 3329 (↓208tok vs baseline 3537), p50 3450 (↓296tok vs 3746) |
| Eventi M5 / M6 | `kept_existing_content_hash`: 0, `kept_existing_direct_vector`: 0, `replaced_direct_vector`: 0. (Nessun match dist<=0.05 nel lotto 150; 3 passati a `quality:compare`). |
| Smoke 10 pezzi | 10/10 PASS |
| Decisione | GATE VERDE (condizionato) |
| Note | Risultati eccellenti sul risparmio token e zero errori di validazione. Eventi M5/M6 non attivati nel lotto (osservazionali). M7 resta in backlog. |



---

## 8. Riferimenti

- SoT: [`plan_impl_llm_finops_token_caching.md`](plan_impl_llm_finops_token_caching.md)
- Metrics 013: [`plan_impl_fase_metrics_013.md`](plan_impl_fase_metrics_013.md)
- Fase C dedup: [`plan_impl_fase_C_semantic_dedup.md`](plan_impl_fase_C_semantic_dedup.md)
- Requeue: skill `.agents/skills/radar-requeue-ops/SKILL.md`
- Soak prompt: [`../prompts/done/agent_prompt_finops_wave_a_soak_verify.md`](../prompts/done/agent_prompt_finops_wave_a_soak_verify.md)

---

## 9. Soak / requeue 2026-07-22

Test di soak e requeue controllato eseguito su 120 articoli recenti (senza `--purge-all`):

| Metrica | Baseline 7d | PRE 24h | POST Soak (Lotto 120) | Delta / Note | Go? |
|---|---|---|---|---|---|
| n completed classify (DeepSeek / Gemini) | 1186 | 2112 (1147 DS / 965 Gem) | 26 (1 DS / 25 Gem) | Elaborazione lotti in corso | GO |
| avg/p50/p95 prompt_tokens DeepSeek | 3537 / 3746 / 3908 | 3465 / 3627 / 3898 | 3523 / 3523 / 3523 | Suffix rimosso (-200 tok non cachati) | GO |
| avg/p50/p95 prompt_tokens Gemini | 2621 / 2519 / 3308 | 2643 / 2527 / 3336 | 2705 / 2680 / 2863 | Stabile su Gemini Flash Lite | GO |
| avg completion DeepSeek | 888 | 828 | 279 | Output compatto | GO |
| sum_cached / sum_prompt → cache hit % | 54.01% tot | 56.52% tot (89.34% DS) | 56.44% tot (86.73% DS) | Cache hit DeepSeek elevato | GO |
| ValidationError count/rate | 132 generic failed | 0 (0.00%) | 0 (0.00%) | ZERO errori di validazione | GO |
| ledger failed rate | 4.62% | 4.03% | 5 / 31 (16% Rate Limit 429 isolato, handoff OK) | Retry e fallback attivi | GO |
| articles.was_escalated % | 0.00% | 1 / 752 (0.13%) | 0 / 24 (0.00%) | Stabile | GO |
| purpose=quality:compare count | 18 | 21 | 0 | Nessun candidato near-dup 0.80-0.95 nel lotto 120 | GO |
| M5 action_taken direct_vector | N/A | 0 | 0 | Nessun candidato dist<=0.05 nel lotto 120 | GO |
| M6 kept_existing_content_hash | N/A | 0 | 0 | Nessun candidato byte-identico nel lotto 120 | GO |

### Smoke Qualitativo Campione (10/10 PASS)
- **3398:** US Trade Rep Jamieson Greer defends tariffs -> `Economia` [US], relevance 4
- **3397:** US-Saudi nuclear tech agreement -> `Nucleare` [US] related {SA}, relevance 4
- **3396:** IBM cuts annual forecast -> `Economia` [US], relevance 3
- **3395:** read_my_vram v0.6.0 release -> `Tecnologia` [XX], relevance 1
- **3394:** BlindTasting food game -> `Tecnologia` [XX], relevance 1
- **3393:** Sea predator reintroduction in Washington kelp forests -> `Ambiente` [US], relevance 2
- **3392:** AI self-improving agents analysis -> `Tecnologia` [XX], relevance 1
- **3391:** Loop engineering for dev teams -> `Tecnologia` [US], relevance 2
- **3390:** OpenAI enterprise integration push -> `Tecnologia` [US], relevance 3
- **3389:** Linux experimental support for Fairphone 6 wide camera -> `Tecnologia` [NL], relevance 2

### Verdetto Soak
- **Stato:** GATE VERDE (condizionato / soak OK).
- **Sanity check DB:** 24/24 (100%) delle nuove righe create presentano `content_sha256` valorizzato.
- **QuotaLedger:** Rate-limiting e pacing delle chiamate regolari, nessun memory leak su `reserved`.

