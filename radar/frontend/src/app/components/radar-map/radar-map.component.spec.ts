import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Article, CountrySummary } from '../../models/article.model';
import { RadarMapComponent } from './radar-map.component';
import {
  installLeafletStub,
  type StubClusterGroup,
  type StubMap,
} from '../../testing/leaflet.stub';

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
    related_countries: [],
    is_read: false,
    ...overrides,
  };
}

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
  selector: 'app-map-host',
  standalone: true,
  imports: [RadarMapComponent],
  template: `
    <app-radar-map
      [articles]="articles"
      [countries]="countries"
      [mapSummary]="mapSummary"
      [mapRelations]="mapRelations"
      [focusCountryCode]="focusCountryCode"
    />
  `,
})
class MapHostComponent {
  articles: Article[] = [];
  countries: CountrySummary[] = [];
  mapSummary: import('../../models/map-summary.model').MapSummaryRow[] = [];
  mapRelations: import('../../models/map-relation.model').MapRelationRow[] = [];
  focusCountryCode: string | null = null;
}

describe('RadarMapComponent (Phase 4)', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    installLeafletStub();
    (window as any).L.polyline = (points: any, options: any) => {
      const events = new Map<string, Array<(e?: unknown) => void>>();
      const p = new (window as any).L.Path();
      p.options = options || {};
      p._latlngs = points;
      p.getLatLngs = () => p._latlngs;
      p.bindTooltip = vi.fn().mockReturnThis();
      p.addTo = vi.fn().mockReturnThis();
      p.bringToFront = vi.fn().mockReturnThis();
      p.setStyle = (style: Record<string, unknown>) => {
        p.options = { ...p.options, ...style };
        return p;
      };
      p.on = (event: string, handler: (e?: unknown) => void) => {
        const list = events.get(event) ?? [];
        list.push(handler);
        events.set(event, list);
        return p;
      };
      p.fire = (event: string, payload?: unknown) => {
        for (const handler of events.get(event) ?? []) {
          handler(payload);
        }
      };
      return p;
    };
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
    vi.stubGlobal('cancelAnimationFrame', () => undefined);

    await TestBed.configureTestingModule({
      imports: [MapHostComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    vi.unstubAllGlobals();
    TestBed.resetTestingModule();
    installLeafletStub();
  });

  function flushGeoJson(): void {
    const geoReqs = httpMock.match((req) => req.url.includes('countries.geo.json'));
    expect(geoReqs.length).toBeGreaterThan(0);
    geoReqs.forEach((req) => req.flush(EMPTY_GEOJSON));
  }

  function getMapCmp(fixture: {
    debugElement: { children: { componentInstance: unknown }[] };
  }): RadarMapComponent {
    return fixture.debugElement.children[0].componentInstance as RadarMapComponent;
  }

  it('does not create executable DOM from a malicious article title', async () => {
    const malicious = '"><img src=x onerror="window.__xss=1">';
    const arts = [makeArticle({ id: 1, title: malicious, primary_category: 'Energia' })];
    const countries: CountrySummary[] = [
      { country_code: 'DE', categories: ['Energia'], article_count: 1 },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.articles = arts;
    fixture.componentInstance.countries = countries;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s?: unknown[]) => void;
      }
    ).updateMapData(arts, countries, []);

    const energia = (
      mapCmp as unknown as { categoryClusterGroups: Map<string, StubClusterGroup> }
    ).categoryClusterGroups.get('Energia');
    expect(energia).toBeTruthy();
    const real = energia!
      .getLayers()
      .find((m) => m && typeof m === 'object' && 'articleData' in (m as object)) as {
      _icon: HTMLElement;
      options: { icon?: { html?: unknown } };
    };
    expect(real).toBeTruthy();
    const htmlOpt = real.options.icon?.html;
    expect(htmlOpt).toBeInstanceOf(HTMLElement);
    const el = htmlOpt as HTMLElement;
    expect(el.querySelector('img')).toBeNull();
    expect(el.title).toBe(malicious);
    expect((window as unknown as { __xss?: number }).__xss).toBeUndefined();
  });

  it('cancels GeoJSON work and removes the map on destroy', async () => {
    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    expect(mapInstance._removed).toBe(false);

    fixture.destroy();
    expect(mapInstance._removed).toBe(true);
    expect((mapCmp as unknown as { destroyed: boolean }).destroyed).toBe(true);
  });

  it('updates .marker-read without clearLayers and preserves spiderfy', async () => {
    const arts = [
      makeArticle({ id: 1, title: 'A', primary_category: 'Energia', is_read: false }),
      makeArticle({ id: 2, title: 'B', primary_category: 'Energia', is_read: false }),
    ];
    const countries: CountrySummary[] = [
      { country_code: 'DE', categories: ['Energia'], article_count: 2 },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.articles = arts;
    fixture.componentInstance.countries = countries;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s?: unknown[]) => void;
      }
    ).updateMapData(arts, countries, []);

    const groups = (mapCmp as unknown as { categoryClusterGroups: Map<string, StubClusterGroup> })
      .categoryClusterGroups;
    const energia = groups.get('Energia')!;
    const clearSpy = vi.spyOn(energia, 'clearLayers');

    // Simulate open spiderfy
    energia._spiderfied = { unspiderfy: vi.fn() };

    // Same geometry, flip is_read via effect path
    arts[0].is_read = true;
    fixture.componentInstance.articles = [...arts];
    fixture.detectChanges();
    await fixture.whenStable();

    // Drive the same fingerprint path explicitly
    (mapCmp as unknown as { syncMarkerReadState: (a: Article[]) => void }).syncMarkerReadState(
      arts,
    );

    expect(clearSpy).not.toHaveBeenCalled();
    expect(energia._spiderfied).toBeTruthy();

    const marker = energia.getLayers().find((m) => {
      const mm = m as { articleData?: Article; isDummy?: boolean };
      return mm.articleData?.id === 1;
    }) as { _icon: HTMLElement; articleData: Article };

    expect(marker.articleData.is_read).toBe(true);
    expect(marker._icon.classList.contains('marker-read')).toBe(true);
  });

  it('converges rapid read toggles on marker class via sync only', async () => {
    const arts = [makeArticle({ id: 9, title: 'Toggle', is_read: false })];
    const countries: CountrySummary[] = [
      { country_code: 'DE', categories: ['Energia'], article_count: 1 },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.articles = arts;
    fixture.componentInstance.countries = countries;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s?: unknown[]) => void;
      }
    ).updateMapData(arts, countries, []);

    const sync = (
      mapCmp as unknown as { syncMarkerReadState: (a: Article[]) => void }
    ).syncMarkerReadState.bind(mapCmp);

    arts[0].is_read = true;
    sync(arts);
    arts[0].is_read = false;
    sync(arts);
    arts[0].is_read = true;
    sync(arts);

    const energia = (
      mapCmp as unknown as { categoryClusterGroups: Map<string, StubClusterGroup> }
    ).categoryClusterGroups.get('Energia')!;
    const marker = energia.getLayers().find((m) => {
      const mm = m as { articleData?: Article };
      return mm.articleData?.id === 9;
    }) as { _icon: HTMLElement; articleData: Article };

    expect(marker.articleData.is_read).toBe(true);
    expect(marker._icon.classList.contains('marker-read')).toBe(true);
  });

  it('invalidateSize does not call setView when camera is unchanged', async () => {
    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    const setViewSpy = vi.spyOn(mapInstance, 'setView');

    mapCmp.invalidateSize();

    expect(setViewSpy).not.toHaveBeenCalled();
  });

  it('flushes deferred geometry after navigation ends', async () => {
    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const applySpy = vi.spyOn(
      mapCmp as unknown as {
        applyGeometryInputs: (a: Article[], c: CountrySummary[], s: unknown[]) => void;
      },
      'applyGeometryInputs',
    );

    (mapCmp as unknown as { isNavigating: boolean }).isNavigating = true;
    (mapCmp as unknown as { pendingGeometryRefresh: boolean }).pendingGeometryRefresh = true;

    (mapCmp as unknown as { finishNavigating: () => void }).finishNavigating();

    expect((mapCmp as unknown as { isNavigating: boolean }).isNavigating).toBe(false);
    expect((mapCmp as unknown as { pendingGeometryRefresh: boolean }).pendingGeometryRefresh).toBe(
      false,
    );
    expect(applySpy).toHaveBeenCalledTimes(1);
  });

  it('updateMapData bumps spiderfyGeneration and refreshes clusters', async () => {
    const arts = [makeArticle({ id: 1, title: 'A', primary_category: 'Energia' })];
    const countries: CountrySummary[] = [
      { country_code: 'DE', categories: ['Energia'], article_count: 1 },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const beforeGen = (mapCmp as unknown as { spiderfyGeneration: number }).spiderfyGeneration;
    const energia = (
      mapCmp as unknown as { categoryClusterGroups: Map<string, StubClusterGroup> }
    ).categoryClusterGroups.get('Energia')!;
    const refreshSpy = vi.spyOn(energia, 'refreshClusters');

    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s?: unknown[]) => void;
      }
    ).updateMapData(arts, countries, []);

    expect(
      (mapCmp as unknown as { spiderfyGeneration: number }).spiderfyGeneration,
    ).toBeGreaterThan(beforeGen);
    expect(refreshSpy).toHaveBeenCalled();
    expect(energia.getLayers().length).toBeGreaterThan(0);
  });

  it('focusAndSpiderfyCountry expands the first category group for the nation', async () => {
    const arts = [
      makeArticle({ id: 1, title: 'E', primary_category: 'Energia', country_code: 'DE' }),
      makeArticle({ id: 2, title: 'T', primary_category: 'Tecnologia', country_code: 'DE' }),
    ];
    const countries: CountrySummary[] = [
      { country_code: 'DE', categories: ['Energia', 'Tecnologia'], article_count: 2 },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s?: unknown[]) => void;
      }
    ).updateMapData(arts, countries, []);

    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    mapInstance.setView([51, 13], 5);

    const spiderfyRoot = vi.spyOn(
      mapCmp as unknown as {
        spiderfyAndCreateRoot: (...args: unknown[]) => boolean;
      },
      'spiderfyAndCreateRoot',
    );

    mapCmp.focusAndSpiderfyCountry('DE');

    // Only one category (first found), not all.
    expect(spiderfyRoot).toHaveBeenCalledTimes(1);
  });

  it('spiderfyAndCreateRoot expands every real marker (no hard cap / parking)', async () => {
    const arts = Array.from({ length: 30 }, (_, i) =>
      makeArticle({
        id: i + 1,
        title: `E${i}`,
        primary_category: 'Energia',
        country_code: 'DE',
      }),
    );
    const countries: CountrySummary[] = [
      { country_code: 'DE', categories: ['Energia'], article_count: 30 },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.articles = arts;
    fixture.componentInstance.countries = countries;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s?: unknown[]) => void;
      }
    ).updateMapData(arts, countries, []);

    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    mapInstance.setView([51, 13], 6);

    mapCmp.focusAndSpiderfyCategory('DE', 'Energia');

    const energia = (
      mapCmp as unknown as { categoryClusterGroups: Map<string, { getLayers: () => unknown[] }> }
    ).categoryClusterGroups.get('Energia')!;
    const real = energia.getLayers().filter((m) => {
      const am = m as { isDummy?: boolean; articleData?: Article };
      return !am.isDummy && !!am.articleData;
    });
    expect(real.length).toBe(30);

    const roots = (mapCmp as unknown as { activeRootMarkers: unknown[] }).activeRootMarkers;
    expect(roots.length).toBeGreaterThanOrEqual(1);
  });

  it('restores nation hub when spiderfy cannot find a parent cluster', async () => {
    const arts = [
      makeArticle({ id: 1, title: 'E', primary_category: 'Energia', country_code: 'DE' }),
    ];
    const countries: CountrySummary[] = [
      { country_code: 'DE', categories: ['Energia'], article_count: 1 },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.articles = arts;
    fixture.componentInstance.countries = countries;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s?: unknown[]) => void;
      }
    ).updateMapData(arts, countries, []);

    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    mapInstance.setView([51, 13], 6);

    vi.spyOn(
      mapCmp as unknown as { spiderfyAndCreateRoot: (...args: unknown[]) => boolean },
      'spiderfyAndCreateRoot',
    ).mockReturnValue(false);

    mapCmp.focusAndSpiderfyCategory('DE', 'Energia');

    const hub = (mapCmp as unknown as { detailHubGroup: { getLayers: () => unknown[] } | null })
      .detailHubGroup;
    expect(hub?.getLayers().length ?? 0).toBeGreaterThanOrEqual(1);
  });

  it('day view places one country pin (not per-category balls) at the centroid', async () => {
    const summary = [
      {
        country_code: 'BE',
        primary_category: 'Economia' as const,
        article_count: 3,
        read_count: 0,
        latitude: 50.85,
        longitude: 4.35,
      },
      {
        country_code: 'BE',
        primary_category: 'Tecnologia' as const,
        article_count: 2,
        read_count: 0,
        latitude: 50.85,
        longitude: 4.35,
      },
      {
        country_code: 'FR',
        primary_category: 'Geopolitica' as const,
        article_count: 4,
        read_count: 1,
        latitude: 46.2,
        longitude: 2.2,
      },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s?: unknown[]) => void;
      }
    ).updateMapData([], [], summary);

    const group = (mapCmp as unknown as { summaryMarkerGroup: { getLayers(): unknown[] } })
      .summaryMarkerGroup;
    expect(group.getLayers().length).toBe(2);
  });

  it('draws relations layer with polylines when mapRelations is provided', async () => {
    const summary = [
      {
        country_code: 'DE',
        primary_category: 'Energia' as const,
        article_count: 1,
        read_count: 0,
        latitude: 51.05,
        longitude: 13.73,
      },
      {
        country_code: 'IT',
        primary_category: 'Energia' as const,
        article_count: 1,
        read_count: 0,
        latitude: 41.87,
        longitude: 12.56,
      },
    ];
    const relations = [
      {
        source_country: 'DE',
        target_country: 'IT',
        primary_category: 'Energia' as const,
        volume: 1,
      },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.mapSummary = summary;
    fixture.componentInstance.mapRelations = relations;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s: unknown[], r: unknown[]) => void;
      }
    ).updateMapData([], [], summary, relations);

    const group = (mapCmp as unknown as { relationsLayerGroup: { getLayers(): unknown[] } })
      .relationsLayerGroup;
    // Tratteggio geometrico: più segmenti solidi per un solo arco
    expect(group.getLayers().length).toBeGreaterThanOrEqual(1);
  });

  it('draws macro multicolor relations curve when zoom is < 5', async () => {
    const summary = [
      {
        country_code: 'DE',
        primary_category: 'Energia' as const,
        article_count: 1,
        read_count: 0,
        latitude: 51.05,
        longitude: 13.73,
      },
      {
        country_code: 'IT',
        primary_category: 'Energia' as const,
        article_count: 1,
        read_count: 0,
        latitude: 41.87,
        longitude: 12.56,
      },
    ];
    const relations = [
      {
        source_country: 'DE',
        target_country: 'IT',
        primary_category: 'Energia' as const,
        volume: 2,
      },
      {
        source_country: 'DE',
        target_country: 'IT',
        primary_category: 'Tecnologia' as const,
        volume: 3,
      },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.mapSummary = summary;
    fixture.componentInstance.mapRelations = relations;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    mapInstance.setView([45, 10], 3);

    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s: unknown[], r: unknown[]) => void;
      }
    ).updateMapData([], [], summary, relations);

    const group = (
      mapCmp as unknown as {
        relationsLayerGroup: { getLayers(): { options: { color: string; className: string } }[] };
      }
    ).relationsLayerGroup;

    expect(group.getLayers().length).toBe(3);
    expect(
      group.getLayers().filter((l) => l.options.className === 'relational-arc-flow--macro').length,
    ).toBe(2);
    expect(
      group.getLayers().filter((l) => l.options.className === 'relational-arc-hit').length,
    ).toBe(1);
  });

  it('draws parallel per-category arcs at pin zoom when pair has multiple categories', async () => {
    const summary = [
      {
        country_code: 'CN',
        primary_category: 'Economia' as const,
        article_count: 2,
        read_count: 0,
        latitude: 35.86,
        longitude: 104.2,
      },
      {
        country_code: 'IT',
        primary_category: 'Economia' as const,
        article_count: 2,
        read_count: 0,
        latitude: 41.87,
        longitude: 12.56,
      },
    ];
    const relations = [
      {
        source_country: 'CN',
        target_country: 'IT',
        primary_category: 'Economia' as const,
        volume: 2,
      },
      {
        source_country: 'CN',
        target_country: 'IT',
        primary_category: 'Energia' as const,
        volume: 1,
      },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.mapSummary = summary;
    fixture.componentInstance.mapRelations = relations;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    mapInstance.setView([45, 10], 5);

    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s: unknown[], r: unknown[]) => void;
      }
    ).updateMapData([], [], summary, relations);

    const group = (
      mapCmp as unknown as {
        relationsLayerGroup: {
          getLayers(): {
            options: { className: string; color: string; dashArray?: string };
            getLatLngs(): { lat: number; lng: number }[];
          }[];
        };
      }
    ).relationsLayerGroup;

    const layers = group.getLayers();
    // 2 categorie × tratti geometrici + 1 hit-area per arco
    expect(layers.length).toBeGreaterThanOrEqual(22);
    const visual = layers.filter((l) => l.options.className === 'relational-arc-flow');
    const hits = layers.filter((l) => l.options.className === 'relational-arc-hit');
    expect(visual.length).toBeGreaterThanOrEqual(20);
    expect(hits.length).toBe(2);
    expect(visual.every((l) => !l.options.dashArray)).toBe(true);

    const midA = visual[0].getLatLngs()[1];
    const midB = visual[Math.floor(visual.length / 2)].getLatLngs()[1];
    // Offset curvatura: tratti della 2ª categoria non coincidono con la 1ª
    expect(midA.lat !== midB.lat || midA.lng !== midB.lng).toBe(true);
  });

  it('emits relationClicked without category on macro arc hit click', async () => {
    const summary = [
      {
        country_code: 'DE',
        primary_category: 'Energia' as const,
        article_count: 1,
        read_count: 0,
        latitude: 51.05,
        longitude: 13.73,
      },
      {
        country_code: 'IT',
        primary_category: 'Tecnologia' as const,
        article_count: 1,
        read_count: 0,
        latitude: 41.87,
        longitude: 12.56,
      },
    ];
    const relations = [
      {
        source_country: 'DE',
        target_country: 'IT',
        primary_category: 'Energia' as const,
        volume: 2,
      },
      {
        source_country: 'DE',
        target_country: 'IT',
        primary_category: 'Tecnologia' as const,
        volume: 3,
      },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.mapSummary = summary;
    fixture.componentInstance.mapRelations = relations;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    mapInstance.setView([45, 10], 3);

    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s: unknown[], r: unknown[]) => void;
      }
    ).updateMapData([], [], summary, relations);

    const emitted: unknown[] = [];
    mapCmp.relationClicked.subscribe((v) => emitted.push(v));

    const group = (
      mapCmp as unknown as {
        relationsLayerGroup: {
          getLayers(): { options: { className: string }; fire: (e: string, p?: unknown) => void }[];
        };
      }
    ).relationsLayerGroup;
    const hit = group.getLayers().find((l) => l.options.className === 'relational-arc-hit');
    expect(hit).toBeTruthy();
    hit!.fire('click', { originalEvent: {} });

    expect(emitted).toEqual([{ sourceCountry: 'DE', targetCountry: 'IT' }]);
  });

  it('emits relationClicked with category on pin-zoom arc hit click', async () => {
    const summary = [
      {
        country_code: 'CN',
        primary_category: 'Infrastrutture' as const,
        article_count: 1,
        read_count: 0,
        latitude: 35.86,
        longitude: 104.2,
      },
      {
        country_code: 'IT',
        primary_category: 'Infrastrutture' as const,
        article_count: 1,
        read_count: 0,
        latitude: 41.87,
        longitude: 12.56,
      },
    ];
    const relations = [
      {
        source_country: 'CN',
        target_country: 'IT',
        primary_category: 'Infrastrutture' as const,
        volume: 2,
      },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.mapSummary = summary;
    fixture.componentInstance.mapRelations = relations;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    mapInstance.setView([45, 10], 5);

    (
      mapCmp as unknown as {
        updateMapData: (a: Article[], c: CountrySummary[], s: unknown[], r: unknown[]) => void;
      }
    ).updateMapData([], [], summary, relations);

    const emitted: unknown[] = [];
    mapCmp.relationClicked.subscribe((v) => emitted.push(v));

    const group = (
      mapCmp as unknown as {
        relationsLayerGroup: {
          getLayers(): { options: { className: string }; fire: (e: string, p?: unknown) => void }[];
        };
      }
    ).relationsLayerGroup;
    const hit = group.getLayers().find((l) => l.options.className === 'relational-arc-hit');
    expect(hit).toBeTruthy();
    hit!.fire('click', { originalEvent: {} });

    expect(emitted).toEqual([
      {
        sourceCountry: 'CN',
        targetCountry: 'IT',
        category: 'Infrastrutture',
      },
    ]);
  });

  it('emits countryClicked on map click at zoom < 5 over a hatched nation (canvas bypass)', async () => {
    const countries: CountrySummary[] = [
      { country_code: 'DE', categories: ['Energia'], article_count: 2 },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.countries = countries;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    mapInstance.setView([50.5, 10.5], 3);
    mapInstance.fire('zoomend');

    const emitted: unknown[] = [];
    mapCmp.countryClicked.subscribe((v) => emitted.push(v));

    mapInstance.fire('click', {
      latlng: { lat: 50.5, lng: 10.5 },
      originalEvent: {},
    });

    expect(emitted).toEqual([{ countryCode: 'DE' }]);
  });

  it('does not emit countryClicked on map click at zoom >= 5 over a nation', async () => {
    const countries: CountrySummary[] = [
      { country_code: 'DE', categories: ['Energia'], article_count: 2 },
    ];

    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.componentInstance.countries = countries;
    fixture.detectChanges();
    flushGeoJson();
    await fixture.whenStable();

    const mapCmp = getMapCmp(fixture);
    const mapInstance = (mapCmp as unknown as { map: StubMap }).map;
    mapInstance.setView([50.5, 10.5], 6);
    mapInstance.fire('zoomend');

    const emitted: unknown[] = [];
    mapCmp.countryClicked.subscribe((v) => emitted.push(v));

    mapInstance.fire('click', {
      latlng: { lat: 50.5, lng: 10.5 },
      originalEvent: {},
    });

    expect(emitted).toEqual([]);
  });
});
