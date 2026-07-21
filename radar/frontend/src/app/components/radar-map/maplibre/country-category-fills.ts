/**
 * Spezza la geometria di una nazione in N fasce longitudinali (una per tipologia).
 * Ogni colore ricopre la nazione una sola volta — niente pattern ripetuto (barcode).
 *
 * Split bbox: mainland hardcoded US/RU, altrimenti poligono più grande (evita Alaska /
 * oltremare / antimeridiano che schiacciano tutte le fasce in 1–2 colori visibili).
 *
 * Paint: largest + isole significative (≥ 0.5% area largest); US/RU = ∩ mainland bbox.
 * Clip fasce: terra ∩ strip via polygon-clipping — mai fallback rettangolo in mare.
 */

import polygonClipping from 'polygon-clipping';

export type LngLat = [number, number];
export type BBox = [number, number, number, number]; // minLng, minLat, maxLng, maxLat

/** Mainland USA — allineato a fitBounds / centroidi Radar. */
export const US_MAINLAND_BBOX: BBox = [-125.0, 24.396308, -66.93457, 49.384358];
/** Mainland Russia (est fino a 169, senza wrap antimeridiano). */
export const RU_MAINLAND_BBOX: BBox = [19.6389, 41.1856, 169.0, 81.8587];

/** Isole: pezzi MultiPolygon con area ≥ questa frazione del largest. */
export const ISLAND_AREA_RATIO = 0.005;

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

/** Sutherland–Hodgman: clip anello chiuso a bbox axis-aligned (usato per mainland US/RU). */
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

function polygonArea(coordinates: LngLat[][]): number {
  if (!coordinates.length) return 0;
  return ringArea(coordinates[0] as LngLat[]);
}

function listPolygons(geometry: GeoJSON.Geometry): LngLat[][][] {
  if (geometry.type === 'Polygon') return [geometry.coordinates as LngLat[][]];
  if (geometry.type === 'MultiPolygon') return geometry.coordinates as LngLat[][][];
  return [];
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
 * (evita span ~360° da antimeridiano / isole remote grezze).
 * Per il paint reale vedi `paintPolygonsBbox` (largest + isole ≥ soglia).
 */
export function resolveSplitBbox(geometry: GeoJSON.Geometry, countryCode?: string): BBox | null {
  if (countryCode === 'US') return US_MAINLAND_BBOX;
  if (countryCode === 'RU') return RU_MAINLAND_BBOX;
  return largestPolygonBbox(geometry) ?? computeGeometryBbox(geometry);
}

/** Bbox unione dei poligoni da colorare (include isole significative). */
export function paintPolygonsBbox(paint: GeoJSON.Polygon[]): BBox | null {
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;
  for (const poly of paint) {
    const b = computeGeometryBbox(poly);
    if (!b) continue;
    minLng = Math.min(minLng, b[0]);
    minLat = Math.min(minLat, b[1]);
    maxLng = Math.max(maxLng, b[2]);
    maxLat = Math.max(maxLat, b[3]);
  }
  if (!Number.isFinite(minLng)) return null;
  return [minLng, minLat, maxLng, maxLat];
}

/** Poligono di area massima (utile a centroidi / regressione). */
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

function ensureClosedRing(ring: LngLat[]): LngLat[] {
  if (ring.length < 2) return ring;
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) return ring;
  return [...ring, first];
}

function toClippingPolygon(coordinates: LngLat[][]): polygonClipping.Polygon {
  return coordinates.map((ring) => ensureClosedRing(ring as LngLat[]));
}

function stripAsClippingPolygon(strip: BBox): polygonClipping.Polygon {
  const [x0, y0, x1, y1] = strip;
  return [
    [
      [x0, y0],
      [x1, y0],
      [x1, y1],
      [x0, y1],
      [x0, y0],
    ],
  ];
}

function fromClippingMulti(
  mp: polygonClipping.MultiPolygon,
): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  const polys = mp.filter((poly) => poly.length > 0 && poly[0].length >= 4);
  if (polys.length === 0) return null;
  if (polys.length === 1) {
    return { type: 'Polygon', coordinates: polys[0] as LngLat[][] };
  }
  return { type: 'MultiPolygon', coordinates: polys as LngLat[][][] };
}

/**
 * Poligoni da colorare: US/RU ∩ mainland bbox; altrimenti largest + pezzi
 * con area ≥ ISLAND_AREA_RATIO del largest (Sicilia, Sardegna, …).
 */
export function extractPaintPolygons(
  geometry: GeoJSON.Geometry,
  countryCode?: string,
): GeoJSON.Polygon[] {
  const polys = listPolygons(geometry);
  if (polys.length === 0) return [];

  if (countryCode === 'US' || countryCode === 'RU') {
    const mainland = countryCode === 'US' ? US_MAINLAND_BBOX : RU_MAINLAND_BBOX;
    const out: GeoJSON.Polygon[] = [];
    for (const poly of polys) {
      const clipped = clipPolygonToBbox(poly as LngLat[][], mainland);
      if (clipped) out.push({ type: 'Polygon', coordinates: clipped });
    }
    return out;
  }

  let largestArea = 0;
  for (const poly of polys) {
    largestArea = Math.max(largestArea, polygonArea(poly as LngLat[][]));
  }
  if (!(largestArea > 0)) return [];

  const threshold = largestArea * ISLAND_AREA_RATIO;
  const out: GeoJSON.Polygon[] = [];
  for (const poly of polys) {
    if (polygonArea(poly as LngLat[][]) >= threshold) {
      out.push({ type: 'Polygon', coordinates: poly });
    }
  }
  return out;
}

/**
 * True se la geometria è un rettangolo axis-aligned che coincide coi 4 angoli dello strip
 * (sintomo del vecchio fallback “rettangolo in mare”).
 */
export function isPureStripRectangle(geometry: GeoJSON.Geometry, strip: BBox, eps = 1e-4): boolean {
  if (geometry.type !== 'Polygon' || geometry.coordinates.length !== 1) return false;
  const ring = geometry.coordinates[0] as LngLat[];
  const pts =
    ring.length > 1 &&
    ring[0][0] === ring[ring.length - 1][0] &&
    ring[0][1] === ring[ring.length - 1][1]
      ? ring.slice(0, -1)
      : ring.slice();
  if (pts.length !== 4) return false;

  const [x0, y0, x1, y1] = strip;
  const near = (a: number, b: number) => Math.abs(a - b) <= eps;
  const onCorner = (p: LngLat) =>
    (near(p[0], x0) || near(p[0], x1)) && (near(p[1], y0) || near(p[1], y1));
  if (!pts.every(onCorner)) return false;

  const xs = new Set(pts.map((p) => (near(p[0], x0) ? '0' : near(p[0], x1) ? '1' : '?')));
  const ys = new Set(pts.map((p) => (near(p[1], y0) ? '0' : near(p[1], y1) ? '1' : '?')));
  return xs.has('0') && xs.has('1') && ys.has('0') && ys.has('1') && !xs.has('?') && !ys.has('?');
}

/**
 * N fasce verticali (O→E) sul bbox di split; ogni fascia = una tipologia presente.
 * Interseca tutti i paint-polygon (mainland + isole significative) con lo strip.
 * Skip se intersezione vuota — mai rettangolo di fascia in mare.
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
  const paint = extractPaintPolygons(feature.geometry, code || undefined);
  if (paint.length === 0) return [];

  // US/RU: mainland hardcoded. Altri: unione paint (largest + isole ≥ soglia) così
  // le fasce O→E coprono anche isole fuori dal solo largest-polygon bbox.
  const bbox =
    code === 'US' || code === 'RU'
      ? resolveSplitBbox(feature.geometry, code)
      : (paintPolygonsBbox(paint) ?? resolveSplitBbox(feature.geometry, code || undefined));
  if (!bbox) return [];

  const paintMp: polygonClipping.MultiPolygon = paint.map((p) =>
    toClippingPolygon(p.coordinates as LngLat[][]),
  );

  const [minLng, minLat, maxLng, maxLat] = bbox;
  const span = maxLng - minLng;
  if (!(span > 0) || !(maxLat > minLat)) return [];

  const n = sorted.length;
  const out: GeoJSON.Feature[] = [];

  for (let i = 0; i < n; i++) {
    const x0 = minLng + (span * i) / n;
    const x1 = minLng + (span * (i + 1)) / n;
    const strip: BBox = [x0, minLat, x1, maxLat];
    let clippedMp: polygonClipping.MultiPolygon;
    try {
      clippedMp = polygonClipping.intersection(paintMp, stripAsClippingPolygon(strip));
    } catch {
      // Geometrie degeneri / numeriche: skip fascia (no fallback in mare).
      continue;
    }
    const clipped = fromClippingMulti(clippedMp);
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
