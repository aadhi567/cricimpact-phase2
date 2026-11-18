/**
 * CricImpact Phase 2 — Bowling Pressure Contribution Score (PCS) API Service Layer
 * Consumes Stage B8 FastAPI endpoints under /api/pcs.
 */

import { PCS_API_ENDPOINTS } from '../config/apiConfig.js';

class PCSApiService {
  /**
   * Internal reusable fetch wrapper with error handling.
   */
  async _fetchJson(url, options = {}) {
    try {
      const response = await fetch(url, {
        headers: {
          'Accept': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errorJson = await response.json();
          if (errorJson.detail) errorDetail = errorJson.detail;
        } catch (_) {}
        throw new Error(errorDetail);
      }

      const json = await response.json();
      return {
        success: json.status === 'success' || !json.status || json.status === 'ok',
        data: json.data || json,
        ...json,
      };
    } catch (err) {
      console.error(`[PCSApiService Error] Failed request to ${url}:`, err);
      throw err;
    }
  }

  /**
   * Health check endpoint: GET /api/pcs/health
   */
  async checkHealth() {
    return this._fetchJson(PCS_API_ENDPOINTS.HEALTH);
  }

  /**
   * GET /api/pcs/dashboard
   */
  async getDashboard() {
    return this._fetchJson(PCS_API_ENDPOINTS.DASHBOARD);
  }

  /**
   * GET /api/pcs/tournaments
   */
  async getTournaments() {
    return this._fetchJson(PCS_API_ENDPOINTS.TOURNAMENTS);
  }

  /**
   * GET /api/pcs/leaderboard
   * @param {Object} params - { scope, season, tournament, min_balls, sort_by, order, search, page, page_size }
   */
  async getLeaderboard(params = {}) {
    const query = new URLSearchParams();
    if (params.scope) query.append('scope', params.scope);
    if (params.season && params.season !== 'all') query.append('season', params.season);
    if (params.tournament && params.tournament !== 'all') query.append('tournament', params.tournament);
    if (params.min_balls !== undefined) query.append('min_balls', params.min_balls);
    if (params.sort_by) query.append('sort_by', params.sort_by);
    if (params.order) query.append('order', params.order);
    if (params.search) query.append('search', params.search);
    if (params.page !== undefined) query.append('page', params.page);
    if (params.page_size !== undefined) query.append('page_size', params.page_size);

    const queryString = query.toString();
    const url = queryString ? `${PCS_API_ENDPOINTS.LEADERBOARD}?${queryString}` : PCS_API_ENDPOINTS.LEADERBOARD;
    return this._fetchJson(url);
  }

  /**
   * GET /api/pcs/players/{player_id}
   */
  async getPlayerProfile(playerId) {
    if (!playerId) throw new Error('Player ID is required for getPlayerProfile');
    return this._fetchJson(PCS_API_ENDPOINTS.PLAYER_PROFILE(playerId));
  }

  /**
   * GET /api/pcs/compare?bowlers=p1,p2,...
   * @param {Array<number>} playerIds - between 1 and 5 IDs
   */
  async compareBowlers(playerIds) {
    if (!Array.isArray(playerIds) || playerIds.length < 1 || playerIds.length > 5) {
      throw new Error('Bowler comparison requires between 1 and 5 player IDs');
    }
    return this._fetchJson(PCS_API_ENDPOINTS.COMPARE(playerIds));
  }

  /**
   * GET /api/pcs/matches
   * @param {Object} params - { season, page, page_size }
   */
  async getMatches(params = {}) {
    const query = new URLSearchParams();
    if (params.season && params.season !== 'all') query.append('season', params.season);
    if (params.page !== undefined) query.append('page', params.page);
    if (params.page_size !== undefined) query.append('page_size', params.page_size);

    const queryString = query.toString();
    const url = queryString ? `${PCS_API_ENDPOINTS.MATCHES}?${queryString}` : PCS_API_ENDPOINTS.MATCHES;
    return this._fetchJson(url);
  }

  /**
   * GET /api/pcs/matches/{match_id}
   */
  async getMatchDetail(matchId) {
    if (!matchId) throw new Error('Match ID is required for getMatchDetail');
    return this._fetchJson(PCS_API_ENDPOINTS.MATCH_DETAIL(matchId));
  }

  /**
   * GET /api/pcs/spells/{spell_id}/deliveries
   */
  async getSpellDeliveries(spellId) {
    if (!spellId) throw new Error('Spell ID is required for getSpellDeliveries');
    return this._fetchJson(PCS_API_ENDPOINTS.SPELL_DELIVERIES(spellId));
  }
}

export const pcsApiService = new PCSApiService();
