/**
 * CricImpact Phase 2 — Stage PRI-3: Pressure Reliability Index (PRI) Page
 *
 * Independent evaluation of:
 * 1. Batting Reliability (T10: mean_p >= 40 OR peak_p >= 60, DNB strictly excluded)
 * 2. Bowling Reliability (EXO_2: max_over_entry_pti >= 35 AND legal_balls >= 12)
 *
 * Strict UI & Methodology Invariants:
 * - Zero shrinkage; exact PRI-2 stored percentages, averages & totals.
 * - No composite PRI score combining reliability rate and contribution quality.
 * - Independent custom numeric Minimum Pressure Innings / Spells inputs (any integer >= 0).
 * - Authoritative B8 Pakistan overall leaderboard visibility applied by backend.
 */

import { priApiService } from '../services/priApiService.js';
import { escapeHtml, formatSigned, getSignedColorClass } from '../components/BattingMetricExplainer.js';
import { formatNumber } from '../utils/formatting.js';

const ACTIVE_CHARTS = {};

function destroyChart(key) {
  if (ACTIVE_CHARTS[key]) {
    try {
      ACTIVE_CHARTS[key].destroy();
    } catch (_) {}
    delete ACTIVE_CHARTS[key];
  }
}

function destroyAllPriCharts() {
  Object.keys(ACTIVE_CHARTS).forEach(destroyChart);
}

/**
 * Validate custom minimum opportunity numeric input string strictly (whole integer >= 0).
 */
export function validateCustomMinInput(rawStr) {
  const s = String(rawStr ?? '').trim();
  if (s === '') return { valid: true, value: 0, error: null };
  if (s.startsWith('-')) {
    return { valid: false, value: null, error: 'Minimum opportunities cannot be negative. Enter 0 or a positive whole number.' };
  }
  if (!/^\d+$/.test(s)) {
    return { valid: false, value: null, error: 'Enter a whole integer (0, 1, 12, 18, ...). Decimals and letters are not allowed.' };
  }
  const num = Number(s);
  if (!Number.isSafeInteger(num) || num < 0) {
    return { valid: false, value: null, error: 'Please enter a valid non-negative integer.' };
  }
  return { valid: true, value: num, error: null };
}

/**
 * POS REL color coding helpers:
 * - POS REL >= 50%: Green
 * - POS REL < 50%: Yellow (never red)
 */
export function getPosRelBadgeClass(relPct) {
  if (relPct === null || relPct === undefined || Number.isNaN(Number(relPct))) {
    return 'bg-[#F1F5F9] text-[#64748B]';
  }
  return Number(relPct) >= 50
    ? 'bg-[#DCFCE7] text-[#15803D] border border-[#BBF7D0]'
    : 'bg-[#FEF9C3] text-[#854D0E] border border-[#FDE047]';
}

export function getPosRelTextClass(relPct) {
  if (relPct === null || relPct === undefined || Number.isNaN(Number(relPct))) {
    return 'text-[#64748B]';
  }
  return Number(relPct) >= 50 ? 'text-[#16A34A]' : 'text-[#CA8A04]';
}

export function getPosRelBarColor(relPct) {
  if (relPct === null || relPct === undefined || Number.isNaN(Number(relPct))) {
    return 'rgba(148, 163, 184, 0.75)';
  }
  return Number(relPct) >= 50 ? 'rgba(22, 163, 74, 0.85)' : 'rgba(234, 179, 8, 0.85)';
}

function createInitialState(initialTab = 'batting') {
  return {
    activeTab: initialTab === 'bowling' ? 'bowling' : 'batting',
    overview: null,
    filters: null,
    batting: {
      scope: 'career',
      season: 'all',
      tournament: 'all',
      team: 'all',
      search: '',
      minInput: '0',
      minValidValue: 0,
      minError: null,
      sort_by: 'positive_hpc_pct',
      order: 'desc',
      page: 1,
      page_size: 20,
      loading: false,
      error: null,
      response: null,
      compareIds: [1699, 6396, 3125], // Suryakumar Yadav, Tim David, Nicholas Pooran
      compareData: null,
      compareLoading: false,
    },
    bowling: {
      scope: 'career',
      season: 'all',
      tournament: 'all',
      team: 'all',
      search: '',
      minInput: '0',
      minValidValue: 0,
      minError: null,
      sort_by: 'positive_pcs_pct',
      order: 'desc',
      page: 1,
      page_size: 20,
      loading: false,
      error: null,
      response: null,
      compareIds: [6523, 2984, 3644], // Blessing Muzarabani, Sikandar Raza, Kuldeep Yadav
      compareData: null,
      compareLoading: false,
    },
  };
}

export async function renderPressureReliabilityPage(container, params = {}) {
  destroyAllPriCharts();
  const initialTab = params.tab === 'bowling' || window.location.hash.includes('/pressure-reliability/bowling') ? 'bowling' : 'batting';
  const state = createInitialState(initialTab);

  // Loading Skeleton
  container.innerHTML = `
    <div class="space-y-6 animate-fadeIn">
      <div class="h-28 rounded-2xl bg-gradient-to-r from-[#EFF6FF] via-white to-[#FDF2F8] border border-[#E2E8F0] animate-pulse"></div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="h-44 rounded-2xl bg-white border border-[#E2E8F0] animate-pulse"></div>
        <div class="h-44 rounded-2xl bg-white border border-[#E2E8F0] animate-pulse"></div>
      </div>
      <div class="h-96 rounded-2xl bg-white border border-[#E2E8F0] animate-pulse"></div>
    </div>
  `;

  try {
    const [overview, filters] = await Promise.all([
      priApiService.getOverview(),
      priApiService.getFilters(),
    ]);
    state.overview = overview;
    state.filters = filters;
  } catch (err) {
    container.innerHTML = `
      <div class="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-2">
        <h2 class="text-base font-black">Unable to Load Pressure Reliability Service</h2>
        <p class="text-xs">${escapeHtml(err.message)}</p>
        <button id="pri-retry-init" class="px-3 py-1.5 rounded-lg bg-rose-600 text-white text-xs font-bold hover:bg-rose-700">Retry</button>
      </div>
    `;
    container.querySelector('#pri-retry-init')?.addEventListener('click', () => renderPressureReliabilityPage(container, params));
    return;
  }

  // Render full shell
  renderPageShell(container, state);

  // Initial data fetches for active tab + comparison
  await Promise.all([
    loadActiveLeaderboard(container, state),
    loadComparison(container, state),
  ]);
  renderAnalyticsCharts(container, state);
}

function renderOverviewCards(overview) {
  const bat = overview?.batting || {};
  const bowl = overview?.bowling || {};

  return `
    <section aria-label="Corpus-Level Pressure Reliability Overview" class="space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 class="text-xs font-black uppercase tracking-wider text-[#1E3A8A]">Corpus-Level Summary Statistics</h2>
          <p class="text-[11px] text-[#64748B]">Dataset-wide aggregates across ${formatNumber(bat.total_matches || 798)} T20 matches (2022–2026) — <strong>not individual player ratings</strong>. Batting and bowling are evaluated independently.</p>
        </div>
        <span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#F1F5F9] text-[#334155] border border-[#CBD5E1]">
          Unshrunk &bull; No Composite Score &bull; Dual-Axis
        </span>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <!-- Batting Overview Panel (Blue Accent) -->
        <div class="bg-white rounded-2xl border border-[#BFDBFE] border-t-4 border-t-[#3B82F6] p-4 sm:p-5 shadow-sm">
          <div class="flex items-center justify-between gap-2 mb-3">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-[#3B82F6]"></span>
              <h3 class="text-sm font-black text-[#1E3A8A]">Batting Reliability Corpus (T10)</h3>
            </div>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE]">mean_p &ge; 40 OR peak_p &ge; 60</span>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Pressure Innings</div>
              <div class="text-lg font-black text-[#0F172A] mt-0.5">${formatNumber(bat.total_qualifying_pressure_innings)}</div>
              <div class="text-[10px] text-[#64748B]">DNB strictly excluded</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Evaluated Batters</div>
              <div class="text-lg font-black text-[#2563EB] mt-0.5">${formatNumber(bat.evaluated_batters)}</div>
              <div class="text-[10px] text-[#64748B]">of ${formatNumber(bat.total_career_batters)} career</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Overall POS REL</div>
              <div class="text-lg font-black ${getPosRelTextClass(bat.overall_positive_hpc_pct)} mt-0.5">${Number(bat.overall_positive_hpc_pct || 0).toFixed(2)}%</div>
              <div class="text-[10px] text-[#64748B]">HPC &gt; 0 strictly</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Avg HPC (Pressure)</div>
              <div class="text-lg font-black ${getSignedColorClass(bat.avg_hpc_under_pressure)} mt-0.5">${formatSigned(bat.avg_hpc_under_pressure, 2)}</div>
              <div class="text-[10px] text-[#64748B]">Corpus mean HPC</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#F0FDF4] border border-[#BBF7D0]">
              <div class="text-[10px] font-bold uppercase text-[#15803D]">Positive Innings</div>
              <div class="text-lg font-black text-[#16A34A] mt-0.5">${formatNumber(bat.positive_pressure_innings)}</div>
              <div class="text-[10px] text-[#15803D]">HPC &gt; 0 (${bat.neutral_pressure_innings || 0} neutral)</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#FEF2F2] border border-[#FECACA]">
              <div class="text-[10px] font-bold uppercase text-[#B91C1C]">Negative Innings</div>
              <div class="text-lg font-black text-[#DC2626] mt-0.5">${formatNumber(bat.negative_pressure_innings)}</div>
              <div class="text-[10px] text-[#B91C1C]">HPC &lt; 0</div>
            </div>
          </div>
        </div>

        <!-- Bowling Overview Panel (Pink Accent) -->
        <div class="bg-white rounded-2xl border border-[#FBCFE8] border-t-4 border-t-[#EC4899] p-4 sm:p-5 shadow-sm">
          <div class="flex items-center justify-between gap-2 mb-3">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-[#EC4899]"></span>
              <h3 class="text-sm font-black text-[#9D174D]">Bowling Reliability Corpus (EXO_2)</h3>
            </div>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-[#FDF2F8] text-[#DB2777] border border-[#FBCFE8]">entry_pti &ge; 35 AND balls &ge; 12</span>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Pressure Spells</div>
              <div class="text-lg font-black text-[#0F172A] mt-0.5">${formatNumber(bowl.total_qualifying_pressure_spells)}</div>
              <div class="text-[10px] text-[#64748B]">Exogenous pre-over</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Evaluated Bowlers</div>
              <div class="text-lg font-black text-[#DB2777] mt-0.5">${formatNumber(bowl.evaluated_bowlers)}</div>
              <div class="text-[10px] text-[#64748B]">of ${formatNumber(bowl.total_career_bowlers)} career</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Overall POS REL</div>
              <div class="text-lg font-black ${getPosRelTextClass(bowl.overall_positive_pcs_pct)} mt-0.5">${Number(bowl.overall_positive_pcs_pct || 0).toFixed(2)}%</div>
              <div class="text-[10px] text-[#64748B]">PCS &gt; 50 strictly</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Avg PCS (Pressure)</div>
              <div class="text-lg font-black text-[#1E3A8A] mt-0.5">${Number(bowl.avg_pcs_under_pressure || 50).toFixed(2)}</div>
              <div class="text-[10px] text-[#64748B]">50.00 = neutral</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#F0FDF4] border border-[#BBF7D0]">
              <div class="text-[10px] font-bold uppercase text-[#15803D]">Positive Spells</div>
              <div class="text-lg font-black text-[#16A34A] mt-0.5">${formatNumber(bowl.positive_pressure_spells)}</div>
              <div class="text-[10px] text-[#15803D]">PCS &gt; 50 (${bowl.neutral_pressure_spells || 0} neutral)</div>
            </div>
            <div class="p-2.5 rounded-xl bg-[#FEF2F2] border border-[#FECACA]">
              <div class="text-[10px] font-bold uppercase text-[#B91C1C]">Negative Spells</div>
              <div class="text-lg font-black text-[#DC2626] mt-0.5">${formatNumber(bowl.negative_pressure_spells)}</div>
              <div class="text-[10px] text-[#B91C1C]">PCS &lt; 50</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderPageShell(container, state) {
  const isBat = state.activeTab === 'batting';
  const domainState = state[state.activeTab];
  const seasons = state.filters?.seasons || [];
  const tournaments = isBat ? (state.filters?.batting_tournaments || []) : (state.filters?.bowling_tournaments || []);
  const teams = isBat ? (state.filters?.batting_teams || []) : (state.filters?.bowling_teams || []);
  const playerOptions = isBat ? (state.filters?.batting_players || []) : (state.filters?.bowling_players || []);

  const title = isBat ? 'Most Reliable Batters Under Pressure' : 'Most Reliable Bowlers Under Pressure';
  const minLabel = isBat ? 'Minimum Pressure Innings' : 'Minimum Pressure Spells';
  const accentBorder = isBat ? 'border-[#3B82F6]' : 'border-[#EC4899]';
  const accentText = isBat ? 'text-[#1E3A8A]' : 'text-[#9D174D]';
  const accentBgSoft = isBat ? 'bg-[#EFF6FF]' : 'bg-[#FDF2F8]';
  const sortOptions = isBat
    ? [
        { val: 'positive_hpc_pct', label: 'Positive Reliability % (Default)' },
        { val: 'avg_hpc_under_pressure', label: 'Average HPC' },
        { val: 'total_hpc_under_pressure', label: 'Total HPC' },
        { val: 'pressure_innings', label: 'Pressure Innings Count' },
      ]
    : [
        { val: 'positive_pcs_pct', label: 'Positive Reliability % (Default)' },
        { val: 'avg_pcs_under_pressure', label: 'Average PCS' },
        { val: 'total_pressure_contribution_rpe', label: 'Total Pressure Contribution (RPE)' },
        { val: 'pressure_spells', label: 'Pressure Spells Count' },
      ];

  container.innerHTML = `
    <div class="space-y-6 animate-fadeIn pb-10">
      <!-- Page Header -->
      <div class="hero-gradient rounded-2xl p-5 sm:p-7 shadow-md">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div class="max-w-3xl">
            <div class="flex flex-wrap items-center gap-2 mb-2">
              <span class="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-white/20 text-white">Pressure Reliability Index (PRI)</span>
              <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-white/15 text-white">Zero Shrinkage &bull; Dual-Axis</span>
            </div>
            <h1 class="text-2xl sm:text-3xl font-black text-white tracking-tight">Pressure Reliability</h1>
            <p class="text-xs sm:text-sm text-white/90 mt-1.5 leading-relaxed">
              Identify which batters and bowlers consistently deliver positive contributions when facing genuinely difficult match situations.
              Reliability Rate and Contribution Quality are always reported separately with zero shrinkage.
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2 flex-shrink-0">
            <a href="#/settings?section=pri-metric-guide" id="pri-metric-guide-link" class="px-3.5 py-2 rounded-xl bg-white text-[#1E3A8A] text-xs font-extrabold hover:bg-[#EFF6FF] shadow-sm transition inline-flex items-center gap-1.5">
              <span>Metric Guide</span>
              <span aria-hidden="true">&rarr;</span>
            </a>
          </div>
        </div>
      </div>

      <!-- Corpus-Level Overview -->
      ${renderOverviewCards(state.overview)}

      <!-- Independent Batting / Bowling Tabs -->
      <div class="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden">
        <div class="border-b border-[#E2E8F0] px-4 sm:px-6 pt-4 flex flex-wrap items-center justify-between gap-3 bg-[#F8FAFC]/60">
          <div role="tablist" aria-label="Pressure Reliability Domains" class="flex items-center gap-2">
            <button
              role="tab"
              id="pri-tab-batting"
              aria-selected="${isBat ? 'true' : 'false'}"
              aria-controls="pri-tab-panel"
              class="px-4 py-2.5 text-xs sm:text-sm font-extrabold rounded-t-xl border-b-2 transition cursor-pointer ${
                isBat
                  ? 'bg-white text-[#1E3A8A] border-[#3B82F6] shadow-xs'
                  : 'text-[#64748B] border-transparent hover:text-[#0F172A] hover:bg-white/60'
              }"
            >
              Batting Reliability
            </button>
            <button
              role="tab"
              id="pri-tab-bowling"
              aria-selected="${!isBat ? 'true' : 'false'}"
              aria-controls="pri-tab-panel"
              class="px-4 py-2.5 text-xs sm:text-sm font-extrabold rounded-t-xl border-b-2 transition cursor-pointer ${
                !isBat
                  ? 'bg-white text-[#9D174D] border-[#EC4899] shadow-xs'
                  : 'text-[#64748B] border-transparent hover:text-[#0F172A] hover:bg-white/60'
              }"
            >
              Bowling Reliability
            </button>
          </div>
          <div class="pb-2 text-[11px] text-[#64748B]">
            ${
              isBat
                ? 'Positive: <strong class="text-[#16A34A]">HPC &gt; 0</strong> &bull; Negative: <strong class="text-[#DC2626]">HPC &lt; 0</strong> &bull; Neutral: <strong>HPC = 0</strong> (never positive)'
                : 'Positive: <strong class="text-[#16A34A]">PCS &gt; 50</strong> &bull; Negative: <strong class="text-[#DC2626]">PCS &lt; 50</strong> &bull; Neutral: <strong>PCS = 50</strong> (never positive)'
            }
          </div>
        </div>

        <div id="pri-tab-panel" role="tabpanel" class="p-4 sm:p-6 space-y-5">
          <!-- Leaderboard Title & Scope Switcher -->
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <h2 class="text-lg sm:text-xl font-black text-[#0F172A]">${title}</h2>
              <p class="text-xs text-[#64748B] mt-0.5">
                Default overall leaderboards apply the Stage B8 visibility policy. Click any player name to inspect their full pressure reliability profile.
              </p>
            </div>
            <!-- Scope Buttons: Career / Season / Tournament -->
            <div class="inline-flex rounded-xl bg-[#F1F5F9] p-1 border border-[#E2E8F0] self-start" role="group" aria-label="Aggregation Scope">
              ${['career', 'season', 'tournament']
                .map((sc) => {
                  const active = domainState.scope === sc;
                  const activeCls = isBat ? 'bg-[#3B82F6] text-white shadow-xs' : 'bg-[#EC4899] text-white shadow-xs';
                  return `<button data-pri-scope="${sc}" class="px-3 py-1.5 rounded-lg text-xs font-bold capitalize transition cursor-pointer ${
                    active ? activeCls : 'text-[#475569] hover:text-[#0F172A]'
                  }">${sc}</button>`;
                })
                .join('')}
            </div>
          </div>

          <!-- Filter Bar (Custom Numeric Min Input + Season/Tournament + Team + Search + Sort) -->
          <div class="p-4 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0] space-y-3">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-3 items-end">
              <!-- Custom Minimum Opportunity Input (NO fixed preset dropdown!) -->
              <div class="lg:col-span-3">
                <label for="pri-min-opp-input" class="block text-[11px] font-extrabold text-[#1E3A8A] mb-1">
                  ${minLabel}
                </label>
                <div class="flex items-center gap-1.5">
                  <input
                    id="pri-min-opp-input"
                    type="text"
                    inputmode="numeric"
                    autocomplete="off"
                    value="${escapeHtml(domainState.minInput)}"
                    placeholder="e.g. 0, 12, 18"
                    aria-describedby="pri-min-opp-help"
                    class="w-full px-3 py-2 text-xs font-bold rounded-lg bg-white border ${
                      domainState.minError ? 'border-[#DC2626] ring-1 ring-[#DC2626]' : 'border-[#CBD5E1] focus:border-[#3B82F6]'
                    } text-[#0F172A] focus:outline-none"
                  />
                  <button id="pri-min-opp-apply" class="px-3 py-2 rounded-lg text-xs font-bold text-white cursor-pointer transition ${
                    isBat ? 'bg-[#3B82F6] hover:bg-[#2563EB]' : 'bg-[#EC4899] hover:bg-[#DB2777]'
                  }">Apply</button>
                </div>
                <p id="pri-min-opp-help" class="text-[10px] mt-1 ${domainState.minError ? 'text-[#DC2626] font-bold' : 'text-[#64748B]'}">
                  ${domainState.minError ? escapeHtml(domainState.minError) : 'Any whole number ≥ 0 (0 = no minimum restriction)'}
                </p>
              </div>

              <!-- Season or Tournament Filter -->
              ${
                domainState.scope === 'season'
                  ? `
                  <div class="lg:col-span-2">
                    <label for="pri-season-select" class="block text-[11px] font-bold text-[#475569] mb-1">Season</label>
                    <select id="pri-season-select" class="w-full px-2.5 py-2 text-xs font-semibold rounded-lg bg-white border border-[#CBD5E1] text-[#0F172A]">
                      <option value="all" ${domainState.season === 'all' ? 'selected' : ''}>All Seasons</option>
                      ${seasons.map((yr) => `<option value="${escapeHtml(yr)}" ${domainState.season === String(yr) ? 'selected' : ''}>${escapeHtml(yr)}</option>`).join('')}
                    </select>
                  </div>
                `
                  : domainState.scope === 'tournament'
                    ? `
                    <div class="lg:col-span-3">
                      <label for="pri-tournament-select" class="block text-[11px] font-bold text-[#475569] mb-1">Tournament</label>
                      <select id="pri-tournament-select" class="w-full px-2.5 py-2 text-xs font-semibold rounded-lg bg-white border border-[#CBD5E1] text-[#0F172A]">
                        <option value="all" ${domainState.tournament === 'all' ? 'selected' : ''}>All Tournaments (Separate Rows)</option>
                        ${tournaments
                          .map(
                            (t) =>
                              `<option value="${t.comp_id}" ${String(domainState.tournament) === String(t.comp_id) ? 'selected' : ''}>${escapeHtml(t.comp_name)} (${escapeHtml(t.season)})</option>`
                          )
                          .join('')}
                      </select>
                    </div>
                  `
                    : ''
              }

              <!-- Team Filter -->
              <div class="${domainState.scope === 'tournament' ? 'lg:col-span-2' : 'lg:col-span-2'}">
                <label for="pri-team-select" class="block text-[11px] font-bold text-[#475569] mb-1">Team</label>
                <select id="pri-team-select" class="w-full px-2.5 py-2 text-xs font-semibold rounded-lg bg-white border border-[#CBD5E1] text-[#0F172A]">
                  <option value="all" ${domainState.team === 'all' ? 'selected' : ''}>All Teams</option>
                  ${teams.map((tm) => `<option value="${escapeHtml(tm)}" ${domainState.team === tm ? 'selected' : ''}>${escapeHtml(tm)}</option>`).join('')}
                </select>
              </div>

              <!-- Search Input -->
              <div class="${domainState.scope === 'career' ? 'lg:col-span-4' : domainState.scope === 'season' ? 'lg:col-span-2' : 'lg:col-span-2'}">
                <label for="pri-search-input" class="block text-[11px] font-bold text-[#475569] mb-1">Search Player / Team</label>
                <input
                  id="pri-search-input"
                  type="search"
                  value="${escapeHtml(domainState.search)}"
                  placeholder="Type player or team..."
                  class="w-full px-3 py-2 text-xs font-medium rounded-lg bg-white border border-[#CBD5E1] text-[#0F172A]"
                />
              </div>

              <!-- Sort Control -->
              <div class="${domainState.scope === 'tournament' ? 'lg:col-span-2' : 'lg:col-span-3'}">
                <label for="pri-sort-select" class="block text-[11px] font-bold text-[#475569] mb-1">Sort By</label>
                <div class="flex items-center gap-1.5">
                  <select id="pri-sort-select" class="w-full px-2.5 py-2 text-xs font-semibold rounded-lg bg-white border border-[#CBD5E1] text-[#0F172A]">
                    ${sortOptions.map((o) => `<option value="${o.val}" ${domainState.sort_by === o.val ? 'selected' : ''}>${o.label}</option>`).join('')}
                  </select>
                  <button id="pri-order-toggle" title="Toggle ascending / descending" class="px-2.5 py-2 rounded-lg bg-white border border-[#CBD5E1] text-xs font-bold text-[#334155] hover:bg-[#F1F5F9] cursor-pointer">
                    ${domainState.order === 'desc' ? '↓' : '↑'}
                  </button>
                </div>
              </div>
            </div>

            <!-- Unshrunk Evaluation Summary Strip -->
            <div class="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#E2E8F0] text-[11px] text-[#475569]">
              <div>
                <strong class="${accentText}">Pure Observed Metrics:</strong>
                All reliability percentages and contribution averages reflect exact unshrunk performance across actual qualifying pressure opportunities.
              </div>
              <div id="pri-result-count-pill" class="font-bold text-[#0F172A]">Loading...</div>
            </div>
          </div>

          <!-- Leaderboard Table Container -->
          <div id="pri-leaderboard-container">
            <div class="h-64 rounded-xl bg-[#F8FAFC] animate-pulse border border-[#E2E8F0]"></div>
          </div>
        </div>
      </div>

      <!-- Domain Visualizations Section (All 5 Required Charts per Tab) -->
      <section aria-label="${isBat ? 'Batting' : 'Bowling'} Reliability Visualizations" class="space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 class="text-base font-black text-[#0F172A]">${isBat ? 'Batting' : 'Bowling'} Pressure Reliability Analytics</h2>
            <p class="text-xs text-[#64748B]">Outcome polarity, seasonal consistency trends, contribution quality, and opportunity distribution.</p>
          </div>
          <span class="px-2.5 py-1 rounded-full text-[10px] font-bold ${accentBgSoft} ${accentText} border ${accentBorder}">
            ${isBat ? 'T10 Batting Corpus' : 'EXO_2 Bowling Corpus'}
          </span>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="bg-white rounded-2xl border border-[#E2E8F0] p-4 shadow-sm">
            <h3 class="text-xs font-black uppercase tracking-wider text-[#475569] mb-2">
              1. Positive vs Negative vs Neutral ${isBat ? 'Innings' : 'Spells'}
            </h3>
            <div class="h-56 relative"><canvas id="pri-chart-polarity"></canvas></div>
          </div>

          <div class="bg-white rounded-2xl border border-[#E2E8F0] p-4 shadow-sm">
            <h3 class="text-xs font-black uppercase tracking-wider text-[#475569] mb-2">
              2. Season-Wise Positive ${isBat ? 'HPC' : 'PCS'} %
            </h3>
            <div class="h-56 relative"><canvas id="pri-chart-season-rate"></canvas></div>
          </div>

          <div class="bg-white rounded-2xl border border-[#E2E8F0] p-4 shadow-sm">
            <h3 class="text-xs font-black uppercase tracking-wider text-[#475569] mb-2">
              3. Average ${isBat ? 'HPC' : 'PCS'} Under Pressure by Season
            </h3>
            <div class="h-56 relative"><canvas id="pri-chart-season-avg"></canvas></div>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div class="bg-white rounded-2xl border border-[#E2E8F0] p-4 shadow-sm">
            <h3 class="text-xs font-black uppercase tracking-wider text-[#475569] mb-2">
              4. Total ${isBat ? 'HPC' : 'Pressure Contribution (RPE)'} by Season
            </h3>
            <div class="h-64 relative"><canvas id="pri-chart-season-total"></canvas></div>
          </div>

          <div class="bg-white rounded-2xl border border-[#E2E8F0] p-4 shadow-sm">
            <h3 class="text-xs font-black uppercase tracking-wider text-[#475569] mb-2">
              5. Reliability % vs ${isBat ? 'Pressure Innings' : 'Pressure Spells'} (Sample Funnel)
            </h3>
            <div class="h-64 relative"><canvas id="pri-chart-scatter"></canvas></div>
          </div>
        </div>
      </section>

      <!-- Up-to-5 Player Comparison Section (Strictly Batting-only or Bowling-only) -->
      <section aria-label="Compare Up to Five ${isBat ? 'Batters' : 'Bowlers'}" class="bg-white rounded-2xl border border-[#E2E8F0] p-5 shadow-sm space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#F1F5F9] pb-3">
          <div>
            <h2 class="text-base font-black text-[#0F172A]">Compare Up to 5 ${isBat ? 'Batters' : 'Bowlers'} Under Pressure</h2>
            <p class="text-xs text-[#64748B]">Compare positive reliability %, average ${isBat ? 'HPC' : 'PCS'}, total contribution, and pressure opportunities side by side.</p>
          </div>
          <div class="flex items-center gap-2">
            <select id="pri-compare-add-select" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#F8FAFC] border border-[#CBD5E1] text-[#0F172A] max-w-[240px]">
              <option value="">+ Add ${isBat ? 'Batter' : 'Bowler'} to compare...</option>
              ${playerOptions
                .map((p) => {
                  const id = isBat ? p.player_id : p.bowler_id;
                  const nm = isBat ? p.batter_name : p.bowler_name;
                  const n = isBat ? p.pressure_innings : p.pressure_spells;
                  return `<option value="${id}">${escapeHtml(nm)} (${n} opps)</option>`;
                })
                .join('')}
            </select>
            <button id="pri-compare-clear" class="px-2.5 py-1.5 rounded-lg text-xs font-bold text-[#64748B] bg-[#F1F5F9] hover:bg-[#E2E8F0] cursor-pointer">Clear</button>
          </div>
        </div>

        <div id="pri-compare-chips" class="flex flex-wrap gap-2"></div>
        <div id="pri-compare-body" class="space-y-4">
          <div class="h-44 rounded-xl bg-[#F8FAFC] animate-pulse"></div>
        </div>
      </section>
    </div>
  `;

  attachPageEvents(container, state);
}

function attachPageEvents(container, state) {
  const isBat = state.activeTab === 'batting';
  const domainState = state[state.activeTab];

  // Tab switchers
  container.querySelector('#pri-tab-batting')?.addEventListener('click', async () => {
    if (state.activeTab === 'batting') return;
    destroyAllPriCharts();
    state.activeTab = 'batting';
    renderPageShell(container, state);
    await Promise.all([loadActiveLeaderboard(container, state), loadComparison(container, state)]);
    renderAnalyticsCharts(container, state);
  });

  container.querySelector('#pri-tab-bowling')?.addEventListener('click', async () => {
    if (state.activeTab === 'bowling') return;
    destroyAllPriCharts();
    state.activeTab = 'bowling';
    renderPageShell(container, state);
    await Promise.all([loadActiveLeaderboard(container, state), loadComparison(container, state)]);
    renderAnalyticsCharts(container, state);
  });

  // Scope switchers (Career / Season / Tournament)
  container.querySelectorAll('[data-pri-scope]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const nextScope = btn.getAttribute('data-pri-scope');
      if (domainState.scope === nextScope) return;
      domainState.scope = nextScope;
      domainState.page = 1;
      destroyAllPriCharts();
      renderPageShell(container, state);
      await Promise.all([loadActiveLeaderboard(container, state), loadComparison(container, state)]);
      renderAnalyticsCharts(container, state);
    });
  });

  // Custom Minimum Opportunity Input (apply on Enter, Apply button, or valid debounced change)
  const minInputEl = container.querySelector('#pri-min-opp-input');
  const minHelpEl = container.querySelector('#pri-min-opp-help');
  const applyMin = async () => {
    const raw = minInputEl ? minInputEl.value : '0';
    domainState.minInput = raw;
    const check = validateCustomMinInput(raw);
    if (!check.valid) {
      domainState.minError = check.error;
      if (minInputEl) minInputEl.className = 'w-full px-3 py-2 text-xs font-bold rounded-lg bg-white border border-[#DC2626] ring-1 ring-[#DC2626] text-[#0F172A] focus:outline-none';
      if (minHelpEl) {
        minHelpEl.className = 'text-[10px] mt-1 text-[#DC2626] font-bold';
        minHelpEl.textContent = check.error;
      }
      return;
    }
    domainState.minError = null;
    domainState.minValidValue = check.value;
    domainState.page = 1;
    if (minInputEl) minInputEl.className = 'w-full px-3 py-2 text-xs font-bold rounded-lg bg-white border border-[#CBD5E1] focus:border-[#3B82F6] text-[#0F172A] focus:outline-none';
    if (minHelpEl) {
      minHelpEl.className = 'text-[10px] mt-1 text-[#64748B]';
      minHelpEl.textContent = check.value === 0 ? 'Showing all evaluated players (no minimum restriction)' : `Filtering for ≥ ${check.value} qualifying pressure ${isBat ? 'innings' : 'spells'}`;
    }
    await loadActiveLeaderboard(container, state);
  };

  let minDebounce = null;
  minInputEl?.addEventListener('input', () => {
    clearTimeout(minDebounce);
    minDebounce = setTimeout(applyMin, 300);
  });
  minInputEl?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      clearTimeout(minDebounce);
      applyMin();
    }
  });
  container.querySelector('#pri-min-opp-apply')?.addEventListener('click', () => {
    clearTimeout(minDebounce);
    applyMin();
  });

  // Season / Tournament / Team / Search / Sort
  container.querySelector('#pri-season-select')?.addEventListener('change', async (e) => {
    domainState.season = e.target.value;
    domainState.page = 1;
    await loadActiveLeaderboard(container, state);
  });

  container.querySelector('#pri-tournament-select')?.addEventListener('change', async (e) => {
    domainState.tournament = e.target.value;
    domainState.page = 1;
    await loadActiveLeaderboard(container, state);
  });

  container.querySelector('#pri-team-select')?.addEventListener('change', async (e) => {
    domainState.team = e.target.value;
    domainState.page = 1;
    await loadActiveLeaderboard(container, state);
  });

  let searchTimer = null;
  container.querySelector('#pri-search-input')?.addEventListener('input', (e) => {
    domainState.search = e.target.value;
    domainState.page = 1;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadActiveLeaderboard(container, state), 260);
  });

  container.querySelector('#pri-sort-select')?.addEventListener('change', async (e) => {
    domainState.sort_by = e.target.value;
    domainState.page = 1;
    await loadActiveLeaderboard(container, state);
  });

  container.querySelector('#pri-order-toggle')?.addEventListener('click', async (e) => {
    domainState.order = domainState.order === 'desc' ? 'asc' : 'desc';
    e.currentTarget.textContent = domainState.order === 'desc' ? '↓' : '↑';
    domainState.page = 1;
    await loadActiveLeaderboard(container, state);
  });

  // Comparison add/clear
  container.querySelector('#pri-compare-add-select')?.addEventListener('change', async (e) => {
    const val = Number(e.target.value);
    e.target.value = '';
    if (!val) return;
    if (domainState.compareIds.includes(val)) return;
    if (domainState.compareIds.length >= 5) {
      alert(`You can compare up to 5 ${isBat ? 'batters' : 'bowlers'} at a time.`);
      return;
    }
    domainState.compareIds = [...domainState.compareIds, val];
    await loadComparison(container, state);
  });

  container.querySelector('#pri-compare-clear')?.addEventListener('click', async () => {
    domainState.compareIds = [];
    domainState.compareData = null;
    destroyChart('compare');
    renderComparisonSection(container, state);
  });
}

async function loadActiveLeaderboard(container, state) {
  const isBat = state.activeTab === 'batting';
  const domainState = state[state.activeTab];
  const tableBox = container.querySelector('#pri-leaderboard-container');
  const countPill = container.querySelector('#pri-result-count-pill');
  if (!tableBox) return;

  domainState.loading = true;
  tableBox.innerHTML = `<div class="h-56 rounded-xl bg-[#F8FAFC] animate-pulse border border-[#E2E8F0]"></div>`;

  try {
    const params = {
      min_opportunities: domainState.minValidValue,
      season: domainState.scope === 'season' ? domainState.season : undefined,
      tournament: domainState.scope === 'tournament' ? domainState.tournament : undefined,
      team: domainState.team,
      search: domainState.search,
      sort_by: domainState.sort_by,
      order: domainState.order,
      page: domainState.page,
      page_size: domainState.page_size,
    };
    const res = isBat
      ? await priApiService.getBattingLeaderboard(domainState.scope, params)
      : await priApiService.getBowlingLeaderboard(domainState.scope, params);
    domainState.response = res;
    domainState.error = null;
  } catch (err) {
    domainState.error = err.message;
  } finally {
    domainState.loading = false;
  }

  if (domainState.error) {
    tableBox.innerHTML = `
      <div class="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
        <strong>Error loading leaderboard:</strong> ${escapeHtml(domainState.error)}
      </div>
    `;
    if (countPill) countPill.textContent = 'Error';
    return;
  }

  const data = domainState.response;
  const items = data?.items || [];
  const pag = data?.pagination || { page: 1, total_pages: 1, total_items: 0 };

  if (countPill) {
    countPill.textContent = `${formatNumber(pag.total_items)} eligible ${isBat ? 'batters' : 'bowlers'} (page ${pag.page}/${pag.total_pages})`;
  }

  if (items.length === 0) {
    tableBox.innerHTML = `
      <div class="p-8 text-center rounded-xl bg-[#F8FAFC] border border-dashed border-[#CBD5E1] space-y-2">
        <div class="text-sm font-black text-[#334155]">No Matching Players Found</div>
        <p class="text-xs text-[#64748B]">
          No ${isBat ? 'batters' : 'bowlers'} met your filter criteria (minimum ${domainState.minValidValue} qualifying pressure ${isBat ? 'innings' : 'spells'}).
          Try lowering the minimum threshold or clearing team/search filters.
        </p>
      </div>
    `;
    return;
  }

  const scopeColHeader =
    domainState.scope === 'tournament'
      ? 'Tournament'
      : domainState.scope === 'season'
        ? 'Season'
        : 'Scope';

  tableBox.innerHTML = `
    <div class="overflow-x-auto rounded-xl border border-[#E2E8F0]">
      <table class="w-full text-left border-collapse text-xs">
        <thead class="${isBat ? 'bg-[#EFF6FF] text-[#1E3A8A]' : 'bg-[#FDF2F8] text-[#9D174D]'} text-[11px] uppercase font-extrabold">
          ${
            isBat
              ? `
                <tr>
                  <th class="py-3 px-3 whitespace-nowrap">Rank</th>
                  <th class="py-3 px-3 whitespace-nowrap">Player</th>
                  <th class="py-3 px-3 whitespace-nowrap">Team</th>
                  <th class="py-3 px-3 whitespace-nowrap">${scopeColHeader}</th>
                  <th class="py-3 px-3.5 text-right whitespace-nowrap">Total HPC</th>
                  <th class="py-3 px-3.5 text-right whitespace-nowrap">POS REL</th>
                  <th class="py-3 px-3 text-right whitespace-nowrap">Pressure Innings</th>
                  <th class="py-3 px-3.5 text-right whitespace-nowrap">Avg HPC</th>
                  <th class="py-3 px-3 text-right whitespace-nowrap text-[#15803D]">Pos HPC</th>
                  <th class="py-3 px-3 text-right whitespace-nowrap text-[#B91C1C]">Neg HPC</th>
                  <th class="py-3 px-3 text-right whitespace-nowrap text-[#64748B]">Neu HPC</th>
                </tr>
              `
              : `
                <tr>
                  <th class="py-3 px-3 whitespace-nowrap">Rank</th>
                  <th class="py-3 px-3 whitespace-nowrap">Bowler</th>
                  <th class="py-3 px-3 whitespace-nowrap">Team</th>
                  <th class="py-3 px-3 whitespace-nowrap">${scopeColHeader}</th>
                  <th class="py-3 px-3 text-right whitespace-nowrap">Pressure Spells</th>
                  <th class="py-3 px-3 text-right whitespace-nowrap text-[#15803D]">Pos PCS</th>
                  <th class="py-3 px-3 text-right whitespace-nowrap text-[#B91C1C]">Neg PCS</th>
                  <th class="py-3 px-3 text-right whitespace-nowrap text-[#64748B]">Neu PCS</th>
                  <th class="py-3 px-3.5 text-right whitespace-nowrap">POS REL</th>
                  <th class="py-3 px-3.5 text-right whitespace-nowrap">Avg PCS</th>
                  <th class="py-3 px-3.5 text-right whitespace-nowrap">Total Contrib (RPE)</th>
                </tr>
              `
          }
        </thead>
        <tbody class="divide-y divide-[#F1F5F9] bg-white">
          ${items
            .map((r) => {
              const pid = isBat ? r.player_id : r.bowler_id;
              const pname = isBat ? r.batter_name : r.bowler_name;
              const opps = isBat ? r.pressure_innings : r.pressure_spells;
              const posN = isBat ? r.positive_hpc_innings : r.positive_pcs_spells;
              const negN = isBat ? r.negative_hpc_innings : r.negative_pcs_spells;
              const neuN = isBat ? r.neutral_hpc_innings : r.neutral_pcs_spells;
              const relPct = isBat ? r.positive_hpc_pct : r.positive_pcs_pct;
              const avgVal = isBat ? r.avg_hpc_under_pressure : r.avg_pcs_under_pressure;
              const totVal = isBat ? r.total_hpc_under_pressure : r.total_pressure_contribution_rpe;
              const scopeCell =
                domainState.scope === 'tournament'
                  ? `<span class="font-medium text-[#334155]">${escapeHtml(r.comp_name || '—')}</span>`
                  : domainState.scope === 'season'
                    ? `<span class="px-2 py-0.5 rounded bg-[#F1F5F9] font-bold text-[#334155]">${escapeHtml(r.season || '—')}</span>`
                    : `<span class="px-2 py-0.5 rounded bg-[#F1F5F9] font-semibold text-[#64748B]">Career</span>`;
              const profileHref = isBat
                ? `#/pressure-reliability/batting/player/${pid}`
                : `#/pressure-reliability/bowling/player/${pid}`;
              const inCompare = domainState.compareIds.includes(Number(pid));
              const posRelBadge = `<span class="px-2 py-0.5 rounded-md font-black ${getPosRelBadgeClass(relPct)}">${Number(relPct).toFixed(2)}%</span>`;

              const avgDisplay = isBat
                ? `<span class="font-bold ${getSignedColorClass(avgVal)}">${formatSigned(avgVal, 2)}</span>`
                : `<span class="font-bold ${avgVal > 50 ? 'text-[#16A34A]' : avgVal < 50 ? 'text-[#DC2626]' : 'text-[#64748B]'}">${Number(avgVal).toFixed(2)}</span>`;

              const playerCell = `
                <td class="py-2.5 px-3 whitespace-nowrap">
                  <div class="flex items-center gap-2">
                    <a href="${profileHref}" class="font-extrabold ${isBat ? 'text-[#1E3A8A] hover:text-[#3B82F6]' : 'text-[#9D174D] hover:text-[#EC4899]'} hover:underline">
                      ${escapeHtml(pname)}
                    </a>
                    <button
                      data-pri-compare-add="${pid}"
                      title="${inCompare ? 'Already in comparison' : 'Add to comparison'}"
                      class="text-[10px] px-1.5 py-0.5 rounded border cursor-pointer transition ${
                        inCompare
                          ? 'bg-[#DCFCE7] text-[#15803D] border-[#86EFAC] font-bold'
                          : 'bg-white text-[#64748B] border-[#CBD5E1] hover:border-[#3B82F6] hover:text-[#1E3A8A]'
                      }"
                    >${inCompare ? '✓' : '+Cmp'}</button>
                  </div>
                </td>
              `;

              if (isBat) {
                return `
                  <tr class="hover:bg-[#F8FAFC] transition-colors">
                    <td class="py-2.5 px-3 font-black text-[#64748B]">#${r.rank}</td>
                    ${playerCell}
                    <td class="py-2.5 px-3 text-[#475569] whitespace-nowrap">${escapeHtml(r.primary_team || '—')}</td>
                    <td class="py-2.5 px-3 whitespace-nowrap max-w-[200px] truncate" title="${escapeHtml(r.comp_name || r.season || 'Career')}">${scopeCell}</td>
                    <td class="py-2.5 px-3.5 text-right font-black ${getSignedColorClass(totVal)} whitespace-nowrap">${formatSigned(totVal, 2)}</td>
                    <td class="py-2.5 px-3.5 text-right whitespace-nowrap">${posRelBadge}</td>
                    <td class="py-2.5 px-3 text-right font-black text-[#0F172A]">${opps}</td>
                    <td class="py-2.5 px-3.5 text-right whitespace-nowrap">${avgDisplay}</td>
                    <td class="py-2.5 px-3 text-right font-bold text-[#16A34A]">${posN}</td>
                    <td class="py-2.5 px-3 text-right font-bold text-[#DC2626]">${negN}</td>
                    <td class="py-2.5 px-3 text-right font-semibold text-[#64748B]">${neuN}</td>
                  </tr>
                `;
              }

              return `
                <tr class="hover:bg-[#F8FAFC] transition-colors">
                  <td class="py-2.5 px-3 font-black text-[#64748B]">#${r.rank}</td>
                  ${playerCell}
                  <td class="py-2.5 px-3 text-[#475569] whitespace-nowrap">${escapeHtml(r.primary_team || '—')}</td>
                  <td class="py-2.5 px-3 whitespace-nowrap max-w-[200px] truncate" title="${escapeHtml(r.comp_name || r.season || 'Career')}">${scopeCell}</td>
                  <td class="py-2.5 px-3 text-right font-black text-[#0F172A]">${opps}</td>
                  <td class="py-2.5 px-3 text-right font-bold text-[#16A34A]">${posN}</td>
                  <td class="py-2.5 px-3 text-right font-bold text-[#DC2626]">${negN}</td>
                  <td class="py-2.5 px-3 text-right font-semibold text-[#64748B]">${neuN}</td>
                  <td class="py-2.5 px-3.5 text-right whitespace-nowrap">${posRelBadge}</td>
                  <td class="py-2.5 px-3.5 text-right whitespace-nowrap">${avgDisplay}</td>
                  <td class="py-2.5 px-3.5 text-right font-bold ${getSignedColorClass(totVal)} whitespace-nowrap">${formatSigned(totVal, 2)}</td>
                </tr>
              `;
            })
            .join('')}
        </tbody>
      </table>
    </div>

    <!-- Pagination Bar -->
    <div class="flex flex-wrap items-center justify-between gap-3 pt-3 text-xs text-[#475569]">
      <div>
        Showing <strong>${(pag.page - 1) * pag.page_size + 1}–${Math.min(pag.page * pag.page_size, pag.total_items)}</strong> of <strong>${formatNumber(pag.total_items)}</strong> eligible records
      </div>
      <div class="flex items-center gap-2">
        <button id="pri-page-prev" ${!pag.has_prev ? 'disabled' : ''} class="px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white font-bold disabled:opacity-40 hover:bg-[#F8FAFC] cursor-pointer">
          &larr; Prev
        </button>
        <span class="font-bold text-[#0F172A] px-2">Page ${pag.page} of ${pag.total_pages}</span>
        <button id="pri-page-next" ${!pag.has_next ? 'disabled' : ''} class="px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white font-bold disabled:opacity-40 hover:bg-[#F8FAFC] cursor-pointer">
          Next &rarr;
        </button>
      </div>
    </div>
  `;

  // Wire pagination + quick compare buttons
  tableBox.querySelector('#pri-page-prev')?.addEventListener('click', async () => {
    if (domainState.page > 1) {
      domainState.page -= 1;
      await loadActiveLeaderboard(container, state);
    }
  });
  tableBox.querySelector('#pri-page-next')?.addEventListener('click', async () => {
    if (pag.has_next) {
      domainState.page += 1;
      await loadActiveLeaderboard(container, state);
    }
  });
  tableBox.querySelectorAll('[data-pri-compare-add]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.getAttribute('data-pri-compare-add'));
      if (domainState.compareIds.includes(id)) {
        domainState.compareIds = domainState.compareIds.filter((x) => x !== id);
      } else {
        if (domainState.compareIds.length >= 5) {
          alert(`You can compare up to 5 ${isBat ? 'batters' : 'bowlers'} at once.`);
          return;
        }
        domainState.compareIds = [...domainState.compareIds, id];
      }
      await Promise.all([loadActiveLeaderboard(container, state), loadComparison(container, state)]);
    });
  });
}

function renderAnalyticsCharts(container, state) {
  if (typeof Chart === 'undefined') return;
  const isBat = state.activeTab === 'batting';
  const data = isBat ? state.overview?.batting : state.overview?.bowling;
  if (!data) return;

  const seasons = (data.season_series || []).map((s) => s.season);
  const posCnt = isBat ? data.positive_pressure_innings : data.positive_pressure_spells;
  const negCnt = isBat ? data.negative_pressure_innings : data.negative_pressure_spells;
  const neuCnt = isBat ? data.neutral_pressure_innings : data.neutral_pressure_spells;

  // 1. Positive vs Negative vs Neutral Doughnut
  destroyChart('polarity');
  const ctx1 = container.querySelector('#pri-chart-polarity');
  if (ctx1) {
    ACTIVE_CHARTS.polarity = new Chart(ctx1, {
      type: 'doughnut',
      data: {
        labels: [`Positive (${formatNumber(posCnt)})`, `Negative (${formatNumber(negCnt)})`, `Neutral (${formatNumber(neuCnt)})`],
        datasets: [
          {
            data: [posCnt, negCnt, neuCnt],
            backgroundColor: ['#16A34A', '#DC2626', '#94A3B8'],
            borderColor: '#FFFFFF',
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11, weight: 'bold' } } },
        },
      },
    });
  }

  // 2. Season-Wise Positive Reliability %
  destroyChart('seasonRate');
  const ctx2 = container.querySelector('#pri-chart-season-rate');
  if (ctx2) {
    const rateSeries = (data.season_series || []).map((s) => (isBat ? s.positive_hpc_pct : s.positive_pcs_pct));
    ACTIVE_CHARTS.seasonRate = new Chart(ctx2, {
      type: 'line',
      data: {
        labels: seasons,
        datasets: [
          {
            label: isBat ? 'Positive HPC %' : 'Positive PCS %',
            data: rateSeries,
            borderColor: isBat ? '#3B82F6' : '#EC4899',
            backgroundColor: isBat ? 'rgba(59, 130, 246, 0.14)' : 'rgba(236, 72, 153, 0.14)',
            fill: true,
            tension: 0.3,
            pointRadius: 4,
            pointBackgroundColor: isBat ? '#1E3A8A' : '#DB2777',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            ticks: { callback: (v) => `${v}%`, font: { size: 10 } },
          },
          x: { ticks: { font: { size: 10 } } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  // 3. Average Contribution Under Pressure by Season
  destroyChart('seasonAvg');
  const ctx3 = container.querySelector('#pri-chart-season-avg');
  if (ctx3) {
    const avgSeries = (data.season_series || []).map((s) => (isBat ? s.avg_hpc_under_pressure : s.avg_pcs_under_pressure));
    const neutralRef = isBat ? 0 : 50;
    ACTIVE_CHARTS.seasonAvg = new Chart(ctx3, {
      type: 'bar',
      data: {
        labels: seasons,
        datasets: [
          {
            label: isBat ? 'Avg HPC' : 'Avg PCS',
            data: avgSeries,
            backgroundColor: avgSeries.map((v) => (v >= neutralRef ? 'rgba(22, 163, 74, 0.78)' : 'rgba(220, 38, 38, 0.78)')),
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            suggestedMin: isBat ? -2 : 45,
            suggestedMax: isBat ? 1 : 55,
            ticks: { font: { size: 10 } },
          },
          x: { ticks: { font: { size: 10 } } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  // 4. Total Contribution Under Pressure by Season
  destroyChart('seasonTotal');
  const ctx4 = container.querySelector('#pri-chart-season-total');
  if (ctx4) {
    const totSeries = (data.season_series || []).map((s) =>
      isBat ? s.total_hpc_under_pressure : s.total_pressure_contribution_rpe
    );
    ACTIVE_CHARTS.seasonTotal = new Chart(ctx4, {
      type: 'bar',
      data: {
        labels: seasons,
        datasets: [
          {
            label: isBat ? 'Total HPC' : 'Total Pressure Contribution (RPE)',
            data: totSeries,
            backgroundColor: totSeries.map((v) => (v >= 0 ? (isBat ? '#3B82F6' : '#EC4899') : '#DC2626')),
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { ticks: { font: { size: 10 } } },
          x: { ticks: { font: { size: 10 } } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  // 5. Reliability % vs Opportunity Count Scatter
  destroyChart('scatter');
  const ctx5 = container.querySelector('#pri-chart-scatter');
  if (ctx5) {
    const pts = (data.scatter_points || []).map((p) => ({
      x: isBat ? p.pressure_innings : p.pressure_spells,
      y: isBat ? p.positive_hpc_pct : p.positive_pcs_pct,
      name: isBat ? p.batter_name : p.bowler_name,
      avg: isBat ? p.avg_hpc_under_pressure : p.avg_pcs_under_pressure,
    }));
    ACTIVE_CHARTS.scatter = new Chart(ctx5, {
      type: 'scatter',
      data: {
        datasets: [
          {
            label: isBat ? 'Batters (≥ 3 Pressure Inns)' : 'Bowlers (≥ 3 Pressure Spells)',
            data: pts,
            backgroundColor: isBat ? 'rgba(59, 130, 246, 0.55)' : 'rgba(236, 72, 153, 0.55)',
            borderColor: isBat ? '#1E3A8A' : '#DB2777',
            pointRadius: 4,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { title: { display: true, text: isBat ? 'Qualifying Pressure Innings' : 'Qualifying Pressure Spells', font: { size: 11, weight: 'bold' } } },
          y: {
            beginAtZero: true,
            max: 100,
            title: { display: true, text: 'Positive Reliability %', font: { size: 11, weight: 'bold' } },
            ticks: { callback: (v) => `${v}%` },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const raw = ctx.raw;
                return `${raw.name}: ${Number(raw.y).toFixed(1)}% (${raw.x} opps) | Avg ${isBat ? 'HPC' : 'PCS'}: ${raw.avg}`;
              },
            },
          },
        },
      },
    });
  }
}

async function loadComparison(container, state) {
  const isBat = state.activeTab === 'batting';
  const domainState = state[state.activeTab];
  if (!domainState.compareIds.length) {
    domainState.compareData = null;
    renderComparisonSection(container, state);
    return;
  }
  domainState.compareLoading = true;
  try {
    domainState.compareData = isBat
      ? await priApiService.compareBatters(domainState.compareIds)
      : await priApiService.compareBowlers(domainState.compareIds);
  } catch (err) {
    domainState.compareData = { error: err.message, players: [] };
  } finally {
    domainState.compareLoading = false;
  }
  renderComparisonSection(container, state);
}

function renderComparisonSection(container, state) {
  const isBat = state.activeTab === 'batting';
  const domainState = state[state.activeTab];
  const chipsEl = container.querySelector('#pri-compare-chips');
  const bodyEl = container.querySelector('#pri-compare-body');
  if (!chipsEl || !bodyEl) return;

  const players = domainState.compareData?.players || [];

  chipsEl.innerHTML = players
    .map((p) => {
      const id = isBat ? p.player_id : p.bowler_id;
      const nm = isBat ? p.batter_name : p.bowler_name;
      return `
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
          isBat ? 'bg-[#EFF6FF] text-[#1E3A8A] border border-[#BFDBFE]' : 'bg-[#FDF2F8] text-[#9D174D] border border-[#FBCFE8]'
        }">
          <span>${escapeHtml(nm)}</span>
          <button data-pri-compare-remove="${id}" class="hover:text-[#DC2626] font-black cursor-pointer" aria-label="Remove ${escapeHtml(nm)}">&times;</button>
        </span>
      `;
    })
    .join('');

  chipsEl.querySelectorAll('[data-pri-compare-remove]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = Number(btn.getAttribute('data-pri-compare-remove'));
      domainState.compareIds = domainState.compareIds.filter((x) => x !== id);
      await Promise.all([loadActiveLeaderboard(container, state), loadComparison(container, state)]);
    });
  });

  if (players.length === 0) {
    destroyChart('compare');
    bodyEl.innerHTML = `
      <div class="p-6 text-center rounded-xl bg-[#F8FAFC] border border-dashed border-[#CBD5E1] text-xs text-[#64748B]">
        Select up to 5 ${isBat ? 'batters' : 'bowlers'} using the dropdown above or the <strong>+Cmp</strong> button in the leaderboard to compare them.
      </div>
    `;
    return;
  }

  bodyEl.innerHTML = `
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-${Math.min(players.length, 5)} gap-3">
      ${players
        .map((p) => {
          const id = isBat ? p.player_id : p.bowler_id;
          const nm = isBat ? p.batter_name : p.bowler_name;
          const opps = isBat ? p.pressure_innings : p.pressure_spells;
          const rel = isBat ? p.positive_hpc_pct : p.positive_pcs_pct;
          const avg = isBat ? p.avg_hpc_under_pressure : p.avg_pcs_under_pressure;
          const tot = isBat ? p.total_hpc_under_pressure : p.total_pressure_contribution_rpe;
          const href = isBat ? `#/pressure-reliability/batting/player/${id}` : `#/pressure-reliability/bowling/player/${id}`;
          const relBadge = rel !== null
            ? `<span class="inline-block px-1.5 py-0.5 rounded font-black text-xs ${getPosRelBadgeClass(rel)}">${Number(rel).toFixed(1)}%</span>`
            : `<span class="text-sm font-black text-[#64748B]">—</span>`;

          if (isBat) {
            return `
              <div class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] space-y-2">
                <a href="${href}" class="text-xs font-black text-[#1E3A8A] hover:underline block truncate">${escapeHtml(nm)}</a>
                <div class="grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <div class="text-[10px] text-[#64748B] font-semibold">Total HPC</div>
                    <div class="text-sm font-black ${tot !== null ? getSignedColorClass(tot) : 'text-[#64748B]'}">${tot !== null ? formatSigned(tot, 2) : '—'}</div>
                  </div>
                  <div>
                    <div class="text-[10px] text-[#64748B] font-semibold">POS REL</div>
                    <div class="mt-0.5">${relBadge}</div>
                  </div>
                  <div>
                    <div class="text-[10px] text-[#64748B] font-semibold">Pressure Innings</div>
                    <div class="font-extrabold text-[#0F172A]">${opps}</div>
                  </div>
                  <div>
                    <div class="text-[10px] text-[#64748B] font-semibold">Avg HPC</div>
                    <div class="font-extrabold text-[#0F172A]">${avg !== null ? formatSigned(avg, 2) : '—'}</div>
                  </div>
                </div>
              </div>
            `;
          }

          return `
            <div class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] space-y-2">
              <a href="${href}" class="text-xs font-black text-[#9D174D] hover:underline block truncate">${escapeHtml(nm)}</a>
              <div class="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <div class="text-[10px] text-[#64748B] font-semibold">POS REL</div>
                  <div class="mt-0.5">${relBadge}</div>
                </div>
                <div>
                  <div class="text-[10px] text-[#64748B] font-semibold">Avg PCS</div>
                  <div class="text-sm font-black text-[#0F172A]">${avg !== null ? Number(avg).toFixed(2) : '—'}</div>
                </div>
                <div>
                  <div class="text-[10px] text-[#64748B] font-semibold">Pressure Spells</div>
                  <div class="font-extrabold text-[#0F172A]">${opps}</div>
                </div>
                <div>
                  <div class="text-[10px] text-[#64748B] font-semibold">Total RPE</div>
                  <div class="font-extrabold ${tot !== null ? getSignedColorClass(tot) : 'text-[#64748B]'}">${tot !== null ? formatSigned(tot, 2) : '—'}</div>
                </div>
              </div>
            </div>
          `;
        })
        .join('')}
    </div>
    <div class="h-64 relative pt-2"><canvas id="pri-chart-compare"></canvas></div>
  `;

  if (typeof Chart !== 'undefined') {
    destroyChart('compare');
    const ctx = bodyEl.querySelector('#pri-chart-compare');
    if (ctx) {
      const labels = players.map((p) => (isBat ? p.batter_name : p.bowler_name));
      const relVals = players.map((p) => (isBat ? p.positive_hpc_pct : p.positive_pcs_pct) ?? 0);
      const oppsVals = players.map((p) => (isBat ? p.pressure_innings : p.pressure_spells) ?? 0);
      const avgVals = players.map((p) => (isBat ? p.avg_hpc_under_pressure : p.avg_pcs_under_pressure) ?? 0);
      const totVals = players.map((p) => (isBat ? p.total_hpc_under_pressure : p.total_pressure_contribution_rpe) ?? 0);

      ACTIVE_CHARTS.compare = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            {
              label: 'POS REL (Green ≥ 50%, Yellow < 50%)',
              data: relVals,
              backgroundColor: relVals.map((v) => getPosRelBarColor(v)),
              borderRadius: 6,
              yAxisID: 'yPct',
            },
            {
              label: isBat ? 'Pressure Innings' : 'Pressure Spells',
              data: oppsVals,
              type: 'line',
              borderColor: isBat ? '#1E3A8A' : '#DB2777',
              backgroundColor: isBat ? '#1E3A8A' : '#DB2777',
              tension: 0.2,
              pointRadius: 5,
              yAxisID: 'yOpps',
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            yPct: {
              type: 'linear',
              position: 'left',
              beginAtZero: true,
              max: 100,
              ticks: { callback: (v) => `${v}%` },
              title: { display: true, text: 'POS REL %', font: { size: 10, weight: 'bold' } },
            },
            yOpps: {
              type: 'linear',
              position: 'right',
              beginAtZero: true,
              grid: { drawOnChartArea: false },
              title: { display: true, text: isBat ? 'Pressure Innings' : 'Pressure Spells', font: { size: 10, weight: 'bold' } },
            },
          },
          plugins: {
            legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10, weight: 'bold' } } },
            tooltip: {
              callbacks: {
                afterBody: (items) => {
                  const idx = items[0]?.dataIndex ?? 0;
                  return isBat
                    ? [
                        `Total HPC: ${formatSigned(totVals[idx], 2)}`,
                        `Avg HPC: ${formatSigned(avgVals[idx], 2)}`,
                      ]
                    : [
                        `Total RPE: ${formatSigned(totVals[idx], 2)}`,
                        `Avg PCS: ${Number(avgVals[idx]).toFixed(2)}`,
                      ];
                },
              },
            },
          },
        },
      });
    }
  }
}
