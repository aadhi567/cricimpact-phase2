/**
 * CricImpact Phase 2 — Bowling Leaderboard Page
 * Filterable, sortable, paginated leaderboard with Pink + Blue design system.
 * First-class support for BCM (BCS, Shrunk BCS, bWPA) and PCS (Pressure Contribution Score).
 */

import { bowlingApiService } from '../services/bowlingApiService.js';
import { pcsApiService } from '../services/pcsApiService.js';
import { renderLoadingSkeleton, renderErrorState } from '../components/LoadingSkeleton.js';
import {
  formatBCS,
  formatBWPA,
  formatEconomy,
  formatNumber,
  formatPercent,
  formatPCS,
  getPCSBadgeClass,
} from '../utils/formatting.js';

export class BowlingLeaderboard {
  constructor() {
    this.container = null;
    this.state = {
      metricMode: 'bcm', // 'bcm' | 'pcs'
      activeTab: 'shrunk_bcs', // 'total_bcs' | 'shrunk_bcs' | 'total_bwpa' | 'pcs_career_shrunk' | 'pcs_season_shrunk' | 'pcs_career_raw'
      pcsScope: 'career', // 'career' | 'season'
      season: 'all',
      tournament: 'all',
      phase: '',
      min_balls: 60,
      sort_by: 'shrunk_bcs',
      order: 'desc',
      page: 1,
      page_size: 25,
      searchQuery: '',
    };
    this.data = null;
    this.tournaments = [];
    this.isLoading = false;
  }

  async render(container, params = {}) {
    this.container = container;
    // Handle URL params if provided
    if (params.metric === 'pcs' || params.pcs === 'true') {
      this.state.metricMode = 'pcs';
      this.state.activeTab = 'pcs_career_shrunk';
      this.state.sort_by = 'pcs_shrunk';
    }
    if (params.phase) {
      this.state.phase = params.phase;
    }
    if (params.season) {
      this.state.season = params.season;
    }
    if (params.tournament) {
      this.state.tournament = params.tournament;
    }

    // Load tournaments list from authoritative API endpoint if not loaded
    if (this.tournaments.length === 0) {
      try {
        const tRes = await (this.state.metricMode === 'pcs' ? pcsApiService : bowlingApiService).getTournaments();
        this.tournaments = tRes.items || [];
      } catch (err) {
        console.warn('Could not load tournaments list:', err);
      }
    }

    await this.fetchData();
  }

  async fetchData() {
    this.isLoading = true;
    if (!this.data) {
      this.container.innerHTML = renderLoadingSkeleton(
        this.state.metricMode === 'pcs'
          ? 'Loading Bowling Pressure Leaderboard (PCS)...'
          : 'Loading Bowling Leaderboard...'
      );
    }

    try {
      if (this.state.metricMode === 'pcs') {
        const pcsSort = this.state.sort_by === 'pcs_raw' ? 'pcs_raw' : 'pcs_shrunk';
        const res = await pcsApiService.getLeaderboard({
          scope: this.state.pcsScope,
          season: this.state.season !== 'all' ? this.state.season : undefined,
          tournament: this.state.tournament !== 'all' ? this.state.tournament : undefined,
          min_balls: this.state.min_balls,
          sort_by: pcsSort,
          order: this.state.order,
          search: this.state.searchQuery || undefined,
          page: this.state.page,
          page_size: this.state.page_size,
        });
        this.data = res.data;
      } else {
        this.data = await bowlingApiService.getLeaderboard({
          season: this.state.season,
          tournament: this.state.tournament !== 'all' ? this.state.tournament : undefined,
          phase: this.state.phase || undefined,
          min_balls: this.state.min_balls,
          sort_by: this.state.sort_by,
          order: this.state.order,
          page: this.state.page,
          page_size: this.state.page_size,
        });
      }
      this.renderContent();
    } catch (err) {
      this.container.innerHTML = renderErrorState(
        `Failed to load leaderboard data: ${err.message}`,
        'window.cricimpactLeaderboard.fetchData()'
      );
    } finally {
      this.isLoading = false;
    }
  }

  renderContent() {
    window.cricimpactLeaderboard = this;
    const { pagination, items, sort_by } = this.data;
    const isPCS = this.state.metricMode === 'pcs';

    // Client-side text filter for BCM (PCS handles search via backend or client fallback)
    const filteredItems = (!isPCS && this.state.searchQuery)
      ? items.filter((it) => it.bowler_name.toLowerCase().includes(this.state.searchQuery.toLowerCase()))
      : items;

    const activeTournamentObj = this.tournaments.find(
      (t) => String(t.comp_id) === String(this.state.tournament) || t.comp_name === this.state.tournament
    );
    const activeTournamentName = activeTournamentObj ? activeTournamentObj.display_name : this.state.tournament;
    const isTournamentFiltered = this.state.tournament && this.state.tournament !== 'all';

    this.container.innerHTML = `
      <div class="space-y-5 animate-fade-in">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm">
          <div>
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              <span class="${isPCS ? 'bg-[#1E3A8A] text-white px-2 py-0.5 rounded text-[10px] font-black uppercase' : 'badge-pink'}">
                ${isPCS ? 'PCS Pressure Telemetry' : 'BCM Ranking Telemetry'}
              </span>
              <span class="text-xs text-[#64748B] font-mono">${pagination.total_items} Qualified Bowlers</span>
              ${isTournamentFiltered ? `
                <span class="bg-[#EFF6FF] text-[#1E40AF] border border-[#BFDBFE] px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1">
                  <span>🏆 Tournament:</span>
                  <span class="font-extrabold">${activeTournamentName}</span>
                  <button onclick="window.cricimpactLeaderboard.handleTournamentChange('all')" title="Clear tournament filter" class="ml-1 text-[#93C5FD] hover:text-[#1E40AF] font-black">&times;</button>
                </span>
              ` : ''}
            </div>
            <h1 class="text-xl md:text-2xl font-black text-[#0F172A] tracking-tight">
              ${isPCS ? 'Bowling Pressure Contribution (PCS) Leaderboard' : 'Bowling Contribution Leaderboard'}
            </h1>
            <p class="text-xs text-[#64748B] mt-1 max-w-xl">
              ${isPCS
                ? 'Rank bowlers on the bipolar 0–100 pressure scale (neutral 50.00). Evaluates containment, dot-ball pressure, and situational wickets.'
                : 'Rank bowlers using raw cumulative contribution (Total BCS) or Empirical Bayes stabilized contribution (Shrunk BCS, M0=48 balls).'}
            </p>
          </div>

          <div class="flex items-center gap-2">
            <button onclick="window.cricimpactLeaderboard.resetFilters()" class="btn-secondary text-xs px-3 py-1.5">
              Reset Filters
            </button>
            <a href="#/bowling/compare" class="btn-pink text-xs px-3 py-1.5">
              Compare Bowlers &rarr;
            </a>
          </div>
        </div>

        <!-- Metric Selector Tabs (BCM vs PCS) -->
        <div class="bg-white p-2 rounded-xl border border-[#E2E8F0] shadow-xs">
          <div class="flex flex-wrap items-center gap-1.5 text-xs font-bold">
            <span class="text-[10px] uppercase text-[#94A3B8] px-2 font-black tracking-wider">Metrics:</span>
            
            <button
              onclick="window.cricimpactLeaderboard.selectTab('shrunk_bcs')"
              class="px-3 py-1.5 rounded-lg transition ${this.state.activeTab === 'shrunk_bcs' ? 'bg-[#EC4899] text-white shadow-xs' : 'text-[#64748B] hover:bg-[#F8FAFC]'}"
            >
              Shrunk BCS (Runs)
            </button>
            <button
              onclick="window.cricimpactLeaderboard.selectTab('total_bcs')"
              class="px-3 py-1.5 rounded-lg transition ${this.state.activeTab === 'total_bcs' ? 'bg-[#3B82F6] text-white shadow-xs' : 'text-[#64748B] hover:bg-[#F8FAFC]'}"
            >
              Total BCS (Raw)
            </button>
            <button
              onclick="window.cricimpactLeaderboard.selectTab('total_bwpa')"
              class="px-3 py-1.5 rounded-lg transition ${this.state.activeTab === 'total_bwpa' ? 'bg-[#2563EB] text-white shadow-xs' : 'text-[#64748B] hover:bg-[#F8FAFC]'}"
            >
              Total bWPA (Win Prob)
            </button>

            <span class="h-4 w-px bg-[#E2E8F0] mx-1"></span>

            <button
              onclick="window.cricimpactLeaderboard.selectTab('pcs_career_shrunk')"
              class="px-3 py-1.5 rounded-lg transition ${this.state.activeTab === 'pcs_career_shrunk' ? 'bg-[#1E3A8A] text-white shadow-xs' : 'text-[#1E3A8A] bg-[#EFF6FF] hover:bg-[#DBEAFE]'}"
            >
              ★ PCS Career Shrunk (0–100)
            </button>
            <button
              onclick="window.cricimpactLeaderboard.selectTab('pcs_career_raw')"
              class="px-3 py-1.5 rounded-lg transition ${this.state.activeTab === 'pcs_career_raw' ? 'bg-[#1E3A8A] text-white shadow-xs' : 'text-[#64748B] hover:bg-[#F8FAFC]'}"
            >
              PCS Career Raw
            </button>
            <button
              onclick="window.cricimpactLeaderboard.selectTab('pcs_season_shrunk')"
              class="px-3 py-1.5 rounded-lg transition ${this.state.activeTab === 'pcs_season_shrunk' ? 'bg-[#1E3A8A] text-white shadow-xs' : 'text-[#64748B] hover:bg-[#F8FAFC]'}"
            >
              PCS Season Shrunk
            </button>
          </div>
        </div>

        <!-- Filter Controls Toolbar -->
        <div class="card-base p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-sm space-y-3">
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
            <!-- Search Filter -->
            <div>
              <label class="block font-bold text-[#64748B] uppercase text-[10px] mb-1">Search Bowler</label>
              <input
                type="text"
                id="search-input"
                placeholder="Filter by name..."
                value="${this.state.searchQuery}"
                oninput="window.cricimpactLeaderboard.handleSearch(this.value)"
                class="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-lg text-xs focus:outline-none focus:border-[#EC4899] bg-[#F8FAFC]"
              />
            </div>

            <!-- Tournament Filter -->
            <div>
              <label class="block font-bold text-[#64748B] uppercase text-[10px] mb-1">Tournament</label>
              <select
                id="tournament-filter-select"
                onchange="window.cricimpactLeaderboard.handleTournamentChange(this.value)"
                class="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-lg text-xs focus:outline-none focus:border-[#3B82F6] bg-white font-medium truncate"
              >
                <option value="all" ${this.state.tournament === 'all' ? 'selected' : ''}>All Tournaments</option>
                ${this.tournaments.map((t) => `
                  <option value="${t.comp_id}" ${String(this.state.tournament) === String(t.comp_id) || this.state.tournament === t.comp_name ? 'selected' : ''}>
                    ${t.display_name}${t.match_count > 0 ? ` (${t.match_count} matches)` : ''}
                  </option>
                `).join('')}
              </select>
            </div>

            <!-- Season Filter -->
            <div>
              <label class="block font-bold text-[#64748B] uppercase text-[10px] mb-1">Season</label>
              <select
                onchange="window.cricimpactLeaderboard.handleSeasonChange(this.value)"
                class="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-lg text-xs focus:outline-none focus:border-[#3B82F6] bg-white font-medium"
              >
                <option value="all" ${this.state.season === 'all' ? 'selected' : ''}>Career (All Seasons)</option>
                <option value="2026" ${this.state.season === '2026' ? 'selected' : ''}>2026</option>
                <option value="2025" ${this.state.season === '2025' ? 'selected' : ''}>2025</option>
                <option value="2024" ${this.state.season === '2024' ? 'selected' : ''}>2024</option>
                <option value="2023" ${this.state.season === '2023' ? 'selected' : ''}>2023</option>
                <option value="2022" ${this.state.season === '2022' ? 'selected' : ''}>2022</option>
              </select>
            </div>

            <!-- Phase Filter (BCM only) or Scope (PCS) -->
            ${isPCS ? `
              <div>
                <label class="block font-bold text-[#64748B] uppercase text-[10px] mb-1">PCS Aggregation Scope</label>
                <select
                  onchange="window.cricimpactLeaderboard.handleScopeChange(this.value)"
                  class="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-lg text-xs focus:outline-none focus:border-[#1E3A8A] bg-white font-medium"
                >
                  <option value="career" ${this.state.pcsScope === 'career' ? 'selected' : ''}>Career Aggregated</option>
                  <option value="season" ${this.state.pcsScope === 'season' ? 'selected' : ''}>Season Partitions</option>
                </select>
              </div>
            ` : `
              <div>
                <label class="block font-bold text-[#64748B] uppercase text-[10px] mb-1">Match Phase</label>
                <select
                  onchange="window.cricimpactLeaderboard.handlePhaseChange(this.value)"
                  class="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-lg text-xs focus:outline-none focus:border-[#EC4899] bg-white font-medium"
                >
                  <option value="" ${!this.state.phase ? 'selected' : ''}>All Phases Combined</option>
                  <option value="powerplay" ${this.state.phase === 'powerplay' ? 'selected' : ''}>Powerplay (Ov 1–6)</option>
                  <option value="middle" ${this.state.phase === 'middle' ? 'selected' : ''}>Middle Overs (Ov 7–16)</option>
                  <option value="death" ${this.state.phase === 'death' ? 'selected' : ''}>Death Overs (Ov 17–20)</option>
                </select>
              </div>
            `}

            <!-- Sort Metric Dropdown -->
            <div>
              <label class="block font-bold text-[#64748B] uppercase text-[10px] mb-1">Sort Metric</label>
              <select
                onchange="window.cricimpactLeaderboard.handleSortChange(this.value)"
                class="w-full px-3 py-1.5 border border-[#E2E8F0] rounded-lg text-xs focus:outline-none focus:border-[#3B82F6] bg-white font-bold text-[#0F172A]"
              >
                ${isPCS ? `
                  <option value="pcs_shrunk" ${this.state.sort_by === 'pcs_shrunk' ? 'selected' : ''}>Shrunk PCS (0–100)</option>
                  <option value="pcs_raw" ${this.state.sort_by === 'pcs_raw' ? 'selected' : ''}>Raw PCS</option>
                  <option value="wickets" ${this.state.sort_by === 'wickets' ? 'selected' : ''}>Wickets Taken</option>
                  <option value="economy" ${this.state.sort_by === 'economy' ? 'selected' : ''}>Economy Rate</option>
                  <option value="strike_rate" ${this.state.sort_by === 'strike_rate' ? 'selected' : ''}>Strike Rate</option>
                  <option value="legal_balls" ${this.state.sort_by === 'legal_balls' ? 'selected' : ''}>Legal Balls</option>
                ` : `
                  <option value="shrunk_bcs" ${this.state.sort_by === 'shrunk_bcs' ? 'selected' : ''}>Total Shrunk BCS (M0=48)</option>
                  <option value="total_bcs" ${this.state.sort_by === 'total_bcs' ? 'selected' : ''}>Total BCS (Unshrunk)</option>
                  <option value="shrunk_bcs_per_over" ${this.state.sort_by === 'shrunk_bcs_per_over' ? 'selected' : ''}>Shrunk BCS / Over</option>
                  <option value="bcs_per_over" ${this.state.sort_by === 'bcs_per_over' ? 'selected' : ''}>Raw BCS / Over</option>
                  <option value="total_bwpa" ${this.state.sort_by === 'total_bwpa' ? 'selected' : ''}>Total bWPA (Win Prob)</option>
                  <option value="wickets" ${this.state.sort_by === 'wickets' ? 'selected' : ''}>Wickets Taken</option>
                  <option value="economy" ${this.state.sort_by === 'economy' ? 'selected' : ''}>Economy Rate</option>
                  <option value="dot_pct" ${this.state.sort_by === 'dot_pct' ? 'selected' : ''}>Dot Ball %</option>
                  <option value="total_erp" ${this.state.sort_by === 'total_erp' ? 'selected' : ''}>Total Runs Prevented (ERP)</option>
                `}
              </select>
            </div>

            <!-- Min Balls Threshold -->
            <div>
              <div class="flex items-center justify-between font-bold text-[#64748B] uppercase text-[10px] mb-1">
                <span>Min Balls</span>
                <span class="text-[#0F172A] font-mono">${this.state.min_balls} balls</span>
              </div>
              <input
                type="range"
                min="0"
                max="500"
                step="30"
                value="${this.state.min_balls}"
                onchange="window.cricimpactLeaderboard.handleMinBallsChange(this.value)"
                class="w-full accent-[#EC4899] cursor-pointer"
              />
            </div>
          </div>
        </div>

        <!-- Leaderboard Table -->
        <div class="card-base bg-white border border-[#E2E8F0] rounded-xl shadow-sm overflow-hidden">
          <div class="overflow-x-auto">
            ${isPCS ? this.renderPCSTable(filteredItems) : this.renderBCMTable(filteredItems, sort_by)}
          </div>

          <!-- Pagination Bar -->
          <div class="p-4 bg-[#F8FAFC] border-t border-[#E2E8F0] flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
            <span class="text-[#64748B]">
              Showing page <strong class="text-[#0F172A]">${pagination.current_page}</strong> of <strong class="text-[#0F172A]">${pagination.total_pages || 1}</strong> (${pagination.total_items} total records)
            </span>

            <div class="flex items-center gap-1.5">
              <button
                onclick="window.cricimpactLeaderboard.handlePageChange(${pagination.current_page - 1})"
                ${pagination.current_page <= 1 ? 'disabled' : ''}
                class="px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white text-[#0F172A] font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#F1F5F9] transition"
              >
                &larr; Previous
              </button>
              <button
                onclick="window.cricimpactLeaderboard.handlePageChange(${pagination.current_page + 1})"
                ${pagination.current_page >= pagination.total_pages ? 'disabled' : ''}
                class="px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white text-[#0F172A] font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#F1F5F9] transition"
              >
                Next &rarr;
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  renderBCMTable(items, sort_by) {
    return `
      <table class="w-full text-xs text-left">
        <thead class="bg-[#F8FAFC] text-[#64748B] font-bold uppercase text-[10px] border-b border-[#E2E8F0]">
          <tr>
            <th class="py-3 px-3 text-center w-12">#</th>
            <th class="py-3 px-3">Bowler</th>
            <th class="py-3 px-3 text-center">Matches</th>
            <th class="py-3 px-3 text-center">Overs</th>
            <th class="py-3 px-3 text-center">Wkts</th>
            <th class="py-3 px-3 text-center">Econ</th>
            <th class="py-3 px-3 text-center">Dot %</th>
            <th class="py-3 px-3 text-right cursor-pointer hover:text-[#EC4899] ${sort_by === 'total_bcs' ? 'text-[#EC4899] font-black' : ''}" onclick="window.cricimpactLeaderboard.handleSortChange('total_bcs')">
              Total BCS ${sort_by === 'total_bcs' ? '▼' : ''}
            </th>
            <th class="py-3 px-3 text-right cursor-pointer hover:text-[#EC4899] ${sort_by === 'shrunk_bcs' ? 'text-[#EC4899] font-black' : ''}" onclick="window.cricimpactLeaderboard.handleSortChange('shrunk_bcs')">
              Shrunk BCS ${sort_by === 'shrunk_bcs' ? '▼' : ''}
            </th>
            <th class="py-3 px-3 text-right cursor-pointer hover:text-[#EC4899] ${sort_by === 'shrunk_bcs_per_over' ? 'text-[#EC4899] font-black' : ''}" onclick="window.cricimpactLeaderboard.handleSortChange('shrunk_bcs_per_over')">
              Shrunk / Ov ${sort_by === 'shrunk_bcs_per_over' ? '▼' : ''}
            </th>
            <th class="py-3 px-3 text-right cursor-pointer hover:text-[#3B82F6] ${sort_by === 'total_bwpa' ? 'text-[#3B82F6] font-black' : ''}" onclick="window.cricimpactLeaderboard.handleSortChange('total_bwpa')">
              bWPA ${sort_by === 'total_bwpa' ? '▼' : ''}
            </th>
            <th class="py-3 px-3 text-center">Action</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#F1F5F9] font-medium text-[#0F172A]">
          ${items.length === 0 ? `
            <tr>
              <td colspan="12" class="py-12 text-center text-xs text-[#64748B]">
                <div class="max-w-md mx-auto space-y-2">
                  <div class="text-2xl">🏏</div>
                  <p class="font-bold text-[#0F172A]">No bowlers match the selected criteria.</p>
                  <p class="text-[11px] text-[#94A3B8]">Try lowering the minimum legal balls threshold or resetting filters.</p>
                  <div class="flex items-center justify-center gap-2 pt-2">
                    <button onclick="window.cricimpactLeaderboard.handleMinBallsChange(1)" class="btn-pink text-xs px-3 py-1">
                      Set Min Balls to 1
                    </button>
                    <button onclick="window.cricimpactLeaderboard.resetFilters()" class="btn-secondary text-xs px-3 py-1">
                      Reset Filters
                    </button>
                  </div>
                </div>
              </td>
            </tr>
          ` : items.map((b) => `
            <tr class="hover:bg-[#FDF2F8]/40 transition cursor-pointer" onclick="window.location.hash='#/bowling/players/${b.bowler_id}'">
              <td class="py-2.5 px-3 text-center font-bold text-[#64748B]">${b.rank}</td>
              <td class="py-2.5 px-3 font-bold text-[#0F172A] hover:text-[#DB2777]">
                <a href="#/bowling/players/${b.bowler_id}">${b.bowler_name}</a>
              </td>
              <td class="py-2.5 px-3 text-center">${b.matches}</td>
              <td class="py-2.5 px-3 text-center font-mono">${b.overs_formatted || b.overs.toFixed(1)}</td>
              <td class="py-2.5 px-3 text-center font-bold">${b.wickets}</td>
              <td class="py-2.5 px-3 text-center font-mono">${formatEconomy(b.economy)}</td>
              <td class="py-2.5 px-3 text-center font-mono">${formatPercent(b.dot_pct)}</td>
              <td class="py-2.5 px-3 text-right font-black text-[#2563EB]">${formatBCS(b.total_bcs)}</td>
              <td class="py-2.5 px-3 text-right font-black text-[#DB2777]">${formatBCS(b.shrunk_bcs || b.total_bcs_shrunk)}</td>
              <td class="py-2.5 px-3 text-right font-mono font-bold text-[#0F172A]">${b.shrunk_bcs_per_over !== null && b.shrunk_bcs_per_over !== undefined ? b.shrunk_bcs_per_over.toFixed(2) : '—'}</td>
              <td class="py-2.5 px-3 text-right font-mono text-[#0F172A]">${formatBWPA(b.total_bwpa)}</td>
              <td class="py-2.5 px-3 text-center">
                <a href="#/bowling/players/${b.bowler_id}" class="text-[11px] font-bold text-[#DB2777] hover:underline">Profile &rarr;</a>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  renderPCSTable(items) {
    return `
      <table class="w-full text-xs text-left">
        <thead class="bg-[#F8FAFC] text-[#64748B] font-bold uppercase text-[10px] border-b border-[#CBD5E1]">
          <tr>
            <th class="py-3 px-3 text-center w-12">#</th>
            <th class="py-3 px-3">Bowler</th>
            ${this.state.pcsScope === 'season' ? '<th class="py-3 px-3 text-center">Season</th>' : ''}
            <th class="py-3 px-3 text-center">Matches</th>
            <th class="py-3 px-3 text-center">Spells</th>
            <th class="py-3 px-3 text-center">Balls</th>
            <th class="py-3 px-3 text-center">Wkts</th>
            <th class="py-3 px-3 text-center">Econ</th>
            <th class="py-3 px-3 text-center">SR</th>
            <th class="py-3 px-3 text-right">Raw PCS</th>
            <th class="py-3 px-3 text-right font-black text-[#1E3A8A]">Shrunk PCS (0–100)</th>
            <th class="py-3 px-3 text-center">Pressure Impact</th>
            <th class="py-3 px-3 text-center">Action</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#F1F5F9] font-medium text-[#0F172A]">
          ${items.length === 0 ? `
            <tr>
              <td colspan="13" class="py-12 text-center text-xs text-[#64748B]">
                <div class="max-w-md mx-auto space-y-2">
                  <div class="text-2xl">⚡</div>
                  <p class="font-bold text-[#0F172A]">No bowlers match the selected PCS criteria.</p>
                  <p class="text-[11px] text-[#94A3B8]">Try lowering the minimum legal balls threshold or resetting filters.</p>
                  <div class="flex items-center justify-center gap-2 pt-2">
                    <button onclick="window.cricimpactLeaderboard.handleMinBallsChange(1)" class="btn-pink text-xs px-3 py-1">
                      Set Min Balls to 1
                    </button>
                    <button onclick="window.cricimpactLeaderboard.resetFilters()" class="btn-secondary text-xs px-3 py-1">
                      Reset Filters
                    </button>
                  </div>
                </div>
              </td>
            </tr>
          ` : items.map((b) => `
            <tr class="hover:bg-[#EFF6FF]/50 transition cursor-pointer" onclick="window.location.hash='#/bowling/players/${b.bowler_id}'">
              <td class="py-2.5 px-3 text-center font-bold text-[#64748B]">${b.rank}</td>
              <td class="py-2.5 px-3 font-bold text-[#0F172A] hover:text-[#1E3A8A]">
                <a href="#/bowling/players/${b.bowler_id}">${b.bowler_name}</a>
              </td>
              ${this.state.pcsScope === 'season' ? `<td class="py-2.5 px-3 text-center font-mono text-[#64748B]">${b.season || '—'}</td>` : ''}
              <td class="py-2.5 px-3 text-center">${b.matches}</td>
              <td class="py-2.5 px-3 text-center">${b.spells}</td>
              <td class="py-2.5 px-3 text-center font-mono">${b.legal_balls}</td>
              <td class="py-2.5 px-3 text-center font-bold">${b.wickets}</td>
              <td class="py-2.5 px-3 text-center font-mono">${formatEconomy(b.economy)}</td>
              <td class="py-2.5 px-3 text-center font-mono text-[#64748B]">${b.strike_rate ? b.strike_rate.toFixed(1) : '—'}</td>
              <td class="py-2.5 px-3 text-right font-mono text-[#64748B]">${formatPCS(b.pcs_raw)}</td>
              <td class="py-2.5 px-3 text-right font-black text-[#1E3A8A] text-sm">${formatPCS(b.pcs_shrunk)}</td>
              <td class="py-2.5 px-3 text-center">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${getPCSBadgeClass(b.pcs_shrunk)}">
                  ${b.pcs_shrunk > 50.00 ? '+Pressure' : b.pcs_shrunk < 50.00 ? '-Leakage' : 'Neutral'}
                </span>
              </td>
              <td class="py-2.5 px-3 text-center">
                <a href="#/bowling/players/${b.bowler_id}" class="text-[11px] font-bold text-[#1E3A8A] hover:underline">Profile &rarr;</a>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  selectTab(tab) {
    this.state.activeTab = tab;
    this.state.page = 1;

    if (tab === 'shrunk_bcs') {
      this.state.metricMode = 'bcm';
      this.state.sort_by = 'shrunk_bcs';
    } else if (tab === 'total_bcs') {
      this.state.metricMode = 'bcm';
      this.state.sort_by = 'total_bcs';
    } else if (tab === 'total_bwpa') {
      this.state.metricMode = 'bcm';
      this.state.sort_by = 'total_bwpa';
    } else if (tab === 'pcs_career_shrunk') {
      this.state.metricMode = 'pcs';
      this.state.pcsScope = 'career';
      this.state.sort_by = 'pcs_shrunk';
    } else if (tab === 'pcs_career_raw') {
      this.state.metricMode = 'pcs';
      this.state.pcsScope = 'career';
      this.state.sort_by = 'pcs_raw';
    } else if (tab === 'pcs_season_shrunk') {
      this.state.metricMode = 'pcs';
      this.state.pcsScope = 'season';
      this.state.sort_by = 'pcs_shrunk';
    }

    this.fetchData();
  }

  handleScopeChange(scope) {
    this.state.pcsScope = scope;
    this.state.page = 1;
    this.fetchData();
  }

  handleSearch(val) {
    this.state.searchQuery = val;
    if (this.state.metricMode === 'pcs') {
      this.state.page = 1;
      this.fetchData();
    } else {
      this.renderContent();
    }
  }

  handleSeasonChange(season) {
    this.state.season = season;
    this.state.page = 1;
    this.fetchData();
  }

  handleTournamentChange(tournament) {
    this.state.tournament = tournament;
    this.state.page = 1;
    this.fetchData();
  }

  handlePhaseChange(phase) {
    this.state.phase = phase;
    this.state.page = 1;
    this.fetchData();
  }

  handleSortChange(sortBy) {
    if (this.state.sort_by === sortBy) {
      this.state.order = this.state.order === 'desc' ? 'asc' : 'desc';
    } else {
      this.state.sort_by = sortBy;
      this.state.order = 'desc';
    }
    this.fetchData();
  }

  handleMinBallsChange(balls) {
    this.state.min_balls = Number(balls);
    this.state.page = 1;
    this.fetchData();
  }

  handlePageChange(newPage) {
    if (newPage < 1 || newPage > this.data.pagination.total_pages) return;
    this.state.page = newPage;
    this.fetchData();
  }

  resetFilters() {
    this.state = {
      metricMode: 'bcm',
      activeTab: 'shrunk_bcs',
      pcsScope: 'career',
      season: 'all',
      tournament: 'all',
      phase: '',
      min_balls: 60,
      sort_by: 'shrunk_bcs',
      order: 'desc',
      page: 1,
      page_size: 25,
      searchQuery: '',
    };
    this.fetchData();
  }
}

export function renderBowlingLeaderboard(container, params) {
  const page = new BowlingLeaderboard();
  return page.render(container, params);
}
