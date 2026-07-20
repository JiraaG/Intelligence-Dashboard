import { Component, input, output, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CalendarModule } from 'primeng/calendar';
import { ProgressBarModule } from 'primeng/progressbar';
import {
  ArticleFilters,
  CountrySummary,
  Sentiment,
  PrimaryCategory,
} from '../../models/article.model';
import { StateService } from '../../services/state.service';

export interface FilterOption<T extends string = string> {
  label: string;
  value: T;
}

/**
 * Toolbar filtri giorno: data, sentiment, categorie, liste paesi e Relazioni attive.
 * Sentiment / Tipologia / Relazioni: stesso pattern tooltip (filtro testo, toggle iOS,
 * un solo bottone Seleziona/Deseleziona tutto).
 *
 * @see docs/03; radar-api-contract (day = map-summary); frontend.md Regola 12.
 */
@Component({
  selector: 'app-radar-toolbar',
  standalone: true,
  imports: [CommonModule, FormsModule, CalendarModule, ProgressBarModule],
  templateUrl: './radar-toolbar.component.html',
  styleUrl: './radar-toolbar.component.scss',
})
export class RadarToolbarComponent {
  private readonly state = inject(StateService);

  countries = input<CountrySummary[]>([]);
  savedCountries = input<CountrySummary[]>([]);
  articleCount = input<number>(0);
  readCount = input<number>(0);
  savedCount = input<number>(0);
  isLoading = input<boolean>(false);
  apiError = input<boolean>(false);

  filtersChange = output<ArticleFilters>();
  countrySelected = output<string>();
  savedCountrySelected = output<string>();

  selectedDate = signal<Date>(new Date());
  selectedSentiment = signal<Sentiment[]>([]);
  selectedCategories = signal<PrimaryCategory[]>([]);

  nationsFilter = signal('');
  savedNationsFilter = signal('');
  relationsFilter = signal('');
  sentimentFilter = signal('');
  categoryFilter = signal('');

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

  isSentimentTooltipHovered = signal(false);
  isSentimentTooltipClicked = signal(false);
  isSentimentTooltipVisible = computed(
    () => this.isSentimentTooltipHovered() || this.isSentimentTooltipClicked(),
  );

  isCategoryTooltipHovered = signal(false);
  isCategoryTooltipClicked = signal(false);
  isCategoryTooltipVisible = computed(
    () => this.isCategoryTooltipHovered() || this.isCategoryTooltipClicked(),
  );

  readonly relationOptions = computed(() => this.state.relationCountryOptions());
  readonly relationEnabled = computed(() => this.state.relationCountriesEnabled());
  readonly relationEnabledCount = computed(() => this.relationEnabled().size);
  readonly relationTotalCount = computed(() => this.relationOptions().length);
  /** True se tutte le nazioni relazione sono attive → bottone = Deseleziona tutto. */
  readonly relationsAllSelected = computed(
    () =>
      this.relationTotalCount() > 0 && this.relationEnabledCount() === this.relationTotalCount(),
  );

  readonly sentimentAllSelected = computed(
    () =>
      this.sentimentOptions.length > 0 &&
      this.selectedSentiment().length === this.sentimentOptions.length,
  );
  readonly categoryAllSelected = computed(
    () =>
      this.categoryOptions.length > 0 &&
      this.selectedCategories().length === this.categoryOptions.length,
  );

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
  readonly filteredSentimentOptions = computed(() =>
    this.filterOptionsByLabel(this.sentimentOptions, this.sentimentFilter()),
  );
  readonly filteredCategoryOptions = computed(() =>
    this.filterOptionsByLabel(this.categoryOptions, this.categoryFilter()),
  );

  readonly today = new Date();

  readonly sentimentOptions: FilterOption<Sentiment>[] = [
    { label: '▲ Positivo', value: 'Positivo' },
    { label: '● Neutrale', value: 'Neutrale' },
    { label: '▼ Negativo', value: 'Negativo' },
  ];

  readonly categoryOptions: FilterOption<PrimaryCategory>[] = [
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

  private closeAllPanelsExcept(
    keep: 'nations' | 'saved' | 'relations' | 'sentiment' | 'category' | null,
  ): void {
    if (keep !== 'nations') this.isTooltipClicked.set(false);
    if (keep !== 'saved') this.isSavedTooltipClicked.set(false);
    if (keep !== 'relations') this.isRelationsTooltipClicked.set(false);
    if (keep !== 'sentiment') this.isSentimentTooltipClicked.set(false);
    if (keep !== 'category') this.isCategoryTooltipClicked.set(false);
  }

  toggleTooltip(event: Event): void {
    event.stopPropagation();
    const next = !this.isTooltipClicked();
    this.closeAllPanelsExcept(next ? 'nations' : null);
    this.isTooltipClicked.set(next);
  }

  closeTooltip(event: Event): void {
    event.stopPropagation();
    this.isTooltipClicked.set(false);
    this.isTooltipHovered.set(false);
  }

  toggleSavedTooltip(event: Event): void {
    event.stopPropagation();
    const next = !this.isSavedTooltipClicked();
    this.closeAllPanelsExcept(next ? 'saved' : null);
    this.isSavedTooltipClicked.set(next);
  }

  closeSavedTooltip(event: Event): void {
    event.stopPropagation();
    this.isSavedTooltipClicked.set(false);
    this.isSavedTooltipHovered.set(false);
  }

  toggleRelationsTooltip(event: Event): void {
    event.stopPropagation();
    const next = !this.isRelationsTooltipClicked();
    this.closeAllPanelsExcept(next ? 'relations' : null);
    this.isRelationsTooltipClicked.set(next);
  }

  closeRelationsTooltip(event: Event): void {
    event.stopPropagation();
    this.isRelationsTooltipClicked.set(false);
    this.isRelationsTooltipHovered.set(false);
  }

  toggleSentimentTooltip(event: Event): void {
    event.stopPropagation();
    const next = !this.isSentimentTooltipClicked();
    this.closeAllPanelsExcept(next ? 'sentiment' : null);
    this.isSentimentTooltipClicked.set(next);
  }

  closeSentimentTooltip(event: Event): void {
    event.stopPropagation();
    this.isSentimentTooltipClicked.set(false);
    this.isSentimentTooltipHovered.set(false);
  }

  toggleCategoryTooltip(event: Event): void {
    event.stopPropagation();
    const next = !this.isCategoryTooltipClicked();
    this.closeAllPanelsExcept(next ? 'category' : null);
    this.isCategoryTooltipClicked.set(next);
  }

  closeCategoryTooltip(event: Event): void {
    event.stopPropagation();
    this.isCategoryTooltipClicked.set(false);
    this.isCategoryTooltipHovered.set(false);
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

  /** Un solo bottone: se tutte on → clear; altrimenti select-all. */
  onToggleSelectAllRelations(event: Event): void {
    event.stopPropagation();
    if (this.relationsAllSelected()) {
      this.state.clearRelationCountries();
    } else {
      this.state.selectAllRelationCountries();
    }
  }

  isSentimentOn(value: Sentiment): boolean {
    return this.selectedSentiment().includes(value);
  }

  onToggleSentiment(value: Sentiment, event: Event): void {
    event.stopPropagation();
    const cur = this.selectedSentiment();
    this.selectedSentiment.set(
      cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value],
    );
    this.onFiltersChange();
  }

  onToggleSelectAllSentiment(event: Event): void {
    event.stopPropagation();
    if (this.sentimentAllSelected()) {
      this.selectedSentiment.set([]);
    } else {
      this.selectedSentiment.set(this.sentimentOptions.map((o) => o.value));
    }
    this.onFiltersChange();
  }

  isCategoryOn(value: PrimaryCategory): boolean {
    return this.selectedCategories().includes(value);
  }

  onToggleCategory(value: PrimaryCategory, event: Event): void {
    event.stopPropagation();
    const cur = this.selectedCategories();
    this.selectedCategories.set(
      cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value],
    );
    this.onFiltersChange();
  }

  onToggleSelectAllCategories(event: Event): void {
    event.stopPropagation();
    if (this.categoryAllSelected()) {
      this.selectedCategories.set([]);
    } else {
      this.selectedCategories.set(this.categoryOptions.map((o) => o.value));
    }
    this.onFiltersChange();
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

  onSentimentFilterInput(event: Event): void {
    event.stopPropagation();
    this.sentimentFilter.set((event.target as HTMLInputElement).value);
  }

  onCategoryFilterInput(event: Event): void {
    event.stopPropagation();
    this.categoryFilter.set((event.target as HTMLInputElement).value);
  }

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

  private filterOptionsByLabel<T extends string>(
    options: FilterOption<T>[],
    query: string,
  ): FilterOption<T>[] {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (o) => o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q),
    );
  }
}
