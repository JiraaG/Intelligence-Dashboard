import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Article, CountrySummary, ArticleFilters } from '../models/article.model';
import { ArticleMockService } from './article-mock.service';

// Segnale globale esportato per riflettere lo stato del fallback offline (USE_MOCK = true)
export const useMockSignal = signal<boolean>(false);

@Injectable({ providedIn: 'root' })
export class ArticleService {
  private readonly http = inject(HttpClient);
  private readonly mock = inject(ArticleMockService);

  getArticles(filters: ArticleFilters): Observable<Article[]> {
    if (useMockSignal()) {
      return this.mock.getArticles(filters.date);
    }
    const params = new HttpParams().set('date', filters.date);
    return this.http.get<Article[]>('/api/articles', { params }).pipe(
      catchError((err) => {
        console.warn('[ArticleService] Errore API backend. Attivazione auto-fallback sui dati mock:', err);
        useMockSignal.set(true);
        return this.mock.getArticles(filters.date);
      })
    );
  }

  getCountries(filters: ArticleFilters): Observable<CountrySummary[]> {
    if (useMockSignal()) {
      return this.mock.getCountries(filters.date);
    }
    const params = new HttpParams().set('date', filters.date);
    return this.http.get<CountrySummary[]>('/api/countries', { params }).pipe(
      catchError((err) => {
        console.warn('[ArticleService] Errore API backend. Attivazione auto-fallback sui dati mock:', err);
        useMockSignal.set(true);
        return this.mock.getCountries(filters.date);
      })
    );
  }
}
