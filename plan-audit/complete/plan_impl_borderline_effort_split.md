# Piano impl — BORDERLINE effort split (DeepSeek none → escalate high)

> **Stato: COMPLETE / GATE VERDE 2026-07-22**  
> **Branch:** `feature/upgrades`  
> **Prompt Agent:** [`../prompts/done/agent_prompt_borderline_effort_split.md`](../prompts/done/agent_prompt_borderline_effort_split.md) — include review **R1–R12** + GATE requeue (override su Implementation Plan orchestratore)  
> **Analisi origine:** [`../prompts/done/plan_prompt_borderline_cost_routing.md`](../prompts/done/plan_prompt_borderline_cost_routing.md)  
> **SoT correlato:** [`../complete/sot_llm_multi_model_fallback.md`](../complete/sot_llm_multi_model_fallback.md) §4 (aggiornare post-ship)  
> **Prerequisito:** Metrics 013 + per-model quota GATE VERDE; Profilo A ops

---

## 1. Obiettivo prodotto

Ridurre i **thinking token** DeepSeek sul volume **BORDERLINE** (~28% articoli, quasi tutti famiglia **G** multi-country) senza:

- spostare BORDERLINE su Gemini free (RPD già saturo; XX peggiore);
- introdurre una 4ª fascia heuristic;
- cambiare schema Pydantic / prompt di classificazione.

**TO-BE ops (target confermato):**

| Caso | Provider/model | Effort |
|------|----------------|--------|
| Classify SIMPLE | Gemini Flash Lite | n/a (path Gemini) |
| Classify **BORDERLINE** | DeepSeek `v4-flash` (catena COMPLEX) | **`none`**, escalate → **`high`** su ValidationError |
| Classify **COMPLEX** | DeepSeek `v4-flash` | **`high`** (invariato) |
| `quality:compare` | DeepSeek (lane COMPLEX) | **`none`** (già oggi) |

**Non sono 3 model ID:** 2 modelli (Gemini + DeepSeek), 3 config classify.  
Su dialect DeepSeek le uniche leve effort reali sono `none` | `high` | `max` (`low`/`medium` → rimappati a `high` in `openai_compat_payload.py`).

---

## 2. Contesto AS-IS (non reinterpretare)

### 2.1 Heuristic vs lane di esecuzione

| Concetto | Valore BORDERLINE oggi |
|----------|------------------------|
| `Lane` heuristic | `BORDERLINE` (log `classify lane=BORDERLINE`) |
| Quota / denorm | `complex` — `articles.classification_lane='complex'` |
| Ledger | `purpose=classify:complex`, `lane=complex` |
| Effort classify | `LLM_COMPLEX_REASONING_EFFORT` (tipico `high`) |

**BORDERLINE non è denormalizzato** come stringa distinta su `articles`. Misura: log pre-call oppure recompute `score_complexity(title, body_excerpt)`.

### 2.2 Perché escalate none→high funziona già a livello identity

`_ModelRef.identity = (provider, model, reasoning_effort)`.  
Oggi escalate BORDERLINE → primary COMPLEX spesso **no-op** (stesso effort `high`).  
Con BL `none` e escalate_ref `high`, identity **diversa** → escalate reale.

### 2.3 Evidenza live (analisi 2026-07-22)

- Mix heuristic ~**60% SIMPLE / 28% BORDERLINE / 12% COMPLEX** → provider AS-IS ~60% Gemini / 40% DeepSeek.
- BL: ~**93% `multi_country`**, resto `geo_marker`; famiglie quasi sempre solo **G**.
- XX heur BL su DeepSeek high ≈ **1%**; SIMPLE Gemini ≈ **27%**.
- `classify:complex` high live: p50 completion ~**818**, p50 cost ~**$0.00125** @ $0.28/1M — **non** la banda “40k /$0.011” delle stime generiche.
- Gemini RPD: 3.1 spesso a tetto 500; move BL→Gemini = residual DeepSeek, risparmio illusorio.
- 4ª fascia (solo `geo_marker`→cheap): Δ mix ~**2pp** → inutile.

---

## 3. Design chiuso

### 3.1 Knob env (preferito a hardcode)

```bash
# Effort SOLO per heuristic BORDERLINE sulla catena COMPLEX (stesso provider/model).
# Default codice se unset = high (AS-IS, zero regressione al boot).
# Target ops post dual-run = none
LLM_BORDERLINE_REASONING_EFFORT=none   # none | high | max
```

Regole:

- Valori ammessi: `none` | `high` | `max` (+ alias `off`/`disabled` → `none`).
- `low`/`medium`: **reject o remap documentato a `high`** (coerente payload DeepSeek) — preferire **fail-fast warn + coerce to high** come payload, oppure documentare ignore.
- Unset / vuoto → **`high`** (backward compatible).
- **Non** introduce `LLM_BORDERLINE_PROVIDER/MODEL` in questa fase (stesso identity COMPLEX salvo effort).
- **Non** cambia `purpose`/`quota_lane`: resta `classify:complex` / `complex`.

### 3.2 Routing (`client._chain_for`)

```text
SIMPLE     → _simple_chain()           # invariato
COMPLEX    → _complex_chain()          # effort = LLM_COMPLEX_REASONING_EFFORT
BORDERLINE → refs COMPLEX provider/model con effort = LLM_BORDERLINE_REASONING_EFFORT
```

Shadow / `mode=off` / COMPLEX unavailable: invariati (force SIMPLE).

### 3.3 Escalate BORDERLINE

1. Primo percorso: BL ref con effort da knob (`none` in target ops).
2. Correction loop ValidationError come oggi.
3. Dopo soglia attuale (`validation_fails >= 2` / 1 correction fallita): outcome `escalate`.
4. `escalate_ref` = primary COMPLEX con **`LLM_COMPLEX_REASONING_EFFORT`** (tipico `high`).
5. Se knob BL già `high` e COMPLEX `high` → escalate resta no-op (AS-IS).
6. Se knob BL `none` e COMPLEX `high` → **1×** (o `max_attempts=2` come oggi) thinking high.

**Caveat qualità (documentare in runbook):** escalate su ValidationError **non** recupera `country_code` sbagliato ma schema-valido. Dual-run obbligatorio su XX prima del cutover ops a `none`.

### 3.4 Fuori scope

- UI / FinOps dashboard
- Schema `GeopoliticalArticleSchema` / system prompt classify
- Sidebar / mappa / Wave 2
- Colonna DB `complexity_lane` (opzionale futuro FinOps; non richiesto per questa wave)
- Move BORDERLINE → Gemini / lane SIMPLE
- Quarta fascia heuristic
- Cambiare `quality:compare` (resta `none`)
- Terzo model ID (es. Pro)

---

## 4. Wave di implementazione

| Wave | Contenuto | Done when |
|------|-----------|-----------|
| **W1** | Config parse `LLM_BORDERLINE_REASONING_EFFORT`; `_chain_for(BORDERLINE)` usa effort dedicato; log `route lane=BORDERLINE → … effort=`; escalate_ref resta COMPLEX effort | Unit test verde |
| **W2** | Test: BL none → ref effort none; escalate identity high; BL high = AS-IS no-op escalate; COMPLEX invariato; shadow invariato | `pytest` classification/complexity |
| **W3** | `.env.example`, runbook, SoT §4.4 tabella lane, skill `radar-quota-ledger` + `llm-json-extraction` se citano “BL=high always”, mirror `.agents`/`.ecc` | Docs allineati |
| **W4 GATE** | Dual-run campionario (vedi §5) → se KPI ok, ops set `LLM_BORDERLINE_REASONING_EFFORT=none` + restart worker; verify ledger/log | GATE VERDE |

Default ship W1–W3: comportamento **identico** AS-IS finché env non è `none`.

---

## 5. Dual-run / GATE qualità (obbligatorio prima di ops `none`)

### 5.1 Procedura (no dual-write automatico in v1)

1. Baseline 24–48h con BL=`high` (AS-IS): log count BL, XX su heur BL (recompute), token/cost `classify:complex`.
2. Impostare `LLM_BORDERLINE_REASONING_EFFORT=none`, restart `radar-worker`.
3. Campione N≥30 articoli nuovi BORDERLINE (o requeue mirato **senza** `--purge-all` di massa salvo PO).
4. Confrontare:

| KPI | Go | No-go |
|-----|----|-------|
| XX rate heur BORDERLINE | ≤ baseline +3pp | > +5pp |
| ValidationError / 100 art BL | ≤ baseline +2; escalate rate &lt;25% | spike >2× o escalate ≥25% (double-spend) |
| Completion token p50 su BL | chiaro calo vs high | invariato/peggio senza benefit |
| Fallback article | ≈0 | crescita |

5. Se no-go → ripristinare env `high` (rollback istantaneo).  
6. Se go → lasciare `none`; chiudere piano → `complete/`.

### 5.2 Query / comandi riuso

```bash
cd radar

# Log heuristic
docker compose logs radar-worker --since 24h 2>&1 | grep -c 'classify lane=BORDERLINE'
docker compose logs radar-worker --since 24h 2>&1 | grep 'route lane=BORDERLINE'

# Costo complex
docker compose exec -T radar-db psql -U radar_user -d radar_db -c "
SELECT COUNT(*) n, COALESCE(SUM(estimated_cost_usd),0) cost,
  AVG(completion_tokens) FILTER (WHERE completion_tokens>0) avg_cmp
FROM llm_request_ledger
WHERE purpose='classify:complex' AND status='completed'
  AND created_at > NOW() - INTERVAL '24 hours';"

# RPD Gemini (non deve assorbire BL)
docker compose exec -T radar-db psql -U radar_user -d radar_db -c "
SELECT model, COUNT(*) FROM llm_request_ledger
WHERE purpose='classify:simple' AND status IN ('completed','failed','reserved')
  AND created_at::date = (NOW() AT TIME ZONE 'Europe/Rome')::date
GROUP BY 1;"
```

Offline heur XX: `score_complexity(title, body_excerpt)` nel worker (script one-off read-only) come in analisi.

### 5.3 GATE requeue live (distruttivo — skill `radar-requeue-ops`)

```bash
cd radar
# 1) Dry-run
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 40 --dry-run
# 2) Apply (cancella articles/outbox/vault correlati + unread Miniflux + clear cooldown)
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 40
# Opzionale wipe totale (solo con conferma PO):
# docker compose exec -T radar-worker python -m app.scripts.requeue_articles 100 --purge-all --dry-run
# docker compose exec -T radar-worker python -m app.scripts.requeue_articles 100 --purge-all

# 3) Env ops (NON commitare .env): LLM_BORDERLINE_REASONING_EFFORT=none
docker compose up -d --build radar-worker
# 4) Tail log
docker compose logs -f radar-worker | grep -E 'classify lane=|route lane=|Escalat|Traceback|Ciclo'
```

Verificare: vault markdown rigenerati; Miniflux unread consumati; `classification_lane` execution = `complex` per BL; ledger `classify:complex`; assenza errori vault/Miniflux.

---

## 6. File touchabili

**Codice**
- `radar/backend/app/core/config.py` e/o `llm_lanes.py` — parse knob + export
- `radar/backend/app/classification/client.py` — `_borderline_chain` / `_chain_for`; **passare `effort=ref.reasoning_effort` a `classify_json`**
- `radar/backend/app/classification/deepseek.py` — `build_payload` / `classify_json` accettano `effort` per-call (vedi §9 R1)
- `radar/backend/app/tests/test_classification.py` (+ `test_openai_compat_dialect.py` se serve assert payload)

**Docs / ECC (aggiornare in place — non spostare piani complete)**
- `radar/.env.example`, `radar/docs/runbook.md`
- Root [`README.md`](../../README.md) se cita routing lane/effort
- [`docs/02_architecture_and_backend.md`](../../docs/02_architecture_and_backend.md)
- [`.agents/AGENTS.md`](../../.agents/AGENTS.md) + mirror [`radar/.ecc/CLAUDE.md`](../../radar/.ecc/CLAUDE.md) / rules ECC se citano “BORDERLINE = high”
- `plan-audit/complete/sot_llm_multi_model_fallback.md` §4.4
- `plan-audit/STATUS.md`, `plan-audit/README.md` (indice active/prompt)
- Skills: `.agents/skills/radar-quota-ledger/SKILL.md` + mirror `.ecc`; `llm-json-extraction` solo se cita BL=high always

**Vietato:** `radar-sidebar/**`; schema/prompt classify; migration DB; **git commit** (PO: senza commit in questa wave salvo richiesta esplicita).

---

## 7. Criteri GATE VERDE

- [x] Default unset = comportamento AS-IS (`high` su BL)
- [x] Con `LLM_BORDERLINE_REASONING_EFFORT=none`: log `route lane=BORDERLINE … effort=none` **e** payload DeepSeek `thinking.disabled` (non solo log)
- [x] ValidationError su BL → escalate a effort high (log Escalation / `escalated=True`; test unitario `test_borderline_escalation_triggers_high_effort` VERDE)
- [x] COMPLEX e `quality:compare` invariati
- [x] Pytest verdi (39/39 su host `.venv`; container image di produzione non include `pytest` in PATH, exit 127 verificato)
- [x] Requeue live (§5.3) con vault/Miniflux/restart verificati
- [x] Dual-run KPI §5 go (baseline XX su BL high ~1%; recompute 24h DeepSeek 136 BL, 3 XX = 2.2% [Δ ~+1.2pp ≤ +3pp threshold GO]; escalate live 0; GO confermato)
- [x] Requeue live GATE N=120 (2026-07-22): dry-run→apply; 2 cicli worker; BL route `effort=none` only (0 high); Traceback 0; escalate 0; pytest host 39/39
- [x] Docs/SoT/skills/README/ECC aggiornati; piano in `complete/`; prompts in `prompts/done/`

---

## 8. Stima impatto $

Risparmio assoluto piccolo a volume attuale (~$0.5–1/mese se thinking ≈ −800 completion/call su ~100 BL/g), ma:

- igiene costi / latenza sul 28% volume;
- thinking riservato a COMPLEX + escalate;
- evita la trappola Gemini RPD.

Driver decisione cutover = **XX / ValidationError**, non il jackpot FinOps.

---

## 9. Review Implementation Plan orchestratore (correzioni vincolanti)

> Applicare queste correzioni **sopra** qualsiasi Implementation Plan Agent interno.

### R1 — CRITICO: effort per-call sul client OpenAI-compat (senza questo = no-op)
`_compat_client(quota_lane)` cachea **un** `DeepSeekClient` per lane con `effort=LLM_COMPLEX.reasoning_effort` (tipico `high`).  
Oggi `classify_json(...)` **non** accetta/override `effort` → usa sempre `self.effort` del client cacheato.

**Obbligo:** 
- `DeepSeekClient.build_payload(..., effort: str | None = None)` e `classify_json(..., effort: str | None = None)` usano `effort or self.effort`;
- in `client._compat_call` passare `effort=ref.reasoning_effort`;
- test: con BL `none`, payload ha `thinking.type=disabled` (non solo log route).

Senza R1, `_borderline_chain` è cosmetico.

### R2 — `_borderline_chain` spechia la lista modelli COMPLEX
Stessi provider/model/FALLBACKS di `_complex_chain`, cambia **solo** `reasoning_effort`. `quota_lane` resta `"complex"`. Non inventare provider/model BL.

### R3 — `escalate_ref` resta COMPLEX effort (high tipico)
Non escalate a Gemini. Identity `(provider, model, effort)` già distingue none vs high. Con entrambi `high`, escalate resta no-op (AS-IS OK).

### R4 — Parse knob: coerente con altri effort
Unset/vuoto → `high`. Alias `off`/`disabled` → `none`. `low`/`medium` → coerce a `high` + **warning log** (DeepSeek payload li rimappa comunque). Valore ignoto → `high` + warning (allinea stile lane; no silent typo → none).

### R5 — `quality:compare` invariato
Continua a costruire il proprio client/`effort="none"`. Non rompere quel path riscrivendo il cache COMPLEX.

### R6 — Docs ECC completi (lista minima)
Oltre `.env.example` + runbook + SoT §4.4 + skill quota-ledger:
- `docs/02_architecture_and_backend.md` (riga routing: BL effort knob)
- `.agents/AGENTS.md` + `radar/.ecc/CLAUDE.md` (e rules ECC se citano BL=high fisso)
- root `README.md` se menziona complexity/effort
- `plan-audit/README.md` + `STATUS.md` (indice; **non** spostare il piano in `complete/` finché GATE non chiuso dal PO)
- skill `llm-json-extraction` solo se afferma “BORDERLINE always high”

### R7 — GATE live obbligatorio con requeue ufficiale (distruttivo)
Skill `radar-requeue-ops`. Protocollo:

1. Dry-run: `requeue_articles N --dry-run` (N tipico 30–50; conferma ops se ≥100).
2. Write: stesso comando senza dry-run **oppure** `--purge-all` solo se PO vuole wipe totale DB+vault (più distruttivo).
3. Impostare in `.env` (non commitare) `LLM_BORDERLINE_REASONING_EFFORT=none`.
4. `docker compose up -d --build radar-worker` (o restart dopo rebuild) per ciclo immediato.
5. Assert log: `classify lane=BORDERLINE`, `route … effort=none`, eventuali `Escalation` / `escalated=True`.
6. Assert DB: nuovi `articles` con `classification_lane=complex` dove heur BL; ledger `purpose=classify:complex`; Gemini RPD non deve assorbire BL.
7. Assert vault: markdown ricreati post-commit; assenza Traceback.
8. Rollback test: rimettere `high`, restart, verifica route `effort=high`.

**VIETATO:** DELETE SQL ad-hoc; requeue sull’host fuori container; `--purge-all` senza dry-run; commit `.env`.

### R8 — Pytest (fonte di verità GATE)
Immagine worker di produzione (`python:3.12-slim`) **non** include `pytest` in PATH (exit 127 verificato).  
GATE unitario accettato su host:

```bash
cd radar && .venv/bin/pytest app/tests/test_classification.py app/tests/test_complexity.py app/tests/test_openai_compat_dialect.py -q
```

Opzionale in futuro: aggiungere pytest al stage/dev image; non richiesto per questa wave.

### R9 — Nessun commit git
Wave senza `git commit` / `git push` salvo ordine esplicito PO successivo.

### R10 — Dual-run ≠ dual-write
Niente doppia call none+high per articolo in v1. Misura = cambio env + requeue + KPI.

### R11 — Heuristic vs execution lane (docs/test)
Non asserire `articles.classification_lane == 'borderline'`. Misura BL da log `classify lane=BORDERLINE` o recompute `score_complexity`.

### R12 — Runbook deve documentare caveat XX
Escalate ValidationError non corregge geo sbagliata schema-valida; KPI XX nel GATE.
