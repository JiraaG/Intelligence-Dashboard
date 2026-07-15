# Asset geografici (GeoJSON)

Il file `countries.geo.json` (~14 MB) fornisce i confini per hatching e focus nazione.
**Non è versionato su Git** — pin documentato in [`ASSET_LICENSE.md`](./ASSET_LICENSE.md).

Dalla root del monorepo:

```bash
cd radar/frontend
npm run verify-geojson:fetch
```

Chiave proprietà primaria: `ISO3166-1-Alpha-2` (vedi `radar-map.component.ts`).
Senza asset, `npm run build` / Docker FE falliscono al passo verify (o la mappa non disegna confini).
