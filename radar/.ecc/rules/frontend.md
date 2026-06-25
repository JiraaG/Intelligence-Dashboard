# Regole Frontend — Path-Scope: `frontend/**`
> **Scope:** Queste regole si applicano ESCLUSIVAMENTE ai file in `frontend/`.
> Non caricare queste regole durante il lavoro su `backend/` o file Docker.
> **Priorità:** ALTA — questi vincoli sovrascrivono qualsiasi comportamento default dell'agente.

---

## Regola 0: Struttura Build Angular 21 — Cartella `browser/` Obbligatoria

> **⚠️ ATTENZIONE:** A partire da Angular 17+, il comando `ng build` produce un output **doppio livello**.
> La cartella `dist/` ha questa struttura:
> ```
> dist/
> └── [nome-progetto]/
>     ├── browser/    ← FILE STATICI da servire con Nginx (index.html, JS, CSS)
>     └── server/     ← Solo se SSR è abilitato (NON usato in questo progetto)
> ```

**OBBLIGATORIO:** Qualsiasi configurazione che copia o serve i file della build Angular DEVE
puntare a `dist/[nome-progetto]/browser/` e non alla cartella `dist/[nome-progetto]/` radice.

Esempi corretti:
```dockerfile
# Dockerfile: Stage 2 — copia dalla cartella browser/
COPY --from=builder /app/dist/radar-frontend/browser /usr/share/nginx/html
```
```nginx
# nginx.conf: root punta alla directory dove Nginx serve i file
root /usr/share/nginx/html;   # già pre-popolata con il contenuto di browser/
```

**VIETATO:**
```dockerfile
# SBAGLIATO: manca la sotto-cartella browser/
COPY --from=builder /app/dist/radar-frontend /usr/share/nginx/html
```

Quando Angular CLI inizializza un nuovo progetto (es. `ng new radar-frontend`), il nome del
proietto definisce il prefisso della cartella `dist/`. Verificare sempre `angular.json`
→ `projects.[nome].architect.build.options.outputPath` per il valore esatto.

---

## Stack Tecnologico Obbligatorio

| Componente          | Tecnologia Obbligatoria              | VIETATO                               |
|---------------------|--------------------------------------|---------------------------------------|
| Framework           | Angular 21 (Standalone Components)   | Angular < 17, Vue, React              |
| UI Library          | PrimeNG 17+                          | Angular Material, Ant Design, Bootstrap|
| Mappa               | Leaflet 1.9.x                        | Google Maps API, Mapbox (a pagamento) |
| Clustering          | leaflet.markercluster                | Plugin cluster non ufficiali          |
| CSS                 | SCSS con variabili custom + CSS vars | TailwindCSS, Styled-Components        |
| Stato               | Angular Signals                      | NgRx, NGXS, Akita, BehaviorSubject   |
| HTTP                | HttpClient Angular                   | Axios, fetch() raw                    |

---

## Regola 1: Standalone Components Obbligatori

Angular 21 usa Standalone Components. Non creare mai `NgModule` tradizionali.

**OBBLIGATORIO:**
```typescript
@Component({
  selector: 'app-radar-map',
  standalone: true,
  imports: [CommonModule, SidebarModule, CarouselModule, CalendarModule],
  templateUrl: './radar-map.component.html',
  styleUrl: './radar-map.component.scss'
})
export class RadarMapComponent { }
```

**VIETATO:**
```typescript
// NO: NgModule obsoleto in Angular 21
@NgModule({
  declarations: [RadarMapComponent],
  imports: [BrowserModule]
})
export class AppModule { }
```

---

## Regola 2: Signals per lo Stato della Mappa

Non usare `BehaviorSubject`, `Subject` o `EventEmitter` per lo stato UI globale.
Usare esclusivamente `signal()`, `computed()` e `effect()` di Angular 21.

**OBBLIGATORIO:**
```typescript
// Stato reattivo con Signals
selectedDate = signal<string>(new Date().toISOString().split('T')[0]);
articles = signal<Article[]>([]);
selectedArticle = signal<Article | null>(null);
isSidebarOpen = signal<boolean>(false);
currentZoomLevel = signal<number>(3);

// Computed derivati
isZoomedOut = computed(() => this.currentZoomLevel() < 5);
articlesByCountry = computed(() => groupArticlesByCountry(this.articles()));
```

**VIETATO:**
```typescript
// NO: RxJS subject per stato locale (usa Signals invece)
private selectedArticle$ = new BehaviorSubject<Article | null>(null);
```

---

## Regola 3: GeoJSON Esclusivamente Locale

I confini geografici delle nazioni devono sempre essere caricati dal file statico locale.
Non usare CDN esterni, API di terze parti o URL dinamici.

**OBBLIGATORIO:**
```typescript
// Caricamento offline dal file locale in assets/
this.http.get<GeoJSON.FeatureCollection>('assets/data/countries.geo.json')
  .subscribe(geoData => {
    this.initializeCountryLayers(geoData);
  });
```

**VIETATO:**
```typescript
// NO: URL esterno per GeoJSON (rompe l'offline, crea dipendenza esterna)
this.http.get('https://cdn.jsdelivr.net/npm/world-atlas/countries-50m.json')
this.http.get('https://raw.githubusercontent.com/.../countries.geo.json')
```

---

## Regola 4: Palette Colori Palantir (Immutabile)

La palette cromatica dell'interfaccia è fissa e non negoziabile.
Usare sempre le CSS Custom Properties definite in `styles.scss`.

```scss
// frontend/src/styles.scss — Palette Palantir (definita una volta sola)
:root {
  // Sfondi
  --color-bg-primary:       #0a0a0f;   // Nero profondo mappa
  --color-bg-secondary:     #0d1117;   // Sidebar e pannelli
  --color-bg-card:          #161b22;   // Card notizie nella sidebar
  --color-bg-overlay:       rgba(10, 10, 15, 0.95);  // Overlay glassmorphism

  // Bordi e separatori
  --color-border-primary:   rgba(0, 212, 255, 0.15); // Ciano desaturato
  --color-border-accent:    rgba(0, 212, 255, 0.40); // Hover/focus

  // Testo
  --color-text-primary:     #e6edf3;   // Testo principale
  --color-text-secondary:   #8b949e;   // Testo secondario/metadata
  --color-text-accent:      #58a6ff;   // Link e accenti

  // Categorie (per hatching SVG e marker)
  --color-nucleare:         #FF6B35;
  --color-elettronica:      #00D4FF;
  --color-chip:             #7B2FBE;
  --color-acqua:            #0080FF;
  --color-energia:          #FFD700;
  --color-infrastrutture:   #4CAF50;
}
```

---

## Regola 5: Logica Zoom — Hatching e Marker

### Soglia di Zoom

- **Zoom < 5**: Modalità macro — mostra hatching SVG sulle nazioni, nascondi marker
- **Zoom >= 5**: Modalità dettaglio — nascondi hatching (opacity 0), mostra marker con icone

```typescript
// Nel componente mappa — listener sull'evento zoom di Leaflet
this.map.on('zoomend', () => {
  const zoom = this.map.getZoom();
  this.currentZoomLevel.set(zoom);

  if (zoom < 5) {
    this.activateHatchingMode();
  } else {
    this.activateMarkerMode();
  }
});
```

### Transizione CSS Obbligatoria

La transizione tra le due modalità DEVE essere fluida (non un toggle istantaneo):
```scss
.leaflet-overlay-pane svg path.country-fill {
  transition: fill-opacity 0.4s ease-in-out;
}
.leaflet-marker-pane {
  transition: opacity 0.3s ease-in-out;
}
```

---

## Regola 6: Layout Split-Screen 70/30

Il layout split-screen è obbligatorio per la visualizzazione delle notizie.
Non usare modal, overlay o tooltip: usare la sidebar laterale sinistra.

- **Stato idle**: mappa = 100% larghezza
- **Stato attivo** (marker cliccato): sidebar = 30% sinistra, mappa = 70% destra
- **Transizione**: cubic-bezier per smoothness, durata 350ms

La sidebar è implementata con CSS puro + classe Angular attivata via Signal.
Il componente `p-sidebar` di PrimeNG può essere usato come wrapper UI.

---

## Regola 7: Clustering a 40px

Il raggio di clustering dei marker è fisso a **40px**.
Non modificare questo valore senza un task esplicito.

```typescript
const clusterGroup = L.markerClusterGroup({
  maxClusterRadius: 40,  // VALORE FISSO — non modificare
  showCoverageOnHover: false
});
```

---

## Regola 8: Nessun Dato Hardcoded in Template HTML

I dati visualizzati nella sidebar e nelle card devono provenire esclusivamente
dallo stato Angular (Signals). Non inserire testo statico nei template HTML.

**OBBLIGATORIO:**
```html
<h2 class="article-title">{{ selectedArticle()?.title }}</h2>
<p class="article-summary">{{ selectedArticle()?.summary }}</p>
```

**VIETATO:**
```html
<!-- NO: dato hardcoded nel template -->
<h2>Notizia di esempio</h2>
<p>Questo è un placeholder in attesa dei dati reali.</p>
```

---

## Regola 9: Installazione dei Pacchetti tramite NPM (--legacy-peer-deps)

A causa dei potenziali conflitti di compatibilità delle dipendenze tra Angular 21, PrimeNG e Leaflet (in particolare per pacchetti legacy o librerie secondarie come `@angular/cdk`), è **obbligatorio** utilizzare sempre il flag `--legacy-peer-deps` durante l'installazione di qualsiasi pacchetto npm per garantire la coerenza della build e prevenire errori di installazione.

**OBBLIGATORIO:**
```bash
npm install <nome-pacchetto> --legacy-peer-deps
```

Nel Dockerfile del frontend:
```dockerfile
RUN npm install --legacy-peer-deps
```

**VIETATO:**
```bash
# NO: causa conflitti bloccanti di risoluzione peer dependencies
npm install <nome-pacchetto>
npm ci
```

---

## Regola 10: Leaflet + ESBuild — Caricamento via Script Globali

> **⚠️ GOTCHA CRITICO (Angular 21 + @angular/build:application):**
> `leaflet.markercluster` è una libreria UMD che si aggancia a `window.L`.
> Con Angular 21 e il bundler ESBuild, un `import 'leaflet.markercluster'` come side-effect
> in un componente TypeScript crea un namespace Leaflet **separato** dal `window.L`.
> Il plugin non trova `window.L.markerClusterGroup` e lancia `TypeError: L.markerClusterGroup is not a function`.

**SOLUZIONE OBBLIGATORIA:**

**1. Aggiungere in `angular.json` → `projects.radar-frontend.architect.build.options.scripts[]`:**
```json
"scripts": [
  "node_modules/leaflet/dist/leaflet.js",
  "node_modules/leaflet.markercluster/dist/leaflet.markercluster.js"
]
```

**2. Accedere a Leaflet nel componente via `window` (NON con `import * as L`):**
```typescript
// CORRETTO: accesso al global window.L iniettato dagli script
const L = (window as any).L as typeof import('leaflet');

// VIETATO: crea un namespace separato che non si lega al plugin
// import * as L from 'leaflet';
// import 'leaflet.markercluster'; // ← side-effect che non funziona con esbuild
```

**3. Types (package.json devDependencies):**
```json
"@types/leaflet": "^1.9.x",
"@types/leaflet.markercluster": "^1.5.x"
```

I tipi TypeScript vengono usati solo a compile-time, il runtime usa sempre `window.L`.

---

## Criteri di Accettazione Automatici

| Pattern Vietato                                       | Motivo                                              |
|-------------------------------------------------------|-----------------------------------------------------|
| `NgModule` nei componenti Angular                     | Pattern obsoleto in Angular 21                      |
| URL CDN per GeoJSON                                   | Rompe l'offline, dipendenza esterna                 |
| `BehaviorSubject` per stato UI                        | Usare Signals invece                                |
| Colori hardcoded (es. `#ff0000`)                      | Devono usare CSS vars della palette                 |
| `maxClusterRadius` diverso da 40                      | Specifica fissa del PRD                             |
| Modal al posto della sidebar split-screen             | Specifica fissa del PRD                             |
| Testo placeholder statico in HTML                     | Viola la regola di completezza del codice           |
| `COPY dist/[nome]/` senza `/browser` nel Dockerfile   | Angular 21 genera `dist/[nome]/browser/` — path errata causa Nginx 404 |
| `npm install` o `npm ci` senza `--legacy-peer-deps`   | Causa fallimenti di installazione per conflitti di peer dependencies tra Angular 21 e librerie terze |
| `import * as L from 'leaflet'` nel componente         | Con esbuild crea namespace separato, markercluster non funziona |
| `import 'leaflet.markercluster'` side-effect nel componente | Il plugin non trova `window.L` e lancia TypeError  |
