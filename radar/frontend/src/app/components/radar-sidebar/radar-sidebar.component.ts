import { Component, input, output, computed, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CarouselModule, Carousel } from 'primeng/carousel';
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

  @ViewChild(Carousel) carousel!: Carousel;

  closed          = output<void>();
  categoryClicked = output<string>();

  mode = computed((): SidebarMode => {
    return this.clusterArticles().length > 1 ? 'cluster' : 'single';
  });

  displayArticle = computed(() => {
    return this.clusterArticles().length === 1 ? this.clusterArticles()[0] : this.article();
  });

  sentimentClass = computed(() => {
    return this.getSentimentClass(this.displayArticle()?.sentiment);
  });

  // Nuovo metodo riutilizzabile per il template del carosello
  getSentimentClass(sentiment?: string): string {
    return sentiment === 'Positivo' ? 'sentiment-pos'
         : sentiment === 'Negativo' ? 'sentiment-neg'
         : 'sentiment-neu';
  }

  clusterSummary = computed(() => {
    const arts = this.clusterArticles();
    const byCategory = new Map<string, number>();
    for (const a of arts) {
      byCategory.set(a.primary_category, (byCategory.get(a.primary_category) ?? 0) + 1);
    }
    return byCategory;
  });

  sortedClusterArticles = computed(() => {
    return [...this.clusterArticles()].sort((a, b) => a.primary_category.localeCompare(b.primary_category));
  });

  carouselResponsiveOptions = [
    { breakpoint: '1400px', numVisible: 1, numScroll: 1 }
  ];

  onCategoryPillClick(category: string): void {
    this.categoryClicked.emit(category);
    
    // Trova il primo articolo di questa categoria nell'array ordinato
    const idx = this.sortedClusterArticles().findIndex(a => a.primary_category === category);
    if (idx !== -1 && this.carousel) {
      this.carousel.page = idx;
    }
  }
}