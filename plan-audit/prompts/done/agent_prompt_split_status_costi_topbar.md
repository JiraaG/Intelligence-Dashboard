# Agent prompt — Topbar Split: STATUS & COSTI in 2 Pulsanti Separati

> **Stato: DONE / SUPERSEDED** — implementato su `feature/upgrades` (`5b84a34`+).  
> **Layout reale SoT:** STATUS all’estrema **sinistra** (`.toolbar-left`); COSTI all’estrema **destra** (`.toolbar-right` dopo RELAZIONI) — non entrambi in left dopo i filtri come nello spec sotto.  
> **SoT UI attuale:** [`docs/03_frontend_and_ui.md`](../../../docs/03_frontend_and_ui.md).  
> **Branch:** `feature/upgrades`  
> **No Commit:** Nessun `git commit` o `git push` senza conferma esplicita dell'utente.

---

## Come usare (storico)

1. Apri una **nuova chat Agent** su branch `feature/upgrades`.
2. Incolla **tutto** il blocco PROMPT sottostante.
3. L'Agent eseguirà l'implementazione frontend/backend necessaria, la ricompilazione Docker e la verifica live.

---

## PROMPT (incolla in Agent mode) — SPEC STORICA

```text
# Task — Topbar UI Refactor: Separazione in 2 Pulsanti & Popover "COSTI" e "STATUS"

## Ruolo & Contesto
Sei un Full-Stack Engineer specializzato in Angular 21 Standalone Components e FastAPI.
Devi separare l'attuale singolo pulsante/popover `STATUS & COSTI` della topbar di Radar in **DUE pulsanti e popover separati**: **`COSTI`** e **`STATUS`**.

---

## Requisiti di Layout & Posizionamento Topbar

1. **Posizione nella Topbar:**
   - Spostare entrambi i pulsanti nel **gruppo di SINISTRA della topbar** (`.toolbar-left`), posizionandoli alla FINE del gruppo di sinistra (dopo i filtri Sentiment e Tipologia).
   - Ordine dei pulsanti da sinistra a destra:
     1. **`COSTI`** -> Esempio label: `COSTI: $0.1139` (mostra il costo del giorno selezionato).
     2. **`STATUS`** -> Esempio label: `STATUS 🟢` (mostra l'indicatore di salute del sistema).

---

## Requisiti dei 2 Popover (Contenuto & Logica)

### 1. Popover "COSTI" (Filtrato per Data Selezionata)
Questo popover deve contenere esclusivamente le metriche storiche/analitiche legate al **giorno selezionato nel calendario**:

- **Sezione 1 — Grid Summary:**
  - `Costo stimato giorno` (es. `$0.1139`)
  - `Articoli ingestiti` (es. `591`)
  - `Richieste LLM` (es. `852`)
  - `Latenza media pipeline` (es. `12,863 ms`)
- **Sezione 2 — Consumo Token & Cache:**
  - Prompt, Completion, Cached % (filtrati per data).
- **Sezione 3 — Richieste LLM per Singolo Modello (Filtrate per Giorno):**
  - Stesso design grafico di adesso (progress bar / righe stilizzate con contatori), ma con i **conteggi di richieste ed utilizzo token del singolo modello per il giorno selezionato** (es. `gemini-3.5-flash-lite: 392 req`, `deepseek-v4-flash: 460 req`).
  - *Nota Backend/DTO:* Se `GET /api/metrics/summary` non restituisce ancora il breakdown per modello del giorno, estendere la risposta DTO aggiungendo la mappa o lista `models_breakdown: [{ model, provider, requests_count, total_tokens }]`.
- **Sezione 4 — Eventi Deduplicazione:**
  - Totale, URL, Vettoriale, Hash (filtrati per data).

---

### 2. Popover "STATUS" (Operativo & Real-Time)
Questo popover deve contenere lo **stato di salute operativo in tempo reale ("Oggi ops")**:

- **Sezione 1 — Banner Stato Sistema:**
  - Indicatore visuale: `🟢 Stato sistema: OPERATIVO (Catena Simple OK)`
  - Badge L1 Fallback se attivo (es. `L1 Fallback (reason)`).
- **Sezione 2 — Modelli & Quote RPD (Tempo Reale / Oggi ops):**
  - Barre di avanzamento RPD live, quote limite, indicatore di cooldown e rate-limiting in tempo reale (da `metricsStatus()`).

---

## Istruzioni di Implementazione Frontend Angular

1. **`radar-toolbar.component.html` & `.ts`:**
   - Creare due popover PrimeNG separati (es. `#costiPopover` e `#statusPopover`).
   - Spostare l'HTML dei due pulsanti all'interno di `.toolbar-left`.
   - Gestire lo stato di apertura dei due popover in modo indipendente.
   - Per `COSTI`: ricavare il valore da `metricsSummary()?.llm?.total_estimated_cost_usd`.
   - Per `STATUS`: ricavare l'emoji stato da `statusDotEmoji()`.

2. **Backend API (`main.py` / `metrics_query.py` se necessario):**
   - Assicurarsi che `GET /api/metrics/summary` includa nella sezione LLM il breakdown delle chiamate per modello per il giorno selezionato, in modo che il popover `COSTI` possa mostrare le linee/contatori per modello filtrati per data.

---

## Verifiche Obbligatorie
1. Verificare che cambiando la data nel calendario, il popover **`COSTI`** aggiorni tutti i suoi numeri (compreso il breakdown per modello).
2. Verificare che il popover **`STATUS`** continui a mostrare le quote RPD in tempo reale di oggi.
3. Eseguire la ricompilazione Docker: `docker compose up -d --build`.
4. Eseguire i test backend: `PYTHONPATH=backend ./.venv/bin/pytest -m "not live" -q`.
5. Produrre il Walkthrough dettagliato delle modifiche.
6. **NO COMMIT:** Non eseguire `git commit` o `git push`.
```
