import { InjectionToken } from '@angular/core';

/**
 * Explicit development/offline mock switch.
 * When true, ArticleService serves ArticleMockService data and never hits the API.
 * When false (default / production), API errors stay visible — no silent mock fallback.
 */
export const MOCK_MODE = new InjectionToken<boolean>('MOCK_MODE', {
  providedIn: 'root',
  factory: () => false,
});
