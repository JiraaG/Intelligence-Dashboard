import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Article } from '../models/article.model';
import { MapRelationRow } from '../models/map-relation.model';
import { ArticleService } from './article.service';
import {
  buildRelationCountryOptions,
  filterMapRelationsByEnabledCountries,
  isBilateralRelationArticle,
  StateService,
} from './state.service';
import { MOCK_MODE } from './mock-mode.token';

const SAMPLE: Article = {
  id: 1,
  title: 'Sample',
  summary: 's',
  published_at: '2026-07-16',
  source_url: 'https://example.com/sample',
  country_code: 'UA',
  latitude: 47.5,
  longitude: 34.4,
  primary_category: 'Economia',
  sentiment: 'Neutrale',
  relevance_level: 2,
  companies_involved: [],
  tags: [],
  infrastructural_entities: [],
  feed_title: 'Feed',
  related_countries: [],
  is_read: false,
};

describe('isBilateralRelationArticle', () => {
  it('matches both directions of the pair', () => {
    expect(
      isBilateralRelationArticle(
        { ...SAMPLE, country_code: 'IT', related_countries: ['CN'] },
        'CN',
        'IT',
      ),
    ).toBe(true);
    expect(
      isBilateralRelationArticle(
        { ...SAMPLE, country_code: 'CN', related_countries: ['IT'] },
        'CN',
        'IT',
      ),
    ).toBe(true);
  });

  it('rejects articles not linking the pair', () => {
    expect(
      isBilateralRelationArticle(
        { ...SAMPLE, country_code: 'IT', related_countries: ['US'] },
        'CN',
        'IT',
      ),
    ).toBe(false);
    expect(
      isBilateralRelationArticle(
        { ...SAMPLE, country_code: 'DE', related_countries: ['IT'] },
        'CN',
        'IT',
      ),
    ).toBe(false);
  });
});

describe('StateService detailError (T-P1-04)', () => {
  let state: StateService;
  let articleService: {
    getMapSummary: ReturnType<typeof vi.fn>;
    getMapRelations: ReturnType<typeof vi.fn>;
    getSavedSummary: ReturnType<typeof vi.fn>;
    getAllArticlesForCountry: ReturnType<typeof vi.fn>;
    updateReadStatus: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    articleService = {
      getMapSummary: vi.fn(() => of([])),
      getMapRelations: vi.fn(() => of([])),
      getSavedSummary: vi.fn(() => of([])),
      getAllArticlesForCountry: vi.fn(),
      updateReadStatus: vi.fn(() => of({ status: 'ok', is_read: true })),
    };

    TestBed.configureTestingModule({
      providers: [
        { provide: MOCK_MODE, useValue: false },
        { provide: ArticleService, useValue: articleService },
        StateService,
      ],
    });
    state = TestBed.inject(StateService);
  });

  it('sets detailError and error() when loadCountryArticles rejects', async () => {
    const boom = new Error('nation fetch failed');
    articleService.getAllArticlesForCountry.mockReturnValue(throwError(() => boom));

    await expect(state.loadCountryArticles('UA')).rejects.toBe(boom);
    expect(state.detailError()).toBe(boom);
    expect(state.error()).toBe(boom);
    expect(state.detailArticles()).toEqual([]);
  });

  it('clears detailError at the start of a new loadCountryArticles call', async () => {
    state.detailError.set(new Error('stale'));
    articleService.getAllArticlesForCountry.mockReturnValue(of([SAMPLE]));

    const pending = state.loadCountryArticles('UA');
    expect(state.detailError()).toBeNull();

    await expect(pending).resolves.toHaveLength(1);
    expect(state.detailError()).toBeNull();
    expect(state.detailArticles()).toHaveLength(1);
  });

  it('clearDetailArticles({ clearError: false }) preserves detailError', () => {
    const err = new Error('keep-me');
    state.detailError.set(err);
    state.detailArticles.set([SAMPLE]);

    state.clearDetailArticles({ clearError: false });

    expect(state.detailArticles()).toEqual([]);
    expect(state.detailError()).toBe(err);
    expect(state.error()).toBe(err);
  });

  it('clearDetailArticles() default clears detailError', () => {
    state.detailError.set(new Error('wipe-me'));
    state.clearDetailArticles();
    expect(state.detailError()).toBeNull();
    expect(state.error()).toBeNull();
  });

  describe('loadRelationArticles', () => {
    it('keeps only bilateral articles and optional category', async () => {
      const itCnEco = {
        ...SAMPLE,
        id: 1,
        country_code: 'IT',
        related_countries: ['CN'],
        primary_category: 'Economia' as const,
      };
      const cnItEco = {
        ...SAMPLE,
        id: 2,
        country_code: 'CN',
        related_countries: ['IT'],
        primary_category: 'Economia' as const,
      };
      const itCnEnergy = {
        ...SAMPLE,
        id: 3,
        country_code: 'IT',
        related_countries: ['CN'],
        primary_category: 'Energia' as const,
      };
      const itUs = {
        ...SAMPLE,
        id: 4,
        country_code: 'IT',
        related_countries: ['US'],
        primary_category: 'Economia' as const,
      };

      articleService.getAllArticlesForCountry.mockImplementation(
        (_date: string, country: string) => {
          if (country === 'IT') return of([itCnEco, itCnEnergy, itUs]);
          if (country === 'CN') return of([cnItEco]);
          return of([]);
        },
      );

      const all = await state.loadRelationArticles('IT', 'CN');
      expect(all.map((a) => a.id).sort()).toEqual([1, 2, 3]);

      const pin = await state.loadRelationArticles('IT', 'CN', 'Economia');
      expect(pin.map((a) => a.id).sort()).toEqual([1, 2]);
    });
  });

  describe('mergeDetailArticlesFromServer (Fase B)', () => {
    it('preserves existing article object references by ID', () => {
      const art1 = { ...SAMPLE, id: 10, title: 'Original' };
      state.detailArticles.set([art1]);

      const incoming = { ...SAMPLE, id: 10, title: 'Updated' };
      const merged = state.mergeDetailArticlesFromServer([incoming]);

      expect(merged).toHaveLength(1);
      expect(merged[0]).toBe(art1); // strict object equality
      expect(art1.title).toBe('Updated');
    });

    it('does not overwrite is_read if it is in pendingReadIds', () => {
      const art1 = { ...SAMPLE, id: 10, is_read: true };
      state.detailArticles.set([art1]);
      state.pendingReadIds.add(10);

      const incoming = { ...SAMPLE, id: 10, is_read: false };
      state.mergeDetailArticlesFromServer([incoming]);

      expect(art1.is_read).toBe(true); // preserved because it was pending
    });

    it('does not overwrite is_saved if it is in pendingSaveIds', () => {
      const art1 = { ...SAMPLE, id: 10, is_saved: true };
      state.detailArticles.set([art1]);
      state.pendingSaveIds.add(10);

      const incoming = { ...SAMPLE, id: 10, is_saved: false };
      state.mergeDetailArticlesFromServer([incoming]);

      expect(art1.is_saved).toBe(true); // preserved because it was pending
    });
  });
});

describe('StateService visibleMapRelations nation filter (Wave 1)', () => {
  const US_CN: MapRelationRow = {
    source_country: 'US',
    target_country: 'CN',
    primary_category: 'Geopolitica',
    volume: 3,
  };
  const US_DE: MapRelationRow = {
    source_country: 'US',
    target_country: 'DE',
    primary_category: 'Economia',
    volume: 1,
  };
  const CN_JP: MapRelationRow = {
    source_country: 'CN',
    target_country: 'JP',
    primary_category: 'Tecnologia',
    volume: 2,
  };
  const ROWS = [US_CN, US_DE, CN_JP];

  let state: StateService;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        { provide: MOCK_MODE, useValue: true },
        {
          provide: ArticleService,
          useValue: {
            getMapSummary: vi.fn(() => of([])),
            getMapRelations: vi.fn(() => of([])),
            getSavedSummary: vi.fn(() => of([])),
            getAllArticlesForCountry: vi.fn(),
            updateReadStatus: vi.fn(() => of({ status: 'ok', is_read: true })),
          },
        },
        StateService,
      ],
    });
    state = TestBed.inject(StateService);
  });

  it('defaults to empty enabled set', () => {
    expect(state.relationCountriesEnabled().size).toBe(0);
    expect(filterMapRelationsByEnabledCountries(ROWS, state.relationCountriesEnabled())).toEqual(
      [],
    );
  });

  it('OR star: US on / CN off shows US↔CN and US↔DE, hides CN↔JP', () => {
    state.toggleRelationCountry('US');
    const visible = filterMapRelationsByEnabledCountries(ROWS, state.relationCountriesEnabled());
    expect(visible).toHaveLength(2);
    expect(visible).toEqual(expect.arrayContaining([US_CN, US_DE]));
    expect(
      visible.find((r) => r.source_country === 'CN' && r.target_country === 'JP'),
    ).toBeUndefined();
  });

  it('selectAllRelationCountries / clearRelationCountries mutate enabled set', () => {
    // Options empty without resource payload — seed via selectAll on options helper.
    const codes = buildRelationCountryOptions(ROWS).map((o) => o.code);
    state.relationCountriesEnabled.set(new Set(codes));
    expect(state.relationCountriesEnabled().size).toBe(4);
    expect(
      filterMapRelationsByEnabledCountries(ROWS, state.relationCountriesEnabled()),
    ).toHaveLength(3);

    state.clearRelationCountries();
    expect(state.relationCountriesEnabled().size).toBe(0);
    expect(filterMapRelationsByEnabledCountries(ROWS, state.relationCountriesEnabled())).toEqual(
      [],
    );
  });

  it('buildRelationCountryOptions sorts IT names and counts arcs', () => {
    const opts = buildRelationCountryOptions(ROWS);
    expect(opts.map((o) => o.code).sort()).toEqual(['CN', 'DE', 'JP', 'US']);
    expect(opts.find((o) => o.code === 'US')?.arcCount).toBe(2);
    expect(opts.find((o) => o.code === 'CN')?.arcCount).toBe(2);
  });

  it('Tipologia subset then nation filter (composition)', () => {
    const afterTipologia = ROWS.filter((r) => r.primary_category === 'Economia');
    expect(afterTipologia).toEqual([US_DE]);
    state.selectAllRelationCountries(); // no-op on empty options from resource
    state.relationCountriesEnabled.set(
      new Set(buildRelationCountryOptions(afterTipologia).map((o) => o.code)),
    );
    expect(
      filterMapRelationsByEnabledCountries(afterTipologia, state.relationCountriesEnabled()),
    ).toEqual([US_DE]);
  });
});
