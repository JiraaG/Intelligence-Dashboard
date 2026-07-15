import {
  Component, AfterViewInit, DestroyRef, input, output,
  signal, computed, effect, inject
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import type * as Leaflet from 'leaflet';
import { Article, CountrySummary } from '../../models/article.model';

/** Minimal MarkerCluster group shape from the global UMD plugin (window.L). */
interface MarkerClusterGroupLike {
  addLayer(layer: Leaflet.Layer): this;
  clearLayers(): this;
  getLayers(): Leaflet.Layer[];
  getAllChildMarkers(): Leaflet.Marker[];
  getVisibleParent(marker: Leaflet.Marker): Leaflet.Marker | null;
  on(type: string, fn: Leaflet.LeafletEventHandlerFn): this;
  addTo(map: Leaflet.Map): this;
  _spiderfied?: { unspiderfy?: () => void } | null;
}

interface MarkerClusterLike extends Leaflet.Marker {
  getAllChildMarkers(): Leaflet.Marker[];
}

/** Leaflet global from angular.json scripts[] + markercluster plugin. */
type LeafletGlobal = typeof import('leaflet') & {
  markerClusterGroup: (options?: Record<string, unknown>) => MarkerClusterGroupLike;
};

interface ArticleMarkerMeta {
  articleData?: Article;
  realLatLng?: Leaflet.LatLng;
  isDummy?: boolean;
}

type ArticleMarker = Leaflet.Marker & ArticleMarkerMeta & {
  _icon?: HTMLElement | null;
};

function getLeaflet(): LeafletGlobal | null {
  const L = (window as unknown as { L?: LeafletGlobal }).L;
  if (!L || typeof L.map !== 'function' || typeof L.markerClusterGroup !== 'function') {
    return null;
  }
  return L;
}

@Component({
  selector: 'app-radar-map',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './radar-map.component.html',
  styleUrl: './radar-map.component.scss'
})
export class RadarMapComponent implements AfterViewInit {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);

  articles         = input.required<Article[]>();
  countries        = input.required<CountrySummary[]>();
  focusCountryCode = input<string | null>(null);

  markerClicked  = output<Article>();
  clusterClicked = output<Article[]>();
  countryClicked = output<Article[]>();

  currentZoomLevel = signal<number>(3);
  isZoomedOut      = computed(() => this.currentZoomLevel() < 5);
  isParsingGeoJson = signal<boolean>(true);
  mapUnavailable   = signal<boolean>(false);

  private readonly CATEGORY_ICONS: Record<string, string> = {
    'Nucleare':       '☢️',
    'Energia':        '⚡',
    'Infrastrutture': '🏗️',
    'Geopolitica':    '🌍',
    'Economia':       '📈',
    'Tecnologia':     '💻',
    'Spazio':         '🚀',
    'Ambiente':       '🌿',
    'Salute':         '⚕️',
    'Sicurezza':      '🛡️'
  };

  private readonly CATEGORY_CSS_VARS: Record<string, string> = {
    'Nucleare':       '--color-nucleare',
    'Energia':        '--color-energia',
    'Infrastrutture': '--color-infrastrutture',
    'Geopolitica':    '--color-geopolitica',
    'Economia':       '--color-economia',
    'Tecnologia':     '--color-tecnologia',
    'Spazio':         '--color-spazio',
    'Ambiente':       '--color-ambiente',
    'Salute':         '--color-salute',
    'Sicurezza':      '--color-sicurezza'
  };

  readonly legendItems = [
    { label: 'Nucleare', icon: '☢️', cssVar: '--color-nucleare' },
    { label: 'Energia', icon: '⚡', cssVar: '--color-energia' },
    { label: 'Infrastrutture', icon: '🏗️', cssVar: '--color-infrastrutture' },
    { label: 'Geopolitica', icon: '🌍', cssVar: '--color-geopolitica' },
    { label: 'Economia', icon: '📈', cssVar: '--color-economia' },
    { label: 'Tecnologia', icon: '💻', cssVar: '--color-tecnologia' },
    { label: 'Spazio', icon: '🚀', cssVar: '--color-spazio' },
    { label: 'Ambiente', icon: '🌿', cssVar: '--color-ambiente' },
    { label: 'Salute', icon: '⚕️', cssVar: '--color-salute' },
    { label: 'Sicurezza', icon: '🛡️', cssVar: '--color-sicurezza' }
  ];

  private readonly UI_OFFSETS: Record<string, [number, number]> = {
    'Nucleare':       [34, 0],
    'Energia':        [28, 20],
    'Infrastrutture': [11, 32],
    'Geopolitica':    [-11, 32],
    'Economia':       [-28, 20],
    'Tecnologia':     [-34, 0],
    'Spazio':         [-28, -20],
    'Ambiente':       [-11, -32],
    'Salute':         [11, -32],
    'Sicurezza':      [28, -20]
  };

  private map: Leaflet.Map | null = null;
  private L: LeafletGlobal | null = null;
  private categoryClusterGroups = new Map<string, MarkerClusterGroupLike>();
  private isNavigating = false;
  private navigatingTargetZoom = 0;
  private geoJsonLayerGroup: Leaflet.LayerGroup | null = null;
  private countryLayersMap = new Map<string, Leaflet.Path[]>();
  private activeRootMarkers: Leaflet.Marker[] = [];
  private lastGeometryFingerprint = '';
  private destroyed = false;
  private geoJsonSub: Subscription | null = null;
  private geoJsonRafId: number | null = null;
  private pendingTimeouts = new Set<ReturnType<typeof setTimeout>>();
  private highlightedMarker: ArticleMarker | null = null;
  private pendingHighlightArticle: Article | null = null;
  private spiderfyGeneration = 0;

  constructor() {
    effect(() => {
      const arts = this.articles();
      const ctrs = this.countries();
      if (!this.map || this.isParsingGeoJson() || this.isNavigating || this.destroyed) {
        return;
      }
      const fingerprint = this.geometryFingerprint(arts);
      if (fingerprint === this.lastGeometryFingerprint) {
        this.syncMarkerReadState(arts);
        return;
      }
      this.updateMapData(arts, ctrs);
    });

    effect(() => {
      const code = this.focusCountryCode();
      if (code && this.map && !this.isParsingGeoJson() && !this.isNavigating && !this.destroyed) {
        this.focusOnCountry(code);
      }
    });

    this.destroyRef.onDestroy(() => this.teardown());
  }

  ngAfterViewInit(): void {
    this.initMap();
    if (!this.mapUnavailable()) {
      this.loadGeoJson();
    }
  }

  /** Call after sidebar open/close or window resize (overlay full-bleed layout). */
  public invalidateSize(): void {
    this.map?.invalidateSize({ animate: false });
  }

  private scheduleTimeout(fn: () => void, ms: number): void {
    const id = setTimeout(() => {
      this.pendingTimeouts.delete(id);
      if (!this.destroyed) fn();
    }, ms);
    this.pendingTimeouts.add(id);
  }

  private clearPendingTimeouts(): void {
    this.pendingTimeouts.forEach((id) => clearTimeout(id));
    this.pendingTimeouts.clear();
  }

  private geometryFingerprint(articles: Article[]): string {
    return articles
      .map((a) => `${a.id}|${a.primary_category}|${a.country_code}|${a.latitude}|${a.longitude}`)
      .sort()
      .join(';');
  }

  private createSafeMarkerIcon(
    L: LeafletGlobal,
    article: Article,
    ox: number,
    oy: number,
  ): Leaflet.DivIcon {
    const emoji = this.CATEGORY_ICONS[article.primary_category] ?? '📍';
    const el = document.createElement('div');
    el.className = 'marker-icon';
    el.style.fontSize = '24px';
    el.style.lineHeight = '44px';
    el.style.textAlign = 'center';
    el.title = article.title;
    el.textContent = emoji;
    if (article.is_read) {
      el.classList.add('marker-read');
    }

    return L.divIcon({
      html: el,
      className: `marker-${article.primary_category.toLowerCase()}`,
      iconSize: [44, 44],
      iconAnchor: [22 - ox, 22 - oy],
    });
  }

  private syncMarkerReadState(articles: Article[]): void {
    const byId = new Map(articles.map((a) => [a.id, a]));
    this.categoryClusterGroups.forEach((cg) => {
      for (const layer of cg.getLayers()) {
        const marker = layer as ArticleMarker;
        if (marker.isDummy || !marker.articleData) continue;
        const latest = byId.get(marker.articleData.id);
        if (!latest) continue;
        marker.articleData.is_read = latest.is_read;
        const iconEl = marker._icon;
        if (iconEl) {
          iconEl.classList.toggle('marker-read', !!latest.is_read);
          const inner = iconEl.querySelector('.marker-icon');
          if (inner) {
            inner.classList.toggle('marker-read', !!latest.is_read);
          }
        }
      }
    });
  }

  private initMap(): void {
    const L = getLeaflet();
    if (!L) {
      this.mapUnavailable.set(true);
      this.isParsingGeoJson.set(false);
      return;
    }
    this.L = L;
    this.mapUnavailable.set(false);

    this.map = L.map('radar-map', {
      center: [20, 0],
      zoom: 3,
      minZoom: 2.2,
      maxBounds: L.latLngBounds(L.latLng(-85, -180), L.latLng(85, 180)),
      maxBoundsViscosity: 1.0,
      zoomControl: false,
      attributionControl: true
    });

    this.geoJsonLayerGroup = L.layerGroup();

    this.map.on('click', (e: Leaflet.LeafletMouseEvent) => {
      const original = e.originalEvent as (Event & { _radarHandled?: boolean }) | undefined;
      if (original?._radarHandled) return;
      this.collapseAllGraphs(true);
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap contributors © CARTO',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(this.map);

    const labelsPane = this.map.createPane('labelsPane');
    labelsPane.style.zIndex = '650';
    labelsPane.style.pointerEvents = 'none';

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', {
      pane: 'labelsPane',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(this.map);

    const categories = Object.keys(this.CATEGORY_CSS_VARS);
    for (const cat of categories) {
      const catClass = `cat-${cat.toLowerCase()}`;

      const cg = L.markerClusterGroup({
        maxClusterRadius: 40,
        showCoverageOnHover: false,
        spiderfyOnMaxZoom: false,
        zoomToBoundsOnClick: false,
        spiderfyDistanceMultiplier: 2.8,
        iconCreateFunction: (cluster: MarkerClusterLike) => {
          const childMarkers = cluster.getAllChildMarkers() as ArticleMarker[];
          const realCount = childMarkers.filter((m) => !m.isDummy).length;
          if (realCount === 0) return L.divIcon({ className: 'hidden', iconSize: [0, 0] });

          const zoom = this.map ? this.map.getZoom() : 3;
          const iconScale = Math.max(1.0, Math.min(3.0, 1.0 + (zoom - 5) * 0.15));
          const iconPx = Math.round(52 * iconScale);
          const half = Math.round(iconPx / 2);
          const [ox, oy] = this.UI_OFFSETS[cat] || [0, 0];

          const clusterEl = document.createElement('div');
          clusterEl.className = 'cluster-icon';
          clusterEl.textContent = String(realCount);

          return L.divIcon({
            html: clusterEl,
            className: `radar-cluster ${catClass}`,
            iconSize: [iconPx, iconPx],
            iconAnchor: [half - (ox * iconScale), half - (oy * iconScale)]
          });
        }
      });

      cg.on('unspiderfied', () => {
        this.clearRootMarkers();
      });

      cg.on('clusterclick', (e: Leaflet.LeafletEvent) => {
        if (this.destroyed || !this.map || !this.L) return;
        const clusterEvent = e as Leaflet.LeafletMouseEvent & { layer: MarkerClusterLike };
        if (clusterEvent.originalEvent) {
          clusterEvent.originalEvent.preventDefault();
          this.L.DomEvent.stopPropagation(clusterEvent.originalEvent);
          (clusterEvent.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
        }

        const cluster = clusterEvent.layer;
        const childMarkers = cluster.getAllChildMarkers() as ArticleMarker[];
        const isAlreadyOpen = cg._spiderfied === cluster;

        this.collapseAllGraphs();

        if (isAlreadyOpen) {
          this.clusterClicked.emit([]);
          return;
        }

        const arts = childMarkers
          .filter((m) => !m.isDummy)
          .map((m) => m.articleData)
          .filter((a): a is Article => !!a);

        if (arts.length > 0) this.clusterClicked.emit(arts);

        const currentZoom = this.map.getZoom();
        const targetZoom = 6;
        const gen = ++this.spiderfyGeneration;

        if (currentZoom >= targetZoom) {
          this.spiderfyAndCreateRoot(cg, childMarkers, gen);
          return;
        }

        this.isNavigating = true;
        this.navigatingTargetZoom = targetZoom;
        this.map.flyTo(cluster.getLatLng(), targetZoom, { animate: true, duration: 0.6 });

        const onZoomEnd = () => {
          this.scheduleTimeout(() => {
            if (this.destroyed || gen !== this.spiderfyGeneration) return;
            this.spiderfyAndCreateRoot(cg, childMarkers, gen);
            this.isNavigating = false;
          }, 250);
        };
        this.map.once('zoomend', onZoomEnd);
      });

      this.categoryClusterGroups.set(cat, cg);
      this.map.addLayer(cg as unknown as Leaflet.Layer);
    }
    this.geoJsonLayerGroup.addTo(this.map);

    this.map.on('zoomend', () => {
      if (this.destroyed || !this.map) return;
      const zoom = this.map.getZoom();
      this.currentZoomLevel.set(zoom);
      this.refreshHatchingStyles();

      if (zoom < 5 && !this.isNavigating) {
        this.collapseAllGraphs(true);
      }
    });
  }

  private clearRootMarkers(): void {
    if (!this.map) return;
    this.activeRootMarkers.forEach((m) => {
      if (this.map!.hasLayer(m)) this.map!.removeLayer(m);
    });
    this.activeRootMarkers = [];
  }

  private spiderfyAndCreateRoot(
    cg: MarkerClusterGroupLike,
    childMarkers: ArticleMarker[],
    generation: number,
  ): void {
    if (this.destroyed || !this.map || !this.L) return;
    if (generation !== this.spiderfyGeneration) return;
    if (!childMarkers || childMarkers.length === 0) return;

    const newParent = cg.getVisibleParent(childMarkers[0]) as
      | (Leaflet.Marker & { spiderfy?: () => void })
      | null
      | undefined;

    if (newParent && typeof newParent.spiderfy === 'function') {
      this.clearRootMarkers();

      const rootIcon = newParent.getIcon();
      const rootMarker = this.L.marker(newParent.getLatLng(), {
        icon: rootIcon,
        interactive: true,
        zIndexOffset: 1000
      }).addTo(this.map);

      rootMarker.on('click', (e: Leaflet.LeafletMouseEvent) => {
        if (e.originalEvent) {
          (e.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
        }
        this.L!.DomEvent.stopPropagation(e);
        this.collapseAllGraphs(true);
      });

      this.activeRootMarkers.push(rootMarker);
      newParent.spiderfy();
    }
  }

  private loadGeoJson(): void {
    this.geoJsonSub?.unsubscribe();
    this.geoJsonSub = this.http
      .get<GeoJSON.FeatureCollection>('assets/data/countries.geo.json')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (geoData) => this.parseGeoJsonIncremental(geoData),
        error: (err) => {
          console.error('[RadarMap] Errore GeoJSON:', err);
          this.isParsingGeoJson.set(false);
        }
      });
  }

  private parseGeoJsonIncremental(geoData: GeoJSON.FeatureCollection): void {
    const L = this.L;
    if (!L || !this.geoJsonLayerGroup || this.destroyed) {
      this.isParsingGeoJson.set(false);
      return;
    }

    const features = geoData.features;
    let index = 0;
    const batchSize = 15;

    const processBatch = () => {
      this.geoJsonRafId = null;
      if (this.destroyed || !this.L || !this.geoJsonLayerGroup) {
        this.isParsingGeoJson.set(false);
        return;
      }

      const end = Math.min(index + batchSize, features.length);
      for (let i = index; i < end; i++) {
        const feature = features[i];
        let code = feature.properties?.['ISO3166-1-Alpha-2'] ?? feature.properties?.['ISO_A2'] ?? 'XX';
        if (code === '-99' || !code || code === 'XX') {
          const name = feature.properties?.['name'];
          if (name === 'France') code = 'FR';
          else if (name === 'Norway') code = 'NO';
        }

        const layer = L.geoJSON(feature, {
          style: () => ({
            color: 'rgba(0, 212, 255, 0.15)',
            weight: 0.5,
            fillOpacity: 0,
            fillColor: 'transparent',
            className: 'country-fill'
          })
        });

        layer.on('click', (e: Leaflet.LeafletMouseEvent) => {
          if (this.isZoomedOut()) {
            if (e.originalEvent) {
              L.DomEvent.stopPropagation(e.originalEvent);
            }
            const countryArts = this.articles().filter((a) => a.country_code === code);
            if (countryArts.length > 0) {
              if (e.originalEvent) {
                (e.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
              }
              this.countryClicked.emit(countryArts);
            }
          }
        });

        layer.addTo(this.geoJsonLayerGroup);

        layer.eachLayer((subLayer: Leaflet.Layer) => {
          if (subLayer instanceof L.Path) {
            const list = this.countryLayersMap.get(code) || [];
            list.push(subLayer);
            this.countryLayersMap.set(code, list);
          }
        });
      }

      index = end;
      if (index < features.length) {
        this.geoJsonRafId = requestAnimationFrame(processBatch);
      } else {
        this.isParsingGeoJson.set(false);
        this.refreshHatchingStyles();
      }
    };

    this.geoJsonRafId = requestAnimationFrame(processBatch);
  }

  private refreshHatchingStyles(): void {
    if (!this.map) return;
    const ctrs = this.countries();
    const zoomedOut = this.currentZoomLevel() < 5;

    const svg = this.map.getContainer().querySelector('.leaflet-overlay-pane svg');
    let defs: SVGDefsElement | null = null;
    if (svg) {
      defs = svg.querySelector('defs');
      if (!defs) {
        defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        svg.insertBefore(defs, svg.firstChild);
      }
    }

    const baseUrl = window.location.href.split('#')[0];
    this.countryLayersMap.forEach((layers, code) => {
      const summary = ctrs.find((c) => c.country_code === code);

      layers.forEach((layer) => {
        if (zoomedOut && summary?.categories?.length && defs) {
          const patternId = this.getOrCreateComboPattern(summary.categories, defs);
          layer.setStyle({
            fillColor: `url(${baseUrl}#${patternId})`,
            fillOpacity: 0.35,
            color: 'rgba(0, 212, 255, 0.25)'
          });
        } else {
          layer.setStyle({
            fillOpacity: 0,
            color: 'rgba(0, 212, 255, 0.15)'
          });
        }
      });
    });

    if (zoomedOut) {
      this.map.getContainer().classList.add('zoom-out-mode');
    } else {
      this.map.getContainer().classList.remove('zoom-out-mode');
    }
  }

  /** Single SVG-pattern owner for country hatching (categories 1–10). */
  private getOrCreateComboPattern(categories: string[], defs: SVGDefsElement): string {
    if (!categories || categories.length === 0) return '';

    const sortedCats = [...categories].sort();
    const id = 'hatch-grid-' + sortedCats.map((c) => c.toLowerCase().replace(/ /g, '-')).join('-');

    if (defs.querySelector(`#${id}`)) return id;

    const pattern = document.createElementNS('http://www.w3.org/2000/svg', 'pattern');
    pattern.setAttribute('id', id);
    pattern.setAttribute('width', '24');
    pattern.setAttribute('height', '24');
    pattern.setAttribute('patternUnits', 'userSpaceOnUse');

    const color = this.CATEGORY_CSS_VARS[sortedCats[0]] || '--color-text-accent';

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('width', '24');
    rect.setAttribute('height', '24');
    rect.setAttribute('fill', `var(${color})`);
    rect.setAttribute('opacity', '0.05');
    pattern.appendChild(rect);

    const strokeWidth = '1.8';
    const strokeOpacity = '0.75';

    const getColorVar = (cat: string) => {
      const cssVar = this.CATEGORY_CSS_VARS[cat] || '--color-text-accent';
      return `var(${cssVar})`;
    };

    const appendLine = (
      x1: string, y1: string, x2: string, y2: string, strokeColor: string,
    ): void => {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x1);
      line.setAttribute('y1', y1);
      line.setAttribute('x2', x2);
      line.setAttribute('y2', y2);
      line.setAttribute('stroke', strokeColor);
      line.setAttribute('stroke-width', strokeWidth);
      line.setAttribute('opacity', strokeOpacity);
      pattern.appendChild(line);
    };

    if (sortedCats.length === 1) {
      appendLine('0', '24', '24', '0', getColorVar(sortedCats[0]));
      appendLine('0', '0', '24', '24', getColorVar(sortedCats[0]));
    } else {
      for (let i = 0; i < sortedCats.length; i++) {
        const strokeColor = getColorVar(sortedCats[i]);
        if (i === 0) {
          appendLine('0', '24', '24', '0', strokeColor);
        } else if (i === 1) {
          appendLine('0', '0', '24', '24', strokeColor);
        } else if (i === 2) {
          appendLine('0', '12', '24', '12', strokeColor);
        } else if (i === 3) {
          appendLine('12', '0', '12', '24', strokeColor);
        } else if (i === 4) {
          appendLine('0', '12', '12', '0', strokeColor);
          appendLine('12', '24', '24', '12', strokeColor);
        } else if (i === 5) {
          appendLine('12', '0', '24', '12', strokeColor);
          appendLine('0', '12', '12', '24', strokeColor);
        } else if (i === 6) {
          appendLine('0', '6', '24', '6', strokeColor);
        } else if (i === 7) {
          appendLine('0', '18', '24', '18', strokeColor);
        } else if (i === 8) {
          appendLine('6', '0', '6', '24', strokeColor);
        } else {
          // i === 9 (10th category) and any further
          appendLine('18', '0', '18', '24', strokeColor);
        }
      }
    }

    defs.appendChild(pattern);
    return id;
  }

  private focusOnCountry(code: string): void {
    const L = this.L;
    if (!this.map || !L || this.isNavigating || this.destroyed) return;

    let bounds: Leaflet.LatLngBounds | null = null;

    if (code === 'US') {
      bounds = L.latLngBounds(L.latLng(24.396308, -125.0), L.latLng(49.384358, -66.93457));
    } else if (code === 'RU') {
      bounds = L.latLngBounds(L.latLng(41.1856, 19.6389), L.latLng(81.8587, 169.0));
    } else {
      const layers = this.countryLayersMap.get(code);
      if (layers && layers.length > 0) {
        const b = L.latLngBounds([]);
        layers.forEach((layer) => {
          const withBounds = layer as Leaflet.Path & { getBounds?: () => Leaflet.LatLngBounds };
          if (typeof withBounds.getBounds === 'function') {
            b.extend(withBounds.getBounds());
          }
        });
        if (b.isValid()) bounds = b;
      }
    }

    if (bounds && bounds.isValid()) {
      this.isNavigating = true;
      this.map.fitBounds(bounds, {
        maxZoom: 4,
        animate: true,
        duration: 1.0
      });

      let cleaned = false;
      const cleanup = () => {
        if (cleaned || this.destroyed) return;
        cleaned = true;
        this.isNavigating = false;
        this.map?.off('zoomend', cleanup);
        this.map?.off('moveend', cleanup);
      };

      this.map.once('zoomend', cleanup);
      this.map.once('moveend', cleanup);
      this.scheduleTimeout(cleanup, 1500);
    }
  }

  private updateMapData(articles: Article[], countries: CountrySummary[]): void {
    const L = this.L;
    if (!L || !this.map) return;

    this.categoryClusterGroups.forEach((group) => group.clearLayers());
    const countryCenters = new Map<string, { latSum: number; lngSum: number; count: number }>();

    for (const article of articles) {
      if (article.latitude && article.longitude) {
        const code = article.country_code || 'XX';
        if (code === 'XX') continue;
        const current = countryCenters.get(code) || { latSum: 0, lngSum: 0, count: 0 };
        current.latSum += article.latitude;
        current.lngSum += article.longitude;
        current.count++;
        countryCenters.set(code, current);
      }
    }

    const populatedSpots = new Set<string>();

    for (const article of articles) {
      const code = article.country_code || 'XX';
      if (code === 'XX') continue;
      const center = countryCenters.get(code);
      if (!center) continue;

      const baseLat = center.latSum / center.count;
      const baseLng = center.lngSum / center.count;
      const realLatLng = L.latLng(baseLat, baseLng);

      const cat = article.primary_category;
      const [ox, oy] = this.UI_OFFSETS[cat] || [0, 0];

      populatedSpots.add(`${code}_${cat}`);

      const icon = this.createSafeMarkerIcon(L, article, ox, oy);
      const marker = L.marker([baseLat, baseLng], { icon }) as ArticleMarker;
      marker.articleData = article;
      marker.realLatLng = realLatLng;
      marker.isDummy = false;

      marker.on('click', (e: Leaflet.LeafletMouseEvent) => {
        if (e.originalEvent) {
          L.DomEvent.stopPropagation(e.originalEvent);
          (e.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
        }
        this.markerClicked.emit(article);
      });

      const targetGroup = this.categoryClusterGroups.get(cat);
      if (targetGroup) targetGroup.addLayer(marker);
    }

    populatedSpots.forEach((spot) => {
      const [code, cat] = spot.split('_');
      const center = countryCenters.get(code)!;
      const baseLat = center.latSum / center.count;
      const baseLng = center.lngSum / center.count;

      const invisibleIcon = L.divIcon({
        html: '',
        className: '',
        iconSize: [0, 0],
        iconAnchor: [0, 0]
      });

      const dummyMarker = L.marker([baseLat, baseLng], {
        icon: invisibleIcon,
        interactive: false
      }) as ArticleMarker;
      dummyMarker.isDummy = true;

      const targetGroup = this.categoryClusterGroups.get(cat);
      if (targetGroup) targetGroup.addLayer(dummyMarker);
    });

    this.lastGeometryFingerprint = this.geometryFingerprint(articles);
    this.refreshHatchingStyles();
    void countries;
  }

  collapseAllGraphs(emitClose: boolean = false): void {
    if (!this.map) return;

    this.spiderfyGeneration++;
    this.clearRootMarkers();

    this.categoryClusterGroups.forEach((cg) => {
      const spiderfiedCluster = cg._spiderfied;
      if (spiderfiedCluster && typeof spiderfiedCluster.unspiderfy === 'function') {
        spiderfiedCluster.unspiderfy();
      }
    });

    if (emitClose) {
      this.clusterClicked.emit([]);
    }
  }

  public focusAndSpiderfyCategory(countryCode: string, category: string): void {
    if (!this.map || this.destroyed) return;
    const cg = this.categoryClusterGroups.get(category);
    if (!cg) return;

    const allMarkers = cg.getLayers() as ArticleMarker[];
    const countryMarkers = allMarkers.filter(
      (m) => m.articleData && m.articleData.country_code === countryCode,
    );

    if (countryMarkers.length === 0) return;

    this.collapseAllGraphs(false);

    const firstMarker = countryMarkers[0];
    const parent = cg.getVisibleParent(firstMarker);
    if (!parent) return;

    const currentZoom = this.map.getZoom();
    const targetZoom = 6;
    const latLng = typeof parent.getLatLng === 'function'
      ? parent.getLatLng()
      : firstMarker.getLatLng();
    const gen = ++this.spiderfyGeneration;

    if (currentZoom >= targetZoom) {
      this.spiderfyAndCreateRoot(cg, countryMarkers, gen);
      return;
    }

    this.isNavigating = true;
    this.navigatingTargetZoom = targetZoom;
    this.map.flyTo(latLng, targetZoom, { animate: true, duration: 0.6 });

    let cleaned = false;
    const cleanup = () => {
      if (cleaned) return;
      cleaned = true;
      this.scheduleTimeout(() => {
        if (this.destroyed || gen !== this.spiderfyGeneration) {
          this.isNavigating = false;
          return;
        }
        this.spiderfyAndCreateRoot(cg, countryMarkers, gen);
        this.isNavigating = false;
        this.map?.off('zoomend', cleanup);
        this.map?.off('moveend', cleanup);
      }, 250);
    };

    this.map.once('zoomend', cleanup);
    this.map.once('moveend', cleanup);
    this.scheduleTimeout(cleanup, 1200);
  }

  public highlightMarkerForArticle(article: Article | null): void {
    if (this.highlightedMarker) {
      const iconDiv = this.highlightedMarker._icon;
      if (iconDiv) {
        iconDiv.classList.remove('marker-highlight');
      }
      if (this.highlightedMarker.setZIndexOffset) {
        this.highlightedMarker.setZIndexOffset(0);
      }
      this.highlightedMarker = null;
    }
    this.pendingHighlightArticle = article;

    if (article) {
      this.applyHighlight(20);
    }
  }

  private applyHighlight(retries: number): void {
    if (!this.pendingHighlightArticle || this.destroyed) return;
    const article = this.pendingHighlightArticle;

    let targetMarker: ArticleMarker | null = null;
    const cg = this.categoryClusterGroups.get(article.primary_category);
    if (cg) {
      const markers = cg.getLayers() as ArticleMarker[];
      targetMarker = markers.find((m) => m.articleData && m.articleData.id === article.id) ?? null;
    }

    if (targetMarker) {
      const iconDiv = targetMarker._icon;
      if (iconDiv) {
        iconDiv.classList.add('marker-highlight');
        this.highlightedMarker = targetMarker;
        if (targetMarker.setZIndexOffset) {
          targetMarker.setZIndexOffset(1000);
        }
      } else if (retries > 0) {
        this.scheduleTimeout(() => this.applyHighlight(retries - 1), 150);
      }
    } else if (retries > 0) {
      this.scheduleTimeout(() => this.applyHighlight(retries - 1), 150);
    }
  }

  private teardown(): void {
    this.destroyed = true;
    this.spiderfyGeneration++;
    this.geoJsonSub?.unsubscribe();
    this.geoJsonSub = null;
    if (this.geoJsonRafId !== null) {
      cancelAnimationFrame(this.geoJsonRafId);
      this.geoJsonRafId = null;
    }
    this.clearPendingTimeouts();
    this.clearRootMarkers();
    this.map?.remove();
    this.map = null;
  }
}
