---
name: radar-sidebar-freeze
description: >
  BLOCCA refactor di radar-sidebar/**. Conserva p-carousel e
  updateCarouselHeight via article-card-{id}. Bug read/unread/save solo in
  state.service.ts (+ radar-map per marker-read). Eccezione mirata: toggle Salva
  e sezione chip related_countries (single+carousel). Vietato altro.
when_to_use:
  - Qualsiasi task su UI laterale, carousel, schede articolo, sidebar
  - Tentativo di "migliorare" il carosello (scroll, ResizeObserver, list)
  - Bug marker letta/non letta (.marker-read) o Notizie Salvate
version: 1.2.0
---

## Quando attivare

Carica questa skill **prima** di toccare layout laterale, carousel PrimeNG, card articolo, o styling della barra sinistra.

## Regole immutabili

1. **Niente refactor** su `radar/frontend/src/app/components/radar-sidebar/**` (TS/HTML/SCSS/spec) ad eccezione del toggle Salva/Rimuovi e della visualizzazione delle chip dei paesi correlati (`related_countries`).
2. Conservare `p-carousel` — vietato sostituire con `app-article-list`, infinite scroll, o list custom.
3. Altezza carousel: `document.getElementById('article-card-' + id)` — non `.p-carousel-item-active`.
4. Bug **read/unread** (classe `.marker-read`) e logica **save**: fix in `state.service.ts` (+ `radar-map.component.ts` per marker). La sidebar **delega** solo (`toggleRead` / `toggleSave` → StateService).
5. Overlay full-bleed: mappa `100vw`; sidebar sopra — non split che restringe la mappa.

## Eccezione mirata (Notizie Salvate e Sezione Paesi Correlati)

1. Consentito aggiungere/aggiornare il toggle **Salva / Rimuovi dai salvati** sulle card (template single + carousel) e lo stile minimo allineato a `.read-btn`.
2. Consentito aggiungere la sezione **"Paesi correlati"** (dopo Aziende e prima di Tag) che mostra le chip (`.related-chip`) display-only dei codici ISO Alpha-2 tradotti in italiano.
3. Vietato qualsiasi altro restyle, refactor carousel, o spostamento della logica di stato dentro la sidebar.

## Anti-pattern

- Refactor "pulizia" della sidebar
- Introdurre ResizeObserver sul carosello
- Spostare logica read/save-state dentro `radar-sidebar/` (oltre alla delega click)

## Verifica

```text
git diff --stat -- radar/frontend/src/app/components/radar-sidebar
# → solo file legati al toggle Salva e ai chip related (html/scss), nessun refactor strutturale
```
