/**
 * CricImpact Phase 2 — Pressure Reliability Index (PRI) Frontend API Service
 * Consumes Stage PRI-3 read-only FastAPI endpoints under /api/pri.
 * Zero client-side recalculation, zero shrinkage, exact PRI-2 values preserved.
 */

import { PRI_API_ENDPOINTS } from '../config/apiConfig.js';

class PRIApiService {
  constructor() {
    this._overviewCache = null;
    this._filtersCache = null;
  }

  async _fetchJson(url) {
    const response = await fetch(url, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      let detail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errBody = await response.json();
        if (errBody && errBody.detail) detail = errBody.detail;
      } catch (_) {}
      throw new Error(detail);
    }
    return response.json();
  }

  async checkHealth() {
    return this._fetchJson(PRI_API_ENDPOINTS.HEALTH);
  }

  async getOverview() {
    if (!this._overviewCache) {
      this._overviewCache = await this._fetchJson(PRI_API_ENDPOINTS.OVERVIEW);
    }
    return this._overviewCache;
  }

  async getFilters() {
    if (!this._filtersCache) {
      this._filtersCache = await this._fetchJson(PRI_API_ENDPOINTS.FILTERS);
    }
    return this._filtersCache;
  }

  _buildQuery(params = {}) {
    const q = new URLSearchParams();
    if (params.min_opportunities !== undefined && params.min_opportunities !== null) {
      q.set('min_opportunities', String(params.min_opportunities));
    }
    if (params.season && params.season !== 'all') q.set('season', String(params.season));
    if (params.tournament && params.tournament !== 'all') q.set('tournament', String(params.tournament));
    if (params.team && params.team !== 'all') q.set('team', String(params.team));
    if (params.search && String(params.search).trim()) q.set('search', String(params.search).trim());
    if (params.sort_by) q.set('sort_by', String(params.sort_by));
    if (params.order) q.set('order', String(params.order));
    if (params.page !== undefined) q.set('page', String(params.page));
    if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
    const str = q.toString();
    return str ? `?${str}` : '';
  }

  async getBattingLeaderboard(scope = 'career', params = {}) {
    const base =
      scope === 'season'
        ? PRI_API_ENDPOINTS.BATTING_SEASON
        : scope === 'tournament'
          ? PRI_API_ENDPOINTS.BATTING_TOURNAMENT
          : PRI_API_ENDPOINTS.BATTING_CAREER;
    return this._fetchJson(`${base}${this._buildQuery(params)}`);
  }

  async getBowlingLeaderboard(scope = 'career', params = {}) {
    const base =
      scope === 'season'
        ? PRI_API_ENDPOINTS.BOWLING_SEASON
        : scope === 'tournament'
          ? PRI_API_ENDPOINTS.BOWLING_TOURNAMENT
          : PRI_API_ENDPOINTS.BOWLING_CAREER;
    return this._fetchJson(`${base}${this._buildQuery(params)}`);
  }

  async getBattingPlayerProfile(playerId) {
    return this._fetchJson(PRI_API_ENDPOINTS.BATTING_PLAYER(playerId));
  }

  async getBowlingPlayerProfile(playerId) {
    return this._fetchJson(PRI_API_ENDPOINTS.BOWLING_PLAYER(playerId));
  }

  async compareBatters(playerIds) {
    return this._fetchJson(PRI_API_ENDPOINTS.BATTING_COMPARE(playerIds));
  }

  async compareBowlers(playerIds) {
    return this._fetchJson(PRI_API_ENDPOINTS.BOWLING_COMPARE(playerIds));
  }
}

export const priApiService = new PRIApiService();
