/**
 * CricImpact Phase 2 — Data Formatting & Display Utilities
 */

/**
 * Format legal deliveries into cricket overs notation (e.g. 23 balls -> '3.5').
 */
export function formatOvers(legalBalls) {
  if (legalBalls === null || legalBalls === undefined || isNaN(legalBalls)) return '—';
  const completed = Math.floor(legalBalls / 6);
  const remaining = legalBalls % 6;
  return `${completed}.${remaining}`;
}

/**
 * Format decimal overs to 1 decimal place string.
 */
export function formatOversDecimal(overs) {
  if (overs === null || overs === undefined || isNaN(overs)) return '—';
  return Number(overs).toFixed(1);
}

/**
 * Format economy rate with 2 decimal places.
 */
export function formatEconomy(econ) {
  if (econ === null || econ === undefined || isNaN(econ)) return '—';
  return Number(econ).toFixed(2);
}

/**
 * Format Bowling Contribution Score (BCS) in runs with optional '+' sign.
 */
export function formatBCS(bcs, includeSign = true) {
  if (bcs === null || bcs === undefined || isNaN(bcs)) return '—';
  const val = Number(bcs);
  const formatted = val.toFixed(2);
  if (includeSign && val > 0) return `+${formatted}`;
  return formatted;
}

/**
 * Format Bowler Win Probability Added (bWPA) with 4 decimal places.
 */
export function formatBWPA(bwpa) {
  if (bwpa === null || bwpa === undefined || isNaN(bwpa)) return '—';
  const val = Number(bwpa);
  const formatted = val.toFixed(4);
  if (val > 0) return `+${formatted}`;
  return formatted;
}

/**
 * Format percentage with 1 decimal place.
 */
export function formatPercent(val) {
  if (val === null || val === undefined || isNaN(val)) return '—';
  return `${Number(val).toFixed(1)}%`;
}

/**
 * Format rate (e.g. BCS per over) to 2 decimal places with optional '+' sign.
 */
export function formatRate(rate, includeSign = true) {
  if (rate === null || rate === undefined || isNaN(rate)) return '—';
  const val = Number(rate);
  const formatted = val.toFixed(2);
  if (includeSign && val > 0) return `+${formatted}`;
  return formatted;
}

/**
 * Format integer numbers with commas (e.g. 190,575).
 */
export function formatNumber(num) {
  if (num === null || num === undefined || isNaN(num)) return '—';
  return Number(num).toLocaleString('en-US');
}

/**
 * Safe string fallback for missing or null telemetry.
 */
export function safeValue(val, fallback = '—') {
  if (val === null || val === undefined || val === '') return fallback;
  return String(val);
}

/**
 * Get CSS badge classes based on numeric contribution sign.
 */
export function getContributionBadgeClass(val) {
  if (val === null || val === undefined || isNaN(val)) return 'badge-blue';
  const num = Number(val);
  if (num > 0) return 'badge-positive';
  if (num < 0) return 'badge-negative';
  return 'badge-blue';
}

/**
 * Format Bowling Pressure Contribution Score (PCS) on 0-100 scale.
 */
export function formatPCS(pcs) {
  if (pcs === null || pcs === undefined || isNaN(pcs)) return '—';
  return Number(pcs).toFixed(2);
}

/**
 * Get CSS badge classes based on PCS value (neutral 50.00).
 */
export function getPCSBadgeClass(val) {
  if (val === null || val === undefined || isNaN(val)) return 'bg-slate-100 text-slate-700 border border-slate-200';
  const num = Number(val);
  if (num > 50.00) return 'bg-emerald-50 text-emerald-700 border border-emerald-200';
  if (num < 50.00) return 'bg-rose-50 text-rose-700 border border-rose-200';
  return 'bg-slate-100 text-slate-700 border border-slate-200';
}
