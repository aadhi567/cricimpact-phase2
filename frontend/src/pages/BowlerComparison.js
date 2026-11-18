/**
 * CricImpact Phase 2 — Bowler Comparison Page
 * Head-to-head comparison of 2 to 5 bowlers across BCM and PCS.
 * Features Pink + Blue theme, Deep Navy PCS layer, side-by-side metric tables,
 * multi-attribute radar profiles, and comparative insights.
 */

import { bowlingApiService } from '../services/bowlingApiService.js';
import { pcsApiService } from '../services/pcsApiService.js';
import { CANONICAL_BOWLERS } from '../config/apiConfig.js';
import {
  formatOvers,
  formatEconomy,
  formatBCS,
  formatBWPA,
  formatPercent,
  formatRate,
  formatPCS,
  getPCSBadgeClass,
} from '../utils/formatting.js';
import { createBarChart, createRadarChart, createLineChart } from '../components/ContributionChart.js';
import { renderLoadingSkeleton } from '../components/LoadingSkeleton.js';
import { renderErrorState } from '../components/ErrorState.js';

// Consistent distinct palette for up to 5 comparison bowlers
const BOWLER_COLORS = [
  { main: '#3B82F6', light: '#EFF6FF', border: '#BFDBFE', text: 'text-blue-700', bg: 'bg-blue-50' },   // Bowler 1: Blue
  { main: '#EC4899', light: '#FDF2F8', border: '#FBCFE8', text: 'text-pink-700', bg: 'bg-pink-50' },   // Bowler 2: Pink
  { main: '#8B5CF6', light: '#F5F3FF', border: '#DDD6FE', text: 'text-purple-700', bg: 'bg-purple-50' }, // Bowler 3: Purple
  { main: '#10B981', light: '#ECFDF5', border: '#A7F3D0', text: 'text-emerald-700', bg: 'bg-emerald-50' }, // Bowler 4: Emerald
  { main: '#F59E0B', light: '#FFFBEB', border: '#FDE68A', text: 'text-amber-700', bg: 'bg-amber-50' },  // Bowler 5: Amber
];

export async function renderBowlerComparison(container, params = {}) {
  // Parse bowler IDs from query or use canonical trio (Rashid Khan, Jasprit Bumrah, Varun Chakravarthy)
  let initialIds = [4722, 2933, 6256];
  if (params.bowlers) {
    const parsed = params.bowlers
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n));
    if (parsed.length >= 1) initialIds = parsed.slice(0, 5);
  }

  container.innerHTML = `
    <div class="space-y-6">
      <div class="flex items-center space-x-2 text-sm text-slate-500 mb-2">
        <a href="#/bowling/dashboard" class="hover:text-blue-600">Bowling</a>
        <span>/</span>
        <span class="text-slate-800 font-medium">Head-to-Head Comparison</span>
      </div>
      ${renderLoadingSkeleton('table')}
    </div>
  `;

  await loadAndRenderComparison(container, initialIds);
}

async function loadAndRenderComparison(container, selectedIds) {
  try {
    const [bcmRes, pcsRes] = await Promise.all([
      bowlingApiService.getBowlerComparison(selectedIds),
      pcsApiService.compareBowlers(selectedIds).then((r) => r.data).catch((err) => {
        console.warn('[BowlerComparison] PCS comparison warning:', err);
        return null;
      }),
    ]);

    if (!bcmRes || !bcmRes.success || !bcmRes.data) {
      throw new Error(bcmRes?.error?.message || 'Failed to load comparison data');
    }

    const bowlers = bcmRes.data.bowlers || [];
    if (bowlers.length === 0) {
      throw new Error('No bowlers found for the selected IDs');
    }

    // Build lookup for PCS profiles by bowler_id
    const pcsMap = {};
    if (pcsRes && pcsRes.bowlers) {
      pcsRes.bowlers.forEach((p) => {
        pcsMap[p.bowler_id] = p;
      });
    }

    // Main layout
    container.innerHTML = `
      <div class="space-y-8 animate-fadeIn">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
          <div>
            <div class="flex items-center space-x-2 text-xs font-bold text-pink-600 uppercase tracking-wider mb-1">
              <span>Multi-Player Analytics</span>
              <span>&bull;</span>
              <span>BCM + PCS Layers</span>
            </div>
            <h1 class="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">Bowler Head-to-Head Comparison</h1>
            <p class="text-slate-500 text-sm mt-1">
              Compare career contribution (BCS runs), win probability added (bWPA), and match-context pressure generation (PCS).
            </p>
          </div>

          <!-- Quick Action: Reset to Canonical Trio -->
          <div class="flex items-center space-x-2">
            <button id="reset-canonical-btn" class="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors shadow-sm">
              Canonical Trio (Rashid, Bumrah, Varun)
            </button>
          </div>
        </div>

        <!-- Bowler Selector & Chips Bar -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div class="flex items-center space-x-2">
              <span class="text-sm font-bold text-slate-800">Selected Bowlers:</span>
              <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${bowlers.length >= 5 ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'}">
                ${bowlers.length} / 5 Selected
              </span>
            </div>

            <!-- Add Bowler Dropdown -->
            <div class="flex items-center space-x-2">
              <label for="add-bowler-select" class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Add Bowler:</label>
              <select id="add-bowler-select" class="text-sm bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-pink-500 focus:outline-none" ${bowlers.length >= 5 ? 'disabled' : ''}>
                <option value="">-- Choose to Add --</option>
                ${CANONICAL_BOWLERS.filter((b) => !selectedIds.includes(b.id)).map((b) => `
                  <option value="${b.id}">${b.name}</option>
                `).join('')}
              </select>
            </div>
          </div>

          <!-- Active Bowler Chips -->
          <div class="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100">
            ${bowlers.map((b, idx) => {
              const theme = BOWLER_COLORS[idx % BOWLER_COLORS.length];
              return `
                <div class="inline-flex items-center space-x-2 px-3 py-1 rounded-xl border text-xs font-semibold shadow-xs ${theme.bg} ${theme.text} ${theme.border}">
                  <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${theme.main};"></span>
                  <span>${b.bowler_name}</span>
                  ${bowlers.length > 2 ? `
                    <button class="remove-bowler-btn hover:opacity-75 transition-opacity ml-1 font-bold text-sm" data-id="${b.bowler_id}" title="Remove bowler">&times;</button>
                  ` : ''}
                </div>
              `;
            }).join('')}
          </div>
        </div>

        <!-- Comparative Metrics Table -->
        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div class="p-5 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 class="font-bold text-slate-900 text-sm">Side-by-Side Analytical Matrix</h3>
              <p class="text-xs text-slate-500">Cross-evaluating conventional stats, BCM runs/bWPA, and PCS pressure [0–100 scale]</p>
            </div>
            <span class="text-xs px-2.5 py-1 rounded-full font-bold bg-slate-100 text-slate-700">Comparative View</span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-600">
              <thead class="bg-slate-50 text-slate-700 font-bold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                <tr>
                  <th class="px-5 py-3 w-1/4">Metric Category</th>
                  ${bowlers.map((b, idx) => {
                    const theme = BOWLER_COLORS[idx % BOWLER_COLORS.length];
                    return `
                      <th class="px-4 py-3 text-center" style="border-top: 3px solid ${theme.main};">
                        <div class="font-extrabold text-sm ${theme.text}">${b.bowler_name}</div>
                        <div class="text-[10px] text-slate-400 font-normal">Rank #${b.career_summary.rank}</div>
                      </th>
                    `;
                  }).join('')}
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 font-mono text-[11px]">
                <!-- Conventional Stats Section -->
                <tr class="bg-slate-50/70 font-semibold text-slate-800 text-[10px] uppercase tracking-wider font-sans">
                  <td colspan="${bowlers.length + 1}" class="px-5 py-2">Conventional Statistics</td>
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Matches</td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center font-bold">${b.career_summary.matches}</td>`).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Overs Bowled</td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center">${b.career_summary.overs_formatted}</td>`).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Wickets</td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center font-black text-slate-900">${b.career_summary.wickets}</td>`).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Economy</td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center font-semibold text-slate-800">${formatEconomy(b.career_summary.economy)}</td>`).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Dot Ball %</td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center font-medium text-blue-600">${formatPercent(b.career_summary.dot_pct)}</td>`).join('')}
                </tr>

                <!-- BCM Contribution Section -->
                <tr class="bg-slate-50/70 font-semibold text-slate-800 text-[10px] uppercase tracking-wider font-sans">
                  <td colspan="${bowlers.length + 1}" class="px-5 py-2">BCM Contribution Analytics (Runs & Win Prob)</td>
                </tr>
                <tr class="bg-blue-50/20">
                  <td class="px-5 py-2.5 font-bold text-blue-900 font-sans">
                    <div>Total BCS (Raw)</div>
                    <div class="text-[10px] text-slate-400 font-normal">Cumulative runs value</div>
                  </td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center font-black text-blue-600 text-sm">${formatBCS(b.career_summary.total_bcs)}</td>`).join('')}
                </tr>
                <tr class="bg-pink-50/20">
                  <td class="px-5 py-2.5 font-bold text-pink-900 font-sans">
                    <div>Shrunk BCS</div>
                    <div class="text-[10px] text-slate-400 font-normal">Empirical Bayes normalized</div>
                  </td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center font-black text-pink-600 text-sm">${formatBCS(b.career_summary.total_bcs_shrunk ?? b.career_summary.shrunk_bcs)}</td>`).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">BCS / Over</td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center font-bold text-slate-800">${formatRate(b.career_summary.bcs_per_over)}</td>`).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Total bWPA</td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center font-bold ${b.career_summary.total_bwpa >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${formatBWPA(b.career_summary.total_bwpa)}</td>`).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Runs Prevented (ERP)</td>
                  ${bowlers.map((b) => `<td class="px-4 py-2.5 text-center font-medium text-blue-700">${formatBCS(b.career_summary.total_erp)}</td>`).join('')}
                </tr>

                <!-- PCS Pressure Analytics Section -->
                <tr class="bg-gradient-to-r from-[#1E3A8A]/10 to-transparent font-semibold text-[#1E3A8A] text-[10px] uppercase tracking-wider font-sans">
                  <td colspan="${bowlers.length + 1}" class="px-5 py-2">
                    ★ PCS Pressure Analytics (Bipolar 0–100 Scale, Neutral 50.00)
                  </td>
                </tr>
                <tr class="bg-[#1E3A8A]/5">
                  <td class="px-5 py-2.5 font-bold text-[#1E3A8A] font-sans">
                    <div>Career Shrunk PCS</div>
                    <div class="text-[10px] text-slate-400 font-normal">Stabilized match pressure</div>
                  </td>
                  ${bowlers.map((b) => {
                    const p = pcsMap[b.bowler_id] || {};
                    const val = p.pcs_career_shrunk ?? p.career_summary?.pcs_career_shrunk;
                    return `
                      <td class="px-4 py-2.5 text-center font-black text-[#1E3A8A] text-sm">
                        ${formatPCS(val)}
                      </td>
                    `;
                  }).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Career Raw PCS</td>
                  ${bowlers.map((b) => {
                    const p = pcsMap[b.bowler_id] || {};
                    const val = p.pcs_career_raw ?? p.career_summary?.pcs_career_raw;
                    return `<td class="px-4 py-2.5 text-center font-mono text-slate-600">${formatPCS(val)}</td>`;
                  }).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Average Spell PCS</td>
                  ${bowlers.map((b) => {
                    const p = pcsMap[b.bowler_id] || {};
                    return `<td class="px-4 py-2.5 text-center font-mono font-bold text-[#1E3A8A]">${formatPCS(p.avg_spell_pcs)}</td>`;
                  }).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Best Spell PCS</td>
                  ${bowlers.map((b) => {
                    const p = pcsMap[b.bowler_id] || {};
                    return `<td class="px-4 py-2.5 text-center font-mono font-bold text-emerald-700">${formatPCS(p.best_spell_pcs)}</td>`;
                  }).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Total Runs Pressure Equiv (RPE)</td>
                  ${bowlers.map((b) => {
                    const p = pcsMap[b.bowler_id] || {};
                    const val = p.total_rpe ?? p.career_summary?.total_rpe;
                    return `<td class="px-4 py-2.5 text-center font-bold ${val >= 0 ? 'text-blue-700' : 'text-rose-700'}">${val !== undefined && val !== null ? (val >= 0 ? '+' : '') + val.toFixed(2) : '—'}</td>`;
                  }).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Positive Pressure Spells</td>
                  ${bowlers.map((b) => {
                    const p = pcsMap[b.bowler_id] || {};
                    const val = p.positive_spells_pct ?? p.tactical_breakdown?.positive_spells_pct;
                    const cnt = p.positive_spells_count;
                    return `<td class="px-4 py-2.5 text-center font-semibold text-emerald-600">${cnt !== undefined ? `${cnt} (${formatPercent(val)})` : formatPercent(val)}</td>`;
                  }).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Negative Leakage Spells</td>
                  ${bowlers.map((b) => {
                    const p = pcsMap[b.bowler_id] || {};
                    const val = p.negative_spells_pct ?? p.tactical_breakdown?.negative_spells_pct;
                    const cnt = p.negative_spells_count;
                    return `<td class="px-4 py-2.5 text-center font-semibold text-rose-600">${cnt !== undefined ? `${cnt} (${formatPercent(val)})` : formatPercent(val)}</td>`;
                  }).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Stand Suppression (Mean Sup)</td>
                  ${bowlers.map((b) => {
                    const p = pcsMap[b.bowler_id] || {};
                    const val = p.avg_sup ?? p.tactical_breakdown?.mean_sup;
                    return `<td class="px-4 py-2.5 text-center font-mono text-slate-700">${val !== undefined && val !== null ? '+' + Number(val).toFixed(2) : '—'}</td>`;
                  }).join('')}
                </tr>
                <tr>
                  <td class="px-5 py-2.5 font-medium text-slate-800 font-sans">Situational Wicket Threat (Mean SWI)</td>
                  ${bowlers.map((b) => {
                    const p = pcsMap[b.bowler_id] || {};
                    const val = p.avg_swi ?? p.tactical_breakdown?.mean_swi;
                    return `<td class="px-4 py-2.5 text-center font-mono text-slate-700">${val !== undefined && val !== null ? Number(val).toFixed(2) : '—'}</td>`;
                  }).join('')}
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Comparative Visualizations: Grouped Bar & Radar -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- PCS Comparison Bar Chart (0-100 scale) -->
          <div class="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="font-bold text-slate-900 text-sm">Pressure Contribution Score (PCS)</h3>
                <p class="text-xs text-slate-500">Career Shrunk PCS on the bipolar 0–100 scale (50 = neutral)</p>
              </div>
              <span class="text-xs px-2.5 py-1 rounded font-bold bg-[#1E3A8A] text-white">PCS Scale</span>
            </div>
            <div class="relative flex-1 min-h-[260px]">
              <canvas id="pcs-comparison-bar-chart"></canvas>
            </div>
          </div>

          <!-- Multi-Dimensional Radar Profile -->
          <div class="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="font-bold text-slate-900 text-sm">Multi-Dimensional Profile Radar</h3>
                <p class="text-xs text-slate-500">Normalized across 5 independent analytical dimensions</p>
              </div>
              <span class="text-xs px-2 py-0.5 rounded font-semibold bg-slate-100 text-slate-700">Dimensions</span>
            </div>
            <div class="relative flex-1 min-h-[260px]">
              <canvas id="radar-comparison-chart"></canvas>
            </div>
          </div>

          <!-- Season PCS Trend Comparison (Section 9) -->
          <div class="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="font-bold text-slate-900 text-sm">Season PCS Trend Comparison</h3>
                <p class="text-xs text-slate-500">Season-by-season Empirical Bayes Shrunk PCS vs 50.00 neutral anchor</p>
              </div>
              <span class="text-xs px-2.5 py-1 rounded font-bold bg-[#EFF6FF] text-[#1E3A8A] border border-[#BFDBFE]">Season Trend</span>
            </div>
            <div class="relative flex-1 min-h-[260px]">
              <canvas id="pcs-season-trend-comparison-chart"></canvas>
            </div>
          </div>

          <!-- Positive vs Negative Pressure Spell Distribution (Section 9) -->
          <div class="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="font-bold text-slate-900 text-sm">Positive vs Negative Pressure Spells</h3>
                <p class="text-xs text-slate-500">Share of spells generating positive pressure (&gt;50) vs pressure leakage (&lt;50)</p>
              </div>
              <span class="text-xs px-2.5 py-1 rounded font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Spell Split</span>
            </div>
            <div class="relative flex-1 min-h-[260px]">
              <canvas id="pcs-posneg-comparison-chart"></canvas>
            </div>
          </div>
        </div>

        <!-- Analytical Independence Note -->
        <div class="p-4 rounded-xl bg-[#F8FAFC] border border-[#CBD5E1] text-xs text-slate-600">
          <strong class="text-[#1E3A8A]">Metric Independence:</strong> BCS (runs-equivalent), bWPA (win probability), and PCS (0–100 pressure control) are independent dimensions. CricImpact never combines them into a single blended score or automatically declares one bowler superior from PCS alone.
        </div>

        <!-- Phase Comparison Cards -->
        <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 class="text-base font-bold text-slate-900">Phase Specialization Breakdown</h3>
              <p class="text-xs text-slate-500">Comparison of overs bowled and BCS generated per phase</p>
            </div>
            <div class="flex items-center space-x-2 text-xs">
              <span class="inline-flex items-center px-2 py-0.5 rounded font-semibold bg-blue-100 text-blue-800">Powerplay</span>
              <span class="inline-flex items-center px-2 py-0.5 rounded font-semibold bg-pink-100 text-pink-800">Middle</span>
              <span class="inline-flex items-center px-2 py-0.5 rounded font-semibold bg-indigo-100 text-indigo-800">Death</span>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            ${['Powerplay', 'Middle', 'Death'].map((phase) => `
              <div class="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
                <div class="font-bold text-slate-900 text-sm border-b border-slate-200 pb-1.5 flex items-center justify-between">
                  <span>${phase}</span>
                  <span class="text-[10px] text-slate-400 font-normal">Overs / Econ / BCS</span>
                </div>
                <div class="space-y-2">
                  ${bowlers.map((b, idx) => {
                    const theme = BOWLER_COLORS[idx % BOWLER_COLORS.length];
                    const ps = (b.phase_splits || []).find((p) => p.phase.toLowerCase() === phase.toLowerCase()) || {};
                    return `
                      <div class="flex items-center justify-between text-xs">
                        <span class="font-semibold ${theme.text}">${b.bowler_name}</span>
                        <span class="text-slate-600 font-mono">${ps.overs_formatted || '0.0'} ov | <strong class="text-slate-900">${formatEconomy(ps.economy)}</strong> | <span class="font-bold text-blue-600">${formatBCS(ps.total_bcs || 0)}</span></span>
                      </div>
                    `;
                  }).join('')}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;

    // Setup interactive handlers
    setupComparisonListeners(container, selectedIds);

    // Render comparative charts
    renderComparisonCharts(bowlers, pcsMap);

  } catch (error) {
    container.innerHTML = renderErrorState({
      title: 'Comparison Error',
      message: error.message || 'Unable to load bowler comparison data.',
      onRetry: `window.location.reload()`,
    });
  }
}

function setupComparisonListeners(container, selectedIds) {
  // Add Bowler select handler
  const addSelect = container.querySelector('#add-bowler-select');
  if (addSelect) {
    addSelect.addEventListener('change', (e) => {
      const newId = parseInt(e.target.value, 10);
      if (newId && !selectedIds.includes(newId) && selectedIds.length < 5) {
        const nextIds = [...selectedIds, newId];
        window.location.hash = `#/bowling/compare?bowlers=${nextIds.join(',')}`;
      }
    });
  }

  // Remove Bowler button handler
  container.querySelectorAll('.remove-bowler-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const idToRemove = parseInt(btn.getAttribute('data-id'), 10);
      if (idToRemove && selectedIds.length > 2) {
        const nextIds = selectedIds.filter((id) => id !== idToRemove);
        window.location.hash = `#/bowling/compare?bowlers=${nextIds.join(',')}`;
      }
    });
  });

  // Reset to Canonical Trio
  const resetBtn = container.querySelector('#reset-canonical-btn');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      window.location.hash = `#/bowling/compare?bowlers=4722,2933,6256`;
    });
  }
}

function renderComparisonCharts(bowlers, pcsMap) {
  // 1. PCS Bar Chart (Bipolar 0–100 scale)
  const pcsBarCtx = document.getElementById('pcs-comparison-bar-chart');
  if (pcsBarCtx && bowlers.length > 0) {
    createBarChart(
      pcsBarCtx,
      {
        labels: bowlers.map((b) => b.bowler_name),
        datasets: [
          {
            label: 'Career Shrunk PCS',
            data: bowlers.map((b) => {
              const p = pcsMap[b.bowler_id];
              return p?.pcs_career_shrunk ?? p?.career_summary?.pcs_career_shrunk ?? 50.0;
            }),
            backgroundColor: bowlers.map((b, idx) => BOWLER_COLORS[idx % BOWLER_COLORS.length].main),
            borderRadius: 6,
          },
        ],
      },
      {
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: {
            min: 40,
            max: 75,
            title: { display: true, text: 'PCS Score [0–100 Scale, 50=Neutral]', font: { size: 10 } },
            grid: { color: '#F1F5F9' },
          },
        },
      }
    );
  }

  // 2. Multi-Attribute Radar Chart
  const radarCtx = document.getElementById('radar-comparison-chart');
  if (radarCtx && bowlers.length > 0) {
    // 5 Dimensions:
    // 1. Run Prevention (ERP normalized)
    // 2. Wicket Threat (WQM)
    // 3. Situational Pressure (Leverage)
    // 4. Pressure Contribution (PCS normalized)
    // 5. Containment (Dot %)
    const dimensions = [
      'Run Prevention (ERP)',
      'Wicket Threat (WQM)',
      'Leverage Resistance',
      'Pressure Gen (PCS)',
      'Dot Containment',
    ];

    const radarDatasets = bowlers.map((b, idx) => {
      const theme = BOWLER_COLORS[idx % BOWLER_COLORS.length];
      const c = b.career_summary;
      const pcs = pcsMap[b.bowler_id];
      const pcsVal = pcs?.pcs_career_shrunk ?? pcs?.career_summary?.pcs_career_shrunk;

      // Safe normalization
      const erpScore = Math.min(100, Math.max(20, 50 + (c.total_erp || 0) * 0.15));
      const wqmScore = Math.min(100, Math.max(20, ((c.mean_wqm || 1.0) / 1.5) * 80));
      const levScore = Math.min(100, Math.max(20, ((c.mean_leverage || 1.0) / 1.5) * 80));
      const pcsScore = Math.min(100, Math.max(20, pcsVal || 50));
      const dotScore = Math.min(100, Math.max(20, ((c.dot_pct || 40) / 60) * 100));

      return {
        label: b.bowler_name,
        data: [erpScore, wqmScore, levScore, pcsScore, dotScore],
        backgroundColor: `${theme.main}20`,
        borderColor: theme.main,
        borderWidth: 2,
        pointBackgroundColor: theme.main,
        pointRadius: 3,
      };
    });

    createRadarChart(
      radarCtx,
      {
        labels: dimensions,
        datasets: radarDatasets,
      },
      {
        scales: {
          r: {
            min: 20,
            max: 100,
            ticks: { display: false },
            grid: { color: '#E2E8F0' },
          },
        },
      }
    );
  }

  // 3. Season PCS Trend Comparison Line Chart
  const seasonTrendCtx = document.getElementById('pcs-season-trend-comparison-chart');
  if (seasonTrendCtx && bowlers.length > 0) {
    const seasonSet = new Set();
    bowlers.forEach((b) => {
      const p = pcsMap[b.bowler_id];
      (p?.seasons_data || []).forEach((s) => seasonSet.add(String(s.season)));
    });
    const allSeasons = Array.from(seasonSet).sort();
    if (allSeasons.length > 0) {
      const datasets = bowlers.map((b, idx) => {
        const theme = BOWLER_COLORS[idx % BOWLER_COLORS.length];
        const p = pcsMap[b.bowler_id];
        const byYr = Object.fromEntries((p?.seasons_data || []).map((s) => [String(s.season), s.pcs_shrunk]));
        return {
          label: b.bowler_name,
          data: allSeasons.map((yr) => (byYr[yr] !== undefined ? byYr[yr] : null)),
          borderColor: theme.main,
          backgroundColor: 'transparent',
          borderWidth: 2.5,
          pointRadius: 4,
          spanGaps: true,
          tension: 0.25,
        };
      });
      datasets.push({
        label: 'Neutral Anchor (50.00)',
        data: allSeasons.map(() => 50.0),
        borderColor: '#94A3B8',
        borderDash: [5, 5],
        pointRadius: 0,
        borderWidth: 1.25,
      });

      createLineChart(
        seasonTrendCtx,
        { labels: allSeasons, datasets },
        {
          scales: {
            y: {
              min: 35,
              max: 75,
              title: { display: true, text: 'Season Shrunk PCS [0–100]', font: { size: 10 } },
              grid: { color: '#F1F5F9' },
            },
          },
        }
      );
    }
  }

  // 4. Positive vs Negative Pressure Spell Distribution Grouped Bar Chart
  const posNegCtx = document.getElementById('pcs-posneg-comparison-chart');
  if (posNegCtx && bowlers.length > 0) {
    createBarChart(
      posNegCtx,
      {
        labels: bowlers.map((b) => b.bowler_name),
        datasets: [
          {
            label: 'Positive Pressure Spells (%)',
            data: bowlers.map((b) => pcsMap[b.bowler_id]?.positive_spells_pct ?? 0),
            backgroundColor: '#16A34A',
            borderRadius: 5,
          },
          {
            label: 'Negative Leakage Spells (%)',
            data: bowlers.map((b) => pcsMap[b.bowler_id]?.negative_spells_pct ?? 0),
            backgroundColor: '#DC2626',
            borderRadius: 5,
          },
        ],
      },
      {
        scales: {
          y: {
            min: 0,
            max: 100,
            title: { display: true, text: 'Percentage of Spells (%)', font: { size: 10 } },
            grid: { color: '#F1F5F9' },
          },
        },
      }
    );
  }
}
