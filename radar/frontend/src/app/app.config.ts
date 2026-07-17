import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZonelessChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { MOCK_MODE } from './services/mock-mode.token';

/**
 * Providers root Angular (zoneless, HttpClient, animazioni).
 *
 * ``MOCK_MODE: false`` è scelta di **produzione deliberata**: l’app parla con
 * ``/api/*``. Offline/demo → override esplicito ``useValue: true`` (TestBed o
 * config locale). Vietato auto-fallback a mock su errore HTTP.
 *
 * @see docs/03 MOCK_MODE; skill spatial-data-mocking; frontend rule §2b.
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZonelessChangeDetection(),
    provideHttpClient(),
    provideAnimationsAsync(),
    { provide: MOCK_MODE, useValue: false },
  ]
};
