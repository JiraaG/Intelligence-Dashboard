import { Component, input, output, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CalendarModule } from 'primeng/calendar';
import { MultiSelectModule } from 'primeng/multiselect';
import { ProgressBarModule } from 'primeng/progressbar';
import { Article, ArticleFilters, Sentiment, PrimaryCategory } from '../../models/article.model';

@Component({
  selector: 'app-radar-toolbar',
  standalone: true,
  imports: [CommonModule, FormsModule, CalendarModule, MultiSelectModule, ProgressBarModule],
  templateUrl: './radar-toolbar.component.html',
  styleUrl: './radar-toolbar.component.scss'
})
export class RadarToolbarComponent {
  articles     = input<Article[]>([]);
  articleCount = input<number>(0);
  isLoading    = input<boolean>(false);

  filtersChange   = output<ArticleFilters>();
  countrySelected = output<string>();

  selectedDate       = signal<Date>(new Date());
  selectedSentiment  = signal<Sentiment[]>([]);
  selectedCategories = signal<PrimaryCategory[]>([]);

  isTooltipHovered = signal<boolean>(false);
  isTooltipClicked = signal<boolean>(false);
  isTooltipVisible = computed(() => (this.isTooltipHovered() || this.isTooltipClicked()) && this.countriesList().length > 0);

  toggleTooltip(event: Event): void {
    event.stopPropagation();
    this.isTooltipClicked.update(v => !v);
  }

  closeTooltip(event: Event): void {
    event.stopPropagation();
    this.isTooltipClicked.set(false);
    this.isTooltipHovered.set(false);
  }

  selectCountry(countryCode: string, event: Event): void {
    event.stopPropagation();
    this.countrySelected.emit(countryCode);
    this.isTooltipClicked.set(false);
    this.isTooltipHovered.set(false);
  }

  readonly today = new Date();

  readonly sentimentOptions = [
    { label: '▲ Positivo', value: 'Positivo' },
    { label: '● Neutrale', value: 'Neutrale' },
    { label: '▼ Negativo', value: 'Negativo' },
  ];

  readonly categoryOptions = [
    { label: '☢️ Nucleare', value: 'Nucleare' },
    { label: '💾 Chip', value: 'Chip' },
    { label: '📡 Elettronica', value: 'Elettronica' },
    { label: '💧 Acqua', value: 'Acqua' },
    { label: '⚡ Energia', value: 'Energia' },
    { label: '🏗️ Infrastrutture', value: 'Infrastrutture' }
  ];

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

  // Calcolo dei paesi coinvolti per l'hover tooltip
  readonly countriesList = computed(() => {
    const arts = this.articles();
    const countMap = new Map<string, number>();
    for (const a of arts) {
      countMap.set(a.country_code, (countMap.get(a.country_code) || 0) + 1);
    }
    
    const list: { code: string; name: string; count: number }[] = [];
    countMap.forEach((count, code) => {
      const name = this.COUNTRY_NAMES[code] || code;
      list.push({ code, name, count });
    });
    
    return list.sort((a, b) => b.count - a.count);
  });

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

