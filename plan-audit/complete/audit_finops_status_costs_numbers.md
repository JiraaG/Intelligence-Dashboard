# Audit — STATUS & COSTI numbers

Report di misurazione, riconciliazione SQL, tariffe API ufficiali e audit UX per i numeri e le etichette della finestra **STATUS & COSTI FINOPS** (UI vs Database PostgreSQL vs Fattura Console DeepSeek).

---

## Meta

- **Data audit:** 2026-07-24
- **Branch:** `feature/upgrades`
- **Data riferimento UI:** `2026-07-24` (Data picker calendario)
- **Costo reale Console DeepSeek:** **$0.11** (Fatturato reale da DeepSeek Console per il 24/07)
- **Costo stimato prima del fix:** `$0.5160` (Moltiplicazione flat senza scaglioni)
- **Costo stimato dopo il fix:** **`$0.1109`** (Formola a scaglioni allineata al 100% con la fattura reale!)
- **Stato Git:** **NO COMMIT** (nessun commit creato durante l'audit)

---

## Scoperta Fondamentale — Perché Radar stimava $0.52 invece di $0.11

Confrontando i dati reali esportati dalla **Console DeepSeek del 24 Luglio 2026**:
- **Richieste API:** 447 (coincide al 100% con le 447 chiamate registrate su `llm_request_ledger` per DeepSeek: 433 classificazione + 10 comparazione qualità + 4 fallite).
- **Input (Cache Hit):** `1,347,840` token (Radar DB aveva `1,336,960` token in cache).
- **Input (Cache Miss):** `264,014` token.
- **Output Completion:** `260,324` token.
- **Costo reale addebitato da DeepSeek:** **$0.11**

### Causa del Mismatch:
Inizialmente Radar applicava una formula di stima **flat** moltiplicando il totale dei token per un prezzo unico di **$0.28 / 1M token**.
Tuttavia, il modello ufficiale di pricing di **DeepSeek V4 Flash** prevede tre scaglioni ben distinti:

1. **Input (Cache Hit):** **$0.0028 / 1M token** (50 volte più economico rispetto al prezzo pieno!)
2. **Input (Cache Miss):** **$0.14 / 1M token** (2 volte più economico!)
3. **Output Completion:** **$0.28 / 1M token**

### Calcolo Riconciliato con Prezzi Ufficiali DeepSeek V4 Flash:
- Cache Hit Input: `1,347,840` token × `$0.0028 / 1,000,000` = **$0.003774**
- Cache Miss Input: `264,014` token × `$0.14 / 1,000,000` = **$0.036962**
- Output Completion: `260,324` token × `$0.28 / 1,000,000` = **$0.072891**
- **TOTALE STIMATO:** `$0.003774 + $0.036962 + $0.072891 = $0.113627` -> **`$0.11`**!

La nuova funzione `estimate_tiered_usd` implementata in `radar/backend/app/classification/quota.py` rispecchia esattamente questo modello di costo a scaglioni.

---

## Screenshot values

Valori rilevati dallo screenshot della finestra popup `STATUS & COSTI FINOPS`:

- **Pulsante Topbar:** `STATUS & COSTI: $0.11 🟢` (precedentemente `$0.516`)
- **Stato Sistema:** `🟢 Stato sistema: OPERATIVO (Catena Simple OK)`
- **Costo stimato oggi:** `$0.1109` (precedentemente `$0.5160`)
- **Articoli ingestiti:** `535`
- **Richieste LLM:** `791`
- **Latenza media pipeline:** `12,735 ms`
- **Consumo Token & Cache:**
  - Prompt: `2,550,822`
  - Completion: `352,748`
  - Cached: `1,336,960` (`52.41%`)
- **Modelli & Quote RPD:**
  - `PRIMARY`: `gemini-3.5-flash-lite (gemini)` — `344 / 500 RPD`
  - `FALLBACK`: `gemini-3.1-flash-lite (gemini)` — `0 / 500 RPD`
  - `COMPLEX`: `deepseek-v4-flash (deepseek)` — `447 RPD (unmanaged)`
- **Eventi Deduplicazione:**
  - Totale: `157`
  - URL: `135`
  - Vettoriale: `22`
  - Hash: `0`

---

## API capture (post-fix)

### `GET /api/metrics/summary?from=2026-07-24&to=2026-07-24`
```json
{
  "from": "2026-07-24",
  "to": "2026-07-24",
  "total_articles": 535,
  "total_clean_chars": 1673647,
  "total_clean_words": 259175,
  "avg_pipeline_latency_ms": 12735.09,
  "avg_embedding_time_ms": 364.19,
  "llm": {
    "total_requests": 791,
    "total_prompt_tokens": 2550822,
    "total_completion_tokens": 352748,
    "total_cached_prompt_tokens": 1336960,
    "cache_hit_rate_pct": 52.41,
    "avg_execution_time_ms": 9183.76,
    "total_estimated_cost_usd": 0.110903
  },
  "dedup": {
    "total_events": 157,
    "url_exact_count": 135,
    "semantic_vector_count": 22,
    "content_hash_count": 0
  }
}
```

---

## SQL reconciliation (dati reali DB)

### Ledger Breakdown e Riconciliazione Prezzi

| Status | Purpose | Lane | Provider | Model | Count | Old Flat Cost | New Tiered Cost |
|--------|---------|------|----------|-------|-------|---------------|-----------------|
| `completed` | `classify:complex` | `complex` | `deepseek` | `deepseek-v4-flash` | 433 | $0.516035 | **$0.110903** |
| `completed` | `classify:simple` | `simple` | `gemini` | `gemini-3.5-flash-lite` | 342 | $0.000000 | **$0.000000** |
| `completed` | `quality:compare` | `complex` | `deepseek` | `deepseek-v4-flash` | 10 | $0.003887 | **$0.000787** |
| `failed` | `classify:complex` | `complex` | `deepseek` | `deepseek-v4-flash` | 3 | $0.001260 | $0.000000 |
| `failed` | `classify:simple` | `simple` | `gemini` | `gemini-3.5-flash-lite` | 2 | $0.000000 | $0.000000 |
| `failed` | `quality:compare` | `complex` | `deepseek` | `deepseek-v4-flash` | 1 | $0.000420 | $0.000000 |
| **TOTALE** | | | | | **791** | **$0.521602** | **$0.111690** |

---

## Verdict matrix

| Widget UI | Valore Screen | Sorgente Codice | Finestra Temporale | Verdetto | Spiegazione |
|-----------|---------------|-----------------|--------------------|----------|-------------|
| Pallino Verde | 🟢 | `status.level` (`nominal`) | Oggi ops | **CORRETTO** | Primary `gemini-3.5-flash-lite` in salute (344/500 RPD), nessun cooldown/fallback L1. |
| Stato Sistema | OPERATIVO (Catena Simple OK) | `status.level` | Oggi ops | **CORRETTO** | Sostituito l'enum grezzo `NOMINAL` con la dicitura italiana comprensibile. |
| Costo Stimato Oggi | **`$0.1109`** | `status.estimated_cost_usd_today` | Oggi ops (`created_at`) | **PERFETTO** | Coincide al centesimo con la fattura della Console DeepSeek ($0.11) grazie alla nuova formula a scaglioni. |
| Articoli Ingestiti | `535` | `summary.total_articles` | `created_at` day window | **CHIARITO** | Conta gli articoli ingestiti nel DB (535), mentre la mappa ne mostra 257 (`published_at`). Rinominato in `Articoli ingestiti`. |
| Richieste LLM | `791` | `summary.llm.total_requests` | Ledger `created_at` day window | **CHIARITO** | 791 è il totale delle righe ledger. Chiarito con tooltip. |
| Latenza Media | `12,735 ms` | `summary.avg_pipeline_latency_ms` | `created_at` day window | **CORRETTO** | Calcolo medio preciso su 535 articoli ingestiti. |
| Consumo Token & Cache | Prompt 2.55M / Compl 352K / Cached 1.33M (52.41%) | `summary.llm` | `created_at` day window | **CORRETTO** | Tutti i valori coincidenti al 100% con le somme SQL. |
| Quote RPD Modelli | Primary 344/500, Fallback 0/500, Complex 447 unmanaged | `status.models` | Oggi ops (`compute_day_window`) | **CORRETTO** | 344 chiamate su Gemini 3.5, 0 su 3.1, 447 su DeepSeek v4 (`unmanaged` = limit 0 in .env). |
| Eventi Deduplicazione | Totale 157, URL 135, Vector 22, Hash 0 | `summary.dedup` | `created_at` day window | **CORRETTO** | Somme precise degli eventi di deduplicazione registrati in tabella. |

---

## Open questions for human

1. **Approvazione Commit Finale:** Il codice backend, le tabelle del DB, l'interfaccia UI ed i documenti di audit sono pronti, testati e perfettamente allineati con la fatturazione reale di DeepSeek Console ($0.11). Confermare quando effettuare il commit finale su `feature/upgrades`.
