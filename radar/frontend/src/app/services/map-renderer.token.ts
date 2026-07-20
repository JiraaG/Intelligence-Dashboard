import { InjectionToken } from '@angular/core';

export type MapRendererId = 'maplibre' | 'leaflet';

/**
 * Risolve il renderer mappa: window override → localStorage → default maplibre.
 * Ops: ``(window as any).__RADAR_MAP_RENDERER__ = 'leaflet'`` oppure
 * ``localStorage.setItem('radar.mapRenderer', 'leaflet')``.
 */
export function resolveMapRenderer(): MapRendererId {
  if (typeof window !== 'undefined') {
    const winFlag = (window as unknown as { __RADAR_MAP_RENDERER__?: string })
      .__RADAR_MAP_RENDERER__;
    if (winFlag === 'leaflet' || winFlag === 'maplibre') {
      return winFlag;
    }
  }
  try {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem('radar.mapRenderer');
      if (stored === 'leaflet' || stored === 'maplibre') {
        return stored;
      }
    }
  } catch {
    /* private mode / SSR */
  }
  return 'maplibre';
}

export const MAP_RENDERER = new InjectionToken<MapRendererId>('MAP_RENDERER', {
  providedIn: 'root',
  factory: resolveMapRenderer,
});
