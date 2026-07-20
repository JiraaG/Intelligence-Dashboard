import { Component, input, output, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CalendarModule } from 'primeng/calendar';
import { MultiSelectModule } from 'primeng/multiselect';
import { ProgressBarModule } from 'primeng/progressbar';
import {
  ArticleFilters,
  CountrySummary,
  Sentiment,
  PrimaryCategory,
} from '../../models/article.model';
import { StateService } from '../../services/state.service';

/**
 * Toolbar filtri giorno: data, sentiment, categorie, liste paesi e Relazioni attive.
 * Non carica ``Article[]`` — solo rollup ``CountrySummary`` + conteggi.
 * Emit ``filtersChange`` / ``countrySelected`` verso App/StateService.
 * Relazioni Wave 1: toggle nazioni via StateService (OR stella).
 *
 * @see docs/03; radar-api-contract (day = map-summary); frontend.md Regola 12.
 */
@Component({
  selector: 'app-radar-toolbar',
  standalone: true,
  imports: [CommonModule, FormsModule, CalendarModule, MultiSelectModule, ProgressBarModule],
  templateUrl: './radar-toolbar.component.html',
  styleUrl: './radar-toolbar.component.scss',
})
export class RadarToolbarComponent {
  private readonly state = inject(StateService);

  /** Rollup day-view (paesi) senza Article[] completo. */
  countries = input<CountrySummary[]>([]);
  /** Rollup vault salvati (cross-day). */
  savedCountries = input<CountrySummary[]>([]);
  articleCount = input<number>(0);
  readCount = input<number>(0);
  savedCount = input<number>(0);
  isLoading = input<boolean>(false);
  /** Banner errore unificato (map-summary o detailError nation-fetch). */
  apiError = input<boolean>(false);

  filtersChange = output<ArticleFilters>();
  countrySelected = output<string>();
  savedCountrySelected = output<string>();

  selectedDate = signal<Date>(new Date());
  selectedSentiment = signal<Sentiment[]>([]);
  selectedCategories = signal<PrimaryCategory[]>([]);

  /** Filtri testo nazione (tooltip). */
  nationsFilter = signal('');
  savedNationsFilter = signal('');
  relationsFilter = signal('');

  isTooltipHovered = signal(false);
  isTooltipClicked = signal(false);
  isTooltipVisible = computed(
    () => (this.isTooltipHovered() || this.isTooltipClicked()) && this.countriesList().length > 0,
  );

  isSavedTooltipHovered = signal(false);
  isSavedTooltipClicked = signal(false);
  isSavedTooltipVisible = computed(
    () =>
      (this.isSavedTooltipHovered() || this.isSavedTooltipClicked()) &&
      this.savedCountriesList().length > 0,
  );

  isRelationsTooltipHovered = signal(false);
  isRelationsTooltipClicked = signal(false);
  isRelationsTooltipVisible = computed(
    () =>
      (this.isRelationsTooltipHovered() || this.isRelationsTooltipClicked()) &&
      this.relationOptions().length > 0,
  );

  readonly relationOptions = computed(() => this.state.relationCountryOptions());
  readonly relationEnabled = computed(() => this.state.relationCountriesEnabled());
  readonly relationEnabledCount = computed(() => this.relationEnabled().size);
  readonly relationTotalCount = computed(() => this.relationOptions().length);

  readonly countriesList = computed(() => this.buildCountryList(this.countries()));
  readonly savedCountriesList = computed(() => this.buildCountryList(this.savedCountries()));

  readonly filteredCountriesList = computed(() =>
    this.filterByNationQuery(this.countriesList(), this.nationsFilter()),
  );
  readonly filteredSavedCountriesList = computed(() =>
    this.filterByNationQuery(this.savedCountriesList(), this.savedNationsFilter()),
  );
  readonly filteredRelationOptions = computed(() =>
    this.filterByNationQuery(this.relationOptions(), this.relationsFilter()),
  );

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
    { label: '🛡️ Sicurezza', value: 'Sicurezza' },
  ];

  /** Nomi IT per ISO comuni; fallback Intl / codice grezzo sotto. */
  readonly COUNTRY_NAMES: Record<string, string> = {
    IT: 'Italia',
    DE: 'Germania',
    FR: 'Francia',
    ES: 'Spagna',
    GB: 'Regno Unito',
    US: 'Stati Uniti',
    CN: 'Cina',
    RU: 'Russia',
    UA: 'Ucraina',
    IR: 'Iran',
    KR: 'Corea del Sud',
    AZ: 'Azerbaigian',
    JP: 'Giappone',
    IN: 'India',
    BR: 'Brasile',
    SA: 'Arabia Saudita',
    TW: 'Taiwan',
    AF: 'Afghanistan',
    AU: 'Australia',
    VE: 'Venezuela',
    PG: 'Papua Nuova Guinea',
    PK: 'Pakistan',
    TR: 'Turchia',
    MX: 'Messico',
    XX: 'World Wide',
  };

  toggleTooltip(event: Event): void {
    event.stopPropagation();
    this.isTooltipClicked.update((v) => !v);
    this.isSavedTooltipClicked.set(false);
    this.isRelationsTooltipClicked.set(false);
  }

  closeTooltip(event: Event): void {
    event.stopPropagation();
    this.isTooltipClicked.set(false);
    this.isTooltipHovered.set(false);
  }

  toggleSavedTooltip(event: Event): void {
    event.stopPropagation();
    this.isSavedTooltipClicked.update((v) => !v);
    this.isTooltipClicked.set(false);
    this.isRelationsTooltipClicked.set(false);
  }

  closeSavedTooltip(event: Event): void {
    event.stopPropagation();
    this.isSavedTooltipClicked.set(false);
    this.isSavedTooltipHovered.set(false);
  }

  toggleRelationsTooltip(event: Event): void {
    event.stopPropagation();
    this.isRelationsTooltipClicked.update((v) => !v);
    this.isTooltipClicked.set(false);
    this.isSavedTooltipClicked.set(false);
  }

  closeRelationsTooltip(event: Event): void {
    event.stopPropagation();
    this.isRelationsTooltipClicked.set(false);
    this.isRelationsTooltipHovered.set(false);
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

  isRelationEnabled(code: string): boolean {
    return this.relationEnabled().has(code);
  }

  onToggleRelation(code: string, event: Event): void {
    event.stopPropagation();
    this.state.toggleRelationCountry(code);
  }

  onSelectAllRelations(event: Event): void {
    event.stopPropagation();
    this.state.selectAllRelationCountries();
  }

  onClearAllRelations(event: Event): void {
    event.stopPropagation();
    this.state.clearRelationCountries();
  }

  onNationsFilterInput(event: Event): void {
    event.stopPropagation();
    this.nationsFilter.set((event.target as HTMLInputElement).value);
  }

  onSavedNationsFilterInput(event: Event): void {
    event.stopPropagation();
    this.savedNationsFilter.set((event.target as HTMLInputElement).value);
  }

  onRelationsFilterInput(event: Event): void {
    event.stopPropagation();
    this.relationsFilter.set((event.target as HTMLInputElement).value);
  }

  /** Bandiera emoji da ISO-2; ``XX`` → ``WW``; codepoint invalidi → bandiera bianca. */
  getFlagEmoji(countryCode: string): string {
    if (!countryCode || countryCode === 'XX') return 'WW';
    const codePoints = countryCode
      .toUpperCase()
      .split('')
      .map((char) => 127397 + char.charCodeAt(0));
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
    const localDate = new Date(date.getTime() - offset * 60 * 1000);
    const dateString = localDate.toISOString().split('T')[0];

    this.filtersChange.emit({
      date: dateString,
      sentiment: this.selectedSentiment().length > 0 ? this.selectedSentiment() : null,
      categories: this.selectedCategories().length > 0 ? this.selectedCategories() : null,
    });
  }

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

  private filterByNationQuery<T extends { code: string; name: string }>(
    list: T[],
    query: string,
  ): T[] {
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter((c) => c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q));
  }
}
