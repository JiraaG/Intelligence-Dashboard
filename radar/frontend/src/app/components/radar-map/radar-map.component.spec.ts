import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Article, CountrySummary } from '../../models/article.model';
import { MAP_RENDERER } from '../../services/map-renderer.token';
import { RadarMapComponent } from './radar-map.component';
import { RadarMapMaplibreComponent } from './maplibre/radar-map-maplibre.component';

@Component({
  selector: 'app-map-host',
  standalone: true,
  imports: [RadarMapComponent],
  template: `
    <app-radar-map
      [articles]="articles"
      [countries]="countries"
      [mapSummary]="[]"
      [mapRelations]="[]"
      [focusCountryCode]="null"
    />
  `,
})
class MapHostComponent {
  articles: Article[] = [];
  countries: CountrySummary[] = [];
}

describe('RadarMapComponent facade', () => {
  beforeEach(async () => {
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
    await TestBed.configureTestingModule({
      imports: [MapHostComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: MAP_RENDERER, useValue: 'maplibre' as const },
      ],
    }).compileComponents();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    TestBed.resetTestingModule();
  });

  it('defaults to maplibre host when MAP_RENDERER is maplibre', () => {
    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.detectChanges();
    const maplibre = fixture.debugElement.query(
      (el) => el.componentInstance instanceof RadarMapMaplibreComponent,
    );
    expect(maplibre).toBeTruthy();
    const facade = fixture.debugElement.children[0].componentInstance as RadarMapComponent;
    expect(facade.renderer).toBe('maplibre');
  });

  it('exposes public delegation methods', () => {
    const fixture = TestBed.createComponent(MapHostComponent);
    fixture.detectChanges();
    const facade = fixture.debugElement.children[0].componentInstance as RadarMapComponent;
    expect(typeof facade.invalidateSize).toBe('function');
    expect(typeof facade.focusAndSpiderfyCategory).toBe('function');
    expect(typeof facade.armSkipCountryFit).toBe('function');
    expect(typeof facade.refocusCountry).toBe('function');
    expect(typeof facade.collapseAllGraphs).toBe('function');
    expect(typeof facade.highlightMarkerForArticle).toBe('function');
    expect(typeof facade.focusAndSpiderfyCountry).toBe('function');
  });
});
