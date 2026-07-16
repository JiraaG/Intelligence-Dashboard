# Remediation — Spider dezoom / hatching close (2026-07-16)

## Sintomo

Con lo spider (fan emoji) aperto, un singolo tick di dezoom con la rotellina chiudeva le icone. L’utente voleva: tenere spider + sidebar aperti finché lo zoom resta in modalità dettaglio (zoom ≥ 5, senza barre/hatching); chiudere entrambi solo quando compare l’hatching (zoom &lt; 5).

## Causa (runtime + MarkerCluster)

1. `leaflet.markercluster` registra auto-unspiderfy su `zoomstart` → `zoomanim` (e `_noanimationUnspiderfy` su `zoomend` se zoom animation off). Il codice disabilitava solo `_unspiderfyWrapper` (click), lasciando lo zoom-unspiderfy attivo.
2. Il nostro `zoomend` faceva `collapseAllGraphs(true)` solo se `zoom < 5 && !nationOpen`, quindi con nazione aperta **non** chiudeva sidebar/spider al passaggio in hatching.

## Fix

File unico: `radar/frontend/src/app/components/radar-map/radar-map.component.ts` (zero touch `radar-sidebar/**`).

| Pezzo | Comportamento |
|-------|----------------|
| `lastSpiderfyCountry` / `lastSpiderfyCategory` | Settati su spiderfy riuscito; azzerati se `collapseAllGraphs(emitClose)` |
| `disableMarkerClusterMapClickUnspiderfy` | Off anche `_unspiderfyZoomStart`, `_unspiderfyZoomAnim`, `_noanimationUnspiderfy` |
| `zoomend` zoom ≥ 5 + nation open + lastSpiderfy | Re-spiderfy deferito 50ms (refresh gambe) |
| `zoomend` zoom &lt; 5 + nation open + lastSpiderfy | `collapseAllGraphs(true)` → chiude sidebar + fan |
| Guard `lastSpiderfyCategory` | Evita close accidentale durante `fitBounds(maxZoom: 4)` all’open nazione |

`angular.json`: budget initial `maximumError` → `1050kB` (il fix sforava 1MB di ~310B).

## Verifica

- Browser: open US → spider 5 emoji a zoom 6; `setZoom(5)` → emoji + sidebar `open` restano; `setZoom(4)` → hatching, fan assente, sidebar non `open`.
- `git diff --stat -- radar/frontend/src/app/components/radar-sidebar` → vuoto.

## Docs allineati

- `radar/.ecc/rules/frontend.md` Regola 5 + 7
- `radar/.ecc/agents/angular-map-expert.md`
- `radar/.ecc/CLAUDE.md`
- `.agents/AGENTS.md` §5.3
- `plan-audit/active/Implementation_Plan.md` / `Implementation_Plan_Execution.md`
- `plan-audit/scratch/frontend_rules.md` (FE-CL-08, FE-ZM-08) + `frontend_audit.md`

## Restore

Restore point su `refactor/testing`:

```text
git checkout ed3d88f
# oppure
git revert ed3d88f
```

Rollback mirato al solo comportamento zoom: ripristinare il `zoomend` precedente (close solo se `!nationOpen`) e rimuovere lo strip degli handler zoom da `disableMarkerClusterMapClickUnspiderfy` — **non** reintrodurre auto-unspiderfy su click hinterland.
