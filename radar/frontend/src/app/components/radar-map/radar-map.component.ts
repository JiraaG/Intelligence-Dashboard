import {
  Component,
  AfterViewInit,
  DestroyRef,
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
import type * as Leaflet from 'leaflet';
import { Article, CountrySummary, PrimaryCategory } from '../../models/article.model';
import { MapSummaryRow } from '../../models/map-summary.model';
import { MapRelationRow } from '../../models/map-relation.model';

/** Payload quando si apre una nazione da poligono o pin summary. */
export interface CountryOpenRequest {
  countryCode: string;
  /** Se settato (pallino categoria / detail), sidebar e spiderfy su quella categoria. */
  category?: PrimaryCategory;
  /** Mantieni la camera corrente (no fitBounds / dezoom). */
  preserveZoom?: boolean;
}

/** Forma minima del MarkerCluster UMD su ``window.L`` (non ESM). */
interface MarkerClusterGroupLike {
  addLayer(layer: Leaflet.Layer): this;
  removeLayer(layer: Leaflet.Layer): this;
  clearLayers(): this;
  getLayers(): Leaflet.Layer[];
  getAllChildMarkers(): Leaflet.Marker[];
  getVisibleParent(marker: Leaflet.Marker): Leaflet.Marker | null;
  on(type: string, fn: Leaflet.LeafletEventHandlerFn): this;
  addTo(map: Leaflet.Map): this;
  /** Forza ridisegno icone dopo race clearLayers/addLayer. */
  refreshClusters?: (layers?: Leaflet.Layer | Leaflet.Layer[]) => this;
  _spiderfied?: { unspiderfy?: () => void } | null;
  options?: { spiderfyDistanceMultiplier?: number };
}

interface MarkerClusterLike extends Leaflet.Marker {
  getAllChildMarkers(): Leaflet.Marker[];
}

/** Leaflet globale da ``angular.json`` scripts[] + plugin markercluster UMD. */
type LeafletGlobal = typeof import('leaflet') & {
  markerClusterGroup: (options?: Record<string, unknown>) => MarkerClusterGroupLike;
};

interface ArticleMarkerMeta {
  articleData?: Article;
  realLatLng?: Leaflet.LatLng;
  isDummy?: boolean;
  /** Marker aggregato da map-summary (day-view, prima del nation open). */
  isSummary?: boolean;
  summaryCount?: number;
  summaryCountry?: string;
  summaryCategory?: string;
}

type ArticleMarker = Leaflet.Marker &
  ArticleMarkerMeta & {
    _icon?: HTMLElement | null;
  };

/**
 * Legge ``window.L`` iniettato dagli script globali (ESBuild + MarkerCluster UMD).
 * Vietato ``import * as L from 'leaflet'`` / side-effect markercluster nel componente.
 *
 * @see SoT: AGENTS.md §5; frontend.md §10.
 */
function getLeaflet(): LeafletGlobal | null {
  const L = (window as unknown as { L?: LeafletGlobal }).L;
  if (!L || typeof L.map !== 'function' || typeof L.markerClusterGroup !== 'function') {
    return null;
  }
  return L;
}

/**
 * Mappa Leaflet Radar: hatching GeoJSON (zoom &lt; 5), pin day-view da map-summary,
 * cluster per-categoria in nation detail con spiderfy custom (hub + fan emoji).
 *
 * Runtime sempre via ``window.L``. Read/unread: fingerprint geometria + sync DOM
 * (no ``clearLayers`` su solo ``is_read``).
 *
 * @see SoT: AGENTS.md §5; frontend.md §7/§10; docs/03.
 */
@Component({
  selector: 'app-radar-map',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './radar-map.component.html',
  styleUrl: './radar-map.component.scss',
})
export class RadarMapComponent implements AfterViewInit {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);

  articles = input.required<Article[]>();
  countries = input.required<CountrySummary[]>();
  /** Aggregati day-view: un pin nazione (anello conic categorie), non pallini per-categoria. */
  mapSummary = input<MapSummaryRow[]>([]);
  mapRelations = input<MapRelationRow[]>([]);
  focusCountryCode = input<string | null>(null);

  markerClicked = output<Article>();
  clusterClicked = output<Article[]>();
  /** Apertura nazione — category / preserveZoom opzionali (pallini summary). */
  countryClicked = output<CountryOpenRequest>();

  currentZoomLevel = signal<number>(3);
  /** True se zoom &lt; 5 (macro: hatching, pin summary nascosti). */
  isZoomedOut = computed(() => this.currentZoomLevel() < 5);
  isParsingGeoJson = signal<boolean>(true);
  mapUnavailable = signal<boolean>(false);

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

  /** Box pixel pin day-view (punta in basso). Hub nazione usa disco compatto separato. */
  private readonly COUNTRY_PIN_SIZE = { w: 64, h: 76 } as const;

  private map: Leaflet.Map | null = null;
  private L: LeafletGlobal | null = null;
  private categoryClusterGroups = new Map<string, MarkerClusterGroupLike>();
  /** Day-view: un pin per paese (non pallini cluster per-categoria). */
  private summaryMarkerGroup: Leaflet.LayerGroup | null = null;
  private relationsLayerGroup: Leaflet.LayerGroup | null = null;
  private countryCentroids = new Map<string, Leaflet.LatLng>();
  /** Nation open: hub singolo mentre lo spiderfy è chiuso. */
  private detailHubGroup: Leaflet.LayerGroup | null = null;
  /**
   * Se false, ``unspiderfied`` non ripristina l'hub (cambio categoria: evita che
   * l'unspiderfy async del fan precedente cancelli il nuovo root).
   */
  private restoreDetailHubOnUnspiderfy = true;
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
  /** Ultimo spiderfy riuscito — riapri dopo zoom (MC auto-unspiderfy disabilitato). */
  private lastSpiderfyCountry: string | null = null;
  private lastSpiderfyCategory: string | null = null;
  /** Se true, il prossimo focusCountryCode salta fitBounds (path pallino summary). */
  private skipNextCountryFit = false;
  /**
   * Input geometria cambiati durante flyTo/fitBounds (`isNavigating`).
   * Senza flush, MarkerCluster può tenere layer in memoria ma zero icone nel pane.
   */
  private pendingGeometryRefresh = false;

  constructor() {
    // Day/nation geometry: rebuild solo se fingerprint cambia; altrimenti sync is_read.
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
    this.initMap();
    if (!this.mapUnavailable()) {
      this.loadGeoJson();
    }
  }

  /** Arma una volta: il prossimo focus paese tiene la camera (dopo click pin summary). */
  public armSkipCountryFit(): void {
    this.skipNextCountryFit = true;
  }

  /** Forza fitBounds anche se ``focusCountryCode`` è invariato (ri-selezione stessa nazione). */
  public refocusCountry(code: string): void {
    this.skipNextCountryFit = false;
    this.focusOnCountry(code);
  }

  /**
   * Dopo open/close sidebar o resize (layout overlay full-bleed).
   * ``pan: false``; ``setView`` solo se la camera è driftata (setView mid-spiderfy
   * svuota il pane MarkerCluster).
   */
  public invalidateSize(): void {
    if (!this.map) return;
    // Conserva camera senza setView incondizionato — setView a metà spiderfy
    // svuota le icone MarkerCluster (layer restano nel group, pane DOM vuoto).
    const center = this.map.getCenter();
    const zoom = this.map.getZoom();
    this.map.invalidateSize({ animate: false, pan: false });
    const after = this.map.getCenter();
    const afterZoom = this.map.getZoom();
    if (
      afterZoom !== zoom ||
      Math.abs(after.lat - center.lat) > 1e-9 ||
      Math.abs(after.lng - center.lng) > 1e-9
    ) {
      this.map.setView(center, zoom, { animate: false });
    }
  }

  /** Timeout tracciato e cancellabile in teardown (no leak post-destroy). */
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

  /**
   * Fingerprint geometria (id/cat/paese/coord o summary) — **senza** ``is_read``.
   * Stesso fingerprint → solo sync DOM read; diverso → rebuild layer.
   * Include la firma delle relazioni (source|target|cat|vol) come richiesto da spec.
   */
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

  /**
   * Applica input geometria: se fingerprint uguale, ``syncMarkerReadState`` (no clearLayers).
   * @see SoT: frontend.md §7 read/unread; AGENTS Phase 4 fingerprint.
   */
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

  /** Fine lock flyTo/fitBounds e applica geometria deferita durante la navigazione. */
  private finishNavigating(): void {
    this.isNavigating = false;
    if (!this.pendingGeometryRefresh || this.destroyed || !this.map || this.isParsingGeoJson()) {
      return;
    }
    this.pendingGeometryRefresh = false;
    this.applyGeometryInputs(this.articles(), this.countries(), this.mapSummary(), this.mapRelations());
  }

  /** MarkerCluster può tenere layer ma non disegnare dopo race clearLayers/setView. */
  private refreshClusterVisibility(): void {
    this.categoryClusterGroups.forEach((cg) => {
      if (typeof cg.refreshClusters === 'function') {
        cg.refreshClusters();
      }
    });
  }

  private markerWeight(marker: ArticleMarker): number {
    if (marker.isDummy) return 0;
    if (marker.isSummary) return marker.summaryCount ?? 1;
    return 1;
  }

  /** Icona emoji articolo (classe ``marker-read`` se già letto). */
  private createSafeMarkerIcon(L: LeafletGlobal, article: Article, sizePx = 28): Leaflet.DivIcon {
    const box = Math.max(16, Math.round(sizePx));
    const fontPx = Math.max(12, Math.round(box * 0.55));
    const emoji = this.CATEGORY_ICONS[article.primary_category] ?? '📍';
    const el = document.createElement('div');
    el.className = 'marker-icon';
    el.style.width = `${box}px`;
    el.style.height = `${box}px`;
    el.style.fontSize = `${fontPx}px`;
    el.style.lineHeight = `${box}px`;
    el.style.textAlign = 'center';
    el.title = article.title;
    el.textContent = emoji;
    if (article.is_read) {
      el.classList.add('marker-read');
    }

    return L.divIcon({
      html: el,
      className: `marker-${article.primary_category.toLowerCase()}`,
      iconSize: [box, box],
      // No CSS offset — spiderfy places icons geographically.
      iconAnchor: [Math.round(box / 2), Math.round(box / 2)],
    });
  }

  /**
   * Aggiorna classe ``.marker-read`` sul DOM senza ``clearLayers`` / rebuild cluster.
   * Toggle duale: wrapper Leaflet + ``.marker-icon`` interno (stili SCSS).
   */
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

  /**
   * Inizializza mappa, tile, 10 cluster (raggio 40, no auto-spiderfy), zoomend hatching.
   * Se ``window.L`` assente → ``mapUnavailable``.
   */
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
      attributionControl: true,
    });

    this.geoJsonLayerGroup = L.layerGroup();
    this.summaryMarkerGroup = L.layerGroup();
    this.relationsLayerGroup = L.layerGroup();
    this.detailHubGroup = L.layerGroup().addTo(this.map);

    this.map.on('click', (e: Leaflet.LeafletMouseEvent) => {
      const original = e.originalEvent as (Event & { _radarHandled?: boolean }) | undefined;
      if (original?._radarHandled) return;
      // Nation detail open: keep spiderfy as-is (no collapse-to-hub on hinterland clicks).
      if (this.focusCountryCode() && this.articles().length > 0) return;
      this.collapseAllGraphs(true);
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap contributors © CARTO',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(this.map);

    const labelsPane = this.map.createPane('labelsPane');
    labelsPane.style.zIndex = '650';
    labelsPane.style.pointerEvents = 'none';

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', {
      pane: 'labelsPane',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(this.map);

    const categories = Object.keys(this.CATEGORY_CSS_VARS);
    for (const cat of categories) {
      const cg = L.markerClusterGroup({
        // SoT: raggio 40, spiderfyOnMaxZoom false — non riallineare a legacy 200/true.
        maxClusterRadius: 40,
        showCoverageOnHover: false,
        spiderfyOnMaxZoom: false,
        zoomToBoundsOnClick: false,
        // Baseline; overridden per open via spiderfyDistanceForCount().
        spiderfyDistanceMultiplier: 3.0,
        iconCreateFunction: (_cluster: MarkerClusterLike) => {
          // Nessun pallino categoria — day = pin summary; detail = hub + emoji spiderfy.
          return L.divIcon({ className: 'hidden', iconSize: [0, 0] });
        },
      });

      cg.on('unspiderfied', () => {
        // Unspiderfy async (cambio categoria) non deve cancellare il nuovo root.
        // Con restoreDetailHubOnUnspiderfy=false, spiderfyAndCreateRoot possiede il root.
        if (!this.restoreDetailHubOnUnspiderfy) {
          return;
        }
        this.clearRootMarkers();
        if (this.L && this.articles().length > 0) {
          this.upsertDetailHubPin(this.L, this.articles());
        } else {
          this.clearDetailHubPin();
        }
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

        if (isAlreadyOpen) {
          this.collapseAllGraphs(true, true);
          return;
        }

        this.collapseAllGraphs(false, false);

        const articleMarkers = childMarkers.filter(
          (m) => !m.isDummy && !m.isSummary && m.articleData,
        );
        const arts = articleMarkers
          .map((m) => m.articleData)
          .filter((a): a is Article => !!a && a.primary_category === cat);

        // Path legacy: cluster senza articoli reali (oggi i pin day stanno in summaryMarkerGroup).
        // Se mai riattivato con isSummary nei cluster, apre nazione preserveZoom.
        if (arts.length === 0) {
          const country = this.dominantSummaryCountry(childMarkers);
          if (country) {
            this.countryClicked.emit({
              countryCode: country,
              category: cat as PrimaryCategory,
              preserveZoom: true,
            });
          } else {
            this.restoreNationHubPin();
          }
          return;
        }

        if (arts.length > 0) this.clusterClicked.emit(arts);

        const currentZoom = this.map.getZoom();
        // Nota: qui soglia in-place = 6; focusAndSpiderfyCategory usa ≥5 (drift interno).
        const targetZoom = 6;
        const gen = ++this.spiderfyGeneration;

        if (currentZoom >= targetZoom) {
          if (!this.spiderfyAndCreateRoot(cg, childMarkers, gen)) {
            this.restoreNationHubPin();
          }
          return;
        }

        this.isNavigating = true;
        this.navigatingTargetZoom = targetZoom;
        this.map.flyTo(cluster.getLatLng(), targetZoom, { animate: true, duration: 0.6 });

        const onZoomEnd = () => {
          this.scheduleTimeout(() => {
            if (this.destroyed || gen !== this.spiderfyGeneration) {
              this.finishNavigating();
              return;
            }
            if (!this.spiderfyAndCreateRoot(cg, childMarkers, gen)) {
              this.restoreNationHubPin();
            }
            this.finishNavigating();
            this.map?.off('zoomend', onZoomEnd);
          }, 250);
        };
        this.map.once('zoomend', onZoomEnd);
        this.scheduleTimeout(onZoomEnd, 1200);
      });

      this.categoryClusterGroups.set(cat, cg);
      this.map.addLayer(cg as unknown as Leaflet.Layer);
      // MC binda map click → unspiderfy in _spiderfierOnAdd; chiuderebbe il fan
      // su click hinterland. Lo disabilitiamo — unspiderfy esplicito altrove.
      this.disableMarkerClusterMapClickUnspiderfy(cg);
    }
    this.geoJsonLayerGroup.addTo(this.map);

    this.map.on('zoomend', () => {
      if (this.destroyed || !this.map) return;
      const zoom = this.map.getZoom();
      this.currentZoomLevel.set(zoom);
      this.refreshHatchingStyles();
      this.syncSummaryMarkerVisibility();
      this.syncRelationsVisibility();

      // Nation open: tieni spider fino a hatching (zoom < 5); sotto chiudi anche sidebar.
      // MC zoom-unspiderfy disabilitato; ri-spiderfy dopo zoom per riposizionare le gambe.
      const nationOpen = this.articles().length > 0 || !!this.focusCountryCode();
      // Serve lastSpiderfy: evita che fitBounds(maxZoom:4) chiuda la sidebar in race.
      if (!this.isNavigating && nationOpen && zoom < 5 && !!this.lastSpiderfyCategory) {
        this.collapseAllGraphs(true);
      } else if (
        !this.isNavigating &&
        nationOpen &&
        zoom >= 5 &&
        this.lastSpiderfyCountry &&
        this.lastSpiderfyCategory
      ) {
        const country = this.lastSpiderfyCountry;
        const category = this.lastSpiderfyCategory;
        // Defer: lascia finire il bookkeeping zoom di MarkerCluster.
        this.scheduleTimeout(() => {
          if (this.destroyed || !this.map) return;
          if (this.map.getZoom() < 5) return;
          this.focusAndSpiderfyCategory(country, category);
        }, 50);
      } else if (zoom < 5 && !this.isNavigating && !nationOpen) {
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

  /** Distanza spiderfy: pochi icone → più spazio; molti → più stretti. */
  private spiderfyDistanceForCount(n: number): number {
    if (n <= 4) return 3.8;
    if (n <= 8) return 3.2;
    if (n <= 14) return 2.7;
    if (n <= 20) return 2.3;
    if (n <= 32) return 1.9;
    if (n <= 48) return 1.6;
    return 1.4;
  }

  /** Box pixel emoji spiderfy — si riduce al crescere del fan. */
  private spiderfyIconSizeForCount(n: number): number {
    if (n <= 4) return 36;
    if (n <= 8) return 30;
    if (n <= 14) return 26;
    if (n <= 20) return 22;
    if (n <= 32) return 18;
    if (n <= 48) return 16;
    return 14;
  }

  /** Ripristina hub nazione dopo spiderfy fallito (mai mappa vuota). */
  private restoreNationHubPin(): void {
    this.restoreDetailHubOnUnspiderfy = true;
    this.clearRootMarkers();
    if (this.L && this.articles().length > 0) {
      this.upsertDetailHubPin(this.L, this.articles());
    }
  }

  /**
   * Espande i marker articolo reali del gruppo via MarkerCluster.spiderfy.
   * False se non parte — il caller deve ripristinare l'hub.
   */
  private spiderfyAndCreateRoot(
    cg: MarkerClusterGroupLike,
    childMarkers: ArticleMarker[],
    generation: number,
  ): boolean {
    if (this.destroyed || !this.map || !this.L) return false;
    if (generation !== this.spiderfyGeneration) return false;
    if (!childMarkers || childMarkers.length === 0) return false;

    const realMarkers = childMarkers.filter((m) => !m.isDummy && !m.isSummary && !!m.articleData);
    if (realMarkers.length === 0) return false;

    // Preferisci marker ancora con parent cluster (il primo può essere orfano dopo race).
    let newParent: (Leaflet.Marker & { spiderfy?: () => void }) | null | undefined;
    for (const m of realMarkers) {
      const parent = cg.getVisibleParent(m) as
        | (Leaflet.Marker & { spiderfy?: () => void })
        | null
        | undefined;
      if (parent && typeof parent.spiderfy === 'function') {
        newParent = parent;
        break;
      }
    }
    if (!newParent || typeof newParent.spiderfy !== 'function') {
      if (typeof cg.refreshClusters === 'function') {
        cg.refreshClusters();
      }
      for (const m of realMarkers) {
        const parent = cg.getVisibleParent(m) as
          | (Leaflet.Marker & { spiderfy?: () => void })
          | null
          | undefined;
        if (parent && typeof parent.spiderfy === 'function') {
          newParent = parent;
          break;
        }
      }
    }
    if (!newParent || typeof newParent.spiderfy !== 'function') return false;

    const n = realMarkers.length;
    if (cg.options) {
      cg.options.spiderfyDistanceMultiplier = this.spiderfyDistanceForCount(n);
    }

    const iconPx = this.spiderfyIconSizeForCount(n);
    for (const m of realMarkers) {
      if (m.articleData && typeof m.setIcon === 'function') {
        m.setIcon(this.createSafeMarkerIcon(this.L, m.articleData, iconPx));
      }
    }

    // Pulisci hub solo a spiderfy confermato — evita mappa bianca sul fallimento.
    this.clearRootMarkers();
    this.clearDetailHubPin();
    this.restoreDetailHubOnUnspiderfy = false;

    const categoryArts = realMarkers.map((m) => m.articleData).filter((a): a is Article => !!a);
    // Disco compatto (non pin alto) così le gambe nord restano visibili.
    const rootIcon = this.createSpiderfyRootIcon(this.L, categoryArts);

    const rootMarker = this.L.marker(newParent.getLatLng(), {
      icon: rootIcon,
      interactive: true,
      zIndexOffset: 1600,
    }).addTo(this.map);

    rootMarker.on('click', (e: Leaflet.LeafletMouseEvent) => {
      if (e.originalEvent) {
        (e.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
      }
      this.L!.DomEvent.stopPropagation(e);
      this.collapseAllGraphs(true, true);
    });

    this.activeRootMarkers.push(rootMarker);
    newParent.spiderfy();
    // spiderfy può ri-bindare unspiderfy su click mappa; tienilo spento.
    this.disableMarkerClusterMapClickUnspiderfy(cg);

    const firstArt = categoryArts[0];
    if (firstArt?.country_code && firstArt.primary_category) {
      this.lastSpiderfyCountry = firstArt.country_code;
      this.lastSpiderfyCategory = firstArt.primary_category;
    }

    for (const m of realMarkers) {
      if (typeof m.setZIndexOffset === 'function') {
        m.setZIndexOffset(1400);
      }
    }
    return true;
  }

  /**
   * MarkerCluster registra map click → unspiderfy e zoom* → auto-unspiderfy.
   * Li rimuoviamo: unspiderfy esplicito via collapseAllGraphs / hub / zoom&lt;5.
   */
  private disableMarkerClusterMapClickUnspiderfy(cg: MarkerClusterGroupLike): void {
    if (!this.map) return;
    const group = cg as MarkerClusterGroupLike & {
      _unspiderfyWrapper?: (e?: Leaflet.LeafletMouseEvent) => void;
      _unspiderfyZoomStart?: () => void;
      _unspiderfyZoomAnim?: (e?: Leaflet.LeafletEvent) => void;
      _noanimationUnspiderfy?: () => void;
    };
    if (typeof group._unspiderfyWrapper === 'function') {
      this.map.off('click', group._unspiderfyWrapper, group);
    }
    if (typeof group._unspiderfyZoomStart === 'function') {
      this.map.off('zoomstart', group._unspiderfyZoomStart, group);
    }
    if (typeof group._unspiderfyZoomAnim === 'function') {
      this.map.off('zoomanim', group._unspiderfyZoomAnim, group);
    }
    if (typeof group._noanimationUnspiderfy === 'function') {
      this.map.off('zoomend', group._noanimationUnspiderfy, group);
    }
  }

  /** Carica GeoJSON paesi (chunked via rAF) — ISO_A2 / FR+NO override ``-99``. */
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
        },
      });
  }

  /**
   * Parse incrementale (batch 15/frame) per non bloccare UI.
   * NaturalEarth ``-99`` su France/Norway → FR/NO per allineare hatching e click.
   */
  private parseGeoJsonIncremental(geoData: GeoJSON.FeatureCollection): void {
    const L = this.L;
    if (!L || !this.geoJsonLayerGroup || this.destroyed) {
      this.isParsingGeoJson.set(false);
      return;
    }

    const features = geoData.features;
    let index = 0;
    const batchSize = 15;
    const stroke =
      getComputedStyle(document.documentElement).getPropertyValue('--color-map-stroke').trim() ||
      'rgba(0, 212, 255, 0.15)';

    const processBatch = () => {
      this.geoJsonRafId = null;
      if (this.destroyed || !this.L || !this.geoJsonLayerGroup) {
        this.isParsingGeoJson.set(false);
        return;
      }

      const end = Math.min(index + batchSize, features.length);
      for (let i = index; i < end; i++) {
        const feature = features[i];
        let code =
          feature.properties?.['ISO3166-1-Alpha-2'] ?? feature.properties?.['ISO_A2'] ?? 'XX';
        // NaturalEarth: France/Norway spesso ``-99`` — remap esplicito.
        if (code === '-99' || !code || code === 'XX') {
          const name = feature.properties?.['name'];
          if (name === 'France') code = 'FR';
          else if (name === 'Norway') code = 'NO';
        }

        const layer = L.geoJSON(feature, {
          style: () => ({
            color: stroke,
            weight: 0.5,
            fillOpacity: 0,
            fillColor: 'transparent',
            className: 'country-fill',
          }),
        });

        layer.on('click', (e: Leaflet.LeafletMouseEvent) => {
          if (e.originalEvent) {
            L.DomEvent.stopPropagation(e.originalEvent);
            (e.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
          }
          // Nazione già aperta su questo poligono: no re-emit (evita fitBounds + re-spiderfy).
          if (this.focusCountryCode() === code && this.articles().length > 0) {
            return;
          }
          // Solo code — Article[] nazione arrivano da App/StateService (Phase 5).
          this.countryClicked.emit({ countryCode: code });
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

  /**
   * Hatching SVG solo con zoom &lt; 5 e countries() con categorie;
   * altrimenti fill trasparente. Classe ``zoom-out-mode`` sul container.
   */
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
    const stroke =
      getComputedStyle(document.documentElement).getPropertyValue('--color-map-stroke').trim() ||
      'rgba(0, 212, 255, 0.15)';
    const strokeActive =
      getComputedStyle(document.documentElement)
        .getPropertyValue('--color-map-stroke-active')
        .trim() || 'rgba(0, 212, 255, 0.25)';

    this.countryLayersMap.forEach((layers, code) => {
      const summary = ctrs.find((c) => c.country_code === code);

      layers.forEach((layer) => {
        if (zoomedOut && summary?.categories?.length && defs) {
          const patternId = this.getOrCreateComboPattern(summary.categories, defs);
          layer.setStyle({
            fillColor: `url(${baseUrl}#${patternId})`,
            fillOpacity: 0.35,
            color: strokeActive,
          });
        } else {
          layer.setStyle({
            fillOpacity: 0,
            color: stroke,
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

  /** Un pattern SVG per combo categorie (1–10) — hatching zoom-out. */
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
      x1: string,
      y1: string,
      x2: string,
      y2: string,
      strokeColor: string,
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

  /**
   * FitBounds su nazione (US/RU bounds hard-coded; altri da GeoJSON).
   * Con ``skipNextCountryFit`` (path pin summary) non muove la camera.
   */
  private focusOnCountry(code: string): void {
    const L = this.L;
    if (!this.map || !L || this.isNavigating || this.destroyed) return;

    // Path pin summary: tieni zoom/centro (no fitBounds/dezoom).
    if (this.skipNextCountryFit) {
      this.skipNextCountryFit = false;
      return;
    }

    let bounds: Leaflet.LatLngBounds | null = null;

    // US/RU: bounds continenti ridotti (Alaska/isole/Kamchatka fuori frame).
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
        duration: 1.0,
      });

      let cleaned = false;
      const cleanup = () => {
        if (cleaned || this.destroyed) return;
        cleaned = true;
        this.finishNavigating();
        this.map?.off('zoomend', cleanup);
        this.map?.off('moveend', cleanup);
      };

      this.map.once('zoomend', cleanup);
      this.map.once('moveend', cleanup);
      this.scheduleTimeout(cleanup, 1500);
    }
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

  private dominantSummaryCountry(markers: ArticleMarker[]): string | null {
    const totals = new Map<string, number>();
    for (const m of markers) {
      if (!m.isSummary || !m.summaryCountry) continue;
      totals.set(m.summaryCountry, (totals.get(m.summaryCountry) ?? 0) + (m.summaryCount ?? 1));
    }
    let best: string | null = null;
    let bestCount = 0;
    totals.forEach((count, code) => {
      if (count > bestCount) {
        best = code;
        bestCount = count;
      }
    });
    return best;
  }

  /** Pin day-view: anello conic categorie + totale; punta sul centroide. */
  private createCountrySummaryPinIcon(
    L: LeafletGlobal,
    total: number,
    categoryCounts: { category: string; count: number }[],
  ): Leaflet.DivIcon {
    const { w, h } = this.COUNTRY_PIN_SIZE;
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

    return L.divIcon({
      html: root,
      className: 'radar-country-pin-wrap',
      iconSize: [w, h],
      // Punta sul centroide — nessun offset laterale CSS.
      iconAnchor: [Math.round(w / 2), h],
    });
  }

  /**
   * Disco centrato come root spiderfy — pin alto coprirebbe le gambe nord.
   */
  private createSpiderfyRootIcon(L: LeafletGlobal, articles: Article[]): Leaflet.DivIcon {
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

    return L.divIcon({
      html: root,
      className: 'radar-spider-root-wrap',
      iconSize: [42, 42],
      iconAnchor: [21, 21],
    });
  }

  private clearDetailHubPin(): void {
    this.detailHubGroup?.clearLayers();
  }

  /**
   * Hub nazione (day→detail chiuso): disco compatto al centroide articoli.
   * Visibile solo se non c'è spiderfy attivo.
   */
  private upsertDetailHubPin(L: LeafletGlobal, articles: Article[]): void {
    if (!this.detailHubGroup || !this.map) return;
    this.detailHubGroup.clearLayers();
    if (articles.length === 0) return;

    let latSum = 0;
    let lngSum = 0;
    let n = 0;
    for (const a of articles) {
      if (!this.hasFiniteCoordinates(a.latitude, a.longitude)) continue;
      if ((a.country_code || 'XX') === 'XX') continue;
      latSum += a.latitude;
      lngSum += a.longitude;
      n++;
    }
    if (n === 0) return;

    // Stesso disco compatto del root spiderfy — evita flash pin alto → disco piccolo.
    const icon = this.createSpiderfyRootIcon(L, articles);
    const marker = L.marker([latSum / n, lngSum / n], {
      icon,
      zIndexOffset: 500,
    }) as ArticleMarker;
    marker.isDummy = false;

    marker.on('click', (e: Leaflet.LeafletMouseEvent) => {
      if (e.originalEvent) {
        L.DomEvent.stopPropagation(e.originalEvent);
        (e.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
      }
      const code = articles[0]?.country_code;
      const cat = articles[0]?.primary_category;
      if (code && cat) {
        this.focusAndSpiderfyCategory(code, cat);
      }
    });

    this.detailHubGroup.addLayer(marker);
  }

  /** Pin day-view solo a zoom ≥ 5 e senza nazione aperta. */
  private syncSummaryMarkerVisibility(): void {
    if (!this.map || !this.summaryMarkerGroup) return;
    const show = this.map.getZoom() >= 5 && this.articles().length === 0;
    const onMap = this.map.hasLayer(this.summaryMarkerGroup);
    if (show && !onMap) {
      this.map.addLayer(this.summaryMarkerGroup);
    } else if (!show && onMap) {
      this.map.removeLayer(this.summaryMarkerGroup);
    }
  }

  /** Relational arcs solo a zoom ≥ 5 e senza nazione aperta. */
  private syncRelationsVisibility(): void {
    if (!this.map || !this.relationsLayerGroup) return;
    const show = this.map.getZoom() >= 5 && this.articles().length === 0;
    const onMap = this.map.hasLayer(this.relationsLayerGroup);
    if (show && !onMap) {
      this.map.addLayer(this.relationsLayerGroup);
    } else if (!show && onMap) {
      this.map.removeLayer(this.relationsLayerGroup);
    }
  }

  /**
   * Disegna gli archi curvi di relazione geopolitica bilaterale.
   */
  private drawGeospatialRelations(relations: MapRelationRow[]): void {
    if (!this.relationsLayerGroup || !this.L) return;
    this.relationsLayerGroup.clearLayers();

    for (const r of relations) {
      const p0 = this.getCountryCentroid(r.source_country);
      const p2 = this.getCountryCentroid(r.target_country);
      if (!p0 || !p2) continue;

      // Generazione punti curva Bezier quadratica
      const points: Leaflet.LatLng[] = [];
      const steps = 30;
      const lat0 = p0.lat;
      const lng0 = p0.lng;
      const lat2 = p2.lat;
      const lng2 = p2.lng;

      const midLat = (lat0 + lat2) / 2;
      const midLng = (lng0 + lng2) / 2;

      const dLat = lat2 - lat0;
      const dLng = lng2 - lng0;

      // Deviazione perpendicolare proporzionale alla distanza
      const curvature = 0.2;
      const p1Lat = midLat - dLng * curvature;
      const p1Lng = midLng + dLat * curvature;

      for (let i = 0; i <= steps; i++) {
        const t = i / steps;
        const lat = (1 - t) * (1 - t) * lat0 + 2 * (1 - t) * t * p1Lat + t * t * lat2;
        const lng = (1 - t) * (1 - t) * lng0 + 2 * (1 - t) * t * p1Lng + t * t * lng2;
        points.push(this.L.latLng(lat, lng));
      }

      const colorVar = this.CATEGORY_CSS_VARS[r.primary_category] || '--color-text-accent';
      const docStyle = getComputedStyle(document.documentElement);
      const color = docStyle.getPropertyValue(colorVar).trim() || '#58a6ff';
      const weight = Math.min(6, 1 + r.volume * 0.5);

      const polyline = this.L.polyline(points, {
        color,
        weight,
        opacity: 0.8,
        className: 'relational-arc-flow',
        interactive: true,
      });

      // Tooltip informativo opzionale (sticky)
      const tooltipText = `${r.source_country} ↔ ${r.target_country} · ${r.primary_category} · n=${r.volume}`;
      polyline.bindTooltip(tooltipText, { sticky: true });

      this.relationsLayerGroup.addLayer(polyline);
    }
  }

  /**
   * Restituisce il centroide di una nazione con caching,
   * override manuali per US/RU e fallback summary.
   */
  private getCountryCentroid(code: string): Leaflet.LatLng | null {
    if (!this.L) return null;
    if (code === 'US') {
      return this.L.latLng(37.0902, -95.7129);
    }
    if (code === 'RU') {
      return this.L.latLng(61.524, 105.3187);
    }
    if (this.countryCentroids.has(code)) {
      return this.countryCentroids.get(code)!;
    }
    const layers = this.countryLayersMap.get(code);
    if (layers && layers.length > 0) {
      const b = this.L.latLngBounds([]);
      layers.forEach((layer) => {
        const withBounds = layer as Leaflet.Path & { getBounds?: () => Leaflet.LatLngBounds };
        if (typeof withBounds.getBounds === 'function') {
          b.extend(withBounds.getBounds());
        }
      });
      if (b.isValid()) {
        const center =
          typeof b.getCenter === 'function'
            ? b.getCenter()
            : this.L.latLng(
                (b.getSouthWest().lat + b.getNorthEast().lat) / 2,
                (b.getSouthWest().lng + b.getNorthEast().lng) / 2,
              );
        this.countryCentroids.set(code, center);
        return center;
      }
    }

    // Fallback coordinate medie dal mapSummary
    const rows = this.mapSummary().filter((r) => r.country_code === code);
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
        const fallbackLatLng = this.L.latLng(latSum / countSum, lngSum / countSum);
        // non salviamo in cache centroids da fallback summary temporanei
        return fallbackLatLng;
      }
    }
    return null;
  }

  /**
   * Rebuild layer: unspiderfy → clear → day (summary) o detail (cluster + hub).
   * Chiama sempre prima di clearLayers per evitare icone fantasma MarkerCluster.
   */
  private updateMapData(
    articles: Article[],
    countries: CountrySummary[],
    summary: MapSummaryRow[],
    relations: MapRelationRow[] = [],
  ): void {
    const L = this.L;
    if (!L || !this.map) return;

    // Unspiderfy prima di clearLayers — altrimenti MC lascia layer senza icone nel pane.
    this.spiderfyGeneration++;
    this.clearRootMarkers();
    this.categoryClusterGroups.forEach((cg) => {
      const spiderfiedCluster = cg._spiderfied;
      if (spiderfiedCluster && typeof spiderfiedCluster.unspiderfy === 'function') {
        spiderfiedCluster.unspiderfy();
      }
    });

    this.categoryClusterGroups.forEach((group) => group.clearLayers());
    this.summaryMarkerGroup?.clearLayers();
    this.relationsLayerGroup?.clearLayers();
    this.clearDetailHubPin();

    if (articles.length === 0) {
      this.renderSummaryMarkers(L, summary);
      this.drawGeospatialRelations(relations);
      this.lastGeometryFingerprint = this.geometryFingerprint(articles, summary, relations);
      this.refreshClusterVisibility();
      this.syncSummaryMarkerVisibility();
      this.syncRelationsVisibility();
      this.refreshHatchingStyles();
      void countries;
      return;
    }

    this.renderDetailMarkers(L, articles);
    this.upsertDetailHubPin(L, articles);
    this.lastGeometryFingerprint = this.geometryFingerprint(articles, summary, relations);
    this.refreshClusterVisibility();
    this.syncSummaryMarkerVisibility();
    this.syncRelationsVisibility();
    this.refreshHatchingStyles();
    void countries;
  }

  /**
   * Day view: un pin per paese al centroide pesato.
   * Mix categorie = anello conic — evita pallini per-categoria che driftano via iconAnchor.
   */
  private renderSummaryMarkers(L: LeafletGlobal, summary: MapSummaryRow[]): void {
    if (!this.summaryMarkerGroup) return;

    type Agg = {
      latSum: number;
      lngSum: number;
      weight: number;
      total: number;
      categories: Map<string, number>;
    };
    const byCountry = new Map<string, Agg>();

    for (const row of summary) {
      const code = row.country_code || 'XX';
      if (code === 'XX') continue;
      if (row.article_count <= 0) continue;
      if (!this.hasFiniteCoordinates(row.latitude, row.longitude)) continue;

      const w = Math.max(1, row.article_count);
      const cur = byCountry.get(code) ?? {
        latSum: 0,
        lngSum: 0,
        weight: 0,
        total: 0,
        categories: new Map<string, number>(),
      };
      cur.latSum += row.latitude * w;
      cur.lngSum += row.longitude * w;
      cur.weight += w;
      cur.total += row.article_count;
      cur.categories.set(
        row.primary_category,
        (cur.categories.get(row.primary_category) ?? 0) + row.article_count,
      );
      byCountry.set(code, cur);
    }

    byCountry.forEach((agg, code) => {
      if (agg.weight === 0 || agg.total <= 0) return;
      const baseLat = agg.latSum / agg.weight;
      const baseLng = agg.lngSum / agg.weight;
      const categoryCounts = Array.from(agg.categories.entries()).map(([category, count]) => ({
        category,
        count,
      }));
      const icon = this.createCountrySummaryPinIcon(L, agg.total, categoryCounts);
      const marker = L.marker([baseLat, baseLng], { icon }) as ArticleMarker;
      marker.isSummary = true;
      marker.isDummy = false;
      marker.summaryCount = agg.total;
      marker.summaryCountry = code;

      marker.on('click', (e: Leaflet.LeafletMouseEvent) => {
        if (e.originalEvent) {
          L.DomEvent.stopPropagation(e.originalEvent);
          (e.originalEvent as Event & { _radarHandled?: boolean })._radarHandled = true;
        }
        this.countryClicked.emit({
          countryCode: code,
          preserveZoom: true,
        });
      });

      this.summaryMarkerGroup!.addLayer(marker);
    });
  }

  /**
   * Nation detail: marker reali per categoria + dummy invisibile per forzare
   * un parent cluster anche con un solo articolo (MC richiede ≥2 child).
   */
  private renderDetailMarkers(L: LeafletGlobal, articles: Article[]): void {
    const countryCenters = new Map<string, { latSum: number; lngSum: number; count: number }>();

    for (const article of articles) {
      if (this.hasFiniteCoordinates(article.latitude, article.longitude)) {
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
      populatedSpots.add(`${code}_${cat}`);

      const icon = this.createSafeMarkerIcon(L, article);
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
        iconAnchor: [0, 0],
      });

      const dummyMarker = L.marker([baseLat, baseLng], {
        icon: invisibleIcon,
        interactive: false,
      }) as ArticleMarker;
      dummyMarker.isDummy = true;

      const targetGroup = this.categoryClusterGroups.get(cat);
      if (targetGroup) targetGroup.addLayer(dummyMarker);
    });
  }

  /**
   * Chiude tutti gli spiderfy. ``emitClose`` → sidebar (clusterClicked []);
   * ``restoreHub`` → ripristina hub nazione (false durante switch categoria).
   */
  collapseAllGraphs(emitClose: boolean = false, restoreHub: boolean = true): void {
    if (!this.map) return;

    this.spiderfyGeneration++;
    this.clearRootMarkers();
    this.restoreDetailHubOnUnspiderfy = restoreHub;
    if (emitClose) {
      this.lastSpiderfyCountry = null;
      this.lastSpiderfyCategory = null;
    }

    this.categoryClusterGroups.forEach((cg) => {
      const spiderfiedCluster = cg._spiderfied;
      if (spiderfiedCluster && typeof spiderfiedCluster.unspiderfy === 'function') {
        spiderfiedCluster.unspiderfy();
      }
    });

    if (restoreHub && this.L && this.articles().length > 0) {
      this.upsertDetailHubPin(this.L, this.articles());
    } else if (!restoreHub) {
      this.clearDetailHubPin();
    }

    if (emitClose) {
      this.clusterClicked.emit([]);
    }
  }

  /**
   * Apre spiderfy per una categoria nella nazione (carousel / hub click).
   * In-place se zoom ≥ 5; altrimenti flyTo 6. Nota: clusterclick usa soglia 6.
   */
  public focusAndSpiderfyCategory(countryCode: string, category: string, attempt = 0): void {
    if (!this.map || this.destroyed) return;
    const cg = this.categoryClusterGroups.get(category);
    if (!cg) return;

    const allMarkers = cg.getLayers() as ArticleMarker[];
    const countryMarkers = allMarkers.filter(
      (m) => m.articleData && m.articleData.country_code === countryCode,
    );

    if (countryMarkers.length === 0) {
      // Marker detail possono ancora arrivare dopo fetch nazione / invalidateSize.
      if (attempt < 10) {
        this.scheduleTimeout(
          () => this.focusAndSpiderfyCategory(countryCode, category, attempt + 1),
          50,
        );
      }
      return;
    }

    this.collapseAllGraphs(false, false);

    const firstMarker = countryMarkers[0];
    const parent = cg.getVisibleParent(firstMarker);
    if (!parent) {
      if (typeof cg.refreshClusters === 'function') {
        cg.refreshClusters();
      }
      const retryParent = cg.getVisibleParent(firstMarker);
      if (!retryParent) {
        this.restoreNationHubPin();
        return;
      }
    }

    const currentZoom = this.map.getZoom();
    const targetZoom = 6;
    const visibleParent = cg.getVisibleParent(firstMarker) ?? firstMarker;
    const latLng =
      typeof visibleParent.getLatLng === 'function'
        ? visibleParent.getLatLng()
        : firstMarker.getLatLng();
    const gen = ++this.spiderfyGeneration;

    // Zoom detail già ok: spiderfy in place — mai fitBounds/dezoom.
    if (currentZoom >= 5) {
      if (!this.spiderfyAndCreateRoot(cg, countryMarkers, gen)) {
        this.restoreNationHubPin();
      }
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
          this.finishNavigating();
          return;
        }
        if (!this.spiderfyAndCreateRoot(cg, countryMarkers, gen)) {
          this.restoreNationHubPin();
        }
        this.finishNavigating();
        this.map?.off('zoomend', cleanup);
        this.map?.off('moveend', cleanup);
      }, 250);
    };

    this.map.once('zoomend', cleanup);
    this.map.once('moveend', cleanup);
    this.scheduleTimeout(cleanup, 1200);
  }

  /**
   * Nation open legacy: prima categoria disponibile → focusAndSpiderfyCategory.
   * Preferisci sempre la variante per-categoria (articolo attivo carousel).
   */
  public focusAndSpiderfyCountry(countryCode: string, attempt = 0): void {
    if (!this.map || this.destroyed) return;

    // Resolve the first available category for this country and delegate.
    for (const [cat, cg] of this.categoryClusterGroups) {
      const markers = (cg.getLayers() as ArticleMarker[]).filter(
        (m) => m.articleData && m.articleData.country_code === countryCode,
      );
      if (markers.length > 0) {
        this.focusAndSpiderfyCategory(countryCode, cat, attempt);
        return;
      }
    }

    if (attempt < 10) {
      this.scheduleTimeout(() => this.focusAndSpiderfyCountry(countryCode, attempt + 1), 50);
    }
  }

  /** Evidenzia marker articolo attivo (carousel) con retry se icona non ancora nel DOM. */
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
          targetMarker.setZIndexOffset(1400);
        }
      } else if (retries > 0) {
        this.scheduleTimeout(() => this.applyHighlight(retries - 1), 150);
      }
      return;
    }

    if (retries > 0) {
      this.scheduleTimeout(() => this.applyHighlight(retries - 1), 150);
    }
  }

  /** DestroyRef: annulla timeout/rAF, unsubscribe GeoJSON, ``map.remove()``. */
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
    if (this.relationsLayerGroup && this.map?.hasLayer(this.relationsLayerGroup)) {
      this.map.removeLayer(this.relationsLayerGroup);
    }
    this.relationsLayerGroup = null;
    this.map?.remove();
    this.map = null;
  }
}
