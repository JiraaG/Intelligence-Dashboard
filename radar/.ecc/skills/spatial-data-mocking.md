---
name: spatial-data-mocking
description: >
  Playbook per il testing offline del frontend Angular 21 in totale isolamento dal backend Python.
  Definisce il set di dati mockati, le istruzioni per attivare/disattivare il mock service,
  e i checklist visivi per validare cluster, split-screen, hatching SVG e carousel PrimeNG
  senza necessità del backend attivo o di dati reali da Miniflux/Gemini.
  **Sidebar freeze:** validare il carosello in sola osservazione — non modificare
  `radar-sidebar/**` né sostituire `p-carousel` con `article-list`.
when_to_use:
  - Sviluppo UI/UX offline prima che il backend sia operativo
  - Test di regressione visiva delle funzionalità della mappa
  - Dimostrazione/preview del Radar senza dati reali
  - Debug di layout, CSS e comportamento dei componenti PrimeNG
version: 1.0.0
---

## Quando Usare Questa Skill

Carica questa skill ogni volta che:
- Sviluppi o modifichi componenti del frontend senza backend attivo
- Devi verificare che il pattern hatching SVG si applichi correttamente in zoom-out
- Vuoi testare la transizione split-screen (70%/30%) al click sui marker
- Devi validare il corretto funzionamento del carosello PrimeNG su cluster di notizie
- Stai preparando una demo o screenshot dell'interfaccia

---

## Come Funziona

Il mock service sostituisce le chiamate HTTP reali iniettando dati statici pre-compilati.
L'interfaccia Angular non sa la differenza: riceve lo stesso tipo di dato `Article[]` sia
in modalità mock che in modalità produzione.

**Phase 4:** il toggle è l'injection token esplicito `MOCK_MODE` (`services/mock-mode.token.ts`).
Default `false` in `app.config.ts`. Per offline/demo, fornire `{ provide: MOCK_MODE, useValue: true }`.
**Vietato** l'auto-fallback silenzioso su mock in caso di errore API: l'errore resta visibile
(`StateService.error` → banner toolbar).

```typescript
// frontend/src/app/services/mock-mode.token.ts
export const MOCK_MODE = new InjectionToken<boolean>('MOCK_MODE', {
  providedIn: 'root',
  factory: () => false,
});
```

> **Nota:** In produzione il token è `false`. Un fallimento di rete/API non attiva i mock.

---

## Dataset Mock Completo

Il dataset copre 7 nazioni e 5 categorie diverse per testare tutti gli scenari visivi:

```typescript
// frontend/src/app/mock/mock-articles.data.ts
// Schema allineato a GeopoliticalArticleSchema Pydantic (contratto immutabile)
import { Article } from '../models/article.model';

const TODAY = new Date().toISOString().split('T')[0];

export const MOCK_ARTICLES: Article[] = [
  // --- CLUSTER TEST: Due articoli in Germania (città diverse) ---
  {
    id: 1,
    title: 'TSMC inaugura la prima fab europea a Dresda',
    summary: 'TSMC ha inaugurato in Sassonia il primo impianto produttivo europeo per chip a 28nm. La Germania consolida il suo ruolo di hub semiconductore del continente.',
    published_at: TODAY,
    source_url: 'https://example.com/tsmc-dresden',
    country_code: 'DE',
    latitude: 51.0504,
    longitude: 13.7373,
    companies_involved: ['TSMC', 'Infineon', 'Bosch'],
    tags: ['Chip', 'Semiconduttori', 'Germania', 'Fab'],
    primary_category: 'Chip',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['TSMC Dresden Fab', 'Silicon Saxony Campus']  // ← OBBLIGATORIO
  },
  {
    id: 2,
    title: 'Siemens Energy amplia la rete di trasmissione ad alta tensione in Baviera',
    summary: "Siemens Energy ha completato il potenziamento di 800km di linee di trasmissione nel sud della Germania.",
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
    infrastructural_entities: ['Rete di trasmissione 380kV Baviera', 'Interconnessione DE-AT']  // ← OBBLIGATORIO
  },

  // --- CLUSTER TEST: Due articoli vicini in Ucraina ---
  {
    id: 3,
    title: 'Centrale di Zaporizhzhia: rapporto IAEA sui sistemi di raffreddamento',
    summary: "L'IAEA certifica il funzionamento dei sistemi di backup della centrale. La missione permanente rimane sul posto.",
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
    infrastructural_entities: ['Centrale Nucleare di Zaporizhzhia', 'Sito di stoccaggio combustibile']  // ← OBBLIGATORIO
  },
  {
    id: 4,
    title: "Diga di Kakhovka: progetto di ricostruzione approvato dall'UE",
    summary: "L'Unione Europea ha approvato 2.3 miliardi di euro per la ricostruzione dell'infrastruttura idrica nel sud dell'Ucraina.",
    published_at: TODAY,
    source_url: 'https://example.com/kakhovka-ue',
    country_code: 'UA',
    latitude: 47.3606,
    longitude: 33.4750,
    companies_involved: ['European Commission', 'EBRD'],
    tags: ['Acqua', 'Diga', 'Ucraina', 'Ricostruzione'],
    primary_category: 'Acqua',
    sentiment: 'Positivo',
    relevance_level: 3,
    infrastructural_entities: ['Diga di Kakhovka', 'Serbatoio di Kakhovka']  // ← OBBLIGATORIO
  },

  // --- SINGOLI MARKER: Test hatching multi-categoria ---
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
    infrastructural_entities: ['Impianto di Natanz', 'Impianto di Fordow']  // ← OBBLIGATORIO
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
    primary_category: 'Chip',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['Samsung Fab Hwaseong', 'Samsung R&D Campus Suwon']  // ← OBBLIGATORIO
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
    infrastructural_entities: ['Trans-Adriatic Pipeline (TAP)', 'Terminale di Melendugno', 'Campo di Shah Deniz II']  // ← OBBLIGATORIO
  }
];
```

---

## Come Attivare il Mock Service

### Step 1: Creare il Mock Service

```typescript
// frontend/src/app/services/article-mock.service.ts
import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { Article, CountrySummary, PrimaryCategory } from '../models/article.model';
import { MOCK_ARTICLES } from '../mock/mock-articles.data';

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

### Step 2: Dependency Injection con `MOCK_MODE` (no silent fallback)

```typescript
// frontend/src/app/services/article.service.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map, of } from 'rxjs';
import { Article, CountrySummary, ArticleFilters } from '../models/article.model';
import { parseArticlesDto } from '../models/article.dto';
import { ArticleMockService } from './article-mock.service';
import { MOCK_MODE } from './mock-mode.token';

@Injectable({ providedIn: 'root' })
export class ArticleService {
  private readonly http = inject(HttpClient);
  private readonly mock = inject(ArticleMockService);
  private readonly mockMode = inject(MOCK_MODE);

  getArticles(filters: ArticleFilters): Observable<Article[]> {
    if (this.mockMode) {
      return this.mock.getArticles(filters.date);
    }
    const params = new HttpParams().set('date', filters.date);
    return this.http.get<unknown>('/api/articles', { params }).pipe(
      map((payload) => parseArticlesDto(payload)),
    );
  }

  getCountries(filters: ArticleFilters): Observable<CountrySummary[]> {
    if (this.mockMode) {
      return this.mock.getCountries(filters.date);
    }
    const params = new HttpParams().set('date', filters.date);
    return this.http.get<CountrySummary[]>('/api/countries', { params });
  }
}
```

Offline: in `app.config.ts` (o TestBed) fornire `{ provide: MOCK_MODE, useValue: true }`.
Produzione: `{ provide: MOCK_MODE, useValue: false }` — errori API restano in `StateService.error()`.

---

## Checklist Visivo per Validazione UI

Usa questo checklist per verificare che ogni funzionalità della mappa funzioni correttamente
con i dati mockati prima di connettere il backend reale.

### ✅ Test 1: Hatching SVG in Zoom-Out (livello < 5)

- [ ] La Germania mostra due colori di hatching (Chip + Energia)
- [ ] L'Ucraina mostra due colori di hatching (Nucleare + Acqua)
- [ ] L'Iran mostra hatching singolo (Nucleare)
- [ ] La Corea del Sud mostra hatching singolo (Chip)
- [ ] L'Azerbaijan mostra hatching singolo (Energia)
- [ ] I marker puntuali sono invisibili in zoom-out
- [ ] **Cliccando su Germania in hatching**: sidebar apre con riepilogo 2 notizie (Chip + Energia) [PRD Fase 5]
- [ ] **Cliccando su Ucraina in hatching**: sidebar apre con riepilogo 2 notizie (Nucleare + Acqua) [PRD Fase 5]

### ✅ Test 2: Dissolvenza e Marker in Zoom-In (livello >= 5)

- [ ] L'hatching SVG sfuma gradualmente con CSS transition opacity a 0
- [ ] I marker puntuali compaiono con la loro icona tematica (☢️ 💾 ⚡ 💧)
- [ ] I due marker tedeschi (Dresda Chip e Monaco Energia) sono separati e cliccabili
- [ ] I due marker ucraini (Zaporizhzhia Nucleare e Kakhovka Acqua) **NON** formano un cluster unico — ciascuno appartiene al proprio cluster group di categoria
- [ ] A zoom intermedio (5-9), i marker della stessa categoria in aree vicine si raggruppano in cluster colorati per categoria

### ✅ Test 3: Cluster per Categoria e Carosello PrimeNG

- [ ] I cluster mostrano colori diversi per categoria (Nucleare=arancione, Chip=viola, Acqua=blu, Energia=giallo, Elettronica=ciano, Infrastrutture=verde)
- [ ] Cliccando su un cluster categoria si apre la sidebar sinistra con **solo** gli articoli di quella categoria
- [ ] Il componente `p-carousel` scorre correttamente tra le notizie della categoria selezionata
- [ ] Ogni slide del carousel mostra: titolo, summary, badge tags, link sorgente
- [ ] A zoom >= 17, i marker sono ancora clusterizzati (spiderfy su click per vederli singolarmente)

### ✅ Test 4: Split-Screen 70/30

- [ ] Mappa occupa 100% in stato idle
- [ ] Al click su un marker singolo: mappa si restringe al 70% (destra), sidebar al 30% (sinistra)
- [ ] La transizione è fluida (CSS cubic-bezier 350ms)
- [ ] Il punto cliccato rimane centrato nella porzione di mappa al 70%
- [ ] Cliccando fuori dalla sidebar o sul bottone ✕, mappa torna al 100%

### ✅ Test 5: Filtraggio Temporale p-calendar

- [ ] Il selettore data in alto mostra la data odierna come default
- [ ] Cambiando data a ieri: 0 notizie (dati mock sono del 2026-06-23)
- [ ] Cambiando data al 2026-06-23: tutte le 7 notizie compaiono
- [ ] La transizione dei marker è animata (fade-out vecchi, fade-in nuovi)

---

## Dati Mock per Scenari di Test Aggiuntivi

```typescript
// Aggiungi a MOCK_ARTICLES per testare scenari edge-case
// Notizia senza aziende (companies_involved: [])
{
  id: 8,
  title: 'Siccità record nel bacino del Po: livello minimo storico',
  summary: 'Il fiume Po registra il livello più basso degli ultimi 70 anni. Le regioni padane attivano protocolli di emergenza idrica.',
  published_at: '2026-06-23',
  source_url: 'https://example.com/po-siccita',
  country_code: 'IT',
  latitude: 44.9007,
  longitude: 10.2186,
  companies_involved: [],       // Test: sidebar senza sezione aziende
  tags: ['Acqua', 'Italia', 'Siccità', 'Emergenza'],
  primary_category: 'Acqua'
}
```
