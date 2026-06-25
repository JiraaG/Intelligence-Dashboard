import { Injectable, inject, signal, computed } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { ArticleService } from './article.service';
import { ArticleFilters, CountrySummary } from '../models/article.model';

@Injectable({ providedIn: 'root' })
export class StateService {
  private readonly articleService = inject(ArticleService);

  // Filtri centralizzati come Signal
  readonly filters = signal<ArticleFilters>({
    date: new Date().toISOString().split('T')[0],
    sentiment: [],
    categories: []
  });

  // Resource per gli articoli (ri-esegue la chiamata HTTP solo quando cambia la data)
  readonly articlesResource = rxResource({
    params: () => ({ date: this.filters().date }),
    stream: (p) => this.articleService.getArticles({ date: p.params.date })
  });

  // Segnale degli articoli filtrati client-side in tempo reale (multiscelta)
  readonly articles = computed(() => {
    const raw = this.articlesResource.value() ?? [];
    const activeFilters = this.filters();

    return raw.filter(art => {
      // Filtro sentiment multiplo (se vuoto, lascia passare tutto)
      if (activeFilters.sentiment && activeFilters.sentiment.length > 0) {
        if (!activeFilters.sentiment.includes(art.sentiment)) {
          return false;
        }
      }

      // Filtro categorie multiplo (se vuoto, lascia passare tutto)
      if (activeFilters.categories && activeFilters.categories.length > 0) {
        if (!activeFilters.categories.includes(art.primary_category)) {
          return false;
        }
      }

      return true;
    });
  });

  // Calcolo dinamico e reattivo dei sommari nazionali in base agli articoli filtrati correnti
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
        categories: Array.from(v.cats) as any[],
        article_count: v.count
      });
    });
    return result;
  });

  readonly isLoading = computed(() => this.articlesResource.isLoading());
  readonly error = computed(() => this.articlesResource.error());
}

