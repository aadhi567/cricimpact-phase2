/**
 * CricImpact Phase 2 — Batting HPP/HPC API Service Client
 * Stage B9: Batting HPP Dashboard UI Modernization.
 * Strictly read-only consumer of validated /api/batting/* endpoints.
 */

import { BATTING_API_ENDPOINTS } from '../config/apiConfig.js';

class BattingApiService {
  constructor() {
    this.cache = new Map();
    this.cacheTTL = 5 * 60 * 1000;
  }

  _buildUrl(base, params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '' && v !== 'all') {
        query.set(k, String(v));
      }
    });
    const qs = query.toString();
    return qs ? `${base}?${qs}` : base;
  }

  async _fetch(url, useCache = true) {
    if (useCache && this.cache.has(url)) {
      const entry = this.cache.get(url);
      if (Date.now() - entry.ts < this.cacheTTL) {
        return entry.data;
      }
    }
    const resp = await fetch(url);
    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`;
      try {
        const errBody = await resp.json();
        if (errBody && errBody.detail) detail = errBody.detail;
      } catch (_) {}
      throw new Error(detail);
    }
    const data = await resp.json();
    if (useCache) {
      this.cache.set(url, { ts: Date.now(), data });
    }
    return data;
  }

  async getHealth() {
    return this._fetch(BATTING_API_ENDPOINTS.HEALTH);
  }

  async getFilters() {
    return this._fetch(BATTING_API_ENDPOINTS.FILTERS);
  }

  async getDashboard(params = {}) {
    return this._fetch(this._buildUrl(BATTING_API_ENDPOINTS.DASHBOARD, params));
  }

  async getExplorer(params = {}) {
    return this._fetch(this._buildUrl(BATTING_API_ENDPOINTS.EXPLORER, params));
  }

  async getPlayers(search = '') {
    return this._fetch(this._buildUrl(BATTING_API_ENDPOINTS.PLAYERS, { search, limit: 1000 }));
  }

  async getPlayerProfile(name, params = {}) {
    return this._fetch(this._buildUrl(BATTING_API_ENDPOINTS.PLAYER_PROFILE(name), params));
  }

  async comparePlayers(names, params = {}) {
    const base = BATTING_API_ENDPOINTS.COMPARE(names);
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '' && v !== 'all') {
        query.set(k, String(v));
      }
    });
    const qs = query.toString();
    const url = qs ? `${base}&${qs}` : base;
    return this._fetch(url);
  }

  async getMatches(params = {}) {
    return this._fetch(this._buildUrl(BATTING_API_ENDPOINTS.MATCHES, params));
  }

  async getMatchDetail(matchId) {
    return this._fetch(BATTING_API_ENDPOINTS.MATCH_DETAIL(matchId));
  }
}

export const battingApiService = new BattingApiService();
