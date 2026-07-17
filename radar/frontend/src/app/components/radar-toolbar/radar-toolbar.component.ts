import { Component, input, output, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CalendarModule } from 'primeng/calendar';
import { MultiSelectModule } from 'primeng/multiselect';
import { ProgressBarModule } from 'primeng/progressbar';
import { ArticleFilters, CountrySummary, Sentiment, PrimaryCategory } from '../../models/article.model';

/**
 * Toolbar filtri giorno: data, sentiment, categorie, lista paesi da day-summary.
 * Non carica ``Article[]`` — solo rollup ``CountrySummary`` + conteggi.
 * Emit ``filtersChange`` / ``countrySelected`` verso App/StateService.
 *
 * @see docs/03; radar-api-contract (day = map-summary).
 */
@Component({
  selector: 'app-radar-toolbar',
  standalone: true,
  imports: [CommonModule, FormsModule, CalendarModule, MultiSelectModule, ProgressBarModule],
  templateUrl: './radar-toolbar.component.html',
  styleUrl: './radar-toolbar.component.scss'
})
export class RadarToolbarComponent {
  /** Rollup day-view (paesi) senza Article[] completo. */
  countries    = input<CountrySummary[]>([]);
  /** Rollup vault salvati (cross-day). */
  savedCountries = input<CountrySummary[]>([]);
  articleCount = input<number>(0);
  readCount    = input<number>(0);
  savedCount   = input<number>(0);
  isLoading    = input<boolean>(false);
  /** Banner errore unificato (map-summary o detailError nation-fetch). */
  apiError     = input<boolean>(false);

  filtersChange   = output<ArticleFilters>();
  countrySelected = output<string>();
  savedCountrySelected = output<string>();

  selectedDate       = signal<Date>(new Date());
  selectedSentiment  = signal<Sentiment[]>([]);
  selectedCategories = signal<PrimaryCategory[]>([]);

  isTooltipHovered = signal<boolean>(false);
  isTooltipClicked = signal<boolean>(false);
  isTooltipVisible = computed(() => (this.isTooltipHovered() || this.isTooltipClicked()) && this.countriesList().length > 0);

  isSavedTooltipHovered = signal<boolean>(false);
  isSavedTooltipClicked = signal<boolean>(false);
  isSavedTooltipVisible = computed(
    () =>
      (this.isSavedTooltipHovered() || this.isSavedTooltipClicked()) &&
      this.savedCountriesList().length > 0,
  );

  toggleTooltip(event: Event): void {
    event.stopPropagation();
    this.isTooltipClicked.update(v => !v);
    this.isSavedTooltipClicked.set(false);
  }

  closeTooltip(event: Event): void {
    event.stopPropagation();
    this.isTooltipClicked.set(false);
    this.isTooltipHovered.set(false);
  }

  toggleSavedTooltip(event: Event): void {
    event.stopPropagation();
    this.isSavedTooltipClicked.update(v => !v);
    this.isTooltipClicked.set(false);
  }

  closeSavedTooltip(event: Event): void {
    event.stopPropagation();
    this.isSavedTooltipClicked.set(false);
    this.isSavedTooltipHovered.set(false);
  }

  selectCountry(countryCode: string, event: Event): void {
    event.stopPropagation();
    this.countrySelected.emit(countryCode);
    this.isTooltipClicked.set(false);
    this.isTooltipHovered.set(false);
  }

  selectSavedCountry(countryCode: string, event: Event): void {
    event.stopPropagation();
    this.savedCountrySelected.emit(countryCode);
    this.isSavedTooltipClicked.set(false);
    this.isSavedTooltipHovered.set(false);
  }

  readonly today = new Date();

  readonly sentimentOptions = [
    { label: '▲ Positivo', value: 'Positivo' },
    { label: '● Neutrale', value: 'Neutrale' },
    { label: '▼ Negativo', value: 'Negativo' },
  ];

  readonly categoryOptions = [
    { label: '☢️ Nucleare', value: 'Nucleare' },
    { label: '⚡ Energia', value: 'Energia' },
    { label: '🏗️ Infrastrutture', value: 'Infrastrutture' },
    { label: '🌍 Geopolitica', value: 'Geopolitica' },
    { label: '📈 Economia', value: 'Economia' },
    { label: '💻 Tecnologia', value: 'Tecnologia' },
    { label: '🚀 Spazio', value: 'Spazio' },
    { label: '🌿 Ambiente', value: 'Ambiente' },
    { label: '⚕️ Salute', value: 'Salute' },
    { label: '🛡️ Sicurezza', value: 'Sicurezza' }
  ];

  /** Nomi IT per ISO comuni; fallback Intl / codice grezzo sotto. */
  readonly COUNTRY_NAMES: Record<string, string> = {
    'IT': 'Italia',
    'DE': 'Germania',
    'FR': 'Francia',
    'ES': 'Spagna',
    'GB': 'Regno Unito',
    'US': 'Stati Uniti',
    'CN': 'Cina',
    'RU': 'Russia',
    'UA': 'Ucraina',
    'IR': 'Iran',
    'KR': 'Corea del Sud',
    'AZ': 'Azerbaigian',
    'JP': 'Giappone',
    'IN': 'India',
    'BR': 'Brasile',
    'SA': 'Arabia Saudita',
    'TW': 'Taiwan',
    'AF': 'Afghanistan',
    'AU': 'Australia',
    'VE': 'Venezuela',
    'PG': 'Papua Nuova Guinea',
    'PK': 'Pakistan',
    'TR': 'Turchia',
    'MX': 'Messico',
    'XX': 'World Wide'
  };

  /**
   * Lista paesi ordinata per conteggio: mappa CODE→nome
   * (tabella / Intl.DisplayNames / codice) + read_count.
   */
  readonly countriesList = computed(() => this.buildCountryList(this.countries()));

  /** Lista nazioni salvate (badge = solo count salvati). */
  readonly savedCountriesList = computed(() => this.buildCountryList(this.savedCountries()));

  private buildCountryList(
    countries: CountrySummary[],
  ): { code: string; name: string; count: number; readCount: number }[] {
    const list: { code: string; name: string; count: number; readCount: number }[] = [];
    for (const c of countries) {
      let name = this.COUNTRY_NAMES[c.country_code];
      if (!name) {
        if (c.country_code === 'XX') {
          name = 'World Wide';
        } else {
          try {
            const displayNames = new Intl.DisplayNames(['it-IT'], { type: 'region' });
            name = displayNames.of(c.country_code) || c.country_code;
          } catch {
            name = c.country_code;
          }
        }
      }
      list.push({
        code: c.country_code,
        name,
        count: c.article_count,
        readCount: c.read_count ?? 0,
      });
    }
    return list.sort((a, b) => b.count - a.count);
  }

  /** Bandiera emoji da ISO-2; ``XX`` → ``WW``; codepoint invalidi → bandiera bianca. */
  getFlagEmoji(countryCode: string): string {
    if (!countryCode || countryCode === 'XX') return 'WW';
    const codePoints = countryCode
      .toUpperCase()
      .split('')
      .map(char => 127397 + char.charCodeAt(0));
    try {
      return String.fromCodePoint(...codePoints);
    } catch {
      return '🏳️';
    }
  }

  /**
   * Data locale → ``YYYY-MM-DD`` (compensa timezone offset).
   * Sentiment/categorie vuoti → ``null`` (filtro assente lato StateService/API).
   */
  onFiltersChange(): void {
    const date = this.selectedDate();
    const offset = date.getTimezoneOffset();
    const localDate = new Date(date.getTime() - (offset * 60 * 1000));
    const dateString = localDate.toISOString().split('T')[0];

    this.filtersChange.emit({
      date:       dateString,
      sentiment:  this.selectedSentiment().length > 0 ? this.selectedSentiment() : null,
      categories: this.selectedCategories().length > 0 ? this.selectedCategories() : null
    });
  }
}
