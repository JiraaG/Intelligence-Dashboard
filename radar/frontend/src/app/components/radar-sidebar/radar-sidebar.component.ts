import { Component, input, output, computed, ViewChild, effect, signal, HostListener } from '@angular/core';
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

  closed               = output<void>();
  categoryClicked      = output<string>();
  activeArticleChanged = output<Article | null>();

  carouselCurrentPage = signal<number>(0);
  private heightUpdateInterval: any;

  constructor() {
    effect(() => {
      if (!this.isOpen()) {
        this.activeArticleChanged.emit(null);
        return;
      }
      
      if (this.mode() === 'single') {
        this.activeArticleChanged.emit(this.displayArticle() || null);
      } else {
        const arts = this.sortedClusterArticles();
        if (arts.length > 0) {
          // Quando si apre il cluster, di default p-carousel parte dalla pagina 0
          this.carouselCurrentPage.set(0);
          this.activeArticleChanged.emit(arts[0]);
          this.updateCarouselHeight();
        }
      }
    }, { allowSignalWrites: true });
  }

  updateCarouselHeight() {
    if (this.heightUpdateInterval) {
      clearInterval(this.heightUpdateInterval);
    }
    
    let attempts = 0;
    this.heightUpdateInterval = setInterval(() => {
      const arts = this.sortedClusterArticles();
      if (arts.length === 0) return;
      const currentArt = arts[this.carouselCurrentPage()];
      const activeCard = document.getElementById('article-card-' + currentArt.id);

      const contentContainer = document.querySelector('.p-carousel-items-content') as HTMLElement;
      if (activeCard && contentContainer && activeCard.offsetHeight > 0) {
        contentContainer.style.height = `${activeCard.offsetHeight}px`;
        contentContainer.style.transition = 'height 0.3s ease-in-out';
      }
      attempts++;
      if (attempts > 15) { // Run for 1.5 seconds to strictly enforce it over PrimeNG
        clearInterval(this.heightUpdateInterval);
      }
    }, 100);
  }

  cleanFeedTitle(title: string | undefined): string {
    if (!title) return '';
    return title.replace(/^Feed:\s*/i, '');
  }

  @HostListener('window:resize')
  onResize() {
    if (this.isOpen() && this.mode() === 'cluster') {
      this.updateCarouselHeight();
    }
  }

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
    
    const idx = this.sortedClusterArticles().findIndex(a => a.primary_category === category);
    if (idx !== -1 && this.carousel) {
      this.carousel.page = idx;
      this.carouselCurrentPage.set(idx);
      this.activeArticleChanged.emit(this.sortedClusterArticles()[idx]);
      this.updateCarouselHeight();
    }
  }

  onCarouselPage(event: any): void {
    const page = event.page;
    this.carouselCurrentPage.set(page);
    const arts = this.sortedClusterArticles();
    if (page >= 0 && page < arts.length) {
      this.activeArticleChanged.emit(arts[page]);
    }
    this.updateCarouselHeight();
  }
}