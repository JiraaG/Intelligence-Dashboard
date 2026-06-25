import { Component, input, output, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CarouselModule } from 'primeng/carousel';
import { ChipModule } from 'primeng/chip';
import { ButtonModule } from 'primeng/button';
import { Article } from '../../models/article.model';

export type SidebarMode = 'single' | 'cluster';

@Component({
  selector: 'app-radar-sidebar',
  standalone: true,
  imports: [CommonModule, CarouselModule, ChipModule, ButtonModule],
  templateUrl: './radar-sidebar.component.html',
  styleUrl: './radar-sidebar.component.scss'
})
export class RadarSidebarComponent {
  article         = input<Article | null>(null);
  clusterArticles = input<Article[]>([]);
  isOpen          = input<boolean>(false);

  closed = output<void>();

  mode = computed((): SidebarMode => {
    return this.clusterArticles().length > 1 ? 'cluster' : 'single';
  });

  displayArticle = computed(() => {
    return this.clusterArticles().length === 1 ? this.clusterArticles()[0] : this.article();
  });

  sentimentClass = computed(() => {
    const s = this.displayArticle()?.sentiment;
    return s === 'Positivo' ? 'sentiment-pos'
         : s === 'Negativo' ? 'sentiment-neg'
         : 'sentiment-neu';
  });

  clusterSummary = computed(() => {
    const arts = this.clusterArticles();
    const byCategory = new Map<string, number>();
    for (const a of arts) {
      byCategory.set(a.primary_category, (byCategory.get(a.primary_category) ?? 0) + 1);
    }
    return byCategory;
  });

  carouselResponsiveOptions = [
    { breakpoint: '1400px', numVisible: 1, numScroll: 1 }
  ];
}
