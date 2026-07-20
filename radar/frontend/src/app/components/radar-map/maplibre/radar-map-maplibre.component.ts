import {
  Component,
  AfterViewInit,
  DestroyRef,
  ElementRef,
  viewChild,
  input,
  output,
  signal,
  computed,
  effect,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import maplibregl, {
  type GeoJSONSource,
  type Map as MapLibreMap,
  type MapLayerMouseEvent,
  type Marker,
} from 'maplibre-gl';
import { Article, CountrySummary, PrimaryCategory } from '../../../models/article.model';
import { MapSummaryRow } from '../../../models/map-summary.model';
import { MapRelationRow } from '../../../models/map-relation.model';
import { CountryOpenRequest, RelationOpenRequest } from '../radar-map.types';
import { greatCircle, MAP_ZOOM_PIN_THRESHOLD } from './great-circle';
import { splitCountryByCategories } from './country-category-fills';

interface LatLng {
  lat: number;
  lng: number;
}

interface SpiderArticleMarker {
  marker: Marker;
  article: Article;
  el: HTMLElement;
}

/**
 * Host MapLibre Radar: fasce soft per tipologia (zoom &lt; 5), pin day-view, archi great-circle
 * multicolore solidi (tutti gli zoom; no fan/dash), hub + spiderfy emoji custom (no MarkerCluster).
 *
 * @see plan-audit/active/plan_impl_map_3d_globe.md
 */
@Component({
  selector: 'app-radar-map-maplibre',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './radar-map-maplibre.component.html',
  styleUrl: './radar-map-maplibre.component.scss',
})
export class RadarMapMaplibreComponent implements AfterViewInit {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);
  private readonly mapHost = viewChild<ElementRef<HTMLDivElement>>('mapHost');

  articles = input.required<Article[]>();
  countries = input.required<CountrySummary[]>();
  mapSummary = input<MapSummaryRow[]>([]);
  mapRelations = input<MapRelationRow[]>([]);
  focusCountryCode = input<string | null>(null);

  markerClicked = output<Article>();
  clusterClicked = output<Article[]>();
  countryClicked = output<CountryOpenRequest>();
  relationClicked = output<RelationOpenRequest>();

  currentZoomLevel = signal<number>(3);
  isZoomedOut = computed(() => this.currentZoomLevel() < MAP_ZOOM_PIN_THRESHOLD);
  isParsingGeoJson = signal<boolean>(true);
  mapUnavailable = signal<boolean>(false);
  projectionMode = signal<'globe' | 'mercator'>('globe');

  private readonly CATEGORY_ICONS: Record<string, string> = {
    Nucleare: '☢️',
    Energia: '⚡',
    Infrastrutture: '🏗️',
    Geopolitica: '🌍',
    Economia: '📈',
    Tecnologia: '💻',
    Spazio: '🚀',
    Ambiente: '🌿',
    Salute: '⚕️',
    Sicurezza: '🛡️',
  };

  private readonly CATEGORY_CSS_VARS: Record<string, string> = {
    Nucleare: '--color-nucleare',
    Energia: '--color-energia',
    Infrastrutture: '--color-infrastrutture',
    Geopolitica: '--color-geopolitica',
    Economia: '--color-economia',
    Tecnologia: '--color-tecnologia',
    Spazio: '--color-spazio',
    Ambiente: '--color-ambiente',
    Salute: '--color-salute',
    Sicurezza: '--color-sicurezza',
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
    { label: 'Sicurezza', icon: '🛡️', cssVar: '--color-sicurezza' },
  ];

  private readonly COUNTRY_PIN_SIZE = { w: 64, h: 76 } as const;
  private readonly COUNTRIES_SOURCE = 'radar-countries';
  private readonly COUNTRIES_FILL = 'radar-countries-fill';
  private readonly COUNTRIES_LINE = 'radar-countries-line';
  private readonly COUNTRY_CAT_SOURCE = 'radar-country-cat-fills';
  private readonly COUNTRY_CAT_FILL = 'radar-country-cat-fill';
  private readonly RELATIONS_SOURCE = 'radar-relations';
  private readonly RELATIONS_LINE = 'radar-relations-line';
  private readonly RELATIONS_HIT = 'radar-relations-hit';

  private map: MapLibreMap | null = null;
  private countryCentroids = new Map<string, LatLng>();
  private countryBounds = new Map<string, [[number, number], [number, number]]>();
  private countriesGeoJson: GeoJSON.FeatureCollection | null = null;
  private lastGeometryFingerprint = '';
  private destroyed = false;
  private geoJsonSub: Subscription | null = null;
  private pendingTimeouts = new Set<ReturnType<typeof setTimeout>>();
  private isNavigating = false;
  private pendingGeometryRefresh = false;
  private skipNextCountryFit = false;
  private spiderfyGeneration = 0;
  private lastSpiderfyCountry: string | null = null;
  private lastSpiderfyCategory: string | null = null;
  private summaryMarkers: Marker[] = [];
  private hubMarker: Marker | null = null;
  private spiderRootMarker: Marker | null = null;
  private spiderMarkers: SpiderArticleMarker[] = [];
  private detailArticlesByCategory = new Map<string, Article[]>();
  private highlightedEl: HTMLElement | null = null;
  private pendingHighlightArticle: Article | null = null;
  private relationPopup: maplibregl.Popup | null = null;
  private hoveredArcKey: string | null = null;
  private lastHatchFingerprint = '';
  /** Ignora click dopo drag/rotate (evita fitBounds nazione mentre si gira il globo). */
  private pointerDownPoint: { x: number; y: number } | null = null;
  private suppressNextMapClick = false;
  private suppressCountryClickUntil = 0;
  private readonly DRAG_CLICK_PX = 6;
  /** Opacità soft ma leggibile (Infrastrutture grigio resta visibile). */
  private readonly CATEGORY_FILL_OPACITY = 0.34;
  /** Ordine legenda = ordine fasce O→E (stesso mentale della toolbar). */
  private readonly CATEGORY_LEGEND_ORDER = Object.keys(this.CATEGORY_CSS_VARS);

  constructor() {
    effect(() => {
      const arts = this.articles();
      const ctrs = this.countries();
      const summary = this.mapSummary();
      const relations = this.mapRelations();
      if (!this.map || this.isParsingGeoJson() || this.destroyed) {
        return;
      }
      if (this.isNavigating) {
        this.pendingGeometryRefresh = true;
        return;
      }
      this.applyGeometryInputs(arts, ctrs, summary, relations);
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
    this.scheduleMapInit(0);
  }

  public armSkipCountryFit(): void {
    this.skipNextCountryFit = true;
  }

  public refocusCountry(code: string): void {
    this.skipNextCountryFit = false;
    this.focusOnCountry(code);
  }

  public invalidateSize(): void {
    if (!this.map) return;
    const host = this.resolveMapHost();
    if (!host || host.clientWidth < 2 || host.clientHeight < 2) return;
    try {
      this.map.resize();
    } catch (err) {
      console.warn('[RadarMapMaplibre] resize skipped:', err);
    }
  }

  collapseAllGraphs(emitClose: boolean = false, restoreHub: boolean = true): void {
    if (!this.map) return;
    this.spiderfyGeneration++;
    this.clearSpiderfy();
    if (emitClose) {
      this.lastSpiderfyCountry = null;
      this.lastSpiderfyCategory = null;
    }
    if (restoreHub && this.articles().length > 0) {
      this.upsertDetailHubPin(this.articles());
    } else if (!restoreHub) {
      this.clearDetailHubPin();
    }
    if (emitClose) {
      this.clusterClicked.emit([]);
    }
  }

  public focusAndSpiderfyCategory(countryCode: string, category: string, attempt = 0): void {
    if (!this.map || this.destroyed) return;
    const arts =
      this.detailArticlesByCategory.get(category)?.filter((a) => a.country_code === countryCode) ??
      [];
    if (arts.length === 0) {
      if (attempt < 10) {
        this.scheduleTimeout(
          () => this.focusAndSpiderfyCategory(countryCode, category, attempt + 1),
          50,
        );
      }
      return;
    }

    this.collapseAllGraphs(false, false);
    const anchor = this.resolveCountryAnchorLatLng(countryCode, arts);
    if (!anchor) {
      this.restoreNationHubPin();
      return;
    }

    const currentZoom = this.map.getZoom();
    const targetZoom = 6;
    const gen = ++this.spiderfyGeneration;

    if (currentZoom >= MAP_ZOOM_PIN_THRESHOLD) {
      if (!this.spiderfyAndCreateRoot(arts, anchor, gen, countryCode, category)) {
        this.restoreNationHubPin();
      }
      return;
    }

    this.isNavigating = true;
    this.map.flyTo({ center: [anchor.lng, anchor.lat], zoom: targetZoom, duration: 600 });
    let cleaned = false;
    const cleanup = () => {
      if (cleaned) return;
      cleaned = true;
      this.scheduleTimeout(() => {
        if (this.destroyed || gen !== this.spiderfyGeneration) {
          this.finishNavigating();
          return;
        }
        if (!this.spiderfyAndCreateRoot(arts, anchor, gen, countryCode, category)) {
          this.restoreNationHubPin();
        }
        this.finishNavigating();
        this.map?.off('moveend', cleanup);
      }, 250);
    };
    this.map.once('moveend', cleanup);
    this.scheduleTimeout(cleanup, 1200);
  }

  public focusAndSpiderfyCountry(countryCode: string, attempt = 0): void {
    if (!this.map || this.destroyed) return;
    for (const [cat, arts] of this.detailArticlesByCategory) {
      if (arts.some((a) => a.country_code === countryCode)) {
        this.focusAndSpiderfyCategory(countryCode, cat, attempt);
        return;
      }
    }
    if (attempt < 10) {
      this.scheduleTimeout(() => this.focusAndSpiderfyCountry(countryCode, attempt + 1), 50);
    }
  }

  public highlightMarkerForArticle(article: Article | null): void {
    if (this.highlightedEl) {
      this.highlightedEl.classList.remove('marker-highlight');
      this.highlightedEl = null;
    }
    this.pendingHighlightArticle = article;
    if (article) {
      this.applyHighlight(20);
    }
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

  private geometryFingerprint(
    articles: Article[],
    summary: MapSummaryRow[],
    relations: MapRelationRow[],
  ): string {
    const relPart = relations
      .map((r) => `${r.source_country}|${r.target_country}|${r.primary_category}|${r.volume}`)
      .sort()
      .join(';');
    if (articles.length > 0) {
      return (
        'detail:' +
        articles
          .map(
            (a) => `${a.id}|${a.primary_category}|${a.country_code}|${a.latitude}|${a.longitude}`,
          )
          .sort()
          .join(';') +
        '::' +
        relPart
      );
    }
    return (
      'summary:' +
      summary
        .map(
          (r) =>
            `${r.country_code}|${r.primary_category}|${r.article_count}|${r.latitude}|${r.longitude}`,
        )
        .sort()
        .join(';') +
      '::' +
      relPart
    );
  }

  private applyGeometryInputs(
    articles: Article[],
    countries: CountrySummary[],
    summary: MapSummaryRow[],
    relations: MapRelationRow[],
  ): void {
    const fingerprint = this.geometryFingerprint(articles, summary, relations);
    if (fingerprint === this.lastGeometryFingerprint) {
      if (articles.length > 0) this.syncMarkerReadState(articles);
      return;
    }
    this.updateMapData(articles, countries, summary, relations);
  }

  private finishNavigating(): void {
    this.isNavigating = false;
    if (!this.pendingGeometryRefresh || this.destroyed || !this.map || this.isParsingGeoJson()) {
      return;
    }
    this.pendingGeometryRefresh = false;
    this.applyGeometryInputs(
      this.articles(),
      this.countries(),
      this.mapSummary(),
      this.mapRelations(),
    );
  }

  private initMap(): void {
    const host = this.resolveMapHost();
    if (!host) {
      this.mapUnavailable.set(true);
      this.isParsingGeoJson.set(false);
      return;
    }

    if (host.clientWidth < 2 || host.clientHeight < 2) {
      // MapLibre throws / matrix-crash if the container is 0×0 at construct.
      return;
    }

    if (this.map) return;

    try {
      // No maxBounds: on globe it clamps/sticks mid-drag and feels like a freeze.
      // (#6148 was exact ±180 span; omit bounds entirely for free pan/rotate.)
      this.map = new maplibregl.Map({
        container: host,
        style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
        center: [0, 20],
        zoom: 3,
        minZoom: 2.2,
        clickTolerance: 12, // default 3px → false nation open su globe/trackpad
        attributionControl: { compact: true },
        fadeDuration: 0,
        renderWorldCopies: false,
      });
    } catch (err) {
      console.error('[RadarMapMaplibre] Map init failed:', err);
      this.mapUnavailable.set(true);
      this.isParsingGeoJson.set(false);
      return;
    }

    this.mapUnavailable.set(false);
    this.map.on('load', () => {
      if (this.destroyed || !this.map) return;
      try {
        this.map.resize();
      } catch {
        /* ignore */
      }
      this.applyProjectionPreference();
      this.loadGeoJson();
    });

    this.map.on('error', (e) => {
      const err = e?.error ?? e;
      console.warn('[RadarMapMaplibre] map error:', err);
      // Style CDN bloccato/fallito: non lasciare il loader "INIZIALIZZAZIONE RADAR" infinito.
      if (this.isParsingGeoJson()) {
        this.isParsingGeoJson.set(false);
      }
    });

    this.map.on('zoomend', () => this.onZoomEnd());
    this.map.on('mousedown', (e) => {
      this.pointerDownPoint = { x: e.point.x, y: e.point.y };
      this.suppressNextMapClick = false;
    });
    const markGesture = (): void => {
      this.suppressNextMapClick = true;
      this.suppressCountryClickUntil = performance.now() + 350;
    };
    this.map.on('dragstart', markGesture);
    this.map.on('rotatestart', markGesture);
    this.map.on('pitchstart', markGesture);
    this.map.on('mouseup', (e) => {
      if (!this.pointerDownPoint) return;
      const dx = e.point.x - this.pointerDownPoint.x;
      const dy = e.point.y - this.pointerDownPoint.y;
      if (dx * dx + dy * dy > this.DRAG_CLICK_PX * this.DRAG_CLICK_PX) {
        this.suppressNextMapClick = true;
        this.suppressCountryClickUntil = performance.now() + 350;
      }
      this.pointerDownPoint = null;
    });
    this.map.on('click', (e) => this.onMapClick(e));
  }

  /** Resolve map container: viewChild signal, then getElementById fallback. */
  private resolveMapHost(): HTMLElement | null {
    const fromQuery = this.mapHost()?.nativeElement;
    if (fromQuery instanceof HTMLElement) return fromQuery;
    return document.getElementById('radar-map-maplibre');
  }

  /** Attende layout non-zero (rAF + ResizeObserver) prima di ``new Map``. */
  private scheduleMapInit(attempt: number): void {
    if (this.destroyed || this.map) return;
    const host = this.resolveMapHost();
    if (host && host.clientWidth >= 2 && host.clientHeight >= 2) {
      this.initMap();
      return;
    }
    if (attempt >= 60) {
      console.error('[RadarMapMaplibre] Map host never gained size', {
        w: host?.clientWidth ?? null,
        h: host?.clientHeight ?? null,
      });
      this.mapUnavailable.set(true);
      this.isParsingGeoJson.set(false);
      return;
    }
    if (attempt === 0 && host && typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(() => {
        if (this.destroyed || this.map) {
          ro.disconnect();
          return;
        }
        if (host.clientWidth >= 2 && host.clientHeight >= 2) {
          ro.disconnect();
          this.initMap();
        }
      });
      ro.observe(host);
      this.destroyRef.onDestroy(() => ro.disconnect());
    }
    this.scheduleTimeout(() => this.scheduleMapInit(attempt + 1), attempt === 0 ? 0 : 50);
  }

  private applyProjectionPreference(): void {
    if (!this.map) return;
    let pref: string | null = null;
    try {
      pref = localStorage.getItem('radar.mapProjection');
    } catch {
      pref = null;
    }

    if (pref === 'mercator') {
      this.useMercatorPitch();
      return;
    }

    // Globe dopo load+resize: evita crash _calcMatrices su container non pronto.
    try {
      const mapWithProjection = this.map as MapLibreMap & {
        setProjection?: (p: { type: string }) => void;
      };
      if (typeof mapWithProjection.setProjection === 'function') {
        mapWithProjection.setProjection({ type: 'globe' });
        this.projectionMode.set('globe');
        requestAnimationFrame(() => {
          try {
            this.map?.resize();
          } catch {
            /* ignore */
          }
        });
        return;
      }
      this.useMercatorPitch();
    } catch (err) {
      console.warn('[RadarMapMaplibre] globe projection unavailable, using 2.5D:', err);
      this.useMercatorPitch();
    }
  }

  private useMercatorPitch(): void {
    if (!this.map) return;
    this.projectionMode.set('mercator');
    try {
      const mapWithProjection = this.map as MapLibreMap & {
        setProjection?: (p: { type: string }) => void;
      };
      mapWithProjection.setProjection?.({ type: 'mercator' });
    } catch {
      /* ignore */
    }
    this.map.setMaxPitch(60);
    this.map.setPitch(45);
  }

  private onZoomEnd(): void {
    if (this.destroyed || !this.map) return;
    const zoom = this.map.getZoom();
    this.currentZoomLevel.set(zoom);
    this.refreshHatchingStyles();
    this.syncSummaryMarkerVisibility();

    this.syncRelationsVisibility();

    const nationOpen = this.articles().length > 0 || !!this.focusCountryCode();
    if (
      !this.isNavigating &&
      nationOpen &&
      zoom < MAP_ZOOM_PIN_THRESHOLD &&
      !!this.lastSpiderfyCategory
    ) {
      this.collapseAllGraphs(true);
    } else if (
      !this.isNavigating &&
      nationOpen &&
      zoom >= MAP_ZOOM_PIN_THRESHOLD &&
      this.lastSpiderfyCountry &&
      this.lastSpiderfyCategory
    ) {
      const country = this.lastSpiderfyCountry;
      const category = this.lastSpiderfyCategory;
      this.scheduleTimeout(() => {
        if (this.destroyed || !this.map) return;
        if (this.map.getZoom() < MAP_ZOOM_PIN_THRESHOLD) return;
        this.focusAndSpiderfyCategory(country, category);
      }, 50);
    } else if (zoom < MAP_ZOOM_PIN_THRESHOLD && !this.isNavigating && !nationOpen) {
      this.collapseAllGraphs(true);
    }
  }

  private onMapClick(e: maplibregl.MapMouseEvent): void {
    if (!this.map) return;
    if (this.shouldIgnoreCountryClick()) return;
    const original = e.originalEvent as (Event & { _radarHandled?: boolean }) | undefined;
    if (original?._radarHandled) return;
    if (this.focusCountryCode() && this.articles().length > 0) return;

    if (this.currentZoomLevel() < MAP_ZOOM_PIN_THRESHOLD) {
      const code = this.pickCountryCodeAt(e.point);
      if (code) {
        if (original) original._radarHandled = true;
        this.countryClicked.emit({ countryCode: code });
        return;
      }
    }
    this.collapseAllGraphs(true);
  }

  /** Ignora click nazione durante/ subito dopo pan/rotate/pitch. */
  private shouldIgnoreCountryClick(): boolean {
    if (this.suppressNextMapClick) return true;
    if (this.isNavigating) return true;
    if (performance.now() < this.suppressCountryClickUntil) return true;
    try {
      if (this.map?.isMoving()) return true;
    } catch {
      /* ignore */
    }
    return false;
  }

  private loadGeoJson(): void {
    this.geoJsonSub?.unsubscribe();
    this.geoJsonSub = this.http
      .get<GeoJSON.FeatureCollection>('assets/data/countries.geo.json')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (geoData) => this.installCountriesSource(geoData),
        error: (err) => {
          console.error('[RadarMapMaplibre] Errore GeoJSON:', err);
          this.isParsingGeoJson.set(false);
        },
      });
  }

  private installCountriesSource(geoData: GeoJSON.FeatureCollection): void {
    if (!this.map || this.destroyed) {
      this.isParsingGeoJson.set(false);
      return;
    }

    const features = geoData.features.map((feature, idx) => {
      let code =
        feature.properties?.['ISO3166-1-Alpha-2'] ?? feature.properties?.['ISO_A2'] ?? 'XX';
      if (code === '-99' || !code || code === 'XX') {
        const name = feature.properties?.['name'];
        if (name === 'France') code = 'FR';
        else if (name === 'Norway') code = 'NO';
      }
      const props = { ...(feature.properties ?? {}), 'ISO3166-1-Alpha-2': code, _radarId: code };
      this.cacheCountryGeometry(code, feature);
      return { ...feature, id: code || idx, properties: props };
    });

    this.countriesGeoJson = { type: 'FeatureCollection', features };

    if (this.map.getSource(this.COUNTRIES_SOURCE)) {
      (this.map.getSource(this.COUNTRIES_SOURCE) as GeoJSONSource).setData(this.countriesGeoJson);
    } else {
      this.map.addSource(this.COUNTRIES_SOURCE, {
        type: 'geojson',
        data: this.countriesGeoJson,
        promoteId: '_radarId',
      });
      this.ensureCountryCategoryFillLayers();
      this.silenceLegacyCategoryFillLayers();
      // Hit-layer quasi invisibile: click zoom-out sulle nazioni con notizie.
      this.map.addLayer({
        id: this.COUNTRIES_FILL,
        type: 'fill',
        source: this.COUNTRIES_SOURCE,
        paint: {
          'fill-color': '#ffffff',
          'fill-opacity': [
            'case',
            ['==', ['to-number', ['coalesce', ['get', 'fillActive'], 0]], 1],
            0.01,
            0,
          ],
        },
      });
      this.map.addLayer({
        id: this.COUNTRIES_LINE,
        type: 'line',
        source: this.COUNTRIES_SOURCE,
        paint: {
          'line-color':
            getComputedStyle(document.documentElement)
              .getPropertyValue('--color-map-stroke')
              .trim() || 'rgba(0, 212, 255, 0.15)',
          'line-width': 0.5,
        },
      });

      this.map.on('click', this.COUNTRIES_FILL, (e: MapLayerMouseEvent) => {
        if (this.shouldIgnoreCountryClick()) return;
        // Solo fill zoom-out + nazioni con notizie.
        if (this.currentZoomLevel() >= MAP_ZOOM_PIN_THRESHOLD) return;
        const feat = e.features?.[0];
        const code = String(feat?.properties?.['ISO3166-1-Alpha-2'] ?? '');
        if (!code || code === 'XX') return;
        const hasNews = this.countries().some(
          (c) => c.country_code === code && (c.categories?.length ?? 0) > 0,
        );
        if (!hasNews) return;
        if (e.originalEvent) {
          (e.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
        }
        if (this.focusCountryCode() === code && this.articles().length > 0) return;
        this.countryClicked.emit({ countryCode: code });
      });

      this.map.on('mouseenter', this.COUNTRIES_FILL, () => {
        if (this.map) this.map.getCanvas().style.cursor = 'pointer';
      });
      this.map.on('mouseleave', this.COUNTRIES_FILL, () => {
        if (this.map) this.map.getCanvas().style.cursor = '';
      });
    }

    if (!this.map.getSource(this.RELATIONS_SOURCE)) {
      this.map.addSource(this.RELATIONS_SOURCE, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      this.map.addLayer({
        id: this.RELATIONS_LINE,
        type: 'line',
        source: this.RELATIONS_SOURCE,
        filter: ['==', ['get', 'role'], 'visual'],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['get', 'weight'],
          'line-opacity': ['get', 'opacity'],
        },
      });
      this.map.addLayer({
        id: this.RELATIONS_HIT,
        type: 'line',
        source: this.RELATIONS_SOURCE,
        filter: ['==', ['get', 'role'], 'hit'],
        paint: {
          'line-color': '#ffffff',
          'line-width': ['get', 'hitWeight'],
          'line-opacity': 0,
        },
      });

      this.map.on('click', this.RELATIONS_HIT, (e: MapLayerMouseEvent) => {
        if (this.shouldIgnoreCountryClick()) return;
        const feat = e.features?.[0];
        if (!feat?.properties) return;
        if (e.originalEvent) {
          (e.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
        }
        const sourceCountry = String(feat.properties['sourceCountry'] ?? '');
        const targetCountry = String(feat.properties['targetCountry'] ?? '');
        const category = feat.properties['category']
          ? (String(feat.properties['category']) as PrimaryCategory)
          : undefined;
        if (!sourceCountry || !targetCountry) return;
        this.relationClicked.emit({
          sourceCountry,
          targetCountry,
          ...(category ? { category } : {}),
        });
      });
      this.map.on('mouseenter', this.RELATIONS_HIT, (e: MapLayerMouseEvent) => {
        if (this.map) this.map.getCanvas().style.cursor = 'pointer';
        this.applyRelationHover(e);
      });
      this.map.on('mousemove', this.RELATIONS_HIT, (e: MapLayerMouseEvent) => {
        this.applyRelationHover(e);
      });
      this.map.on('mouseleave', this.RELATIONS_HIT, () => {
        if (this.map) this.map.getCanvas().style.cursor = '';
        this.clearRelationHover();
      });
    }

    this.isParsingGeoJson.set(false);
    this.refreshHatchingStyles();
    this.applyGeometryInputs(
      this.articles(),
      this.countries(),
      this.mapSummary(),
      this.mapRelations(),
    );
  }

  private cacheCountryGeometry(code: string, feature: GeoJSON.Feature): void {
    if (!code || code === 'XX') return;
    const bbox = this.computeBbox(feature.geometry);
    if (bbox) {
      this.countryBounds.set(code, bbox);
    }
    if (code === 'US' || code === 'RU' || code === 'NL') return;
    if (this.countryCentroids.has(code)) return;
    const centroid = this.geometryLargestPolygonCentroid(feature.geometry);
    if (centroid) {
      this.countryCentroids.set(code, centroid);
    } else if (bbox) {
      this.countryCentroids.set(code, {
        lat: (bbox[0][1] + bbox[1][1]) / 2,
        lng: (bbox[0][0] + bbox[1][0]) / 2,
      });
    }
  }

  /** Absolute shoelace area of an outer ring (lng/lat). */
  private ringArea(ring: number[][]): number {
    const len =
      ring.length > 1 &&
      ring[0][0] === ring[ring.length - 1][0] &&
      ring[0][1] === ring[ring.length - 1][1]
        ? ring.length - 1
        : ring.length;
    if (len < 3) return 0;
    let area = 0;
    for (let i = 0; i < len; i++) {
      const [x1, y1] = ring[i];
      const [x2, y2] = ring[(i + 1) % len];
      area += x1 * y2 - x2 * y1;
    }
    return Math.abs(area) * 0.5;
  }

  /** Shoelace centroid of an outer ring; falls back to vertex average. */
  private ringCentroid(ring: number[][]): LatLng | null {
    const len =
      ring.length > 1 &&
      ring[0][0] === ring[ring.length - 1][0] &&
      ring[0][1] === ring[ring.length - 1][1]
        ? ring.length - 1
        : ring.length;
    if (len < 1) return null;
    let area2 = 0;
    let cx = 0;
    let cy = 0;
    for (let i = 0; i < len; i++) {
      const [x1, y1] = ring[i];
      const [x2, y2] = ring[(i + 1) % len];
      const cross = x1 * y2 - x2 * y1;
      area2 += cross;
      cx += (x1 + x2) * cross;
      cy += (y1 + y2) * cross;
    }
    if (Math.abs(area2) < 1e-12) {
      let sx = 0;
      let sy = 0;
      for (let i = 0; i < len; i++) {
        sx += ring[i][0];
        sy += ring[i][1];
      }
      return { lat: sy / len, lng: sx / len };
    }
    return { lat: cy / (3 * area2), lng: cx / (3 * area2) };
  }

  /**
   * Polygon → outer-ring centroid. MultiPolygon → largest-area polygon centroid
   * (avoids NL Caribbean / FR overseas pulling the pin into the ocean).
   */
  private geometryLargestPolygonCentroid(geometry: GeoJSON.Geometry | null): LatLng | null {
    if (!geometry) return null;
    if (geometry.type === 'Polygon') {
      return this.ringCentroid(geometry.coordinates[0] ?? []);
    }
    if (geometry.type === 'MultiPolygon') {
      let best: LatLng | null = null;
      let bestArea = -1;
      for (const poly of geometry.coordinates) {
        const ring = poly[0] ?? [];
        const area = this.ringArea(ring);
        if (area > bestArea) {
          bestArea = area;
          best = this.ringCentroid(ring);
        }
      }
      return best;
    }
    return null;
  }

  private computeBbox(
    geometry: GeoJSON.Geometry | null,
  ): [[number, number], [number, number]] | null {
    if (!geometry) return null;
    let minLng = Infinity;
    let minLat = Infinity;
    let maxLng = -Infinity;
    let maxLat = -Infinity;
    const visit = (coords: unknown): void => {
      if (!Array.isArray(coords)) return;
      if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
        const lng = coords[0] as number;
        const lat = coords[1] as number;
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
    return [
      [minLng, minLat],
      [maxLng, maxLat],
    ];
  }

  private resolveCategoryColor(category: string, docStyle: CSSStyleDeclaration): string {
    // Infrastrutture (#9e9e9e) a bassa opacità sparisce sul basemap scuro — fill dedicato più chiaro.
    if (category === 'Infrastrutture') return '#c5ccd6';
    const cssVar = this.CATEGORY_CSS_VARS[category] || '--color-text-accent';
    return docStyle.getPropertyValue(cssVar).trim() || '#58a6ff';
  }

  /** Categorie per nazione da map-summary (stessa SoT dei pin / carosello). */
  private categoriesByCountryFromSummary(summary: MapSummaryRow[]): Map<string, string[]> {
    const grouped = new Map<string, Set<string>>();
    for (const row of summary) {
      const code = row.country_code || '';
      if (!code || code === 'XX' || row.article_count <= 0) continue;
      const set = grouped.get(code) ?? new Set<string>();
      set.add(row.primary_category);
      grouped.set(code, set);
    }
    const out = new Map<string, string[]>();
    grouped.forEach((set, code) => {
      out.set(code, Array.from(set));
    });
    return out;
  }

  private categoryFillLayerId(category: string): string {
    return `${this.COUNTRIES_FILL}-${category.toLowerCase().replace(/ /g, '-')}`;
  }

  /** Nasconde i fill solidi per-categoria della iterazione precedente (se presenti). */
  private silenceLegacyCategoryFillLayers(): void {
    if (!this.map) return;
    for (const category of Object.keys(this.CATEGORY_CSS_VARS)) {
      const layerId = this.categoryFillLayerId(category);
      if (this.map.getLayer(layerId)) {
        this.map.setPaintProperty(layerId, 'fill-opacity', 0);
      }
    }
  }

  /** Source + layer delle fasce tipologia (una fascia geografica per colore, no tile ripetuto). */
  private ensureCountryCategoryFillLayers(): void {
    if (!this.map) return;
    if (!this.map.getSource(this.COUNTRY_CAT_SOURCE)) {
      this.map.addSource(this.COUNTRY_CAT_SOURCE, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
    }
    if (this.map.getLayer(this.COUNTRY_CAT_FILL)) return;
    const beforeId = this.map.getLayer(this.COUNTRIES_FILL) ? this.COUNTRIES_FILL : undefined;
    this.map.addLayer(
      {
        id: this.COUNTRY_CAT_FILL,
        type: 'fill',
        source: this.COUNTRY_CAT_SOURCE,
        paint: {
          'fill-color': ['coalesce', ['get', 'fillColor'], '#58a6ff'],
          'fill-opacity': 0,
          'fill-antialias': true,
        },
      },
      beforeId,
    );
  }

  private refreshHatchingStyles(): void {
    if (!this.map || !this.countriesGeoJson) return;
    this.ensureCountryCategoryFillLayers();
    this.silenceLegacyCategoryFillLayers();
    const zoomedOut = this.currentZoomLevel() < MAP_ZOOM_PIN_THRESHOLD;
    const docStyle = getComputedStyle(document.documentElement);
    const strokeActive =
      docStyle.getPropertyValue('--color-map-stroke-active').trim() || 'rgba(0, 212, 255, 0.25)';
    const stroke =
      docStyle.getPropertyValue('--color-map-stroke').trim() || 'rgba(0, 212, 255, 0.15)';

    // Stessa SoT dei pin: map-summary filtrato (non un rollup parallelo).
    const catsByCode = this.categoriesByCountryFromSummary(this.mapSummary());
    const hatchAssignments: string[] = [];
    const stripFeatures: GeoJSON.Feature[] = [];
    const paintedCodes = new Set<string>();

    const hitFeatures = this.countriesGeoJson.features.map((feature) => {
      const code = String(feature.properties?.['ISO3166-1-Alpha-2'] ?? '');
      const cats = zoomedOut && code ? (catsByCode.get(code) ?? []) : [];
      const fillActive = cats.length > 0 ? 1 : 0;
      hatchAssignments.push(`${code}:${[...cats].sort().join('+')}`);
      // Una sola geometria per country_code (evita doppi set di fasce).
      if (cats.length > 0 && !paintedCodes.has(code)) {
        paintedCodes.add(code);
        stripFeatures.push(
          ...splitCountryByCategories(
            feature,
            cats,
            (cat) => this.resolveCategoryColor(cat, docStyle),
            this.CATEGORY_LEGEND_ORDER,
          ),
        );
      }
      return {
        ...feature,
        properties: {
          ...(feature.properties ?? {}),
          fillActive,
        },
      };
    });

    const fingerprint = `${zoomedOut ? 1 : 0}|${hatchAssignments.join(',')}`;
    if (fingerprint !== this.lastHatchFingerprint) {
      this.lastHatchFingerprint = fingerprint;
      this.countriesGeoJson = { type: 'FeatureCollection', features: hitFeatures };
      const countrySource = this.map.getSource(this.COUNTRIES_SOURCE) as GeoJSONSource | undefined;
      if (countrySource) {
        countrySource.setData(this.countriesGeoJson);
      }
      const catSource = this.map.getSource(this.COUNTRY_CAT_SOURCE) as GeoJSONSource | undefined;
      if (catSource) {
        catSource.setData({ type: 'FeatureCollection', features: stripFeatures });
      }
    }

    if (this.map.getLayer(this.COUNTRY_CAT_FILL)) {
      this.map.setPaintProperty(
        this.COUNTRY_CAT_FILL,
        'fill-opacity',
        zoomedOut ? this.CATEGORY_FILL_OPACITY : 0,
      );
    }

    if (this.map.getLayer(this.COUNTRIES_LINE)) {
      this.map.setPaintProperty(
        this.COUNTRIES_LINE,
        'line-color',
        zoomedOut ? strokeActive : stroke,
      );
    }

    const canvas = this.map.getContainer();
    if (zoomedOut) canvas.classList.add('zoom-out-mode');
    else canvas.classList.remove('zoom-out-mode');
  }

  private pickCountryCodeAt(point: maplibregl.PointLike): string | null {
    if (!this.map) return null;
    const features = this.map.queryRenderedFeatures(point, { layers: [this.COUNTRIES_FILL] });
    const hits = features
      .map((f) => String(f.properties?.['ISO3166-1-Alpha-2'] ?? ''))
      .filter((c) => !!c && c !== 'XX');
    if (hits.length === 0) return null;
    const withNews = hits.find((code) =>
      this.countries().some((c) => c.country_code === code && (c.categories?.length ?? 0) > 0),
    );
    return withNews ?? null;
  }

  private focusOnCountry(code: string): void {
    if (!this.map || this.isNavigating || this.destroyed) return;
    if (this.skipNextCountryFit) {
      this.skipNextCountryFit = false;
      return;
    }

    let bounds: [[number, number], [number, number]] | null = null;
    if (code === 'US') {
      bounds = [
        [-125.0, 24.396308],
        [-66.93457, 49.384358],
      ];
    } else if (code === 'RU') {
      bounds = [
        [19.6389, 41.1856],
        [169.0, 81.8587],
      ];
    } else {
      bounds = this.countryBounds.get(code) ?? null;
    }

    if (!bounds) return;
    this.isNavigating = true;
    this.map.fitBounds(bounds, { maxZoom: 4, duration: 1000, padding: 40 });
    let cleaned = false;
    const cleanup = () => {
      if (cleaned || this.destroyed) return;
      cleaned = true;
      this.finishNavigating();
      this.map?.off('moveend', cleanup);
    };
    this.map.once('moveend', cleanup);
    this.scheduleTimeout(cleanup, 1500);
  }

  private hasFiniteCoordinates(lat: number, lon: number): boolean {
    return (
      Number.isFinite(lat) &&
      Number.isFinite(lon) &&
      lat >= -90 &&
      lat <= 90 &&
      lon >= -180 &&
      lon <= 180
    );
  }

  private getCountryCentroid(code: string, summaryOverride?: MapSummaryRow[]): LatLng | null {
    if (code === 'US') return { lat: 37.0902, lng: -95.7129 };
    if (code === 'RU') return { lat: 61.524, lng: 105.3187 };
    if (code === 'NL') return { lat: 52.1326, lng: 5.2913 };
    if (this.countryCentroids.has(code)) return this.countryCentroids.get(code)!;

    const rows = (summaryOverride ?? this.mapSummary()).filter((r) => r.country_code === code);
    if (rows.length > 0) {
      let latSum = 0;
      let lngSum = 0;
      let countSum = 0;
      for (const r of rows) {
        if (this.hasFiniteCoordinates(r.latitude, r.longitude)) {
          latSum += r.latitude * r.article_count;
          lngSum += r.longitude * r.article_count;
          countSum += r.article_count;
        }
      }
      if (countSum > 0) {
        return { lat: latSum / countSum, lng: lngSum / countSum };
      }
    }
    return null;
  }

  private resolveCountryAnchorLatLng(
    code: string,
    fallbackArticles?: Article[],
    summaryOverride?: MapSummaryRow[],
  ): LatLng | null {
    const centroid = this.getCountryCentroid(code, summaryOverride);
    if (centroid) return centroid;
    if (!fallbackArticles?.length) return null;
    let latSum = 0;
    let lngSum = 0;
    let n = 0;
    for (const a of fallbackArticles) {
      if ((a.country_code || 'XX') !== code) continue;
      if (!this.hasFiniteCoordinates(a.latitude, a.longitude)) continue;
      latSum += a.latitude;
      lngSum += a.longitude;
      n++;
    }
    if (n === 0) return null;
    return { lat: latSum / n, lng: lngSum / n };
  }

  private updateMapData(
    articles: Article[],
    countries: CountrySummary[],
    summary: MapSummaryRow[],
    relations: MapRelationRow[] = [],
  ): void {
    if (!this.map) return;
    this.spiderfyGeneration++;
    this.clearSpiderfy();
    this.clearSummaryMarkers();
    this.clearDetailHubPin();
    this.detailArticlesByCategory.clear();

    if (articles.length === 0) {
      this.renderSummaryMarkers(summary);
      this.drawGeospatialRelations(relations);
      this.lastGeometryFingerprint = this.geometryFingerprint(articles, summary, relations);
      this.syncSummaryMarkerVisibility();
      this.syncRelationsVisibility();
      this.refreshHatchingStyles();
      void countries;
      return;
    }

    this.indexDetailArticles(articles);
    this.upsertDetailHubPin(articles);
    this.lastGeometryFingerprint = this.geometryFingerprint(articles, summary, relations);
    this.syncSummaryMarkerVisibility();
    this.syncRelationsVisibility();
    this.refreshHatchingStyles();
    void countries;
  }

  private indexDetailArticles(articles: Article[]): void {
    this.detailArticlesByCategory.clear();
    for (const article of articles) {
      const code = article.country_code || 'XX';
      if (code === 'XX') continue;
      const list = this.detailArticlesByCategory.get(article.primary_category) ?? [];
      list.push(article);
      this.detailArticlesByCategory.set(article.primary_category, list);
    }
  }

  private buildCountryPinHtml(
    total: number,
    categoryCounts: { category: string; count: number }[],
  ): HTMLElement {
    const segments = categoryCounts.filter((c) => c.count > 0).sort((a, b) => b.count - a.count);
    let cursor = 0;
    const parts: string[] = [];
    for (const s of segments) {
      const pct = (s.count / Math.max(1, total)) * 100;
      const cssVar = this.CATEGORY_CSS_VARS[s.category] ?? '--color-tecnologia';
      parts.push(`var(${cssVar}) ${cursor}% ${cursor + pct}%`);
      cursor += pct;
    }
    const conic =
      parts.length > 0
        ? `conic-gradient(from -90deg, ${parts.join(', ')})`
        : 'var(--color-tecnologia)';

    const root = document.createElement('div');
    root.className = 'radar-country-pin';
    const catLabel = segments.map((s) => s.category).join(', ');
    root.title = `${total} notizie${catLabel ? ` · ${catLabel}` : ''}`;

    const ring = document.createElement('div');
    ring.className = 'radar-country-pin__ring';
    ring.style.background = conic;

    const core = document.createElement('div');
    core.className = 'radar-country-pin__core';
    core.textContent = String(total);

    const tip = document.createElement('div');
    tip.className = 'radar-country-pin__tip';

    root.append(ring, core, tip);
    return root;
  }

  private buildSpiderRootHtml(articles: Article[]): HTMLElement {
    const categories = new Map<string, number>();
    for (const a of articles) {
      categories.set(a.primary_category, (categories.get(a.primary_category) ?? 0) + 1);
    }
    const total = Math.max(1, articles.length);
    const segments = Array.from(categories.entries())
      .map(([category, count]) => ({ category, count }))
      .filter((c) => c.count > 0)
      .sort((a, b) => b.count - a.count);
    let cursor = 0;
    const parts: string[] = [];
    for (const s of segments) {
      const pct = (s.count / total) * 100;
      const cssVar = this.CATEGORY_CSS_VARS[s.category] ?? '--color-tecnologia';
      parts.push(`var(${cssVar}) ${cursor}% ${cursor + pct}%`);
      cursor += pct;
    }
    const conic =
      parts.length > 0
        ? `conic-gradient(from -90deg, ${parts.join(', ')})`
        : 'var(--color-tecnologia)';

    const root = document.createElement('div');
    root.className = 'radar-spider-root';
    root.title = `${articles.length} notizie`;

    const ring = document.createElement('div');
    ring.className = 'radar-spider-root__ring';
    ring.style.background = conic;

    const core = document.createElement('div');
    core.className = 'radar-spider-root__core';
    core.textContent = String(articles.length);

    root.append(ring, core);
    return root;
  }

  private createArticleMarkerEl(article: Article, sizePx = 28): HTMLElement {
    const box = Math.max(16, Math.round(sizePx));
    const fontPx = Math.max(12, Math.round(box * 0.55));
    const emoji = this.CATEGORY_ICONS[article.primary_category] ?? '📍';
    const wrap = document.createElement('div');
    wrap.className = `marker-${article.primary_category.toLowerCase()}`;
    const el = document.createElement('div');
    el.className = 'marker-icon';
    el.style.width = `${box}px`;
    el.style.height = `${box}px`;
    el.style.fontSize = `${fontPx}px`;
    el.style.lineHeight = `${box}px`;
    el.style.textAlign = 'center';
    el.title = article.title;
    el.textContent = emoji;
    if (article.is_read) el.classList.add('marker-read');
    wrap.appendChild(el);
    return wrap;
  }

  private renderSummaryMarkers(summary: MapSummaryRow[]): void {
    this.clearSummaryMarkers();
    type Agg = { total: number; categories: Map<string, number> };
    const byCountry = new Map<string, Agg>();

    for (const row of summary) {
      const code = row.country_code || 'XX';
      if (code === 'XX' || row.article_count <= 0) continue;
      const cur = byCountry.get(code) ?? { total: 0, categories: new Map<string, number>() };
      cur.total += row.article_count;
      cur.categories.set(
        row.primary_category,
        (cur.categories.get(row.primary_category) ?? 0) + row.article_count,
      );
      byCountry.set(code, cur);
    }

    byCountry.forEach((agg, code) => {
      if (agg.total <= 0 || !this.map) return;
      const anchor = this.resolveCountryAnchorLatLng(code, undefined, summary);
      if (!anchor) return;
      const categoryCounts = Array.from(agg.categories.entries()).map(([category, count]) => ({
        category,
        count,
      }));
      const el = this.buildCountryPinHtml(agg.total, categoryCounts);
      const wrap = document.createElement('div');
      wrap.className = 'radar-country-pin-wrap';
      wrap.appendChild(el);
      wrap.addEventListener('click', (ev) => {
        ev.stopPropagation();
        (ev as Event & { _radarHandled?: boolean })._radarHandled = true;
        this.countryClicked.emit({ countryCode: code, preserveZoom: true });
      });

      const marker = new maplibregl.Marker({
        element: wrap,
        anchor: 'bottom',
        offset: [0, 0],
      })
        .setLngLat([anchor.lng, anchor.lat])
        .addTo(this.map);
      this.summaryMarkers.push(marker);
    });
  }

  private clearSummaryMarkers(): void {
    for (const m of this.summaryMarkers) m.remove();
    this.summaryMarkers = [];
  }

  private syncSummaryMarkerVisibility(): void {
    if (!this.map) return;
    const show = this.map.getZoom() >= MAP_ZOOM_PIN_THRESHOLD && this.articles().length === 0;
    for (const m of this.summaryMarkers) {
      const el = m.getElement();
      el.style.display = show ? '' : 'none';
      el.style.pointerEvents = show ? 'auto' : 'none';
    }
  }

  private syncRelationsVisibility(): void {
    if (!this.map) return;
    const show = this.articles().length === 0;
    const vis = show ? 'visible' : 'none';
    if (this.map.getLayer(this.RELATIONS_LINE)) {
      this.map.setLayoutProperty(this.RELATIONS_LINE, 'visibility', vis);
    }
    if (this.map.getLayer(this.RELATIONS_HIT)) {
      this.map.setLayoutProperty(this.RELATIONS_HIT, 'visibility', vis);
    }
  }

  private drawGeospatialRelations(relations: MapRelationRow[]): void {
    if (!this.map) return;
    const source = this.map.getSource(this.RELATIONS_SOURCE) as GeoJSONSource | undefined;
    if (!source) return;

    this.clearRelationHover();

    if (relations.length === 0) {
      source.setData({ type: 'FeatureCollection', features: [] });
      return;
    }

    // MapLibre: always one solid multicolor arc per nation pair (no per-cat fan / geometric dash).
    // Leaflet legacy keeps zoom-gated dash+fan — do not port that here.
    source.setData({
      type: 'FeatureCollection',
      features: this.buildMacroRelationFeatures(relations),
    });
  }

  /** One great-circle per pair; color segments ∝ category volume (solid, all zoom levels). */
  private buildMacroRelationFeatures(relations: MapRelationRow[]): GeoJSON.Feature[] {
    const aggregated = this.aggregateRelations(relations);
    const docStyle = getComputedStyle(document.documentElement);
    const features: GeoJSON.Feature[] = [];
    const steps = 30;

    for (const agg of aggregated) {
      const p0 = this.getCountryCentroid(agg.source_country);
      const p2 = this.getCountryCentroid(agg.target_country);
      if (!p0 || !p2) continue;
      const coords = greatCircle(p0.lat, p0.lng, p2.lat, p2.lng, steps, 0.2);
      const weight = Math.min(3, 1 + agg.totalVolume * 0.3);
      const opacity = 0.45;
      const arcKey = `${agg.source_country}|${agg.target_country}`;
      const breakdownText = agg.breakdown.map((b) => `${b.category} ${b.volume}`).join(' · ');
      const tooltipText = `${agg.source_country} ↔ ${agg.target_country} · ${breakdownText} · n=${agg.totalVolume}`;
      let currentStep = 0;
      let seg = 0;

      for (let idx = 0; idx < agg.breakdown.length; idx++) {
        const item = agg.breakdown[idx];
        let itemSteps = Math.round((item.volume / agg.totalVolume) * steps);
        if (idx === agg.breakdown.length - 1) itemSteps = steps - currentStep;
        if (itemSteps <= 0 && currentStep < steps) itemSteps = 1;
        const startIdx = currentStep;
        const endIdx = Math.min(steps, currentStep + itemSteps);
        if (startIdx >= endIdx) continue;
        const slice = coords.slice(startIdx, endIdx + 1);
        if (slice.length < 2) continue;
        const color = this.resolveCategoryColor(item.category, docStyle);
        features.push({
          type: 'Feature',
          id: `${arcKey}|v|${seg}`,
          properties: {
            role: 'visual',
            arcKey,
            color,
            weight,
            opacity,
          },
          geometry: { type: 'LineString', coordinates: slice },
        });
        seg++;
        currentStep = endIdx;
      }

      features.push({
        type: 'Feature',
        id: `${arcKey}|h`,
        properties: {
          role: 'hit',
          arcKey,
          hitWeight: Math.max(28, weight * 6),
          sourceCountry: agg.source_country,
          targetCountry: agg.target_country,
          tooltipText,
        },
        geometry: { type: 'LineString', coordinates: coords },
      });
    }
    return features;
  }

  private applyRelationHover(e: MapLayerMouseEvent): void {
    if (!this.map) return;
    const feat = e.features?.[0];
    if (!feat?.properties) return;
    const arcKey = String(feat.properties['arcKey'] ?? '');
    const tooltipText = String(feat.properties['tooltipText'] ?? '');
    if (!arcKey) return;

    if (arcKey !== this.hoveredArcKey) {
      this.hoveredArcKey = arcKey;
      // Paint by arcKey (affidabile): feature-state su GeoJSON tileati falliva spesso.
      this.map.setPaintProperty(this.RELATIONS_LINE, 'line-width', [
        'case',
        ['==', ['get', 'arcKey'], arcKey],
        ['+', ['to-number', ['get', 'weight']], 3],
        ['to-number', ['get', 'weight']],
      ]);
      this.map.setPaintProperty(this.RELATIONS_LINE, 'line-opacity', [
        'case',
        ['==', ['get', 'arcKey'], arcKey],
        1,
        ['to-number', ['get', 'opacity']],
      ]);
    }

    if (tooltipText) {
      if (!this.relationPopup) {
        this.relationPopup = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          className: 'radar-relation-tooltip',
          offset: 12,
          maxWidth: '320px',
        });
      }
      this.relationPopup.setLngLat(e.lngLat).setText(tooltipText).addTo(this.map);
    }
  }

  private clearRelationHover(): void {
    if (this.map && this.hoveredArcKey) {
      this.map.setPaintProperty(this.RELATIONS_LINE, 'line-width', [
        'to-number',
        ['get', 'weight'],
      ]);
      this.map.setPaintProperty(this.RELATIONS_LINE, 'line-opacity', [
        'to-number',
        ['get', 'opacity'],
      ]);
    }
    this.hoveredArcKey = null;
    this.relationPopup?.remove();
    this.relationPopup = null;
  }

  private aggregateRelations(relations: MapRelationRow[]): {
    source_country: string;
    target_country: string;
    totalVolume: number;
    breakdown: { category: string; volume: number }[];
  }[] {
    const map = new Map<
      string,
      {
        source_country: string;
        target_country: string;
        totalVolume: number;
        breakdown: { category: string; volume: number }[];
      }
    >();
    for (const r of relations) {
      const key = `${r.source_country}|${r.target_country}`;
      let agg = map.get(key);
      if (!agg) {
        agg = {
          source_country: r.source_country,
          target_country: r.target_country,
          totalVolume: 0,
          breakdown: [],
        };
        map.set(key, agg);
      }
      agg.totalVolume += r.volume;
      agg.breakdown.push({ category: r.primary_category, volume: r.volume });
    }
    const result = Array.from(map.values());
    for (const agg of result) {
      agg.breakdown.sort((a, b) => b.volume - a.volume);
    }
    return result;
  }

  private clearDetailHubPin(): void {
    this.hubMarker?.remove();
    this.hubMarker = null;
  }

  private upsertDetailHubPin(articles: Article[]): void {
    this.clearDetailHubPin();
    if (!this.map || articles.length === 0) return;

    const focus = this.focusCountryCode();
    const code =
      (focus && focus !== 'XX' ? focus : null) ??
      this.dominantArticleCountry(articles) ??
      (articles[0]?.country_code && articles[0].country_code !== 'XX'
        ? articles[0].country_code
        : null);
    if (!code) return;
    const anchor = this.resolveCountryAnchorLatLng(code, articles);
    if (!anchor) return;

    const el = this.buildSpiderRootHtml(articles);
    const wrap = document.createElement('div');
    wrap.className = 'radar-spider-root-wrap';
    wrap.appendChild(el);
    wrap.addEventListener('click', (ev) => {
      ev.stopPropagation();
      (ev as Event & { _radarHandled?: boolean })._radarHandled = true;
      const cat =
        articles.find((a) => a.country_code === code)?.primary_category ??
        articles[0]?.primary_category;
      if (code && cat) this.focusAndSpiderfyCategory(code, cat);
    });

    this.hubMarker = new maplibregl.Marker({ element: wrap, anchor: 'center' })
      .setLngLat([anchor.lng, anchor.lat])
      .addTo(this.map);
  }

  private dominantArticleCountry(articles: Article[]): string | null {
    const totals = new Map<string, number>();
    for (const a of articles) {
      const code = a.country_code || 'XX';
      if (code === 'XX') continue;
      totals.set(code, (totals.get(code) ?? 0) + 1);
    }
    let best: string | null = null;
    let bestCount = 0;
    totals.forEach((count, c) => {
      if (count > bestCount) {
        best = c;
        bestCount = count;
      }
    });
    return best;
  }

  /**
   * Multiplier Leaflet MC (spiderfyDistanceForCount) — alimenta cerchio/spirale pixel.
   * @see leaflet.markercluster MarkerCluster.Spiderfier.js
   */
  private spiderfyDistanceMultiplier(n: number): number {
    if (n <= 4) return 3.8;
    if (n <= 8) return 3.2;
    if (n <= 14) return 2.7;
    if (n <= 20) return 2.3;
    if (n <= 32) return 1.9;
    if (n <= 48) return 1.6;
    return 1.4;
  }

  private spiderfyIconSizeForCount(n: number): number {
    if (n <= 4) return 36;
    if (n <= 8) return 30;
    if (n <= 14) return 26;
    if (n <= 20) return 22;
    if (n <= 32) return 18;
    if (n <= 48) return 16;
    return 14;
  }

  /** Cerchio per n &lt; 9 (come MC `_generatePointsCircle`). */
  private generateSpiderfyCircle(
    count: number,
    centerPx: { x: number; y: number },
    multiplier: number,
  ): Array<{ x: number; y: number }> {
    const footSeparation = 25;
    const circumference = multiplier * footSeparation * (2 + count);
    let legLength = Math.max(35, circumference / (Math.PI * 2));
    // Extra margine rispetto all'icon size così i marker non si toccano.
    const iconPx = this.spiderfyIconSizeForCount(count);
    legLength = Math.max(legLength, (count * (iconPx + 10)) / (Math.PI * 2));
    const angleStep = (Math.PI * 2) / count;
    const res: Array<{ x: number; y: number }> = [];
    for (let i = 0; i < count; i++) {
      const angle = i * angleStep - Math.PI / 2;
      res.push({
        x: Math.round(centerPx.x + legLength * Math.cos(angle)),
        y: Math.round(centerPx.y + legLength * Math.sin(angle)),
      });
    }
    return res;
  }

  /** Spirale per n ≥ 9 (come MC `_generatePointsSpiral`) — evita l'anello pieno. */
  private generateSpiderfySpiral(
    count: number,
    centerPx: { x: number; y: number },
    multiplier: number,
  ): Array<{ x: number; y: number }> {
    const twoPi = Math.PI * 2;
    let legLength = multiplier * 11; // _spiralLengthStart
    const separation = multiplier * 28; // _spiralFootSeparation
    const lengthFactor = multiplier * 5 * twoPi; // _spiralLengthFactor
    let angle = 0;
    const res: Array<{ x: number; y: number }> = new Array(count);
    for (let i = count; i >= 0; i--) {
      if (i < count) {
        res[i] = {
          x: Math.round(centerPx.x + legLength * Math.cos(angle)),
          y: Math.round(centerPx.y + legLength * Math.sin(angle)),
        };
      }
      angle += separation / legLength + i * 0.0005;
      legLength += lengthFactor / angle;
    }
    return res;
  }

  private spiderfyScreenPositions(
    count: number,
    centerPx: { x: number; y: number },
  ): Array<{ x: number; y: number }> {
    const mult = this.spiderfyDistanceMultiplier(count);
    // MC switchover: spiral from 9+ markers.
    if (count >= 9) {
      return this.generateSpiderfySpiral(count, centerPx, mult);
    }
    return this.generateSpiderfyCircle(count, centerPx, mult);
  }

  private spiderfyAndCreateRoot(
    arts: Article[],
    anchor: LatLng,
    generation: number,
    countryCode: string,
    category: string,
  ): boolean {
    if (this.destroyed || !this.map) return false;
    if (generation !== this.spiderfyGeneration) return false;
    if (arts.length === 0) return false;

    this.clearDetailHubPin();
    this.clearSpiderfy();

    const n = arts.length;
    const iconPx = this.spiderfyIconSizeForCount(n);
    const centerPx = this.map.project([anchor.lng, anchor.lat]);
    const positions = this.spiderfyScreenPositions(n, { x: centerPx.x, y: centerPx.y });

    const rootEl = this.buildSpiderRootHtml(arts);
    const rootWrap = document.createElement('div');
    rootWrap.className = 'radar-spider-root-wrap';
    rootWrap.appendChild(rootEl);
    rootWrap.addEventListener('click', (ev) => {
      ev.stopPropagation();
      (ev as Event & { _radarHandled?: boolean })._radarHandled = true;
      this.collapseAllGraphs(true, true);
    });
    this.spiderRootMarker = new maplibregl.Marker({ element: rootWrap, anchor: 'center' })
      .setLngLat([anchor.lng, anchor.lat])
      .addTo(this.map);

    for (let i = 0; i < arts.length; i++) {
      const article = arts[i];
      const pt = positions[i];
      const ll = this.map.unproject([pt.x, pt.y]);
      const el = this.createArticleMarkerEl(article, iconPx);
      el.style.margin = '0';
      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        (ev as Event & { _radarHandled?: boolean })._radarHandled = true;
        this.markerClicked.emit(article);
      });
      const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([ll.lng, ll.lat])
        .addTo(this.map!);
      this.spiderMarkers.push({ marker, article, el });
    }

    this.lastSpiderfyCountry = countryCode;
    this.lastSpiderfyCategory = category;
    if (this.pendingHighlightArticle) this.applyHighlight(5);
    return true;
  }

  private clearSpiderfy(): void {
    this.spiderRootMarker?.remove();
    this.spiderRootMarker = null;
    for (const s of this.spiderMarkers) s.marker.remove();
    this.spiderMarkers = [];
    this.highlightedEl = null;
  }

  private restoreNationHubPin(): void {
    this.clearSpiderfy();
    if (this.articles().length > 0) {
      this.upsertDetailHubPin(this.articles());
    }
  }

  private syncMarkerReadState(articles: Article[]): void {
    const byId = new Map(articles.map((a) => [a.id, a]));
    for (const s of this.spiderMarkers) {
      const latest = byId.get(s.article.id);
      if (!latest) continue;
      s.article.is_read = latest.is_read;
      const inner = s.el.querySelector('.marker-icon');
      if (inner) {
        inner.classList.toggle('marker-read', !!latest.is_read);
      }
      s.el.classList.toggle('marker-read', !!latest.is_read);
    }
  }

  private applyHighlight(retries: number): void {
    if (!this.pendingHighlightArticle || this.destroyed) return;
    const article = this.pendingHighlightArticle;
    const found = this.spiderMarkers.find((s) => s.article.id === article.id);
    if (found) {
      found.el.classList.add('marker-highlight');
      this.highlightedEl = found.el;
      return;
    }
    if (retries > 0) {
      this.scheduleTimeout(() => this.applyHighlight(retries - 1), 150);
    }
  }

  private teardown(): void {
    this.destroyed = true;
    this.spiderfyGeneration++;
    this.geoJsonSub?.unsubscribe();
    this.geoJsonSub = null;
    this.clearPendingTimeouts();
    this.clearRelationHover();
    this.clearSpiderfy();
    this.clearSummaryMarkers();
    this.clearDetailHubPin();
    this.map?.remove();
    this.map = null;
  }
}
