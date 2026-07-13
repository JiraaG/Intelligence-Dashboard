import {
  Component, AfterViewInit, OnDestroy, input, output,
  signal, computed, effect, inject
} from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import type * as Leaflet from 'leaflet';

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
  isParsingGeoJson = signal<boolean>(true);

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

  private map!: Leaflet.Map;
  private categoryClusterGroups = new Map<string, any>();
  private isNavigating = false;
  private navigatingTargetZoom = 0;               
  private geoJsonLayerGroup = L.layerGroup();
  private countryLayersMap = new Map<string, Leaflet.Path[]>();
  
  private activeRootMarkers: Leaflet.Marker[] = [];

  constructor() {
    effect(() => {
      const arts = this.articles();
      const ctrs = this.countries();
      if (this.map && !this.isParsingGeoJson() && !this.isNavigating) {
        this.updateMapData(arts, ctrs);
      }
    });

    effect(() => {
      const code = this.focusCountryCode();
      if (code && this.map && !this.isParsingGeoJson() && !this.isNavigating) {
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

    // Se l'utente clicca su un punto vuoto della mappa, chiudiamo tutti i grafi e la sidebar.
    this.map.on('click', (e: any) => {
      if (e.originalEvent && (e.originalEvent as any)._radarHandled) return;
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
      const cssVar = this.CATEGORY_CSS_VARS[cat];
      const catClass = `cat-${cat.toLowerCase()}`;

      const cg = L.markerClusterGroup({
        maxClusterRadius: 40,            
        showCoverageOnHover: false,
        spiderfyOnMaxZoom: false,        
        zoomToBoundsOnClick: false,
        spiderfyDistanceMultiplier: 2.8, 
        iconCreateFunction: (cluster: any) => {
          const childMarkers = cluster.getAllChildMarkers();
          
          const realCount = childMarkers.filter((m: any) => !m['isDummy']).length;
          if (realCount === 0) return L.divIcon({ className: 'hidden', iconSize: [0,0] });

          const zoom = this.map ? this.map.getZoom() : 3;
          const iconScale = Math.max(1.0, Math.min(3.0, 1.0 + (zoom - 5) * 0.15));
          const iconPx = Math.round(52 * iconScale);
          const half = Math.round(iconPx / 2);
          
          const [ox, oy] = this.UI_OFFSETS[cat] || [0, 0];

          return L.divIcon({
            html: `<div class="cluster-icon">${realCount}</div>`,
            className: `radar-cluster ${catClass}`,
            iconSize: [iconPx, iconPx],
            iconAnchor: [half - (ox * iconScale), half - (oy * iconScale)]
          });
        }
      });

      // GARANZIA: Se Leaflet interviene in autonomia a chiudere i nodi (es: per zoom), 
      // spazziamo via i dummy clone per evitare l'effetto "fantasma intoccabile".
      cg.on('unspiderfied', () => {
        this.clearRootMarkers();
      });

      cg.on('clusterclick', (e: any) => {
        if (e.originalEvent) {
          e.originalEvent.preventDefault();
          L.DomEvent.stopPropagation(e.originalEvent);
          (e.originalEvent as any)._radarHandled = true;
        }

        const cluster = e.layer;
        const childMarkers: Leaflet.Marker[] = cluster.getAllChildMarkers();
        
        const isAlreadyOpen = (cg as any)._spiderfied === cluster;
        
        this.collapseAllGraphs();

        if (isAlreadyOpen) {
          this.clusterClicked.emit([]);
          return;
        }

        let arts: Article[] = childMarkers
          .filter((m: any) => !m['isDummy'])
          .map((m: any) => m['articleData'] as Article)
          .filter(Boolean);

        if (arts.length > 0) this.clusterClicked.emit(arts);

        const currentZoom = this.map.getZoom();
        const targetZoom = 6; 

        if (currentZoom >= targetZoom) {
          this.spiderfyAndCreateRoot(cg, childMarkers);
          return;
        }

        this.isNavigating = true;
        this.navigatingTargetZoom = targetZoom;
        this.map.flyTo(cluster.getLatLng(), targetZoom, { animate: true, duration: 0.6 });

        this.map.once('zoomend', () => {
          setTimeout(() => {
            this.spiderfyAndCreateRoot(cg, childMarkers);
            this.isNavigating = false;
          }, 250);
        });
      });

      this.categoryClusterGroups.set(cat, cg);
      this.map.addLayer(cg);
    }
    this.geoJsonLayerGroup.addTo(this.map);

    this.map.on('zoomend', () => {
      const zoom = this.map.getZoom();
      this.currentZoomLevel.set(zoom);
      this.refreshHatchingStyles();

      if (zoom < 5 && !this.isNavigating) {
        this.collapseAllGraphs(true);
      }
    });
  }

  private clearRootMarkers(): void {
    // Eliminiamo dalla mappa tutti i pallini radice clone "fantasma" rimasti in sospeso
    this.activeRootMarkers.forEach(m => {
      if (this.map.hasLayer(m)) this.map.removeLayer(m);
    });
    this.activeRootMarkers = [];
  }

  private spiderfyAndCreateRoot(cg: any, childMarkers: any[]): void {
    if (!childMarkers || childMarkers.length === 0) return;
    const newParent = cg.getVisibleParent(childMarkers[0]);
    
    if (newParent && typeof newParent.spiderfy === 'function') {
      
      // Assicuriamoci che non ci siano vecchi cloni attivi (risolve bug di persistenza clicks)
      this.clearRootMarkers();

      const rootIcon = newParent.getIcon();
      const rootMarker = L.marker(newParent.getLatLng(), {
        icon: rootIcon,
        interactive: true,
        zIndexOffset: 1000 
      }).addTo(this.map);
      
      rootMarker.on('click', (e: any) => {
        if (e.originalEvent) {
          (e.originalEvent as any)._radarHandled = true;
        }
        L.DomEvent.stopPropagation(e);
        this.collapseAllGraphs(true); 
      });

      this.activeRootMarkers.push(rootMarker);
      
      newParent.spiderfy();
    }
  }

  private loadGeoJson(): void {
    this.http.get<GeoJSON.FeatureCollection>('assets/data/countries.geo.json')
      .subscribe({
        next: (geoData) => this.parseGeoJsonIncremental(geoData),
        error: (err) => {
          console.error('[RadarMap] Errore GeoJSON:', err);
          this.isParsingGeoJson.set(false);
        }
      });
  }

  private parseGeoJsonIncremental(geoData: GeoJSON.FeatureCollection): void {
    const features = geoData.features;
    let index = 0;
    const batchSize = 15;

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
            color: 'rgba(0, 212, 255, 0.15)',
            weight: 0.5,
            fillOpacity: 0,
            fillColor: 'transparent',
            className: 'country-fill'
          })
        });

        layer.on('click', (e: any) => {
          if (this.isZoomedOut()) {
            // Impediamo alla mappa di far scattare il suo "click a vuoto" in background
            if (e.originalEvent) {
              L.DomEvent.stopPropagation(e.originalEvent);
            }
            const countryArts = this.articles().filter(a => a.country_code === code);
            if (countryArts.length > 0) {
              if (e.originalEvent) {
                (e.originalEvent as any)._radarHandled = true;
              }
              this.countryClicked.emit(countryArts);
            }
          }
        });

        layer.addTo(this.geoJsonLayerGroup);

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
        requestAnimationFrame(processBatch);
      } else {
        this.isParsingGeoJson.set(false);
        this.refreshHatchingStyles();
      }
    };

    requestAnimationFrame(processBatch);
  }

  private refreshHatchingStyles(): void {
    const ctrs = this.countries();
    const zoomedOut = this.currentZoomLevel() < 5;

    const svg = this.map ? this.map.getContainer().querySelector('.leaflet-overlay-pane svg') : null;
    let defs: SVGElement | null = null;
    if (svg) {
      defs = svg.querySelector('defs') as SVGElement;
      if (!defs) {
        defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        svg.insertBefore(defs, svg.firstChild);
      }
    }

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
    if (!categories || categories.length === 0) return '';

    const sortedCats = [...categories].sort();
    const id = 'hatch-grid-' + sortedCats.map(c => c.toLowerCase().replace(/ /g, '-')).join('-');

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
          line2.setAttribute('x1', '0'); line1.setAttribute('y1', '12');
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
    if (this.isNavigating) return;

    let bounds: Leaflet.LatLngBounds | null = null;

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
      
      const cleanup = () => {
        this.isNavigating = false;
        this.map.off('zoomend', cleanup);
        this.map.off('moveend', cleanup);
      };
      
      this.map.once('zoomend', cleanup);
      this.map.once('moveend', cleanup);
      setTimeout(cleanup, 1500);
    }
  }

  private updateMapData(articles: Article[], countries: CountrySummary[]): void {
    this.categoryClusterGroups.forEach(group => group.clearLayers());
    const countryCenters = new Map<string, { latSum: number, lngSum: number, count: number }>();
    
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
      
      let baseLat = center.latSum / center.count;
      let baseLng = center.lngSum / center.count;
      const realLatLng = L.latLng(baseLat, baseLng);

      const cat = article.primary_category;
      const [ox, oy] = this.UI_OFFSETS[cat] || [0, 0];
      
      populatedSpots.add(`${code}_${cat}`);

      const emoji = this.CATEGORY_ICONS[cat] ?? '📍';
      const icon = L.divIcon({
        html: `<div class="marker-icon" style="font-size: 24px; line-height: 44px; text-align: center;" title="${article.title}">${emoji}</div>`,
        className: `marker-${cat.toLowerCase()}`,
        iconSize: [44, 44],
        iconAnchor: [22 - ox, 22 - oy] 
      });

      const marker = L.marker([baseLat, baseLng], { icon });
      (marker as any)['articleData'] = article;
      (marker as any)['realLatLng'] = realLatLng;
      (marker as any)['isDummy'] = false;
      
      marker.on('click', (e: any) => {
        if (e.originalEvent) {
          L.DomEvent.stopPropagation(e.originalEvent);
          (e.originalEvent as any)._radarHandled = true;
        }
        this.markerClicked.emit(article);
      });

      const targetGroup = this.categoryClusterGroups.get(cat);
      if (targetGroup) targetGroup.addLayer(marker);
    }

    populatedSpots.forEach(spot => {
      const [code, cat] = spot.split('_');
      const center = countryCenters.get(code)!;
      let baseLat = center.latSum / center.count;
      let baseLng = center.lngSum / center.count;

      const invisibleIcon = L.divIcon({
        html: '',
        className: '',
        iconSize: [0, 0], 
        iconAnchor: [0, 0]
      });

      const dummyMarker = L.marker([baseLat, baseLng], { icon: invisibleIcon, interactive: false });
      (dummyMarker as any)['isDummy'] = true;
      
      const targetGroup = this.categoryClusterGroups.get(cat);
      if (targetGroup) targetGroup.addLayer(dummyMarker);
    });

    this.refreshHatchingStyles();
  }

  collapseAllGraphs(emitClose: boolean = false): void {
    if (!this.map) return;
    
    this.clearRootMarkers();
    
    this.categoryClusterGroups.forEach(cg => {
      const spiderfiedCluster = (cg as any)._spiderfied;
      if (spiderfiedCluster && typeof spiderfiedCluster.unspiderfy === 'function') {
        spiderfiedCluster.unspiderfy();
      }
    });

    if (emitClose) {
      this.clusterClicked.emit([]);
    }
  }

  public focusAndSpiderfyCategory(countryCode: string, category: string): void {
    if (!this.map) return;
    const cg = this.categoryClusterGroups.get(category);
    if (!cg) return;

    const allMarkers = cg.getLayers();
    const countryMarkers = allMarkers.filter((m: any) => m.articleData && m.articleData.country_code === countryCode);

    if (countryMarkers.length === 0) return;

    this.collapseAllGraphs(false);

    const firstMarker = countryMarkers[0];
    const parent = cg.getVisibleParent(firstMarker);

    if (!parent) return;

    const currentZoom = this.map.getZoom();
    const targetZoom = 6;
    
    const latLng = typeof parent.getLatLng === 'function' ? parent.getLatLng() : firstMarker.getLatLng();

    if (currentZoom >= targetZoom) {
      this.spiderfyAndCreateRoot(cg, countryMarkers);
      return;
    }

    this.isNavigating = true;
    this.navigatingTargetZoom = targetZoom;
    this.map.flyTo(latLng, targetZoom, { animate: true, duration: 0.6 });

    const cleanup = () => {
      setTimeout(() => {
        this.spiderfyAndCreateRoot(cg, countryMarkers);
        this.isNavigating = false;
        this.map.off('zoomend', cleanup);
        this.map.off('moveend', cleanup);
      }, 250);
    };

    this.map.once('zoomend', cleanup);
    this.map.once('moveend', cleanup);
    setTimeout(cleanup, 1200);
  }

  private highlightedMarker: any = null;
  private pendingHighlightArticle: Article | null = null;

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
    if (!this.pendingHighlightArticle) return;
    const article = this.pendingHighlightArticle;

    let targetMarker: any = null;
    const cg = this.categoryClusterGroups.get(article.primary_category);
    if (cg) {
      const markers = cg.getLayers();
      targetMarker = markers.find((m: any) => m.articleData && m.articleData.id === article.id);
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
        setTimeout(() => {
          this.applyHighlight(retries - 1);
        }, 150);
      }
    } else if (retries > 0) {
      setTimeout(() => {
        this.applyHighlight(retries - 1);
      }, 150);
    }
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }
}