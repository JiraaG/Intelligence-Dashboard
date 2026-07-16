# Piano di Implementazione Frontend — Radar Informativo Globale

> **Stato:** `[NEW]`
> **Aggiornato:** 2026-06-24 (v3 — Integrazione Angular 21 rxResource, Ottimizzazioni Vector GeoJSON, Hatching Directive, Doppio Layer Leaflet ed Esclusione Radicale Colori HEX nei Componenti)
> **Scope:** `frontend/` — Angular 21, PrimeNG 17+, Leaflet 1.9.x, SCSS Palantir
> **Dipende da:** Backend FastAPI (`[IMPLEMENTED]`) + PostgreSQL + Miniflux

---

## Fonti di Riferimento Consultate

| File | Contributo al Piano |
|------|---------------------|
| [plan.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/plan.md) | PRD ufficiale: specifiche UX (hatching, zoom, split-screen, clustering, filtraggio temporale) |
| [plan_backend_ecc.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/plan_backend_ecc.md) | Schema Pydantic completo con `infrastructural_entities`, `sentiment`, `relevance_level` |
| [ecc_deep_dive_analysis.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/ecc_deep_dive_analysis.md) | Pattern ECC: offline mock service, verification loop, path-scoped rules |
| [RSS.txt](file:///c:/Users/lucag/Documents/Dashboard%20finance/RSS.txt) | 9 sorgenti reali per mock data realistici |
| [angular-map-expert.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/.ecc/agents/angular-map-expert.md) | Specifiche tecniche mappa, icone, clustering, hatching SVG |
| [frontend.md (rules)](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/.ecc/rules/frontend.md) | Regole ECC immutabili (Regole 0–9) |
| [AGENTS.md](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/.ecc/agents/geo-data-architect.md) | Guardrail immutabili (niente ORM, niente placeholder, niente tag multimediali nel parser) |

---

## Panoramica Architetturale

Il frontend è una **Single Page Application Angular 21** che consuma le API REST del backend Radar via proxy Nginx (`/api/` in produzione, `proxy.conf.json` in sviluppo). L'architettura è interamente basata su **Signals** e sulle nuove API native **rxResource** per una gestione ottimale dello stato asincrono e la prevenzione di memory leak causati da cambi filtro frenetici. Non ha routing client-side multiplo: è un'unica vista "mappa operativa" in stile Palantir con layout split-screen 70/30.

### Struttura Target `src/app/`

```
frontend/
├── proxy.conf.json                     ← Proxy Angular dev → backend:8000 (FASE 9)
├── src/
│   ├── index.html                      ← SEO: title IT, meta description, lang="it" (FASE 8)
│   ├── main.ts                         ← Bootstrap Angular (già presente)
│   ├── styles.scss                     ← Design System Palantir completo + configurazione Pane (FASE 1)
│   └── app/
│       ├── app.config.ts               ← provideHttpClient, provideAnimationsAsync (FASE 3)
│       ├── app.ts                      ← Root shell component (FASE 7)
│       ├── app.html                    ← Shell: toolbar + map-container + sidebar (FASE 7)
│       ├── app.scss                    ← Layout full-screen + split-screen CSS (FASE 7)
│       │
│       ├── models/
│       │   └── article.model.ts        ← Article + CountrySummary + ArticleFilters (FASE 2)
│       │
│       ├── shared/
│       │   └── directives/
│       │       └── leaflet-hatch.directive.ts ← Iniezione pattern hatching SVG (FASE 4)
│       │
│       ├── services/
│       │   ├── article.service.ts      ← HTTP /api/articles + auto-fallback resiliente (FASE 3)
│       │   ├── article-mock.service.ts ← 9 articoli da fonti RSS reali (FASE 3)
│       │   └── state.service.ts        ← Centralized rxResource Store (FASE 3)
│       │
│       └── components/
│           ├── radar-map/              ← Leaflet + GeoJSON una-tantum + requestAnimationFrame (FASE 4)
│           │   ├── radar-map.component.ts
│           │   ├── radar-map.component.html
│           │   └── radar-map.component.scss
│           │
│           ├── radar-toolbar/          ← Toolbar fluttuante + filtri (FASE 5)
│           │   ├── radar-toolbar.component.ts
│           │   ├── radar-toolbar.component.html
│           │   └── radar-toolbar.component.scss
│           │
│           └── radar-sidebar/          ← Sidebar 30% + carousel + entità (FASE 6)
│               ├── radar-sidebar.component.ts
│               ├── radar-sidebar.component.html
│               └── radar-sidebar.component.scss
```

---

## Modifiche Tecniche e Ottimizzazioni di Performance (Angular 21)

### 1. Integrazione `rxResource` per lo Stato Asincrono
Al posto della tradizionale chiamata tramite `forkJoin(...).subscribe(...)` e la gestione manuale del flag `isLoading = signal(false)`, lo store centralizzato [`state.service.ts`](file:///c:/Users/lucag/Documents/Dashboard%20finance/frontend/src/app/services/state.service.ts) utilizza il costrutto nativo `rxResource` di Angular 21. Sfruttando i segnali reattivi `.isLoading()`, `.value()` ed `.error()`, le richieste HTTP pendenti vengono annullate automaticamente dal runtime di Angular se l'utente modifica rapidamente e ripetutamente i filtri o le date, azzerando i memory leak e minimizzando il carico sul server.

### 2. Circuito di Auto-Fallback Resiliente
Qualora le API REST reali su `/api/articles` o `/api/countries` restituiscano un errore (causato da downtime del backend o dalle quote LLM superate), un operatore `catchError` cattura l'eccezione, logga l'accaduto ed effettua in tempo reale uno switch logico configurando il segnale `useMockSignal` su `true`. Questo reindirizza istantaneamente e in modo trasparente l'applicazione verso i mock locali pre-caricati da `RSS.txt`, garantendo la continuità operativa dell'interfaccia.

### 3. Ottimizzazione della Memoria Vector per GeoJSON da 14.6 MB
Il caricamento del file `countries.geo.json` (14.6 MB) e il relativo parsing tramite `L.geoJSON()` avvengono **una sola volta** all'inizializzazione del componente mappa.
* **Divieto di Ricostruzione:** È vietato svuotare, distruggere o rigenerare il layer cartografico dei paesi. I filtri Toolbar scorrono un dizionario di vettori pre-esistenti (`countryLayersMap`) aggiornando i colori sui nodi Leaflet esistenti tramite il metodo nativo `.setStyle()`. Questo garantisce aggiornamenti a 60fps esenti da garbage collection massiva.
* **Non-Blocking Bootstrap:** Il parsing iniziale dei poligoni viene dilazionato in batch tramite `requestAnimationFrame` per scongiurare il congelamento del thread della UI. Un overlay grafico temporaneo (`App Bootstrapping Overlay`) intrattiene visivamente l'utente fino al completamento.

### 4. Mappa Multilivello con Doppio Layer per Etichette Geografiche
Per garantire la leggibilità delle scritte geografiche (città, mari, confini testuali) al di sopra dei poligoni geometrici colorati con pattern hatching, configuriamo un sistema a doppio layer:
* **Base Layer:** Mappa scura senza etichette (`dark_nolabels`) caricata direttamente sullo sfondo del container.
* **Overlays Layer:** Poligoni del GeoJSON configurati sul default pane (`overlayPane` con z-index 400).
* **Labels Layer:** Caricamento delle sole etichette (`dark_only_labels`) su un pane custom (`labelsPane`) configurato forzatamente a `zIndex: 650` con `pointer-events: none` in modo da non intercettare i click destinati ai marker o ai poligoni sottostanti.

### 5. Isolamento dell'Hatching in una Direttiva Condivisa
La logica di iniezione dei pattern SVG geometrici per le 6 categorie geopolitiche è isolata in [`shared/directives/leaflet-hatch.directive.ts`](file:///c:/Users/lucag/Documents/Dashboard%20finance/frontend/src/app/shared/directives/leaflet-hatch.directive.ts). Il componente `radar-map` si limita a fungere da contenitore logico pulito, delegando le manipolazioni dirette del DOM SVG alla direttiva tramite l'attributo `[appLeafletHatch]`.

### 6. Isolamento Radicale dei Colori (Ban dei Codici HEX nei Componenti)
Nessun file TypeScript o foglio stile locale dei componenti (`radar-map`, `radar-toolbar`, `radar-sidebar`) può contenere codici colore esadecimali (HEX). Tutti i colori geopolitici ed estetici dell'interfaccia Palantir sono centralizzati nel file globale [`styles.scss`](file:///c:/Users/lucag/Documents/Dashboard%20finance/frontend/src/styles.scss) sotto forma di CSS Custom Properties (`--color-*`). I componenti interrogano queste proprietà a runtime via `var()` nei fogli SCSS o tramite `getComputedStyle()` in TypeScript.

---

## FASE 0 — Prerequisiti e Verifica Ambiente

> **Obiettivo:** Garantire l'ambiente operativo prima di scrivere codice. ~5 min.
> **Stato:** `[x]`

### 0.1 Verifica Versioni

```bash
cd radar/frontend
node --version      # deve essere >= 20.x
npm --version       # deve essere >= 10.x
npx ng version      # deve mostrare Angular CLI 21.x
```

### 0.2 Verifica Assets Critici

```bash
# GeoJSON locale — deve esistere (14.6 MB)
ls src/assets/data/countries.geo.json

# PrimeNG installato
ls node_modules/primeng/package.json

# Leaflet + cluster installati
ls node_modules/leaflet/package.json
ls node_modules/leaflet.markercluster/package.json
```

### 0.3 Build di Sanità Pre-Sviluppo

```bash
npm run build -- --configuration=production
# ATTESO: dist/radar-frontend/browser/index.html esiste
```

> **⚠️ BLOCCANTE:** Se il file `src/assets/data/countries.geo.json` non esiste, non procedere.
> Il file è già presente nel progetto (14.6 MB). NON scaricarlo da CDN esterni.

---

## FASE 1 — Design System Palantir (`styles.scss`)

> **File:** [`frontend/src/styles.scss`](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/styles.scss)
> **Stato:** `[x]`

### 1.1 Reset Globale e Tipografia

```scss
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  width: 100%;
  height: 100%;
  overflow: hidden;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: #0a0a0f;
}
```

### 1.2 CSS Custom Properties — Palette Palantir Immutabile

```scss
:root {
  // ─── SFONDI ─────────────────────────────────────────────────────────────────
  --color-bg-primary:     #0a0a0f;   // Nero profondo mappa
  --color-bg-secondary:   #0d1117;   // Sidebar e pannelli
  --color-bg-card:        #161b22;   // Card notizie
  --color-bg-overlay:     rgba(10, 10, 15, 0.95);
  --color-bg-toolbar:     rgba(13, 17, 23, 0.90);

  // ─── BORDI ──────────────────────────────────────────────────────────────────
  --color-border-primary: rgba(0, 212, 255, 0.12);
  --color-border-accent:  rgba(0, 212, 255, 0.40);
  --color-border-card:    rgba(0, 212, 255, 0.08);

  // ─── TESTO ──────────────────────────────────────────────────────────────────
  --color-text-primary:   #e6edf3;
  --color-text-secondary: #8b949e;
  --color-text-muted:     #484f58;
  --color-text-accent:    #58a6ff;

  // ─── CATEGORIE — IMMUTABILI (usate da hatching SVG, marker, badge) ───────
  --color-nucleare:       #FF6B35;
  --color-elettronica:    #00D4FF;
  --color-chip:           #7B2FBE;
  --color-acqua:          #0080FF;
  --color-energia:        #FFD700;
  --color-infrastrutture: #4CAF50;

  // ─── SENTIMENT ──────────────────────────────────────────────────────────────
  --color-sentiment-pos:  #3fb950;
  --color-sentiment-neu:  #8b949e;
  --color-sentiment-neg:  #f85149;

  // ─── ANIMAZIONI ─────────────────────────────────────────────────────────────
  --transition-smooth: cubic-bezier(0.4, 0, 0.2, 1);
  --transition-fast:   0.15s var(--transition-smooth);
  --transition-medium: 0.35s var(--transition-smooth);
  --transition-slow:   0.6s var(--transition-smooth);

  // ─── LAYOUT ─────────────────────────────────────────────────────────────────
  --sidebar-width:     30vw;
  --sidebar-min-width: 340px;
  --toolbar-height:    56px;
  --z-toolbar:         900;
  --z-sidebar:         1000;
}
```

### 1.3 Import PrimeNG + Leaflet

```scss
// PrimeNG — tema dark compatibile
@import 'primeng/resources/themes/lara-dark-blue/theme.css';
@import 'primeng/resources/primeng.css';
@import 'primeicons/primeicons.css';

// Leaflet + Cluster
@import 'leaflet/dist/leaflet.css';
@import 'leaflet.markercluster/dist/MarkerCluster.css';
@import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
```

### 1.4 Override Leaflet e Pane Estetici

```scss
.leaflet-container {
  background: var(--color-bg-primary) !important;
  font-family: 'Inter', sans-serif !important;
}

// Stile Pane Custom per le Etichette Mappa (Labels Overlay Pane)
// Posizionato SOPRA i poligoni ma sotto i marker operativi
.leaflet-pane.leaflet-labelsPane-pane {
  z-index: 650 !important;
  pointer-events: none !important;
}

// Transizioni zoom OBBLIGATORIE (Regola 5 ECC)
.leaflet-overlay-pane svg path.country-fill {
  transition: fill-opacity 0.4s ease-in-out;
}
.leaflet-marker-pane {
  transition: opacity 0.3s ease-in-out;
}

// Cluster Radar — stile glassmorphism
.radar-cluster {
  background: rgba(0, 212, 255, 0.12);
  border: 1.5px solid rgba(0, 212, 255, 0.55);
  border-radius: 50%;
  backdrop-filter: blur(8px);

  .cluster-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    color: var(--color-elettronica);
    font-size: 0.8125rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
  }
}

// Marker puntuale
.marker-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  font-size: 18px;
  filter: drop-shadow(0 0 8px rgba(0, 212, 255, 0.35));
  transition: transform var(--transition-fast);
  cursor: pointer;
  &:hover { transform: scale(1.25); }
}

// Hatching zoom-out: nascondi marker
.zoom-out-mode .leaflet-marker-pane {
  opacity: 0;
  pointer-events: none;
}
```

---

## FASE 2 — Modelli TypeScript

> **File:** [`frontend/src/app/models/article.model.ts`](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/app/models/article.model.ts)
> **Stato:** `[x]`

### 2.1 Tipi e Interfacce

```typescript
export type PrimaryCategory =
  | 'Nucleare'
  | 'Elettronica'
  | 'Chip'
  | 'Acqua'
  | 'Energia'
  | 'Infrastrutture';

export type Sentiment = 'Positivo' | 'Neutrale' | 'Negativo';

// ─── ARTICOLO — allineato a GeopoliticalArticleSchema Pydantic ────────────────
export interface Article {
  id:                       number;
  title:                    string;
  summary:                  string;
  published_at:             string;           // 'YYYY-MM-DD'
  source_url:               string;
  country_code:             string;           // ISO Alpha-2, 'XX' = fallback
  latitude:                 number;
  longitude:                number;
  primary_category:         PrimaryCategory;
  sentiment:                Sentiment;
  relevance_level:          number;           // 1–5
  companies_involved:       string[];         // da array_agg backend
  tags:                     string[];         // da array_agg backend
  infrastructural_entities: string[];         // Asset fisici (es. ["Centrale Zaporizhzhia"])
}

// ─── RIEPILOGO PAESE — per hatching SVG e click-nazione ──────────────────────
export interface CountrySummary {
  country_code:  string;
  categories:    PrimaryCategory[];
  article_count: number;
}

// ─── FILTRI ATTIVI ─────────────────────────────────────────────────────────────
export interface ArticleFilters {
  date:             string;               // 'YYYY-MM-DD'
  sentiment?:       Sentiment | null;
  relevance_level?: number | null;        // 1–5, null = tutti
}
```

---

## FASE 3 — Servizi HTTP, Mock e rxResource Store

> **Stato:** `[NEW]`

### 3.1 `app.config.ts` — Provider Globali (Zoneless Abilitato)

```typescript
import { ApplicationConfig, provideExperimentalZonelessChangeDetection } from '@angular/core';
import { provideHttpClient }       from '@angular/common/http';
import { provideAnimationsAsync }  from '@angular/platform-browser/animations/async';

export const appConfig: ApplicationConfig = {
  providers: [
    provideExperimentalZonelessChangeDetection(),
    provideHttpClient(),
    provideAnimationsAsync(),
  ]
};
```

### 3.2 `article-mock.service.ts` — 9 Articoli da Fonti RSS Reali

```typescript
import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { Article, CountrySummary, PrimaryCategory } from '../models/article.model';

const TODAY = new Date().toISOString().split('T')[0];

export const MOCK_ARTICLES: Article[] = [
  {
    id: 1,
    title: 'TSMC Dresden fab begins production of 28nm automotive chips',
    summary: 'TSMC\'s first European fab in Saxony begins mass production, backed by €5B EU funding. Germany aims for 20% of global chip output by 2030.',
    published_at: TODAY,
    source_url: 'https://www.theguardian.com/technology/2026/tsmc-dresden',
    country_code: 'DE', latitude: 51.0504, longitude: 13.7373,
    primary_category: 'Chip', sentiment: 'Positivo', relevance_level: 4,
    companies_involved: ['TSMC', 'Infineon', 'Bosch', 'NXP'],
    tags: ['Chip', 'Semiconduttori', 'Germania', 'Europa', 'Automotive'],
    infrastructural_entities: ['TSMC Dresden Fab', 'Silicon Saxony Campus'],
  },
  {
    id: 2,
    title: 'IAEA confirms cooling system stable at Zaporizhzhia nuclear plant',
    summary: 'UN inspectors report stable conditions but warn of ongoing military risks within the exclusion zone. Emergency generators remain on standby.',
    published_at: TODAY,
    source_url: 'https://feeds.bbci.co.uk/news/world/2026/zaporizhzhia',
    country_code: 'UA', latitude: 47.5083, longitude: 34.3981,
    primary_category: 'Nucleare', sentiment: 'Neutrale', relevance_level: 5,
    companies_involved: ['IAEA', 'Energoatom', 'Rosatom'],
    tags: ['Nucleare', 'IAEA', 'Ucraina', 'Sicurezza', 'Zaporizhzhia'],
    infrastructural_entities: ['Centrale Nucleare di Zaporizhzhia', 'Sito di stoccaggio combustibile esaurito'],
  },
  {
    id: 3,
    title: 'TAP pipeline sets record gas flow into Southern Europe',
    summary: 'The Trans-Adriatic Pipeline reached its annual capacity limit of 10 bcm. SOCAR eyes a doubling of capacity through the TAP expansion project.',
    published_at: TODAY,
    source_url: 'https://rss.dw.com/rdf/rss-en-bus/2026/tap-record',
    country_code: 'AZ', latitude: 40.1431, longitude: 47.5769,
    primary_category: 'Energia', sentiment: 'Positivo', relevance_level: 3,
    companies_involved: ['TAP AG', 'SOCAR', 'BP', 'Statoil'],
    tags: ['Energia', 'Gas', 'Pipeline', 'Europa', 'Azerbaigian'],
    infrastructural_entities: ['Trans-Adriatic Pipeline (TAP)', 'Terminale di Melendugno'],
  },
  {
    id: 4,
    title: 'Italy\'s Po River hits historic low as drought emergency declared',
    summary: 'Northern Italy activates national water emergency plan as Po levels drop 40% below seasonal average. Agriculture in the Po Valley faces critical irrigation shortages.',
    published_at: TODAY,
    source_url: 'https://feeds.npr.org/1004/rss.xml/2026/po-river-drought',
    country_code: 'IT', latitude: 44.9005, longitude: 9.8564,
    primary_category: 'Acqua', sentiment: 'Negativo', relevance_level: 4,
    companies_involved: ['AIPO', 'ANBI', 'Consorzio Irrigazioni Cremonesi'],
    tags: ['Acqua', 'Siccità', 'Italia', 'Crisi Idrica', 'Po'],
    infrastructural_entities: ['Fiume Po', 'Bacino del Lago Maggiore', 'Canale Cavour'],
  },
  {
    id: 5,
    title: 'Huawei\'s Kirin 9020 bypasses ASML sanctions with domestic 7nm process',
    summary: 'Huawei\'s new flagship SoC, produced entirely by SMIC without Dutch lithography, achieves 5G performance comparable to Qualcomm Snapdragon 8 Gen 2.',
    published_at: TODAY,
    source_url: 'https://www.wired.com/feed/tag/ai/latest/2026/huawei-kirin',
    country_code: 'CN', latitude: 22.5431, longitude: 114.0579,
    primary_category: 'Elettronica', sentiment: 'Neutrale', relevance_level: 4,
    companies_involved: ['Huawei', 'SMIC', 'HiSilicon'],
    tags: ['Elettronica', '5G', 'Chip', 'Sanzioni', 'Cina', 'ASML'],
    infrastructural_entities: ['SMIC Shanghai Fab', 'Huawei R&D Campus Shenzhen'],
  },
  {
    id: 6,
    title: 'Poland completes A1 motorway Baltic extension, sealing EU north-south corridor',
    summary: 'The final 50km section of Poland\'s A1 motorway links Gdańsk to the Czech border, creating a strategic freight corridor for EU eastern flank logistics.',
    published_at: TODAY,
    source_url: 'https://www.cnbc.com/id/19794221/device/rss/2026/poland-a1',
    country_code: 'PL', latitude: 51.9194, longitude: 19.1451,
    primary_category: 'Infrastrutture', sentiment: 'Positivo', relevance_level: 2,
    companies_involved: ['GDDKiA', 'Strabag', 'Budimex'],
    tags: ['Infrastrutture', 'Autostrada', 'Polonia', 'UE', 'Logistica'],
    infrastructural_entities: ['Autostrada A1 (Polonia)', 'Porto di Gdańsk', 'Corridoio TEN-T'],
  },
  {
    id: 7,
    title: 'EDF restarts Flamanville EPR reactor after 15-year delay and cost overruns',
    summary: 'France\'s first third-generation nuclear reactor finally reaches full power, marking a milestone for European nuclear energy independence from Russian gas.',
    published_at: TODAY,
    source_url: 'https://finance.yahoo.com/news/rssindex/2026/flamanville-epr',
    country_code: 'FR', latitude: 49.5237, longitude: -1.8787,
    primary_category: 'Nucleare', sentiment: 'Positivo', relevance_level: 5,
    companies_involved: ['EDF', 'Framatome', 'Areva'],
    tags: ['Nucleare', 'Francia', 'EPR', 'Energia', 'EDF'],
    infrastructural_entities: ['Reattore EPR Flamanville 3', 'Centrale Nucleare di Flamanville'],
  },
  {
    id: 8,
    title: 'Intel 18A process node validated for external customers, challenging TSMC N2',
    summary: 'Intel Foundry confirms first external tape-outs on the 18A node with backside power delivery, signaling a credible challenge to TSMC\'s process leadership.',
    published_at: TODAY,
    source_url: 'https://hnrss.org/newest/2026/intel-18a',
    country_code: 'US', latitude: 37.3861, longitude: -122.0839,
    primary_category: 'Chip', sentiment: 'Positivo', relevance_level: 4,
    companies_involved: ['Intel', 'Intel Foundry Services', 'TSMC'],
    tags: ['Chip', 'Semiconduttori', 'USA', 'Intel', 'Foundry', '18A'],
    infrastructural_entities: ['Intel Fab 52 (Arizona)', 'Intel Campus Santa Clara'],
  },
  {
    id: 9,
    title: 'NASA demonstrates space-based solar power transmission to ground station',
    summary: 'NASA\'s SSPP prototype successfully beams 1.5kW via microwave from LEO orbit to a receiving antenna in Mojave Desert, validating the concept for future grid-scale deployment.',
    published_at: TODAY,
    source_url: 'https://www.nasa.gov/technology/feed/2026/space-solar-power',
    country_code: 'US', latitude: 34.9592, longitude: -116.8267,
    primary_category: 'Energia', sentiment: 'Positivo', relevance_level: 3,
    companies_involved: ['NASA', 'Northrop Grumman', 'Caltech'],
    tags: ['Energia', 'Solare', 'Spazio', 'NASA', 'Innovazione'],
    infrastructural_entities: ['SSPP Prototype Satellite', 'Stazione ricevente Mojave Desert'],
  },
];

@Injectable({ providedIn: 'root' })
export class ArticleMockService {
  getArticles(date: string): Observable<Article[]> {
    return of(MOCK_ARTICLES);
  }

  getCountries(date: string): Observable<CountrySummary[]> {
    const grouped = new Map<string, { cats: Set<string>; count: number }>();
    for (const a of MOCK_ARTICLES) {
      const entry = grouped.get(a.country_code) ?? { cats: new Set<string>(), count: 0 };
      entry.cats.add(a.primary_category);
      entry.count++;
      grouped.set(a.country_code, entry);
    }
    const result: CountrySummary[] = [];
    grouped.forEach((v, k) => {
      result.push({
        country_code: k,
        categories: [...v.cats] as PrimaryCategory[],
        article_count: v.count
      });
    });
    return of(result);
  }
}
```

### 3.3 `article.service.ts` — HTTP Production e Circuito di Auto-Fallback

```typescript
import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Article, CountrySummary, ArticleFilters } from '../models/article.model';
import { ArticleMockService } from './article-mock.service';

// Segnale globale esportato per riflettere lo stato del fallback offline (USE_MOCK)
export const useMockSignal = signal<boolean>(false);

@Injectable({ providedIn: 'root' })
export class ArticleService {
  private readonly http = inject(HttpClient);
  private readonly mock = inject(ArticleMockService);

  getArticles(filters: ArticleFilters): Observable<Article[]> {
    if (useMockSignal()) {
      return this.mock.getArticles(filters.date);
    }
    let params = new HttpParams().set('date', filters.date);
    if (filters.sentiment) params = params.set('sentiment', filters.sentiment);
    if (filters.relevance_level != null) {
      params = params.set('relevance_level', filters.relevance_level.toString());
    }
    return this.http.get<Article[]>('/api/articles', { params }).pipe(
      catchError((err) => {
        console.warn('[ArticleService] Errore API backend. Attivazione auto-fallback sui dati mock RSS:', err);
        useMockSignal.set(true); // Auto-fallback trasparente impostando USE_MOCK = true (via signal)
        return this.mock.getArticles(filters.date);
      })
    );
  }

  getCountries(filters: ArticleFilters): Observable<CountrySummary[]> {
    if (useMockSignal()) {
      return this.mock.getCountries(filters.date);
    }
    let params = new HttpParams().set('date', filters.date);
    if (filters.sentiment) params = params.set('sentiment', filters.sentiment);
    if (filters.relevance_level != null) {
      params = params.set('relevance_level', filters.relevance_level.toString());
    }
    return this.http.get<CountrySummary[]>('/api/countries', { params }).pipe(
      catchError((err) => {
        console.warn('[ArticleService] Errore API backend. Attivazione auto-fallback sui dati mock RSS:', err);
        useMockSignal.set(true); // Auto-fallback trasparente impostando USE_MOCK = true (via signal)
        return this.mock.getCountries(filters.date);
      })
    );
  }
}
```

### 3.4 `state.service.ts` — Store Centralizzato con `rxResource`

```typescript
import { Injectable, inject, signal, computed } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { ArticleService } from './article.service';
import { ArticleFilters, Article, CountrySummary } from '../models/article.model';

@Injectable({ providedIn: 'root' })
export class StateService {
  private readonly articleService = inject(ArticleService);

  // Filtri centralizzati come Signal
  readonly filters = signal<ArticleFilters>({
    date: new Date().toISOString().split('T')[0],
    sentiment: null,
    relevance_level: null
  });

  // Resource per gli articoli (autocancel in caso di cambiodata rapido da parte del runtime)
  readonly articlesResource = rxResource({
    request: () => this.filters(),
    loader: ({ request }) => this.articleService.getArticles(request)
  });

  // Resource per i paesi
  readonly countriesResource = rxResource({
    request: () => this.filters(),
    loader: ({ request }) => this.articleService.getCountries(request)
  });

  // Segnali derivati comodi per i componenti
  readonly articles = computed(() => this.articlesResource.value() ?? []);
  readonly countries = computed(() => this.countriesResource.value() ?? []);
  readonly isLoading = computed(() => this.articlesResource.isLoading() || this.countriesResource.isLoading());
  readonly error = computed(() => this.articlesResource.error() || this.countriesResource.error());
}
```

---

## FASE 4 — Componente Mappa (`radar-map`) e Direttiva Hatching

> **Stato:** `[NEW]`

### 4.1 `radar-map.component.ts` — Mappa e Gestione Memoria GeoJSON (One-Shot)

```typescript
import {
  Component, AfterViewInit, OnDestroy, input, output,
  signal, computed, effect, inject
} from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import * as L from 'leaflet';
import 'leaflet.markercluster';
import { Article, CountrySummary } from '../../models/article.model';
import { LeafletHatchDirective } from '../../shared/directives/leaflet-hatch.directive';

@Component({
  selector: 'app-radar-map',
  standalone: true,
  imports: [CommonModule, LeafletHatchDirective],
  templateUrl: './radar-map.component.html',
  styleUrl: './radar-map.component.scss'
})
export class RadarMapComponent implements AfterViewInit, OnDestroy {
  private readonly http = inject(HttpClient);

  // Input
  articles  = input.required<Article[]>();
  countries = input.required<CountrySummary[]>();

  // Output
  markerClicked  = output<Article>();
  clusterClicked = output<Article[]>();
  countryClicked = output<Article[]>();

  // Stato zoom e caricamento GeoJSON
  currentZoomLevel = signal<number>(3);
  isZoomedOut      = computed(() => this.currentZoomLevel() < 5);
  isParsingGeoJson = signal<boolean>(true); // Gestisce l'overlay grafico iniziale

  // Mappe categoria → icona emoji
  private readonly CATEGORY_ICONS: Record<string, string> = {
    'Nucleare':       '☢️',
    'Chip':           '💾',
    'Acqua':          '💧',
    'Energia':        '⚡',
    'Elettronica':    '📡',
    'Infrastrutture': '🏗️',
  };

  // Mappatura delle variabili CSS Custom Properties globali (Isolamento Radicale dei Colori - NO HEX in TS)
  private readonly CATEGORY_CSS_VARS: Record<string, string> = {
    'Nucleare':       '--color-nucleare',
    'Elettronica':    '--color-elettronica',
    'Chip':           '--color-chip',
    'Acqua':          '--color-acqua',
    'Energia':        '--color-energia',
    'Infrastrutture': '--color-infrastrutture',
  };

  // Istanze Leaflet
  private map!: L.Map;
  private clusterGroup!: L.MarkerClusterGroup;
  private geoJsonLayerGroup = L.layerGroup();
  private countryLayersMap = new Map<string, L.Path>(); // Riferimento per il refresh rapido via .setStyle()

  ngAfterViewInit(): void {
    this.initMap();
    this.loadGeoJson();

    // Effect: aggiorna i dati visivi sulla mappa in base a filtri e date
    effect(() => {
      const arts = this.articles();
      const ctrs = this.countries();
      if (this.map && !this.isParsingGeoJson()) {
        this.updateMapData(arts, ctrs);
      }
    });
  }

  private initMap(): void {
    this.map = L.map('radar-map', {
      center: [20, 0],
      zoom: 3,
      zoomControl: false,
      attributionControl: true
    });

    // Doppio Layer - Base Layer scuro (Senza etichette) sotto i poligoni di hatching
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap contributors © CARTO',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(this.map);

    // Doppio Layer - Creazione Pane custom per le etichette geografiche (Labels Overlay Pane)
    // Configurato forzatamente SOPRA i poligoni del GeoJSON
    const labelsPane = this.map.createPane('labelsPane');
    labelsPane.style.zIndex = '650';
    labelsPane.style.pointerEvents = 'none'; // I click passano sotto per poter cliccare i paesi/marker

    // Aggiunta Tile Layer per le sole etichette testuali sul Pane custom
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', {
      pane: 'labelsPane',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(this.map);

    // Cluster Group
    this.clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 40,
      showCoverageOnHover: false,
      iconCreateFunction: (cluster) => {
        const count = cluster.getChildCount();
        return L.divIcon({
          html: `<div class="cluster-icon">${count}</div>`,
          className: 'radar-cluster',
          iconSize: [40, 40]
        });
      }
    });

    this.clusterGroup.on('clusterclick', (e: any) => {
      const childMarkers: L.Marker[] = e.layer.getAllChildMarkers();
      const arts: Article[] = childMarkers
        .map((m: any) => m['articleData'] as Article)
        .filter(Boolean);
      if (arts.length > 0) this.clusterClicked.emit(arts);
    });

    this.map.addLayer(this.clusterGroup);
    this.geoJsonLayerGroup.addTo(this.map);

    // Listener zoom → attiva l'hatching in zoom-out
    this.map.on('zoomend', () => {
      const zoom = this.map.getZoom();
      this.currentZoomLevel.set(zoom);
      this.refreshHatchingStyles();
    });
  }

  private loadGeoJson(): void {
    // Caricamento una tantum dell'asset locale da 14.6 MB per prevenire memory leak
    this.http.get<GeoJSON.FeatureCollection>('assets/data/countries.geo.json')
      .subscribe({
        next: (geoData) => this.parseGeoJsonIncremental(geoData),
        error: (err) => {
          console.error('[RadarMap] Errore caricamento GeoJSON:', err);
          this.isParsingGeoJson.set(false);
        }
      });
  }

  private parseGeoJsonIncremental(geoData: GeoJSON.FeatureCollection): void {
    const features = geoData.features;
    let index = 0;
    const batchSize = 15; // Processa 15 poligoni per frame per mantenere l'interfaccia a 60fps all'avvio

    const processBatch = () => {
      const end = Math.min(index + batchSize, features.length);
      for (let i = index; i < end; i++) {
        const feature = features[i];
        const code = feature.properties?.['ISO_A2'] ?? 'XX';

        const layer = L.geoJSON(feature, {
          style: () => ({
            color: 'rgba(0, 212, 255, 0.15)', // Bordo soft
            weight: 0.5,
            fillOpacity: 0,
            fillColor: 'transparent',
            className: 'country-fill'
          })
        });

        // Click su nazione in hatching-mode
        layer.on('click', () => {
          if (this.isZoomedOut()) {
            const countryArts = this.articles().filter(a => a.country_code === code);
            if (countryArts.length > 0) this.countryClicked.emit(countryArts);
          }
        });

        layer.addTo(this.geoJsonLayerGroup);

        // Memorizza il riferimento al path vettoriale per non distruggere il DOM al cambio filtri
        layer.eachLayer((subLayer) => {
          if (subLayer instanceof L.Path) {
            this.countryLayersMap.set(code, subLayer);
          }
        });
      }

      index = end;
      if (index < features.length) {
        requestAnimationFrame(processBatch); // Esecuzione al frame successivo
      } else {
        this.isParsingGeoJson.set(false); // Nasconde l'App Bootstrapping Overlay
        this.refreshHatchingStyles();
      }
    };

    requestAnimationFrame(processBatch);
  }

  private refreshHatchingStyles(): void {
    const ctrs = this.countries();
    const zoomedOut = this.isZoomedOut();
    const docStyle = getComputedStyle(document.documentElement);

    // Aggiornamento dei layer vettoriali tramite metodo nativo .setStyle() a frame rate pieno
    this.countryLayersMap.forEach((layer, code) => {
      const summary = ctrs.find(c => c.country_code === code);

      if (zoomedOut && summary?.categories?.length) {
        const cat = summary.categories[0];
        // Riferimento al pattern SVG geometrico configurato dalla LeafletHatchDirective
        layer.setStyle({
          fillColor: `url(#hatch-${cat.toLowerCase().replace(/ /g, '-')})`,
          fillOpacity: 0.35,
          color: 'rgba(0, 212, 255, 0.25)'
        });
      } else {
        layer.setStyle({
          fillOpacity: 0,
          color: 'rgba(0, 212, 255, 0.15)'
        });
      }
    });

    if (zoomedOut) {
      this.map.getContainer().classList.add('zoom-out-mode');
    } else {
      this.map.getContainer().classList.remove('zoom-out-mode');
    }
  }

  private updateMapData(articles: Article[], countries: CountrySummary[]): void {
    // Svuota solo i marker del cluster group, senza toccare il GeoJSON di sfondo
    this.clusterGroup.clearLayers();

    for (const article of articles) {
      if (!article.latitude || !article.longitude) continue;

      const emoji = this.CATEGORY_ICONS[article.primary_category] ?? '📍';
      const icon = L.divIcon({
        html: `<div class="marker-icon" title="${article.title}">${emoji}</div>`,
        className: `marker-${article.primary_category.toLowerCase()}`,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });

      const marker = L.marker([article.latitude, article.longitude], { icon });
      (marker as any)['articleData'] = article;
      marker.on('click', () => this.markerClicked.emit(article));
      this.clusterGroup.addLayer(marker);
    }

    this.refreshHatchingStyles();
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }
}
```

### 4.2 `radar-map.component.html`

```html
<div class="radar-map-canvas-container" appLeafletHatch>
  <!-- Canvas Mappa Leaflet -->
  <div id="radar-map" class="radar-map-canvas" [class.blur-active]="isParsingGeoJson()"></div>
  
  <!-- App Bootstrapping Overlay grafico non bloccante -->
  <div class="bootstrapping-overlay" *ngIf="isParsingGeoJson()">
    <div class="loader-content">
      <span class="loader-icon">📡</span>
      <h2>INIZIALIZZAZIONE RADAR</h2>
      <p>Caricamento e ottimizzazione dei confini vettoriali...</p>
      <div class="loader-bar">
        <div class="loader-bar-fill"></div>
      </div>
    </div>
  </div>
</div>
```

### 4.3 `radar-map.component.scss` (Isolamento Radicale: Zero HEX)

```scss
:host {
  display: block;
  width: 100%;
  height: 100%;
}

.radar-map-canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
}

.radar-map-canvas {
  width: 100%;
  height: 100%;
  background: var(--color-bg-primary);
  transition: filter var(--transition-medium);

  &.blur-active {
    filter: blur(8px);
  }
}

.bootstrapping-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--color-bg-overlay);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);

  .loader-content {
    text-align: center;
    color: var(--color-text-primary);
    font-family: 'JetBrains Mono', monospace;

    .loader-icon {
      font-size: 3rem;
      display: inline-block;
      animation: pulse 1.5s infinite ease-in-out;
    }

    h2 {
      font-size: 1.1rem;
      font-weight: 700;
      letter-spacing: 0.25em;
      margin-top: 16px;
      color: var(--color-text-accent);
    }

    p {
      font-size: 0.75rem;
      color: var(--color-text-secondary);
      margin-top: 8px;
    }

    .loader-bar {
      width: 240px;
      height: 2px;
      background: var(--color-border-primary);
      margin: 20px auto 0 auto;
      overflow: hidden;
      position: relative;

      .loader-bar-fill {
        width: 100%;
        height: 100%;
        background: var(--color-text-accent);
        position: absolute;
        left: -100%;
        animation: loading 2s infinite ease-in-out;
      }
    }
  }
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 0.6; }
  50% { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(1); opacity: 0.6; }
}

@keyframes loading {
  0% { left: -100%; }
  50% { left: 0; }
  100% { left: 100%; }
}
```

### 4.4 `shared/directives/leaflet-hatch.directive.ts` — Direttiva Hatching SVG

```typescript
import { Directive, ElementRef, OnInit, inject } from '@angular/core';

@Directive({
  selector: '[appLeafletHatch]',
  standalone: true
})
export class LeafletHatchDirective implements OnInit {
  private readonly el = inject(ElementRef);

  ngOnInit(): void {
    // Individua l'elemento SVG nativo di Leaflet una volta disponibile nel DOM
    const observer = new MutationObserver(() => {
      const svg = this.el.nativeElement.querySelector('.leaflet-overlay-pane svg');
      if (svg) {
        this.injectSvgPatterns(svg as SVGElement);
        observer.disconnect();
      }
    });
    observer.observe(this.el.nativeElement, { childList: true, subtree: true });
  }

  private injectSvgPatterns(svg: SVGElement): void {
    let defs = svg.querySelector('defs');
    if (!defs) {
      defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      svg.insertBefore(defs, svg.firstChild);
    }

    // Definizione dei pattern geometrici associati alle 6 categorie
    const patterns = [
      { id: 'hatch-nucleare', angle: 45, color: 'var(--color-nucleare)' },
      { id: 'hatch-elettronica', angle: 135, color: 'var(--color-elettronica)' },
      { id: 'hatch-chip', angle: 90, color: 'var(--color-chip)' },
      { id: 'hatch-acqua', angle: 0, color: 'var(--color-acqua)' },
      { id: 'hatch-energia', angle: 30, color: 'var(--color-energia)' },
      { id: 'hatch-infrastrutture', angle: 60, color: 'var(--color-infrastrutture)' }
    ];

    patterns.forEach(p => {
      if (defs!.querySelector(`#${p.id}`)) return;

      const pattern = document.createElementNS('http://www.w3.org/2000/svg', 'pattern');
      pattern.setAttribute('id', p.id);
      pattern.setAttribute('width', '12');
      pattern.setAttribute('height', '12');
      pattern.setAttribute('patternUnits', 'userSpaceOnUse');

      // Riempimento di sfondo semitrasparente per dare volume visivo
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('width', '12');
      rect.setAttribute('height', '12');
      rect.setAttribute('fill', p.color);
      rect.setAttribute('opacity', '0.10');
      pattern.appendChild(rect);

      // Linea diagonale geometrica di hatching
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      if (p.angle === 45) {
        line.setAttribute('x1', '0'); line.setAttribute('y1', '12');
        line.setAttribute('x2', '12'); line.setAttribute('y2', '0');
      } else if (p.angle === 135) {
        line.setAttribute('x1', '0'); line.setAttribute('y1', '0');
        line.setAttribute('x2', '12'); line.setAttribute('y2', '12');
      } else if (p.angle === 90) {
        line.setAttribute('x1', '6'); line.setAttribute('y1', '0');
        line.setAttribute('x2', '6'); line.setAttribute('y2', '12');
      } else if (p.angle === 0) {
        line.setAttribute('x1', '0'); line.setAttribute('y1', '6');
        line.setAttribute('x2', '12'); line.setAttribute('y2', '6');
      } else {
        line.setAttribute('x1', '0'); line.setAttribute('y1', '12');
        line.setAttribute('x2', '12'); line.setAttribute('y2', '0');
      }
      line.setAttribute('stroke', p.color);
      line.setAttribute('stroke-width', '1.8');
      line.setAttribute('opacity', '0.65');
      pattern.appendChild(line);

      defs!.appendChild(pattern);
    });
  }
}
```

---

## FASE 5 — Toolbar Fluttuante (`radar-toolbar`)

> **File:** `frontend/src/app/components/radar-toolbar/`
> **Stato:** `[NEW]`

### 5.1 Component TypeScript

```typescript
import { Component, input, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CalendarModule } from 'primeng/calendar';
import { DropdownModule } from 'primeng/dropdown';
import { ProgressBarModule } from 'primeng/progressbar';
import { ArticleFilters, Sentiment } from '../../models/article.model';

@Component({
  selector: 'app-radar-toolbar',
  standalone: true,
  imports: [CommonModule, FormsModule, CalendarModule, DropdownModule, ProgressBarModule],
  templateUrl: './radar-toolbar.component.html',
  styleUrl: './radar-toolbar.component.scss'
})
export class RadarToolbarComponent {
  articleCount = input<number>(0);
  isLoading    = input<boolean>(false);

  filtersChange = output<ArticleFilters>();

  selectedDate      = signal<Date>(new Date());
  selectedSentiment = signal<Sentiment | null>(null);
  selectedRelevance = signal<number | null>(null);

  readonly today = new Date();

  readonly sentimentOptions = [
    { label: 'Tutti i sentiment', value: null },
    { label: '▲ Positivo', value: 'Positivo' },
    { label: '● Neutrale', value: 'Neutrale' },
    { label: '▼ Negativo', value: 'Negativo' },
  ];

  readonly relevanceOptions = [
    { label: 'Tutte le rilevanze', value: null },
    { label: '★★★★★ Critica (5)', value: 5 },
    { label: '★★★★☆ Alta (4)',    value: 4 },
    { label: '★★★☆☆ Media (3)',   value: 3 },
    { label: '★★☆☆☆ Bassa (2)',   value: 2 },
    { label: '★☆☆☆☆ Minima (1)', value: 1 },
  ];

  onFiltersChange(): void {
    this.filtersChange.emit({
      date:            this.selectedDate().toISOString().split('T')[0],
      sentiment:       this.selectedSentiment(),
      relevance_level: this.selectedRelevance()
    });
  }
}
```

### 5.2 `radar-toolbar.component.html`

```html
<div class="radar-toolbar">
  <div class="brand-group">
    <span class="brand-icon">📡</span>
    <span class="brand-title">RADAR</span>
  </div>

  <div class="divider"></div>

  <!-- Calendario PrimeNG -->
  <p-calendar
    [(ngModel)]="selectedDate"
    (onSelect)="onFiltersChange()"
    [maxDate]="today"
    dateFormat="yy-mm-dd"
    [showIcon]="true"
    placeholder="Seleziona Data">
  </p-calendar>

  <!-- Sentiment Dropdown -->
  <p-dropdown
    [options]="sentimentOptions"
    [(ngModel)]="selectedSentiment"
    (onChange)="onFiltersChange()"
    placeholder="Sentiment">
  </p-dropdown>

  <!-- Relevance Dropdown -->
  <p-dropdown
    [options]="relevanceOptions"
    [(ngModel)]="selectedRelevance"
    (onChange)="onFiltersChange()"
    placeholder="Rilevanza">
  </p-dropdown>

  <div class="divider"></div>

  <div class="article-count">
    NOTIZIE RILEVATE: <strong>{{ articleCount() }}</strong>
  </div>

  <!-- Progress Bar per stato caricamento asincrono -->
  <div class="loader-wrapper" *ngIf="isLoading()">
    <p-progressBar mode="indeterminate" styleClass="radar-progress-bar"></p-progressBar>
  </div>
</div>
```

### 5.3 `radar-toolbar.component.scss` (Isolamento Radicale)

```scss
.radar-toolbar {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: var(--z-toolbar);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 20px;
  background: var(--color-bg-toolbar);
  border: 1px solid var(--color-border-primary);
  border-radius: 12px;
  backdrop-filter: blur(20px);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.6),
    0 0 0 1px rgba(0, 212, 255, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
  white-space: nowrap;

  .brand-group {
    display: flex;
    align-items: center;
    gap: 8px;

    .brand-icon { font-size: 1.1rem; }

    .brand-title {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6875rem;
      font-weight: 700;
      letter-spacing: 0.18em;
      color: var(--color-text-accent);
      text-transform: uppercase;
    }
  }

  .divider {
    width: 1px;
    height: 28px;
    background: var(--color-border-card);
  }

  .article-count {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);

    strong {
      color: var(--color-text-accent);
      font-weight: 600;
    }
  }

  .loader-wrapper {
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 3px;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
    overflow: hidden;
  }

  ::ng-deep {
    .p-calendar .p-inputtext,
    .p-dropdown .p-inputtext {
      background: rgba(22, 27, 34, 0.8) !important;
      border-color: var(--color-border-primary) !important;
      color: var(--color-text-primary) !important;
      border-radius: 8px !important;
      font-size: 0.8125rem !important;
    }

    .p-dropdown-panel {
      background: var(--color-bg-secondary) !important;
      border-color: var(--color-border-primary) !important;
    }

    .p-dropdown-item:hover {
      background: rgba(0, 212, 255, 0.08) !important;
    }

    .radar-progress-bar {
      height: 3px !important;
      background-color: transparent !important;
      .p-progressbar-value {
        background-color: var(--color-text-accent) !important;
      }
    }
  }
}
```

---

## FASE 6 — Sidebar Split-Screen (`radar-sidebar`)

> **File:** `frontend/src/app/components/radar-sidebar/`
> **Stato:** `[NEW]`

### 6.1 Component TypeScript

```typescript
import { Component, input, output, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CarouselModule } from 'primeng/carousel';
import { ChipModule } from 'primeng/chip';
import { ButtonModule } from 'primeng/button';
import { Article } from '../../models/article.model';

export type SidebarMode = 'single' | 'cluster';

@Component({
  selector: 'app-radar-sidebar',
  standalone: true,
  imports: [CommonModule, CarouselModule, ChipModule, ButtonModule],
  templateUrl: './radar-sidebar.component.html',
  styleUrl: './radar-sidebar.component.scss'
})
export class RadarSidebarComponent {
  article         = input<Article | null>(null);
  clusterArticles = input<Article[]>([]);
  isOpen          = input<boolean>(false);

  closed = output<void>();

  mode = computed((): SidebarMode => {
    return this.clusterArticles().length > 1 ? 'cluster' : 'single';
  });

  displayArticle = computed(() => {
    return this.clusterArticles().length === 1 ? this.clusterArticles()[0] : this.article();
  });

  sentimentClass = computed(() => {
    const s = this.displayArticle()?.sentiment;
    return s === 'Positivo' ? 'sentiment-pos'
         : s === 'Negativo' ? 'sentiment-neg'
         : 'sentiment-neu';
  });

  clusterSummary = computed(() => {
    const arts = this.clusterArticles();
    const byCategory = new Map<string, number>();
    for (const a of arts) {
      byCategory.set(a.primary_category, (byCategory.get(a.primary_category) ?? 0) + 1);
    }
    return byCategory;
  });

  carouselResponsiveOptions = [
    { breakpoint: '1400px', numVisible: 1, numScroll: 1 }
  ];
}
```

### 6.2 `radar-sidebar.component.html`

```html
<div class="radar-sidebar-wrapper" [class.open]="isOpen()">

  <div class="sidebar-header">
    <div class="header-brand">
      <span class="header-icon">📡</span>
      <span class="sidebar-title">INTELLIGENCE</span>
    </div>
    <button class="close-btn" id="sidebar-close-btn" (click)="closed.emit()">✕</button>
  </div>

  <!-- VISTA SINGOLA NOTIZIA -->
  <div class="sidebar-content" *ngIf="mode() === 'single' && displayArticle()">
    <div class="article-card">
      <div class="card-meta-top">
        <span class="category-badge"
              [style.--cat-color]="'var(--color-' + displayArticle()!.primary_category.toLowerCase() + ')'">
          {{ displayArticle()!.primary_category | uppercase }}
        </span>
        <span class="country-code">{{ displayArticle()!.country_code }}</span>
      </div>

      <div [class]="'sentiment-badge ' + sentimentClass()">
        <span>{{ displayArticle()!.sentiment }}</span>
        <span class="relevance-stars">
          @for (i of [1,2,3,4,5]; track i) {
            <span [class.active]="i <= displayArticle()!.relevance_level">★</span>
          }
        </span>
      </div>

      <h2 class="article-title">{{ displayArticle()!.title }}</h2>
      <p class="article-summary">{{ displayArticle()!.summary }}</p>

      <div class="article-meta">
        <span class="meta-date">{{ displayArticle()!.published_at }}</span>
        <a [href]="displayArticle()!.source_url" target="_blank" rel="noopener" class="source-link">
          Leggi fonte →
        </a>
      </div>

      <!-- Entità Infrastrutturali -->
      <div class="badge-section" *ngIf="displayArticle()!.infrastructural_entities?.length">
        <span class="badge-label">🏭 Entità Infrastrutturali</span>
        <div class="badge-list">
          <p-chip
            *ngFor="let e of displayArticle()!.infrastructural_entities"
            [label]="e"
            styleClass="radar-chip infra-chip">
          </p-chip>
        </div>
      </div>

      <!-- Aziende -->
      <div class="badge-section" *ngIf="displayArticle()!.companies_involved?.length">
        <span class="badge-label">🏢 Aziende</span>
        <div class="badge-list">
          <p-chip
            *ngFor="let c of displayArticle()!.companies_involved"
            [label]="c"
            styleClass="radar-chip company-chip">
          </p-chip>
        </div>
      </div>

      <!-- Tag -->
      <div class="badge-section" *ngIf="displayArticle()!.tags?.length">
        <span class="badge-label">🏷️ Tag</span>
        <div class="badge-list">
          <p-chip
            *ngFor="let t of displayArticle()!.tags"
            [label]="t"
            styleClass="radar-chip tag-chip">
          </p-chip>
        </div>
      </div>
    </div>
  </div>

  <!-- VISTA CLUSTER / MULTI-ARTICOLI -->
  <div class="sidebar-cluster" *ngIf="mode() === 'cluster' && clusterArticles().length > 1">
    <div class="cluster-summary">
      <span class="cluster-count">
        <strong>{{ clusterArticles().length }}</strong> notizie rilevate
      </span>
      <div class="cluster-categories">
        @for (entry of clusterSummary() | keyvalue; track entry.key) {
          <span class="cat-pill"
                [style.--cat-color]="'var(--color-' + entry.key.toLowerCase() + ')'">
            {{ entry.key }}: {{ entry.value }}
          </span>
        }
      </div>
    </div>

    <p-carousel
      [value]="clusterArticles()"
      [numVisible]="1"
      [numScroll]="1"
      [circular]="true"
      [responsiveOptions]="carouselResponsiveOptions"
      styleClass="radar-carousel">
      <ng-template pTemplate="item" let-a>
        <div class="carousel-card">
          <span class="carousel-category"
                [style.--cat-color]="'var(--color-' + a.primary_category.toLowerCase() + ')'">
            {{ a.primary_category }}
          </span>
          <span class="carousel-country">{{ a.country_code }}</span>
          <h3 class="carousel-title">{{ a.title }}</h3>
          <p class="carousel-summary">{{ a.summary }}</p>
          <a [href]="a.source_url" target="_blank" rel="noopener" class="carousel-link">
            Apri Fonte →
          </a>
        </div>
      </ng-template>
    </p-carousel>
  </div>
</div>
```

### 6.3 `radar-sidebar.component.scss` (Isolamento Radicale)

```scss
.radar-sidebar-wrapper {
  position: fixed; top: 0; left: 0;
  width: var(--sidebar-width);
  min-width: var(--sidebar-min-width);
  height: 100vh;
  background: var(--color-bg-overlay);
  border-right: 1px solid var(--color-border-primary);
  backdrop-filter: blur(20px);
  transform: translateX(-100%);
  transition: transform var(--transition-medium);
  z-index: var(--z-sidebar);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--color-border-accent) transparent;

  &.open { transform: translateX(0); }
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-bottom: 1px solid var(--color-border-primary);

  .header-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    .sidebar-title {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.875rem;
      font-weight: 700;
      color: var(--color-text-primary);
      letter-spacing: 0.2em;
    }
  }

  .close-btn {
    background: transparent;
    border: none;
    color: var(--color-text-secondary);
    font-size: 1.1rem;
    cursor: pointer;
    transition: color var(--transition-fast);
    &:hover { color: var(--color-text-accent); }
  }
}

.sidebar-content {
  padding: 24px;
}

.article-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.card-meta-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  .country-code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.875rem;
    color: var(--color-text-accent);
    font-weight: 600;
  }
}

.category-badge {
  display: inline-block;
  padding: 3px 10px; border-radius: 4px;
  font-size: 0.6875rem; font-weight: 700;
  letter-spacing: 0.12em;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--cat-color, var(--color-border-card));
  color: var(--cat-color, var(--color-text-accent));
}

.sentiment-badge {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 4px 12px; border-radius: 6px;
  font-size: 0.75rem; font-weight: 600; width: fit-content;

  &.sentiment-pos { background: rgba(63,185,80,0.10); color: var(--color-sentiment-pos); border: 1px solid rgba(63,185,80,0.22); }
  &.sentiment-neu { background: rgba(139,148,158,0.10); color: var(--color-sentiment-neu); border: 1px solid rgba(139,148,158,0.22); }
  &.sentiment-neg { background: rgba(248,81,73,0.10); color: var(--color-sentiment-neg); border: 1px solid rgba(248,81,73,0.22); }

  .relevance-stars span { color: var(--color-text-muted); font-size: 0.625rem; }
  .relevance-stars span.active { color: var(--color-energia); }
}

.article-title {
  font-size: 1.15rem;
  font-weight: 600;
  line-height: 1.4;
  color: var(--color-text-primary);
}

.article-summary {
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.article-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--color-text-muted);
  border-top: 1px solid var(--color-border-card);
  padding-top: 12px;

  .source-link {
    color: var(--color-text-accent);
    text-decoration: none;
    font-weight: 500;
    &:hover { text-decoration: underline; }
  }
}

.badge-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  .badge-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .badge-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
}

::ng-deep .radar-chip {
  background: rgba(22, 27, 34, 0.8) !important;
  border: 1px solid var(--color-border-card) !important;
  color: var(--color-text-secondary) !important;
  font-size: 0.75rem !important;
  padding: 2px 10px !important;
  border-radius: 4px !important;
}
::ng-deep .infra-chip { color: var(--color-text-accent) !important; }
::ng-deep .company-chip { border-color: rgba(0, 212, 255, 0.12) !important; }

// Stili Vista Cluster
.sidebar-cluster {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.cluster-summary {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-primary);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;

  .cluster-count {
    font-size: 0.875rem;
    color: var(--color-text-primary);
    strong { color: var(--color-text-accent); }
  }

  .cluster-categories {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
}

.cat-pill {
  display: inline-block;
  padding: 2px 8px; border-radius: 3px;
  font-size: 0.6875rem; font-weight: 600;
  background: rgba(255,255,255,0.04);
  color: var(--cat-color, var(--color-text-secondary));
  border: 1px solid var(--cat-color, var(--color-border-card));
}
```

---

## FASE 7 — Shell Orchestrator (`app.ts`)

> **File:** `frontend/src/app/app.ts`, `app.html`, `app.scss`
> **Stato:** `[NEW]`

### 7.1 `app.ts` — Utilizzo di rxResource e Signals (Sradicato forkJoin)

```typescript
import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { StateService } from './services/state.service';
import { Article, ArticleFilters } from './models/article.model';
import { RadarMapComponent }     from './components/radar-map/radar-map.component';
import { RadarToolbarComponent } from './components/radar-toolbar/radar-toolbar.component';
import { RadarSidebarComponent } from './components/radar-sidebar/radar-sidebar.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RadarMapComponent, RadarToolbarComponent, RadarSidebarComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  // Iniezione dello Store Centralizzato
  readonly state = inject(StateService);

  // Signals per la gestione degli elementi selezionati (sidebar)
  selectedArticle = signal<Article | null>(null);
  clusterArticles = signal<Article[]>([]);
  isSidebarOpen   = signal<boolean>(false);

  // computed derivati
  articleCount = computed(() => this.state.articles().length);
  isMapSplit   = computed(() => this.isSidebarOpen());

  onFiltersChange(f: ArticleFilters): void {
    this.closeSidebar();
    this.state.filters.set(f); // Aggiorna i filtri globali → Innesca automaticamente rxResource
  }

  // Click su marker singolo (zoom ≥ 5)
  onMarkerClick(article: Article): void {
    this.selectedArticle.set(article);
    this.clusterArticles.set([article]);
    this.isSidebarOpen.set(true);
  }

  // Click su cluster (zoom ≥ 5)
  onClusterClick(articles: Article[]): void {
    this.selectedArticle.set(articles[0]);
    this.clusterArticles.set(articles);
    this.isSidebarOpen.set(true);
  }

  // Click su nazione (zoom < 5)
  onCountryClick(articles: Article[]): void {
    this.selectedArticle.set(articles[0]);
    this.clusterArticles.set(articles);
    this.isSidebarOpen.set(true);
  }

  closeSidebar(): void {
    this.isSidebarOpen.set(false);
    this.selectedArticle.set(null);
    this.clusterArticles.set([]);
  }
}
```

### 7.2 `app.html`

```html
<!-- Toolbar centrata -->
<app-radar-toolbar
  [articleCount]="articleCount()"
  [isLoading]="state.isLoading()"
  (filtersChange)="onFiltersChange($event)">
</app-radar-toolbar>

<!-- Mappa Leaflet -->
<div class="map-container" [class.split-active]="isMapSplit()">
  <app-radar-map
    [articles]="state.articles()"
    [countries]="state.countries()"
    (markerClicked)="onMarkerClick($event)"
    (clusterClicked)="onClusterClick($event)"
    (countryClicked)="onCountryClick($event)">
  </app-radar-map>
</div>

<!-- Sidebar Split-Screen -->
<app-radar-sidebar
  [article]="selectedArticle()"
  [clusterArticles]="clusterArticles()"
  [isOpen]="isSidebarOpen()"
  (closed)="closeSidebar()">
</app-radar-sidebar>
```

### 7.3 `app.scss`

```scss
:host {
  display: block;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--color-bg-primary);
}

.map-container {
  position: fixed;
  top: 0;
  right: 0;
  width: 100vw;
  height: 100vh;
  transition: width var(--transition-medium);

  &.split-active {
    width: calc(100vw - var(--sidebar-width));
  }
}
```

---

## FASE 8 — `index.html` SEO

> **File:** [`frontend/src/index.html`](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/frontend/src/index.html)
> **Stato:** `[x]`

```html
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>Radar Informativo Globale — Intelligence Dashboard</title>
  <meta name="description"
        content="Dashboard geopolitica per il monitoraggio in tempo reale di eventi nucleari, energetici, tecnologici e infrastrutturali su mappa interattiva in stile operativo.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <meta name="theme-color" content="#0a0a0f">
  <base href="/">
  <link rel="icon" type="image/x-icon" href="favicon.ico">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
</head>
<body>
  <app-root></app-root>
</body>
</html>
```

---

## FASE 9 — Configurazione npm, TypeScript e Proxy Dev

> **Stato:** `[x]`

### 9.1 Installazione Dipendenze

```bash
cd radar/frontend
npm install --legacy-peer-deps
```

### 9.2 `proxy.conf.json` — Proxy per Sviluppo con Backend Reale

```json
{
  "/api": {
    "target": "http://localhost:8000",
    "secure": false,
    "changeOrigin": true,
    "logLevel": "debug"
  }
}
```

---

## FASE 10 — Test Offline con Mock Service

> **Stato:** `[NEW]`

### Checklist Visiva Completa (Verification Loop)

| # | Scenario | Verifica |
|---|----------|---------|
| 1 | Avvio app | Visualizzazione dell'App Bootstrapping Overlay grafico durante il parsing GeoJSON |
| 2 | Avvio app | Sparizione automatica dell'overlay e rendering delle tile scure senza blocchi della UI |
| 3 | Toolbar | Centrata in alto con effetto glassmorphism, font JetBrains Mono e visualizzazione del count |
| 4 | Marker | 9 emoji tematiche visibili (es. 💾 per Chip, ☢️ per Nucleare) |
| 5 | Clustering | I marker USA (2) si raggruppano se la distanza spaziale è inferiore a 40px |
| 6 | Zoom < 5 | Le nazioni associate ai mock (DE, UA, AZ, IT, CN, PL, FR, US) presentano l'hatching SVG |
| 7 | Zoom < 5 | Tutti i marker puntuali e i cluster vengono nascosti (opacity: 0 e pointer-events disabilitati) |
| 8 | Zoom >= 5 | I poligoni di hatching tornano invisibili e compaiono i marker operativi |
| 9 | Etichette | I testi geografici (es. nomi città) rimangono nitidi e leggibili SOPRA i poligoni colorati |
| 10 | Click nazione | Cliccando su una nazione in zoom < 5, la sidebar si apre mostrando il riepilogo e il carosello |
| 11 | Click marker | Cliccando su un marker in zoom >= 5, si apre la sidebar in layout split-screen 70/30 |
| 12 | Sidebar | Transizione split-screen fluida da 350ms con easing cubic-bezier |
| 13 | Sidebar | Sezione "Entità Infrastrutturali" visualizzata con chip dedicati |
| 14 | Sidebar | Campo sentiment colorato coerentemente (es. rosso per Negativo, verde per Positivo) |
| 15 | Rilevanza | Le stelle di rilevanza (1-5) si accendono coerentemente |
| 16 | Carosello | Scorrimento degli articoli multipli in modalità cluster funzionante ed esteticamente premium |
| 17 | Cambio data | La selezione di una data diversa nella toolbar innesca istantaneamente l'aggiornamento |
| 18 | rxResource | Le richieste pendenti precedenti vengono cancellate all'ispezione network se si cambia data rapidamente |
| 19 | Fallback | Simulando l'offline del backend (con endpoint errato), l'applicazione attiva il fallback a mock |
| 20 | Zero HEX | Nessun codice colore esadecimale hardcodato nei file `.ts` o `.scss` dei componenti |
| 21 | GeoJSON | Nessuna richiesta di rete CDN esterna per `countries.geo.json` |

---

## FASE 11 — Integrazione Backend Reale

> **Stato:** `[NEW]`

### 11.1 Switch da Mock a Produzione
Configurare il segnale globale in `article.service.ts` per disattivare il mock preventivo all'avvio:
```typescript
export const useMockSignal = signal<boolean>(false);
```

### 11.2 Avvio Stack Docker
```bash
cd radar
docker compose up --build
```

---

## FASE 12 — Build Produzione e Verifica Docker

> **Stato:** `[NEW]`

```bash
cd radar/frontend
npm run build -- --configuration=production
```

---

## Vincoli ECC — Checklist di Conformità

| Vincolo | Regola ECC | Verifica |
|---------|------------|----------|
| Standalone | Regola 1 | Nessun modulo NgModule importato o definito per i componenti del piano |
| Signals | Regola 2 | Gestione dello stato interamente affidata a `signal` e `computed` |
| GeoJSON locale | Regola 3 | File caricato esclusivamente dal path statico `assets/data/countries.geo.json` |
| Zero HEX | Regola 4 | Nessun colore esadecimale hardcodato nei componenti. Tutto tramite CSS custom properties |
| Transizione zoom | Regola 5 | Dissolvenza di fill-opacity pari a 0.4s configurata in styles.scss |
| Split-screen | Regola 6 | Ridimensionamento mappa 70/30 a 350ms con easing cubic-bezier |
| MaxCluster | Regola 7 | `maxClusterRadius` impostato esattamente a 40 in `radar-map.component.ts` |
| No Hardcoded HTML| Regola 8 | I testi del template sono associati esclusivamente a variabili o segnali TypeScript |
| Legacy peer | Regola 9 | Flag `--legacy-peer-deps` integrato in ogni comando di installazione pacchetti |
| No TODO | AGENTS.md | File di specifiche e sorgenti privi di commenti TODO o segnaposto incompleti |

---

## Tabella Stato Complessivo

| Fase | Descrizione | Stima | Stato |
|------|-------------|-------|-------|
| 0 | Verifica ambiente | 5 min | `[x]` |
| 1 | Design System — styles.scss + Pane configurazione | 30 min | `[x]` |
| 2 | Modelli TypeScript (+ infrastructural_entities) | 15 min | `[x]` |
| 3 | Servizi HTTP + Mock + rxResource Store | 50 min | `[x]` |
| 4 | Mappa Leaflet (One-Shot) + requestAnimationFrame + Hatching Directive | 115 min | `[x]` |
| 5 | Toolbar fluttuante + 3 filtri | 40 min | `[x]` |
| 6 | Sidebar + carousel + infra_entities | 65 min | `[x]` |
| 7 | Shell Orchestrator + rxResource signals | 30 min | `[x]` |
| 8 | index.html SEO (lang IT, meta IT) | 5 min | `[x]` |
| 9 | npm + proxy.conf.json + tsconfig | 10 min | `[x]` |
| 10 | Test offline (22-point checklist) | 30 min | `[x]` |
| 11 | Integrazione backend reale | 30 min | `[x]` |
| 12 | Build produzione + Docker | 20 min | `[x]` |
| **TOTALE** | | **~7.3 ore** | `[x]` |
