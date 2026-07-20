# Frontend — Radar Informativo Globale

SPA Angular 21 del monorepo `radar/`. Documentazione di prodotto: [docs/03_frontend_and_ui.md](../../docs/03_frontend_and_ui.md).

## Prerequisiti

- Node 22+ (allineato al Dockerfile)
- Asset GeoJSON: `src/assets/data/countries.geo.json` (gitignored)
  - Pin/licenza: [`ASSET_LICENSE.md`](./src/assets/data/ASSET_LICENSE.md)
  - Istruzioni: [`README_GEOJSON.txt`](./src/assets/data/README_GEOJSON.txt)

## Script

| Comando | Uso |
|---------|-----|
| `npm start` | Dev server `http://localhost:4200` (proxy `proxy.conf.json` → `localhost:8000`). Con solo Compose base l’API non è pubblicata sull’host: pubblica `:8000`, oppure uvicorn locale, oppure CORS (`CORS_ALLOW_ORIGINS=http://localhost:4200`) contro un API raggiungibile. Stack Docker UI: `http://localhost/` |
| `npm run verify-geojson` | Verifica SHA/schema asset GeoJSON (fail se manca) |
| `npm run verify-geojson:fetch` | Download pinnato + verify |
| `npm run verify-map-renderer` | Gate: dipendenza `maplibre-gl`, host `maplibre/` presente, `MAP_RENDERER` default = `maplibre` |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run test:ci` | Unit test senza watch |
| `npm run build:ci` | Fetch/verify GeoJSON + build production |
| `npm run lint` | Prettier check (locale; **non** eseguito in CI) |
| `npm run build` | Build locale (`prebuild` = verify senza fetch) |

Installazione dipendenze (come in Docker):

```bash
npm ci --legacy-peer-deps
```

**Non esiste** uno script `ng e2e` in questo repository.

## Renderer mappa (Phase I)

- **Default:** MapLibre GL 5.24 (host `src/app/components/radar-map/maplibre/`) — facade `radar-map.component.ts`
- Token: `MAP_RENDERER` in `services/map-renderer.token.ts` (override `window.__RADAR_MAP_RENDERER__` / `localStorage` `radar.mapRenderer`; default `maplibre`)
- Proiezione: `localStorage` `radar.mapProjection` = `globe` \| `mercator`
- **Legacy Leaflet:** host `radar-map/leaflet/` (LEGACY FREEZE). Attivare:

```js
localStorage.setItem('radar.mapRenderer', 'leaflet'); // poi reload
// oppure: window.__RADAR_MAP_RENDERER__ = 'leaflet';
```

## Vincoli

- **Sidebar freeze:** non refactorare `src/app/components/radar-sidebar/**` — eccezioni: toggle Salva + chip `related_countries`
- MapLibre default; Leaflet solo via `MAP_RENDERER=leaflet` (`window.L` / `angular.json` scripts — solo host legacy); stub test in `src/app/testing/leaflet.stub.ts`
- Mock solo con token `MOCK_MODE` (`useValue: true`) — mai fallback silenzioso su errore API
- Spiderfy: path MapLibre = fan custom **senza** MarkerCluster (cerchio n&lt;9 / spirale n≥9, offset pixel); path Leaflet = `maxClusterRadius: 40`, `spiderfyOnMaxZoom: false`
- Nation spiderfy: hub disco compatto (`radar-spider-root`); **tutte** le icone della categoria attiva (niente hard cap 24); size+distanza adattivi
- Focus: pin summary = `preserveZoom`; poligono/toolbar = `fitBounds` (`maxZoom: 4`); `refocusCountry` se stesso codice; hub/pin/spider = `getCountryCentroid` (US/RU/NL mainland); hatching zoom &lt; 5 = `pickCountryCodeAt`
- Overlay: dopo open/close sidebar → `map.resize()` (MapLibre) / `invalidateSize()` (Leaflet legacy)
- Hatching MapLibre: fasce soft O→E (1 colore × tipologia da `map-summary`; mainland US/RU; **non** `fill-pattern` barcode); Leaflet legacy: SVG combo pattern; archi zoom-pin: geometric dash; globe: no `maxBounds`; CSP Nginx apex + `*.basemaps.cartocdn.com`
- **Archi relazioni (Fase H + UI):** MapLibre great-circle (default); legacy Leaflet `relationsPane` z 550; zoom &lt; 5 multicolore; zoom ≥ 5 per-categoria + geometric dash; click → `relationClicked` / `loadRelationArticles` (bilaterale)
- **Notizie Salvate:** contatore toolbar date-agnostic + tooltip nazioni; open = stesso zoom/spiderfy di LETTE/TROVATE; save⇒read, unread⇒unsave

## Docker

Build multi-stage in `Dockerfile` → fetch/verify GeoJSON → immagine Nginx.  
Avvio stack: da `radar/` con `docker compose up --build -d` (UI su porta **80**).
