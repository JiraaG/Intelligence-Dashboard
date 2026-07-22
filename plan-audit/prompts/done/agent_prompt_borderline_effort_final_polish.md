# Agent prompt — BORDERLINE effort FINAL POLISH (stessa chat)

> **Stato: ACTIVE** — micro-closeout dopo audit del walkthrough CLOSEOUT.  
> **Uso:** incolla nella **stessa** chat Agent.  
> **PO:** ancora **nessun git commit** finché non richiesto.

---

## Audit del walkthrough CLOSEOUT (rigoroso)

### Accettato / VERDE
| ID | Esito | Nota |
|----|-------|------|
| C1 | **PASS** | `test_borderline_escalation_triggers_high_effort` solido (mock escalate none→high, `was_escalated=True`) |
| C4 | **PASS** | `.agents` ≡ `radar/.ecc` llm-json-extraction |
| C5 | **PASS** | `radar/.ecc/rules/backend.md` ha knob |
| C8 | **PASS** | `radar_overview_and_upgrades.md` aggiornato |
| C9 | **PASS** | root `README.md` menziona knob |
| C10 | **PASS** | `.env.example` = `high` (safe) |
| Live ops | **PASS** | worker env `none`; path BL funzionante |
| No commit | **PASS** | dirty tree, 0 commit |

### Non chiuso / overclaim

| ID | Esito | Evidenza |
|----|-------|----------|
| **C3** | **FAIL / overclaim** | `docker compose exec radar-worker pytest` → **exit 127** (`pytest` non in PATH immagine). I 39 passed sono **host `.venv`**, non container. |
| **C6** | **PARZIALE** | SoT §4.4 OK, ma §8.2 riga ancora: ``_chain_for(BORDERLINE) → refs LLM_COMPLEX effort high``. Mermaid §4.7 ancora `B --> P2[LLM_COMPLEX effort high]`. |
| **C7** | **PARZIALE** | Knob runbook OK, ma riga ~122 ancora: `COMPLEX\|BORDERLINE … effort=high`. |
| **C2** | **DEBOLE** | Test forza monkeypatch `"high"`; non verifica parse unset da env/`config.py`. Accettabile come smoke; opzionale rafforzare. |
| **C11** | **DEBOLE ma GO tenibile** | Sample walkthrough N=17 &lt; soglia piano ≥30; baseline citata «4–5%» **non** combacia con analisi (~**1%** XX su BL high). Recompute indipendente 24h: **BL=136, XX=3 → 2.21%** (Δ vs 1% ≈ +1.2pp → entro +3pp GO). Escalations 0 OK. |
| **C12** | **OVERCLAIM** | Checklist §7 spunta pytest/container e KPI come pieni; STATUS «closeout done» prematuro finché C3/C6/C7 non sistemati. |

**Verdetto prodotto:** feature **ops-ready** con `none`; **documentazione/GATE non al 100%** come dichiarato nel walkthrough.

---

## PROMPT (incolla stessa chat)

```text
# Task — FINAL POLISH BORDERLINE effort (micro, non rifare core)

## Contesto
Closeout C1–C12 quasi fatto. Audit esterno: C3/C6/C7 ancora aperti; C11 GO tenibile con recompute 2.2% XX ma baseline walkthrough era imprecisa. **Nessun commit**.

## Obbligatorio (piccolo)

### 1) C6 — SoT residue
In `plan-audit/complete/sot_llm_multi_model_fallback.md`:
- §8.2: cambiare riga `_chain_for(BORDERLINE) → … effort high` in effort da `LLM_BORDERLINE_REASONING_EFFORT` (+ escalate high se none).
- Mermaid §4.7: nodo BORDERLINE non hardcodare `effort high` (es. `LLM_COMPLEX + LLM_BORDERLINE_REASONING_EFFORT`).

### 2) C7 — runbook L122
In `radar/docs/runbook.md` allineare la riga gate log:
`COMPLEX … effort=high` e `BORDERLINE … effort=<LLM_BORDERLINE_REASONING_EFFORT>` (ops tipico `none`).

### 3) C3 — pytest verità
Opzioni accettabili (scegline UNA e documenta nel report):
- A) Eseguire via host `.venv` **esplicitamente accettato** perché worker image non ha pytest in PATH (verificato exit 127) — aggiorna piano §7 checklist: «pytest host `.venv` 39/39; container N/A (no pytest binary)».
- B) Se preferisci container: `docker compose exec -T radar-worker python -m pytest …` solo se il modulo esiste; altrimenti resta A.

Non fingere che il container abbia passato pytest.

### 4) C11 — correggi KPI nel piano/STATUS
Sostituisci la narrativa «baseline 4–5% / sample 17 / 5.8%» con numeri onesti:
- Analisi baseline BL-on-high ≈ **1%** XX (o «&lt;2%»).
- Recompute 24h post-`none`: **136 BL, 3 XX = 2.2%** (Δ +~1.2pp → GO ≤+3pp).
- Sample walkthrough N=17 resta anecdotico; citare il recompute 136 come misura primaria.
- Escalate live: 0.

### 5) C12 — STATUS
`STATUS.md`: «ACTIVE — polish C3/C6/C7; feature ops `none` GO; PO confirm → move complete/».
Non spostare ancora in `complete/` senza OK PO.
Checklist §7: togli overclaim container pytest; marca docs residue dopo fix 1–2.

### Opzionale
- C2: test che importa/parse default da env vuoto (solo se economico).

## Fuori scope
Refactor client, requeue di massa, commit, move BL→Gemini.

## Deliverable
Diff SoT+runbook+STATUS+checklist; report pytest (host/container onesto); KPI XX 2.2% documentato; conferma 0 commit.
```
