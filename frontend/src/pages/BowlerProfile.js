/**
 * CricImpact Phase 2 — Bowler Profile Page
 * Deep-dive career and season contribution analytics for an individual bowler.
 * Integrates BCM (BCS, bWPA, ERP, WQM) and PCS (Pressure Contribution Score).
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
  formatNumber,
  formatRate,
  formatPCS,
  getPCSBadgeClass,
} from '../utils/formatting.js';
import { renderMetricCard } from '../components/MetricCard.js';
import { createBarChart, createLineChart, createDoughnutChart } from '../components/ContributionChart.js';
import { renderPhaseBreakdown } from '../components/PhaseBreakdown.js';
import { renderLoadingSkeleton } from '../components/LoadingSkeleton.js';
import { renderErrorState } from '../components/ErrorState.js';

export async function renderBowlerProfile(container, params = {}) {
  const bowlerId = params.id ? parseInt(params.id, 10) : CANONICAL_BOWLERS[0].id; // Default to Rashid Khan (4722)

  // Show loading skeleton
  container.innerHTML = `
    <div class="space-y-6">
      <div class="flex items-center space-x-2 text-sm text-slate-500 mb-2">
        <a href="#/bowling/leaderboard" class="hover:text-blue-600">Bowling Leaderboard</a>
        <span>/</span>
        <span class="text-slate-800 font-medium">Bowler Profile</span>
      </div>
      ${renderLoadingSkeleton('profile')}
    </div>
  `;

  try {
    const [bcmRes, pcsData] = await Promise.all([
      bowlingApiService.getBowlerProfile(bowlerId),
      pcsApiService.getPlayerProfile(bowlerId).then((r) => r.data).catch((err) => {
        console.warn('[BowlerProfile] PCS fetch warning:', err);
        return null;
      }),
    ]);

    if (!bcmRes || !bcmRes.success || !bcmRes.data) {
      throw new Error(bcmRes?.error?.message || 'Bowler profile not found');
    }

    const data = bcmRes.data;
    const c = data.career_summary;

    // Render complete profile
    container.innerHTML = `
      <div class="space-y-8 animate-fadeIn">
        <!-- Breadcrumbs & Quick Bowler Switcher -->
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
          <div class="flex items-center space-x-2 text-sm text-slate-500">
            <a href="#/bowling/dashboard" class="hover:text-pink-600 transition-colors">Bowling</a>
            <span>/</span>
            <a href="#/bowling/leaderboard" class="hover:text-pink-600 transition-colors">Leaderboard</a>
            <span>/</span>
            <span class="text-slate-900 font-semibold">${data.bowler_name}</span>
          </div>

          <div class="flex items-center space-x-2 self-end sm:self-auto">
            <label for="bowler-quick-select" class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Quick Switch:</label>
            <select id="bowler-quick-select" class="text-sm bg-white border border-slate-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-pink-500 focus:outline-none">
              ${CANONICAL_BOWLERS.map((b) => `
                <option value="${b.id}" ${b.id === bowlerId ? 'selected' : ''}>${b.name}</option>
              `).join('')}
            </select>
          </div>
        </div>

        <!-- Bowler Hero Header -->
        <div class="bg-white rounded-2xl p-6 sm:p-8 shadow-sm border border-slate-200 relative overflow-hidden">
          <div class="absolute -top-12 -right-12 w-48 h-48 bg-gradient-to-br from-pink-100 to-blue-100 rounded-full blur-2xl opacity-60 pointer-events-none"></div>
          
          <div class="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div class="space-y-3">
              <div class="flex flex-wrap items-center gap-3">
                <h1 class="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">${data.bowler_name}</h1>
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
                  ID: ${data.bowler_id}
                </span>
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-pink-50 text-pink-700 border border-pink-200">
                  Rank #${c.rank} Overall
                </span>
                ${(() => {
                  const pc = pcsData?.career || pcsData?.career_summary;
                  if (!pc) return '';
                  return `
                    <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-[#1E3A8A] text-white shadow-xs">
                      PCS: ${formatPCS(pc.pcs_career_shrunk)} (Rank #${pc.rank || '—'})
                    </span>
                  `;
                })()}
              </div>
              <p class="text-slate-600 text-sm max-w-2xl">
                Independent Bowling Contribution Model (BCM) career evaluation across ${c.matches} matches and ${c.overs_formatted} overs.
              </p>
            </div>

            <!-- Header Quick Stats Pill -->
            <div class="grid grid-cols-3 sm:grid-cols-4 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200 text-center">
              <div>
                <div class="text-xs text-slate-500 font-semibold uppercase">Matches</div>
                <div class="text-lg font-bold text-slate-800">${c.matches}</div>
              </div>
              <div>
                <div class="text-xs text-slate-500 font-semibold uppercase">Overs</div>
                <div class="text-lg font-bold text-slate-800 font-mono">${c.overs_formatted}</div>
              </div>
              <div>
                <div class="text-xs text-slate-500 font-semibold uppercase">Wickets</div>
                <div class="text-lg font-bold text-slate-800">${c.wickets}</div>
              </div>
              <div class="hidden sm:block">
                <div class="text-xs text-slate-500 font-semibold uppercase">Economy</div>
                <div class="text-lg font-bold text-slate-800 font-mono">${formatEconomy(c.economy)}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- BCM Contribution Telemetry (6 Core Cards) -->
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
              <span class="w-3 h-3 rounded-full bg-[#EC4899]"></span>
              <span>BCM Career Contribution Scorecard</span>
            </h2>
            <span class="text-xs text-slate-500">Dual-Scale Architecture (Runs vs Win Probability)</span>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            ${renderMetricCard({
              title: 'Total BCS (Raw)',
              value: formatBCS(c.total_bcs),
              subtitle: 'Cumulative runs value',
              accent: 'blue',
              badge: 'Raw Contribution',
              tooltip: 'Unshrunk cumulative runs saved above expectation across career.',
            })}

            ${renderMetricCard({
              title: 'Shrunk BCS',
              value: formatBCS(c.total_bcs_shrunk ?? c.shrunk_bcs),
              subtitle: 'Empirical Bayes (M0=48b)',
              accent: 'pink',
              badge: 'Stabilized Impact',
              tooltip: 'Regressed toward corpus prior to prevent small-sample distortion.',
            })}

            ${renderMetricCard({
              title: 'BCS / Over',
              value: formatRate(c.bcs_per_over),
              subtitle: 'Runs saved per 6 balls',
              accent: 'blue',
              badge: 'Efficiency',
              tooltip: 'Rate metric: raw BCS divided by overs bowled.',
            })}

            ${renderMetricCard({
              title: 'Shrunk BCS / Over',
              value: formatRate(c.shrunk_bcs_per_over),
              subtitle: 'Shrunk runs per 6 balls',
              accent: 'pink',
              badge: 'Rate Impact',
              tooltip: 'Bayes-stabilized efficiency rate for cross-sample fairness.',
            })}

            ${renderMetricCard({
              title: 'Total bWPA',
              value: formatBWPA(c.total_bwpa),
              subtitle: 'Win Probability Added',
              accent: c.total_bwpa >= 0 ? 'green' : 'red',
              badge: 'Win Impact',
              tooltip: 'Sum of delivery-level bowler win probability changes. Plotted strictly on separate [-1, +1] scale.',
            })}

            ${renderMetricCard({
              title: 'Runs Prevented (ERP)',
              value: formatBCS(c.total_erp),
              subtitle: 'Expected vs actual runs',
              accent: 'blue',
              badge: 'Run Prevention',
              tooltip: 'Total expected runs prevented based on venue and match situation baselines.',
            })}
          </div>
        </div>

        <!-- Metric Explanation Callout -->
        <div class="bg-gradient-to-r from-blue-50/60 to-pink-50/60 rounded-xl p-4 border border-slate-200/80 text-xs text-slate-700 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <div class="flex items-center space-x-2">
            <span class="flex-shrink-0 w-2 h-2 rounded-full bg-pink-500"></span>
            <span><strong>Model Architecture Insight:</strong> BCS evaluates bowling on a runs scale through Expected Runs Prevented (ERP) + context-dependent Wicket Value weighted by match leverage. bWPA evaluates direct Win Probability shifts. They are complementary, never combined into a single axis.</span>
          </div>
          <a href="#/bowling/compare?bowlers=${c.bowler_id}" class="text-pink-600 hover:text-pink-700 font-semibold flex-shrink-0 flex items-center space-x-1">
            <span>Compare Bowler</span>
            <span>&rarr;</span>
          </a>
        </div>

        <!-- Charts Section: Season Progression & Phase Splits -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Season BCS Trend -->
          <div class="bg-white rounded-xl p-5 border border-slate-200 shadow-sm flex flex-col">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="font-bold text-slate-900 text-sm">Season BCS Progression</h3>
                <p class="text-xs text-slate-500">Total Bowling Contribution Score by season</p>
              </div>
              <span class="text-xs px-2 py-0.5 rounded font-semibold bg-blue-50 text-blue-700 border border-blue-200">Runs Scale</span>
            </div>
            <div class="relative flex-1 min-h-[220px]">
              <canvas id="season-bcs-chart"></canvas>
            </div>
          </div>

          <!-- Season bWPA Trend -->
          <div class="bg-white rounded-xl p-5 border border-slate-200 shadow-sm flex flex-col">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="font-bold text-slate-900 text-sm">Season bWPA Progression</h3>
                <p class="text-xs text-slate-500">Win Probability Added by season (Dual axis separation)</p>
              </div>
              <span class="text-xs px-2 py-0.5 rounded font-semibold bg-pink-50 text-pink-700 border border-pink-200">Probability Scale</span>
            </div>
            <div class="relative flex-1 min-h-[220px]">
              <canvas id="season-bwpa-chart"></canvas>
            </div>
          </div>

          <!-- Phase Share Doughnut -->
          <div class="bg-white rounded-xl p-5 border border-slate-200 shadow-sm flex flex-col">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="font-bold text-slate-900 text-sm">Phase Contribution Share</h3>
                <p class="text-xs text-slate-500">BCS distribution across match phases</p>
              </div>
              <span class="text-xs px-2 py-0.5 rounded font-semibold bg-slate-100 text-slate-700">Splits</span>
            </div>
            <div class="relative flex-1 min-h-[220px]">
              <canvas id="phase-doughnut-chart"></canvas>
            </div>
          </div>
        </div>

        <!-- Phase Performance Breakdown -->
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-bold text-slate-900">Innings Phase Performance Breakdown</h2>
            <p class="text-xs text-slate-500">Powerplay (Blue), Middle (Pink), Death (Deep Blue)</p>
          </div>
          ${renderPhaseBreakdown(data.phase_splits)}
        </div>

        <!-- ========================================================================= -->
        <!-- DEDICATED SECTION: Pressure Contribution Score (PCS) Profile Analytics   -->
        <!-- ========================================================================= -->
        ${pcsData ? renderPCSProfileSection(pcsData) : ''}

        <!-- Match Spells Tables (Top 5 Impact & Recent 5) -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Top 5 Impact Spells -->
          <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
            <div class="p-5 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
              <div>
                <h3 class="font-bold text-slate-900 text-sm">Top 5 Impact Match Spells (BCM)</h3>
                <p class="text-xs text-slate-500">Ranked by single-match Bowling Contribution Score (BCS)</p>
              </div>
              <span class="text-xs px-2.5 py-1 rounded-full font-bold bg-blue-100 text-blue-800">Peak Performance</span>
            </div>
            <div class="overflow-x-auto flex-1">
              <table class="w-full text-left text-xs text-slate-600">
                <thead class="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    <th class="px-4 py-2.5">Date / Match</th>
                    <th class="px-3 py-2.5">Opponent</th>
                    <th class="px-3 py-2.5 text-center">Overs</th>
                    <th class="px-3 py-2.5 text-center">W-R</th>
                    <th class="px-3 py-2.5 text-right">Econ</th>
                    <th class="px-3 py-2.5 text-right font-bold text-blue-700">BCS</th>
                    <th class="px-3 py-2.5 text-right">bWPA</th>
                    <th class="px-3 py-2.5 text-center">Action</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  ${(data.top_spells || []).slice(0, 5).map((spell) => `
                    <tr class="hover:bg-blue-50/30 transition-colors">
                      <td class="px-4 py-2.5 whitespace-nowrap">
                        <div class="font-medium text-slate-800">${spell.match_date || 'Match ' + spell.match_id}</div>
                        <div class="text-[10px] text-slate-400">Match #${spell.match_id}</div>
                      </td>
                      <td class="px-3 py-2.5 font-medium text-slate-700">${spell.opponent || 'N/A'}</td>
                      <td class="px-3 py-2.5 text-center">${spell.overs_formatted || formatOvers(spell.legal_balls)}</td>
                      <td class="px-3 py-2.5 text-center font-bold text-slate-900">${spell.wickets}/${spell.bowler_runs}</td>
                      <td class="px-3 py-2.5 text-right">${formatEconomy(spell.economy)}</td>
                      <td class="px-3 py-2.5 text-right font-bold text-blue-600">${formatBCS(spell.total_bcs)}</td>
                      <td class="px-3 py-2.5 text-right ${spell.total_bwpa >= 0 ? 'text-emerald-600' : 'text-rose-600'} font-medium">
                        ${formatBWPA(spell.total_bwpa)}
                      </td>
                      <td class="px-3 py-2.5 text-center">
                        <a href="#/bowling/match/${spell.match_id}" class="text-blue-600 hover:text-blue-800 font-semibold hover:underline">
                          View &rarr;
                        </a>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>

          <!-- Recent 5 Match Spells -->
          <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
            <div class="p-5 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
              <div>
                <h3 class="font-bold text-slate-900 text-sm">Recent Match Spells (BCM)</h3>
                <p class="text-xs text-slate-500">Most recent chronological appearances</p>
              </div>
              <span class="text-xs px-2.5 py-1 rounded-full font-bold bg-pink-100 text-pink-800">Form Analysis</span>
            </div>
            <div class="overflow-x-auto flex-1">
              <table class="w-full text-left text-xs text-slate-600">
                <thead class="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    <th class="px-4 py-2.5">Date / Match</th>
                    <th class="px-3 py-2.5">Opponent</th>
                    <th class="px-3 py-2.5 text-center">Overs</th>
                    <th class="px-3 py-2.5 text-center">W-R</th>
                    <th class="px-3 py-2.5 text-right">Econ</th>
                    <th class="px-3 py-2.5 text-right font-bold text-pink-700">BCS</th>
                    <th class="px-3 py-2.5 text-right">bWPA</th>
                    <th class="px-3 py-2.5 text-center">Action</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  ${(data.recent_spells || []).slice(0, 5).map((spell) => `
                    <tr class="hover:bg-pink-50/30 transition-colors">
                      <td class="px-4 py-2.5 whitespace-nowrap">
                        <div class="font-medium text-slate-800">${spell.match_date || 'Match ' + spell.match_id}</div>
                        <div class="text-[10px] text-slate-400">Match #${spell.match_id}</div>
                      </td>
                      <td class="px-3 py-2.5 font-medium text-slate-700">${spell.opponent || 'N/A'}</td>
                      <td class="px-3 py-2.5 text-center">${spell.overs_formatted || formatOvers(spell.legal_balls)}</td>
                      <td class="px-3 py-2.5 text-center font-bold text-slate-900">${spell.wickets}/${spell.bowler_runs}</td>
                      <td class="px-3 py-2.5 text-right">${formatEconomy(spell.economy)}</td>
                      <td class="px-3 py-2.5 text-right font-bold text-pink-600">${formatBCS(spell.total_bcs)}</td>
                      <td class="px-3 py-2.5 text-right ${spell.total_bwpa >= 0 ? 'text-emerald-600' : 'text-rose-600'} font-medium">
                        ${formatBWPA(spell.total_bwpa)}
                      </td>
                      <td class="px-3 py-2.5 text-center">
                        <a href="#/bowling/match/${spell.match_id}" class="text-pink-600 hover:text-pink-800 font-semibold hover:underline">
                          View &rarr;
                        </a>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Explainability Accordion: How This Bowler's Contribution is Formed -->
        <div class="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 class="text-base font-bold text-slate-900">Mathematical Attribution Architecture</h3>
              <p class="text-xs text-slate-500">Deconstructing ${data.bowler_name}'s performance across three independent analytical pillars</p>
            </div>
            <span class="px-2.5 py-1 rounded text-xs font-bold bg-slate-100 text-slate-700">BCM + PCS</span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
              <div class="font-bold text-slate-800">1. Run Prevention (ERP)</div>
              <div class="text-slate-600">Generated <strong class="text-blue-600">${formatBCS(c.total_erp)}</strong> runs prevented against expectation based on historical venue & situation baselines.</div>
            </div>

            <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
              <div class="font-bold text-slate-800">2. Wicket Threat (Mean WQM)</div>
              <div class="text-slate-600">Average batter threat multiplier of <strong class="text-pink-600">${c.mean_wqm ? c.mean_wqm.toFixed(2) : '1.00'}x</strong>, measuring quality of dismissed batters.</div>
            </div>

            <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
              <div class="font-bold text-slate-800">3. Average Match Leverage</div>
              <div class="text-slate-600">Delivered overs at an average leverage of <strong class="text-slate-900">${c.mean_leverage ? c.mean_leverage.toFixed(2) : '1.00'}x</strong>, quantifying situational pressure.</div>
            </div>

            <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
              <div class="font-bold text-slate-800">4. Bayes Shrinkage Effect</div>
              <div class="text-slate-600">Shrunk from <strong class="text-blue-600">${formatBCS(c.total_bcs)}</strong> to <strong class="text-pink-600">${formatBCS(c.total_bcs_shrunk ?? c.shrunk_bcs)}</strong> (prior M0=48 balls) for cross-era fairness.</div>
            </div>
          </div>
        </div>
      </div>
    `;

    // Initialize quick switcher listener
    const quickSelect = container.querySelector('#bowler-quick-select');
    if (quickSelect) {
      quickSelect.addEventListener('change', (e) => {
        window.location.hash = `#/bowling/players/${e.target.value}`;
      });
    }

    // Initialize interactive PCS Season Selector (Section 8)
    const pcsSeasonSelect = container.querySelector('#pcs-profile-season-select');
    if (pcsSeasonSelect && pcsData) {
      pcsSeasonSelect.addEventListener('change', (e) => {
        const chosen = e.target.value;
        const allSpells = pcsData.spells_history || [];
        const filtered = chosen === 'all' ? allSpells : allSpells.filter((s) => String(s.season) === chosen);
        const seasonInfo = (pcsData.season_history || []).find((sh) => String(sh.season) === chosen);

        const summaryBar = container.querySelector('#pcs-season-selected-summary');
        if (summaryBar) {
          if (chosen === 'all' || !seasonInfo) {
            summaryBar.classList.add('hidden');
          } else {
            summaryBar.classList.remove('hidden');
            summaryBar.innerHTML = `
              <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span class="font-bold text-[#1E3A8A]">Season ${seasonInfo.season} PCS Summary:</span>
                <div class="flex flex-wrap items-center gap-4 font-mono">
                  <span>Shrunk PCS: <strong class="text-[#1E3A8A]">${formatPCS(seasonInfo.pcs_shrunk)}</strong></span>
                  <span>Raw PCS: <strong>${formatPCS(seasonInfo.pcs_raw)}</strong></span>
                  <span>Spells: <strong>${seasonInfo.spells}</strong></span>
                  <span>Balls: <strong>${seasonInfo.legal_balls}</strong></span>
                  <span>Wkts: <strong>${seasonInfo.wickets}</strong></span>
                  <span>Econ: <strong>${formatEconomy(seasonInfo.economy)}</strong></span>
                </div>
              </div>
            `;
          }
        }

        const countEl = container.querySelector('#pcs-spells-count-label');
        if (countEl) countEl.textContent = `Showing ${filtered.length} Spells${chosen !== 'all' ? ` (Season ${chosen})` : ''}`;

        const tbody = container.querySelector('#pcs-spells-log-tbody');
        if (tbody) {
          tbody.innerHTML = renderPCSSpellsRows(filtered);
        }
      });
    }

    // Render Charts
    renderProfileCharts(data, pcsData);

  } catch (error) {
    container.innerHTML = renderErrorState({
      title: 'Unable to load bowler profile',
      message: error.message || 'An unexpected error occurred while fetching the bowler profile data.',
      onRetry: `window.location.reload()`,
    });
  }
}

function renderPCSSpellsRows(spells) {
  if (!spells || spells.length === 0) {
    return `<tr><td colspan="13" class="px-4 py-6 text-center text-slate-400 font-sans">No spells recorded in this season.</td></tr>`;
  }
  return spells.map((s) => `
    <tr class="hover:bg-[#EFF6FF]/40 transition-colors">
      <td class="px-4 py-2.5 whitespace-nowrap font-sans">
        <div class="font-medium text-slate-800">${s.match_date || 'Match ' + s.match_id}</div>
        <div class="text-[10px] text-slate-400">Match #${s.match_id} (${s.season})</div>
      </td>
      <td class="px-3 py-2.5 font-sans font-medium text-slate-700">${s.opposition || s.batting_team || 'Opponent'}</td>
      <td class="px-3 py-2.5 text-center">${s.overs.toFixed(1)}</td>
      <td class="px-3 py-2.5 text-center font-bold text-slate-900">${s.wickets}/${s.bowler_runs}</td>
      <td class="px-3 py-2.5 text-right">${formatEconomy(s.economy)}</td>
      <td class="px-3 py-2.5 text-right text-slate-600">${s.total_swi !== null ? s.total_swi.toFixed(1) : '—'}</td>
      <td class="px-3 py-2.5 text-right text-slate-600">${s.total_dci !== null ? s.total_dci.toFixed(1) : '—'}</td>
      <td class="px-3 py-2.5 text-right text-slate-600">${s.total_sup !== null ? s.total_sup.toFixed(1) : '—'}</td>
      <td class="px-3 py-2.5 text-right text-rose-600">${s.total_leakage !== null ? s.total_leakage.toFixed(1) : '—'}</td>
      <td class="px-3 py-2.5 text-right font-bold ${s.total_rpe >= 0 ? 'text-blue-700' : 'text-rose-700'}">${s.total_rpe !== null ? (s.total_rpe >= 0 ? '+' : '') + s.total_rpe.toFixed(2) : '—'}</td>
      <td class="px-3 py-2.5 text-right font-black text-[#1E3A8A] text-xs">${formatPCS(s.pcs_spell)}</td>
      <td class="px-3 py-2.5 text-center font-sans">
        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${getPCSBadgeClass(s.pcs_spell)}">
          ${s.pressure_category === 'positive' ? '+Pressure' : s.pressure_category === 'negative' ? '-Leakage' : 'Neutral'}
        </span>
      </td>
      <td class="px-3 py-2.5 text-center font-sans">
        <a href="#/bowling/match/${s.match_id}" class="text-[11px] font-bold text-[#1E3A8A] hover:underline">
          Scorecard &rarr;
        </a>
      </td>
    </tr>
  `).join('');
}

function renderPCSProfileSection(pcsData) {
  const c = pcsData.career || pcsData.career_summary || {};
  const tb = pcsData.pressure_breakdown || pcsData.tactical_breakdown || {};
  const spells = pcsData.spells_history || pcsData.spells || [];
  const seasons = (pcsData.season_history || []).map((sh) => String(sh.season));

  const posSpellsPct = tb.positive_spells_pct !== undefined ? tb.positive_spells_pct :
    (spells.length > 0 ? ((spells.filter((s) => s.pressure_category === 'positive').length / spells.length) * 100) : 50.0);
  const negSpellsPct = tb.negative_spells_pct !== undefined ? tb.negative_spells_pct :
    (spells.length > 0 ? ((spells.filter((s) => s.pressure_category === 'negative').length / spells.length) * 100) : 50.0);

  const meanSup = tb.avg_sup_per_spell !== undefined ? tb.avg_sup_per_spell : (tb.mean_sup || 0);
  const meanDci = tb.avg_dci_per_spell !== undefined ? tb.avg_dci_per_spell : (tb.mean_dci || 0);
  const meanSwi = tb.avg_swi_per_spell !== undefined ? tb.avg_swi_per_spell : (tb.mean_swi || 0);
  const meanLeakage = tb.avg_leakage_per_spell !== undefined ? tb.avg_leakage_per_spell : (tb.mean_leakage || 0);
  const dotPct = tb.dot_ball_pct !== undefined ? tb.dot_ball_pct : (tb.dot_ball_ratio ? tb.dot_ball_ratio * 100 : 0);
  const boundaryPct = tb.boundary_rate ? tb.boundary_rate * 100 : (c.boundaries && c.legal_balls ? (c.boundaries / c.legal_balls * 100) : 0);

  return `
    <div class="space-y-6 pt-4 border-t-2 border-[#E2E8F0]">
      <!-- Section Header -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-gradient-to-r from-[#1E3A8A]/10 via-white to-[#3B82F6]/5 p-5 rounded-2xl border border-[#CBD5E1] shadow-xs">
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="px-2.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#1E3A8A] text-white">
              Pressure Contribution Score (PCS)
            </span>
            <span class="text-xs text-[#1E3A8A] font-bold font-mono">${c.matches || 0} Matches &bull; ${c.spells || 0} Spells &bull; ${formatNumber(c.legal_balls || 0)} Balls</span>
          </div>
          <h2 class="text-xl font-black text-[#0F172A] tracking-tight">
            Pressure & Containment Dossier
          </h2>
          <p class="text-xs text-[#64748B] mt-1 max-w-2xl">
            Independent evaluation on a bipolar 0–100 scale (neutral 50.00). Evaluates match-context pressure,
            dangerous stand containment, situational wickets (SWI), and suppression without volume tallying.
          </p>
        </div>

        <div class="flex items-center gap-2">
          <span class="px-3 py-1.5 rounded-lg bg-[#EFF6FF] text-[#1E3A8A] text-xs font-bold border border-[#BFDBFE]">
            Shrunk: <strong class="text-sm">${formatPCS(c.pcs_career_shrunk)}</strong> / 100
          </span>
        </div>
      </div>

      <!-- PCS Career KPIs (6 Cards) -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        ${renderMetricCard({
          title: 'Career Shrunk PCS',
          value: formatPCS(c.pcs_career_shrunk),
          unit: '0–100',
          subtitle: `Raw PCS: ${formatPCS(c.pcs_career_raw)}`,
          accent: 'deep-blue',
          badge: 'Primary PCS',
          tooltip: 'Empirical Bayes shrunk career score on the bipolar 0–100 scale (neutral 50.00).',
        })}

        ${renderMetricCard({
          title: 'Positive Pressure Spells',
          value: formatPercent(posSpellsPct),
          unit: '',
          subtitle: `${spells.filter((s) => s.pressure_category === 'positive').length} spells > 50`,
          accent: 'blue',
          badge: 'Consistency',
          tooltip: 'Percentage of bowling spells generating positive net match pressure (> 50.00).',
        })}

        ${renderMetricCard({
          title: 'Negative Leakage Spells',
          value: formatPercent(negSpellsPct),
          unit: '',
          subtitle: `${spells.filter((s) => s.pressure_category === 'negative').length} spells < 50`,
          accent: 'pink',
          badge: 'Leakage Rate',
          tooltip: 'Percentage of bowling spells suffering net pressure leakage (< 50.00).',
        })}

        ${renderMetricCard({
          title: 'Total RPE',
          value: formatBCS(c.total_rpe),
          subtitle: 'Runs Pressure Equiv',
          accent: 'deep-blue',
          badge: 'Net Pressure',
          tooltip: 'Cumulative Runs Pressure Equivalent across career deliveries.',
        })}

        ${renderMetricCard({
          title: 'Dot Ball Pressure',
          value: formatPercent(dotPct),
          unit: '',
          subtitle: `${formatNumber(c.dot_balls || 0)} dot deliveries`,
          accent: 'blue',
          badge: 'Containment',
          tooltip: 'Career dot-ball ratio generating sequential pressure.',
        })}

        ${renderMetricCard({
          title: 'Boundary Leakage',
          value: formatPercent(boundaryPct),
          unit: '',
          subtitle: `${formatNumber(c.boundaries || 0)} boundaries`,
          accent: 'pink',
          badge: 'Leakage',
          tooltip: 'Boundary conceded percentage relieving match pressure.',
        })}
      </div>

      <!-- Tactical Pressure Breakdown Callout Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div class="p-4 bg-white rounded-xl border border-slate-200 shadow-xs space-y-2">
          <div class="flex items-center justify-between">
            <h4 class="font-bold text-slate-900 flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-[#1E3A8A]"></span>
              Stand Control & Suppression
            </h4>
            <span class="text-[10px] font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">Containment</span>
          </div>
          <p class="text-slate-600 leading-relaxed">
            Delivers a mean suppression score of <strong>+${meanSup.toFixed(2)}</strong> per spell against dangerous batting partnerships, maintaining an average dangerous containment index (DCI) of <strong>+${meanDci.toFixed(2)}</strong>.
          </p>
        </div>

        <div class="p-4 bg-white rounded-xl border border-slate-200 shadow-xs space-y-2">
          <div class="flex items-center justify-between">
            <h4 class="font-bold text-slate-900 flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-[#EC4899]"></span>
              Situational Wicket Threat (SWI)
            </h4>
            <span class="text-[10px] font-bold text-pink-700 bg-pink-50 px-2 py-0.5 rounded">High Leverage</span>
          </div>
          <p class="text-slate-600 leading-relaxed">
            Generates a mean Situational Wicket Importance (SWI) of <strong>${meanSwi.toFixed(2)}</strong> per spell, recording <strong>${tb.stand_break_count ?? 0}</strong> dangerous partnership breaks and <strong>${tb.multi_wicket_overs_count ?? 0}</strong> multi-wicket overs across career appearances.
          </p>
        </div>

        <div class="p-4 bg-white rounded-xl border border-slate-200 shadow-xs space-y-2">
          <div class="flex items-center justify-between">
            <h4 class="font-bold text-slate-900 flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-emerald-600"></span>
              Net Pressure Equilibrium
            </h4>
            <span class="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">RPE Metric</span>
          </div>
          <p class="text-slate-600 leading-relaxed">
            Averages <strong>${(c.total_rpe && c.spells ? c.total_rpe / c.spells : 0) >= 0 ? '+' : ''}${(c.total_rpe && c.spells ? (c.total_rpe / c.spells).toFixed(2) : '0.00')}</strong> Runs Pressure Equivalent per spell, with an average boundary leakage penalty of <strong>-${Math.abs(meanLeakage).toFixed(2)}</strong>.
          </p>
        </div>
      </div>

      <!-- Season PCS Progression Chart -->
      <div class="bg-white rounded-xl p-5 border border-slate-200 shadow-sm flex flex-col">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="font-bold text-slate-900 text-sm">Season PCS Progression (Bipolar Scale [0–100])</h3>
            <p class="text-xs text-slate-500">Empirical Bayes Shrunk PCS by season relative to 50.00 neutral baseline</p>
          </div>
          <span class="text-xs px-2.5 py-1 rounded font-bold bg-[#1E3A8A] text-white">Neutral = 50.00</span>
        </div>
        <div class="relative flex-1 min-h-[220px]">
          <canvas id="season-pcs-chart"></canvas>
        </div>
      </div>

      <!-- Match-Wise Spell Pressure Log Table with Interactive Season Filter -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="p-5 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 class="font-bold text-slate-900 text-sm">Match Spells Pressure Log (PCS)</h3>
            <p class="text-xs text-slate-500">Evaluated match spells with SWI, DCI, Suppression, Leakage, RPE and Spell PCS</p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <div class="flex items-center gap-2">
              <label for="pcs-profile-season-select" class="text-[11px] font-bold uppercase text-slate-500">Season:</label>
              <select id="pcs-profile-season-select" class="text-xs font-semibold bg-white border border-slate-300 rounded-lg px-2.5 py-1 text-slate-800">
                <option value="all">All Seasons (${seasons.length})</option>
                ${seasons.slice().reverse().map((s) => `<option value="${s}">Season ${s}</option>`).join('')}
              </select>
            </div>
            <span id="pcs-spells-count-label" class="text-xs font-mono text-[#64748B]">Showing ${spells.length} Spells</span>
          </div>
        </div>
        <div id="pcs-season-selected-summary" class="hidden px-5 py-3 bg-[#EFF6FF] border-b border-[#BFDBFE]"></div>
        <div class="overflow-x-auto max-h-96">
          <table class="w-full text-left text-xs text-slate-600">
            <thead class="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200 sticky top-0 z-10 text-[10px] uppercase">
              <tr>
                <th class="px-4 py-2.5">Date / Match</th>
                <th class="px-3 py-2.5">Opponent</th>
                <th class="px-3 py-2.5 text-center">Overs</th>
                <th class="px-3 py-2.5 text-center">W-R</th>
                <th class="px-3 py-2.5 text-right">Econ</th>
                <th class="px-3 py-2.5 text-right font-mono">SWI</th>
                <th class="px-3 py-2.5 text-right font-mono">DCI</th>
                <th class="px-3 py-2.5 text-right font-mono">Sup</th>
                <th class="px-3 py-2.5 text-right font-mono">Leak</th>
                <th class="px-3 py-2.5 text-right font-mono">RPE</th>
                <th class="px-3 py-2.5 text-right font-black text-[#1E3A8A]">Spell PCS</th>
                <th class="px-3 py-2.5 text-center">Impact</th>
                <th class="px-3 py-2.5 text-center">Action</th>
              </tr>
            </thead>
            <tbody id="pcs-spells-log-tbody" class="divide-y divide-slate-100 font-mono text-[11px]">
              ${renderPCSSpellsRows(spells)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function renderProfileCharts(data, pcsData) {
  const seasons = data.season_breakdown || [];
  const splits = data.phase_splits || [];

  // 1. Season BCS Trend (Bar chart)
  const bcsCtx = document.getElementById('season-bcs-chart');
  if (bcsCtx && seasons.length > 0) {
    createBarChart(
      bcsCtx,
      {
        labels: seasons.map((s) => s.season),
        datasets: [
          {
            label: 'Season Total BCS',
            data: seasons.map((s) => s.total_bcs),
            backgroundColor: '#3B82F6', // Blue
            hoverBackgroundColor: '#2563EB',
            borderRadius: 4,
          },
        ],
      },
      {
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: {
            title: { display: true, text: 'BCS (Runs Scale)', font: { size: 10 } },
          },
        },
      }
    );
  }

  // 2. Season bWPA Trend (Line chart on separate canvas)
  const bwpaCtx = document.getElementById('season-bwpa-chart');
  if (bwpaCtx && seasons.length > 0) {
    createLineChart(
      bwpaCtx,
      {
        labels: seasons.map((s) => s.season),
        datasets: [
          {
            label: 'Season Total bWPA',
            data: seasons.map((s) => s.total_bwpa),
            borderColor: '#EC4899', // Pink
            backgroundColor: 'rgba(236, 72, 153, 0.1)',
            fill: true,
            tension: 0.3,
            pointBackgroundColor: '#DB2777',
            pointRadius: 4,
          },
        ],
      },
      {
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: {
            title: { display: true, text: 'bWPA (Win Probability Scale)', font: { size: 10 } },
          },
        },
      }
    );
  }

  // 3. Phase Doughnut Chart
  const phaseCtx = document.getElementById('phase-doughnut-chart');
  if (phaseCtx && splits.length > 0) {
    createDoughnutChart(
      phaseCtx,
      {
        labels: splits.map((s) => s.phase),
        datasets: [
          {
            data: splits.map((s) => Math.max(0, s.total_bcs)),
            backgroundColor: [
              '#3B82F6', // Powerplay: Blue
              '#EC4899', // Middle: Pink
              '#1E3A8A', // Death: Deep Blue
            ],
            borderWidth: 2,
            borderColor: '#FFFFFF',
          },
        ],
      },
      {
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
        },
        cutout: '65%',
      }
    );
  }

  // 4. Season PCS Trend (Line Chart on Bipolar 0-100 Scale)
  if (pcsData && pcsData.season_history && pcsData.season_history.length > 0) {
    const pcsCtx = document.getElementById('season-pcs-chart');
    if (pcsCtx) {
      const sh = pcsData.season_history;
      createLineChart(
        pcsCtx,
        {
          labels: sh.map((s) => s.season),
          datasets: [
            {
              label: 'Season Shrunk PCS',
              data: sh.map((s) => s.pcs_shrunk),
              borderColor: '#1E3A8A', // Deep Navy
              backgroundColor: 'rgba(30, 58, 138, 0.1)',
              fill: true,
              tension: 0.3,
              pointBackgroundColor: '#1E3A8A',
              pointRadius: 5,
              borderWidth: 2.5,
            },
            {
              label: 'Neutral Anchor (50.00)',
              data: sh.map(() => 50.0),
              borderColor: '#94A3B8', // Slate Grey dashed line
              borderDash: [5, 5],
              fill: false,
              pointRadius: 0,
              borderWidth: 1.5,
            },
          ],
        },
        {
          plugins: {
            legend: { position: 'top', labels: { font: { size: 11 } } },
          },
          scales: {
            y: {
              min: 30,
              max: 80,
              title: { display: true, text: 'PCS Scale [0–100]', font: { size: 10 } },
              grid: { color: '#F1F5F9' },
            },
          },
        }
      );
    }
  }
}
