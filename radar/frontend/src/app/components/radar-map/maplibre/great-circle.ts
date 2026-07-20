/**
 * Campiona un arco great-circle (o Bézier quadratico lat/lng) tra due punti.
 * Usato per archi relazioni MapLibre (LineString).
 *
 * @param lat1 Latitude punto A
 * @param lng1 Longitude punto A
 * @param lat2 Latitude punto B
 * @param lng2 Longitude punto B
 * @param n Numero di segmenti (≥1); restituisce n+1 punti
 * @param curvature Fattore di curvatura perpendicolare (default 0.2)
 * @returns Coordinate GeoJSON ``[lng, lat]``
 */
export function greatCircle(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
  n: number,
  curvature = 0.2,
): [number, number][] {
  const steps = Math.max(1, Math.floor(n));
  const midLat = (lat1 + lat2) / 2;
  const midLng = (lng1 + lng2) / 2;
  const dLat = lat2 - lat1;
  const dLng = lng2 - lng1;
  const p1Lat = midLat - dLng * curvature;
  const p1Lng = midLng + dLat * curvature;

  const coords: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const lat = (1 - t) * (1 - t) * lat1 + 2 * (1 - t) * t * p1Lat + t * t * lat2;
    const lng = (1 - t) * (1 - t) * lng1 + 2 * (1 - t) * t * p1Lng + t * t * lng2;
    coords.push([lng, lat]);
  }
  return coords;
}

/** Soglia zoom day-view: hatching/fill sotto; pin/archi legacy sopra. */
export const MAP_ZOOM_PIN_THRESHOLD = 5;
