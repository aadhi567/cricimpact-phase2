/**
 * CricImpact Phase 2 — Match & Spell Analysis Page
 * Match listing/browsing and in-depth match spell scorecard
 * with ball-by-ball delivery-level transition explorer, BCS and PCS pressure explainability.
 */

import { bowlingApiService } from '../services/bowlingApiService.js';
import { pcsApiService } from '../services/pcsApiService.js';
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
import { renderLoadingSkeleton } from '../components/LoadingSkeleton.js';
import { renderErrorState } from '../components/ErrorState.js';

export async function renderMatchAnalysis(container, params = {}) {
  if (params.id) {
    // Render specific match detail and spells view
    await renderMatchDetailView(container, parseInt(params.id, 10));
  } else {
    // Render match browser / list view
    await renderMatchListView(container, params);
  }
}

// -------------------------------------------------------------
// 1. MATCH LIST VIEW (#/bowling/matches)
// -------------------------------------------------------------
async function renderMatchListView(container, params) {
  const page = parseInt(params.page || '1', 10);
  const season = params.season || '';

  container.innerHTML = `
    <div class="space-y-6">
      <div class="flex items-center space-x-2 text-sm text-slate-500 mb-2">
        <a href="#/bowling/dashboard" class="hover:text-blue-600">Bowling</a>
        <span>/</span>
        <span class="text-slate-800 font-medium">Match Explorer</span>
      </div>
      ${renderLoadingSkeleton('table')}
    </div>
  `;

  try {
    const response = await bowlingApiService.getMatches({ page, page_size: 15, season: season || undefined });
    if (!response || !response.success || !response.data) {
      throw new Error(response?.error?.message || 'Failed to fetch match list');
    }

    const { items, pagination } = response.data;

    container.innerHTML = `
      <div class="space-y-6 animate-fadeIn">
        <!-- Header -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
          <div>
            <div class="flex items-center space-x-2 text-xs font-bold text-blue-600 uppercase tracking-wider mb-1">
              <span>Match-Level Analytics</span>
              <span>&bull;</span>
              <span>${pagination.total_items} Verified Matches</span>
            </div>
            <h1 class="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">Bowling Match Explorer</h1>
            <p class="text-slate-500 text-sm mt-1">
              Explore match scorecards, leverage contexts, and ball-by-ball delivery contributions across BCM and PCS.
            </p>
          </div>

          <!-- Season Filter -->
          <div class="flex items-center space-x-2">
            <label for="match-season-filter" class="text-xs font-semibold text-slate-500 uppercase">Season:</label>
            <select id="match-season-filter" class="text-sm bg-white border border-slate-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:outline-none">
              <option value="">All Seasons</option>
              ${['2026', '2025', '2024', '2023', '2022'].map((s) => `
                <option value="${s}" ${season === s ? 'selected' : ''}>${s}</option>
              `).join('')}
            </select>
          </div>
        </div>

        <!-- Matches Table -->
        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-600">
              <thead class="bg-slate-50 text-slate-700 font-bold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                <tr>
                  <th class="px-5 py-3.5">Match ID & Date</th>
                  <th class="px-4 py-3.5">Teams</th>
                  <th class="px-4 py-3.5">Venue</th>
                  <th class="px-4 py-3.5 text-center">Spells</th>
                  <th class="px-4 py-3.5 text-center">Wickets</th>
                  <th class="px-4 py-3.5">Top Impact Bowler</th>
                  <th class="px-4 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                ${items.map((m) => `
                  <tr class="hover:bg-slate-50/70 transition-colors">
                    <td class="px-5 py-3 whitespace-nowrap">
                      <div class="font-bold text-slate-900">Match #${m.match_id}</div>
                      <div class="text-[11px] text-slate-500">${m.match_date} (${m.season})</div>
                    </td>
                    <td class="px-4 py-3 font-semibold text-slate-800">
                      ${m.teams && m.teams.length >= 2 ? `${m.teams[0]} vs ${m.teams[1]}` : 'T20 Match'}
                    </td>
                    <td class="px-4 py-3 text-slate-600 truncate max-w-xs" title="${m.venue || ''}">
                      ${m.venue || 'Standard T20 Venue'}
                    </td>
                    <td class="px-4 py-3 text-center font-medium">${m.total_spells}</td>
                    <td class="px-4 py-3 text-center font-bold text-slate-900">${m.total_wickets}</td>
                    <td class="px-4 py-3">
                      ${m.top_bowler ? `
                        <div class="font-semibold text-blue-700">${m.top_bowler.bowler_name}</div>
                        <div class="text-[11px] text-slate-500">${m.top_bowler.wickets} wkts &bull; <strong class="text-blue-600">${formatBCS(m.top_bowler.bcs)} BCS</strong></div>
                      ` : '<span class="text-slate-400">N/A</span>'}
                    </td>
                    <td class="px-4 py-3 text-right">
                      <a href="#/bowling/match/${m.match_id}" class="px-3 py-1.5 text-xs font-bold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors border border-blue-200">
                        Scorecard &rarr;
                      </a>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div class="p-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600">
            <div>
              Showing page <strong class="text-slate-900">${pagination.current_page}</strong> of <strong class="text-slate-900">${pagination.total_pages}</strong> (${pagination.total_items} matches)
            </div>
            <div class="flex items-center space-x-2">
              <button id="prev-page-btn" class="px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 font-semibold disabled:opacity-40 disabled:cursor-not-allowed" ${page <= 1 ? 'disabled' : ''}>
                &larr; Previous
              </button>
              <button id="next-page-btn" class="px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 font-semibold disabled:opacity-40 disabled:cursor-not-allowed" ${page >= pagination.total_pages ? 'disabled' : ''}>
                Next &rarr;
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Filter and Pagination Listeners
    const seasonSelect = container.querySelector('#match-season-filter');
    if (seasonSelect) {
      seasonSelect.addEventListener('change', (e) => {
        window.location.hash = `#/bowling/matches?season=${e.target.value}&page=1`;
      });
    }

    const prevBtn = container.querySelector('#prev-page-btn');
    if (prevBtn && page > 1) {
      prevBtn.addEventListener('click', () => {
        window.location.hash = `#/bowling/matches?season=${season}&page=${page - 1}`;
      });
    }

    const nextBtn = container.querySelector('#next-page-btn');
    if (nextBtn && page < pagination.total_pages) {
      nextBtn.addEventListener('click', () => {
        window.location.hash = `#/bowling/matches?season=${season}&page=${page + 1}`;
      });
    }

  } catch (error) {
    container.innerHTML = renderErrorState({
      title: 'Unable to load matches',
      message: error.message || 'An error occurred while fetching matches.',
      onRetry: `window.location.reload()`,
    });
  }
}

// -------------------------------------------------------------
// 2. MATCH DETAIL & SPELL VIEW (#/bowling/match/:id)
// -------------------------------------------------------------
async function renderMatchDetailView(container, matchId) {
  container.innerHTML = `
    <div class="space-y-6">
      <div class="flex items-center space-x-2 text-sm text-slate-500 mb-2">
        <a href="#/bowling/matches" class="hover:text-blue-600">Match Explorer</a>
        <span>/</span>
        <span class="text-slate-800 font-medium">Match #${matchId}</span>
      </div>
      ${renderLoadingSkeleton('table')}
    </div>
  `;

  try {
    const [bcmRes, pcsRes] = await Promise.all([
      bowlingApiService.getMatchSpells(matchId),
      pcsApiService.getMatchDetail(matchId).then((r) => r.data).catch((err) => {
        console.warn('[MatchAnalysis] PCS match detail warning:', err);
        return null;
      }),
    ]);

    if (!bcmRes || !bcmRes.success || !bcmRes.data) {
      throw new Error(bcmRes?.error?.message || 'Failed to load match spells');
    }

    const { match_date, venue, spells } = bcmRes.data;

    // Create PCS spell lookup by bowler_id and innings
    const pcsSpellMap = {};
    const pcsSpells = pcsRes?.bowler_spells || pcsRes?.spells || [];
    pcsSpells.forEach((ps) => {
      const key = `${ps.innings}_${ps.bowler_id}`;
      pcsSpellMap[key] = ps;
    });

    // Group spells by Innings
    const inn1Spells = spells.filter((s) => s.innings === 1);
    const inn2Spells = spells.filter((s) => s.innings === 2);

    container.innerHTML = `
      <div class="space-y-8 animate-fadeIn">
        <!-- Match Header -->
        <div class="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-sm relative overflow-hidden">
          <div class="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div class="flex items-center space-x-2 text-xs font-bold text-blue-600 uppercase tracking-wider mb-1">
                <span>Match Scorecard & Spells</span>
                <span>&bull;</span>
                <span>BCM + PCS Telemetry</span>
              </div>
              <h1 class="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">Match #${matchId}</h1>
              <p class="text-slate-600 text-sm mt-1">
                ${match_date} &bull; <span class="font-medium text-slate-800">${venue}</span>
              </p>
            </div>

            <a href="#/bowling/matches" class="self-start sm:self-auto px-3.5 py-2 text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors">
              &larr; Back to Matches
            </a>
          </div>
        </div>

        <!-- Innings 1 Spells -->
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-bold text-slate-900 flex items-center space-x-2">
              <span class="w-3 h-3 rounded-full bg-blue-600"></span>
              <span>Innings 1 Bowling Spells</span>
            </h2>
            <span class="text-xs text-slate-500 font-medium">${inn1Spells.length} Bowlers</span>
          </div>
          ${renderSpellsTable(inn1Spells, matchId, pcsSpellMap)}
        </div>

        <!-- Innings 2 Spells -->
        ${inn2Spells.length > 0 ? `
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <h2 class="text-lg font-bold text-slate-900 flex items-center space-x-2">
                <span class="w-3 h-3 rounded-full bg-pink-600"></span>
                <span>Innings 2 Bowling Spells</span>
              </h2>
              <span class="text-xs text-slate-500 font-medium">${inn2Spells.length} Bowlers</span>
            </div>
            ${renderSpellsTable(inn2Spells, matchId, pcsSpellMap)}
          </div>
        ` : ''}

        <!-- Delivery Transition Viewer Container (Populated dynamically) -->
        <div id="delivery-viewer-section" class="hidden space-y-4 pt-4 border-t border-slate-200">
          <div class="flex items-center justify-between">
            <div>
              <h3 id="delivery-viewer-title" class="text-base font-bold text-slate-900">Spell Deliveries</h3>
              <p id="delivery-viewer-subtitle" class="text-xs text-slate-500">Ball-by-ball delivery transitions with context, leverage, and PCS pressure metrics</p>
            </div>
            <button id="close-delivery-viewer" class="text-xs font-bold text-slate-500 hover:text-slate-800 p-1">
              Close &times;
            </button>
          </div>
          <div id="delivery-table-container"></div>
        </div>
      </div>
    `;

    // Attach listeners for "View Deliveries" buttons
    container.querySelectorAll('.view-deliveries-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const spellId = btn.getAttribute('data-spell-id');
        const bowlerName = btn.getAttribute('data-bowler-name');
        await loadAndRenderDeliveries(container, spellId, bowlerName);
      });
    });

  } catch (error) {
    container.innerHTML = renderErrorState({
      title: 'Unable to load match scorecard',
      message: error.message || 'An error occurred while loading this match.',
      onRetry: `window.location.reload()`,
    });
  }
}

function renderSpellsTable(spells, matchId, pcsSpellMap) {
  if (!spells || spells.length === 0) {
    return `<div class="p-6 bg-white rounded-xl border border-slate-200 text-center text-xs text-slate-500">No spells recorded for this innings.</div>`;
  }

  return `
    <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-600">
          <thead class="bg-slate-50 text-slate-700 font-bold border-b border-slate-200 uppercase tracking-wider text-[11px]">
            <tr>
              <th class="px-5 py-3">Bowler</th>
              <th class="px-3 py-3 text-center">Overs</th>
              <th class="px-3 py-3 text-center">M</th>
              <th class="px-3 py-3 text-center">R</th>
              <th class="px-3 py-3 text-center font-bold text-slate-900">W</th>
              <th class="px-3 py-3 text-right">Econ</th>
              <th class="px-3 py-3 text-center">Dots</th>
              <th class="px-3 py-3 text-right text-blue-700 font-bold">BCS</th>
              <th class="px-3 py-3 text-right">bWPA</th>
              <th class="px-3 py-3 text-right">ERP</th>
              <th class="px-3 py-3 text-center">Leverage</th>
              <th class="px-3 py-3 text-right font-mono text-[#1E3A8A]">RPE</th>
              <th class="px-3 py-3 text-right font-black text-[#1E3A8A]">Spell PCS</th>
              <th class="px-4 py-3 text-center">Deliveries</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 font-mono text-[11px]">
            ${spells.map((s) => {
              const pcsKey = `${s.innings}_${s.bowler_id}`;
              const ps = pcsSpellMap ? pcsSpellMap[pcsKey] : null;
              const pcsVal = ps ? ps.pcs_spell : null;
              const pcsCat = ps ? ps.pressure_category : 'neutral';

              return `
                <tr class="hover:bg-slate-50/80 transition-colors">
                  <td class="px-5 py-3 whitespace-nowrap font-sans">
                    <a href="#/bowling/profile/${s.bowler_id}" class="font-bold text-slate-900 hover:text-blue-600 transition-colors">
                      ${s.bowler_name}
                    </a>
                    <div class="text-[10px] text-slate-400">${s.team || ''}</div>
                  </td>
                  <td class="px-3 py-3 text-center font-medium">${s.overs_formatted || formatOvers(s.legal_balls)}</td>
                  <td class="px-3 py-3 text-center text-slate-400">${s.maidens}</td>
                  <td class="px-3 py-3 text-center font-medium">${s.bowler_runs}</td>
                  <td class="px-3 py-3 text-center font-black text-slate-900 text-sm">${s.wickets}</td>
                  <td class="px-3 py-3 text-right font-medium">${formatEconomy(s.economy)}</td>
                  <td class="px-3 py-3 text-center text-blue-600 font-medium">${s.dot_balls}</td>
                  <td class="px-3 py-3 text-right font-black text-blue-600 text-sm">${formatBCS(s.total_bcs)}</td>
                  <td class="px-3 py-3 text-right font-bold ${s.total_bwpa >= 0 ? 'text-emerald-600' : 'text-rose-600'}">
                    ${formatBWPA(s.total_bwpa)}
                  </td>
                  <td class="px-3 py-3 text-right text-blue-700 font-medium">${formatBCS(s.total_erp)}</td>
                  <td class="px-3 py-3 text-center text-slate-600">${s.mean_leverage ? s.mean_leverage.toFixed(2) + 'x' : '1.00x'}</td>
                  <td class="px-3 py-3 text-right font-mono font-bold ${ps && ps.total_rpe >= 0 ? 'text-blue-700' : 'text-rose-600'}">
                    ${ps && ps.total_rpe !== null && ps.total_rpe !== undefined ? `${ps.total_rpe >= 0 ? '+' : ''}${ps.total_rpe.toFixed(2)}` : '—'}
                  </td>
                  <td class="px-3 py-3 text-right font-sans">
                    ${pcsVal !== null && pcsVal !== undefined ? `
                      <span class="inline-flex items-center px-2 py-0.5 rounded font-black text-xs ${getPCSBadgeClass(pcsVal)}">
                        ${formatPCS(pcsVal)}
                      </span>
                    ` : '<span class="text-slate-400">—</span>'}
                  </td>
                  <td class="px-4 py-3 text-center font-sans">
                    <button data-spell-id="${s.spell_id}" data-bowler-name="${s.bowler_name}" class="view-deliveries-btn px-2.5 py-1 text-[11px] font-bold text-pink-600 bg-pink-50 hover:bg-pink-100 rounded-md border border-pink-200 transition-colors">
                      Balls (${s.legal_balls}) &darr;
                    </button>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// -------------------------------------------------------------
// 3. DELIVERY LEVEL TRANSITION EXPLORER (BCM + PCS Telemetry)
// -------------------------------------------------------------
async function loadAndRenderDeliveries(container, spellId, bowlerName) {
  const viewer = container.querySelector('#delivery-viewer-section');
  const title = container.querySelector('#delivery-viewer-title');
  const subtitle = container.querySelector('#delivery-viewer-subtitle');
  const tableContainer = container.querySelector('#delivery-table-container');

  if (!viewer || !tableContainer) return;

  viewer.classList.remove('hidden');
  title.textContent = `${bowlerName} - Ball-by-Ball Spell Analysis (BCM + PCS)`;
  subtitle.textContent = `Detailed delivery transitions for Spell ID: ${spellId}`;
  tableContainer.innerHTML = renderLoadingSkeleton('table');

  viewer.scrollIntoView({ behavior: 'smooth' });

  const closeBtn = container.querySelector('#close-delivery-viewer');
  if (closeBtn) {
    closeBtn.onclick = () => viewer.classList.add('hidden');
  }

  try {
    const [bcmDelivRes, pcsDelivRes] = await Promise.all([
      bowlingApiService.getSpellDeliveries(spellId),
      pcsApiService.getSpellDeliveries(spellId).then((r) => r.data).catch((err) => {
        console.warn('[MatchAnalysis] PCS deliveries warning:', err);
        return null;
      }),
    ]);

    if (!bcmDelivRes || !bcmDelivRes.success || !bcmDelivRes.data) {
      throw new Error(bcmDelivRes?.error?.message || 'Failed to fetch spell deliveries');
    }

    const { deliveries } = bcmDelivRes.data;

    // Create PCS delivery lookup by delivery_id or over.ball
    const pcsDelivMap = {};
    const pcsDeliveries = pcsDelivRes?.deliveries || pcsDelivRes?.delivery_timeline || [];
    pcsDeliveries.forEach((pd) => {
      const key = `${pd.overid}_${pd.over_ball_num}`;
      pcsDelivMap[key] = pd;
    });

    // Build Sequential Multi-Wicket State Transition Panel (Section 10)
    const wicketEvents = deliveries
      .map((d) => {
        const pd = pcsDelivMap[`${d.overid}_${d.over_ball_num}`] || {};
        const isAnyWkt = Boolean(d.is_wicket_event || d.is_bowler_wkt || pd.is_wicket);
        const isBowlerWkt = Boolean(d.is_bowler_wkt || pd.is_bowler_wkt);
        return isAnyWkt ? { d, pd, isBowlerWkt } : null;
      })
      .filter(Boolean);

    let sequentialPanelHtml = '';
    if (wicketEvents.length > 0) {
      let stateIdx = 0;
      const chainItems = [];
      wicketEvents.forEach((ev, idx) => {
        const sBefore = `${ev.d.score_before}/${ev.d.wickets_lost_before}`;
        const sAfter = `${ev.d.score_before + (ev.d.bowler_runs || 0)}/${ev.d.wickets_lost_before + 1}`;
        const swiTxt = ev.pd.swi !== undefined ? `+${Number(ev.pd.swi).toFixed(2)} SWI` : '';
        const rpeTxt = ev.pd.rpe !== undefined ? `${ev.pd.rpe >= 0 ? '+' : ''}${Number(ev.pd.rpe).toFixed(2)} RPE` : '';
        if (idx === 0) {
          chainItems.push(`
            <div class="px-2.5 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-[11px] font-mono">
              <div class="text-[9px] font-bold uppercase text-slate-500">S${stateIdx}</div>
              <div class="font-black text-slate-800">${sBefore}</div>
            </div>
          `);
        }
        stateIdx += 1;
        chainItems.push(`
          <span class="text-slate-400 font-black">&rarr;</span>
          <div class="px-2.5 py-1.5 rounded-lg border text-[11px] ${ev.isBowlerWkt ? 'bg-[#EFF6FF] border-[#BFDBFE] text-[#1E3A8A]' : 'bg-amber-50 border-amber-200 text-amber-900'}">
            <div class="font-bold">${ev.isBowlerWkt ? `Wicket ${idx + 1} (${ev.d.dismissal_type || 'Out'})` : `Run-Out (Team Event)`} &bull; Ov ${ev.d.overid}.${ev.d.over_ball_num}</div>
            <div class="text-[10px] font-mono">${ev.isBowlerWkt ? `${swiTxt} | ${rpeTxt}` : 'No individual bowler wicket credit'}</div>
          </div>
          <span class="text-slate-400 font-black">&rarr;</span>
          <div class="px-2.5 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-[11px] font-mono">
            <div class="text-[9px] font-bold uppercase text-slate-500">S${stateIdx}</div>
            <div class="font-black text-slate-800">${sAfter}</div>
          </div>
        `);
      });

      sequentialPanelHtml = `
        <div class="mb-4 p-4 rounded-xl bg-white border border-[#CBD5E1] shadow-xs space-y-2.5">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h4 class="text-xs font-black uppercase tracking-wider text-[#1E3A8A]">
              Sequential Wicket State Transitions (${wicketEvents.length} Dismissal Event${wicketEvents.length > 1 ? 's' : ''})
            </h4>
            <span class="text-[11px] text-slate-500">Incremental bowler SWI credit per transition &bull; Run-outs excluded from individual credit</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            ${chainItems.join('')}
          </div>
        </div>
      `;
    }

    tableContainer.innerHTML = `
      ${sequentialPanelHtml}
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-600">
            <thead class="bg-slate-50 text-slate-700 font-bold border-b border-slate-200 uppercase tracking-wider text-[10px]">
              <tr>
                <th class="px-3 py-2.5 text-center">Over.Ball</th>
                <th class="px-3 py-2.5">Phase</th>
                <th class="px-4 py-2.5">Striker</th>
                <th class="px-3 py-2.5 text-center">Score</th>
                <th class="px-3 py-2.5 text-center">Runs</th>
                <th class="px-3 py-2.5 text-center">Outcome</th>
                <th class="px-3 py-2.5 text-right text-blue-700 font-bold">BCS</th>
                <th class="px-3 py-2.5 text-right font-medium">bWPA</th>
                <th class="px-3 py-2.5 text-right">ERP</th>
                <th class="px-3 py-2.5 text-center font-mono">Lev</th>
                <th class="px-3 py-2.5 text-center font-mono text-[#1E3A8A]">PTI</th>
                <th class="px-3 py-2.5 text-center font-mono text-[#1E3A8A]">SWI</th>
                <th class="px-3 py-2.5 text-right font-mono text-[#1E3A8A]">RPE</th>
                <th class="px-3 py-2.5 text-right font-mono font-bold text-[#1E3A8A]">PCS</th>
                <th class="px-3 py-2.5 text-center">Explain</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 font-mono text-[11px]">
              ${deliveries.map((d, idx) => {
                const pdKey = `${d.overid}_${d.over_ball_num}`;
                const pd = pcsDelivMap[pdKey] || {};

                return `
                  <tr class="hover:bg-slate-50 transition-colors ${d.is_wicket_event ? 'bg-amber-50/50' : ''}">
                    <td class="px-3 py-2 text-center font-bold text-slate-800">${d.overid}.${d.over_ball_num}</td>
                    <td class="px-3 py-2 font-sans font-medium text-slate-600">${d.innings_phase}</td>
                    <td class="px-4 py-2 font-sans font-medium text-slate-800">${d.striker_name}</td>
                    <td class="px-3 py-2 text-center text-slate-500">${d.score_before}/${d.wickets_lost_before}</td>
                    <td class="px-3 py-2 text-center font-bold text-slate-900">${d.bowler_runs}</td>
                    <td class="px-3 py-2 text-center font-sans">
                      ${d.is_bowler_wkt ? `
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800">
                          WICKET (${d.dismissal_type || 'out'})
                        </span>
                      ` : (d.is_wicket_event || pd.is_wicket) ? `
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300" title="Team-state dismissal without individual bowler wicket credit">
                          RUN OUT (Team Event)
                        </span>
                      ` : d.is_dot_ball ? `
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-800">
                          DOT
                        </span>
                      ` : d.is_boundary ? `
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800">
                          BOUNDARY (${d.bowler_runs})
                        </span>
                      ` : `
                        <span class="text-slate-500">${d.bowler_runs}r</span>
                      `}
                    </td>
                    <td class="px-3 py-2 text-right font-black text-blue-600">${formatBCS(d.bcs)}</td>
                    <td class="px-3 py-2 text-right font-medium ${d.bwpa >= 0 ? 'text-emerald-600' : 'text-rose-600'}">
                      ${formatBWPA(d.bwpa)}
                    </td>
                    <td class="px-3 py-2 text-right text-slate-700">${formatBCS(d.erp)}</td>
                    <td class="px-3 py-2 text-center text-slate-600">${d.leverage ? d.leverage.toFixed(2) + 'x' : '1.00x'}</td>
                    <td class="px-3 py-2 text-center font-bold text-slate-700">${pd.pti !== undefined ? pd.pti.toFixed(2) : '—'}</td>
                    <td class="px-3 py-2 text-center font-bold ${pd.swi > 0 ? 'text-emerald-600' : 'text-slate-400'}">${pd.swi !== undefined ? pd.swi.toFixed(1) : '—'}</td>
                    <td class="px-3 py-2 text-right ${pd.rpe >= 0 ? 'text-blue-700 font-bold' : 'text-rose-600'}">${pd.rpe !== undefined ? (pd.rpe >= 0 ? '+' : '') + pd.rpe.toFixed(2) : '—'}</td>
                    <td class="px-3 py-2 text-right font-black text-[#1E3A8A]">${pd.pcs_delivery !== undefined ? formatPCS(pd.pcs_delivery) : '—'}</td>
                    <td class="px-3 py-2 text-center font-sans">
                      <button class="explain-ball-btn text-[10px] font-bold text-blue-600 hover:underline" data-idx="${idx}">
                        Info
                      </button>
                    </td>
                  </tr>
                  <!-- Expandable row explanation -->
                  <tr id="ball-explain-${idx}" class="hidden bg-slate-50/90 font-sans text-xs">
                    <td colspan="15" class="p-3 border-t border-slate-200">
                      <div class="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3 text-slate-700">
                        <div class="p-2 bg-white rounded border border-slate-200">
                          <span class="text-[10px] font-bold uppercase text-slate-400 block">Runs Prevention (BCM)</span>
                          <div><strong>Exp Runs:</strong> ${d.exp_bowler_runs ? d.exp_bowler_runs.toFixed(2) : '0.00'}</div>
                          <div><strong>Wicket Value (V_wkt):</strong> ${d.V_wkt ? d.V_wkt.toFixed(2) : '0.00'} runs</div>
                          <div><strong>bWPA:</strong> ${(d.delta_wp_bowl * 100).toFixed(2)}% win swing</div>
                        </div>

                        <div class="p-2 bg-white rounded border border-slate-200">
                          <span class="text-[10px] font-bold uppercase text-[#1E3A8A] block">Threat & Containment (PCS)</span>
                          <div><strong>PTI (Partnership Threat):</strong> ${pd.pti !== undefined ? pd.pti.toFixed(2) : '—'}</div>
                          <div><strong>DCI (Dangerous Containment):</strong> ${pd.dci !== undefined ? pd.dci.toFixed(2) : '—'}</div>
                          <div><strong>Suppression (Sup):</strong> ${pd.sup !== undefined ? pd.sup.toFixed(2) : '—'}</div>
                        </div>

                        <div class="p-2 bg-white rounded border border-slate-200">
                          <span class="text-[10px] font-bold uppercase text-rose-600 block">Wicket &amp; Leakage (PCS)</span>
                          <div><strong>SWI (Situational Wicket):</strong> ${pd.swi !== undefined ? pd.swi.toFixed(2) : '0.00'}</div>
                          <div><strong>Leakage:</strong> ${pd.leakage !== undefined ? pd.leakage.toFixed(2) : '0.00'}</div>
                          <div><strong>Net RPE:</strong> ${pd.rpe !== undefined ? (pd.rpe >= 0 ? '+' : '') + pd.rpe.toFixed(2) : '0.00'} runs</div>
                          ${pd.sequential_event_note ? `<div class="mt-1 text-[10px] font-semibold text-[#1E3A8A]">${pd.sequential_event_note}</div>` : ''}
                        </div>

                        <div class="p-2 bg-white rounded border border-slate-200">
                          <span class="text-[10px] font-bold uppercase text-slate-400 block">Match Situation</span>
                          <div><strong>Balls Left:</strong> ${d.legal_balls_remaining_before}</div>
                          <div><strong>Score:</strong> ${d.score_before}/${d.wickets_lost_before}</div>
                          <div><strong>Leverage:</strong> ${d.leverage ? d.leverage.toFixed(2) : '1.00'}x</div>
                        </div>

                        <div class="p-2 bg-white rounded border border-slate-200">
                          <span class="text-[10px] font-bold uppercase text-[#1E3A8A] block">Delivery Pressure Impact</span>
                          <div class="text-sm font-black text-[#1E3A8A]">${pd.pcs_delivery !== undefined ? formatPCS(pd.pcs_delivery) : '—'}</div>
                          <span class="text-[10px] ${pd.pcs_delivery > 50 ? 'text-emerald-700' : pd.pcs_delivery < 50 ? 'text-rose-700' : 'text-slate-500'}">
                            ${pd.pcs_delivery > 50 ? 'Generated net pressure' : pd.pcs_delivery < 50 ? 'Relieved pressure (leakage)' : 'Neutral baseline ball'}
                          </span>
                        </div>
                      </div>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Attach row expand listeners
    tableContainer.querySelectorAll('.explain-ball-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const idx = btn.getAttribute('data-idx');
        const row = tableContainer.querySelector(`#ball-explain-${idx}`);
        if (row) row.classList.toggle('hidden');
      });
    });

  } catch (error) {
    tableContainer.innerHTML = renderErrorState({
      title: 'Unable to load deliveries',
      message: error.message || 'An error occurred while loading deliveries for this spell.',
      onRetry: `window.location.reload()`,
    });
  }
}
