# GeoJSON — confini mondiali

Il file `countries.geo.json` (~14 MB) **non** è tracciato in Git.

## Procedura consigliata

Dalla root del monorepo:

```bash
cd radar/frontend
npm run verify-geojson:fetch
```

Scarica l’URL pinnato in `ASSET_LICENSE.md`, verifica SHA-256 e valida il `FeatureCollection`.

## Manuale

1. Scarica l’URL canonico da `ASSET_LICENSE.md` (commit pin `datasets/geo-countries`).
2. Salva come `countries.geo.json` in questa cartella.
3. Esegui `npm run verify-geojson` (senza `--fetch`) per controllare SHA + schema.

## Contratto mappa

Proprietà usata da `radar-map`: `ISO3166-1-Alpha-2` (fallback `ISO_A2`).
**Non** caricare da CDN a runtime — solo asset locale.
