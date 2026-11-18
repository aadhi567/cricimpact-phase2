/**
 * CricImpact Phase 2 — Bowling Analytics API Service Layer
 * Consumes verified Stage B5 FastAPI endpoints.
 */

import { API_ENDPOINTS } from '../config/apiConfig.js';

class BowlingApiService {
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
      console.error(`[BowlingApiService Error] Failed request to ${url}:`, err);
      throw err;
    }
  }

  /**
   * Health check endpoint.
   */
  async checkHealth() {
    return this._fetchJson(API_ENDPOINTS.HEALTH);
  }

  /**
   * GET /api/bowling/dashboard
   */
  async getDashboard() {
    return this._fetchJson(API_ENDPOINTS.DASHBOARD);
  }

  /**
   * GET /api/bowling/tournaments
   */
  async getTournaments() {
    return this._fetchJson(API_ENDPOINTS.TOURNAMENTS);
  }

  /**
   * GET /api/bowling/leaderboard
   * @param {Object} params - { season, tournament, phase, min_balls, sort_by, order, page, page_size }
   */
  async getLeaderboard(params = {}) {
    const query = new URLSearchParams();
    if (params.season && params.season !== 'all') query.append('season', params.season);
    if (params.tournament && params.tournament !== 'all') query.append('tournament', params.tournament);
    if (params.phase) query.append('phase', params.phase);
    if (params.min_balls !== undefined) query.append('min_balls', params.min_balls);
    if (params.sort_by) query.append('sort_by', params.sort_by);
    if (params.order) query.append('order', params.order);
    if (params.page !== undefined) query.append('page', params.page);
    if (params.page_size !== undefined) query.append('page_size', params.page_size);

    const queryString = query.toString();
    const url = queryString ? `${API_ENDPOINTS.LEADERBOARD}?${queryString}` : API_ENDPOINTS.LEADERBOARD;
    return this._fetchJson(url);
  }

  /**
   * GET /api/bowling/players/{player_id}
   */
  async getPlayerProfile(playerId) {
    if (!playerId) throw new Error('Player ID is required for getPlayerProfile');
    return this._fetchJson(API_ENDPOINTS.PLAYER_PROFILE(playerId));
  }

  async getBowlerProfile(playerId) {
    return this.getPlayerProfile(playerId);
  }

  /**
   * GET /api/bowling/compare?player_ids=p1,p2,...
   * @param {Array<number>} playerIds - between 2 and 5 IDs
   */
  async compareBowlers(playerIds) {
    if (!Array.isArray(playerIds) || playerIds.length < 2 || playerIds.length > 5) {
      throw new Error('Bowler comparison requires between 2 and 5 player IDs');
    }
    return this._fetchJson(API_ENDPOINTS.COMPARE(playerIds));
  }

  async getBowlerComparison(playerIds) {
    return this.compareBowlers(playerIds);
  }

  /**
   * GET /api/bowling/matches
   * @param {Object} params - { season, team, sort_by, order, page, page_size }
   */
  async getMatches(params = {}) {
    const query = new URLSearchParams();
    if (params.season && params.season !== 'all') query.append('season', params.season);
    if (params.team) query.append('team', params.team);
    if (params.sort_by) query.append('sort_by', params.sort_by);
    if (params.order) query.append('order', params.order);
    if (params.page !== undefined) query.append('page', params.page);
    if (params.page_size !== undefined) query.append('page_size', params.page_size);

    const queryString = query.toString();
    const url = queryString ? `${API_ENDPOINTS.MATCHES}?${queryString}` : API_ENDPOINTS.MATCHES;
    return this._fetchJson(url);
  }

  /**
   * GET /api/bowling/matches/{match_id}/spells
   */
  async getMatchSpells(matchId) {
    if (!matchId) throw new Error('Match ID is required for getMatchSpells');
    return this._fetchJson(API_ENDPOINTS.MATCH_SPELLS(matchId));
  }

  /**
   * GET /api/bowling/spells/{spell_id}/deliveries
   */
  async getSpellDeliveries(spellId) {
    if (!spellId) throw new Error('Spell ID is required for getSpellDeliveries');
    return this._fetchJson(API_ENDPOINTS.SPELL_DELIVERIES(spellId));
  }
}

export const bowlingApiService = new BowlingApiService();
