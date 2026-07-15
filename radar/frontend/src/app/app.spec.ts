import { Component, importProvidersFrom, input, output, signal, computed } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from './app';
import { Article, ArticleFilters, CountrySummary } from './models/article.model';
import { ArticleService } from './services/article.service';
import { StateService } from './services/state.service';
import { RadarMapComponent } from './components/radar-map/radar-map.component';
import { RadarToolbarComponent } from './components/radar-toolbar/radar-toolbar.component';
import { RadarSidebarComponent } from './components/radar-sidebar/radar-sidebar.component';
import { installLeafletStub, type StubClusterGroup, type StubMap } from './testing/leaflet.stub';
import { MOCK_MODE } from './services/mock-mode.token';

const FIXTURE_DATE = '2026-07-14';

function makeArticle(overrides: Partial<Article> & Pick<Article, 'id' | 'title'>): Article {
  return {
    summary: 'Fixture summary',
    published_at: FIXTURE_DATE,
    source_url: `https://example.com/article-${overrides.id}`,
    country_code: 'DE',
    latitude: 51.05,
    longitude: 13.73,
    primary_category: 'Energia',
    sentiment: 'Neutrale',
    relevance_level: 3,
    companies_involved: [],
    tags: [],
    infrastructural_entities: [],
    feed_title: 'Fixture Feed',
    is_read: false,
    ...overrides,
  };
}

const FIXTURE_ARTICLES: Article[] = [
  makeArticle({
    id: 1,
    title: 'Unread nuclear update',
    primary_category: 'Nucleare',
    country_code: 'UA',
    latitude: 47.5,
    longitude: 34.4,
    is_read: false,
  }),
  makeArticle({
    id: 2,
    title: 'Read energy update',
    primary_category: 'Energia',
    country_code: 'UA',
    latitude: 47.4,
    longitude: 34.3,
    is_read: true,
  }),
  makeArticle({
    id: 3,
    title: 'Unread tech update',
    primary_category: 'Tecnologia',
    country_code: 'DE',
    latitude: 51.05,
    longitude: 13.73,
    is_read: false,
  }),
];

const EMPTY_GEOJSON = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { 'ISO3166-1-Alpha-2': 'DE', name: 'Germany' },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [10, 50],
            [11, 50],
            [11, 51],
            [10, 51],
            [10, 50],
          ],
        ],
      },
    },
  ],
};

@Component({
  selector: 'app-radar-toolbar',
  standalone: true,
  template: '',
})
class ToolbarStubComponent {
  countries = input<CountrySummary[]>([]);
  articleCount = input(0);
  readCount = input(0);
  isLoading = input(false);
  apiError = input(false);
  filtersChange = output<ArticleFilters>();
  countrySelected = output<string>();
}

@Component({
  selector: 'app-radar-sidebar',
  standalone: true,
  template: '',
})
class SidebarStubComponent {
  article = input<Article | null>(null);
  clusterArticles = input<Article[]>([]);
  isOpen = input(false);
  closed = output<void>();
  categoryClicked = output<string>();
  activeArticleChanged = output<Article | null>();
}

@Component({
  selector: 'app-radar-map',
  standalone: true,
  template: '',
})
class MapStubComponent {
  articles = input.required<Article[]>();
  countries = input.required<CountrySummary[]>();
  mapSummary = input<import('./models/map-summary.model').MapSummaryRow[]>([]);
  focusCountryCode = input<string | null>(null);
  markerClicked = output<Article>();
  clusterClicked = output<Article[]>();
  countryClicked = output<import('./components/radar-map/radar-map.component').CountryOpenRequest>();
  collapseAllGraphs(_emitClose?: boolean): void {
    /* no-op stub */
  }
  focusAndSpiderfyCategory(_countryCode: string, _category: string): void {
    /* no-op stub */
  }
  focusAndSpiderfyCountry(_countryCode: string): void {
    /* no-op stub */
  }
  highlightMarkerForArticle(_article: Article | null): void {
    /* no-op stub */
  }
  invalidateSize(): void {
    /* no-op stub */
  }
}

@Component({
  selector: 'app-map-host',
  standalone: true,
  imports: [RadarMapComponent],
  template: `
    <app-radar-map
      [articles]="articles"
      [countries]="countries"
      [mapSummary]="mapSummary"
      [focusCountryCode]="focusCountryCode"
    />
  `,
})
class MapHostComponent {
  articles: Article[] = [];
  countries: CountrySummary[] = [];
  mapSummary: import('./models/map-summary.model').MapSummaryRow[] = [];
  focusCountryCode: string | null = null;
}

/**
 * Lightweight StateService stand-in for App tests.
 * Avoids Angular 21 rxResource + TestBed PendingTasks race in Vitest/jsdom.
 */
function createStateStub(initial: Article[] = FIXTURE_ARTICLES, error: unknown = null) {
  const detailSignal = signal<Article[]>(structuredClone(initial));
  const errorSignal = signal<unknown>(error);
  return {
    filters: signal<ArticleFilters>({
      date: FIXTURE_DATE,
      sentiment: [],
      categories: [],
    }),
    detailArticles: detailSignal,
    detailLoading: signal(false),
    articles: computed(() => detailSignal()),
    countries: computed(() => [] as CountrySummary[]),
    filteredSummary: computed(() => [] as import('./models/map-summary.model').MapSummaryRow[]),
    articleCount: computed(() => detailSignal().length),
    readCount: computed(() => detailSignal().filter((a) => a.is_read).length),
    isLoading: computed(() => false),
    error: computed(() => errorSignal()),
    clearDetailArticles(): void {
      detailSignal.set([]);
    },
    async loadCountryArticles(countryCode: string): Promise<Article[]> {
      const arts = detailSignal().filter((a) => a.country_code === countryCode);
      detailSignal.set(arts);
      return arts;
    },
    toggleReadStatus(articleId: number, isRead: boolean): void {
      detailSignal.update((arts) => {
        return arts.map((a) => {
          if (a.id !== articleId) return a;
          a.is_read = isRead;
          return a;
        });
      });
    },
  };
}

describe('App / map behavior', () => {
  beforeEach(() => {
    installLeafletStub();
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    TestBed.resetTestingModule();
    installLeafletStub();
  });

  describe('read-status ordering', () => {
    it('preserves article id order while flipping is_read', () => {
      const state = createStateStub(FIXTURE_ARTICLES);
      const beforeIds = state.articles().map((a) => a.id);
      expect(beforeIds).toEqual([1, 2, 3]);
      expect(
        state
          .articles()
          .filter((a) => !a.is_read)
          .map((a) => a.id),
      ).toEqual([1, 3]);

      state.toggleReadStatus(1, true);

      expect(state.articles().map((a) => a.id)).toEqual(beforeIds);
      expect(state.articles().find((a) => a.id === 1)?.is_read).toBe(true);
      expect(
        state
          .articles()
          .filter((a) => !a.is_read)
          .map((a) => a.id),
      ).toEqual([3]);
    });
  });

  describe('RadarMapComponent', () => {
    let httpMock: HttpTestingController;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [MapHostComponent],
        providers: [provideHttpClient(), provideHttpClientTesting()],
      }).compileComponents();

      httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
      httpMock.verify();
    });

    function flushGeoJson(): void {
      const geoReqs = httpMock.match((req) => req.url.includes('countries.geo.json'));
      expect(geoReqs.length).toBeGreaterThan(0);
      geoReqs.forEach((req) => req.flush(EMPTY_GEOJSON));
    }

    it('removes the Leaflet map on destroy', async () => {
      const fixture = TestBed.createComponent(MapHostComponent);
      fixture.detectChanges();
      flushGeoJson();
      await fixture.whenStable();

      const mapCmp = fixture.debugElement.children[0].componentInstance as RadarMapComponent;
      const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
      expect(mapInstance._removed).toBe(false);

      fixture.destroy();
      expect(mapInstance._removed).toBe(true);
    });

    it('clears GeoJSON parsing error state when the asset request fails', async () => {
      const fixture = TestBed.createComponent(MapHostComponent);
      fixture.detectChanges();

      const geoReq = httpMock.expectOne((req) => req.url.includes('countries.geo.json'));
      geoReq.flush('missing', { status: 404, statusText: 'Not Found' });
      await fixture.whenStable();

      const mapCmp = fixture.debugElement.children[0].componentInstance as RadarMapComponent;
      expect(mapCmp.isParsingGeoJson()).toBe(false);
    });

    it('keeps article markers inside cluster groups for large country sets', async () => {
      const bulk: Article[] = Array.from({ length: 80 }, (_, i) =>
        makeArticle({
          id: i + 1,
          title: `Bulk article ${i + 1}`,
          country_code: 'DE',
          primary_category: 'Energia',
          latitude: 51.05 + (i % 5) * 0.01,
          longitude: 13.73 + (i % 5) * 0.01,
        }),
      );
      const countries: CountrySummary[] = [
        { country_code: 'DE', categories: ['Energia'], article_count: bulk.length },
      ];

      const fixture = TestBed.createComponent(MapHostComponent);
      fixture.componentInstance.articles = bulk;
      fixture.componentInstance.countries = countries;
      fixture.detectChanges();
      flushGeoJson();
      await fixture.whenStable();

      const mapCmp = fixture.debugElement.children[0].componentInstance as RadarMapComponent;
      expect(mapCmp.isParsingGeoJson()).toBe(false);

      // Drive cluster population directly after GeoJSON is ready (same path as the map effect).
      (
        mapCmp as unknown as {
          updateMapData: (articles: Article[], countries: CountrySummary[], summary?: unknown[]) => void;
        }
      ).updateMapData(bulk, countries, []);

      const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
      const categoryGroups = (
        mapCmp as unknown as { categoryClusterGroups: Map<string, StubClusterGroup> }
      ).categoryClusterGroups;

      const energiaGroup = categoryGroups.get('Energia');
      expect(energiaGroup).toBeTruthy();
      // 80 real markers + 1 dummy for the DE_Energia spot
      expect(energiaGroup!.getLayers().length).toBe(81);

      const directArticleMarkersOnMap = mapInstance._layers.filter(
        (layer) => layer && typeof layer === 'object' && 'articleData' in (layer as object),
      );
      expect(directArticleMarkersOnMap).toHaveLength(0);

      const clusterGroupsOnMap = mapInstance._layers.filter(
        (layer) => layer && typeof layer === 'object' && 'getAllChildMarkers' in (layer as object),
      );
      expect(clusterGroupsOnMap.length).toBe(10);
    });
  });

  describe('App', () => {
    beforeEach(async () => {
      const stateStub = createStateStub();

      await TestBed.configureTestingModule({
        imports: [App],
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          importProvidersFrom(NoopAnimationsModule),
          { provide: StateService, useValue: stateStub },
          { provide: MOCK_MODE, useValue: false },
          {
            provide: ArticleService,
            useValue: {
              getMapSummary: () => of([]),
              getArticlesPage: () => of({ items: structuredClone(FIXTURE_ARTICLES), next_cursor: null, total: 3 }),
              getAllArticlesForCountry: () => of(structuredClone(FIXTURE_ARTICLES)),
              getCountries: () => of([]),
              updateReadStatus: () => of({ status: 'success', is_read: true }),
            },
          },
        ],
      })
        .overrideComponent(App, {
          remove: {
            imports: [RadarMapComponent, RadarToolbarComponent, RadarSidebarComponent],
          },
          add: {
            imports: [MapStubComponent, ToolbarStubComponent, SidebarStubComponent],
          },
        })
        .compileComponents();
    });

    it('creates the app shell', () => {
      const fixture = TestBed.createComponent(App);
      fixture.detectChanges();
      expect(fixture.componentInstance).toBeTruthy();
      expect(fixture.nativeElement.querySelector('app-radar-map')).toBeTruthy();
    });

    it('opens and closes cluster articles from map events', () => {
      const fixture = TestBed.createComponent(App);
      const app = fixture.componentInstance;
      fixture.detectChanges();

      app.onClusterClick([FIXTURE_ARTICLES[0], FIXTURE_ARTICLES[1]]);
      expect(app.isSidebarOpen()).toBe(true);
      expect(app.clusterArticles().map((a) => a.id)).toEqual([1, 2]);
      expect(app.selectedArticle()?.id).toBe(1);

      app.onClusterClick([]);
      expect(app.isSidebarOpen()).toBe(false);
      expect(app.clusterArticles()).toEqual([]);
    });

    it('auto-marks unread article as read when carousel active article changes', () => {
      const fixture = TestBed.createComponent(App);
      const app = fixture.componentInstance;
      fixture.detectChanges();
      const spy = vi.spyOn(app.state, 'toggleReadStatus');

      app.onActiveArticleChanged({ ...FIXTURE_ARTICLES[0], is_read: false });
      expect(spy).toHaveBeenCalledWith(1, true);
    });

    it('does not call toggle when active article is already read', () => {
      const fixture = TestBed.createComponent(App);
      const app = fixture.componentInstance;
      fixture.detectChanges();
      const spy = vi.spyOn(app.state, 'toggleReadStatus');

      app.onActiveArticleChanged({ ...FIXTURE_ARTICLES[1], is_read: true });
      expect(spy).not.toHaveBeenCalled();
    });

    it('ignores null active article for auto-read', () => {
      const fixture = TestBed.createComponent(App);
      const app = fixture.componentInstance;
      fixture.detectChanges();
      const spy = vi.spyOn(app.state, 'toggleReadStatus');

      app.onActiveArticleChanged(null);
      expect(spy).not.toHaveBeenCalled();
    });

    it('exposes error state from StateService to the shell', async () => {
      TestBed.resetTestingModule();
      installLeafletStub();

      await TestBed.configureTestingModule({
        imports: [App],
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          importProvidersFrom(NoopAnimationsModule),
          {
            provide: StateService,
            useValue: createStateStub([], new Error('backend unavailable')),
          },
        ],
      })
        .overrideComponent(App, {
          remove: {
            imports: [RadarMapComponent, RadarToolbarComponent, RadarSidebarComponent],
          },
          add: {
            imports: [MapStubComponent, ToolbarStubComponent, SidebarStubComponent],
          },
        })
        .compileComponents();

      const fixture = TestBed.createComponent(App);
      fixture.detectChanges();

      expect(fixture.componentInstance.state.error()).toBeTruthy();
      expect(fixture.componentInstance.state.articles()).toEqual([]);
    });
  });
});
