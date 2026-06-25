import {
  Component, AfterViewInit, OnDestroy, input, output,
  signal, computed, effect, inject
} from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import type * as Leaflet from 'leaflet';
import type * as LMarkerCluster from 'leaflet.markercluster';

const L = (window as any).L;
import { Article, CountrySummary } from '../../models/article.model';
import { LeafletHatchDirective } from '../../shared/directives/leaflet-hatch.directive';

@Component({
  selector: 'app-radar-map',
  standalone: true,
  imports: [CommonModule, LeafletHatchDirective],
  templateUrl: './radar-map.component.html',
  styleUrl: './radar-map.component.scss'
})
export class RadarMapComponent implements AfterViewInit, OnDestroy {
  private readonly http = inject(HttpClient);

  // Input
  articles         = input.required<Article[]>();
  countries        = input.required<CountrySummary[]>();
  focusCountryCode = input<string | null>(null);

  // Output
  markerClicked  = output<Article>();
  clusterClicked = output<Article[]>();
  countryClicked = output<Article[]>();

  // Stato zoom e caricamento GeoJSON
  currentZoomLevel = signal<number>(3);
  isZoomedOut      = computed(() => this.currentZoomLevel() < 5);
  isParsingGeoJson = signal<boolean>(true); // Gestisce l'overlay grafico iniziale

  // Mappe categoria → icona emoji
  private readonly CATEGORY_ICONS: Record<string, string> = {
    'Nucleare':       '☢️',
    'Chip':           '💾',
    'Acqua':          '💧',
    'Energia':        '⚡',
    'Elettronica':    '📡',
    'Infrastrutture': '🏗️',
  };

  // Mappatura delle variabili CSS Custom Properties globali (Isolamento Radicale dei Colori - NO HEX in TS)
  private readonly CATEGORY_CSS_VARS: Record<string, string> = {
    'Nucleare':       '--color-nucleare',
    'Elettronica':    '--color-elettronica',
    'Chip':           '--color-chip',
    'Acqua':          '--color-acqua',
    'Energia':        '--color-energia',
    'Infrastrutture': '--color-infrastrutture',
  };

  // Legenda delle categorie geopolitiche
  readonly legendItems = [
    { label: 'Nucleare', icon: '☢️', cssVar: '--color-nucleare' },
    { label: 'Chip', icon: '💾', cssVar: '--color-chip' },
    { label: 'Elettronica', icon: '📡', cssVar: '--color-elettronica' },
    { label: 'Acqua', icon: '💧', cssVar: '--color-acqua' },
    { label: 'Energia', icon: '⚡', cssVar: '--color-energia' },
    { label: 'Infrastrutture', icon: '🏗️', cssVar: '--color-infrastrutture' }
  ];

  // Istanze Leaflet
  private map!: Leaflet.Map;
  private clusterGroup!: Leaflet.MarkerClusterGroup;
  private geoJsonLayerGroup = L.layerGroup();
  private countryLayersMap = new Map<string, Leaflet.Path[]>(); // Riferimento per il refresh rapido via .setStyle()

  constructor() {
    // Effect: aggiorna i dati visivi sulla mappa in base a filtri e date
    effect(() => {
      const arts = this.articles();
      const ctrs = this.countries();
      if (this.map && !this.isParsingGeoJson()) {
        this.updateMapData(arts, ctrs);
      }
    });

    // Effect: focus su nazione quando viene selezionata
    effect(() => {
      const code = this.focusCountryCode();
      if (code && this.map && !this.isParsingGeoJson()) {
        this.focusOnCountry(code);
      }
    });
  }

  ngAfterViewInit(): void {
    this.initMap();
    this.loadGeoJson();
  }

  private initMap(): void {
    this.map = L.map('radar-map', {
      center: [20, 0],
      zoom: 3,
      minZoom: 2.2,
      maxBounds: L.latLngBounds(L.latLng(-85, -180), L.latLng(85, 180)),
      maxBoundsViscosity: 1.0,
      zoomControl: false,
      attributionControl: true
    });

    // Doppio Layer - Base Layer scuro (Senza etichette) sotto i poligoni di hatching
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap contributors © CARTO',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(this.map);

    // Doppio Layer - Creazione Pane custom per le etichette geografiche (Labels Overlay Pane)
    // Configurato forzatamente SOPRA i poligoni del GeoJSON
    const labelsPane = this.map.createPane('labelsPane');
    labelsPane.style.zIndex = '650';
    labelsPane.style.pointerEvents = 'none'; // I click passano sotto per poter cliccare i paesi/marker

    // Aggiunta Tile Layer per le sole etichette testuali sul Pane custom
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', {
      pane: 'labelsPane',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(this.map);

    // Cluster Group - clustering attivo fino a zoom elevato (17) per evitare sovrapposizioni e consentire spiderfy
    this.clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 40,
      showCoverageOnHover: false,
      disableClusteringAtZoom: 9,
      iconCreateFunction: (cluster: any) => {
        const count = cluster.getChildCount();
        return L.divIcon({
          html: `<div class="cluster-icon">${count}</div>`,
          className: 'radar-cluster',
          iconSize: [40, 40]
        });
      }
    });

    this.clusterGroup.on('clusterclick', (e: any) => {
      const childMarkers: Leaflet.Marker[] = e.layer.getAllChildMarkers();
      const arts: Article[] = childMarkers
        .map((m: any) => m['articleData'] as Article)
        .filter(Boolean);
      if (arts.length > 0) this.clusterClicked.emit(arts);
    });

    this.map.addLayer(this.clusterGroup);
    this.geoJsonLayerGroup.addTo(this.map);

    // Listener zoom → attiva l'hatching in zoom-out
    this.map.on('zoomend', () => {
      const zoom = this.map.getZoom();
      this.currentZoomLevel.set(zoom);
      this.refreshHatchingStyles();
    });
  }

  private loadGeoJson(): void {
    // Caricamento una tantum dell'asset locale da 14.6 MB per prevenire memory leak
    this.http.get<GeoJSON.FeatureCollection>('assets/data/countries.geo.json')
      .subscribe({
        next: (geoData) => this.parseGeoJsonIncremental(geoData),
        error: (err) => {
          console.error('[RadarMap] Errore caricamento GeoJSON:', err);
          this.isParsingGeoJson.set(false);
        }
      });
  }

  private parseGeoJsonIncremental(geoData: GeoJSON.FeatureCollection): void {
    const features = geoData.features;
    let index = 0;
    const batchSize = 15; // Processa 15 poligoni per frame per mantenere l'interfaccia a 60fps all'avvio

    const processBatch = () => {
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
            color: 'rgba(0, 212, 255, 0.15)', // Bordo soft
            weight: 0.5,
            fillOpacity: 0,
            fillColor: 'transparent',
            className: 'country-fill'
          })
        });

        // Click su nazione in hatching-mode
        layer.on('click', () => {
          if (this.isZoomedOut()) {
            const countryArts = this.articles().filter(a => a.country_code === code);
            if (countryArts.length > 0) this.countryClicked.emit(countryArts);
          }
        });

        layer.addTo(this.geoJsonLayerGroup);

        // Memorizza il riferimento ai path vettoriali (supporta MultiPolygons come isole/parti distaccate)
        layer.eachLayer((subLayer: any) => {
          if (subLayer instanceof L.Path) {
            const list = this.countryLayersMap.get(code) || [];
            list.push(subLayer);
            this.countryLayersMap.set(code, list);
          }
        });
      }

      index = end;
      if (index < features.length) {
        requestAnimationFrame(processBatch); // Esecuzione al frame successivo
      } else {
        this.isParsingGeoJson.set(false); // Nasconde l'App Bootstrapping Overlay
        this.refreshHatchingStyles();
      }
    };

    requestAnimationFrame(processBatch);
  }

  private refreshHatchingStyles(): void {
    const ctrs = this.countries();
    const zoomedOut = this.isZoomedOut();

    const svg = this.map ? this.map.getContainer().querySelector('.leaflet-overlay-pane svg') : null;
    let defs: SVGElement | null = null;
    if (svg) {
      defs = svg.querySelector('defs') as SVGElement;
      if (!defs) {
        defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        svg.insertBefore(defs, svg.firstChild);
      }
    }

    // Aggiornamento dei layer vettoriali tramite metodo nativo .setStyle() a frame rate pieno su tutte le parti geografiche
    const baseUrl = window.location.href.split('#')[0];
    this.countryLayersMap.forEach((layers, code) => {
      const summary = ctrs.find(c => c.country_code === code);

      layers.forEach(layer => {
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

  private getOrCreateComboPattern(categories: string[], defs: SVGElement): string {
    if (!categories || categories.length === 0) {
      return '';
    }

    const sortedCats = [...categories].sort();
    const id = 'hatch-grid-' + sortedCats.map(c => c.toLowerCase().replace(/ /g, '-')).join('-');

    if (defs.querySelector(`#${id}`)) {
      return id;
    }

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

    if (sortedCats.length === 1) {
      const line1 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line1.setAttribute('x1', '0'); line1.setAttribute('y1', '24');
      line1.setAttribute('x2', '24'); line1.setAttribute('y2', '0');
      line1.setAttribute('stroke', getColorVar(sortedCats[0]));
      line1.setAttribute('stroke-width', strokeWidth);
      line1.setAttribute('opacity', strokeOpacity);
      pattern.appendChild(line1);

      const line2 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line2.setAttribute('x1', '0'); line2.setAttribute('y1', '0');
      line2.setAttribute('x2', '24'); line2.setAttribute('y2', '24');
      line2.setAttribute('stroke', getColorVar(sortedCats[0]));
      line2.setAttribute('stroke-width', strokeWidth);
      line2.setAttribute('opacity', strokeOpacity);
      pattern.appendChild(line2);
    } else {
      for (let i = 0; i < sortedCats.length; i++) {
        const cat = sortedCats[i];
        const strokeColor = getColorVar(cat);

        if (i === 0) {
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('x1', '0'); line.setAttribute('y1', '24');
          line.setAttribute('x2', '24'); line.setAttribute('y2', '0');
          line.setAttribute('stroke', strokeColor);
          line.setAttribute('stroke-width', strokeWidth);
          line.setAttribute('opacity', strokeOpacity);
          pattern.appendChild(line);
        } else if (i === 1) {
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('x1', '0'); line.setAttribute('y1', '0');
          line.setAttribute('x2', '24'); line.setAttribute('y2', '24');
          line.setAttribute('stroke', strokeColor);
          line.setAttribute('stroke-width', strokeWidth);
          line.setAttribute('opacity', strokeOpacity);
          pattern.appendChild(line);
        } else if (i === 2) {
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('x1', '0'); line.setAttribute('y1', '12');
          line.setAttribute('x2', '24'); line.setAttribute('y2', '12');
          line.setAttribute('stroke', strokeColor);
          line.setAttribute('stroke-width', strokeWidth);
          line.setAttribute('opacity', strokeOpacity);
          pattern.appendChild(line);
        } else if (i === 3) {
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('x1', '12'); line.setAttribute('y1', '0');
          line.setAttribute('x2', '12'); line.setAttribute('y2', '24');
          line.setAttribute('stroke', strokeColor);
          line.setAttribute('stroke-width', strokeWidth);
          line.setAttribute('opacity', strokeOpacity);
          pattern.appendChild(line);
        } else if (i === 4) {
          const line1 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line1.setAttribute('x1', '0'); line1.setAttribute('y1', '12');
          line1.setAttribute('x2', '12'); line1.setAttribute('y2', '0');
          line1.setAttribute('stroke', strokeColor);
          line1.setAttribute('stroke-width', strokeWidth);
          line1.setAttribute('opacity', strokeOpacity);
          pattern.appendChild(line1);

          const line2 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line2.setAttribute('x1', '12'); line2.setAttribute('y1', '24');
          line2.setAttribute('x2', '24'); line2.setAttribute('y2', '12');
          line2.setAttribute('stroke', strokeColor);
          line2.setAttribute('stroke-width', strokeWidth);
          line2.setAttribute('opacity', strokeOpacity);
          pattern.appendChild(line2);
        } else if (i === 5) {
          const line1 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line1.setAttribute('x1', '12'); line1.setAttribute('y1', '0');
          line1.setAttribute('x2', '24'); line1.setAttribute('y2', '12');
          line1.setAttribute('stroke', strokeColor);
          line1.setAttribute('stroke-width', strokeWidth);
          line1.setAttribute('opacity', strokeOpacity);
          pattern.appendChild(line1);

          const line2 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line2.setAttribute('x1', '0'); line2.setAttribute('y1', '12');
          line2.setAttribute('x2', '12'); line2.setAttribute('y2', '24');
          line2.setAttribute('stroke', strokeColor);
          line2.setAttribute('stroke-width', strokeWidth);
          line2.setAttribute('opacity', strokeOpacity);
          pattern.appendChild(line2);
        }
      }
    }

    defs.appendChild(pattern);
    return id;
  }

  private focusOnCountry(code: string): void {
    if (!this.map) return;

    let bounds: Leaflet.LatLngBounds | null = null;

    // Configurazione statica per paesi trans-antimeridiano per evitare disallineamenti di coordinate
    if (code === 'US') {
      bounds = L.latLngBounds(L.latLng(24.396308, -125.0), L.latLng(49.384358, -66.93457));
    } else if (code === 'RU') {
      bounds = L.latLngBounds(L.latLng(41.1856, 19.6389), L.latLng(81.8587, 169.0));
    } else {
      const layers = this.countryLayersMap.get(code);
      if (layers && layers.length > 0) {
        const b = L.latLngBounds([]);
        layers.forEach(layer => {
          if (typeof (layer as any).getBounds === 'function') {
            b.extend((layer as any).getBounds());
          }
        });
        if (b.isValid()) {
          bounds = b;
        }
      }
    }

    if (bounds && bounds.isValid()) {
      this.map.fitBounds(bounds, {
        maxZoom: 4,
        animate: true,
        duration: 1.0
      });
    }
  }

  private updateMapData(articles: Article[], countries: CountrySummary[]): void {
    // Svuota solo i marker del cluster group, senza toccare il GeoJSON di sfondo
    this.clusterGroup.clearLayers();

    const coordinateCounts = new Map<string, number>();

    for (const article of articles) {
      if (!article.latitude || !article.longitude) continue;

      let lat = article.latitude;
      let lng = article.longitude;
      const key = `${lat.toFixed(5)},${lng.toFixed(5)}`;
      const count = coordinateCounts.get(key) || 0;
      coordinateCounts.set(key, count + 1);

      if (count > 0) {
        // Applica una dispersione a cerchio deterministica per evitare sovrapposizioni complete (zoom >= 7)
        const angle = (count * 2 * Math.PI) / 8; // Distribuisce in 8 direzioni
        const radius = 0.004 * (1 + Math.floor(count / 8) * 0.5); // Concentrico se > 8
        lat += Math.sin(angle) * radius;
        lng += Math.cos(angle) * radius;
      }

      const emoji = this.CATEGORY_ICONS[article.primary_category] ?? '📍';
      const icon = L.divIcon({
        html: `<div class="marker-icon" title="${article.title}">${emoji}</div>`,
        className: `marker-${article.primary_category.toLowerCase()}`,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });

      const marker = L.marker([lat, lng], { icon });
      (marker as any)['articleData'] = article;
      marker.on('click', () => this.markerClicked.emit(article));
      this.clusterGroup.addLayer(marker);
    }

    this.refreshHatchingStyles();
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }
}
