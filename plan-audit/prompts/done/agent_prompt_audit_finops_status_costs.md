# Agent prompt — Audit numeri STATUS & COSTI FinOps (UI vs DB)

> **Stato: ACTIVE** — audit/verifica + eventuale fix etichette/contratto metriche (2026-07-24).  
> **NO COMMIT** salvo richiesta esplicita dell’utente.  
> **Screenshot di riferimento:** allegato dall’utente in chat (`STATUS & COSTI: $0.516`, banner NOMINAL, 535 articoli, 791 richieste LLM, token/cache, RPD modelli, dedup).  
> **SoT feature:** [`../../active/plan_impl_finops_ui_metrics.md`](../../active/plan_impl_finops_ui_metrics.md)  
> **Walkthrough:** [`../../active/walkthrough_finops_ui_metrics.md`](../../active/walkthrough_finops_ui_metrics.md)

---

## Come usare

1. Chat **Agent** su `feature/upgrades`.
2. Incolla il **PROMPT** sotto e **allega lo screenshot** della finestra STATUS & COSTI.
3. Prima **misura e spiega** (SQL vs UI); poi proponi/applica fix etichette e coerenza date se confermati dal check.
4. Scrivi report in `plan-audit/active/audit_finops_status_costs_numbers.md`.
5. **Nessun commit.**

---

## Contesto rapido (ipotesi da verificare — non assumere vere)

Sospetti già emersi in review umana (da confermare con SQL live):

1. **"Articoli analizzati" = 535** vs toolbar giorno **~257** → possibile mismatch `articles.created_at` (metrics) vs `published_at` (map-summary / day view).
2. **"Richieste LLM" = 791** > articoli → ledger conta **tutti** gli status/purpose (retry, escalate, quality:compare?), non 1:1 con articoli.
3. **"Costo stimato oggi" = $0.516** → somma `estimated_cost_usd` classify completed (Gemini free ≈ $0 + **DeepSeek paid**); non è “solo DeepSeek” ma può essere **dominato** da COMPLEX.
4. Label UI dice sempre **"oggi"** ma `metricsSummary` è bindato a `filters().date` (calendario), mentre `metricsStatus` RPD è sempre day-window `RADAR_TIME_ZONE` “oggi ops”.
5. **"NOMINAL"** poco esplicativo (verde ok) → serve label IT human-readable.

---

## PROMPT (incolla in Agent mode)

```text
# Task — AUDIT COMPLETO numeri finestra STATUS & COSTI (+ fix etichette se confermati)

## Ruolo
FinOps / backend+FE Radar. Verifica che i numeri nello screenshot STATUS & COSTI siano corretti rispetto al DB e al contratto API. Spiega ogni discrepanza. Poi migliora etichette UX (NOMINAL → testo chiaro IT; chiarire finestra temporale e cosa include il costo). NO git commit.

## Input
- Screenshot utente allegato (valori tipici: $0.516, NOMINAL, 535 articoli, 791 LLM req, prompt/completion/cached, RPD 344/500 · 0/500 · 447 unmanaged, dedup 157/135/22/0).
- Codice: `radar/backend/app/main.py` (`/api/metrics/summary`, `/api/metrics/status`)
- FE: `state.service.ts` (metricsSummaryResource params = filters.date; metricsStatusResource ignora date)
- FE: `radar-toolbar.component.html` (label "Costo stimato oggi", "Articoli analizzati", "Stato sistema: NOMINAL")
- Stack Docker già up preferibilmente (`radar/`)

## Autorità
1. Spiegazione onesta DB ↔ API ↔ UI (questo audit)
2. SoT `plan-audit/active/plan_impl_finops_ui_metrics.md` per intent FinOps
3. Skills api-contract / freeze (freeze: non toccare sidebar in questo task salvo necessità zero)

## VIETATO
- git commit / push
- docker compose restart sull’intero stack
- --purge-all / requeue distruttivo
- Cambiare formule di pricing provider inventate; usare `estimated_cost_usd` già in ledger + env `*_USD_PER_1M_TOKENS`

---

## Parte A — Misura live (obbligatoria)

Working dir: `radar/`

### A1. Cattura API (stessa data dello screenshot / calendario UI)
```bash
DATE=2026-07-24   # o la data nel date picker UI
docker compose exec radar-backend curl -s "http://localhost:8000/api/metrics/summary?from=${DATE}&to=${DATE}" | tee /tmp/metrics_summary.json
docker compose exec radar-backend curl -s "http://localhost:8000/api/metrics/status" | tee /tmp/metrics_status.json
docker compose exec radar-backend curl -s "http://localhost:8000/api/map-summary?date=${DATE}" | tee /tmp/map_summary.json
```
Calcola dalla map-summary la somma `article_count` (o equivalente) = “articoli del giorno” visti in mappa.

### A2. SQL di riconciliazione (dentro radar-backend o radar-db)
Esegui query (adatta TZ da `RADAR_TIME_ZONE` / day window di `compute_day_window`) e riporta i risultati nel report:

1. **Articoli per created_at** nel day window (deve ≈ summary.total_articles)
2. **Articoli per published_at = DATE** (deve ≈ somma map-summary / 257 UI)
3. **Ledger COUNT(*)** nel day window (≈ 791?) breakdown per `status`, `purpose`, `lane`, `provider`, `model`
4. **Ledger SUM(estimated_cost_usd)** completed classify-only (≈ $0.516?) **split per provider/model**
5. **Token SUM** prompt/completion/cached (e cache_hit = cached/prompt) vs UI
6. **RPD per model** (stessa SQL di `get_model_rpd_used` / status) vs barre UI 344/500, 0/500, 447 unmanaged
7. **Dedup events** count per dedup_kind vs 157/135/22/0

Template SQL (adatta binding date):
```sql
-- A. articles by created_at day window
SELECT COUNT(*) FROM articles WHERE created_at >= $start AND created_at < $end;

-- B. articles by published_at calendar day
SELECT COUNT(*) FROM articles WHERE published_at = DATE '2026-07-24';

-- C. ledger breakdown
SELECT status, purpose, lane, provider, model, COUNT(*),
       COALESCE(SUM(estimated_cost_usd),0) AS cost,
       COALESCE(SUM(prompt_tokens),0) AS prompt,
       COALESCE(SUM(completion_tokens),0) AS completion,
       COALESCE(SUM(cached_prompt_tokens),0) AS cached
FROM llm_request_ledger
WHERE created_at >= $start AND created_at < $end
GROUP BY 1,2,3,4,5
ORDER BY COUNT(*) DESC;

-- D. cost classify-only completed
SELECT provider, model,
       SUM(estimated_cost_usd) AS cost,
       COUNT(*) AS n
FROM llm_request_ledger
WHERE created_at >= $start AND created_at < $end
  AND status = 'completed'
  AND (purpose LIKE 'classify:%' OR purpose = 'classify_article')
GROUP BY 1,2;

-- E. dedup
SELECT dedup_kind, COUNT(*) FROM article_dedup_events
WHERE created_at >= $start AND created_at < $end
GROUP BY 1;
```

### A3. Env pricing (senza stampare secret)
Riporta solo i **rate** (non API keys):
`LLM_SIMPLE_USD_PER_1M_TOKENS`, `LLM_COMPLEX_USD_PER_1M_TOKENS` (o legacy DeepSeek).
Spiega perché $0.52 può essere plausibile (es. quasi tutto DeepSeek) o gonfiato.

### A4. Tabella verdetto per ogni widget UI
Per ciascuno: **CORRETTO / FUORVIANTE / BUG** + motivo

| Widget UI | Valore screen | Sorgente codice | Finestra temporale | Verdetto |
|-----------|---------------|-----------------|--------------------|----------|
| Pallino verde | 🟢 | status.level | oggi ops | |
| Stato sistema NOMINAL | … | status.level | oggi ops | |
| Costo stimato oggi $0.516 | … | status preferito / summary | ? | |
| Articoli analizzati 535 | … | summary.total_articles | created_at day | |
| Richieste LLM 791 | … | summary.llm.total_requests | ledger ALL status? | |
| Latenza media pipeline | … | avg pipeline | created_at | |
| Token prompt/compl/cached/% | … | summary.llm | ledger ALL? | |
| RPD primary/fallback/complex | … | status.models | oggi ops RPD | |
| Dedup totale/url/vett/hash | … | summary.dedup | created_at day | |

---

## Parte B — Risposte obbligatorie nel report

1. I dati “quadrano”? Perché 535 ≠ 257 e 791 ≠ 535?
2. Il costo include Gemini+DeepSeek o solo uno? Quanto pesa ciascuno?
3. Summary è “giorno calendario UI” o “oggi”? Status RPD è allineato?
4. Cache hit % formula (cached/prompt) è corretta semanticamente?
5. Complex “447 RPD (unmanaged)” con rpd_limit=0: corretto?
6. Conviene ancora fare i residui review (test_metrics_status, MOCK check)? Sì/No + priorità.

---

## Parte C — Fix UX/contratto (applica se Parte A conferma i mismatch)

Solo dopo evidenza SQL. Scope minimo:

### C1. Etichette IT più chiare (toolbar popover)
Sostituisci `NOMINAL` / `FALLBACK_OR_ESCALATION` / `DEGRADED` con label umane, es.:
- nominal → **Operativo** (sottotitolo: “Catena Simple primaria OK”)
- fallback_or_escalation → **Degradato leggero** / **Fallback attivo** (motivo da `l1_reason`)
- degraded → **Risorse limitate** / **Worker non pronto**
Mantieni pallino 🟢🟡🔴 invariato (verde corretto per nominal).

### C2. Chiarire finestra temporale nelle label
- Non scrivere “oggi” se il numero viene da `filters().date`.
- Esempi: `Costo giorno (calendario)`, `Articoli ingestiti (created_at)`, oppure allineare summary a `published_at` se product decide che deve matchare la mappa — **decisione vincolante sotto**.

### C3. Decisione prodotto (scegli e implementa UNA, documenta)
**Scelta default per questo audit (se SQL conferma mismatch created_at vs published_at):**
- Tieni metrics su `created_at` (FinOps ingest-day) MA:
  - rinomina “Articoli analizzati” → **Articoli ingestiti nel giorno**
  - aggiungi seconda metrica opzionale **Pubblicati (mappa)** = count `published_at` (stessa DATE) OPPURE nota in UI “≠ conteggio mappa (published_at)”
- Per “Richieste LLM”: o filtra `status='completed'` + purpose classify (allinea al costo), o etichetta **Tentativi ledger (tutti gli status)**.

Default consigliato implementare:
1. Label status IT (C1)
2. Label costo/articoli/richieste più oneste (C2/C3)
3. `total_requests` in summary per il popover: preferisci count completed classify (nuovo campo `llm.total_classify_completed` o riusa filtro) così 791 non confonde — **oppure** solo relabel senza cambiare API se vuoi rischio zero.

Non cambiare barre RPD se SQL le conferma.

### C4. Docs
Aggiorna `docs/02` / skill api-contract in 2–3 frasi: created_at vs published_at; cost = classify completed all providers; requests count semantics.

---

## Parte D — Deliverable

Crea/sovrascrivi:
`plan-audit/active/audit_finops_status_costs_numbers.md`

Heading obbligatori:
1. `# Audit — STATUS & COSTI numbers`
2. `## Meta`
3. `## Screenshot values`
4. `## API capture`
5. `## SQL reconciliation` (tabelle risultati)
6. `## Verdict matrix` (widget → CORRETTO/FUORVIANTE/BUG)
7. `## Cost split by provider`
8. `## UX / label recommendations applied` (cosa hai cambiato / cosa no)
9. `## Residuals worth doing?`
10. `## Open questions for human`

In chat finale: path report + 5 bullet (535 vs 257, 791, $0.52 split, label NOMINAL, fix applicati sì/no).
Conferma: **nessun commit**.
```

---

## Nota per l’umano (prima di lanciare)

**Riserve residue (test status / MOCK):** utili ma **basse priorità** rispetto a questo audit: i numeri/etichette fuorvianti sono il problema reale percepito. Fai prima questo check; i unit test status aggiungili al commit se vuoi hardening.

**Verde NOMINAL:** corretto come colore se primary sano; cambia solo il **testo**.
