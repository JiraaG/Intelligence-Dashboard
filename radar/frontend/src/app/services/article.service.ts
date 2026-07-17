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
import { parseArticlesPageDto, parseMapSummaryDto } from '../models/article.dto';
import { ArticleMockService } from './article-mock.service';
import { MOCK_MODE } from './mock-mode.token';

export interface ReadStatusResponse {
  status: string;
  is_read: boolean;
}

const DEFAULT_PAGE_LIMIT = 50;
const MAX_PAGE_LIMIT = 100;

/**
 * Confine HTTP articoli / map-summary.
 *
 * Switch mock **solo** via token ``MOCK_MODE`` (inject). Se false, errori HTTP
 * restano errori — **nessun** fallback silenzioso a ``ArticleMockService``.
 * Pagine: clamp 1…100; nation open concatena keyset fino a ``next_cursor`` null.
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
   * Sentiment multiplo: API accetta un solo valore — se array length≠1, omesso.
   */
  getMapSummary(filters: {
    date: string;
    sentiment?: Sentiment | Sentiment[] | null;
  }): Observable<MapSummaryRow[]> {
    if (this.mockMode) {
      return this.mock.getMapSummary(filters.date, filters.sentiment ?? undefined);
    }
    let params = new HttpParams().set('date', filters.date);
    const singleSentiment = Array.isArray(filters.sentiment)
      ? (filters.sentiment.length === 1 ? filters.sentiment[0] : undefined)
      : filters.sentiment ?? undefined;
    if (singleSentiment) {
      params = params.set('sentiment', singleSentiment);
    }
    return this.http.get<unknown>('/api/map-summary', { params }).pipe(
      map((payload) => parseMapSummaryDto(payload)),
    );
  }

  /**
   * Una pagina envelope ``{ items, next_cursor, total }`` (limit clampato ≤100).
   */
  getArticlesPage(filters: ArticlesPageFilters): Observable<ArticlesPage> {
    const limit = Math.min(Math.max(filters.limit ?? DEFAULT_PAGE_LIMIT, 1), MAX_PAGE_LIMIT);
    if (this.mockMode) {
      return this.mock.getArticlesPage({ ...filters, limit });
    }
    let params = new HttpParams().set('date', filters.date).set('limit', String(limit));
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
    extra: Omit<ArticlesPageFilters, 'date' | 'country' | 'cursor' | 'limit'> = {},
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
      return of({ status: 'success', is_read: isRead });
    }
    return this.http.patch<ReadStatusResponse>(
      `/api/articles/${articleId}/read_status`,
      { is_read: isRead },
    );
  }
}
