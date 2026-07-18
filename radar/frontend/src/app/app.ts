import { Component, computed, effect, inject, signal, viewChild, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { StateService } from './services/state.service';
import { Article, ArticleFilters, PrimaryCategory } from './models/article.model';
import {
  CountryOpenRequest,
  RadarMapComponent,
} from './components/radar-map/radar-map.component';
import { RadarToolbarComponent } from './components/radar-toolbar/radar-toolbar.component';
import { RadarSidebarComponent } from './components/radar-sidebar/radar-sidebar.component';

/**
 * Shell UI: mappa + toolbar + sidebar (freeze: importata, mai modificata qui).
 *
 * Coordina nation-open (generation token), ``invalidateSize`` prima di spiderfy,
 * close che può preservare ``detailError``, auto-read sul cambio card carosello.
 *
 * @see SoT: frontend.md §2b/§7; skill radar-sidebar-freeze.
 */
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RadarMapComponent, RadarToolbarComponent, RadarSidebarComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  readonly state = inject(StateService);

  constructor() {
    effect(() => {
      const evt = this.state.lastProcessedArticleEvent();
      if (!evt) return;
      void this.handleProcessedArticle(evt);
    });
  }

  private async handleProcessedArticle(evt: {
    article_id: number;
    country_code: string;
    primary_category: string;
    published_at: string;
  }): Promise<void> {
    if (!this.isSidebarOpen()) {
      return;
    }
    const focus = this.focusCountryCode();
    if (!focus || focus.toUpperCase() !== evt.country_code.toUpperCase()) {
      return;
    }

    const gen = this.nationOpenGeneration;
    try {
      await (
        this.state.sidebarMode() === 'saved'
          ? this.state.softReloadSavedCountryArticles(focus)
          : this.state.softReloadCountryArticles(focus)
      );
      if (gen !== this.nationOpenGeneration) return;

      const detail = this.state.detailArticles();
      const byId = new Map(detail.map((a) => [a.id, a]));
      const incoming = byId.get(evt.article_id);
      if (!incoming) {
        // Articolo filtrato via toolbar (sentiment/categoria): niente salto carosello.
        return;
      }

      // Carosello = tutta la nazione (tutte le categorie); focus sulla card nuova.
      // Spiderfy solo la categoria dell'articolo appena arrivato (icone/colore pin).
      this.selectedArticle.set(incoming);
      this.clusterArticles.set(detail.map((a) => byId.get(a.id) ?? a));
      this.lastSpiderfyKey = null;
      this.scheduleCategorySpiderfy(focus, incoming.primary_category);
    } catch {
      // Soft-refresh fallito: non chiudere sidebar
    }
  }

  selectedArticle  = signal<Article | null>(null);
  clusterArticles  = signal<Article[]>([]);
  isSidebarOpen    = signal<boolean>(false);
  focusCountryCode = signal<string | null>(null);

  readonly mapComponent = viewChild(RadarMapComponent);

  articleCount = computed(() => this.state.articleCount());
  readCount    = computed(() => this.state.readCount());
  savedCount   = computed(() => this.state.savedCount());
  /** Overlay full-bleed: true quando la sidebar è aperta (mappa resta 100vw). */
  isMapSplit   = computed(() => this.isSidebarOpen());

  /** Ignora risultati nation-fetch obsoleti se l'utente cambia pallino in fretta. */
  private nationOpenGeneration = 0;
  /** Evita re-spiderfy a ogni slide carosello nella stessa categoria. */
  private lastSpiderfyKey: string | null = null;

  @HostListener('window:resize')
  onWindowResize(): void {
    this.mapComponent()?.invalidateSize();
  }

  /** Dopo transizione CSS / layout: Leaflet deve ricalcolare size (overlay full-bleed). */
  private scheduleInvalidateSize(): void {
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

  /**
   * Apre nazione: fetch paged → carosello (categoria pallino o full nation) → spiderfy.
   * Fallimento → ``closeSidebar(false)`` (banner ``detailError`` resta).
   *
   * @param req Codice paese oppure ``CountryOpenRequest`` (preserveZoom / category).
   */
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
      // Allinea ordine carosello (sort categoria) così spiderfy segue la card visibile.
      const displayArticle =
        (category
          ? arts.find((a) => a.primary_category === category)
          : undefined) ??
        [...focusList].sort((a, b) =>
          a.primary_category.localeCompare(b.primary_category),
        )[0] ??
        focusList[0];

      this.selectedArticle.set(displayArticle);
      // Pallino categoria → carosello solo quella; poligono/toolbar → nazione intera.
      this.clusterArticles.set(focusList);
      this.isSidebarOpen.set(true);
      // Summary/pallino: tieni camera. Poligono/toolbar: fitBounds sulla nazione.
      if (open.preserveZoom) {
        this.mapComponent()?.armSkipCountryFit();
      } else if (this.focusCountryCode() === open.countryCode) {
        // Stesso codice di nuovo: il signal non ri-emette — forza fitBounds.
        this.mapComponent()?.refocusCountry(open.countryCode);
      }
      this.focusCountryCode.set(open.countryCode);

      // Spiderfy solo la categoria dell'articolo a schermo (non tutte).
      this.scheduleCategorySpiderfy(open.countryCode, displayArticle.primary_category);
    } catch {
      if (gen !== this.nationOpenGeneration) return;
      this.closeSidebar(false);
    }
  }

  /**
   * Dopo i marker detail: resize mappa, poi spiderfy.
   * Ordine obbligatorio — ``invalidateSize`` non deve arrivare dopo spiderfy.
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

  /**
   * Vault salvati: stesso path UI di toolbar LETTE/TROVATE
   * (fitBounds + spiderfy categoria), fetch via ``loadSavedCountryArticles``.
   */
  async onToolbarSavedCountrySelect(countryCode: string): Promise<void> {
    if (!countryCode) return;

    const gen = ++this.nationOpenGeneration;

    try {
      const arts = await this.state.loadSavedCountryArticles(countryCode);
      if (gen !== this.nationOpenGeneration) return;

      if (arts.length === 0) {
        this.closeSidebar();
        this.focusCountryCode.set(countryCode);
        return;
      }

      const displayArticle =
        [...arts].sort((a, b) => a.primary_category.localeCompare(b.primary_category))[0] ??
        arts[0];

      this.selectedArticle.set(displayArticle);
      this.clusterArticles.set(arts);
      this.isSidebarOpen.set(true);
      if (this.focusCountryCode() === countryCode) {
        this.mapComponent()?.refocusCountry(countryCode);
      }
      this.focusCountryCode.set(countryCode);
      this.scheduleCategorySpiderfy(countryCode, displayArticle.primary_category);
    } catch {
      if (gen !== this.nationOpenGeneration) return;
      this.closeSidebar(false);
    }
  }

  /**
   * Chiude sidebar e azzera detail. ``clearError=false`` lascia il banner nation-fetch
   * (T-P1-04); default true per close intenzionale utente.
   */
  closeSidebar(clearError = true): void {
    this.nationOpenGeneration++;
    this.lastSpiderfyKey = null;
    this.isSidebarOpen.set(false);
    this.selectedArticle.set(null);
    this.clusterArticles.set([]);
    this.focusCountryCode.set(null);
    this.state.clearDetailArticles({ clearError });
    this.mapComponent()?.collapseAllGraphs();
    this.scheduleInvalidateSize();
  }

  /** Pill categoria in sidebar → spiderfy quella categoria (senza rifetch). */
  onSidebarCategoryClick(category: string): void {
    const code = this.focusCountryCode();
    const country = code || this.clusterArticles()[0]?.country_code;
    if (!country) return;
    this.lastSpiderfyKey = `${country}|${category}`;
    this.mapComponent()?.focusAndSpiderfyCategory(country, category);
  }

  /**
   * Card attiva carosello: highlight marker + auto-read se non letta.
   * Spiderfy solo al cambio categoria visibile (``lastSpiderfyKey``).
   */
  onActiveArticleChanged(article: Article | null): void {
    this.mapComponent()?.highlightMarkerForArticle(article);
    // Focus carosello / card: auto-mark letta; toggle manuale in sidebar resta.
    if (article && !article.is_read) {
      this.state.toggleReadStatus(article.id, true);
    }
    // Spiderfy solo se cambia la categoria visibile — non a ogni slide.
    if (!article?.country_code || !article.primary_category) return;
    const countryCode = this.focusCountryCode() ?? article.country_code;
    const spiderKey = `${countryCode}|${article.primary_category}`;
    if (spiderKey === this.lastSpiderfyKey) return;
    this.lastSpiderfyKey = spiderKey;
    this.mapComponent()?.focusAndSpiderfyCategory(countryCode, article.primary_category);
  }
}
