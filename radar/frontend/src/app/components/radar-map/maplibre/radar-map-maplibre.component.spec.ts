import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RadarMapMaplibreComponent } from './radar-map-maplibre.component';
import { StateService } from '../../../services/state.service';
import { MOCK_MODE } from '../../../services/mock-mode.token';
import { signal } from '@angular/core';

describe('RadarMapMaplibreComponent Legenda Tipologie', () => {
  let component: RadarMapMaplibreComponent;
  let fixture: ComponentFixture<RadarMapMaplibreComponent>;

  const mockStateService = {
    filters: signal({
      date: '2026-07-26',
      sentiment: [],
      categories: [],
    }),
    sidebarMode: signal('nation'),
    categoryCounts: signal({
      Nucleare: 5,
      Energia: 12,
      Ambiente: 3,
    }),
    setFilters: vi.fn(),
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RadarMapMaplibreComponent],
      providers: [
        { provide: StateService, useValue: mockStateService },
        { provide: MOCK_MODE, useValue: true },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(RadarMapMaplibreComponent);
    component = fixture.componentInstance;
  });

  it('orders legend items alphabetically A to Z', () => {
    const labels = component.legendItems.map((item) => item.label);
    expect(labels[0]).toBe('Ambiente');
    expect(labels[labels.length - 1]).toBe('Tecnologia');
    const sorted = [...labels].sort();
    expect(labels).toEqual(sorted);
  });

  it('computes category counts accurately from StateService', () => {
    expect(component.getCategoryCount('Nucleare')).toBe(5);
    expect(component.getCategoryCount('Energia')).toBe(12);
    expect(component.getCategoryCount('Ambiente')).toBe(3);
    expect(component.getCategoryCount('Tecnologia')).toBe(0);
  });

  it('defaults to 15 in legend badge text when no selection highlight is locked', () => {
    expect(component.legendBadgeText()).toBe('15');
    expect(component.highlightedCount()).toBe(0);
    expect(component.isCategoryCardActive('Ambiente')).toBe(false);
  });

  it('toggles category card highlight lock on click and updates badge text', () => {
    const dummyEvent = { stopPropagation: vi.fn() } as unknown as MouseEvent;
    component.onCategoryCardClick('Ambiente', dummyEvent);
    expect(component.isCategoryCardActive('Ambiente')).toBe(true);
    expect(component.legendBadgeText()).toBe('1/15');
  });

  it('toggles select all categories highlight lock', () => {
    const dummyEvent = { stopPropagation: vi.fn() } as unknown as MouseEvent;
    component.toggleSelectAllCategories(dummyEvent);
    expect(component.highlightedCount()).toBe(15);
    expect(component.legendBadgeText()).toBe('15/15');
    component.toggleSelectAllCategories(dummyEvent);
    expect(component.highlightedCount()).toBe(0);
    expect(component.legendBadgeText()).toBe('15');
  });
});
