# Agent prompt — FinOps Wave A: soak / requeue verify (costo + qualità)

> **Stato: DONE / soak OK** — eseguito 2026-07-22 (GATE VERDE condizionato confermato; M5/M6 osservazionali)  
> **SoT:** [`../../complete/plan_impl_llm_finops_token_caching.md`](../../complete/plan_impl_llm_finops_token_caching.md)  
> **Twin verifica:** [`../../complete/plan_impl_llm_finops_token_caching_verification.md`](../../complete/plan_impl_llm_finops_token_caching_verification.md) (§9 Soak)  
> **Branch:** `feature/upgrades`  
> **Scopo:** misurare delta costo vs ledger DB e validare qualità/procedure su un lotto controllato (articoli recenti / “oggi”), senza aprire M7.

---

## Come usare (orchestratore)

1. Nuova chat **Agent** su `feature/upgrades` (repo root).
2. Incolla il blocco **PROMPT** intero.
3. L’agente **non** implementa feature nuove: solo misura, requeue controllato, report go/no-go.
4. **`--purge-all` vietato** salvo conferma esplicita dell’utente in chat.

---

## PROMPT (incolla in Agent mode)

```text
# Task — VERIFY / SOAK: FinOps Wave A (costo ledger + qualità post-deploy)

## Ruolo
Sei ops/verify engineer sul Radar. Wave A (M1–M6) è già shipped con GATE VERDE **condizionato**. Il tuo compito è un **test controllato** su articoli recenti (“oggi” / ultime ~24h di ingest) per:
1) quantificare il **delta costo/token** rispetto ai dati già in DB (`llm_request_ledger`);
2) verificare che **qualità articoli e procedure** (classify → embed → dedup → commit → metrics) siano in ordine;
3) annotare M5/M6 se compaiono (o perché restano 0).

NON implementare M7/M8. NON refactor. Fix codice solo se trovi un bug bloccante evidente (e segnalalo prima).

## Autorità
1. Twin: `plan-audit/complete/plan_impl_llm_finops_token_caching_verification.md` (§2 SQL, §4 live, §5 go/no-go)
2. Piano: `plan-audit/complete/plan_impl_llm_finops_token_caching.md`
3. Skill `radar-requeue-ops` + `radar-docker-ops` + `radar-quota-ledger`
4. Runbook: `radar/docs/runbook.md`
5. Questo prompt (override su “rielabora tutto a caso”)

## Decisioni chiuse (NON violare)
- SEMPRE dry-run prima di qualsiasi `requeue_articles` in write
- NO `--purge-all` senza conferma esplicita utente in questa chat
- N requeue consigliato: **80–150** (ultime entry Miniflux read → unread). Se volume “oggi” è minore, usa quel N e documenta
- Requeue di URL già in DB **cancella** le righe articles correlate e riprocessa: è distruttivo su vault/cooldown — ok solo dopo dry-run OK
- M5/M6 a 0 eventi ≠ fail automatico (annotare “no near-dup / no hash twin nel lotto”)
- Token unknown → NULL, non inventare 0
- NO tocchi `radar-sidebar/**`; NO commit `.env`/secrets; NO commit git senza richiesta utente
- Stack deve essere healthy (`docker compose ps`) prima del write

## Contesto da leggere PRIMA
- `plan-audit/STATUS.md` (FinOps = COMPLETE condizionato)
- Twin verifica (baseline già compilata §2.2 — riusala come confronto)
- `.agents/skills/radar-requeue-ops/SKILL.md`
- `.agents/skills/radar-docker-ops/SKILL.md`
- Endpoint metrics: GET `/api/metrics/summary` (campo `cache_hit_rate_pct`)

## Procedura obbligatoria (ordine)

### A — Snapshot PRE (readonly)
1. Conferma stack healthy (api + worker + db).
2. Esegui SQL twin §2.1 su due finestre e salva output:
   - Baseline storica: ultimi **7 giorni** (o riusa numeri twin §2.2 se ancora validi)
   - Finestra “oggi” / ultime **24h** pre-requeue: prompt/completion/cached per provider+purpose; fail/ValidationError; escalate %; dedup `action_taken`
3. GET `/api/metrics/summary` → annota `cache_hit_rate_pct` (+ eventuali contatori content_hash se esposti).
4. Conta articoli creati nelle ultime 24h e ledger completed nelle ultime 24h.

### B — Requeue controllato
1. `cd radar`
2. Dry-run:
   `docker compose exec -T radar-worker python -m app.scripts.requeue_articles 120 --dry-run`
3. Se anteprima OK (N ragionevole, URL sensati), write **senza** purge-all:
   `docker compose exec -T radar-worker python -m app.scripts.requeue_articles 120`
4. `docker compose restart radar-worker`
5. Monitora log worker fino a lavorazione sostanziale del lotto (route SIMPLE/COMPLEX, errori Miniflux 403 = WARN non-bloccante se residuali). Timeout atteso: decine di minuti — non abortire prematuramente.

### C — Snapshot POST + delta costo
Riesegui le stesse query §2.1 sulla finestra **post-requeue** (dal timestamp cutover di questo test) e compila tabella:

| Metrica | PRE (7d o twin) | PRE 24h | POST lotto | Delta | Go? |
|---|---|---|---|---|---|
| n completed classify (DeepSeek / Gemini / Gemma) | | | | | |
| avg/p50/p95 prompt_tokens classify DeepSeek | | | | | |
| avg completion DeepSeek | | | | | |
| sum_cached / sum_prompt → cache hit % (DS complex) | | | | | |
| ValidationError count/rate | | | | | |
| ledger failed rate | | | | | |
| was_escalated % | | | | | |
| purpose=quality:compare count | | | | | |
| M5 action_taken direct_vector (kept/replaced) | | | | | |
| M6 kept_existing_content_hash | | | | | |
| metrics cache_hit_rate_pct | | | | | |

Criteri twin §5 (tolleranze): ValidationError non peggiora vs baseline; prompt DeepSeek non regredisce materialmente; replace ancora vivo (direct **o** quality:compare).

### D — Qualità articoli (smoke umano su campione)
Campiona **≥10** articoli processati nel lotto (mix keep/new/replace se disponibili):
- summary italiano coerente, non troncato assurdo
- country ISO / related_countries plausibili
- tipologia / sentiment non junk
- marker read/saved invariati dove applicabile
- se c’è replace: titolo/body aggiornati, no doppio vault sporco ovvio

Documenta 10/10 PASS o elenca FAIL con article_id.

### E — Procedure / pipeline sanity
Verifica da log+DB che il flusso atteso tenga:
- QuotaLedger reserve/complete (no leak “reserved” eterni sul lotto)
- embed + dedup events coerenti
- `content_sha256` popolato sulle nuove/aggiornate rows
- nessun spike ValidationError → correction loop infinito
- Miniflux scrape WARN isolati non bloccano il lotto

### F — Deliverable (obbligo)
1. Aggiorna twin `plan-audit/complete/plan_impl_llm_finops_token_caching_verification.md` con sezione **“Soak / requeue YYYY-MM-DD”** (tabella delta + smoke + nota M5/M6).
2. Se esito conferma condizionato → lascia GATE VERDE (condizionato) e annota “soak OK”.
3. Se regressione → STOP, propone ROLLBACK mirato (M3 suffix / disable M5 / disable M6) senza implementare rollback finché l’utente non conferma.
4. Report finale in chat: verdetto GO/HOLD/NO-GO, N processati, delta token/cache principali, ValidationError, eventi M5/M6, 10 smoke, rischi residui.
5. **Non** aggiornare STATUS a “incondizionato” solo perché il soak è OK se M5/M6 restano 0 — resta “condizionato / osservazionale su M5-M6” finché non ci sono eventi naturali o un test dedicato near-dup.

## Anti-pattern
- Purge-all “per essere sicuri”
- Confrontare costi mescolando purpose diversi senza split provider+purpose
- Dichiarare M5/M6 rotti solo perché count=0
- Aspettarsi risparmio enorme su prompt: M3 è modest (~200 tok); il grosso è cache hit + meno compare (M5)
- Commit non richiesto / push / tocco .env secrets in chat

## Done quando
Tabella delta compilata, smoke ≥10, twin aggiornato con sezione soak, verdetto esplicito GO/HOLD/NO-GO all’utente.
```
