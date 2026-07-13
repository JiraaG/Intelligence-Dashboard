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
  readCount    = computed(() => this.articles().filter(a => a.is_read).length);
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
    const countMap = new Map<string, { total: number, read: number }>();
    for (const a of arts) {
      const stats = countMap.get(a.country_code) || { total: 0, read: 0 };
      stats.total += 1;
      if (a.is_read) stats.read += 1;
      countMap.set(a.country_code, stats);
    }
    
    const list: { code: string; name: string; count: number; readCount: number }[] = [];
    countMap.forEach((stats, code) => {
      let name = this.COUNTRY_NAMES[code];
      if (!name) {
        if (code === 'XX') {
          name = 'World Wide';
        } else {
          try {
            const displayNames = new Intl.DisplayNames(['it-IT'], { type: 'region' });
            name = displayNames.of(code) || code;
          } catch (e) {
            name = code;
          }
        }
      }
      list.push({ code, name, count: stats.total, readCount: stats.read });
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

