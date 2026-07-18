import { Injectable, inject, signal, computed, NgZone, DestroyRef } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';
import { ArticleService } from './article.service';
import { Article, ArticleFilters, CountrySummary, PrimaryCategory } from '../models/article.model';
import { MapSummaryRow } from '../models/map-summary.model';
import { MOCK_MODE } from './mock-mode.token';

export interface ArticleProcessedEvent {
  article_id: number;
  country_code: string;
  primary_category: string;
  published_at: string;
}

export type SidebarMode = 'nation' | 'saved';

/**
 * Stato Signals condiviso: map-summary day-view + saved vault + detail + read/save.
 *
 * Mutazioni ``is_read`` / ``is_saved`` preservano le reference oggetto detenute
 * dal carosello; l'array viene sostituito per rinfrescare i computed.
 *
 * @see SoT: radar/.ecc/rules/frontend.md §2b (detailError); skill radar-sidebar-freeze.
 */
@Injectable({ providedIn: 'root' })
export class StateService {
  private readonly articleService = inject(ArticleService);
  private readonly zone = inject(NgZone);
  private readonly destroyRef = inject(DestroyRef);
  private readonly mockMode = inject(MOCK_MODE);
  private eventSource: EventSource | null = null;

  readonly pendingReadIds = new Set<number>();
  readonly pendingSaveIds = new Set<number>();

  /** Ultimo evento SSE (null = nessuno). Consumato da App effect. */
  readonly lastProcessedArticleEvent = signal<ArticleProcessedEvent | null>(null);

  constructor() {
    if (!this.mockMode) {
      this.initRealTimeConnection();
    }
    this.destroyRef.onDestroy(() => this.closeRealTimeConnection());
  }

  private initRealTimeConnection(): void {
    if (typeof EventSource === 'undefined') {
      console.warn('[StateService] EventSource non definita (ad es. ambiente Node/SSR).');
      return;
    }
    this.zone.runOutsideAngular(() => {
      const es = new EventSource('/api/articles/events');
      this.eventSource = es;
      es.addEventListener('article_processed', (evt: Event) => {
        const msg = evt as MessageEvent<string>;
        let data: ArticleProcessedEvent;
        try {
          data = JSON.parse(msg.data) as ArticleProcessedEvent;
        } catch {
          console.error('[StateService] SSE payload non JSON:', msg.data);
          return;
        }
        this.zone.run(() => {
          this.lastProcessedArticleEvent.set(data);
          this.mapSummaryResource.reload();
          this.savedSummaryResource.reload();
        });
      });
      es.onerror = () => {
        console.warn('[StateService] SSE connection error (browser will retry).');
      };
    });
  }

  private closeRealTimeConnection(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  /** Contatore per-articolo: solo l'ultima toggle può applicare risposta/rollback. */
  private readonly readMutationVersion = new Map<number, number>();
  private readonly saveMutationVersion = new Map<number, number>();

  readonly filters = signal<ArticleFilters>({
    date: new Date().toISOString().split('T')[0],
    sentiment: [],
    categories: [],
  });

  /** Articoli nazione/salvati per sidebar + marker detail (vuoto in day-view). */
  readonly detailArticles = signal<Article[]>([]);
  readonly detailLoading = signal(false);

  /** Modalità sidebar: nation (day) vs saved (cross-day vault). */
  readonly sidebarMode = signal<SidebarMode>('nation');

  /** Day-view: `GET /api/map-summary` in base a data (+ sentiment selezionati, OR). */
  readonly mapSummaryResource = rxResource({
    params: () => {
      const f = this.filters();
      const sentiment =
        f.sentiment && f.sentiment.length > 0 ? f.sentiment : undefined;
      return { date: f.date, sentiment };
    },
    stream: (p) =>
      this.articleService.getMapSummary({
        date: p.params.date,
        sentiment: p.params.sentiment ?? null,
      }),
  });

  /** Vault salvati: `GET /api/saved-summary` (no date; sentiment OR). */
  readonly savedSummaryResource = rxResource({
    params: () => {
      const f = this.filters();
      const sentiment =
        f.sentiment && f.sentiment.length > 0 ? f.sentiment : undefined;
      return { sentiment };
    },
    stream: (p) =>
      this.articleService.getSavedSummary({
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

  /** Righe saved-summary con filtro categoria client-side. */
  readonly filteredSavedSummary = computed((): MapSummaryRow[] => {
    const raw = this.savedSummaryResource.value() ?? [];
    const cats = this.filters().categories;
    if (!cats || cats.length === 0) return raw;
    return raw.filter((row) => cats.includes(row.primary_category));
  });

  /** Rollup paesi da ``filteredSummary`` (categorie, count, read). */
  readonly countries = computed((): CountrySummary[] => {
    return this.rollupCountries(this.filteredSummary());
  });

  /** Rollup paesi salvati da ``filteredSavedSummary``. */
  readonly savedCountries = computed((): CountrySummary[] => {
    return this.rollupCountries(this.filteredSavedSummary());
  });

  readonly articleCount = computed(() =>
    this.filteredSummary().reduce((sum, row) => sum + row.article_count, 0),
  );

  readonly readCount = computed(() =>
    this.filteredSummary().reduce((sum, row) => sum + row.read_count, 0),
  );

  readonly savedCount = computed(() =>
    this.filteredSavedSummary().reduce((sum, row) => sum + row.article_count, 0),
  );

  /**
   * Alias della lista detail (sidebar / test). Vuoto finché non si apre una nazione.
   * Day-view non carica più un dump ``Article[]`` globale.
   */
  readonly articles = computed(() => this.detailArticles());

  readonly isLoading = computed(
    () =>
      this.mapSummaryResource.isLoading() ||
      this.savedSummaryResource.isLoading() ||
      this.detailLoading(),
  );

  /**
   * Errore nation-fetch (T-P1-04). Su fallimento ``App.closeSidebar(false)`` lo lascia
   * visibile nel banner; close utente lo azzera.
   */
  readonly detailError = signal<unknown>(null);

  /** Errore UI: summary / saved-summary oppure detail (banner toolbar). */
  readonly error = computed(
    () =>
      this.mapSummaryResource.error() ??
      this.savedSummaryResource.error() ??
      this.detailError(),
  );

  private rollupCountries(rows: MapSummaryRow[]): CountrySummary[] {
    const grouped = new Map<string, { cats: Set<PrimaryCategory>; count: number; read: number }>();

    for (const row of rows) {
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
  }

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
    this.sidebarMode.set('nation');
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
    this.sidebarMode.set('nation');
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

  /**
   * Carica articoli salvati per country (cross-day), filtri client-side toolbar.
   */
  async loadSavedCountryArticles(countryCode: string): Promise<Article[]> {
    const f = this.filters();
    this.sidebarMode.set('saved');
    this.detailLoading.set(true);
    this.detailError.set(null);
    try {
      const all = await firstValueFrom(
        this.articleService.getAllSavedArticlesForCountry(countryCode.toUpperCase()),
      );
      const filtered = all.filter((art) => this.matchesClientFilters(art, f));
      this.detailArticles.set(filtered);
      return filtered;
    } catch (err) {
      console.error('[StateService] Impossibile caricare articoli salvati:', err);
      this.detailArticles.set([]);
      this.detailError.set(err);
      throw err;
    } finally {
      this.detailLoading.set(false);
    }
  }

  /**
   * Soft-merge lista nazione/salvati: preserva reference Article esistenti
   * e flag ottimistici se mutazione in-flight (sidebar freeze / no flicker).
   */
  mergeDetailArticlesFromServer(serverArticles: Article[]): Article[] {
    const prev = this.detailArticles();
    const prevById = new Map(prev.map((a) => [a.id, a]));
    const merged: Article[] = [];

    for (const incoming of serverArticles) {
      const existing = prevById.get(incoming.id);
      if (!existing) {
        merged.push(incoming);
        continue;
      }
      const pendingRead = this.pendingReadIds.has(incoming.id);
      const pendingSave = this.pendingSaveIds.has(incoming.id);

      existing.title = incoming.title;
      existing.summary = incoming.summary;
      existing.primary_category = incoming.primary_category;
      existing.sentiment = incoming.sentiment;
      existing.relevance_level = incoming.relevance_level;
      existing.country_code = incoming.country_code;
      existing.latitude = incoming.latitude;
      existing.longitude = incoming.longitude;
      existing.published_at = incoming.published_at;
      existing.source_url = incoming.source_url;
      existing.feed_title = incoming.feed_title;
      if (!pendingRead) {
        existing.is_read = incoming.is_read;
      }
      if (!pendingSave) {
        existing.is_saved = incoming.is_saved;
      }
      merged.push(existing);
    }

    this.detailArticles.set(merged);
    return merged;
  }

  async softReloadCountryArticles(countryCode: string): Promise<Article[]> {
    const f = this.filters();
    const all = await firstValueFrom(
      this.articleService.getAllArticlesForCountry(f.date, countryCode.toUpperCase()),
    );
    const filtered = all.filter((art) => this.matchesClientFilters(art, f));
    return this.mergeDetailArticlesFromServer(filtered);
  }

  async softReloadSavedCountryArticles(countryCode: string): Promise<Article[]> {
    const f = this.filters();
    const all = await firstValueFrom(
      this.articleService.getAllSavedArticlesForCountry(countryCode.toUpperCase()),
    );
    const filtered = all.filter((art) => this.matchesClientFilters(art, f));
    return this.mergeDetailArticlesFromServer(filtered);
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
   * Unread ⇒ anche ``is_saved=false`` (coupling server + locale).
   *
   * @param articleId Articolo da sincronizzare con la PATCH API.
   * @param isRead Stato ottimistico richiesto dall'utente (o auto-read da App).
   * @see SoT: radar-sidebar-freeze; frontend.md §2b.
   */
  toggleReadStatus(articleId: number, isRead: boolean): void {
    this.pendingReadIds.add(articleId);
    const version = (this.readMutationVersion.get(articleId) ?? 0) + 1;
    this.readMutationVersion.set(articleId, version);

    const target = this.detailArticles().find((a) => a.id === articleId);
    const prevRead = !!target?.is_read;
    const prevSaved = !!target?.is_saved;

    this.detailArticles.update((arts) => {
      return arts.map((a) => {
        if (a.id !== articleId) return a;
        a.is_read = isRead;
        if (!isRead) a.is_saved = false;
        return a;
      });
    });

    if (target) {
      this.patchSummaryReadCount(target.country_code, target.primary_category, prevRead, isRead);
      if (!isRead && prevSaved) {
        this.patchSavedSummaryCount(target.country_code, target.primary_category, true, false);
      }
    }

    this.articleService.updateReadStatus(articleId, isRead).subscribe({
      next: (res) => {
        this.pendingReadIds.delete(articleId);
        if (this.readMutationVersion.get(articleId) !== version) return;
        const art = this.detailArticles().find((a) => a.id === articleId);
        const beforeRead = !!art?.is_read;
        const beforeSaved = !!art?.is_saved;
        const nextSaved =
          res.is_saved !== undefined ? res.is_saved : !isRead ? false : beforeSaved;
        this.detailArticles.update((arts) => {
          return arts.map((a) => {
            if (a.id !== articleId) return a;
            a.is_read = res.is_read;
            if (res.is_saved !== undefined) a.is_saved = res.is_saved;
            else if (!res.is_read) a.is_saved = false;
            return a;
          });
        });
        if (art && beforeRead !== res.is_read) {
          this.patchSummaryReadCount(art.country_code, art.primary_category, beforeRead, res.is_read);
        }
        if (art && beforeSaved !== nextSaved) {
          this.patchSavedSummaryCount(
            art.country_code,
            art.primary_category,
            beforeSaved,
            nextSaved,
          );
        }
      },
      error: (err) => {
        this.pendingReadIds.delete(articleId);
        console.error('[StateService] Impossibile aggiornare lo stato letto/non letto:', err);
        if (this.readMutationVersion.get(articleId) !== version) return;
        const art = this.detailArticles().find((a) => a.id === articleId);
        const beforeRead = !!art?.is_read;
        const beforeSaved = !!art?.is_saved;
        this.detailArticles.update((arts) => {
          return arts.map((a) => {
            if (a.id !== articleId) return a;
            a.is_read = prevRead;
            a.is_saved = prevSaved;
            return a;
          });
        });
        if (art) {
          this.patchSummaryReadCount(art.country_code, art.primary_category, beforeRead, prevRead);
          this.patchSavedSummaryCount(
            art.country_code,
            art.primary_category,
            beforeSaved,
            prevSaved,
          );
        }
      },
    });
  }

  /**
   * Toggle ``is_saved`` ottimistico + patch saved-summary counts.
   * Save ⇒ anche ``is_read=true`` (coupling). Unsave non forza unread.
   */
  toggleSavedStatus(articleId: number, isSaved: boolean): void {
    this.pendingSaveIds.add(articleId);
    const version = (this.saveMutationVersion.get(articleId) ?? 0) + 1;
    this.saveMutationVersion.set(articleId, version);

    const target = this.detailArticles().find((a) => a.id === articleId);
    const prevSaved = !!target?.is_saved;
    const prevRead = !!target?.is_read;

    this.detailArticles.update((arts) => {
      return arts.map((a) => {
        if (a.id !== articleId) return a;
        a.is_saved = isSaved;
        if (isSaved) a.is_read = true;
        return a;
      });
    });

    if (target) {
      this.patchSavedSummaryCount(target.country_code, target.primary_category, prevSaved, isSaved);
      if (isSaved) {
        this.patchSummaryReadCount(target.country_code, target.primary_category, prevRead, true);
      }
    }

    this.articleService.updateSavedStatus(articleId, isSaved).subscribe({
      next: (res) => {
        this.pendingSaveIds.delete(articleId);
        if (this.saveMutationVersion.get(articleId) !== version) return;
        const art = this.detailArticles().find((a) => a.id === articleId);
        const beforeSaved = !!art?.is_saved;
        const beforeRead = !!art?.is_read;
        const nextRead =
          res.is_read !== undefined ? res.is_read : res.is_saved ? true : beforeRead;
        this.detailArticles.update((arts) => {
          return arts.map((a) => {
            if (a.id !== articleId) return a;
            a.is_saved = res.is_saved;
            if (res.is_read !== undefined) a.is_read = res.is_read;
            else if (res.is_saved) a.is_read = true;
            return a;
          });
        });
        if (art && beforeSaved !== res.is_saved) {
          this.patchSavedSummaryCount(
            art.country_code,
            art.primary_category,
            beforeSaved,
            res.is_saved,
          );
        }
        if (art && beforeRead !== nextRead) {
          this.patchSummaryReadCount(art.country_code, art.primary_category, beforeRead, nextRead);
        }
      },
      error: (err) => {
        this.pendingSaveIds.delete(articleId);
        console.error('[StateService] Impossibile aggiornare lo stato salvato:', err);
        if (this.saveMutationVersion.get(articleId) !== version) return;
        const art = this.detailArticles().find((a) => a.id === articleId);
        const beforeSaved = !!art?.is_saved;
        const beforeRead = !!art?.is_read;
        this.detailArticles.update((arts) => {
          return arts.map((a) => {
            if (a.id !== articleId) return a;
            a.is_saved = prevSaved;
            a.is_read = prevRead;
            return a;
          });
        });
        if (art) {
          this.patchSavedSummaryCount(
            art.country_code,
            art.primary_category,
            beforeSaved,
            prevSaved,
          );
          this.patchSummaryReadCount(art.country_code, art.primary_category, beforeRead, prevRead);
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

  /**
   * Aggiorna ``article_count`` sul saved-summary (delta ±1). Crea riga se save
   * su country×category assente; rimuove riga se count scende a 0.
   */
  private patchSavedSummaryCount(
    countryCode: string,
    category: PrimaryCategory,
    wasSaved: boolean,
    nowSaved: boolean,
  ): void {
    if (wasSaved === nowSaved) return;
    const delta = nowSaved ? 1 : -1;
    this.savedSummaryResource.value.update((rows) => {
      const list = rows ? [...rows] : [];
      const idx = list.findIndex(
        (row) => row.country_code === countryCode && row.primary_category === category,
      );
      if (idx >= 0) {
        const row = list[idx];
        const nextCount = Math.max(0, row.article_count + delta);
        if (nextCount === 0) {
          list.splice(idx, 1);
        } else {
          list[idx] = {
            ...row,
            article_count: nextCount,
            read_count: Math.min(row.read_count, nextCount),
          };
        }
        return list;
      }
      if (delta > 0) {
        list.push({
          country_code: countryCode,
          primary_category: category,
          article_count: 1,
          read_count: 0,
          latitude: 0,
          longitude: 0,
        });
      }
      return list;
    });
  }
}
