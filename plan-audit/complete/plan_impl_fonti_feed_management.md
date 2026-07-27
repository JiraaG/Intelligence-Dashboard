# Piano impl — FONTI (attività giorno + catalogo feed)

> **Stato: COMPLETE / GATE VERDE** — 2026-07-27  
> **Branch:** `feature/upgrades`  
> **Prompt Agent:** [`../prompts/done/agent_prompt_fonti_feed_management.md`](../prompts/done/agent_prompt_fonti_feed_management.md)  
> **Walkthrough:** [`walkthrough_fonti_feed_management.md`](walkthrough_fonti_feed_management.md)  
> **Origine analisi:** chat Plan Mode + `.cursor/plans/feed_rss_option_b_059bf880.plan.md`  
> **Prerequisiti:** Metrics 013 **GATE VERDE**; FinOps UI STATUS/COSTI **GATE VERDE**; seed Miniflux ops già in repo

---

## 1. Obiettivo prodotto

Chiudere il gap “gestione/visibilità feed” senza CRUD add da UI e senza scrivere il seed dal container.

1. **Topbar — nuovo pulsante `FONTI`** (stile glass STATUS/COSTI):
   - Vista **Giorno** (default): fonti che hanno contributi articoli nella **data del calendario** (allineata alla mappa).
   - Vista **Catalogo**: tutti i feed seed + stato live Miniflux; **toggle** enable/disable.
2. **STATUS** — riga compatta `Sorgenti N/M attive` (read-only; niente lista/toggle).
3. **Add nuovi URL** resta **seed JSON + CLI** (`import-miniflux-feeds.sh`); docs chiare per clone GitHub.
4. **Default:** tutti i feed `enabled: true` (campo assente = true).

**Non obiettivi di questa fase:** discovery URL, POST create, DELETE, scrittura `config/` dal backend, volume `config` RW, nuovi publisher oltre i ~35 già in seed/`RSS.txt`.

---

## 2. Contesto AS-IS

| Area | Realtà codice |
|------|----------------|
| Catalogo | [`radar/config/miniflux-feeds.seed.json`](../../radar/config/miniflux-feeds.seed.json) = SoT Git (~35 feed, 10 publisher). [`RSS.txt`](../../RSS.txt) = mirror umano (stesso set; path Guardian `/` vs `/uk/` già normalizzati dallo sync). |
| Ops sync | [`radar/ops/miniflux_feeds_sync.py`](../../radar/ops/miniflux_feeds_sync.py) + `import-miniflux-feeds.sh` / `sync-miniflux-seed.sh`. Import **non** synca oggi `disabled`/`enabled`. |
| Volume config | Compose: `./config:/app/config:ro` su backend e worker — **RO**. |
| Miniflux client API | [`extraction/client.py`](../../radar/backend/app/extraction/client.py): solo entries unread, mark-read, refresh-all. **Niente** list/update feed. |
| Endpoint by-feed | `GET /api/metrics/by-feed?from=&to=` esiste; filtra su **`created_at`**; **nessun consumo FE**. |
| Giorno mappa | `published_at` (`map-summary`, articles). COSTI/metrics summary: `created_at`. |
| Topbar UI | STATUS left, COSTI right; popover glass custom — **no `p-dialog`**. |
| Auth API | Nessuna auth applicativa; Miniflux API key = token admin pieno sulla rete `radar-data`. |
| Sidebar | **FREEZE** — non toccare `radar-sidebar/**` (feed_title già display-only). |

**Volume prodotti:** seed pieno → centinaia articoli/giorno (docs); ~600 raw Miniflux plausibile; vault/mappa vedono meno per dedup. **Non serve espandere da RSS.txt** (nessun backlog nascosto).

---

## 3. Decisioni chiuse

1. **Nome UI:** `FONTI` (non “RSS” / “FEED”).
2. **Un solo bottone** con due viste interne (`Giorno` | `Catalogo`). Non catalogo pieno in STATUS.
3. **Vista Giorno** = `by-feed` con **`date_field=published_at`** e `from=to=filters.date` (allineamento mappa). Solo `article_count > 0`. **Niente toggle.**
4. **Vista Catalogo** = `GET /api/feeds` (merge seed RO + Miniflux live) + `PATCH .../toggle`. Toggle scrive **solo** Miniflux `disabled`; **non** riscrive seed.
5. Seed campo opzionale `enabled` (default **true**). Import applica `disabled: not enabled`. Sync live→seed esporta `enabled`.
6. Mutazioni: `FEED_ADMIN_TOKEN` opzionale — se set, richiede header `X-Feed-Admin-Token`; se vuoto, LAN open (come resto API). Documentare.
7. Pattern FE = STATUS/COSTI (`toolbar-left` dopo STATUS; `closeAllPanelsExcept('fonti')`).
8. `MOCK_MODE` esplicito — no fallback silenzioso.
9. Add feed nuovi = seed + CLI (mantenere). Migliorie fase: docs + `enabled` su import. Helper `add-feed.sh` / UI add = **deferred**.
10. Commit git: **solo** se l’utente lo chiede.

---

## 4. Contratto API target

### 4.1 `GET /api/metrics/by-feed` (estensione)

Query esistenti: `from`, `to` (default oggi TZ).

Nuova query: `date_field=published_at|created_at`  
- Default per **nuovo FE FONTI:** `published_at`  
- Default API se omesso: preferire `published_at` (breaking vs caller ops che usavano `created_at` — oggi **nessun FE**; runbook/curl: documentare; se serve compat ops, default `created_at` e FE passa esplicitamente `published_at` — **scelta vincolante: FE passa sempre `published_at`; default API resta `created_at`** per non sorprendere script esistenti).

Response invariata:

```json
{
  "from": "YYYY-MM-DD",
  "to": "YYYY-MM-DD",
  "items": [
    {
      "feed_id": 1,
      "feed_domain": "bbc.com",
      "feed_title": "BBC News — World",
      "article_count": 42,
      "total_clean_chars": 0,
      "avg_clean_chars": 0,
      "avg_pipeline_latency_ms": null,
      "avg_embedding_time_ms": null
    }
  ]
}
```

### 4.2 `GET /api/feeds`

Merge seed + `GET /v1/feeds` Miniflux (match URL normalizzata; euristiche Guardian come sync ops).

```json
{
  "active_count": 28,
  "total_count": 35,
  "error_count": 1,
  "groups": [
    {
      "category": "BBC News",
      "feeds": [
        {
          "id": 12,
          "title": "BBC News — World",
          "feed_url": "https://...",
          "site_url": "https://...",
          "category": "BBC News",
          "scraper_rules": "#main-content",
          "crawler": true,
          "disabled": false,
          "enabled_in_seed": true,
          "in_seed": true,
          "parsing_error_count": 0,
          "parsing_error_msg": "",
          "checked_at": "...",
          "next_check_at": "..."
        }
      ]
    }
  ]
}
```

Feed live senza match seed: `in_seed: false` (visibili in Catalogo).  
Feed seed senza match Miniflux: `id: null`, `disabled` da seed `enabled` (o marker `not_imported`).

### 4.3 `PATCH /api/feeds/{feed_id}/toggle`

Body: `{ "disabled": true|false }`  
→ Miniflux `PUT /v1/feeds/{id}` con `disabled`.  
Gate token se `FEED_ADMIN_TOKEN` non vuoto → 401 altrimenti.

---

## 5. UI target

### 5.1 Pulsante FONTI

- Posizione: `.toolbar-left`, **dopo STATUS** (prima del divider verso calendario/filtri).
- Label: `FONTI` + badge conteggio fonti con articoli nel giorno (`items.length` by-feed) oppure `N/M` in Catalogo.
- Popover: stesse classi glass di STATUS (`.countries-tooltip.status-popover` o equivalente condiviso).
- Segment/tabs: **Giorno** | **Catalogo**.

**Giorno**

- Header: data selezionata · `N fonti · M articoli`
- Accordion/publisher → righe sotto-feed con count
- Empty state: “Nessuna fonte per questa data”
- Reload on open + on `filters.date` change

**Catalogo**

- Accordion publisher → switch iOS-like (coerente Sentiment/Tipologia)
- Stato: attivo / disabilitato / errore (tooltip msg)
- Ultimo check se disponibile
- Nessun form add URL

### 5.2 STATUS — sezione Sorgenti

Dopo banner/alert o in coda sezioni esistenti (senza appesantire RPD):

- `Sorgenti: {active_count}/{total_count} attive`
- Se `error_count > 0`: nota compatta errori
- Read-only; opzionale hint “Apri FONTI → Catalogo”

---

## 6. Onde di implementazione

| Wave | Scope |
|------|--------|
| **W0** | Docs/skills: `radar-api-contract` (+ mirror ecc), `docs/02_*`, `docs/03_*`, getting-started §6, ops README; `FEED_ADMIN_TOKEN` in `.env.example` |
| **W1** | `date_field` su by-feed; pytest |
| **W2** | MinifluxClient `list_feeds` / `update_feed`; `api/feeds.py`; register router; token gate; pytest |
| **W3** | Seed `enabled` + import/sync `miniflux_feeds_sync.py` |
| **W4** | FE models/DTO/service/mock + StateService resources |
| **W5** | Toolbar FONTI popover (Giorno + Catalogo) + STATUS snippet |
| **W6** | Docker rebuild FE/BE; smoke live; walkthrough `plan-audit/active/walkthrough_fonti_feed_management.md` |

---

## 7. File toccati (previsto)

**Backend:** `main.py`, `extraction/client.py`, `api/feeds.py` (NEW), `core/config.py`, tests.  
**Ops:** `miniflux_feeds_sync.py`, seed JSON (campo `enabled` opzionale — può restare omesso = true).  
**Frontend:** `radar-toolbar` (html/ts/scss), `article.service.ts`, `article-mock.service.ts`, `state.service.ts`, models/dto.  
**Docs/skills:** api-contract, getting-started, ops README, `docs/03_frontend_and_ui.md`.

**NO-TOUCH:** `radar-sidebar/**` (oltre freeze), worker classify, map legend, volume `:ro` → non cambiare in RW.

---

## 8. Come si aggiungono feed (rimane valido)

Clone / operatore:

1. `.env` + `docker compose up -d --build`
2. Miniflux API key → `MINIFLUX_API_KEY`
3. `./ops/import-miniflux-feeds.sh` (o `bootstrap-miniflux.sh`)
4. **Nuovo feed:** edit seed (`category`, `title`, `feed_url`, `scraper_rules`, `crawler`, `enabled`) + mirror `RSS.txt` → import → commit seed+OPML  
   Oppure live in Miniflux Admin → `sync-miniflux-seed.sh` → commit.

UI FONTI **non** sostituisce questo path per URL nuovi; semplifica spegnere/accendere sezioni e vedere chi ha prodotto nel giorno.

---

## 9. Verification / Gate

- [x] by-feed `date_field=published_at` allineato (smoke) a volumi mappa stessa data — vedi walkthrough 2026-07-22 (603=603)
- [x] FONTI Giorno: no toggle; filtra su calendario; empty state ok — codice + bundle; click UI manuale residuo
- [x] Catalogo: toggle → Miniflux disabled; STATUS N/M aggiornato — smoke PATCH + GET feeds 35/35
- [x] Import con `enabled: false` → feed disabled in Miniflux — codice ops (import live non rieseguito)
- [x] Token set → PATCH senza header = 401 — pytest
- [x] MOCK_MODE: lista statica; no SSE regressione — mock + errors fuori banner mappa
- [x] Sidebar freeze rispettato; nessun `p-dialog`
- [x] Walkthrough onesto in `plan-audit/active/` — [`walkthrough_fonti_feed_management.md`](walkthrough_fonti_feed_management.md)

**GATE:** **VERDE** 2026-07-27 — UI Catalogo toggle verificato live (Miniflux `disabled` + conteggio N/M); tipografia/badge allineati.

---

## 10. Deferred (fuori gate)

- UI add / discovery / delete
- `ops/add-feed.sh` helper
- Volume config RW / scrittura seed da API
- Nuovi publisher oltre seed attuale
- Filtri secondari in FONTI Giorno (per categoria geopolitica articolo — non richiesto)
