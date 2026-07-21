import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  clipRingToBbox,
  computeGeometryBbox,
  extractPaintPolygons,
  ISLAND_AREA_RATIO,
  isPureStripRectangle,
  paintPolygonsBbox,
  resolveSplitBbox,
  splitCountryByCategories,
  US_MAINLAND_BBOX,
} from './country-category-fills';

/** Ray-cast point-in-polygon (anello esterno; lat=y, lng=x). */
function pointInRing(point: [number, number], ring: [number, number][]): boolean {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 0) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function pointInGeometry(point: [number, number], geometry: GeoJSON.Geometry): boolean {
  if (geometry.type === 'Polygon') {
    const rings = geometry.coordinates as [number, number][][];
    if (!pointInRing(point, rings[0])) return false;
    for (let h = 1; h < rings.length; h++) {
      if (pointInRing(point, rings[h])) return false;
    }
    return true;
  }
  if (geometry.type === 'MultiPolygon') {
    return geometry.coordinates.some((poly) =>
      pointInGeometry(point, { type: 'Polygon', coordinates: poly }),
    );
  }
  return false;
}

function countExteriorRings(geometry: GeoJSON.Geometry): number {
  if (geometry.type === 'Polygon') return 1;
  if (geometry.type === 'MultiPolygon') return geometry.coordinates.length;
  return 0;
}

describe('country-category-fills', () => {
  const square: GeoJSON.Feature = {
    type: 'Feature',
    properties: { 'ISO3166-1-Alpha-2': 'XX' },
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [0, 0],
          [10, 0],
          [10, 10],
          [0, 10],
          [0, 0],
        ],
      ],
    },
  };

  it('clips a ring to a vertical half bbox', () => {
    const ring: [number, number][] = [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
      [0, 0],
    ];
    const clipped = clipRingToBbox(ring, [0, 0, 5, 10]);
    expect(clipped.length).toBeGreaterThanOrEqual(4);
    const lngs = clipped.map((p) => p[0]);
    expect(Math.max(...lngs)).toBeLessThanOrEqual(5.0001);
  });

  it('computes bbox for a polygon', () => {
    expect(computeGeometryBbox(square.geometry!)).toEqual([0, 0, 10, 10]);
  });

  it('splits into N non-repeating longitudinal strips', () => {
    const colors = (cat: string) => (cat === 'A' ? '#ff0000' : '#00ff00');
    const parts = splitCountryByCategories(square, ['B', 'A'], colors);
    expect(parts).toHaveLength(2);
    expect(parts[0].properties?.['category']).toBe('A');
    expect(parts[1].properties?.['category']).toBe('B');
    expect(parts[0].properties?.['fillColor']).toBe('#ff0000');
    expect(parts[1].properties?.['fillColor']).toBe('#00ff00');
    expect(parts[0].properties?.['stripCount']).toBe(2);
  });

  it('returns a single strip for one category covering the full bbox', () => {
    const parts = splitCountryByCategories(square, ['Solo'], () => '#abc');
    expect(parts).toHaveLength(1);
    const bbox = computeGeometryBbox(parts[0].geometry!);
    expect(bbox).toEqual([0, 0, 10, 10]);
  });

  it('uses US mainland bbox so antimeridian MultiPolygon still yields N strips', () => {
    // Mainland ~[-125,-67] + Alaska near dateline → full bbox span ~360° (bug precedente).
    const usLike: GeoJSON.Feature = {
      type: 'Feature',
      properties: { 'ISO3166-1-Alpha-2': 'US' },
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [
            [
              [-124, 25],
              [-67, 25],
              [-67, 49],
              [-124, 49],
              [-124, 25],
            ],
          ],
          [
            [
              [-170, 55],
              [-140, 55],
              [-140, 70],
              [-170, 70],
              [-170, 55],
            ],
          ],
          [
            [
              [170, 52],
              [179, 52],
              [179, 54],
              [170, 54],
              [170, 52],
            ],
          ],
        ],
      },
    };

    const full = computeGeometryBbox(usLike.geometry!);
    expect(full).not.toBeNull();
    expect(full![2] - full![0]).toBeGreaterThan(300);
    expect(resolveSplitBbox(usLike.geometry!, 'US')).toEqual(US_MAINLAND_BBOX);

    const paint = extractPaintPolygons(usLike.geometry!, 'US');
    expect(paint.length).toBe(1);
    expect(paint.every((p) => computeGeometryBbox(p)![0] >= US_MAINLAND_BBOX[0] - 1e-6)).toBe(true);

    const cats = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
    const legend = ['H', 'G', 'F', 'E', 'D', 'C', 'B', 'A'];
    const parts = splitCountryByCategories(usLike, cats, (c) => `#${c}`, legend);
    expect(parts).toHaveLength(8);
    expect(parts.map((p) => p.properties?.['category'])).toEqual(legend);
    // Solo mainland (Alaska/dateline esclusi) — niente isole oltremare.
    for (const p of parts) {
      expect(p.geometry?.type).toBe('Polygon');
      const bb = computeGeometryBbox(p.geometry!);
      expect(bb).not.toBeNull();
      expect(bb![0]).toBeGreaterThanOrEqual(US_MAINLAND_BBOX[0] - 1e-3);
      expect(bb![2]).toBeLessThanOrEqual(US_MAINLAND_BBOX[2] + 1e-3);
    }
  });

  it('keeps significant islands (≥ 0.5% largest) and drops tiny scraps', () => {
    // Large area 100; island area 1 (=1%); scrap area 0.01 (=0.01%).
    const archipelago: GeoJSON.Feature = {
      type: 'Feature',
      properties: { 'ISO3166-1-Alpha-2': 'AR' },
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [
            [
              [0, 0],
              [10, 0],
              [10, 10],
              [0, 10],
              [0, 0],
            ],
          ],
          [
            [
              [20, 0],
              [21, 0],
              [21, 1],
              [20, 1],
              [20, 0],
            ],
          ],
          [
            [
              [30, 0],
              [30.1, 0],
              [30.1, 0.1],
              [30, 0.1],
              [30, 0],
            ],
          ],
        ],
      },
    };

    const paint = extractPaintPolygons(archipelago.geometry!);
    expect(paint).toHaveLength(2);
    expect(ISLAND_AREA_RATIO).toBe(0.005);

    const parts = splitCountryByCategories(archipelago, ['Solo'], () => '#0f0');
    expect(parts).toHaveLength(1);
    expect(parts[0].geometry?.type).toBe('MultiPolygon');
    expect(countExteriorRings(parts[0].geometry!)).toBeGreaterThanOrEqual(2);
    expect(pointInGeometry([5, 5], parts[0].geometry!)).toBe(true);
    expect(pointInGeometry([20.5, 0.5], parts[0].geometry!)).toBe(true);
    expect(pointInGeometry([30.05, 0.05], parts[0].geometry!)).toBe(false);
  });

  it('does not bleed fill into a concave bay (anti-bleed)', () => {
    // C aperta a est: baia (7,5) fuori dalla terra.
    const concave: GeoJSON.Feature = {
      type: 'Feature',
      properties: { 'ISO3166-1-Alpha-2': 'CC' },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [0, 0],
            [10, 0],
            [10, 3],
            [3, 3],
            [3, 7],
            [10, 7],
            [10, 10],
            [0, 10],
            [0, 0],
          ],
        ],
      },
    };

    const bay: [number, number] = [7, 5];
    expect(pointInGeometry(bay, concave.geometry!)).toBe(false);

    const parts = splitCountryByCategories(concave, ['W', 'E'], () => '#f00');
    expect(parts.length).toBeGreaterThanOrEqual(1);
    for (const p of parts) {
      expect(pointInGeometry(bay, p.geometry!)).toBe(false);
    }
    // Fascia est (strip 1): non deve essere il rettangolo pieno [5,0]–[10,10] in mare.
    const east = parts.find((p) => p.properties?.['stripIndex'] === 1);
    expect(east).toBeDefined();
    expect(isPureStripRectangle(east!.geometry!, [5, 0, 10, 10])).toBe(false);
  });

  it('skips empty strip∩land instead of emitting a sea rectangle', () => {
    // Terra ovest + isola est (entrambe ≥0.5%): N=3 → fascia centrale in mare → skip.
    const gapped: GeoJSON.Feature = {
      type: 'Feature',
      properties: { 'ISO3166-1-Alpha-2': 'GP' },
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [
            [
              [0, 0],
              [2, 0],
              [2, 10],
              [0, 10],
              [0, 0],
            ],
          ],
          [
            [
              [8, 0],
              [10, 0],
              [10, 2],
              [8, 2],
              [8, 0],
            ],
          ],
        ],
      },
    };
    const parts = splitCountryByCategories(gapped, ['A', 'B', 'C'], () => '#00f');
    expect(parts).toHaveLength(2);
    expect(parts.map((p) => p.properties?.['category'])).toEqual(['A', 'C']);
    for (const p of parts) {
      const idx = Number(p.properties?.['stripIndex']);
      const strip: [number, number, number, number] = [(10 * idx) / 3, 0, (10 * (idx + 1)) / 3, 10];
      expect(isPureStripRectangle(p.geometry!, strip)).toBe(false);
    }
  });
});

describe('country-category-fills sweep (countries.geo.json)', () => {
  const geoPath = resolve(process.cwd(), 'src/assets/data/countries.geo.json');

  it('loads MultiPolygon nations: islands kept, no pure-strip sea fallback', () => {
    if (!existsSync(geoPath)) {
      // Asset gitignored: skip locale senza fetch; CI/Docker usano verify-geojson --fetch.
      console.warn(`[sweep] skip: missing ${geoPath}`);
      return;
    }

    const collection = JSON.parse(readFileSync(geoPath, 'utf8')) as GeoJSON.FeatureCollection;
    const multipoly = collection.features.filter(
      (f) => f.geometry?.type === 'MultiPolygon' && f.properties?.['ISO3166-1-Alpha-2'],
    );
    expect(multipoly.length).toBeGreaterThan(50);

    let withSignificantIslands = 0;

    for (const feature of multipoly) {
      const code = String(feature.properties!['ISO3166-1-Alpha-2']);
      const paint = extractPaintPolygons(feature.geometry!, code);
      expect(paint.length).toBeGreaterThanOrEqual(1);

      if (code !== 'US' && code !== 'RU' && paint.length >= 2) {
        withSignificantIslands += 1;
        const single = splitCountryByCategories(feature, ['Solo'], () => '#abc');
        expect(single.length).toBe(1);
        expect(countExteriorRings(single[0].geometry!)).toBeGreaterThanOrEqual(2);
      }

      const parts = splitCountryByCategories(feature, ['A', 'B'], (c) => `#${c}`);
      const bbox =
        code === 'US' || code === 'RU'
          ? resolveSplitBbox(feature.geometry!, code)
          : (paintPolygonsBbox(paint) ?? resolveSplitBbox(feature.geometry!, code));
      expect(bbox).not.toBeNull();
      const [minLng, minLat, maxLng, maxLat] = bbox!;
      const span = maxLng - minLng;
      const n = 2;
      for (const p of parts) {
        const idx = Number(p.properties?.['stripIndex']);
        const strip: [number, number, number, number] = [
          minLng + (span * idx) / n,
          minLat,
          minLng + (span * (idx + 1)) / n,
          maxLat,
        ];
        // Anti-bleed: mai il rettangolo strip grezzo in mare (vecchio fallback).
        // Su coste irregolari land∩strip non è un rettangolo puro; se lo è, i vertici
        // devono comunque giacere sulla terra paint (clipping corretto su box-like land).
        if (isPureStripRectangle(p.geometry!, strip)) {
          const ring = (p.geometry as GeoJSON.Polygon).coordinates[0] as [number, number][];
          const sample = ring[0];
          const inPaint = paint.some((poly) => pointInGeometry(sample, poly));
          expect(inPaint).toBe(true);
        }
      }
    }

    expect(withSignificantIslands).toBeGreaterThan(10);
  });
});
