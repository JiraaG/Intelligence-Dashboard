import { Component, input, output, signal, computed, inject, DestroyRef } from '@angular/core';
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
  private readonly destroyRef = inject(DestroyRef);

  readonly nowTick = signal<number>(Date.now());

  constructor() {
    const timer = setInterval(() => {
      if (this.isStatusTooltipVisible()) {
        this.nowTick.set(Date.now());
      }
    }, 1000);
    this.destroyRef.onDestroy(() => clearInterval(timer));
  }

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

  isCostiTooltipHovered = signal(false);
  isCostiTooltipClicked = signal(false);
  isCostiTooltipVisible = computed(
    () => this.isCostiTooltipHovered() || this.isCostiTooltipClicked(),
  );

  isStatusTooltipHovered = signal(false);
  isStatusTooltipClicked = signal(false);
  isStatusTooltipVisible = computed(
    () => this.isStatusTooltipHovered() || this.isStatusTooltipClicked(),
  );

  readonly metricsSummary = computed(() => this.state.metricsSummary());
  readonly metricsStatus = computed(() => this.state.metricsStatus());
  readonly statusLevel = computed(() => this.metricsStatus()?.level ?? 'nominal');

  readonly primaryModel = computed(() => this.metricsStatus()?.models?.find((m) => m.role === 'primary'));
  readonly fallbackModels = computed(() => this.metricsStatus()?.models?.filter((m) => m.role === 'fallback') ?? []);
  readonly complexModel = computed(() => this.metricsStatus()?.models?.find((m) => m.role === 'complex'));
  readonly complexReasoningEffort = computed(() => this.complexModel()?.reasoning_effort || 'high');

  readonly totalCostUsd = computed(() => {
    return this.metricsSummary()?.llm?.total_estimated_cost_usd ?? 0;
  });

  readonly modelsByCost = computed(() => {
    const list = this.metricsSummary()?.llm?.models_breakdown;
    if (!list) return [];
    return [...list].sort((a, b) => (b.estimated_cost_usd ?? 0) - (a.estimated_cost_usd ?? 0));
  });

  readonly modelsByTokens = computed(() => {
    const list = this.metricsSummary()?.llm?.models_breakdown;
    if (!list) return [];
    return [...list].sort((a, b) => (b.total_tokens ?? 0) - (a.total_tokens ?? 0));
  });

  readonly totalTokensSum = computed(() => {
    const llm = this.metricsSummary()?.llm;
    if (!llm) return 0;
    return (llm.total_prompt_tokens ?? 0) + (llm.total_completion_tokens ?? 0);
  });
  readonly statusDotEmoji = computed(() => {
    const lvl = this.statusLevel();
    if (lvl === 'nominal') return '🟢';
    if (lvl === 'fallback_or_escalation') return '🟡';
    return '🔴';
  });
  readonly statusLevelLabel = computed(() => {
    const lvl = this.statusLevel();
    if (lvl === 'nominal') return 'OPERATIVO (Catena Simple OK)';
    if (lvl === 'fallback_or_escalation') return 'FALLBACK / ESCALATION ATTIVA';
    return 'RISORSE LIMITATE / DEGRADATO';
  });
  readonly statusDotTooltip = computed(() => {
    const lvl = this.statusLevel();
    if (lvl === 'nominal') {
      return '🟢 OPERATIVO: Corsia SIMPLE nominale ed attiva senza errori o fallback.';
    }
    if (lvl === 'fallback_or_escalation') {
      return '🟡 FALLBACK / ESCALATION ATTIVA: Modello primario in cooldown o limite RPD raggiunto. Il sistema sta usando la corsia di fallback L1 o escalation COMPLEX.';
    }
    return '🔴 RISORSE LIMITATE / DEGRADATO: Worker stale, tutti i modelli in cooldown o limiti RPD giornalieri esauriti.';
  });

  readonly l1ReasonLabel = computed(() => {
    const reason = this.metricsStatus()?.l1_reason;
    if (reason === 'primary_cooldown') return 'Fallback L1 (Pausa Primario)';
    if (reason === 'primary_rpd_exhausted') return 'Fallback L1 (Quota Esaurita)';
    if (reason === 'recent_articles') return 'Fallback L1 (Articoli Recenti)';
    return 'Fallback L1 Attivo';
  });

  readonly l1ReasonDescription = computed(() => {
    const reason = this.metricsStatus()?.l1_reason;
    if (reason === 'primary_cooldown') {
      return 'Il modello primario SIMPLE è in pausa temporanea (cooldown). Le chiamate sono dirottate in automatico sul modello di Fallback L1.';
    }
    if (reason === 'primary_rpd_exhausted') {
      return 'La quota giornaliera (RPD) del modello primario SIMPLE è esaurita. Il sistema sta utilizzando il modello di Fallback L1 per garantire la continuità.';
    }
    if (reason === 'recent_articles') {
      return 'Dirottamento automatico al modello Fallback L1 per la deduplicazione e la gestione degli articoli recenti.';
    }
    return 'Le richieste della corsia SIMPLE vengono attualmente dirottate sul modello di Fallback L1 per garantire l\'elaborazione dei dati.';
  });

  readonly l1BadgeTooltip = computed(() => {
    return `Fallback L1 Attivo: ${this.l1ReasonDescription()}`;
  });

  readonly degradedReasonDescription = computed(() => {
    return 'Tutti i modelli di Intelligenza Artificiale configurati sono attualmente in pausa per cooldown o quota RPD esaurita. L\'elaborazione di nuovi articoli riprenderà automaticamente al loro sblocco.';
  });

  formatCooldownUntil(isoString: string | null | undefined, nowMs: number): string {
    if (!isoString) return 'In pausa';
    const target = new Date(isoString);
    if (isNaN(target.getTime())) return 'In pausa';

    const diffMs = target.getTime() - nowMs;
    if (diffMs <= 0) return 'In fase di sblocco...';

    const now = new Date(nowMs);
    const totalSeconds = Math.floor(diffMs / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;

    const isToday =
      target.getDate() === now.getDate() &&
      target.getMonth() === now.getMonth() &&
      target.getFullYear() === now.getFullYear();

    const tomorrow = new Date(now);
    tomorrow.setDate(now.getDate() + 1);
    const isTomorrow =
      target.getDate() === tomorrow.getDate() &&
      target.getMonth() === tomorrow.getMonth() &&
      target.getFullYear() === tomorrow.getFullYear();

    const hh = target.getHours().toString().padStart(2, '0');
    const mm = target.getMinutes().toString().padStart(2, '0');
    const ss = target.getSeconds().toString().padStart(2, '0');
    const timeStr = `${hh}:${mm}:${ss}`;

    let timeDiffStr = '';
    if (hours > 0) {
      timeDiffStr = `tra ${hours}h ${mins}m ${secs}s`;
    } else if (mins > 0) {
      timeDiffStr = `tra ${mins}m ${secs}s`;
    } else {
      timeDiffStr = `tra ${secs}s`;
    }

    if (isToday) {
      return `scade oggi alle ${timeStr} (${timeDiffStr})`;
    } else if (isTomorrow) {
      return `scade domani alle ${timeStr} (${timeDiffStr})`;
    } else {
      const day = target.getDate().toString().padStart(2, '0');
      const month = (target.getMonth() + 1).toString().padStart(2, '0');
      return `scade il ${day}/${month} alle ${timeStr} (${timeDiffStr})`;
    }
  }

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
    { label: '🤖 Intelligenza Artificiale', value: 'Intelligenza Artificiale' },
    { label: '🔒 Cybersecurity', value: 'Cybersecurity' },
    { label: '💎 Finanza', value: 'Finanza' },
    { label: '⚔️ Difesa', value: 'Difesa' },
    { label: '⛏️ Materie Prime', value: 'Materie Prime' },
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
    keep: 'nations' | 'saved' | 'relations' | 'sentiment' | 'category' | 'status' | 'costi' | null,
  ): void {
    if (keep !== 'nations') this.isTooltipClicked.set(false);
    if (keep !== 'saved') this.isSavedTooltipClicked.set(false);
    if (keep !== 'relations') this.isRelationsTooltipClicked.set(false);
    if (keep !== 'sentiment') this.isSentimentTooltipClicked.set(false);
    if (keep !== 'category') this.isCategoryTooltipClicked.set(false);
    if (keep !== 'status') this.isStatusTooltipClicked.set(false);
    if (keep !== 'costi') this.isCostiTooltipClicked.set(false);
  }

  toggleCostiTooltip(event: Event): void {
    event.stopPropagation();
    const next = !this.isCostiTooltipClicked();
    this.closeAllPanelsExcept(next ? 'costi' : null);
    this.isCostiTooltipClicked.set(next);
    if (next) {
      this.state.metricsSummaryResource.reload();
    }
  }

  closeCostiTooltip(event: Event): void {
    event.stopPropagation();
    this.isCostiTooltipClicked.set(false);
    this.isCostiTooltipHovered.set(false);
  }

  toggleStatusTooltip(event: Event): void {
    event.stopPropagation();
    const next = !this.isStatusTooltipClicked();
    this.closeAllPanelsExcept(next ? 'status' : null);
    this.isStatusTooltipClicked.set(next);
    if (next) {
      this.state.metricsStatusResource.reload();
    }
  }

  closeStatusTooltip(event: Event): void {
    event.stopPropagation();
    this.isStatusTooltipClicked.set(false);
    this.isStatusTooltipHovered.set(false);
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
