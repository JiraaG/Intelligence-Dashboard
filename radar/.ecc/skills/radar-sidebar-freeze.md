---
name: radar-sidebar-freeze
description: >
  BLOCCA qualsiasi modifica a radar-sidebar/**. Conserva p-carousel e
  updateCarouselHeight via article-card-{id}. Bug read/unread solo in
  state.service.ts + radar-map.component.ts. Vietato app-article-list.
when_to_use:
  - Qualsiasi task su UI laterale, carousel, schede articolo, sidebar
  - Tentativo di "migliorare" il carosello (scroll, ResizeObserver, list)
  - Bug marker letta/non letta (.marker-read)
version: 1.0.0
---

## Quando attivare

Carica questa skill **prima** di toccare layout laterale, carousel PrimeNG, card articolo, o styling della barra sinistra.

## Regole immutabili

1. **Zero touch** su `radar/frontend/src/app/components/radar-sidebar/**` (TS/HTML/SCSS/spec).
2. Conservare `p-carousel` — vietato sostituire con `app-article-list`, infinite scroll, o list custom.
3. Altezza carousel: `document.getElementById('article-card-' + id)` — non `.p-carousel-item-active`.
4. Bug **read/unread** (classe `.marker-read`): fix **solo** in `state.service.ts` + `radar-map.component.ts`.
5. Overlay full-bleed: mappa `100vw`; sidebar sopra — non split che restringe la mappa.

## Anti-pattern

- Refactor "pulizia" della sidebar
- Introdurre ResizeObserver sul carosello
- Spostare logica read-state dentro `radar-sidebar/`

## Verifica

```text
git diff --stat -- radar/frontend/src/app/components/radar-sidebar
# → deve restare vuoto
```
