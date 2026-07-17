---
name: spatial-data-mocking
description: >
  Playbook per il testing offline del frontend Angular 21 in totale isolamento dal backend Python.
  Definisce il set di dati mockati, le istruzioni per attivare/disattivare il mock service,
  e i checklist visivi per validare cluster, overlay full-bleed, hatching SVG e carousel PrimeNG
  senza necessità del backend attivo o di dati reali da Miniflux/Gemini.
  **Sidebar freeze:** validare il carosello in sola osservazione — non modificare
  `radar-sidebar/**` né sostituire `p-carousel` con `article-list`.
when_to_use:
  - Sviluppo UI/UX offline prima che il backend sia operativo
  - Test di regressione visiva delle funzionalità della mappa
  - Dimostrazione/preview del Radar senza dati reali
  - Debug di layout, CSS e comportamento dei componenti PrimeNG
version: 1.1.0
---

## Quando Usare Questa Skill

Carica questa skill ogni volta che:
- Sviluppi o modifichi componenti del frontend senza backend attivo
- Devi verificare che il pattern hatching SVG si applichi correttamente in zoom-out
- Vuoi testare l'overlay full-bleed (mappa 100vw; sidebar sopra) al click sui marker
- Devi validare il corretto funzionamento del carosello PrimeNG su cluster di notizie
- Stai preparando una demo o screenshot dell'interfaccia

---

## Come Funziona

Il mock service sostituisce le chiamate HTTP reali iniettando dati statici pre-compilati.
L'interfaccia Angular non sa la differenza: riceve gli stessi tipi (`MapSummaryRow[]`,
`ArticlesPage`) sia in modalità mock che in modalità produzione.

**Phase 4–5:** il toggle è l'injection token esplicito `MOCK_MODE` (`services/mock-mode.token.ts`).
Default `false` in `app.config.ts`. Per offline/demo, fornire `{ provide: MOCK_MODE, useValue: true }`.
**Vietato** l'auto-fallback silenzioso su mock in caso di errore API: l'errore resta visibile
(`StateService.error` → banner toolbar). Nation-fetch (T-P1-04): anche i fallimenti di
`loadCountryArticles` popolano `detailError` (merge in `error()`); non chiudere la sidebar
azzerando l'errore (`closeSidebar(false)` sul catch).

Contratto API Phase 5 (allineato a `article.service.ts` / `article-mock.service.ts`):
- Day view: `getMapSummary` → `GET /api/map-summary`
- Saved vault: `getSavedSummary` → `GET /api/saved-summary` (no date; `is_saved`)
- Nation open: `getArticlesPage` → `GET /api/articles` con envelope `{ items, next_cursor, total }` (page ≤ 100; FE concatena)
- Saved open: `getArticlesPage({ saved: true, country })` — ignora date

```typescript
// frontend/src/app/services/mock-mode.token.ts
export const MOCK_MODE = new InjectionToken<boolean>('MOCK_MODE', {
  providedIn: 'root',
  factory: () => false,
});
```

> **Nota:** In produzione il token è `false`. Un fallimento di rete/API non attiva i mock.

**Categorie primary ammesse (10 — SoT `PRIMARY_CATEGORIES`):**
Nucleare, Energia, Infrastrutture, Geopolitica, Economia, Tecnologia, Spazio, Ambiente, Salute, Sicurezza.

**Vietato** come `primary_category`: `Chip`, `Acqua`, `Elettronica` (possono restare solo come tag testuali).

---

## Dataset Mock Completo

Il dataset copre 5 nazioni e 4 categorie valide per testare gli scenari visivi.
**SoT codice:** `radar/frontend/src/app/services/article-mock.service.ts` (non inventare categorie).

```typescript
// frontend/src/app/services/article-mock.service.ts (estratto dataset)
import { Article } from '../models/article.model';

const TODAY = new Date().toISOString().split('T')[0];

export const MOCK_ARTICLES: Article[] = [
  // --- CLUSTER TEST: Due articoli in Germania (città diverse) ---
  {
    id: 1,
    title: 'TSMC inaugura la prima fab europea a Dresda',
    summary: 'TSMC ha inaugurato in Sassonia il primo impianto produttivo europeo per chip a 28nm.',
    published_at: TODAY,
    source_url: 'https://example.com/tsmc-dresden',
    country_code: 'DE',
    latitude: 51.0504,
    longitude: 13.7373,
    companies_involved: ['TSMC', 'Infineon', 'Bosch'],
    tags: ['Chip', 'Semiconduttori', 'Germania', 'Fab'],
    primary_category: 'Tecnologia',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['TSMC Dresden Fab', 'Silicon Saxony Campus'],
    feed_title: 'Silicon Saxony News',
    is_read: false,
  },
  {
    id: 2,
    title: 'Siemens Energy amplia la rete di trasmissione ad alta tensione in Baviera',
    summary: 'Siemens Energy ha completato il potenziamento di 800km di linee di trasmissione nel sud della Germania.',
    published_at: TODAY,
    source_url: 'https://example.com/siemens-baviera',
    country_code: 'DE',
    latitude: 48.1351,
    longitude: 11.5820,
    companies_involved: ['Siemens Energy', 'Tennet'],
    tags: ['Energia', 'Grid', 'Germania', 'Rinnovabili'],
    primary_category: 'Energia',
    sentiment: 'Neutrale',
    relevance_level: 3,
    infrastructural_entities: ['Rete di trasmissione 380kV Baviera', 'Interconnessione DE-AT'],
    feed_title: 'Bavarian Grid Monitor',
    is_read: true,
  },

  // --- CLUSTER TEST: Due articoli vicini in Ucraina ---
  {
    id: 3,
    title: 'Centrale di Zaporizhzhia: rapporto IAEA sui sistemi di raffreddamento',
    summary: "L'IAEA certifica il funzionamento dei sistemi di backup della centrale.",
    published_at: TODAY,
    source_url: 'https://example.com/zaporizhzhia-iaea',
    country_code: 'UA',
    latitude: 47.5083,
    longitude: 34.3981,
    companies_involved: ['IAEA', 'Energoatom', 'Rosatom'],
    tags: ['Nucleare', 'IAEA', 'Ucraina', 'Sicurezza'],
    primary_category: 'Nucleare',
    sentiment: 'Negativo',
    relevance_level: 5,
    infrastructural_entities: ['Centrale Nucleare di Zaporizhzhia', 'Sito di stoccaggio combustibile'],
    feed_title: 'IAEA Bulletin',
    is_read: false,
  },
  {
    id: 4,
    title: "Diga di Kakhovka: progetto di ricostruzione approvato dall'UE",
    summary: "L'Unione Europea ha approvato 2.3 miliardi di euro per la ricostruzione dell'infrastruttura idrica.",
    published_at: TODAY,
    source_url: 'https://example.com/kakhovka-ue',
    country_code: 'UA',
    latitude: 47.3606,
    longitude: 33.4750,
    companies_involved: ['European Commission', 'EBRD'],
    tags: ['Acqua', 'Diga', 'Ucraina', 'Ricostruzione'],
    primary_category: 'Ambiente',
    sentiment: 'Positivo',
    relevance_level: 3,
    infrastructural_entities: ['Diga di Kakhovka', 'Serbatoio di Kakhovka'],
    feed_title: 'EU Reconstruction Index',
    is_read: false,
  },

  // --- SINGOLI MARKER ---
  {
    id: 5,
    title: 'Iran accelera arricchimento uranio, IAEA convoca riunione di emergenza',
    summary: 'Le centrifughe iraniane hanno raggiunto una capacità di arricchimento record al 60%.',
    published_at: TODAY,
    source_url: 'https://example.com/iran-uranium',
    country_code: 'IR',
    latitude: 32.4279,
    longitude: 53.6880,
    companies_involved: ['IAEA'],
    tags: ['Nucleare', 'Iran', 'IAEA', 'ONU', 'Geopolitica'],
    primary_category: 'Nucleare',
    sentiment: 'Negativo',
    relevance_level: 5,
    infrastructural_entities: ['Impianto di Natanz', 'Impianto di Fordow'],
    feed_title: 'United Nations Security News',
    is_read: false,
  },
  {
    id: 6,
    title: 'Samsung avvia produzione chip 2nm a Seoul: sfida diretta a TSMC',
    summary: 'Samsung Electronics ha avviato la produzione di massa di chip a 2nm nel suo impianto di Hwaseong.',
    published_at: TODAY,
    source_url: 'https://example.com/samsung-2nm',
    country_code: 'KR',
    latitude: 37.5665,
    longitude: 126.9780,
    companies_involved: ['Samsung Electronics', 'TSMC', 'Apple'],
    tags: ['Chip', 'Samsung', 'Corea del Sud', '2nm', 'Semiconduttori'],
    primary_category: 'Tecnologia',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['Samsung Fab Hwaseong', 'Samsung R&D Campus Suwon'],
    feed_title: 'Korea Tech Herald',
    is_read: false,
  },
  {
    id: 7,
    title: "Pipeline TAP: record storico di esportazione gas dall'Azerbaigian all'Europa",
    summary: "Il gasdotto Trans-Adriatico ha trasportato 12 miliardi di m³ nel primo semestre 2026.",
    published_at: TODAY,
    source_url: 'https://example.com/tap-record',
    country_code: 'AZ',
    latitude: 40.1431,
    longitude: 47.5769,
    companies_involved: ['TAP AG', 'SOCAR', 'BP', 'SNAM'],
    tags: ['Energia', 'Gas', 'Pipeline', 'Azerbaijan', 'Europa'],
    primary_category: 'Energia',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['Trans-Adriatic Pipeline (TAP)', 'Terminale di Melendugno', 'Campo di Shah Deniz II'],
    feed_title: 'Trans-Adriatic Pipeline Press',
    is_read: false,
  }
];
```

---

## Come Attivare il Mock Service

### Step 1: Mock Service (Phase 5)

```typescript
// frontend/src/app/services/article-mock.service.ts
import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import {
  Article,
  ArticlesPage,
  ArticlesPageFilters,
  CountrySummary,
  PrimaryCategory,
  Sentiment,
} from '../models/article.model';
import { MapSummaryRow } from '../models/map-summary.model';

@Injectable({ providedIn: 'root' })
export class ArticleMockService {
  getMapSummary(date: string, sentiment?: Sentiment | Sentiment[] | null): Observable<MapSummaryRow[]> {
    // Aggrega MOCK_ARTICLES per (country_code, primary_category) → MapSummaryRow[]
    // ...
  }

  getArticlesPage(filters: ArticlesPageFilters): Observable<ArticlesPage> {
    // Filtra + keyset cursor + envelope { items, next_cursor, total }; limit clamp 1–100
    // ...
  }

  /** @deprecated Prefer getMapSummary / getArticlesPage */
  getArticles(date: string): Observable<Article[]> {
    return of(MOCK_ARTICLES);
  }

  getCountries(date: string): Observable<CountrySummary[]> {
    // ...
  }
}
```

### Step 2: Dependency Injection con `MOCK_MODE` (no silent fallback)

```typescript
// frontend/src/app/services/article.service.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ArticlesPage, ArticlesPageFilters, Sentiment } from '../models/article.model';
import { MapSummaryRow } from '../models/map-summary.model';
import { parseArticlesPageDto, parseMapSummaryDto } from '../models/article.dto';
import { ArticleMockService } from './article-mock.service';
import { MOCK_MODE } from './mock-mode.token';

@Injectable({ providedIn: 'root' })
export class ArticleService {
  private readonly http = inject(HttpClient);
  private readonly mock = inject(ArticleMockService);
  private readonly mockMode = inject(MOCK_MODE);

  getMapSummary(filters: {
    date: string;
    sentiment?: Sentiment | Sentiment[] | null;
  }): Observable<MapSummaryRow[]> {
    if (this.mockMode) {
      return this.mock.getMapSummary(filters.date, filters.sentiment ?? undefined);
    }
    let params = new HttpParams().set('date', filters.date);
    // ... sentiment opzionale
    return this.http.get<unknown>('/api/map-summary', { params }).pipe(
      map((payload) => parseMapSummaryDto(payload)),
    );
  }

  getArticlesPage(filters: ArticlesPageFilters): Observable<ArticlesPage> {
    if (this.mockMode) {
      return this.mock.getArticlesPage(filters);
    }
    // GET /api/articles → parseArticlesPageDto → { items, next_cursor, total }
    // ...
  }
}
```

Offline: in `app.config.ts` (o TestBed) fornire `{ provide: MOCK_MODE, useValue: true }`.
Produzione: `{ provide: MOCK_MODE, useValue: false }` — errori API (map-summary, saved-summary **e** nation/saved-fetch via `detailError`) restano in `StateService.error()`.

---

## Checklist Visivo per Validazione UI

Usa questo checklist per verificare che ogni funzionalità della mappa funzioni correttamente
con i dati mockati prima di connettere il backend reale.

### ✅ Test 1: Hatching SVG in Zoom-Out (livello < 5)

- [ ] La Germania mostra due colori di hatching (Tecnologia + Energia)
- [ ] L'Ucraina mostra due colori di hatching (Nucleare + Ambiente)
- [ ] L'Iran mostra hatching singolo (Nucleare)
- [ ] La Corea del Sud mostra hatching singolo (Tecnologia)
- [ ] L'Azerbaijan mostra hatching singolo (Energia)
- [ ] I marker puntuali sono invisibili in zoom-out
- [ ] **Cliccando su Germania in hatching**: sidebar apre (nation load via `getArticlesPage` / envelope)
- [ ] **Cliccando su Ucraina in hatching**: sidebar apre con articoli Nucleare + Ambiente

### ✅ Test 2: Dissolvenza e Marker in Zoom-In (livello >= 5)

- [ ] L'hatching SVG sfuma gradualmente con CSS transition opacity a 0
- [ ] I marker puntuali compaiono con icona tematica (categorie 10: es. ☢️ Nucleare, ⚡ Energia, 💻 Tecnologia, 🌿 Ambiente)
- [ ] I due marker tedeschi (Dresda Tecnologia e Monaco Energia) sono separati e cliccabili
- [ ] I due marker ucraini (Zaporizhzhia Nucleare e Kakhovka Ambiente) **NON** formano un cluster unico — ciascuno appartiene al proprio cluster group di categoria
- [ ] A zoom intermedio (5-9), i marker della stessa categoria in aree vicine si raggruppano in cluster colorati per categoria

### ✅ Test 3: Cluster per Categoria e Carosello PrimeNG

- [ ] I cluster usano le 10 categorie valide (Nucleare, Energia, Infrastrutture, Geopolitica, Economia, Tecnologia, Spazio, Ambiente, Salute, Sicurezza) — **no** Chip/Acqua/Elettronica come primary
- [ ] Cliccando su un cluster categoria si apre la sidebar sinistra con **solo** gli articoli di quella categoria
- [ ] Il componente `p-carousel` scorre correttamente tra le notizie della categoria selezionata (**osservare only** — non editare `radar-sidebar/**`)
- [ ] Ogni slide del carousel mostra: titolo, summary, badge tags, link sorgente
- [ ] `spiderfyOnMaxZoom: false`; `maxClusterRadius: 40` — espansione custom, non spiderfy Leaflet automatico

### ✅ Test 4: Overlay Full-Bleed (Phase 4)

- [ ] Mappa occupa 100vw / 100vh in stato idle
- [ ] Al click su marker/nazione: **mappa resta 100vw**; sidebar disegna **sopra** (overlay) — **non** restringere a 70%/30%
- [ ] Dopo open/close sidebar: `map.invalidateSize()` viene chiamato
- [ ] Cliccando fuori dalla sidebar o sul bottone ✕, sidebar chiude; mappa resta full-bleed

### ✅ Test 5: Filtraggio Temporale p-calendar

- [ ] Il selettore data in alto mostra la data odierna come default
- [ ] In mock mode i dati usano `TODAY` — cambiando data in passato tipicamente 0 notizie (day view via `getMapSummary`)
- [ ] Con data odierna: le 7 notizie mock compaiono (summary + nation pages)
- [ ] Day view usa `getMapSummary`; nation open concatena pagine `{ items, next_cursor, total }`

### ✅ Test 6: Notizie Salvate

- [ ] Contatore toolbar **NOTIZIE SALVATE** non dipende dalla data del calendario
- [ ] Tooltip **Nazioni Salvate** elenca paesi con badge count
- [ ] Click nazione → carousel multi-day + **fitBounds / flyTo 6 + spiderfy** (parity LETTE/TROVATE)
- [ ] Card: **Salva notizia** / **Rimuovi dai salvati**; save ⇒ letta; unread ⇒ unsave
- [ ] Mock: `getSavedSummary` + `getArticlesPage({ saved: true })`

---

## Dati Mock per Scenari di Test Aggiuntivi

```typescript
// Aggiungi a MOCK_ARTICLES per testare scenari edge-case
// Notizia senza aziende (companies_involved: [])
{
  id: 8,
  title: 'Siccità record nel bacino del Po: livello minimo storico',
  summary: 'Il fiume Po registra il livello più basso degli ultimi 70 anni. Le regioni padane attivano protocolli di emergenza idrica.',
  published_at: TODAY,
  source_url: 'https://example.com/po-siccita',
  country_code: 'IT',
  latitude: 44.9007,
  longitude: 10.2186,
  companies_involved: [],       // Test: sidebar senza sezione aziende
  tags: ['Acqua', 'Italia', 'Siccità', 'Emergenza'],
  primary_category: 'Ambiente',  // NON 'Acqua'
  sentiment: 'Negativo',
  relevance_level: 3,
  infrastructural_entities: ['Bacino del Po'],
  feed_title: 'Italian Climate Watch',
  is_read: false,
}
```
