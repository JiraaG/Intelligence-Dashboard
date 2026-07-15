import { Injectable, inject, signal, computed } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { ArticleService } from './article.service';
import { ArticleFilters, CountrySummary, PrimaryCategory } from '../models/article.model';

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

  readonly articlesResource = rxResource({
    params: () => ({ date: this.filters().date }),
    stream: (p) => this.articleService.getArticles({ date: p.params.date }),
  });

  readonly articles = computed(() => {
    const raw = this.articlesResource.value() ?? [];
    const activeFilters = this.filters();

    return raw.filter((art) => {
      if (activeFilters.sentiment && activeFilters.sentiment.length > 0) {
        if (!activeFilters.sentiment.includes(art.sentiment)) {
          return false;
        }
      }

      if (activeFilters.categories && activeFilters.categories.length > 0) {
        if (!activeFilters.categories.includes(art.primary_category)) {
          return false;
        }
      }

      return true;
    });
  });

  readonly countries = computed(() => {
    const arts = this.articles();
    const grouped = new Map<string, { cats: Set<string>; count: number }>();

    for (const a of arts) {
      const entry = grouped.get(a.country_code) ?? { cats: new Set<string>(), count: 0 };
      entry.cats.add(a.primary_category);
      entry.count++;
      grouped.set(a.country_code, entry);
    }

    const result: CountrySummary[] = [];
    grouped.forEach((v, k) => {
      result.push({
        country_code: k,
        categories: Array.from(v.cats) as PrimaryCategory[],
        article_count: v.count,
      });
    });
    return result;
  });

  readonly isLoading = computed(() => this.articlesResource.isLoading());
  readonly error = computed(() => this.articlesResource.error());

  /**
   * Hybrid update for sidebar freeze compatibility:
   * mutate `is_read` on the existing object (sidebar holds the same refs) and
   * return a new array so toolbar computed signals refresh.
   */
  toggleReadStatus(articleId: number, isRead: boolean): void {
    const version = (this.readMutationVersion.get(articleId) ?? 0) + 1;
    this.readMutationVersion.set(articleId, version);

    this.articlesResource.value.update((arts) => {
      if (!arts) return arts;
      return arts.map((a) => {
        if (a.id !== articleId) return a;
        a.is_read = isRead;
        return a;
      });
    });

    this.articleService.updateReadStatus(articleId, isRead).subscribe({
      next: (res) => {
        if (this.readMutationVersion.get(articleId) !== version) return;
        this.articlesResource.value.update((arts) => {
          if (!arts) return arts;
          return arts.map((a) => {
            if (a.id !== articleId) return a;
            a.is_read = res.is_read;
            return a;
          });
        });
      },
      error: (err) => {
        console.error('[StateService] Impossibile aggiornare lo stato letto/non letto:', err);
        if (this.readMutationVersion.get(articleId) !== version) return;
        this.articlesResource.value.update((arts) => {
          if (!arts) return arts;
          return arts.map((a) => {
            if (a.id !== articleId) return a;
            a.is_read = !isRead;
            return a;
          });
        });
      },
    });
  }
}
