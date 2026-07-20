import { describe, expect, it } from 'vitest';
import { resolveMapRenderer } from './map-renderer.token';

describe('resolveMapRenderer', () => {
  it('defaults to maplibre when no override is set', () => {
    delete (window as unknown as { __RADAR_MAP_RENDERER__?: string }).__RADAR_MAP_RENDERER__;
    try {
      localStorage.removeItem('radar.mapRenderer');
    } catch {
      /* ignore */
    }
    expect(resolveMapRenderer()).toBe('maplibre');
  });

  it('honors window.__RADAR_MAP_RENDERER__', () => {
    (window as unknown as { __RADAR_MAP_RENDERER__: string }).__RADAR_MAP_RENDERER__ = 'leaflet';
    expect(resolveMapRenderer()).toBe('leaflet');
    delete (window as unknown as { __RADAR_MAP_RENDERER__?: string }).__RADAR_MAP_RENDERER__;
  });
});
