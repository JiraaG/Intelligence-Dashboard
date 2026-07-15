# countries.geo.json — asset license & pin

## Expected path

`radar/frontend/src/assets/data/countries.geo.json`

(Runtime URL served by Angular: `assets/data/countries.geo.json`)

## Origin

Derivative of **Natural Earth** Admin 0 – Countries at **1:10m**, packaged by
[datasets/geo-countries](https://github.com/datasets/geo-countries).

- Upstream Natural Earth theme: `ne_10m_admin_0_countries`
- Package: `geo-countries` datapackage version **0.2.0**
- Source commit for this pin: `b0b7794e15e7ec4374bf183dd73cce5b92e1c0ae`
  (file path `data/countries.geojson`, commit date 2025-04-10)
- Local pin recorded: 2026-07-15

## Canonical download URL (deterministic)

https://raw.githubusercontent.com/datasets/geo-countries/b0b7794e15e7ec4374bf183dd73cce5b92e1c0ae/data/countries.geojson

After download, save/rename exactly to `countries.geo.json` at the expected path above.

Floating alternatives that may currently match this SHA (do **not** use for automation):

- https://raw.githubusercontent.com/datasets/geo-countries/main/data/countries.geojson
- https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson

## Integrity

- **SHA-256:** `45F41865ADEC4F86602C2CD05C0E29CD8B437614BF2F5B5A863D12463202CAE4`
- **Size:** 14643643 bytes
- **Format:** GeoJSON `FeatureCollection`, 258 features
- Collection `name` field: `ne_10m_admin_0_countries`

## Feature properties (map contract)

Keys present on every feature:

- `name`
- `ISO3166-1-Alpha-2` ← **primary key used by `radar-map`**
- `ISO3166-1-Alpha-3`

`radar-map` resolves country codes as:
`properties['ISO3166-1-Alpha-2'] ?? properties['ISO_A2'] ?? 'XX'`,
with name-based overrides for France/Norway when the code is `-99` / missing.

There is no feature-level `id`, and no `ISO_A2` / `iso_a2` on this file.

## License

- **Natural Earth** base data: public domain (Natural Earth Terms of Use).
- **datasets/geo-countries** redistribution: **ODC-PDDL-1.0**
  (Open Data Commons Public Domain Dedication and License v1.0)
  — see https://opendatacommons.org/licenses/pddl/

Not ODbL. No share-alike obligation for this derivative pin.

## Git / CI policy

This binary is **not** tracked in Git (`radar/.gitignore`).
Obtain via `node scripts/verify-geojson.mjs --fetch` (or manual download of the canonical URL),
then verify SHA-256 before `ng build`.
