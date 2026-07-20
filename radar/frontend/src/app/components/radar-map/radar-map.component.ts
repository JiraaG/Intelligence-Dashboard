import { Component, viewChild, input, output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Article, CountrySummary } from '../../models/article.model';
import { MapSummaryRow } from '../../models/map-summary.model';
import { MapRelationRow } from '../../models/map-relation.model';
import { MAP_RENDERER } from '../../services/map-renderer.token';
import { CountryOpenRequest, RelationOpenRequest } from './radar-map.types';
import { RadarMapMaplibreComponent } from './maplibre/radar-map-maplibre.component';
import { RadarMapLeafletComponent } from './leaflet/radar-map-leaflet.component';

export type { CountryOpenRequest, RelationOpenRequest } from './radar-map.types';

/**
 * Facade mappa Radar: monta MapLibre (default) o Leaflet legacy via ``MAP_RENDERER``.
 * Stesso contratto Input/Output/metodi pubblici usato da App.
 */
@Component({
  selector: 'app-radar-map',
  standalone: true,
  imports: [CommonModule, RadarMapMaplibreComponent, RadarMapLeafletComponent],
  templateUrl: './radar-map.component.html',
  styleUrl: './radar-map.component.scss',
})
export class RadarMapComponent {
  readonly renderer = inject(MAP_RENDERER);

  private readonly maplibreHost = viewChild(RadarMapMaplibreComponent);
  private readonly leafletHost = viewChild(RadarMapLeafletComponent);

  articles = input.required<Article[]>();
  countries = input.required<CountrySummary[]>();
  mapSummary = input<MapSummaryRow[]>([]);
  mapRelations = input<MapRelationRow[]>([]);
  focusCountryCode = input<string | null>(null);

  markerClicked = output<Article>();
  clusterClicked = output<Article[]>();
  countryClicked = output<CountryOpenRequest>();
  relationClicked = output<RelationOpenRequest>();

  private activeHost(): RadarMapMaplibreComponent | RadarMapLeafletComponent | undefined {
    return this.renderer === 'leaflet' ? this.leafletHost() : this.maplibreHost();
  }

  public invalidateSize(): void {
    this.activeHost()?.invalidateSize();
  }

  public focusAndSpiderfyCategory(countryCode: string, category: string): void {
    this.activeHost()?.focusAndSpiderfyCategory(countryCode, category);
  }

  public armSkipCountryFit(): void {
    this.activeHost()?.armSkipCountryFit();
  }

  public refocusCountry(code: string): void {
    this.activeHost()?.refocusCountry(code);
  }

  public collapseAllGraphs(emitClose: boolean = false, restoreHub: boolean = true): void {
    this.activeHost()?.collapseAllGraphs(emitClose, restoreHub);
  }

  public highlightMarkerForArticle(article: Article | null): void {
    this.activeHost()?.highlightMarkerForArticle(article);
  }

  public focusAndSpiderfyCountry(countryCode: string): void {
    this.activeHost()?.focusAndSpiderfyCountry(countryCode);
  }
}
