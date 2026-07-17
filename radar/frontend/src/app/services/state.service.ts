import { Injectable, inject, signal, computed } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';
import { ArticleService } from './article.service';
import { Article, ArticleFilters, CountrySummary, PrimaryCategory } from '../models/article.model';
import { MapSummaryRow } from '../models/map-summary.model';

/**
 * Stato Signals condiviso: map-summary day-view + detail nazione + read-status.
 *
 * Non tocca `radar-sidebar/**`: le mutazioni `is_read` preservano le reference
 * oggetto detenute dal carosello; l'array viene sostituito per rinfrescare i computed.
 *
 * @see SoT: radar/.ecc/rules/frontend.md §2b (detailError); skill radar-sidebar-freeze.
 */
@Injectable({ providedIn: 'root' })
export class StateService {
  private readonly articleService = inject(ArticleService);

  /** Contatore per-articolo: solo l'ultima toggle può applicare risposta/rollback. */
  private readonly readMutationVersion = new Map<number, number>();

  readonly filters = signal<ArticleFilters>({
    date: new Date().toISOString().split('T')[0],
    sentiment: [],
    categories: [],
  });

  /** Articoli nazione per sidebar + marker detail (vuoto in day-view). */
  readonly detailArticles = signal<Article[]>([]);
  readonly detailLoading = signal(false);

  /** Day-view: `GET /api/map-summary` in base a data (+ sentiment singolo se selezionato). */
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

  /** Righe summary con filtro categoria client-side (toolbar). */
  readonly filteredSummary = computed((): MapSummaryRow[] => {
    const raw = this.mapSummaryResource.value() ?? [];
    const cats = this.filters().categories;
    if (!cats || cats.length === 0) return raw;
    return raw.filter((row) => cats.includes(row.primary_category));
  });

  /** Rollup paesi da ``filteredSummary`` (categorie, count, read). */
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
   * Alias della lista detail (sidebar / test). Vuoto finché non si apre una nazione.
   * Day-view non carica più un dump ``Article[]`` globale.
   */
  readonly articles = computed(() => this.detailArticles());

  readonly isLoading = computed(() => this.mapSummaryResource.isLoading() || this.detailLoading());

  /**
   * Errore nation-fetch (T-P1-04). Su fallimento ``App.closeSidebar(false)`` lo lascia
   * visibile nel banner; close utente lo azzera.
   */
  readonly detailError = signal<unknown>(null);

  /** Errore UI: summary oppure detail (banner toolbar). */
  readonly error = computed(() => this.mapSummaryResource.error() ?? this.detailError());

  /**
   * Svuota detail nazione. ``clearError: false`` preserva ``detailError`` (fail nation-fetch).
   */
  clearDetailArticles(options?: { clearError?: boolean }): void {
    const clearError = options?.clearError ?? true;
    if (clearError) {
      this.detailError.set(null);
    }
    this.detailArticles.set([]);
    this.detailLoading.set(false);
  }

  /**
   * Carica tutti gli articoli date+country (pagine keyset fino a ``next_cursor`` null),
   * poi applica filtri sentiment/categoria client-side dalla toolbar.
   *
   * @param countryCode Codice ISO Alpha-2 della nazione aperta.
   * @returns Lista filtrata; in catch setta ``detailError`` e rilancia.
   * @see SoT: frontend.md §2b T-P1-04; radar-api-contract.
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

  /** Filtri toolbar applicati in memoria sulla lista nazione già scaricata. */
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
   * Update ibrido compatibile con sidebar freeze: muta ``is_read`` sull'oggetto
   * esistente (stesse ref del carosello) e sostituisce l'array per i signal derivati.
   * Versione per-id: risposte/rollback di toggle obsolete vengono ignorate.
   *
   * @param articleId Articolo da sincronizzare con la PATCH API.
   * @param isRead Stato ottimistico richiesto dall'utente (o auto-read da App).
   * @see SoT: radar-sidebar-freeze; frontend.md §2b.
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

  /**
   * Aggiorna ``read_count`` sulla riga map-summary corrispondente (delta ±1, clamp).
   * Non rebuilda i marker: solo contatori toolbar/pin.
   */
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
