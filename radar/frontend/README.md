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
| `npm start` | Dev server `http://localhost:4200` (proxy: `proxy.conf.json` → API) |
| `npm run verify-geojson` | Verifica SHA/schema asset GeoJSON (fail se manca) |
| `npm run verify-geojson:fetch` | Download pinnato + verify |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run test:ci` | Unit test senza watch |
| `npm run build:ci` | Fetch/verify GeoJSON + build production |
| `npm run lint` | Prettier check |
| `npm run build` | Build locale (`prebuild` = verify senza fetch) |

Installazione dipendenze (come in Docker):

```bash
npm ci --legacy-peer-deps
```

**Non esiste** uno script `ng e2e` in questo repository.

## Vincoli

- **Sidebar freeze:** non editare `src/app/components/radar-sidebar/**`
- Leaflet solo via `window.L` (`angular.json` scripts); stub test in `src/app/testing/leaflet.stub.ts`
- Mock solo con token `MOCK_MODE` (`useValue: true`) — mai fallback silenzioso su errore API
- Cluster: `maxClusterRadius: 40`, `spiderfyOnMaxZoom: false`

## Docker

Build multi-stage in `Dockerfile` → fetch/verify GeoJSON → immagine Nginx.  
Avvio stack: da `radar/` con `docker compose up --build -d` (UI su porta **80**).
