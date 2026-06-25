import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { StateService } from './services/state.service';
import { Article, ArticleFilters } from './models/article.model';
import { RadarMapComponent }     from './components/radar-map/radar-map.component';
import { RadarToolbarComponent } from './components/radar-toolbar/radar-toolbar.component';
import { RadarSidebarComponent } from './components/radar-sidebar/radar-sidebar.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RadarMapComponent, RadarToolbarComponent, RadarSidebarComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  // Iniezione dello Store Centralizzato
  readonly state = inject(StateService);

  // Signals per la gestione degli elementi selezionati (sidebar)
  selectedArticle  = signal<Article | null>(null);
  clusterArticles  = signal<Article[]>([]);
  isSidebarOpen    = signal<boolean>(false);
  focusCountryCode = signal<string | null>(null);

  // computed derivati
  articleCount = computed(() => this.state.articles().length);
  isMapSplit   = computed(() => this.isSidebarOpen());

  onFiltersChange(f: ArticleFilters): void {
    this.closeSidebar();
    this.focusCountryCode.set(null);
    this.state.filters.set(f); // Aggiorna i filtri globali → Innesca automaticamente rxResource
  }

  // Click su marker singolo (zoom ≥ 5)
  onMarkerClick(article: Article): void {
    this.selectedArticle.set(article);
    this.clusterArticles.set([article]);
    this.isSidebarOpen.set(true);
  }

  // Click su cluster (zoom ≥ 5)
  onClusterClick(articles: Article[]): void {
    this.selectedArticle.set(articles[0]);
    this.clusterArticles.set(articles);
    this.isSidebarOpen.set(true);
  }

  // Click su nazione (zoom < 5)
  onCountryClick(articles: Article[]): void {
    this.selectedArticle.set(articles[0]);
    this.clusterArticles.set(articles);
    this.isSidebarOpen.set(true);
  }

  // Selezione nazione da toolbar tooltip
  onToolbarCountrySelect(countryCode: string): void {
    const countryArts = this.state.articles().filter(a => a.country_code === countryCode);
    if (countryArts.length > 0) {
      this.selectedArticle.set(countryArts[0]);
      this.clusterArticles.set(countryArts);
      this.isSidebarOpen.set(true);
    }
    this.focusCountryCode.set(countryCode);
  }

  closeSidebar(): void {
    this.isSidebarOpen.set(false);
    this.selectedArticle.set(null);
    this.clusterArticles.set([]);
    this.focusCountryCode.set(null);
  }
}
