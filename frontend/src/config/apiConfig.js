/**
 * CricImpact Phase 2 — API Configuration & Constants
 */

// Optional backend origin override for split frontend (Vercel) / backend (Render) deployments.
// Defaults to '' (same-origin relative /api/* paths) so local FastAPI & proxied deploys work unchanged.
const _rawApiOrigin =
  typeof window !== 'undefined' && typeof window.__CRICIMPACT_API_BASE__ === 'string'
    ? window.__CRICIMPACT_API_BASE__.trim()
    : '';
export const API_ORIGIN = _rawApiOrigin.replace(/\/+$/, '');

export const API_BASE = `${API_ORIGIN}/api/bowling`;
export const PCS_BASE = `${API_ORIGIN}/api/pcs`;
export const BATTING_BASE = `${API_ORIGIN}/api/batting`;
export const PRI_BASE = `${API_ORIGIN}/api/pri`;

export const API_ENDPOINTS = {
  HEALTH: `${API_ORIGIN}/health`,
  BOWLING_HEALTH: `${API_ORIGIN}/api/health`,
  DASHBOARD: `${API_BASE}/dashboard`,
  LEADERBOARD: `${API_BASE}/leaderboard`,
  PLAYER_PROFILE: (playerId) => `${API_BASE}/players/${playerId}`,
  COMPARE: (playerIds) => `${API_BASE}/compare?player_ids=${playerIds.join(',')}`,
  MATCHES: `${API_BASE}/matches`,
  MATCH_SPELLS: (matchId) => `${API_BASE}/matches/${matchId}/spells`,
  SPELL_DELIVERIES: (spellId) => `${API_BASE}/spells/${spellId}/deliveries`,
  TOURNAMENTS: `${API_BASE}/tournaments`,
};

export const PCS_API_ENDPOINTS = {
  HEALTH: `${PCS_BASE}/health`,
  DASHBOARD: `${PCS_BASE}/dashboard`,
  LEADERBOARD: `${PCS_BASE}/leaderboard`,
  PLAYER_PROFILE: (playerId) => `${PCS_BASE}/players/${playerId}`,
  COMPARE: (playerIds) => `${PCS_BASE}/compare?bowlers=${playerIds.join(',')}`,
  MATCHES: `${PCS_BASE}/matches`,
  MATCH_DETAIL: (matchId) => `${PCS_BASE}/matches/${matchId}`,
  SPELL_DELIVERIES: (spellId) => `${PCS_BASE}/spells/${spellId}/deliveries`,
  TOURNAMENTS: `${PCS_BASE}/tournaments`,
};

export const BATTING_API_ENDPOINTS = {
  HEALTH: `${BATTING_BASE}/health`,
  FILTERS: `${BATTING_BASE}/filters`,
  DASHBOARD: `${BATTING_BASE}/dashboard`,
  EXPLORER: `${BATTING_BASE}/explorer`,
  PLAYERS: `${BATTING_BASE}/players`,
  PLAYER_PROFILE: (name) => `${BATTING_BASE}/players/${encodeURIComponent(name)}`,
  COMPARE: (names) => `${BATTING_BASE}/compare?players=${names.map((n) => encodeURIComponent(n)).join(',')}`,
  MATCHES: `${BATTING_BASE}/matches`,
  MATCH_DETAIL: (matchId) => `${BATTING_BASE}/matches/${encodeURIComponent(matchId)}`,
};

export const PRI_API_ENDPOINTS = {
  HEALTH: `${PRI_BASE}/health`,
  OVERVIEW: `${PRI_BASE}/overview`,
  FILTERS: `${PRI_BASE}/filters`,
  BATTING_CAREER: `${PRI_BASE}/batting/career`,
  BATTING_SEASON: `${PRI_BASE}/batting/season`,
  BATTING_TOURNAMENT: `${PRI_BASE}/batting/tournament`,
  BOWLING_CAREER: `${PRI_BASE}/bowling/career`,
  BOWLING_SEASON: `${PRI_BASE}/bowling/season`,
  BOWLING_TOURNAMENT: `${PRI_BASE}/bowling/tournament`,
  BATTING_PLAYER: (playerId) => `${PRI_BASE}/batting/players/${encodeURIComponent(playerId)}`,
  BOWLING_PLAYER: (playerId) => `${PRI_BASE}/bowling/players/${encodeURIComponent(playerId)}`,
  BATTING_COMPARE: (ids) => `${PRI_BASE}/batting/compare?player_ids=${ids.join(',')}`,
  BOWLING_COMPARE: (ids) => `${PRI_BASE}/bowling/compare?player_ids=${ids.join(',')}`,
};

export const CANONICAL_BOWLERS = [
  { id: 4722, name: 'Rashid Khan', country: 'Afghanistan' },
  { id: 6464, name: 'Arshdeep Singh', country: 'India' },
  { id: 6256, name: 'Varun Chakravarthy', country: 'India' },
  { id: 360, name: 'Bhuvneshwar Kumar', country: 'India' },
  { id: 2876, name: 'Axar Patel', country: 'India' },
  { id: 2933, name: 'Jasprit Bumrah', country: 'India' },
];

export const APP_METADATA = {
  TITLE: 'CricImpact Phase 2',
  SUBTITLE: 'Integrated Batting & Bowling Contextual Contribution Analytics',
  VERSION: '1.0.0',
  CORPUS_SUMMARY: {
    MATCHES: 798,
    DELIVERIES: 190575,
    SPELLS: 9482,
    BOWLERS: 638,
    WICKETS: 9662,
    SEASONS: '2022 – 2026',
  },
};
