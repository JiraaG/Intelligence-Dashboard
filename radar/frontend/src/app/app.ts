import { Component, computed, inject, signal, viewChild, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { StateService } from './services/state.service';
import { Article, ArticleFilters, PrimaryCategory } from './models/article.model';
import {
  CountryOpenRequest,
  RadarMapComponent,
} from './components/radar-map/radar-map.component';
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

  articleCount = computed(() => this.state.articleCount());
  readCount    = computed(() => this.state.readCount());
  isMapSplit   = computed(() => this.isSidebarOpen());

  /** Ignore stale nation-fetch results when the user clicks another pallino quickly. */
  private nationOpenGeneration = 0;
  /** Skip collapse/spiderfy when carousel only changes article within the same category. */
  private lastSpiderfyKey: string | null = null;

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

  async onCountryClick(req: CountryOpenRequest | string): Promise<void> {
    const open: CountryOpenRequest =
      typeof req === 'string' ? { countryCode: req } : req;
    if (!open.countryCode) return;

    const gen = ++this.nationOpenGeneration;

    try {
      const arts = await this.state.loadCountryArticles(open.countryCode);
      if (gen !== this.nationOpenGeneration) return;

      if (arts.length === 0) {
        this.closeSidebar();
        this.focusCountryCode.set(open.countryCode);
        return;
      }

      const category = open.category;
      const sidebarArts = category
        ? arts.filter((a) => a.primary_category === category)
        : arts;
      const focusList = sidebarArts.length > 0 ? sidebarArts : arts;
      // Match sidebar carousel order (sort by category) so spiderfy tracks the visible card.
      const displayArticle =
        (category
          ? arts.find((a) => a.primary_category === category)
          : undefined) ??
        [...focusList].sort((a, b) =>
          a.primary_category.localeCompare(b.primary_category),
        )[0] ??
        focusList[0];

      this.selectedArticle.set(displayArticle);
      // Category pallino → carousel on that category only; polygon/toolbar → full nation.
      this.clusterArticles.set(focusList);
      this.isSidebarOpen.set(true);
      // Skip fitBounds maxZoom 4 (hides markers via zoom-out-mode). Spiderfy path
      // flyTo zoom 6 when needed so icons expand for the active category.
      this.mapComponent()?.armSkipCountryFit();
      this.focusCountryCode.set(open.countryCode);

      // Spiderfy only the category of the article on screen (not every category).
      this.scheduleCategorySpiderfy(open.countryCode, displayArticle.primary_category);
    } catch {
      if (gen !== this.nationOpenGeneration) return;
      this.closeSidebar();
    }
  }

  /**
   * After detail markers replace summary balls: resize map, then spiderfy.
   * Order matters — invalidateSize must not run after spiderfy.
   */
  private scheduleCategorySpiderfy(countryCode: string, category: PrimaryCategory): void {
    this.lastSpiderfyKey = `${countryCode}|${category}`;
    requestAnimationFrame(() => {
      this.mapComponent()?.invalidateSize();
      setTimeout(() => {
        this.mapComponent()?.invalidateSize();
        this.mapComponent()?.focusAndSpiderfyCategory(countryCode, category);
      }, 320);
    });
  }

  async onToolbarCountrySelect(countryCode: string): Promise<void> {
    await this.onCountryClick({ countryCode });
  }

  closeSidebar(): void {
    this.nationOpenGeneration++;
    this.lastSpiderfyKey = null;
    this.isSidebarOpen.set(false);
    this.selectedArticle.set(null);
    this.clusterArticles.set([]);
    this.focusCountryCode.set(null);
    this.state.clearDetailArticles();
    this.mapComponent()?.collapseAllGraphs();
    this.scheduleInvalidateSize();
  }

  onSidebarCategoryClick(category: string): void {
    const code = this.focusCountryCode();
    const country = code || this.clusterArticles()[0]?.country_code;
    if (!country) return;
    this.lastSpiderfyKey = `${country}|${category}`;
    this.mapComponent()?.focusAndSpiderfyCategory(country, category);
  }

  onActiveArticleChanged(article: Article | null): void {
    this.mapComponent()?.highlightMarkerForArticle(article);
    // Carousel (or single-card) focus: auto-mark as read; manual toggle in sidebar still works.
    if (article && !article.is_read) {
      this.state.toggleReadStatus(article.id, true);
    }
    // Spiderfy only when the visible category changes — not on every carousel slide.
    if (!article?.country_code || !article.primary_category) return;
    const countryCode = this.focusCountryCode() ?? article.country_code;
    const spiderKey = `${countryCode}|${article.primary_category}`;
    if (spiderKey === this.lastSpiderfyKey) return;
    this.lastSpiderfyKey = spiderKey;
    this.mapComponent()?.focusAndSpiderfyCategory(countryCode, article.primary_category);
  }
}
