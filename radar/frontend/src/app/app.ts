import { Component, computed, inject, signal, viewChild, HostListener } from '@angular/core';
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
  readonly state = inject(StateService);

  selectedArticle  = signal<Article | null>(null);
  clusterArticles  = signal<Article[]>([]);
  isSidebarOpen    = signal<boolean>(false);
  focusCountryCode = signal<string | null>(null);

  readonly mapComponent = viewChild(RadarMapComponent);

  articleCount = computed(() => this.state.articles().length);
  isMapSplit   = computed(() => this.isSidebarOpen());

  @HostListener('window:resize')
  onWindowResize(): void {
    this.mapComponent()?.invalidateSize();
  }

  private scheduleInvalidateSize(): void {
    // After CSS transition / layout — overlay full-bleed still needs Leaflet resize.
    requestAnimationFrame(() => {
      this.mapComponent()?.invalidateSize();
      setTimeout(() => this.mapComponent()?.invalidateSize(), 360);
    });
  }

  onFiltersChange(f: ArticleFilters): void {
    this.closeSidebar();
    this.focusCountryCode.set(null);
    this.state.filters.set(f);
  }

  onMarkerClick(article: Article): void {
    this.selectedArticle.set(article);
    this.clusterArticles.set([article]);
    this.isSidebarOpen.set(true);
    this.scheduleInvalidateSize();
  }

  onClusterClick(articles: Article[]): void {
    if (!articles || articles.length === 0) {
      this.closeSidebar();
      return;
    }
    this.selectedArticle.set(articles[0]);
    this.clusterArticles.set(articles);
    this.isSidebarOpen.set(true);
    this.scheduleInvalidateSize();
  }

  onCountryClick(articles: Article[]): void {
    if (articles.length > 0) {
      this.selectedArticle.set(articles[0]);
      this.clusterArticles.set(articles);
      this.isSidebarOpen.set(true);
      this.focusCountryCode.set(articles[0].country_code);
      this.scheduleInvalidateSize();
    }
  }

  onToolbarCountrySelect(countryCode: string): void {
    const countryArts = this.state.articles().filter(a => a.country_code === countryCode);
    if (countryArts.length > 0) {
      this.selectedArticle.set(countryArts[0]);
      this.clusterArticles.set(countryArts);
      this.isSidebarOpen.set(true);
      this.scheduleInvalidateSize();
    }
    this.focusCountryCode.set(countryCode);
  }

  closeSidebar(): void {
    this.isSidebarOpen.set(false);
    this.selectedArticle.set(null);
    this.clusterArticles.set([]);
    this.focusCountryCode.set(null);
    this.mapComponent()?.collapseAllGraphs();
    this.scheduleInvalidateSize();
  }

  onSidebarCategoryClick(category: string): void {
    const code = this.focusCountryCode();
    if (code) {
      this.mapComponent()?.focusAndSpiderfyCategory(code, category);
    } else {
      const arts = this.clusterArticles();
      if (arts.length > 0 && arts[0].country_code) {
        this.mapComponent()?.focusAndSpiderfyCategory(arts[0].country_code, category);
      }
    }
  }

  onActiveArticleChanged(article: Article | null): void {
    this.mapComponent()?.highlightMarkerForArticle(article);
  }
}
