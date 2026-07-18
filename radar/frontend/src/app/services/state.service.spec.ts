import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Article } from '../models/article.model';
import { ArticleService } from './article.service';
import { StateService } from './state.service';
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
  is_read: false,
};

describe('StateService detailError (T-P1-04)', () => {
  let state: StateService;
  let articleService: {
    getMapSummary: ReturnType<typeof vi.fn>;
    getAllArticlesForCountry: ReturnType<typeof vi.fn>;
    updateReadStatus: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    articleService = {
      getMapSummary: vi.fn(() => of([])),
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
