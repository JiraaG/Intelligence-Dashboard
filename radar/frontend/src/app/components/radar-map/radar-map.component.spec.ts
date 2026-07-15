import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Article, CountrySummary } from '../../models/article.model';
import { RadarMapComponent } from './radar-map.component';
import { installLeafletStub, type StubClusterGroup, type StubMap } from '../../testing/leaflet.stub';

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
      [focusCountryCode]="focusCountryCode"
    />
  `,
})
class MapHostComponent {
  articles: Article[] = [];
  countries: CountrySummary[] = [];
  focusCountryCode: string | null = null;
}

describe('RadarMapComponent (Phase 4)', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    installLeafletStub();
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

  function getMapCmp(fixture: { debugElement: { children: { componentInstance: unknown }[] } }): RadarMapComponent {
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
        updateMapData: (a: Article[], c: CountrySummary[]) => void;
      }
    ).updateMapData(arts, countries);

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
        updateMapData: (a: Article[], c: CountrySummary[]) => void;
      }
    ).updateMapData(arts, countries);

    const groups = (
      mapCmp as unknown as { categoryClusterGroups: Map<string, StubClusterGroup> }
    ).categoryClusterGroups;
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
    (
      mapCmp as unknown as { syncMarkerReadState: (a: Article[]) => void }
    ).syncMarkerReadState(arts);

    expect(clearSpy).not.toHaveBeenCalled();
    expect(energia._spiderfied).toBeTruthy();

    const marker = energia
      .getLayers()
      .find((m) => {
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
        updateMapData: (a: Article[], c: CountrySummary[]) => void;
      }
    ).updateMapData(arts, countries);

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
});
