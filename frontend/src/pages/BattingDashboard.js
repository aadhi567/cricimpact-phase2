/**
 * CricImpact Phase 2 — Modernized Batting HPP Overview Dashboard
 * Stage B9: Pink + Blue + Deep Navy light theme, matching Bowling & PCS UI.
 * Displays validated HPP/HPC metrics without modifying underlying calculations.
 */

import { battingApiService } from '../services/battingApiService.js';
import { renderMetricCard } from '../components/MetricCard.js';
import { renderLoadingSkeleton, renderErrorState } from '../components/LoadingSkeleton.js';
import {
  renderBattingMetricExplainer,
  formatSigned,
  getSignedColorClass,
  escapeHtml,
} from '../components/BattingMetricExplainer.js';
import { formatNumber } from '../utils/formatting.js';

export class BattingDashboard {
  constructor() {
    this.container = null;
    this.filtersMeta = null;
    this.data = null;
    this.activeTab = 'top';
    this.charts = {};
    this.state = {
      comp_category: 'all',
      tournament: 'all',
      season: 'all',
      team: 'all',
      tier: 'all',
    };
  }

  destroyCharts() {
    Object.values(this.charts).forEach((ch) => {
      if (ch && typeof ch.destroy === 'function') ch.destroy();
    });
    this.charts = {};
  }

  async render(container) {
    this.container = container;
    this.destroyCharts();
    container.innerHTML = renderLoadingSkeleton('Loading Batting HPP Analytics Dashboard...');

    try {
      const [filtersMeta, dashData] = await Promise.all([
        this.filtersMeta ? Promise.resolve(this.filtersMeta) : battingApiService.getFilters(),
        battingApiService.getDashboard(this.state),
      ]);
      this.filtersMeta = filtersMeta;
      this.data = dashData;
      this.renderShell();
    } catch (err) {
      container.innerHTML = renderErrorState(
        `Failed to load Batting HPP Dashboard: ${err.message}`,
        'window.location.reload()'
      );
    }
  }

  async refreshData() {
    const bodyEl = document.getElementById('batting-dash-body');
    if (bodyEl) {
      bodyEl.classList.add('opacity-50', 'pointer-events-none');
    }
    try {
      this.data = await battingApiService.getDashboard(this.state);
      this.renderShell();
    } catch (err) {
      if (this.container) {
        this.container.innerHTML = renderErrorState(
          `Failed to apply batting dashboard filters: ${err.message}`,
          'window.location.reload()'
        );
      }
    }
  }

  renderShell() {
    this.destroyCharts();
    const { kpis, scope } = this.data;
    const meta = this.filtersMeta;
    const hasActiveFilter = Object.values(this.state).some((v) => v !== 'all');

    const compCatOptions = ['all', ...meta.comp_categories]
      .map((c) => `<option value="${escapeHtml(c)}" ${this.state.comp_category === c ? 'selected' : ''}>${c === 'all' ? 'All Formats / Categories' : escapeHtml(c)}</option>`)
      .join('');

    const tourneyOptions = [
      `<option value="all" ${this.state.tournament === 'all' ? 'selected' : ''}>All Tournaments (${meta.tournaments.length})</option>`,
      ...meta.tournaments.map(
        (t) => `<option value="${escapeHtml(t.comp_name)}" ${this.state.tournament === t.comp_name ? 'selected' : ''}>${escapeHtml(t.comp_name)} (${t.match_count}m)</option>`
      ),
    ].join('');

    const seasonOptions = [
      `<option value="all" ${this.state.season === 'all' ? 'selected' : ''}>All Seasons</option>`,
      ...meta.seasons.slice().reverse().map(
        (s) => `<option value="${escapeHtml(s)}" ${this.state.season === s ? 'selected' : ''}>Season ${escapeHtml(s)}</option>`
      ),
    ].join('');

    const teamOptions = [
      `<option value="all" ${this.state.team === 'all' ? 'selected' : ''}>All Teams (${meta.teams.length})</option>`,
      ...meta.teams.map(
        (t) => `<option value="${escapeHtml(t)}" ${this.state.team === t ? 'selected' : ''}>${escapeHtml(t)}</option>`
      ),
    ].join('');

    const tierOptions = [
      `<option value="all" ${this.state.tier === 'all' ? 'selected' : ''}>All Pressure Tiers</option>`,
      ...meta.pressure_tiers.map(
        (t) => `<option value="${escapeHtml(t)}" ${this.state.tier === t ? 'selected' : ''}>${escapeHtml(t)} Pressure</option>`
      ),
    ].join('');

    this.container.innerHTML = `
      <div class="space-y-6 animate-fade-in">
        <!-- Hero Banner -->
        <section class="hero-gradient-batting rounded-2xl p-5 sm:p-7 shadow-md relative overflow-hidden">
          <div class="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div class="max-w-3xl">
              <div class="flex flex-wrap items-center gap-2 mb-2">
                <span class="px-2.5 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider bg-white/20 text-white backdrop-blur-sm">
                  Batting Analytics &bull; HPP / HPC
                </span>
                <span class="px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-[#1E3A8A]/60 text-white border border-white/20">
                  Validated Production Engine
                </span>
                <span class="text-xs text-white/90 font-mono">
                  ${formatNumber(kpis.matches_played)} Matches &bull; ${formatNumber(kpis.batted_stints)} Batted Stints
                </span>
              </div>
              <h1 id="page-main-heading" tabindex="-1" class="hero-title-fluid font-black text-white tracking-tight">
                Batting HPP Overview Dashboard
              </h1>
              <p class="text-xs sm:text-sm text-white/90 mt-2 leading-relaxed">
                Evaluate batters by Runs Above Expectation (RAE) and pressure-adjusted High-Pressure Contribution (HPC)
                across every match state. DNB stints are strictly labeled <strong>Not Batted</strong> and excluded from averages.
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <a href="#/batting/explorer" class="px-3.5 py-2 rounded-xl bg-white text-[#1E3A8A] hover:bg-[#EFF6FF] font-bold text-xs shadow-sm transition">
                HPP Explorer &rarr;
              </a>
              <a href="#/batting/compare" class="px-3.5 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white border border-white/25 font-bold text-xs backdrop-blur-sm transition">
                Compare Batters
              </a>
              <a href="#/batting/worm_graph" class="px-3.5 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white border border-white/25 font-bold text-xs backdrop-blur-sm transition">
                Worm Graph
              </a>
            </div>
          </div>
        </section>

        <!-- Global Scope Filter Toolbar -->
        <section class="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-sm" aria-label="Dashboard Filters">
          <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-[#3B82F6]"></span>
              <h2 class="text-xs font-black uppercase tracking-wider text-[#0F172A]">Filter Analytical Scope</h2>
            </div>
            ${hasActiveFilter ? `
              <button type="button" id="batting-dash-reset" class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-[#FDF2F8] text-[#DB2777] border border-[#FBCFE8] hover:bg-[#FCE7F3] transition">
                Reset All Filters &times;
              </button>
            ` : `<span class="text-[11px] text-[#64748B]">Full Corpus: 2022–2026 &bull; ${formatNumber(kpis.unique_batters)} Batters</span>`}
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <div>
              <label for="bd-comp-cat" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Format</label>
              <select id="bd-comp-cat" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${compCatOptions}
              </select>
            </div>
            <div>
              <label for="bd-tournament" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Tournament</label>
              <select id="bd-tournament" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${tourneyOptions}
              </select>
            </div>
            <div>
              <label for="bd-season" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Season</label>
              <select id="bd-season" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${seasonOptions}
              </select>
            </div>
            <div>
              <label for="bd-team" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Team</label>
              <select id="bd-team" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${teamOptions}
              </select>
            </div>
            <div>
              <label for="bd-tier" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Pressure Tier</label>
              <select id="bd-tier" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${tierOptions}
              </select>
            </div>
          </div>
        </section>

        <div id="batting-dash-body" class="space-y-6 transition-opacity">
          <!-- 6 Core KPI Cards -->
          <section aria-label="Key Performance Indicators" class="space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h2 class="text-sm font-black text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-[#EC4899]"></span>
                Core Batting Telemetry
              </h2>
              <span class="text-[11px] text-[#64748B]">
                ${formatNumber(kpis.batted_stints)} Batted Stints &bull; ${formatNumber(kpis.dnb_stints)} Not Batted (DNB excluded from averages)
              </span>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
              ${renderMetricCard({
                title: 'Total Runs',
                value: formatNumber(kpis.total_runs),
                unit: 'Runs',
                subtitle: `SR ${kpis.corpus_strike_rate.toFixed(1)} (${formatNumber(kpis.total_balls)} balls)`,
                accent: 'blue',
                tooltip: 'Total runs scored across all batted stints in scope',
              })}
              ${renderMetricCard({
                title: 'Total Contribution',
                value: formatSigned(kpis.total_hpc, 1),
                unit: 'HPC',
                subtitle: `+${formatNumber(Math.round(kpis.pos_hpc_sum))} pos / ${formatNumber(Math.round(kpis.neg_hpc_sum))} neg`,
                accent: 'pink',
                tooltip: 'Sum of pressure-adjusted High-Pressure Contribution (HPC)',
              })}
              ${renderMetricCard({
                title: 'Average HPC',
                value: formatSigned(kpis.avg_hpc, 2),
                unit: '/ inn',
                subtitle: `Mean RAE: ${formatSigned(kpis.avg_rae, 2)} runs`,
                accent: 'deep-blue',
                tooltip: 'Mean HPC per batted innings (DNB strictly excluded)',
              })}
              ${renderMetricCard({
                title: 'Avg Pressure Faced',
                value: kpis.avg_pressure_faced.toFixed(2),
                unit: '/ 100',
                subtitle: 'Pre-delivery situation index',
                accent: 'pink',
                tooltip: 'Mean pre-delivery match pressure on the 0–100 scale',
              })}
              ${renderMetricCard({
                title: 'Positive Contrib %',
                value: `${kpis.positive_contribution_pct.toFixed(1)}%`,
                unit: 'Inns',
                subtitle: `${formatNumber(kpis.positive_stints)} of ${formatNumber(kpis.batted_stints)} batted`,
                accent: 'blue',
                tooltip: 'Share of batted innings with strictly positive HPC (> 0)',
              })}
              ${renderMetricCard({
                title: 'Matches Played',
                value: formatNumber(kpis.matches_played),
                unit: 'T20s',
                subtitle: `${formatNumber(kpis.unique_batters)} unique batters`,
                accent: 'deep-blue',
                tooltip: 'Standard T20 matches in active scope',
              })}
            </div>
          </section>

          <!-- Player Performance Cohorts Section -->
          <section class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-4" aria-label="Player Performance Cohorts">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#F1F5F9] pb-3">
              <div>
                <h2 class="text-base font-black text-[#0F172A]">Player Performance Spotlight</h2>
                <p class="text-xs text-[#64748B]">Click any batter to open their complete HPP profile and match-by-match breakdown.</p>
              </div>
              <div class="flex flex-wrap gap-1.5 bg-[#F8FAFC] p-1 rounded-xl border border-[#E2E8F0]" role="tablist" aria-label="Player performance views">
                ${this._renderCohortTabBtn('top', 'Top Contributors')}
                ${this._renderCohortTabBtn('positive', 'Best Positive %')}
                ${this._renderCohortTabBtn('negative', 'Negative Impact')}
                ${this._renderCohortTabBtn('recent', 'Recent Trends')}
              </div>
            </div>

            <div id="batting-cohort-panel">
              ${this._renderCohortTable()}
            </div>
          </section>

          <!-- Performance Charts Grid (5 Visualizations) -->
          <section class="space-y-5" aria-label="Batting Performance Charts">
            <div class="flex items-center justify-between">
              <h2 class="text-sm font-black text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-[#3B82F6]"></span>
                Visual Performance Analytics
              </h2>
              <span class="text-[11px] text-[#64748B]">Interactive charts built strictly from validated HPP stints</span>
            </div>

            <!-- Row 1: HPC Distribution + Runs vs HPC Scatter -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
                <div class="flex items-center justify-between mb-3">
                  <div>
                    <h3 class="text-sm font-black text-[#0F172A]">HPC Distribution</h3>
                    <p class="text-[11px] text-[#64748B]">Frequency of batted innings across contribution buckets</p>
                  </div>
                  <span class="badge-blue">Stint Level</span>
                </div>
                <div class="relative h-64 w-full">
                  <canvas id="chart-bd-hpc-dist" aria-label="HPC Distribution Bar Chart" role="img"></canvas>
                </div>
              </div>

              <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
                <div class="flex items-center justify-between mb-3">
                  <div>
                    <h3 class="text-sm font-black text-[#0F172A]">Runs vs Total HPC</h3>
                    <p class="text-[11px] text-[#64748B]">Volume vs pressure-adjusted value (click a point to view profile)</p>
                  </div>
                  <span class="badge-pink">Min ${scope.min_innings_qual} Inns</span>
                </div>
                <div class="relative h-64 w-full">
                  <canvas id="chart-bd-runs-hpc" aria-label="Runs versus HPC Scatter Chart" role="img"></canvas>
                </div>
              </div>
            </div>

            <!-- Row 2: Season Contribution Trend + Pressure vs Contribution -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
                <div class="flex items-center justify-between mb-3">
                  <div>
                    <h3 class="text-sm font-black text-[#0F172A]">Season Contribution &amp; Pressure Trend</h3>
                    <p class="text-[11px] text-[#64748B]">Positive contribution % &amp; average pressure faced across seasons</p>
                  </div>
                  <span class="badge-blue">2022–2026</span>
                </div>
                <div class="relative h-64 w-full">
                  <canvas id="chart-bd-season-trend" aria-label="Season Contribution Trend Chart" role="img"></canvas>
                </div>
              </div>

              <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
                <div class="flex items-center justify-between mb-3">
                  <div>
                    <h3 class="text-sm font-black text-[#0F172A]">Pressure Tier vs Contribution</h3>
                    <p class="text-[11px] text-[#64748B]">Mean HPC &amp; Mean RAE across Low, Medium, High &amp; Extreme pressure</p>
                  </div>
                  <span class="badge-pink">Asymmetric Curve</span>
                </div>
                <div class="relative h-64 w-full">
                  <canvas id="chart-bd-pressure-contrib" aria-label="Pressure versus Contribution Chart" role="img"></canvas>
                </div>
              </div>
            </div>

            <!-- Row 3: Player Contribution Ranking + 1st Inn vs Chase Context -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
              <div class="lg:col-span-2 bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
                <div class="flex items-center justify-between mb-3">
                  <div>
                    <h3 class="text-sm font-black text-[#0F172A]">Player Contribution Ranking</h3>
                    <p class="text-[11px] text-[#64748B]">Top positive HPC leaders vs lowest negative HPC impact in active scope</p>
                  </div>
                  <a href="#/batting/explorer" class="text-xs font-bold text-[#2563EB] hover:text-[#1E3A8A]">Full Explorer &rarr;</a>
                </div>
                <div class="relative h-72 w-full">
                  <canvas id="chart-bd-ranking" aria-label="Player Contribution Ranking Horizontal Bar Chart" role="img"></canvas>
                </div>
              </div>

              <!-- 1st Innings vs 2nd Innings Chase Card -->
              <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm flex flex-col justify-between">
                <div>
                  <h3 class="text-sm font-black text-[#0F172A]">Innings Pressure Split</h3>
                  <p class="text-[11px] text-[#64748B] mb-4">Setting targets vs second-innings chases</p>
                  <div class="space-y-3">
                    ${this.data.charts.innings_comparison.map((inn) => `
                      <div class="p-3.5 rounded-xl border ${inn.innings === 1 ? 'bg-[#EFF6FF]/60 border-[#BFDBFE]' : 'bg-[#FDF2F8]/60 border-[#FBCFE8]'}">
                        <div class="flex items-center justify-between mb-2">
                          <span class="text-xs font-black ${inn.innings === 1 ? 'text-[#1E3A8A]' : 'text-[#BE185D]'}">${escapeHtml(inn.label)}</span>
                          <span class="text-[11px] font-mono text-[#64748B]">${formatNumber(inn.stints)} inns</span>
                        </div>
                        <div class="grid grid-cols-3 gap-2 text-xs">
                          <div>
                            <div class="text-[10px] uppercase font-bold text-[#64748B]">Avg Pressure</div>
                            <div class="font-black text-[#0F172A]">${inn.avg_pressure.toFixed(1)}</div>
                          </div>
                          <div>
                            <div class="text-[10px] uppercase font-bold text-[#64748B]">Avg HPC</div>
                            <div class="font-black ${getSignedColorClass(inn.avg_hpc)}">${formatSigned(inn.avg_hpc, 2)}</div>
                          </div>
                          <div>
                            <div class="text-[10px] uppercase font-bold text-[#64748B]">Pos %</div>
                            <div class="font-black text-[#1E3A8A]">${inn.positive_pct.toFixed(1)}%</div>
                          </div>
                        </div>
                      </div>
                    `).join('')}
                  </div>
                </div>
                <div class="mt-4 pt-3 border-t border-[#F1F5F9] text-[11px] text-[#64748B]">
                  Pressure tiers quantify situational difficulty before each delivery without altering raw run totals.
                </div>
              </div>
            </div>
          </section>

          <!-- Metric Explanations -->
          ${renderBattingMetricExplainer({ compact: false })}
        </div>
      </div>
    `;

    this.bindEvents();
    this.renderCharts();
  }

  _renderCohortTabBtn(id, label) {
    const active = this.activeTab === id;
    return `
      <button
        type="button"
        role="tab"
        aria-selected="${active ? 'true' : 'false'}"
        data-cohort-tab="${id}"
        class="px-3 py-1.5 rounded-lg text-xs font-bold transition ${
          active
            ? 'bg-gradient-to-r from-[#3B82F6] to-[#EC4899] text-white shadow-sm'
            : 'text-[#64748B] hover:text-[#0F172A] hover:bg-white'
        }"
      >${label}</button>
    `;
  }

  _renderCohortTable() {
    let rows = [];
    let extraColLabel = 'Crisis HPC';
    if (this.activeTab === 'top') {
      rows = this.data.top_contributors || [];
    } else if (this.activeTab === 'positive') {
      rows = this.data.best_positive_contributors || [];
      extraColLabel = 'Pos Inns';
    } else if (this.activeTab === 'negative') {
      rows = this.data.negative_contributors || [];
      extraColLabel = 'Neg HPC';
    } else {
      rows = this.data.recent_trends || [];
      extraColLabel = 'vs Career';
    }

    if (!rows.length) {
      return `<div class="py-8 text-center text-xs text-[#64748B]">No batters match the selected scope criteria.</div>`;
    }

    return `
      <div class="table-wrapper rounded-xl border border-[#E2E8F0]" tabindex="0" role="region" aria-label="Player Performance Cohort Table">
        <table class="text-xs text-left">
          <caption class="visually-hidden">Batting performance spotlight players</caption>
          <thead class="bg-[#F8FAFC] text-[10px] font-bold uppercase tracking-wider text-[#64748B] border-b border-[#E2E8F0]">
            <tr>
              <th scope="col" class="py-2.5 px-3 text-center w-10">#</th>
              <th scope="col" class="py-2.5 px-3">Batter</th>
              <th scope="col" class="py-2.5 px-3">Team</th>
              <th scope="col" class="py-2.5 px-3 text-right">Inns</th>
              <th scope="col" class="py-2.5 px-3 text-right">Runs</th>
              <th scope="col" class="py-2.5 px-3 text-right">SR</th>
              <th scope="col" class="py-2.5 px-3 text-right">Total RAE</th>
              <th scope="col" class="py-2.5 px-3 text-right">Total HPC</th>
              <th scope="col" class="py-2.5 px-3 text-right">POS REL</th>
              <th scope="col" class="py-2.5 px-3 text-right">${extraColLabel}</th>
              <th scope="col" class="py-2.5 px-3 text-center">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#F1F5F9]">
            ${rows.map((p, i) => {
              const profileHref = `#/batting/players/${encodeURIComponent(p.batter_name)}`;
              const compareHref = `#/batting/compare?players=${encodeURIComponent(p.batter_name)},Abhishek%20Sharma`;
              let extraVal = formatSigned(p.crisis_total_hpc, 1);
              let extraCls = 'text-[#1E3A8A]';
              if (this.activeTab === 'positive') {
                extraVal = `${p.positive_innings}/${p.innings_batted}`;
                extraCls = 'text-[#16A34A]';
              } else if (this.activeTab === 'negative') {
                extraVal = formatSigned(p.neg_hpc_sum, 1);
                extraCls = 'text-[#DC2626]';
              } else if (this.activeTab === 'recent') {
                extraVal = p.trend_delta !== null && p.trend_delta !== undefined ? `${formatSigned(p.trend_delta, 2)}/inn` : '—';
                extraCls = getSignedColorClass(p.trend_delta);
              }

              return `
                <tr class="hover:bg-[#F8FAFC] transition">
                  <td class="py-2.5 px-3 text-center font-mono text-[#94A3B8] font-bold">${i + 1}</td>
                  <th scope="row" class="py-2.5 px-3 font-bold text-[#0F172A] whitespace-nowrap">
                    <a href="${profileHref}" class="hover:text-[#DB2777] transition">${escapeHtml(p.batter_name)}</a>
                  </th>
                  <td class="py-2.5 px-3 text-[#64748B] whitespace-nowrap">${escapeHtml(p.primary_team || '—')}</td>
                  <td class="py-2.5 px-3 text-right font-mono text-[#334155]">${p.innings_batted}</td>
                  <td class="py-2.5 px-3 text-right font-mono font-bold text-[#0F172A]">${formatNumber(p.actual_runs)}</td>
                  <td class="py-2.5 px-3 text-right font-mono text-[#334155]">${p.strike_rate !== null ? p.strike_rate.toFixed(1) : '—'}</td>
                  <td class="py-2.5 px-3 text-right font-mono font-semibold ${getSignedColorClass(p.total_rae)}">${formatSigned(p.total_rae, 1)}</td>
                  <td class="py-2.5 px-3 text-right font-mono font-black ${getSignedColorClass(p.total_hpc)}">
                    <span class="px-2 py-0.5 rounded-md ${p.total_hpc >= 0 ? 'bg-[#DCFCE7]' : 'bg-[#FEE2E2]'}">${formatSigned(p.total_hpc, 1)}</span>
                  </td>
                  <td class="py-2.5 px-3 text-right font-mono font-semibold">
                    ${
                      p.positive_contribution_pct !== null
                        ? `<span class="px-2 py-0.5 rounded-md font-black ${
                            p.positive_contribution_pct >= 50
                              ? 'bg-[#DCFCE7] text-[#15803D] border border-[#BBF7D0]'
                              : 'bg-[#FEF9C3] text-[#854D0E] border border-[#FDE047]'
                          }">${p.positive_contribution_pct.toFixed(1)}%</span>`
                        : '—'
                    }
                  </td>
                  <td class="py-2.5 px-3 text-right font-mono font-semibold ${extraCls}">${extraVal}</td>
                  <td class="py-2.5 px-3 text-center whitespace-nowrap">
                    <div class="inline-flex items-center gap-1.5">
                      <a href="${profileHref}" class="px-2 py-1 rounded-lg bg-[#EFF6FF] text-[#2563EB] hover:bg-[#DBEAFE] font-bold text-[10px] transition">Profile</a>
                      <a href="${compareHref}" class="px-2 py-1 rounded-lg bg-[#FDF2F8] text-[#DB2777] hover:bg-[#FCE7F3] font-bold text-[10px] transition">Compare</a>
                    </div>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  bindEvents() {
    const bindSelect = (id, key) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', (e) => {
          this.state[key] = e.target.value;
          this.refreshData();
        });
      }
    };
    bindSelect('bd-comp-cat', 'comp_category');
    bindSelect('bd-tournament', 'tournament');
    bindSelect('bd-season', 'season');
    bindSelect('bd-team', 'team');
    bindSelect('bd-tier', 'tier');

    const resetBtn = document.getElementById('batting-dash-reset');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        this.state = { comp_category: 'all', tournament: 'all', season: 'all', team: 'all', tier: 'all' };
        this.refreshData();
      });
    }

    document.querySelectorAll('[data-cohort-tab]').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.activeTab = btn.dataset.cohortTab;
        document.querySelectorAll('[data-cohort-tab]').forEach((b) => {
          const isAct = b.dataset.cohortTab === this.activeTab;
          b.setAttribute('aria-selected', isAct ? 'true' : 'false');
          b.className = `px-3 py-1.5 rounded-lg text-xs font-bold transition ${
            isAct
              ? 'bg-gradient-to-r from-[#3B82F6] to-[#EC4899] text-white shadow-sm'
              : 'text-[#64748B] hover:text-[#0F172A] hover:bg-white'
          }`;
        });
        const panel = document.getElementById('batting-cohort-panel');
        if (panel) panel.innerHTML = this._renderCohortTable();
      });
    });
  }

  renderCharts() {
    if (typeof Chart === 'undefined') return;
    const ch = this.data.charts;

    // 1. HPC Distribution Bar Chart
    const distCtx = document.getElementById('chart-bd-hpc-dist');
    if (distCtx) {
      this.charts.dist = new Chart(distCtx, {
        type: 'bar',
        data: {
          labels: ch.hpc_distribution.map((b) => b.label),
          datasets: [{
            label: 'Batted Stints',
            data: ch.hpc_distribution.map((b) => b.count),
            backgroundColor: ch.hpc_distribution.map((b) => (b.is_positive ? '#3B82F6' : '#EC4899')),
            borderRadius: 6,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.parsed.y.toLocaleString()} batted stints`,
              },
            },
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 10 } } },
            y: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B', font: { size: 10 } } },
          },
        },
      });
    }

    // 2. Runs vs Total HPC Scatter
    const scatterCtx = document.getElementById('chart-bd-runs-hpc');
    if (scatterCtx) {
      const pts = ch.runs_vs_hpc.map((p) => ({
        x: p.runs,
        y: p.total_hpc,
        name: p.batter_name,
        sr: p.strike_rate,
        inns: p.innings,
      }));
      this.charts.scatter = new Chart(scatterCtx, {
        type: 'scatter',
        data: {
          datasets: [{
            label: 'Batters',
            data: pts,
            backgroundColor: pts.map((pt) => (pt.y >= 0 ? 'rgba(59, 130, 246, 0.72)' : 'rgba(236, 72, 153, 0.72)')),
            borderColor: pts.map((pt) => (pt.y >= 0 ? '#1E3A8A' : '#BE185D')),
            borderWidth: 1,
            pointRadius: 5,
            pointHoverRadius: 7,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          onClick: (_, elements) => {
            if (elements.length > 0) {
              const pt = pts[elements[0].index];
              if (pt && pt.name) {
                window.location.hash = `#/batting/players/${encodeURIComponent(pt.name)}`;
              }
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const p = ctx.raw;
                  return `${p.name}: ${p.x} runs, ${p.y >= 0 ? '+' : ''}${p.y.toFixed(1)} HPC (${p.inns} inns, SR ${p.sr ?? '—'})`;
                },
              },
            },
          },
          scales: {
            x: {
              title: { display: true, text: 'Total Runs', color: '#475569', font: { size: 11, weight: 'bold' } },
              grid: { color: '#F1F5F9' },
              ticks: { color: '#64748B', font: { size: 10 } },
            },
            y: {
              title: { display: true, text: 'Total HPC', color: '#475569', font: { size: 11, weight: 'bold' } },
              grid: { color: '#F1F5F9' },
              ticks: { color: '#64748B', font: { size: 10 } },
            },
          },
        },
      });
    }

    // 3. Season Trend (Positive % bars + Avg Pressure line)
    const seasonCtx = document.getElementById('chart-bd-season-trend');
    if (seasonCtx) {
      this.charts.season = new Chart(seasonCtx, {
        type: 'bar',
        data: {
          labels: ch.season_trend.map((s) => s.season),
          datasets: [
            {
              type: 'bar',
              label: 'Positive Contribution %',
              data: ch.season_trend.map((s) => s.positive_pct),
              backgroundColor: 'rgba(59, 130, 246, 0.78)',
              borderRadius: 6,
              yAxisID: 'y',
            },
            {
              type: 'line',
              label: 'Avg Pressure Faced',
              data: ch.season_trend.map((s) => s.avg_pressure),
              borderColor: '#EC4899',
              backgroundColor: '#EC4899',
              tension: 0.3,
              borderWidth: 2.5,
              pointRadius: 4,
              yAxisID: 'y',
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 10, font: { size: 11 }, color: '#334155' } },
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 11 } } },
            y: {
              min: 0,
              max: 60,
              grid: { color: '#F1F5F9' },
              ticks: { color: '#64748B', font: { size: 10 } },
              title: { display: true, text: 'Rate / Pressure Index', color: '#64748B', font: { size: 10 } },
            },
          },
        },
      });
    }

    // 4. Pressure vs Contribution (Tier Breakdown)
    const pressCtx = document.getElementById('chart-bd-pressure-contrib');
    if (pressCtx) {
      this.charts.pressure = new Chart(pressCtx, {
        type: 'bar',
        data: {
          labels: ch.pressure_vs_contribution.map((t) => `${t.tier} (${t.share_pct}%)`),
          datasets: [
            {
              label: 'Mean HPC',
              data: ch.pressure_vs_contribution.map((t) => t.avg_hpc),
              backgroundColor: '#1E3A8A',
              borderRadius: 6,
            },
            {
              label: 'Mean RAE',
              data: ch.pressure_vs_contribution.map((t) => t.avg_rae),
              backgroundColor: '#EC4899',
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', labels: { boxWidth: 10, font: { size: 11 }, color: '#334155' } },
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 10 } } },
            y: {
              grid: { color: '#F1F5F9' },
              ticks: { color: '#64748B', font: { size: 10 } },
              title: { display: true, text: 'Mean Impact per Innings', color: '#64748B', font: { size: 10 } },
            },
          },
        },
      });
    }

    // 5. Player Contribution Ranking Horizontal Bar
    const rankCtx = document.getElementById('chart-bd-ranking');
    if (rankCtx) {
      const combined = [
        ...(ch.player_ranking.top || []),
        ...(ch.player_ranking.bottom || []).slice().reverse(),
      ];
      this.charts.ranking = new Chart(rankCtx, {
        type: 'bar',
        data: {
          labels: combined.map((p) => p.batter_name),
          datasets: [{
            label: 'Total HPC',
            data: combined.map((p) => p.total_hpc),
            backgroundColor: combined.map((p) => (p.total_hpc >= 0 ? '#3B82F6' : '#EC4899')),
            borderRadius: 4,
          }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          onClick: (_, elements) => {
            if (elements.length > 0) {
              const p = combined[elements[0].index];
              if (p) window.location.hash = `#/batting/players/${encodeURIComponent(p.batter_name)}`;
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.parsed.x >= 0 ? '+' : ''}${ctx.parsed.x.toFixed(1)} HPC (${combined[ctx.dataIndex].runs} runs)`,
              },
            },
          },
          scales: {
            x: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B', font: { size: 10 } } },
            y: { grid: { display: false }, ticks: { color: '#0F172A', font: { size: 10, weight: 'bold' } } },
          },
        },
      });
    }
  }
}

const instance = new BattingDashboard();
export function renderBattingDashboard(container) {
  return instance.render(container);
}
