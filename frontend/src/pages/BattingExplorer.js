/**
 * CricImpact Phase 2 — Modernized Batting HPP Explorer & Leaderboard
 * Stage B9: Searchable, filterable, sortable batter explorer with Pink + Blue light theme.
 * Supports Season, Team, Tournament, Pressure Tier, Contribution Range & Min Innings filters.
 */

import { battingApiService } from '../services/battingApiService.js';
import { renderLoadingSkeleton, renderErrorState } from '../components/LoadingSkeleton.js';
import {
  renderBattingMetricExplainer,
  formatSigned,
  getSignedColorClass,
  escapeHtml,
} from '../components/BattingMetricExplainer.js';
import { formatNumber } from '../utils/formatting.js';

export class BattingExplorer {
  constructor() {
    this.container = null;
    this.filtersMeta = null;
    this.data = null;
    this.compareSelection = new Set();
    this.debounceTimer = null;
    this.state = {
      search: '',
      season: 'all',
      team: 'all',
      tournament: 'all',
      comp_category: 'all',
      tier: 'all',
      min_inns: 5,
      min_hpc: '',
      max_hpc: '',
      sort_by: 'total_hpc',
      sort_order: 'desc',
      page: 1,
      page_size: 25,
    };
  }

  async render(container, params = {}) {
    this.container = container;
    if (params && params.search) this.state.search = params.search;
    if (params && params.season) this.state.season = params.season;
    if (params && params.team) this.state.team = params.team;
    if (params && params.tournament) this.state.tournament = params.tournament;

    container.innerHTML = renderLoadingSkeleton('Loading Batting HPP Explorer...');

    try {
      const [meta, res] = await Promise.all([
        this.filtersMeta ? Promise.resolve(this.filtersMeta) : battingApiService.getFilters(),
        battingApiService.getExplorer(this.state),
      ]);
      this.filtersMeta = meta;
      this.data = res;
      this.renderShell();
    } catch (err) {
      container.innerHTML = renderErrorState(
        `Failed to load Batting HPP Explorer: ${err.message}`,
        'window.location.reload()'
      );
    }
  }

  async fetchAndUpdateTable() {
    const wrap = document.getElementById('explorer-table-container');
    if (wrap) wrap.classList.add('opacity-50');
    try {
      this.data = await battingApiService.getExplorer(this.state);
      this.renderTableRegion();
    } catch (err) {
      if (wrap) {
        wrap.innerHTML = `<div class="p-6 text-center text-xs text-[#DC2626] font-bold">Error: ${escapeHtml(err.message)}</div>`;
      }
    } finally {
      if (wrap) wrap.classList.remove('opacity-50');
    }
  }

  renderShell() {
    const meta = this.filtersMeta;
    const seasonOpts = [
      `<option value="all" ${this.state.season === 'all' ? 'selected' : ''}>All Seasons</option>`,
      ...meta.seasons.slice().reverse().map(
        (s) => `<option value="${escapeHtml(s)}" ${this.state.season === s ? 'selected' : ''}>Season ${escapeHtml(s)}</option>`
      ),
    ].join('');

    const teamOpts = [
      `<option value="all" ${this.state.team === 'all' ? 'selected' : ''}>All Teams (${meta.teams.length})</option>`,
      ...meta.teams.map(
        (t) => `<option value="${escapeHtml(t)}" ${this.state.team === t ? 'selected' : ''}>${escapeHtml(t)}</option>`
      ),
    ].join('');

    const tourneyOpts = [
      `<option value="all" ${this.state.tournament === 'all' ? 'selected' : ''}>All Tournaments (${meta.tournaments.length})</option>`,
      ...meta.tournaments.map(
        (t) => `<option value="${escapeHtml(t.comp_name)}" ${this.state.tournament === t.comp_name ? 'selected' : ''}>${escapeHtml(t.comp_name)} (${t.match_count}m)</option>`
      ),
    ].join('');

    const tierOpts = [
      `<option value="all" ${this.state.tier === 'all' ? 'selected' : ''}>All Pressure Tiers</option>`,
      ...meta.pressure_tiers.map(
        (t) => `<option value="${escapeHtml(t)}" ${this.state.tier === t ? 'selected' : ''}>${escapeHtml(t)} Pressure</option>`
      ),
    ].join('');

    this.container.innerHTML = `
      <div class="space-y-6 animate-fade-in">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E2E8F0]">
          <div>
            <div class="flex items-center gap-2 text-[11px] font-black uppercase tracking-wider text-[#3B82F6] mb-1">
              <span>Batting Analytics</span>
              <span>&bull;</span>
              <span class="text-[#EC4899]">HPP Explorer &amp; Leaderboard</span>
            </div>
            <h1 id="page-main-heading" tabindex="-1" class="hero-title-fluid font-black text-[#0F172A] tracking-tight">
              Batting HPP Explorer
            </h1>
            <p class="text-xs text-[#64748B] mt-1">
              Search, filter, and rank all 880 batters by HPC, RAE, runs, strike rate, average, and pressure performance.
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <a href="#/batting/dashboard" class="px-3 py-2 rounded-xl bg-white border border-[#E2E8F0] text-xs font-bold text-[#334155] hover:border-[#3B82F6] hover:text-[#2563EB] transition">
              &larr; HPP Dashboard
            </a>
            <button type="button" id="explorer-compare-launch" class="px-3.5 py-2 rounded-xl bg-gradient-to-r from-[#3B82F6] to-[#EC4899] text-white text-xs font-bold shadow-sm hover:opacity-95 transition">
              Compare Selected (<span id="explorer-compare-cnt">${this.compareSelection.size}</span>)
            </button>
          </div>
        </div>

        <!-- Filters Panel -->
        <section class="bg-white border border-[#E2E8F0] rounded-2xl p-4 sm:p-5 shadow-sm space-y-4" aria-label="Explorer Search and Filters">
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label for="exp-search" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Search Batter / Team</label>
              <input id="exp-search" type="search" value="${escapeHtml(this.state.search)}" placeholder="e.g. Virat Kohli, India..." class="w-full px-3 py-2 text-xs font-medium bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
            </div>
            <div>
              <label for="exp-season" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Season</label>
              <select id="exp-season" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${seasonOpts}
              </select>
            </div>
            <div>
              <label for="exp-team" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Team</label>
              <select id="exp-team" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${teamOpts}
              </select>
            </div>
            <div>
              <label for="exp-tournament" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Tournament</label>
              <select id="exp-tournament" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${tourneyOpts}
              </select>
            </div>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-2 border-t border-[#F1F5F9]">
            <div>
              <label for="exp-tier" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Pressure Tier</label>
              <select id="exp-tier" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${tierOpts}
              </select>
            </div>
            <div>
              <label for="exp-min-inns" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Min Innings</label>
              <select id="exp-min-inns" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${[1, 3, 5, 10, 20, 30, 50].map((n) => `<option value="${n}" ${this.state.min_inns === n ? 'selected' : ''}>${n}+ Inns</option>`).join('')}
              </select>
            </div>
            <div>
              <label for="exp-min-hpc" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Min Total HPC</label>
              <input id="exp-min-hpc" type="number" step="5" value="${escapeHtml(this.state.min_hpc)}" placeholder="Any" class="w-full px-3 py-2 text-xs font-medium bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
            </div>
            <div>
              <label for="exp-max-hpc" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Max Total HPC</label>
              <input id="exp-max-hpc" type="number" step="5" value="${escapeHtml(this.state.max_hpc)}" placeholder="Any" class="w-full px-3 py-2 text-xs font-medium bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
            </div>
            <div>
              <label for="exp-sort" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Sort Metric</label>
              <select id="exp-sort" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                <option value="total_hpc" ${this.state.sort_by === 'total_hpc' ? 'selected' : ''}>Total HPC</option>
                <option value="mean_hpc" ${this.state.sort_by === 'mean_hpc' ? 'selected' : ''}>Average HPC</option>
                <option value="actual_runs" ${this.state.sort_by === 'actual_runs' ? 'selected' : ''}>Total Runs</option>
                <option value="strike_rate" ${this.state.sort_by === 'strike_rate' ? 'selected' : ''}>Strike Rate</option>
                <option value="batting_average" ${this.state.sort_by === 'batting_average' ? 'selected' : ''}>Batting Average</option>
                <option value="total_rae" ${this.state.sort_by === 'total_rae' ? 'selected' : ''}>Total RAE</option>
                <option value="positive_contribution_pct" ${this.state.sort_by === 'positive_contribution_pct' ? 'selected' : ''}>Positive Contrib %</option>
                <option value="avg_pressure_faced" ${this.state.sort_by === 'avg_pressure_faced' ? 'selected' : ''}>Avg Pressure</option>
                <option value="crisis_total_hpc" ${this.state.sort_by === 'crisis_total_hpc' ? 'selected' : ''}>Crisis HPC</option>
              </select>
            </div>
            <div class="flex items-end">
              <button type="button" id="exp-reset-btn" class="w-full px-3 py-2 rounded-xl text-xs font-bold bg-[#FDF2F8] text-[#DB2777] border border-[#FBCFE8] hover:bg-[#FCE7F3] transition">
                Reset Filters
              </button>
            </div>
          </div>
        </section>

        <!-- Results Table Card -->
        <section id="explorer-table-container" class="bg-white border border-[#E2E8F0] rounded-2xl shadow-sm overflow-hidden transition-opacity" aria-live="polite">
        </section>

        <!-- Metric Reference -->
        ${renderBattingMetricExplainer({ compact: true })}
      </div>
    `;

    this.renderTableRegion();
    this.bindEvents();
  }

  renderTableRegion() {
    const wrap = document.getElementById('explorer-table-container');
    if (!wrap) return;
    const { items, pagination } = this.data;

    if (!items.length) {
      wrap.innerHTML = `
        <div class="p-10 text-center space-y-3">
          <div class="text-sm font-bold text-[#0F172A]">No batters match your current filters</div>
          <p class="text-xs text-[#64748B]">Try lowering the Minimum Innings threshold or clearing the HPC contribution range.</p>
          <button type="button" id="exp-empty-reset" class="px-4 py-2 rounded-xl bg-[#3B82F6] text-white text-xs font-bold hover:bg-[#2563EB] transition">
            Clear All Filters
          </button>
        </div>
      `;
      const btn = document.getElementById('exp-empty-reset');
      if (btn) btn.addEventListener('click', () => this.resetFilters());
      return;
    }

    const sortArrow = (key) => {
      if (this.state.sort_by !== key) return '';
      return this.state.sort_order === 'desc' ? ' ▼' : ' ▲';
    };

    wrap.innerHTML = `
      <div class="px-4 py-3 border-b border-[#E2E8F0] bg-[#F8FAFC] flex flex-wrap items-center justify-between gap-2 text-xs">
        <span class="font-bold text-[#0F172A]">
          Showing <span class="text-[#2563EB]">${items.length}</span> of <span class="text-[#DB2777]">${formatNumber(pagination.total_items)}</span> qualifying batters
        </span>
        <span class="text-[11px] text-[#64748B]">Page ${pagination.page} of ${pagination.total_pages} &bull; Click any column header to sort</span>
      </div>

      <div class="table-wrapper" tabindex="0" role="region" aria-label="Batting HPP Explorer Table">
        <table class="text-xs text-left">
          <caption class="visually-hidden">Filterable Batting HPP Leaderboard</caption>
          <thead class="bg-[#F8FAFC] text-[10px] font-bold uppercase tracking-wider text-[#64748B] border-b border-[#E2E8F0]">
            <tr>
              <th scope="col" class="py-3 px-3 text-center w-10">Rank</th>
              <th scope="col" class="py-3 px-3 cursor-pointer hover:text-[#0F172A]" data-sort="batter_name">Batter${sortArrow('batter_name')}</th>
              <th scope="col" class="py-3 px-3">Team</th>
              <th scope="col" class="py-3 px-3 text-right cursor-pointer hover:text-[#0F172A]" data-sort="innings_batted">Inns (DNB)${sortArrow('innings_batted')}</th>
              <th scope="col" class="py-3 px-3 text-right cursor-pointer hover:text-[#0F172A]" data-sort="actual_runs">Runs${sortArrow('actual_runs')}</th>
              <th scope="col" class="py-3 px-3 text-right cursor-pointer hover:text-[#0F172A]" data-sort="batting_average">Avg${sortArrow('batting_average')}</th>
              <th scope="col" class="py-3 px-3 text-right cursor-pointer hover:text-[#0F172A]" data-sort="strike_rate">SR${sortArrow('strike_rate')}</th>
              <th scope="col" class="py-3 px-3 text-right cursor-pointer hover:text-[#0F172A]" data-sort="total_rae">Total RAE${sortArrow('total_rae')}</th>
              <th scope="col" class="py-3 px-3 text-right cursor-pointer hover:text-[#0F172A]" data-sort="avg_pressure_faced">Avg P${sortArrow('avg_pressure_faced')}</th>
              <th scope="col" class="py-3 px-3 text-right cursor-pointer hover:text-[#0F172A]" data-sort="positive_contribution_pct">Pos %${sortArrow('positive_contribution_pct')}</th>
              <th scope="col" class="py-3 px-3 text-right cursor-pointer hover:text-[#0F172A]" data-sort="mean_hpc">Avg HPC${sortArrow('mean_hpc')}</th>
              <th scope="col" class="py-3 px-3 text-right cursor-pointer hover:text-[#0F172A]" data-sort="total_hpc">Total HPC${sortArrow('total_hpc')}</th>
              <th scope="col" class="py-3 px-3 text-center">Compare</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#F1F5F9]">
            ${items.map((p) => {
              const selected = this.compareSelection.has(p.batter_name);
              const profHref = `#/batting/players/${encodeURIComponent(p.batter_name)}`;
              return `
                <tr class="hover:bg-[#F8FAFC] transition">
                  <td class="py-2.5 px-3 text-center font-mono font-bold text-[#94A3B8]">${p.rank}</td>
                  <th scope="row" class="py-2.5 px-3 font-bold text-[#0F172A] whitespace-nowrap">
                    <a href="${profHref}" class="hover:text-[#DB2777] transition">${escapeHtml(p.batter_name)}</a>
                  </th>
                  <td class="py-2.5 px-3 text-[#64748B] whitespace-nowrap">${escapeHtml(p.primary_team || '—')}</td>
                  <td class="py-2.5 px-3 text-right font-mono text-[#334155] whitespace-nowrap">
                    ${p.innings_batted}${p.dnb_count > 0 ? ` <span class="text-[10px] text-[#94A3B8]">(${p.dnb_count} DNB)</span>` : ''}
                  </td>
                  <td class="py-2.5 px-3 text-right font-mono font-bold text-[#0F172A]">${formatNumber(p.actual_runs)}</td>
                  <td class="py-2.5 px-3 text-right font-mono text-[#334155]">${p.batting_average !== null ? p.batting_average.toFixed(1) : '—'}</td>
                  <td class="py-2.5 px-3 text-right font-mono text-[#334155]">${p.strike_rate !== null ? p.strike_rate.toFixed(1) : '—'}</td>
                  <td class="py-2.5 px-3 text-right font-mono font-semibold ${getSignedColorClass(p.total_rae)}">${formatSigned(p.total_rae, 1)}</td>
                  <td class="py-2.5 px-3 text-right font-mono text-[#1E3A8A]">${p.avg_pressure_faced !== null ? p.avg_pressure_faced.toFixed(1) : '—'}</td>
                  <td class="py-2.5 px-3 text-right font-mono font-semibold text-[#334155]">${p.positive_contribution_pct !== null ? p.positive_contribution_pct.toFixed(1) + '%' : '—'}</td>
                  <td class="py-2.5 px-3 text-right font-mono font-bold ${getSignedColorClass(p.mean_hpc)}">${formatSigned(p.mean_hpc, 2)}</td>
                  <td class="py-2.5 px-3 text-right font-mono font-black ${getSignedColorClass(p.total_hpc)}">
                    <span class="px-2 py-0.5 rounded-md ${p.total_hpc >= 0 ? 'bg-[#DCFCE7]' : 'bg-[#FEE2E2]'}">${formatSigned(p.total_hpc, 1)}</span>
                  </td>
                  <td class="py-2.5 px-3 text-center">
                    <button
                      type="button"
                      data-toggle-compare="${escapeHtml(p.batter_name)}"
                      aria-pressed="${selected ? 'true' : 'false'}"
                      class="px-2.5 py-1 rounded-lg text-[10px] font-bold transition ${
                        selected
                          ? 'bg-[#EC4899] text-white'
                          : 'bg-[#F1F5F9] text-[#475569] hover:bg-[#EFF6FF] hover:text-[#2563EB]'
                      }"
                    >${selected ? '✓ Added' : '+ Add'}</button>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>

      <!-- Pagination Footer -->
      <div class="px-4 py-3 border-t border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between text-xs">
        <button type="button" id="exp-prev-page" ${pagination.page <= 1 ? 'disabled' : ''} class="px-3 py-1.5 rounded-lg font-bold border border-[#CBD5E1] bg-white text-[#334155] disabled:opacity-40 hover:bg-[#EFF6FF] transition">
          &larr; Previous
        </button>
        <span class="font-mono text-[#64748B]">Page ${pagination.page} / ${pagination.total_pages}</span>
        <button type="button" id="exp-next-page" ${pagination.page >= pagination.total_pages ? 'disabled' : ''} class="px-3 py-1.5 rounded-lg font-bold border border-[#CBD5E1] bg-white text-[#334155] disabled:opacity-40 hover:bg-[#EFF6FF] transition">
          Next &rarr;
        </button>
      </div>
    `;

    // Bind table header sorting
    wrap.querySelectorAll('[data-sort]').forEach((th) => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        if (this.state.sort_by === key) {
          this.state.sort_order = this.state.sort_order === 'desc' ? 'asc' : 'desc';
        } else {
          this.state.sort_by = key;
          this.state.sort_order = key === 'batter_name' ? 'asc' : 'desc';
        }
        const sortSel = document.getElementById('exp-sort');
        if (sortSel) sortSel.value = this.state.sort_by;
        this.state.page = 1;
        this.fetchAndUpdateTable();
      });
    });

    // Bind compare buttons
    wrap.querySelectorAll('[data-toggle-compare]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const name = btn.dataset.toggleCompare;
        if (this.compareSelection.has(name)) {
          this.compareSelection.delete(name);
        } else if (this.compareSelection.size < 5) {
          this.compareSelection.add(name);
        }
        const cntEl = document.getElementById('explorer-compare-cnt');
        if (cntEl) cntEl.textContent = String(this.compareSelection.size);
        this.renderTableRegion();
      });
    });

    // Bind pagination
    const prevBtn = document.getElementById('exp-prev-page');
    const nextBtn = document.getElementById('exp-next-page');
    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        if (this.state.page > 1) {
          this.state.page -= 1;
          this.fetchAndUpdateTable();
        }
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        if (this.state.page < pagination.total_pages) {
          this.state.page += 1;
          this.fetchAndUpdateTable();
        }
      });
    }
  }

  resetFilters() {
    this.state = {
      search: '',
      season: 'all',
      team: 'all',
      tournament: 'all',
      comp_category: 'all',
      tier: 'all',
      min_inns: 5,
      min_hpc: '',
      max_hpc: '',
      sort_by: 'total_hpc',
      sort_order: 'desc',
      page: 1,
      page_size: 25,
    };
    this.renderShell();
    this.fetchAndUpdateTable();
  }

  bindEvents() {
    const searchEl = document.getElementById('exp-search');
    if (searchEl) {
      searchEl.addEventListener('input', (e) => {
        this.state.search = e.target.value;
        this.state.page = 1;
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.fetchAndUpdateTable(), 220);
      });
    }

    const bindSel = (id, key, isInt = false) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', (e) => {
          this.state[key] = isInt ? parseInt(e.target.value, 10) : e.target.value;
          this.state.page = 1;
          this.fetchAndUpdateTable();
        });
      }
    };
    bindSel('exp-season', 'season');
    bindSel('exp-team', 'team');
    bindSel('exp-tournament', 'tournament');
    bindSel('exp-tier', 'tier');
    bindSel('exp-min-inns', 'min_inns', true);
    bindSel('exp-sort', 'sort_by');

    const bindNum = (id, key) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', (e) => {
          this.state[key] = e.target.value === '' ? '' : Number(e.target.value);
          this.state.page = 1;
          this.fetchAndUpdateTable();
        });
      }
    };
    bindNum('exp-min-hpc', 'min_hpc');
    bindNum('exp-max-hpc', 'max_hpc');

    const resetBtn = document.getElementById('exp-reset-btn');
    if (resetBtn) resetBtn.addEventListener('click', () => this.resetFilters());

    const cmpBtn = document.getElementById('explorer-compare-launch');
    if (cmpBtn) {
      cmpBtn.addEventListener('click', () => {
        if (this.compareSelection.size >= 2) {
          const list = Array.from(this.compareSelection).map((n) => encodeURIComponent(n)).join(',');
          window.location.hash = `#/batting/compare?players=${list}`;
        } else {
          window.location.hash = '#/batting/compare';
        }
      });
    }
  }
}

const instance = new BattingExplorer();
export function renderBattingExplorer(container, params) {
  return instance.render(container, params);
}
