import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { LeafletStub, StubPath, installLeafletStub, uninstallLeafletStub } from './leaflet.stub';

describe('LeafletStub', () => {
  beforeEach(() => {
    installLeafletStub();
  });

  afterEach(() => {
    uninstallLeafletStub();
  });

  it('exposes map helpers without throwing', () => {
    expect(LeafletStub.map).toBeTypeOf('function');
    expect(LeafletStub.marker).toBeTypeOf('function');
    expect(LeafletStub.markerClusterGroup).toBeTypeOf('function');
    expect(LeafletStub.tileLayer).toBeTypeOf('function');
    expect(LeafletStub.geoJSON).toBeTypeOf('function');
    expect(LeafletStub.layerGroup).toBeTypeOf('function');
    expect(LeafletStub.divIcon).toBeTypeOf('function');
    expect(LeafletStub.latLng).toBeTypeOf('function');
    expect(LeafletStub.latLngBounds).toBeTypeOf('function');
    expect(LeafletStub.Path).toBe(StubPath);
    expect(LeafletStub.DomEvent.stopPropagation).toBeTypeOf('function');
  });

  it('supports chainable map/layer APIs used by radar-map', () => {
    const map = LeafletStub.map('stub-map', { center: [20, 0], zoom: 3 });
    const tiles = LeafletStub.tileLayer('https://example.test/{z}/{x}/{y}.png', {
      maxZoom: 19,
    });
    const group = LeafletStub.markerClusterGroup({ maxClusterRadius: 40 });
    const marker = LeafletStub.marker([45.0, 9.0], {
      icon: LeafletStub.divIcon({ className: 'marker-test', iconSize: [44, 44] }),
    });

    expect(() => {
      tiles.addTo(map);
      group.addTo(map);
      group.addLayer(marker);
      map.createPane('labelsPane');
      map.flyTo([45, 9], 6, { animate: true });
    }).not.toThrow();

    expect(map.getZoom()).toBe(6);
    expect(map.hasLayer(group)).toBe(true);
    expect(group.getLayers()).toHaveLength(1);
    expect(group.getAllChildMarkers()[0]).toBe(marker);
  });

  it('builds valid latLng bounds and Path instances for GeoJSON', () => {
    const sw = LeafletStub.latLng(24.396308, -125.0);
    const ne = LeafletStub.latLng(49.384358, -66.93457);
    const bounds = LeafletStub.latLngBounds(sw, ne);

    expect(sw).toEqual({ lat: 24.396308, lng: -125.0 });
    expect(bounds.isValid()).toBe(true);

    const empty = LeafletStub.latLngBounds();
    expect(empty.isValid()).toBe(false);
    empty.extend(sw).extend(ne);
    expect(empty.isValid()).toBe(true);

    const feature = {
      type: 'Feature',
      properties: { 'ISO3166-1-Alpha-2': 'IT' },
      geometry: { type: 'Polygon', coordinates: [] },
    };
    const layer = LeafletStub.geoJSON(feature, {});
    const seen: unknown[] = [];
    layer.eachLayer((sub) => {
      seen.push(sub);
      expect(sub).toBeInstanceOf(LeafletStub.Path);
      expect(sub.getBounds().isValid()).toBe(true);
    });
    expect(seen).toHaveLength(1);

    installLeafletStub();
    expect((window as Window & { L?: unknown }).L).toBe(LeafletStub);
  });
});
