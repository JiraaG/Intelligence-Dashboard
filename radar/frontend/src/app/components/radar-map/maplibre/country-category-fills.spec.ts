import { describe, expect, it } from 'vitest';
import {
  clipRingToBbox,
  computeGeometryBbox,
  resolveSplitBbox,
  splitCountryByCategories,
  US_MAINLAND_BBOX,
} from './country-category-fills';

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

    const cats = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
    const legend = ['H', 'G', 'F', 'E', 'D', 'C', 'B', 'A'];
    const parts = splitCountryByCategories(usLike, cats, (c) => `#${c}`, legend);
    expect(parts).toHaveLength(8);
    expect(parts.map((p) => p.properties?.['category'])).toEqual(legend);
    // Solo Polygon (mainland) — niente MultiPolygon isole.
    for (const p of parts) {
      expect(p.geometry?.type).toBe('Polygon');
    }
  });
});
