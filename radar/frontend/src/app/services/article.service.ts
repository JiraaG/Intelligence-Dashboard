import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { EMPTY, Observable, expand, map, of, reduce } from 'rxjs';
import {
  Article,
  ArticleFilters,
  ArticlesPage,
  ArticlesPageFilters,
  CountrySummary,
  Sentiment,
} from '../models/article.model';
import { MapSummaryRow } from '../models/map-summary.model';
import { MapRelationRow } from '../models/map-relation.model';
import { MetricsSummary, MetricsStatus } from '../models/metrics.model';
import { parseArticlesPageDto, parseMapSummaryDto, parseMapRelationsDto, parseMetricsSummaryDto, parseMetricsStatusDto } from '../models/article.dto';
import { ArticleMockService } from './article-mock.service';
import { MOCK_MODE } from './mock-mode.token';

export interface ReadStatusResponse {
  status: string;
  is_read: boolean;
  is_saved?: boolean;
}

export interface SavedStatusResponse {
  status: string;
  is_saved: boolean;
  is_read?: boolean;
}

const DEFAULT_PAGE_LIMIT = 50;
const MAX_PAGE_LIMIT = 100;

/**
 * Confine HTTP articoli / map-summary / saved-summary.
 *
 * Switch mock **solo** via token ``MOCK_MODE`` (inject). Se false, errori HTTP
 * restano errori — **nessun** fallback silenzioso a ``ArticleMockService``.
 * Pagine: clamp 1…100; nation/saved open concatena keyset fino a ``next_cursor`` null.
 *
 * @see radar-api-contract; docs/03; frontend rule §2b; spatial-data-mocking.
 */
@Injectable({ providedIn: 'root' })
export class ArticleService {
  private readonly http = inject(HttpClient);
  private readonly mock = inject(ArticleMockService);
  private readonly mockMode = inject(MOCK_MODE);

  /**
   * Day view: ``GET /api/map-summary`` (o mock aggregato).
   * Sentiment multiplo: query ripetuta ``sentiment=`` (OR lato API).
   */
  getMapSummary(filters: {
    date: string;
    sentiment?: Sentiment | Sentiment[] | null;
  }): Observable<MapSummaryRow[]> {
    if (this.mockMode) {
      return this.mock.getMapSummary(filters.date, filters.sentiment ?? undefined);
    }
    let params = new HttpParams().set('date', filters.date);
    const sentiments = Array.isArray(filters.sentiment)
      ? filters.sentiment
      : filters.sentiment
        ? [filters.sentiment]
        : [];
    for (const s of sentiments) {
      params = params.append('sentiment', s);
    }
    return this.http.get<unknown>('/api/map-summary', { params }).pipe(
      map((payload) => parseMapSummaryDto(payload)),
    );
  }

  /**
   * Day view relations: ``GET /api/map-relations`` (o mock derivato).
   * Sentiment multiplo: query ripetuta ``sentiment=`` (OR lato API).
   */
  getMapRelations(filters: {
    date: string;
    sentiment?: Sentiment | Sentiment[] | null;
  }): Observable<MapRelationRow[]> {
    if (this.mockMode) {
      return this.mock.getMapRelations(filters.date, filters.sentiment ?? undefined);
    }
    let params = new HttpParams().set('date', filters.date);
    const sentiments = Array.isArray(filters.sentiment)
      ? filters.sentiment
      : filters.sentiment
        ? [filters.sentiment]
        : [];
    for (const s of sentiments) {
      params = params.append('sentiment', s);
    }
    return this.http.get<unknown>('/api/map-relations', { params }).pipe(
      map((payload) => parseMapRelationsDto(payload)),
    );
  }

  /**
   * Vault salvati: ``GET /api/saved-summary`` (no date).
   * Sentiment multiplo: query ripetuta ``sentiment=`` (OR lato API).
   */
  getSavedSummary(filters: {
    sentiment?: Sentiment | Sentiment[] | null;
  } = {}): Observable<MapSummaryRow[]> {
    if (this.mockMode) {
      return this.mock.getSavedSummary(filters.sentiment ?? undefined);
    }
    let params = new HttpParams();
    const sentiments = Array.isArray(filters.sentiment)
      ? filters.sentiment
      : filters.sentiment
        ? [filters.sentiment]
        : [];
    for (const s of sentiments) {
      params = params.append('sentiment', s);
    }
    return this.http.get<unknown>('/api/saved-summary', { params }).pipe(
      map((payload) => parseMapSummaryDto(payload)),
    );
  }

  /**
   * Una pagina envelope ``{ items, next_cursor, total }`` (limit clampato ≤100).
   * Con ``saved=true`` omette ``date``.
   */
  getArticlesPage(filters: ArticlesPageFilters): Observable<ArticlesPage> {
    const limit = Math.min(Math.max(filters.limit ?? DEFAULT_PAGE_LIMIT, 1), MAX_PAGE_LIMIT);
    if (this.mockMode) {
      return this.mock.getArticlesPage({ ...filters, limit });
    }
    let params = new HttpParams().set('limit', String(limit));
    if (filters.saved) {
      params = params.set('saved', 'true');
    } else if (filters.date) {
      params = params.set('date', filters.date);
    }
    if (filters.country) params = params.set('country', filters.country);
    if (filters.category) params = params.set('category', filters.category);
    if (filters.sentiment) params = params.set('sentiment', filters.sentiment);
    if (filters.relevance_level != null) {
      params = params.set('relevance_level', String(filters.relevance_level));
    }
    if (filters.cursor != null) params = params.set('cursor', String(filters.cursor));
    return this.http.get<unknown>('/api/articles', { params }).pipe(
      map((payload) => parseArticlesPageDto(payload)),
    );
  }

  /**
   * Concatena pagine keyset finché ``next_cursor`` è null
   * (nation open — carosello completo, page size = MAX 100).
   */
  getAllArticlesForCountry(
    date: string,
    country: string,
    extra: Omit<ArticlesPageFilters, 'date' | 'country' | 'cursor' | 'limit' | 'saved'> = {},
  ): Observable<Article[]> {
    const limit = MAX_PAGE_LIMIT;
    return this.getArticlesPage({ date, country, limit, ...extra }).pipe(
      expand((page) =>
        page.next_cursor != null
          ? this.getArticlesPage({ date, country, limit, cursor: page.next_cursor, ...extra })
          : EMPTY,
      ),
      reduce((acc, page) => acc.concat(page.items), [] as Article[]),
    );
  }

  /**
   * Concatena pagine salvate per country (no date), page size = MAX 100.
   */
  getAllSavedArticlesForCountry(
    country: string,
    extra: Omit<ArticlesPageFilters, 'date' | 'country' | 'cursor' | 'limit' | 'saved'> = {},
  ): Observable<Article[]> {
    const limit = MAX_PAGE_LIMIT;
    return this.getArticlesPage({ saved: true, country, limit, ...extra }).pipe(
      expand((page) =>
        page.next_cursor != null
          ? this.getArticlesPage({
              saved: true,
              country,
              limit,
              cursor: page.next_cursor,
              ...extra,
            })
          : EMPTY,
      ),
      reduce((acc, page) => acc.concat(page.items), [] as Article[]),
    );
  }

  /** @deprecated Preferire ``getMapSummary``; tenuto per caller legacy ``/api/countries``. */
  getCountries(filters: ArticleFilters): Observable<CountrySummary[]> {
    if (this.mockMode) {
      return this.mock.getCountries(filters.date);
    }
    const params = new HttpParams().set('date', filters.date);
    return this.http.get<CountrySummary[]>('/api/countries', { params });
  }

  /** PATCH read-status; in mock risponde ``of(...)`` senza HTTP. */
  updateReadStatus(articleId: number, isRead: boolean): Observable<ReadStatusResponse> {
    if (this.mockMode) {
      return of({
        status: 'success',
        is_read: isRead,
        ...(isRead ? {} : { is_saved: false }),
      });
    }
    return this.http.patch<ReadStatusResponse>(
      `/api/articles/${articleId}/read_status`,
      { is_read: isRead },
    );
  }

  /** PATCH saved-status; save ⇒ is_read=true. In mock risponde ``of(...)`` senza HTTP. */
  updateSavedStatus(articleId: number, isSaved: boolean): Observable<SavedStatusResponse> {
    if (this.mockMode) {
      return of({
        status: 'success',
        is_saved: isSaved,
        ...(isSaved ? { is_read: true } : {}),
      });
    }
    return this.http.patch<SavedStatusResponse>(
      `/api/articles/${articleId}/saved_status`,
      { is_saved: isSaved },
    );
  }

  getMetricsSummary(filters: { from?: string; to?: string } = {}): Observable<MetricsSummary> {
    if (this.mockMode) {
      return this.mock.getMetricsSummary(filters.from, filters.to);
    }
    let params = new HttpParams();
    if (filters.from) params = params.set('from', filters.from);
    if (filters.to) params = params.set('to', filters.to);
    return this.http.get<unknown>('/api/metrics/summary', { params }).pipe(
      map((payload) => parseMetricsSummaryDto(payload)),
    );
  }

  getMetricsStatus(): Observable<MetricsStatus> {
    if (this.mockMode) {
      return this.mock.getMetricsStatus();
    }
    return this.http.get<unknown>('/api/metrics/status').pipe(
      map((payload) => parseMetricsStatusDto(payload)),
    );
  }
}
