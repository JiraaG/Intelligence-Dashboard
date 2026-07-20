/**
 * Spezza la geometria di una nazione in N fasce longitudinali (una per tipologia).
 * Ogni colore ricopre la nazione una sola volta — niente pattern ripetuto (barcode).
 *
 * Split bbox: mainland hardcoded US/RU, altrimenti poligono più grande (evita Alaska /
 * oltremare / antimeridiano che schiacciano tutte le fasce in 1–2 colori visibili).
 */

export type LngLat = [number, number];
export type BBox = [number, number, number, number]; // minLng, minLat, maxLng, maxLat

/** Mainland USA — allineato a fitBounds / centroidi Radar. */
export const US_MAINLAND_BBOX: BBox = [-125.0, 24.396308, -66.93457, 49.384358];
/** Mainland Russia (est fino a 169, senza wrap antimeridiano). */
export const RU_MAINLAND_BBOX: BBox = [19.6389, 41.1856, 169.0, 81.8587];

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function intersectAtX(a: LngLat, b: LngLat, x: number): LngLat {
  const t = Math.abs(b[0] - a[0]) < 1e-12 ? 0 : (x - a[0]) / (b[0] - a[0]);
  return [x, lerp(a[1], b[1], t)];
}

function intersectAtY(a: LngLat, b: LngLat, y: number): LngLat {
  const t = Math.abs(b[1] - a[1]) < 1e-12 ? 0 : (y - a[1]) / (b[1] - a[1]);
  return [lerp(a[0], b[0], t), y];
}

/** Sutherland–Hodgman: clip anello chiuso a bbox axis-aligned. */
export function clipRingToBbox(ring: LngLat[], bbox: BBox): LngLat[] {
  const [minX, minY, maxX, maxY] = bbox;
  let output =
    ring.length > 1 &&
    ring[0][0] === ring[ring.length - 1][0] &&
    ring[0][1] === ring[ring.length - 1][1]
      ? ring.slice(0, -1)
      : ring.slice();

  const edges: Array<{
    inside: (p: LngLat) => boolean;
    intersect: (a: LngLat, b: LngLat) => LngLat;
  }> = [
    { inside: (p) => p[0] >= minX, intersect: (a, b) => intersectAtX(a, b, minX) },
    { inside: (p) => p[0] <= maxX, intersect: (a, b) => intersectAtX(a, b, maxX) },
    { inside: (p) => p[1] >= minY, intersect: (a, b) => intersectAtY(a, b, minY) },
    { inside: (p) => p[1] <= maxY, intersect: (a, b) => intersectAtY(a, b, maxY) },
  ];

  for (const edge of edges) {
    if (output.length === 0) return [];
    const input = output;
    output = [];
    for (let i = 0; i < input.length; i++) {
      const cur = input[i];
      const prev = input[(i + input.length - 1) % input.length];
      const curIn = edge.inside(cur);
      const prevIn = edge.inside(prev);
      if (curIn) {
        if (!prevIn) output.push(edge.intersect(prev, cur));
        output.push(cur);
      } else if (prevIn) {
        output.push(edge.intersect(prev, cur));
      }
    }
  }

  if (output.length < 3) return [];
  const closed: LngLat[] = [...output, output[0]];
  return closed;
}

function clipPolygonToBbox(coordinates: LngLat[][], bbox: BBox): LngLat[][] | null {
  if (!coordinates.length) return null;
  const exterior = clipRingToBbox(coordinates[0] as LngLat[], bbox);
  if (exterior.length < 4) return null;
  const rings: LngLat[][] = [exterior];
  for (let h = 1; h < coordinates.length; h++) {
    const hole = clipRingToBbox(coordinates[h] as LngLat[], bbox);
    if (hole.length >= 4) rings.push(hole);
  }
  return rings;
}

export function computeGeometryBbox(geometry: GeoJSON.Geometry): BBox | null {
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;
  const visit = (coords: unknown): void => {
    if (!Array.isArray(coords) || coords.length === 0) return;
    if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
      const lng = coords[0] as number;
      const lat = coords[1] as number;
      if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;
      minLng = Math.min(minLng, lng);
      maxLng = Math.max(maxLng, lng);
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
      return;
    }
    for (const c of coords) visit(c);
  };
  if (geometry.type === 'GeometryCollection') {
    for (const g of geometry.geometries)
      visit((g as GeoJSON.Geometry & { coordinates?: unknown }).coordinates);
  } else {
    visit((geometry as GeoJSON.Geometry & { coordinates: unknown }).coordinates);
  }
  if (!Number.isFinite(minLng)) return null;
  return [minLng, minLat, maxLng, maxLat];
}

/** Area shoelace assoluta (gradi²) di un anello esterno. */
function ringArea(ring: LngLat[]): number {
  let a = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1];
  }
  return Math.abs(a) / 2;
}

function ringBbox(ring: LngLat[]): BBox | null {
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;
  for (const [lng, lat] of ring) {
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue;
    minLng = Math.min(minLng, lng);
    maxLng = Math.max(maxLng, lng);
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
  }
  if (!Number.isFinite(minLng)) return null;
  return [minLng, minLat, maxLng, maxLat];
}

/** Bbox del poligono di area massima (MultiPolygon → mainland tipico). */
export function largestPolygonBbox(geometry: GeoJSON.Geometry): BBox | null {
  if (geometry.type === 'Polygon') {
    return ringBbox(geometry.coordinates[0] as LngLat[]);
  }
  if (geometry.type === 'MultiPolygon') {
    let best: BBox | null = null;
    let bestArea = -1;
    for (const poly of geometry.coordinates) {
      const ring = poly[0] as LngLat[];
      const area = ringArea(ring);
      if (area > bestArea) {
        bestArea = area;
        best = ringBbox(ring);
      }
    }
    return best;
  }
  return computeGeometryBbox(geometry);
}

/**
 * Bbox su cui allineare le N fasce. US/RU hardcoded; altrimenti largest polygon
 * (evita span ~360° da antimeridiano / isole remote).
 */
export function resolveSplitBbox(geometry: GeoJSON.Geometry, countryCode?: string): BBox | null {
  if (countryCode === 'US') return US_MAINLAND_BBOX;
  if (countryCode === 'RU') return RU_MAINLAND_BBOX;
  return largestPolygonBbox(geometry) ?? computeGeometryBbox(geometry);
}

/** Poligono di area massima (una sola massa continentale — niente isole sparse). */
export function extractLargestPolygon(geometry: GeoJSON.Geometry): GeoJSON.Polygon | null {
  if (geometry.type === 'Polygon') {
    return geometry;
  }
  if (geometry.type === 'MultiPolygon') {
    let best: LngLat[][] | null = null;
    let bestArea = -1;
    for (const poly of geometry.coordinates) {
      const ring = poly[0] as LngLat[];
      const area = ringArea(ring);
      if (area > bestArea) {
        bestArea = area;
        best = poly as LngLat[][];
      }
    }
    return best ? { type: 'Polygon', coordinates: best } : null;
  }
  return null;
}

function clipGeometryToBbox(
  geometry: GeoJSON.Geometry,
  bbox: BBox,
): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  if (geometry.type === 'Polygon') {
    const rings = clipPolygonToBbox(geometry.coordinates as LngLat[][], bbox);
    return rings ? { type: 'Polygon', coordinates: rings } : null;
  }
  if (geometry.type === 'MultiPolygon') {
    const polys: LngLat[][][] = [];
    for (const poly of geometry.coordinates) {
      const rings = clipPolygonToBbox(poly as LngLat[][], bbox);
      if (rings) polys.push(rings);
    }
    if (polys.length === 0) return null;
    if (polys.length === 1) return { type: 'Polygon', coordinates: polys[0] };
    return { type: 'MultiPolygon', coordinates: polys };
  }
  return null;
}

/**
 * N fasce verticali (O→E) sul mainland; ogni fascia = una tipologia presente.
 * Usa solo il poligono più grande (no isole → niente “colori extra” sparsi).
 *
 * @param categoryOrder Ordine stabile (es. legenda); default alfabetico.
 */
export function splitCountryByCategories(
  feature: GeoJSON.Feature,
  categories: string[],
  colorFor: (category: string) => string,
  categoryOrder?: readonly string[],
): GeoJSON.Feature[] {
  if (!feature.geometry || categories.length === 0) return [];

  const unique = [...new Set(categories)];
  const sorted = categoryOrder?.length
    ? [...unique].sort((a, b) => {
        const ia = categoryOrder.indexOf(a);
        const ib = categoryOrder.indexOf(b);
        const ra = ia === -1 ? Number.MAX_SAFE_INTEGER : ia;
        const rb = ib === -1 ? Number.MAX_SAFE_INTEGER : ib;
        return ra - rb || a.localeCompare(b);
      })
    : [...unique].sort();

  const code = String(
    feature.properties?.['ISO3166-1-Alpha-2'] ?? feature.properties?.['ISO_A2'] ?? '',
  );
  const bbox = resolveSplitBbox(feature.geometry, code || undefined);
  if (!bbox) return [];

  const largest = extractLargestPolygon(feature.geometry);
  if (!largest) return [];
  // Ritaglia al bbox di split (US/RU mainland); poi spezza quel solo poligono.
  const baseGeom = clipGeometryToBbox(largest, bbox) ?? largest;
  if (baseGeom.type !== 'Polygon') return [];

  const [minLng, minLat, maxLng, maxLat] = bbox;
  const span = maxLng - minLng;
  if (!(span > 0) || !(maxLat > minLat)) return [];

  const n = sorted.length;
  const out: GeoJSON.Feature[] = [];

  for (let i = 0; i < n; i++) {
    const x0 = minLng + (span * i) / n;
    const x1 = minLng + (span * (i + 1)) / n;
    const strip: BBox = [x0, minLat, x1, maxLat];
    let clipped = clipGeometryToBbox(baseGeom, strip);
    // Garantisce 1 fascia per tipologia: se il clip fallisce, usa il rettangolo di fascia
    // intersecato col bbox del mainland (meglio un pezzo rettangolare che perdere il colore).
    if (!clipped) {
      const rings = clipPolygonToBbox(baseGeom.coordinates as LngLat[][], strip);
      if (rings) clipped = { type: 'Polygon', coordinates: rings };
    }
    if (!clipped) continue;
    out.push({
      type: 'Feature',
      properties: {
        fillColor: colorFor(sorted[i]),
        category: sorted[i],
        countryCode: code,
        stripIndex: i,
        stripCount: n,
      },
      geometry: clipped,
    });
  }
  return out;
}
