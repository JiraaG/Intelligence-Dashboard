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

> **MapLibre parity (Phase I):** i Test 1–7 sotto devono passare sul renderer **default MapLibre** con la **stessa UX** del path Leaflet legacy (hatching, pin, spiderfy, overlay, salvati, archi). Forzare Leaflet solo per regressione ops: `localStorage.setItem('radar.mapRenderer','leaflet')` + reload.

### ✅ Test 1: Hatching SVG in Zoom-Out (livello < 4)

- [ ] La Germania mostra due colori di hatching (Tecnologia + Energia)
- [ ] L'Ucraina mostra due colori di hatching (Nucleare + Ambiente)
- [ ] L'Iran mostra hatching singolo (Nucleare)
- [ ] La Corea del Sud mostra hatching singolo (Tecnologia)
- [ ] L'Azerbaijan mostra hatching singolo (Energia)
- [ ] I marker puntuali sono invisibili in zoom-out
- [ ] **Cliccando su Germania in hatching**: sidebar apre (nation load via `getArticlesPage` / envelope)
- [ ] **Cliccando su Ucraina in hatching**: sidebar apre con articoli Nucleare + Ambiente

### ✅ Test 2: Dissolvenza e Marker in Zoom-In (livello >= 4 / latch pin)

- [ ] L'hatching SVG sfuma gradualmente con CSS transition opacity a 0
- [ ] I marker puntuali compaiono con icona tematica (categorie 10: es. ☢️ Nucleare, ⚡ Energia, 💻 Tecnologia, 🌿 Ambiente)
- [ ] I due marker tedeschi (Dresda Tecnologia e Monaco Energia) sono separati e cliccabili
- [ ] I due marker ucraini (Zaporizhzhia Nucleare e Kakhovka Ambiente) **NON** formano un cluster unico — ciascuno appartiene al proprio gruppo di categoria (MapLibre: hub/fan custom; Leaflet legacy: cluster group)
- [ ] A zoom intermedio (4–9), i marker della stessa categoria in aree vicine si raggruppano per categoria (parity UX)
- [ ] **Isteresi globo:** a zoom ~4, pan N/S **senza wheel** non deve sfarfallare pin↔hatching (`resolvePinMode` / exit solo &lt; 3.6)

### ✅ Test 3: Cluster / spiderfy per Categoria e Carosello PrimeNG

- [ ] Le 15 categorie valide (Nucleare…Materie Prime) — **no** Chip/Acqua/Elettronica come primary
- [ ] Cliccando hub/categoria si apre la sidebar sinistra con **solo** gli articoli di quella categoria
- [ ] Il componente `p-carousel` scorre correttamente tra le notizie della categoria selezionata (**osservare only** — non editare `radar-sidebar/**`)
- [ ] Ogni slide del carousel mostra: titolo, summary, badge tags, link sorgente
- [ ] MapLibre: spiderfy custom **senza** MarkerCluster; n &lt; 9 cerchio / n ≥ 9 **spirale** (pixel, non gradi); Leaflet legacy: `spiderfyOnMaxZoom: false`, `maxClusterRadius: 40`
- [ ] MapLibre: **non** riscrivere il carosello allo spiderfy (`clusterClicked` solo su collapse `[]`)

### ✅ Test 4: Overlay Full-Bleed (Phase 4)

- [ ] Mappa occupa 100vw / 100vh in stato idle
- [ ] Al click su marker/nazione: **mappa resta 100vw**; sidebar disegna **sopra** (overlay) — **non** restringere a 70%/30%
- [ ] Dopo open/close sidebar: `map.resize()` (MapLibre) / `map.invalidateSize()` (Leaflet legacy)
- [ ] Cliccando fuori dalla sidebar o sul bottone ✕, sidebar chiude; mappa resta full-bleed

### ✅ Test 5: Filtraggio Temporale p-calendar

- [ ] Il selettore data in alto mostra la data odierna come default
- [ ] In mock mode i dati usano `TODAY` — cambiando data in passato tipicamente 0 notizie (day view via `getMapSummary`)
- [ ] Con data odierna: le 7 notizie mock compaiono (summary + nation pages)
- [ ] Day view usa `getMapSummary`; nation open concatena pagine `{ items, next_cursor, total }`

### ✅ Test 6: Notizie Salvate

- [ ] Contatore toolbar **NOTIZIE SALVATE** non dipende dalla data del calendario
- [ ] Tooltip **Nazioni Salvate** elenca paesi con badge count
- [ ] Click nazione → carousel multi-day + **fitBounds / flyTo 6 + spiderfy** (parity LETTE/TROVATE; MapLibre e Leaflet)
- [ ] Card: **Salva notizia** / **Rimuovi dai salvati**; save ⇒ letta; unread ⇒ unsave
- [ ] Mock: `getSavedSummary` + `getArticlesPage({ saved: true })`

### ✅ Test 7: Relazioni Geospaziali (Fase H + archi UI)

- [ ] Day view zoom **&lt; 4**: archi **multicolore** aggregati visibili sopra hatching (non nascosti) — MapLibre e Leaflet — **solo se** almeno una nazione è flaggata nel pannello Relazioni (default: nessuna → **0 archi**)
- [ ] Day view zoom **≥ 4**: **MapLibre** = stessa macro multicolore **continua** (no fan/dash); **Leaflet legacy** = archi **per-categoria** con geometric dash + fan parallelo multi-cat
- [ ] Toolbar unificata: **Sentiment**, **Tipologia**, **RELAZIONI ATTIVE** — stesso tooltip (titolo mono, un bottone Seleziona↔Deseleziona tutto, filtro testo, toggle iOS a destra); Relazioni: semantica OR (USA on + Cina off → arco USA↔Cina sì); filtro nazione anche su Nazioni Coinvolte / Nazioni Salvate
- [ ] Tipologia toolbar filtra categorie **prima** del filtro nazioni
- [ ] Hover arco: tooltip + highlight (anche in Europa densa) — invariato rispetto a pre-filtro
- [ ] Click arco MapLibre / macro Leaflet: sidebar/carosello con notizie bilaterali A↔B **tutte** le categorie (entrambi i versi)
- [ ] Click arco pin Leaflet (≥4): stessa cosa filtrata per la **tipologia** dell’arco
- [ ] Nation-open: archi nascosti (no interferenza spiderfy)
- [ ] Card: sezione "Paesi correlati" con chip se `related_countries` non vuoto
- [ ] Zoom &lt; 4: hatching **multi-colore** — MapLibre: N fasce soft = N tipologie da `map-summary` (mainland US/RU; isole significative ≥0.5% area largest; clip terra∩strip — niente bande in mare; ordine legenda); Leaflet: SVG combo pattern — non fill solido di una sola categoria; non barcode `fill-pattern` su MapLibre
- [ ] Path MapLibre: great-circle / LineString macro multicolore solida (tutti gli zoom) + hover thicken/tooltip; path Leaflet legacy: `relationsPane` + geometric dash ≥4

### ✅ Test 8: FinOps UI — STATUS + COSTI (topbar split)

- [ ] Topbar **sinistra** inizia con **STATUS** (pallino 🟢/🟡/🔴); **destra** termina con **COSTI: $X.XXXX** (giorno calendario).
- [ ] Popover **STATUS**: banner + eventuali alert L1/degradato; RPD SIMPLE→FALLBACK→BORDERLINE→COMPLEX; sezione **Gestione & Effort** (NONE/NONE/BL/COMPLEX).
- [ ] Popover **COSTI**: 6 sezioni (generali → costi/modello con effort → token → richieste/modello → dedup senza Totale → overall all-time).
- [ ] MOCK_MODE: `getMetricsSummary` ha `models_breakdown` con `reasoning_effort` + `overall`; `getMetricsStatus` ha `borderline`, `reasoning_effort` sui models, e almeno un FALLBACK se configurato nel fixture.
- [ ] Card sidebar **"ANALISI FINOPS & FONTE RSS"** dopo i Tag (modello, lane, token, latenza, costo, feed XML).
- [ ] **Legenda Tipologie**: pulsante `🏷️ LEGENDA TIPOLOGIE 15` (o `N/15` con lock) in basso al centro (`bottom: 20px; left: 50%`) apre popover griglia a 3 colonne glassmorphic per tutte le 15 tipologie A-Z con card selezionabili, badge notizie `(14)` sempre visibile senza overflow, glow illuminazione campiture (`0.85`) senza oscuramento delle altre tipologie (`0.34`), e auto-close a zoom >= 4. Il filtraggio articoli è gestito dal selettore Tipologia in toolbar.

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
