# Plan prompt — Fase A: LLM locale AMD (ROCm/Ollama) + lane SIMPLE/COMPLEX

> **Stato: COMPLETE (analisi 2026-07-19; impl Profilo F `54c8038` + VRAM unload shipped)** — prompt storico.  
> **Uso:** non rieseguire come ACTIVE; delta residuo opz. = scorecard fixture qualità.  
> **Shipped:** host-Ollama Profilo F; tag ops `gemma4-radar` (FROM `gemma4:12b`, `num_ctx=8192`); `think=true`; **no SIMPLE→DeepSeek escalate**; `normalize_llm_json_dict`; overlay `docker-compose.ollama-host.yml`; **VRAM** `ollama_lifecycle` + `OLLAMA_*` + `ops/verify-ollama-vram.sh`.  
> **Piano vivo:** [`../../active/plan_impl_fase_A_local_amd_ollama.md`](../../active/plan_impl_fase_A_local_amd_ollama.md) (residuo opz. scorecard).  
> **Blueprint:** [`radar_overview_and_upgrades.md`](../../../radar_overview_and_upgrades.md) §3.A.  
> **Nota roadmap:** Fase B/H DONE; Fase C BACKLOG. Restore code: `54c8038` (Profilo F); map anchors `a240b3c`.  
> **Contesto host empirico (2026-07-18/19):** GPU AMD Navi 22 (RX 6700/6750 XT class), ROCm rock 6.10.5 caricato, `/dev/kfd`+`/dev/dri` presenti, host Ollama `0.30.7` con modelli già pullati (`gemma4:12b`, `gemma4:26b`, `qwen3:14b`, `qwen2.5:14b`, …). RAM ~30 GiB.  
> **Ops LLM attuale:** Profilo B DeepSeek-only tipico in `.env.example`; lane env `openai` = OpenAI-compat httpx (adatto a Ollama `/v1`). Package `openai` **vietato**.

---

## PROMPT (incolla in Plan mode)

```text
Ruolo: analyst + architect pipeline LLM Radar Informativo Globale — Fase A (inferenza locale AMD GPU + integrazione lane).

Obiettivo
Produrre un’ANALISI RIGOROSA e un PIANO ESEGUIBILE (piano only — NESSUN codice finché non richiesto) per abilitare l’elaborazione LLM **locale a costo zero** su hardware AMD (Radeon RX 6750 XT / Navi 22, 12 GB VRAM) via Ollama+ROCm, integrata nelle lane `LLM_SIMPLE_*` / `LLM_COMPLEX_*` già esistenti, senza rompere cloud hybrid / Profili A–E.

Ambito prodotto (Fase A overview §3.A)
1) Servizio `radar-ollama` (o host Ollama) su rete `radar-data`, GPU passthrough `/dev/kfd`+`/dev/dri`, target `gfx1030`.
2) Scelta modello(i) locale(i) realistiche per 12 GB VRAM (blueprint cita Gemma 4 14B Q4 — **VERIFICARE** tag Ollama reali vs host: oggi esistono `gemma4:12b` ~7.6 GB, `gemma4:26b` ~17 GB troppo grande per full-GPU, `qwen3:14b` / `qwen2.5:14b` ~9 GB, ecc.).
3) Quattro topologie di routing (documentare trade-off e raccomandazione unica vincolante):
   - Scenario 1 Full Local (SIMPLE=COMPLEX=locale)
   - Scenario 2 Local SIMPLE + Cloud COMPLEX (consigliato overview)
   - Scenario 3 Cloud SIMPLE + Local COMPLEX
   - Scenario 4 Dual local (due modelli) — VRAM risk / offload CPU
4) Wiring env: `PROVIDER=openai` + `BASE_URL=http://radar-ollama:11434/v1` (o host gateway), `API_KEY` dummy, RPM/TPM/RPD=0, timeout lunghi, `REASONING_EFFORT` none vs high dove sensato.
5) Qualità JSON strict Radar: schema Pydantic, no CoT, CSV `related_countries`, anti-XX / categorie (restore `f7cf83d`) — misurare se il locale regge lo stesso contratto di DeepSeek/Gemini.
6) Ops: pull modello, health, smoke classify, fallback se Ollama down, impatto quota ledger / soft-trim, docs `.env.example` Profilo “Local-*”.

────────────────────────────────────────
Contesto obbligatorio da leggere PRIMA di pianificare
────────────────────────────────────────
Blueprint / SoT
- radar_overview_and_upgrades.md §3.A (intero blocco AMD/Ollama + scenari 1–4) e §1–2 AS-IS pipeline
- plan-audit/complete/sot_llm_multi_model_fallback.md (§0 limiti lane; provider `openai` dialect stock; Profili A–E; VIETATO package openai)
- plan-audit/STATUS.md (B/H DONE; C pgvector BACKLOG; restore tip `a240b3c`; Fase A ACTIVE)
- radar/.env.example (lane knobs, commenti Profilo A/B/C/D/E)
- skill .agents/skills/llm-json-extraction/SKILL.md (+ mirror radar/.ecc/skills/)
- skill .agents/skills/radar-quota-ledger/SKILL.md (RPM/TPM wait vs RPD cross-lane; soft-trim = SIMPLE.rpd)
- skill .agents/skills/radar-docker-ops/SKILL.md (reti edge/data, no latest, health)

Codice lane / client
- radar/backend/app/core/llm_lanes.py (OPENAI_COMPAT_PROVIDERS, BASE_URL defaults, dialect)
- radar/backend/app/core/config.py (load lane env)
- radar/backend/app/classification/deepseek.py (httpx OpenAI-compat stock vs thinking)
- radar/backend/app/classification/client.py (routing complexity, residual, cooldown)
- radar/backend/app/classification/complexity.py (v2.2 quorum — impatto volume SIMPLE vs COMPLEX)
- radar/backend/app/classification/prompts.py + validator.py (contratto JSON post-f7cf83d)
- radar/docker-compose.yml (dove inserire radar-ollama; reti; devices)
- overlay esistenti: radar/docker-compose.gemma-simple.yml / gemini-simple.yml (pattern overlay, non confondere con Ollama)

Evidenza host (usare come case study; verificare al momento del piano)
- GPU: AMD Navi 22 (RX 6700/6750 XT family), ROCm module loaded, /dev/kfd + /dev/dri/renderD128
- Ollama host già installato (0.30.7) con modelli pullati: gemma4:12b, gemma4:26b, qwen3:14b, qwen2.5:14b, mistral-small:22b, phi4:14b, qwen3.5:9b, nomic-embed-text, …
- RAM host ~30 GiB (offload possibile ma lento — Scenario 4 rischioso)
- Stack Radar Compose attuale: worker tipicamente cloud (Profilo B); Miniflux feed count spesso basso (volume mappa ≠ LLM)

Vincoli NON negoziabili
- Nessun package `openai` Python; solo httpx OpenAI-compat già nel client
- Schema Pydantic strict CSV str; no campo reasoning / no CoT nel system prompt
- Ingest solo in radar-worker; main.py API-only
- Reti: ollama su radar-data (non edge); FE non vede Ollama
- Sidebar freeze: non toccare radar-sidebar/**
- Non inventare provider nuovi se `PROVIDER=openai` + BASE_URL basta
- Non mescolare implementazione Fase C pgvector / Fase D air-gap mappe in questo piano (citare solo se dipende)
- Preferire overlay compose (`docker-compose.ollama.yml`) piuttosto che gonfiare il compose base se il piano lo giustifica
- Documentare VERIFY-ON-HOST: ROCm image tag pinnato (no `latest`), gfx1030, VRAM budget

────────────────────────────────────────
Domande di analisi obbligatorie (rispondi tutte)
────────────────────────────────────────

### A — Hardware & runtime locale
A1. Conferma AS-IS host: GPU, ROCm, device nodes, Ollama version, modelli pullati e footprint VRAM stimato.
A2. Container vs host-Ollama: trade-off (ROCm image ollama/ollama:rocm vs bind host network). Raccomandazione unica.
A3. Tag immagine/digest strategy (no latest); env HCC_AMDGPU_TARGET=gfx1030; OLLAMA_NUM_PARALLEL vs VRAM.
A4. Cosa succede se GPU assente / ROCm rotto: fail-soft verso cloud lane? hard-fail worker?

### B — Modelli e qualità schema Radar
B1. Shortlist modelli ≤12 GB VRAM adatti a JSON strict IT (confronta blueprint “Gemma 4 14B” vs tag reali gemma4:12b / qwen3:14b / …).
B2. gemma4:26b e mistral-small:22b: solo se offload accettabile? Escludere da default.
B3. Come validare qualità: smoke classify su 10 fixture (politica, soft-news, multilaterale, paper) — assert primary_category/country_code/related senza CoT.
B4. Timeout / concurrency worker (GEMINI/LLM concurrency) vs token/s locali tipici ROCm.

### C — Integrazione lane & scenari
C1. Mappa scenari 1–4 → blocchi `.env` concreti con PROVIDER=openai + BASE_URL + effort.
C2. Decisione vincolante: quale scenario è default ops su QUESTA macchina (motiva con VRAM, qualità, costo cloud residuo).
C3. Residual cross-lane: se locale down e SIMPLE=locale, COMPLEX=cloud (o viceversa) — comportamento atteso vs codice attuale.
C4. QuotaLedger: RPM/RPD=0 su locale; soft-trim SIMPLE; impatto ibernazione ciclo.
C5. Serve nuovo Profilo F “Local-Hybrid” in `.env.example` + SoT? (sì/no + bozza).

### D — Compose / rete / sicurezza
D1. File target: overlay compose vs edit base; volume `./data/ollama`; restart policy.
D2. Reachability worker→ollama DNS `radar-ollama:11434`; mai esporre 11434 su host pubblico di default.
D3. Healthcheck Ollama; depends_on worker?
D4. Interazione con overlay gemma-simple / gemini-simple esistenti (naming, non conflitto).

### E — Docs / ECC / gate
E1. File docs da aggiornare (01, 02, ops README, sot_llm, overview §3.A se stale).
E2. Skill da sync (llm-json-extraction nota BASE_URL ollama; docker-ops).
E3. Fuori scope esplicito (pgvector embeddings nomic-embed-text già presente host — non Fase A).
E4. Rischi: VRAM OOM, CPU offload, JSON invalid → correction/escalate cloud, latenza batch 48h.

────────────────────────────────────────
Output del Plan (formato obbligatorio)
────────────────────────────────────────
1. Verdetto AS-IS (host GPU/Ollama + lane cloud attuali) — cosa già basta / cosa manca
2. Matrice problemi P0/P1/P2 (VRAM, modello, compose, qualità JSON, ops)
3. Decisioni vincolanti: container vs host; modello SIMPLE; modello COMPLEX; scenario default
4. Piano a wave (es. W1 overlay+env smoke; W2 qualità fixture; W3 docs/ECC/SoT Profilo Local)
5. File target precisi + gate misurabili (es. classify 10/10 schema-valid; p50 latency; VRAM <11 GB)
6. Fuori scope esplicito
7. Rischi e rollback (tornare Profilo B cloud-only)

Regole di esecuzione di QUESTO piano
- Nessun codice in questa chat Plan
- Nessun commit/push
- Non inventare endpoint/provider non presenti
- Preferisci env+overlay rispetto a refactor client
- Se proponi cambio codice client, motiva perché BASE_URL openai-compat non basta
- Verifica con WebSearch/fetch tag Ollama/ROCm aggiornati se il blueprint overview è stale (Gemma 4 14B naming)
```

---

## Note operative post-analisi

Dopo il piano approvato, implementazione tipica (altra chat Agent):
1. Overlay `docker-compose.ollama.yml` (+ eventuale Profilo Local in `.env.example`)
2. Smoke: `docker compose … up`, `ollama pull`, classify fixture via worker
3. Misurare VRAM (`rocm-smi` / `ollama ps`) e tasso ValidationError
4. Docs + SoT sync; aggiornare `plan-audit/STATUS.md`
5. Non toccare Fase C pgvector anche se `nomic-embed-text` è già in Ollama

### Comandi utili pre-piano (host)
```bash
lspci | grep -i VGA
rocminfo | head
ls /dev/kfd /dev/dri
ollama --version && ollama list
cd radar && docker compose ps
```
