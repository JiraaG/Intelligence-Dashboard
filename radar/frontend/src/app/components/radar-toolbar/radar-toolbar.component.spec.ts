import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RadarToolbarComponent } from './radar-toolbar.component';
import { StateService } from '../../services/state.service';
import { MOCK_MODE } from '../../services/mock-mode.token';
import { signal } from '@angular/core';

describe('RadarToolbarComponent', () => {
  let component: RadarToolbarComponent;
  let fixture: ComponentFixture<RadarToolbarComponent>;

  const mockStateService = {
    filters: signal({
      date: '2026-07-26',
      sentiment: [],
      categories: [],
    }),
    sidebarMode: signal('nation'),
    articleCount: signal(10),
    readCount: signal(4),
    savedCount: signal(2),
    relationCountriesEnabled: signal(new Set<string>()),
    relationCountryOptions: signal([]),
    visibleMapRelations: signal([]),
    metricsSummaryResource: { reload: vi.fn(), value: signal(null) },
    metricsStatusResource: { reload: vi.fn(), value: signal(null) },
    metricsSummary: signal(null),
    metricsStatus: signal(null),
    setFilters: vi.fn(),
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RadarToolbarComponent],
      providers: [
        { provide: StateService, useValue: mockStateService },
        { provide: MOCK_MODE, useValue: true },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(RadarToolbarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('renders correctly with Tipologia filter in toolbar', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const text = compiled.textContent || '';
    expect(text).toContain('Tipologia');
    expect(compiled.querySelector('.radar-toolbar')).not.toBeNull();
  });

  it('toggles category tooltip visibility', () => {
    const dummyEvent = { stopPropagation: vi.fn() } as unknown as MouseEvent;
    expect(component.isCategoryTooltipVisible()).toBe(false);
    component.toggleCategoryTooltip(dummyEvent);
    expect(component.isCategoryTooltipVisible()).toBe(true);
    component.closeCategoryTooltip(dummyEvent);
    expect(component.isCategoryTooltipVisible()).toBe(false);
  });
});
