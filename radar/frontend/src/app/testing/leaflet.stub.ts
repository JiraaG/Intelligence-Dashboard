/**
 * Typed stub for `window.L` used by radar-map.
 * Leaflet is loaded via angular.json scripts[], not ES imports, so unit tests
 * must install this stub before RadarMapComponent evaluates `const L = window.L`.
 */

export interface StubLatLng {
  lat: number;
  lng: number;
}

export interface StubLatLngBounds {
  extend(latlng: StubLatLng | StubLatLngBounds): StubLatLngBounds;
  isValid(): boolean;
  getSouthWest(): StubLatLng;
  getNorthEast(): StubLatLng;
}

export type StubEventHandler = (event?: unknown) => void;

export class StubPath {
  options: Record<string, unknown> = {};

  setStyle(style: Record<string, unknown>): this {
    this.options = { ...this.options, ...style };
    return this;
  }

  getBounds(): StubLatLngBounds {
    return createLatLngBounds(createLatLng(0, 0), createLatLng(1, 1));
  }
}

function createLatLng(lat: number, lng: number): StubLatLng {
  return { lat, lng };
}

function createLatLngBounds(
  a?: StubLatLng | [number, number],
  b?: StubLatLng | [number, number],
): StubLatLngBounds {
  const points: StubLatLng[] = [];

  const push = (value: StubLatLng | [number, number] | undefined): void => {
    if (!value) return;
    if (Array.isArray(value)) {
      points.push(createLatLng(value[0], value[1]));
    } else {
      points.push(value);
    }
  };

  push(a);
  push(b);

  const bounds: StubLatLngBounds = {
    extend(latlng: StubLatLng | StubLatLngBounds): StubLatLngBounds {
      if ('lat' in latlng && 'lng' in latlng) {
        points.push(latlng);
      } else {
        points.push(latlng.getSouthWest(), latlng.getNorthEast());
      }
      return bounds;
    },
    isValid(): boolean {
      return points.length > 0;
    },
    getSouthWest(): StubLatLng {
      return points[0] ?? createLatLng(0, 0);
    },
    getNorthEast(): StubLatLng {
      return points[points.length - 1] ?? createLatLng(0, 0);
    },
  };

  return bounds;
}

function createEventTarget() {
  const handlers = new Map<string, StubEventHandler[]>();

  return {
    on(event: string, handler: StubEventHandler) {
      const list = handlers.get(event) ?? [];
      list.push(handler);
      handlers.set(event, list);
      return this;
    },
    once(event: string, handler: StubEventHandler) {
      const wrap: StubEventHandler = (e) => {
        this.off(event, wrap);
        handler(e);
      };
      return this.on(event, wrap);
    },
    off(event: string, handler?: StubEventHandler) {
      if (!handler) {
        handlers.delete(event);
        return this;
      }
      const list = handlers.get(event) ?? [];
      handlers.set(
        event,
        list.filter((h) => h !== handler),
      );
      return this;
    },
    fire(event: string, payload?: unknown) {
      const list = [...(handlers.get(event) ?? [])];
      for (const handler of list) {
        handler(payload);
      }
    },
  };
}

export interface StubMap {
  options: Record<string, unknown>;
  _removed: boolean;
  _layers: unknown[];
  _panes: Record<string, HTMLElement>;
  _zoom: number;
  on(event: string, handler: StubEventHandler): StubMap;
  once(event: string, handler: StubEventHandler): StubMap;
  off(event: string, handler?: StubEventHandler): StubMap;
  fire(event: string, payload?: unknown): void;
  addLayer(layer: unknown): StubMap;
  removeLayer(layer: unknown): StubMap;
  hasLayer(layer: unknown): boolean;
  createPane(name: string): HTMLElement;
  getZoom(): number;
  getContainer(): HTMLElement;
  flyTo(latlng: StubLatLng | [number, number], zoom: number, _opts?: unknown): StubMap;
  fitBounds(_bounds: StubLatLngBounds, _opts?: unknown): StubMap;
  remove(): void;
}

export interface StubMarker {
  options: Record<string, unknown>;
  _latlng: StubLatLng;
  _icon: HTMLElement | null;
  articleData?: unknown;
  isDummy?: boolean;
  realLatLng?: StubLatLng;
  on(event: string, handler: StubEventHandler): StubMarker;
  addTo(map: StubMap): StubMarker;
  getLatLng(): StubLatLng;
  getIcon(): unknown;
  setZIndexOffset(offset: number): StubMarker;
}

export interface StubClusterGroup {
  options: Record<string, unknown>;
  _spiderfied: unknown;
  _layers: unknown[];
  on(event: string, handler: StubEventHandler): StubClusterGroup;
  addLayer(layer: unknown): StubClusterGroup;
  clearLayers(): StubClusterGroup;
  getLayers(): unknown[];
  getAllChildMarkers(): unknown[];
  getVisibleParent(marker: StubMarker): {
    spiderfy(): void;
    unspiderfy(): void;
    getLatLng(): StubLatLng;
    getIcon(): unknown;
  };
  addTo(map: StubMap): StubClusterGroup;
}

export interface LeafletStubApi {
  map: (id: string | HTMLElement, options?: Record<string, unknown>) => StubMap;
  marker: (latlng: [number, number] | StubLatLng, options?: Record<string, unknown>) => StubMarker;
  markerClusterGroup: (options?: Record<string, unknown>) => StubClusterGroup;
  tileLayer: (
    url: string,
    options?: Record<string, unknown>,
  ) => { addTo(map: StubMap): unknown; options: Record<string, unknown>; url: string };
  layerGroup: () => {
    addTo(map: StubMap): unknown;
    addLayer(layer: unknown): unknown;
    clearLayers(): unknown;
    getLayers(): unknown[];
  };
  geoJSON: (
    feature: unknown,
    options?: Record<string, unknown>,
  ) => {
    on(event: string, handler: StubEventHandler): unknown;
    addTo(group: { addLayer?(layer: unknown): unknown }): unknown;
    eachLayer(fn: (layer: StubPath) => void): void;
  };
  divIcon: (options?: Record<string, unknown>) => Record<string, unknown>;
  latLng: (lat: number, lng: number) => StubLatLng;
  latLngBounds: (
    a?: StubLatLng | [number, number],
    b?: StubLatLng | [number, number],
  ) => StubLatLngBounds;
  Path: typeof StubPath;
  DomEvent: {
    stopPropagation: (event: unknown) => void;
    disableClickPropagation: (el: unknown) => void;
  };
}

function resolveLatLng(latlng: [number, number] | StubLatLng): StubLatLng {
  if (Array.isArray(latlng)) {
    return createLatLng(latlng[0], latlng[1]);
  }
  return latlng;
}

function createMap(id: string | HTMLElement, options: Record<string, unknown> = {}): StubMap {
  const events = createEventTarget();
  let container: HTMLElement;
  if (typeof id === 'string') {
    container = document.getElementById(id) ?? document.createElement('div');
    if (!container.id) container.id = id;
  } else {
    container = id;
  }

  if (!container.querySelector('.leaflet-overlay-pane')) {
    const overlay = document.createElement('div');
    overlay.className = 'leaflet-overlay-pane';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    overlay.appendChild(svg);
    container.appendChild(overlay);
  }

  const panes: Record<string, HTMLElement> = {};
  const layers: unknown[] = [];
  let zoom = typeof options['zoom'] === 'number' ? (options['zoom'] as number) : 3;

  const mapObj: StubMap = {
    options,
    _removed: false,
    _layers: layers,
    _panes: panes,
    _zoom: zoom,
    on: (event, handler) => {
      events.on(event, handler);
      return mapObj;
    },
    once: (event, handler) => {
      events.once(event, handler);
      return mapObj;
    },
    off: (event, handler) => {
      events.off(event, handler);
      return mapObj;
    },
    fire: (event, payload) => events.fire(event, payload),
    addLayer(layer) {
      if (!layers.includes(layer)) layers.push(layer);
      return mapObj;
    },
    removeLayer(layer) {
      const idx = layers.indexOf(layer);
      if (idx >= 0) layers.splice(idx, 1);
      return mapObj;
    },
    hasLayer(layer) {
      return layers.includes(layer);
    },
    createPane(name) {
      const pane = document.createElement('div');
      pane.className = `leaflet-pane leaflet-${name}`;
      pane.style.zIndex = '400';
      pane.style.pointerEvents = 'auto';
      container.appendChild(pane);
      panes[name] = pane;
      return pane;
    },
    getZoom() {
      return zoom;
    },
    getContainer() {
      return container;
    },
    flyTo(_latlng, nextZoom) {
      zoom = nextZoom;
      mapObj._zoom = nextZoom;
      return mapObj;
    },
    fitBounds(_bounds, _opts) {
      return mapObj;
    },
    remove() {
      mapObj._removed = true;
      layers.length = 0;
    },
  };

  return mapObj;
}

function createMarker(
  latlng: [number, number] | StubLatLng,
  options: Record<string, unknown> = {},
): StubMarker {
  const events = createEventTarget();
  const resolved = resolveLatLng(latlng);
  const marker: StubMarker = {
    options,
    _latlng: resolved,
    _icon: document.createElement('div'),
    on(event, handler) {
      events.on(event, handler);
      return marker;
    },
    addTo(map) {
      map.addLayer(marker);
      return marker;
    },
    getLatLng() {
      return marker._latlng;
    },
    getIcon() {
      return options['icon'] ?? null;
    },
    setZIndexOffset(offset) {
      marker.options = { ...marker.options, zIndexOffset: offset };
      return marker;
    },
  };
  return marker;
}

function createClusterGroup(options: Record<string, unknown> = {}): StubClusterGroup {
  const events = createEventTarget();
  const layers: unknown[] = [];
  const group: StubClusterGroup = {
    options,
    _spiderfied: null,
    _layers: layers,
    on(event, handler) {
      events.on(event, handler);
      return group;
    },
    addLayer(layer) {
      layers.push(layer);
      return group;
    },
    clearLayers() {
      layers.length = 0;
      group._spiderfied = null;
      return group;
    },
    getLayers() {
      return [...layers];
    },
    getAllChildMarkers() {
      return [...layers];
    },
    getVisibleParent(child) {
      return {
        spiderfy() {
          group._spiderfied = this;
        },
        unspiderfy() {
          group._spiderfied = null;
        },
        getLatLng() {
          return child.getLatLng();
        },
        getIcon() {
          return child.getIcon();
        },
      };
    },
    addTo(map) {
      map.addLayer(group);
      return group;
    },
  };
  return group;
}

function createLayerGroup() {
  const layers: unknown[] = [];
  const group = {
    addTo(map: StubMap) {
      map.addLayer(group);
      return group;
    },
    addLayer(layer: unknown) {
      layers.push(layer);
      return group;
    },
    clearLayers() {
      layers.length = 0;
      return group;
    },
    getLayers() {
      return [...layers];
    },
  };
  return group;
}

function createTileLayer(url: string, options: Record<string, unknown> = {}) {
  const layer = {
    url,
    options,
    addTo(map: StubMap) {
      map.addLayer(layer);
      return layer;
    },
  };
  return layer;
}

function createGeoJson(feature: unknown, options: Record<string, unknown> = {}) {
  const events = createEventTarget();
  const path = new StubPath();
  const layer = {
    options,
    feature,
    on(event: string, handler: StubEventHandler) {
      events.on(event, handler);
      return layer;
    },
    addTo(group: { addLayer?(l: unknown): unknown }) {
      group.addLayer?.(layer);
      return layer;
    },
    eachLayer(fn: (sub: StubPath) => void) {
      fn(path);
    },
  };
  return layer;
}

export const LeafletStub: LeafletStubApi = {
  map: createMap,
  marker: createMarker,
  markerClusterGroup: createClusterGroup,
  tileLayer: createTileLayer,
  layerGroup: createLayerGroup,
  geoJSON: createGeoJson,
  divIcon: (options: Record<string, unknown> = {}) => ({ ...options, _stub: true }),
  latLng: createLatLng,
  latLngBounds: createLatLngBounds,
  Path: StubPath,
  DomEvent: {
    stopPropagation(_event: unknown): void {
      /* no-op for tests */
    },
    disableClickPropagation(_el: unknown): void {
      /* no-op for tests */
    },
  },
};

type LeafletWindow = Window & { L?: LeafletStubApi };

function asLeafletWindow(target: Window = window): LeafletWindow {
  return target as unknown as LeafletWindow;
}

export function installLeafletStub(target: Window = window): LeafletStubApi {
  const win = asLeafletWindow(target);
  win.L = LeafletStub;
  return LeafletStub;
}

export function uninstallLeafletStub(target: Window = window): void {
  const win = asLeafletWindow(target);
  delete win.L;
}

// Ensure window.L exists before RadarMapComponent captures it at module load.
installLeafletStub();
