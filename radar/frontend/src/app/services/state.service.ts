import { Injectable, inject, signal, computed } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';
import { ArticleService } from './article.service';
import { Article, ArticleFilters, CountrySummary, PrimaryCategory } from '../models/article.model';
import { MapSummaryRow } from '../models/map-summary.model';

@Injectable({ providedIn: 'root' })
export class StateService {
  private readonly articleService = inject(ArticleService);

  /** Per-article mutation counter — only the latest toggle may apply response/rollback. */
  private readonly readMutationVersion = new Map<number, number>();

  readonly filters = signal<ArticleFilters>({
    date: new Date().toISOString().split('T')[0],
    sentiment: [],
    categories: [],
  });

  /** Nation-scoped articles for sidebar + map markers (empty on day view). */
  readonly detailArticles = signal<Article[]>([]);
  readonly detailLoading = signal(false);

  readonly mapSummaryResource = rxResource({
    params: () => {
      const f = this.filters();
      const sentiment = f.sentiment && f.sentiment.length === 1 ? f.sentiment[0] : undefined;
      return { date: f.date, sentiment };
    },
    stream: (p) =>
      this.articleService.getMapSummary({
        date: p.params.date,
        sentiment: p.params.sentiment ?? null,
      }),
  });

  /** Summary rows with client-side category filter applied. */
  readonly filteredSummary = computed((): MapSummaryRow[] => {
    const raw = this.mapSummaryResource.value() ?? [];
    const cats = this.filters().categories;
    if (!cats || cats.length === 0) return raw;
    return raw.filter((row) => cats.includes(row.primary_category));
  });

  readonly countries = computed((): CountrySummary[] => {
    const grouped = new Map<string, { cats: Set<PrimaryCategory>; count: number; read: number }>();

    for (const row of this.filteredSummary()) {
      const entry = grouped.get(row.country_code) ?? {
        cats: new Set<PrimaryCategory>(),
        count: 0,
        read: 0,
      };
      entry.cats.add(row.primary_category);
      entry.count += row.article_count;
      entry.read += row.read_count;
      grouped.set(row.country_code, entry);
    }

    const result: CountrySummary[] = [];
    grouped.forEach((v, k) => {
      result.push({
        country_code: k,
        categories: Array.from(v.cats),
        article_count: v.count,
        read_count: v.read,
      });
    });
    return result;
  });

  readonly articleCount = computed(() =>
    this.filteredSummary().reduce((sum, row) => sum + row.article_count, 0),
  );

  readonly readCount = computed(() =>
    this.filteredSummary().reduce((sum, row) => sum + row.read_count, 0),
  );

  /**
   * Alias for nation detail list (sidebar / tests). Empty until a country is opened.
   * Day view no longer loads a full Article[] dump.
   */
  readonly articles = computed(() => this.detailArticles());

  readonly isLoading = computed(() => this.mapSummaryResource.isLoading() || this.detailLoading());
  readonly detailError = signal<unknown>(null);

  readonly error = computed(() => this.mapSummaryResource.error() ?? this.detailError());

  clearDetailArticles(options?: { clearError?: boolean }): void {
    const clearError = options?.clearError ?? true;
    if (clearError) {
      this.detailError.set(null);
    }
    this.detailArticles.set([]);
    this.detailLoading.set(false);
  }

  /**
   * Load every article for date+country (paginate until next_cursor is null),
   * then apply client-side sentiment/category filters from toolbar.
   */
  async loadCountryArticles(countryCode: string): Promise<Article[]> {
    const f = this.filters();
    this.detailLoading.set(true);
    this.detailError.set(null);
    try {
      const all = await firstValueFrom(
        this.articleService.getAllArticlesForCountry(f.date, countryCode.toUpperCase()),
      );
      const filtered = all.filter((art) => this.matchesClientFilters(art, f));
      this.detailArticles.set(filtered);
      return filtered;
    } catch (err) {
      console.error('[StateService] Impossibile caricare articoli nazione:', err);
      this.detailArticles.set([]);
      this.detailError.set(err);
      throw err;
    } finally {
      this.detailLoading.set(false);
    }
  }

  private matchesClientFilters(art: Article, f: ArticleFilters): boolean {
    if (f.sentiment && f.sentiment.length > 0 && !f.sentiment.includes(art.sentiment)) {
      return false;
    }
    if (f.categories && f.categories.length > 0 && !f.categories.includes(art.primary_category)) {
      return false;
    }
    return true;
  }

  /**
   * Hybrid update for sidebar freeze compatibility:
   * mutate `is_read` on the existing object (sidebar holds the same refs) and
   * return a new array so toolbar computed signals refresh.
   */
  toggleReadStatus(articleId: number, isRead: boolean): void {
    const version = (this.readMutationVersion.get(articleId) ?? 0) + 1;
    this.readMutationVersion.set(articleId, version);

    const target = this.detailArticles().find((a) => a.id === articleId);
    const prevRead = !!target?.is_read;

    this.detailArticles.update((arts) => {
      return arts.map((a) => {
        if (a.id !== articleId) return a;
        a.is_read = isRead;
        return a;
      });
    });

    if (target) {
      this.patchSummaryReadCount(target.country_code, target.primary_category, prevRead, isRead);
    }

    this.articleService.updateReadStatus(articleId, isRead).subscribe({
      next: (res) => {
        if (this.readMutationVersion.get(articleId) !== version) return;
        const art = this.detailArticles().find((a) => a.id === articleId);
        const before = !!art?.is_read;
        this.detailArticles.update((arts) => {
          return arts.map((a) => {
            if (a.id !== articleId) return a;
            a.is_read = res.is_read;
            return a;
          });
        });
        if (art && before !== res.is_read) {
          this.patchSummaryReadCount(art.country_code, art.primary_category, before, res.is_read);
        }
      },
      error: (err) => {
        console.error('[StateService] Impossibile aggiornare lo stato letto/non letto:', err);
        if (this.readMutationVersion.get(articleId) !== version) return;
        const art = this.detailArticles().find((a) => a.id === articleId);
        const before = !!art?.is_read;
        this.detailArticles.update((arts) => {
          return arts.map((a) => {
            if (a.id !== articleId) return a;
            a.is_read = !isRead;
            return a;
          });
        });
        if (art) {
          this.patchSummaryReadCount(art.country_code, art.primary_category, before, !isRead);
        }
      },
    });
  }

  private patchSummaryReadCount(
    countryCode: string,
    category: PrimaryCategory,
    wasRead: boolean,
    nowRead: boolean,
  ): void {
    if (wasRead === nowRead) return;
    const delta = nowRead ? 1 : -1;
    this.mapSummaryResource.value.update((rows) => {
      if (!rows) return rows;
      return rows.map((row) => {
        if (row.country_code !== countryCode || row.primary_category !== category) {
          return row;
        }
        return {
          ...row,
          read_count: Math.max(0, Math.min(row.article_count, row.read_count + delta)),
        };
      });
    });
  }
}
