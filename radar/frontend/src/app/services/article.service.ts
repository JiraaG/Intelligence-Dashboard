import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map, of } from 'rxjs';
import { Article, CountrySummary, ArticleFilters } from '../models/article.model';
import { parseArticlesDto } from '../models/article.dto';
import { ArticleMockService } from './article-mock.service';
import { MOCK_MODE } from './mock-mode.token';

export interface ReadStatusResponse {
  status: string;
  is_read: boolean;
}

@Injectable({ providedIn: 'root' })
export class ArticleService {
  private readonly http = inject(HttpClient);
  private readonly mock = inject(ArticleMockService);
  private readonly mockMode = inject(MOCK_MODE);

  getArticles(filters: ArticleFilters): Observable<Article[]> {
    if (this.mockMode) {
      return this.mock.getArticles(filters.date);
    }
    const params = new HttpParams().set('date', filters.date);
    return this.http.get<unknown>('/api/articles', { params }).pipe(
      map((payload) => parseArticlesDto(payload)),
    );
  }

  getCountries(filters: ArticleFilters): Observable<CountrySummary[]> {
    if (this.mockMode) {
      return this.mock.getCountries(filters.date);
    }
    const params = new HttpParams().set('date', filters.date);
    return this.http.get<CountrySummary[]>('/api/countries', { params });
  }

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
