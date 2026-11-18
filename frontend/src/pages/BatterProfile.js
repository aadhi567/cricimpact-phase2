/**
 * CricImpact Phase 2 — Modernized Individual Batter HPP Profile Page
 * Stage B9: Pink + Blue + Deep Navy light theme.
 * Sections: Batting Summary, Contribution Analysis, 5 Performance Graphs,
 * and Interactive Match Breakdown with strict DNB ("Not Batted") preservation.
 */

import { battingApiService } from '../services/battingApiService.js';
import { renderLoadingSkeleton, renderErrorState } from '../components/LoadingSkeleton.js';
import {
  renderBattingMetricExplainer,
  getPressureTierBadge,
  formatSigned,
  getSignedColorClass,
  escapeHtml,
} from '../components/BattingMetricExplainer.js';
import { formatNumber } from '../utils/formatting.js';

export class BatterProfile {
  constructor() {
    this.container = null;
    this.allPlayers = null;
    this.profile = null;
    this.charts = {};
    this.selectedMatchIdx = null;
    this.showDnb = true;
    this.state = {
      player: 'Abhishek Sharma',
      season: 'all',
      tournament: 'all',
    };
  }

  destroyCharts() {
    Object.values(this.charts).forEach((ch) => {
      if (ch && typeof ch.destroy === 'function') ch.destroy();
    });
    this.charts = {};
  }

  async render(container, params = {}) {
    this.container = container;
    this.destroyCharts();

    const targetName = params.name || params.id || params.player || this.state.player || 'Abhishek Sharma';
    const decoded = decodeURIComponent(String(targetName));
    if (decoded !== this.state.player) {
      this.state = { player: decoded, season: 'all', tournament: 'all' };
      this.selectedMatchIdx = null;
    }

    container.innerHTML = renderLoadingSkeleton(`Loading Batter HPP Profile: ${escapeHtml(this.state.player)}...`);

    try {
      const [playersRes, prof] = await Promise.all([
        this.allPlayers ? Promise.resolve({ players: this.allPlayers }) : battingApiService.getPlayers(),
        battingApiService.getPlayerProfile(this.state.player, {
          season: this.state.season,
          tournament: this.state.tournament,
        }),
      ]);
      this.allPlayers = playersRes.players;
      this.profile = prof;
      this.state.player = prof.summary.batter_name;
      if (this.selectedMatchIdx === null && prof.match_log.length > 0) {
        this.selectedMatchIdx = prof.match_log.length - 1;
      }
      this.renderContent();
    } catch (err) {
      container.innerHTML = renderErrorState(
        `Unable to load profile for "${escapeHtml(this.state.player)}": ${err.message}`,
        `window.location.hash='#/batting/players/Abhishek%20Sharma'`
      );
    }
  }

  async reloadScoped() {
    try {
      this.profile = await battingApiService.getPlayerProfile(this.state.player, {
        season: this.state.season,
        tournament: this.state.tournament,
      });
      this.selectedMatchIdx = this.profile.match_log.length > 0 ? this.profile.match_log.length - 1 : null;
      this.renderContent();
    } catch (err) {
      this.container.innerHTML = renderErrorState(
        `Failed to update player scope: ${err.message}`,
        'window.location.reload()'
      );
    }
  }

  renderContent() {
    this.destroyCharts();
    const { summary, available_seasons, available_tournaments, by_innings, by_pressure_tier, season_breakdown, match_log } = this.profile;
    document.title = `${summary.batter_name} — Batting HPP Profile | CricImpact Phase 2`;

    const playerOptions = (this.allPlayers || [])
      .map((p) => `<option value="${escapeHtml(p.batter_name)}" ${p.batter_name === summary.batter_name ? 'selected' : ''}>${escapeHtml(p.batter_name)} (${p.innings_batted} inns, ${p.actual_runs} runs)</option>`)
      .join('');

    const seasonOptions = [
      `<option value="all" ${this.state.season === 'all' ? 'selected' : ''}>All Seasons (${available_seasons.length})</option>`,
      ...available_seasons.slice().reverse().map((s) => `<option value="${escapeHtml(s)}" ${this.state.season === s ? 'selected' : ''}>Season ${escapeHtml(s)}</option>`),
    ].join('');

    const tourneyOptions = [
      `<option value="all" ${this.state.tournament === 'all' ? 'selected' : ''}>All Tournaments (${available_tournaments.length})</option>`,
      ...available_tournaments.map((t) => `<option value="${escapeHtml(t)}" ${this.state.tournament === t ? 'selected' : ''}>${escapeHtml(t)}</option>`),
    ].join('');

    const visibleLog = this.showDnb ? match_log : match_log.filter((m) => !m.is_dnb);
    const activeMatch = this.selectedMatchIdx !== null && match_log[this.selectedMatchIdx] ? match_log[this.selectedMatchIdx] : null;

    this.container.innerHTML = `
      <div class="space-y-6 animate-fade-in">
        <!-- Profile Hero & Player Switcher -->
        <section class="hero-gradient-batting rounded-2xl p-5 sm:p-7 shadow-md">
          <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <div class="flex flex-wrap items-center gap-2 mb-2">
                <span class="px-2.5 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider bg-white/20 text-white">
                  Batter HPP Profile
                </span>
                ${summary.teams.slice(0, 3).map((tm) => `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#1E3A8A]/60 text-white border border-white/20">${escapeHtml(tm)}</span>`).join('')}
                ${summary.dnb_count > 0 ? `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-white/15 text-white border border-white/25">${summary.dnb_count} Not Batted (DNB)</span>` : ''}
              </div>
              <h1 id="page-main-heading" tabindex="-1" class="hero-title-fluid font-black text-white tracking-tight">
                ${escapeHtml(summary.batter_name)}
              </h1>
              <p class="text-xs text-white/90 mt-1">
                ${summary.total_matches} Matches &bull; ${summary.innings_batted} Innings Batted &bull; ${formatNumber(summary.actual_runs)} Runs (${formatNumber(summary.balls_faced)} Balls) &bull; Total HPC: <strong>${formatSigned(summary.total_hpc, 2)}</strong>
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <a href="#/batting/compare?players=${encodeURIComponent(summary.batter_name)},Suryakumar%20Yadav" class="px-3.5 py-2 rounded-xl bg-white text-[#1E3A8A] hover:bg-[#EFF6FF] font-bold text-xs shadow-sm transition">
                Compare Batter &rarr;
              </a>
              <a href="#/batting/explorer" class="px-3.5 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white border border-white/25 font-bold text-xs transition">
                Back to Explorer
              </a>
            </div>
          </div>

          <!-- Switcher & Scope Controls -->
          <div class="mt-5 pt-4 border-t border-white/20 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label for="bp-player-select" class="block text-[10px] font-bold uppercase tracking-wider text-white/80 mb-1">Switch Batter (880 Players)</label>
              <select id="bp-player-select" class="w-full px-3 py-2 text-xs font-semibold bg-white text-[#0F172A] rounded-xl border-0 shadow-sm">
                ${playerOptions}
              </select>
            </div>
            <div>
              <label for="bp-season-select" class="block text-[10px] font-bold uppercase tracking-wider text-white/80 mb-1">Season Scope</label>
              <select id="bp-season-select" class="w-full px-3 py-2 text-xs font-semibold bg-white text-[#0F172A] rounded-xl border-0 shadow-sm">
                ${seasonOptions}
              </select>
            </div>
            <div>
              <label for="bp-tourney-select" class="block text-[10px] font-bold uppercase tracking-wider text-white/80 mb-1">Tournament Scope</label>
              <select id="bp-tourney-select" class="w-full px-3 py-2 text-xs font-semibold bg-white text-[#0F172A] rounded-xl border-0 shadow-sm">
                ${tourneyOptions}
              </select>
            </div>
          </div>
        </section>

        <!-- SECTION 1: BATTING SUMMARY -->
        <section class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-4" aria-label="Batting Summary">
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-[#F1F5F9] pb-2.5">
            <h2 class="text-sm font-black uppercase tracking-wider text-[#0F172A] flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-[#3B82F6]"></span>
              1. Batting Summary
            </h2>
            <span class="text-[11px] text-[#64748B]">DNB innings (${summary.dnb_count}) are excluded from averages &amp; strike rates</span>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
            ${this._miniStat('Runs', formatNumber(summary.actual_runs), 'text-[#0F172A]', 'blue')}
            ${this._miniStat('Innings', `${summary.innings_batted}${summary.dnb_count > 0 ? ` (${summary.dnb_count} DNB)` : ''}`, 'text-[#0F172A]', 'slate')}
            ${this._miniStat('Average', summary.batting_average !== null ? summary.batting_average.toFixed(2) : '—', 'text-[#1E3A8A]', 'blue')}
            ${this._miniStat('Strike Rate', summary.strike_rate !== null ? summary.strike_rate.toFixed(1) : '—', 'text-[#DB2777]', 'pink')}
            ${this._miniStat('Balls Faced', formatNumber(summary.balls_faced), 'text-[#0F172A]', 'slate')}
            ${this._miniStat('4s / 6s', `${summary.fours} / ${summary.sixes}`, 'text-[#2563EB]', 'blue')}
            ${this._miniStat('Expected Runs', summary.expected_runs !== null ? summary.expected_runs.toFixed(1) : '—', 'text-[#475569]', 'slate')}
            ${this._miniStat('Total HPC', formatSigned(summary.total_hpc, 2), getSignedColorClass(summary.total_hpc), 'pink')}
          </div>
        </section>

        <!-- SECTION 2: CONTRIBUTION ANALYSIS -->
        <section class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-5" aria-label="Contribution Analysis">
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-[#F1F5F9] pb-2.5">
            <h2 class="text-sm font-black uppercase tracking-wider text-[#0F172A] flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-[#EC4899]"></span>
              2. Contribution Analysis (HPC, RAE &amp; Context)
            </h2>
            <span class="text-[11px] font-semibold text-[#64748B]">Avg Pressure Faced: <strong class="text-[#1E3A8A]">${summary.avg_pressure_faced !== null ? summary.avg_pressure_faced.toFixed(2) : '—'} / 100</strong></span>
          </div>

          <!-- Core Contribution KPIs -->
          <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <div class="p-3.5 rounded-xl bg-[#FDF2F8]/70 border border-[#FBCFE8]">
              <div class="text-[10px] font-bold uppercase text-[#BE185D]">Total RAE</div>
              <div class="text-xl font-black mt-1 ${getSignedColorClass(summary.total_rae)}">${formatSigned(summary.total_rae, 2)}</div>
              <div class="text-[11px] text-[#64748B] mt-0.5">Mean: ${formatSigned(summary.mean_rae, 2)} / inn</div>
            </div>
            <div class="p-3.5 rounded-xl bg-[#EFF6FF]/70 border border-[#BFDBFE]">
              <div class="text-[10px] font-bold uppercase text-[#1E3A8A]">Total HPC</div>
              <div class="text-xl font-black mt-1 ${getSignedColorClass(summary.total_hpc)}">${formatSigned(summary.total_hpc, 2)}</div>
              <div class="text-[11px] text-[#64748B] mt-0.5">+${summary.pos_hpc_sum !== null ? summary.pos_hpc_sum.toFixed(1) : '0.0'} pos / ${summary.neg_hpc_sum !== null ? summary.neg_hpc_sum.toFixed(1) : '0.0'} neg</div>
            </div>
            <div class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Average HPC</div>
              <div class="text-xl font-black mt-1 ${getSignedColorClass(summary.mean_hpc)}">${formatSigned(summary.mean_hpc, 2)}</div>
              <div class="text-[11px] text-[#64748B] mt-0.5">Per batted innings</div>
            </div>
            <div class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div class="text-[10px] font-bold uppercase text-[#64748B]">Positive Contrib %</div>
              <div class="text-xl font-black mt-1 text-[#1E3A8A]">${summary.positive_contribution_pct !== null ? summary.positive_contribution_pct.toFixed(1) + '%' : '—'}</div>
              <div class="text-[11px] text-[#64748B] mt-0.5">${summary.positive_innings} pos / ${summary.negative_innings} neg</div>
            </div>
            <div class="p-3.5 rounded-xl bg-[#FEF3C7]/40 border border-[#FDE68A]">
              <div class="text-[10px] font-bold uppercase text-[#B45309]">Crisis HPC (High+Ext)</div>
              <div class="text-xl font-black mt-1 ${getSignedColorClass(summary.crisis_total_hpc)}">${formatSigned(summary.crisis_total_hpc, 2)}</div>
              <div class="text-[11px] text-[#64748B] mt-0.5">${summary.crisis_innings} high-pressure inns</div>
            </div>
          </div>

          <!-- Contribution by Innings + Contribution by Pressure Tier -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div class="space-y-2.5">
              <h3 class="text-xs font-black uppercase tracking-wider text-[#475569]">Contribution by Innings</h3>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                ${by_innings.map((inn) => `
                  <div class="p-3.5 rounded-xl border ${inn.innings === 1 ? 'bg-[#EFF6FF]/50 border-[#BFDBFE]' : 'bg-[#FDF2F8]/50 border-[#FBCFE8]'}">
                    <div class="text-xs font-black ${inn.innings === 1 ? 'text-[#1E3A8A]' : 'text-[#BE185D]'}">${escapeHtml(inn.label)}</div>
                    <div class="text-[11px] text-[#64748B] mb-2">${inn.innings_batted} inns &bull; ${formatNumber(inn.runs)} runs (SR ${inn.strike_rate !== null ? inn.strike_rate.toFixed(1) : '—'})</div>
                    <div class="grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <span class="text-[10px] text-[#64748B] block">Total HPC</span>
                        <strong class="${getSignedColorClass(inn.total_hpc)}">${formatSigned(inn.total_hpc, 1)}</strong>
                      </div>
                      <div>
                        <span class="text-[10px] text-[#64748B] block">Avg HPC</span>
                        <strong class="${getSignedColorClass(inn.mean_hpc)}">${formatSigned(inn.mean_hpc, 2)}</strong>
                      </div>
                      <div>
                        <span class="text-[10px] text-[#64748B] block">Avg P</span>
                        <strong class="text-[#0F172A]">${inn.avg_pressure !== null ? inn.avg_pressure.toFixed(1) : '—'}</strong>
                      </div>
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>

            <div class="space-y-2.5">
              <h3 class="text-xs font-black uppercase tracking-wider text-[#475569]">Contribution by Pressure Tier</h3>
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                ${by_pressure_tier.map((t) => `
                  <div class="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                    <div class="mb-1.5">${getPressureTierBadge(t.tier)}</div>
                    <div class="text-sm font-black ${getSignedColorClass(t.total_hpc)}">${formatSigned(t.total_hpc, 1)}</div>
                    <div class="text-[10px] text-[#64748B] mt-0.5">${t.innings_batted} inns &bull; ${t.runs}r</div>
                    <div class="text-[10px] text-[#64748B]">Avg: ${formatSigned(t.mean_hpc, 2)}</div>
                  </div>
                `).join('')}
              </div>
            </div>
          </div>
        </section>

        <!-- SECTION 3: 5 PERFORMANCE GRAPHS -->
        <section class="space-y-4" aria-label="Performance Graphs">
          <h2 class="text-sm font-black uppercase tracking-wider text-[#0F172A] flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-[#1E3A8A]"></span>
            3. Performance Graphs
          </h2>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <!-- Graph 1: Career Contribution Graph -->
            <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
              <h3 class="text-sm font-black text-[#0F172A]">Career Cumulative Contribution</h3>
              <p class="text-[11px] text-[#64748B] mb-3">Cumulative HPC trajectory across batted innings</p>
              <div class="relative h-60 w-full">
                <canvas id="chart-bp-career-cum" aria-label="Career Cumulative HPC Graph" role="img"></canvas>
              </div>
            </div>

            <!-- Graph 2: Season-wise HPC Trend -->
            <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
              <h3 class="text-sm font-black text-[#0F172A]">Season-Wise HPC Trend</h3>
              <p class="text-[11px] text-[#64748B] mb-3">Total HPC &amp; Mean HPC per season</p>
              <div class="relative h-60 w-full">
                <canvas id="chart-bp-season-trend" aria-label="Season-wise HPC Trend Chart" role="img"></canvas>
              </div>
            </div>

            <!-- Graph 3: Runs vs Expected Runs -->
            <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
              <h3 class="text-sm font-black text-[#0F172A]">Runs vs Expected Runs</h3>
              <p class="text-[11px] text-[#64748B] mb-3">Actual runs scored compared to match-state expected runs (latest 30 batted innings)</p>
              <div class="relative h-60 w-full">
                <canvas id="chart-bp-runs-exp" aria-label="Runs versus Expected Runs Chart" role="img"></canvas>
              </div>
            </div>

            <!-- Graph 4: Pressure vs Contribution -->
            <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
              <h3 class="text-sm font-black text-[#0F172A]">Pressure vs Contribution</h3>
              <p class="text-[11px] text-[#64748B] mb-3">Innings HPC plotted against pre-delivery pressure faced (0–100)</p>
              <div class="relative h-60 w-full">
                <canvas id="chart-bp-pressure-hpc" aria-label="Pressure versus HPC Scatter Plot" role="img"></canvas>
              </div>
            </div>
          </div>

          <!-- Graph 5: Match-by-Match Contribution -->
          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
            <h3 class="text-sm font-black text-[#0F172A]">Match-by-Match HPC Contribution</h3>
            <p class="text-[11px] text-[#64748B] mb-3">Individual innings contribution (blue = positive, pink = negative; DNB matches excluded from chart bars)</p>
            <div class="relative h-60 w-full">
              <canvas id="chart-bp-match-hpc" aria-label="Match-by-Match Contribution Bar Chart" role="img"></canvas>
            </div>
          </div>
        </section>

        <!-- SECTION 4: MATCH BREAKDOWN & INSPECTOR -->
        <section class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-4" aria-label="Match Breakdown">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#F1F5F9] pb-3">
            <div>
              <h2 class="text-sm font-black uppercase tracking-wider text-[#0F172A] flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-[#EC4899]"></span>
                4. Match-by-Match Breakdown
              </h2>
              <p class="text-xs text-[#64748B] mt-0.5">Select any match row to inspect the batter's contribution card or launch its Win Probability Worm Graph.</p>
            </div>
            <div class="flex items-center gap-3">
              <label class="inline-flex items-center gap-2 text-xs font-semibold text-[#334155] cursor-pointer">
                <input id="bp-show-dnb" type="checkbox" ${this.showDnb ? 'checked' : ''} class="rounded border-[#CBD5E1] text-[#EC4899]">
                <span>Show Not Batted (DNB: ${summary.dnb_count})</span>
              </label>
            </div>
          </div>

          <!-- Selected Match Contribution Inspector -->
          ${activeMatch ? this._renderSelectedMatchInspector(activeMatch) : ''}

          <!-- Match Log Table -->
          <div class="table-wrapper rounded-xl border border-[#E2E8F0]" tabindex="0" role="region" aria-label="Batter Match Log Table">
            <table class="text-xs text-left">
              <caption class="visually-hidden">Chronological match-by-match batting contribution log for ${escapeHtml(summary.batter_name)}</caption>
              <thead class="bg-[#F8FAFC] text-[10px] font-bold uppercase tracking-wider text-[#64748B] border-b border-[#E2E8F0]">
                <tr>
                  <th scope="col" class="py-2.5 px-3">Date</th>
                  <th scope="col" class="py-2.5 px-3">Tournament</th>
                  <th scope="col" class="py-2.5 px-3">Fixture</th>
                  <th scope="col" class="py-2.5 px-3 text-center">Inn</th>
                  <th scope="col" class="py-2.5 px-3 text-right">Runs (Balls)</th>
                  <th scope="col" class="py-2.5 px-3 text-center">4s / 6s</th>
                  <th scope="col" class="py-2.5 px-3 text-right">Exp Runs</th>
                  <th scope="col" class="py-2.5 px-3 text-right">RAE</th>
                  <th scope="col" class="py-2.5 px-3 text-right">Mean P</th>
                  <th scope="col" class="py-2.5 px-3 text-center">Tier</th>
                  <th scope="col" class="py-2.5 px-3 text-center">Status</th>
                  <th scope="col" class="py-2.5 px-3 text-right">HPC</th>
                  <th scope="col" class="py-2.5 px-3 text-center">Worm</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[#F1F5F9]">
                ${visibleLog.slice().reverse().map((m) => {
                  const origIdx = match_log.indexOf(m);
                  const isSel = origIdx === this.selectedMatchIdx;
                  if (m.is_dnb) {
                    return `
                      <tr data-match-idx="${origIdx}" class="cursor-pointer transition ${isSel ? 'bg-[#EFF6FF]' : 'bg-[#F8FAFC]/70 hover:bg-[#F1F5F9]'}">
                        <td class="py-2.5 px-3 font-mono text-[#64748B] whitespace-nowrap">${escapeHtml(m.date || '—')}</td>
                        <td class="py-2.5 px-3 text-[#475569] max-w-[180px] truncate">${escapeHtml(m.comp_name)}</td>
                        <th scope="row" class="py-2.5 px-3 font-semibold text-[#334155] whitespace-nowrap">${escapeHtml(m.teams)}</th>
                        <td class="py-2.5 px-3 text-center font-mono text-[#64748B]">Inn ${m.inn}</td>
                        <td class="py-2.5 px-3 text-right font-semibold text-[#64748B] italic">Not Batted</td>
                        <td class="py-2.5 px-3 text-center text-[#94A3B8]">—</td>
                        <td class="py-2.5 px-3 text-right text-[#94A3B8]">—</td>
                        <td class="py-2.5 px-3 text-right text-[#94A3B8]">—</td>
                        <td class="py-2.5 px-3 text-right text-[#94A3B8]">—</td>
                        <td class="py-2.5 px-3 text-center">${getPressureTierBadge('DNB')}</td>
                        <td class="py-2.5 px-3 text-center text-[#64748B] font-semibold">Not Batted</td>
                        <td class="py-2.5 px-3 text-right font-mono text-[#94A3B8]">—</td>
                        <td class="py-2.5 px-3 text-center">
                          <a href="#/batting/worm_graph?match=${encodeURIComponent(m.match_id)}" class="text-[#2563EB] hover:text-[#1E3A8A] font-bold text-[11px]" onclick="event.stopPropagation()">View &rarr;</a>
                        </td>
                      </tr>
                    `;
                  }
                  return `
                    <tr data-match-idx="${origIdx}" class="cursor-pointer transition ${isSel ? 'bg-[#EFF6FF]' : 'hover:bg-[#F8FAFC]'}">
                      <td class="py-2.5 px-3 font-mono text-[#64748B] whitespace-nowrap">${escapeHtml(m.date || '—')}</td>
                      <td class="py-2.5 px-3 text-[#3B82F6] font-medium max-w-[180px] truncate">${escapeHtml(m.comp_name)}</td>
                      <th scope="row" class="py-2.5 px-3 font-semibold text-[#0F172A] whitespace-nowrap">${escapeHtml(m.teams)}</th>
                      <td class="py-2.5 px-3 text-center font-mono text-[#475569]">Inn ${m.inn}</td>
                      <td class="py-2.5 px-3 text-right font-mono font-bold text-[#0F172A] whitespace-nowrap">${m.runs} <span class="text-[#64748B] font-normal">(${m.balls})</span></td>
                      <td class="py-2.5 px-3 text-center font-mono text-[#475569]">${m.fours} / ${m.sixes}</td>
                      <td class="py-2.5 px-3 text-right font-mono text-[#64748B]">${m.exp_runs !== null ? m.exp_runs.toFixed(1) : '—'}</td>
                      <td class="py-2.5 px-3 text-right font-mono font-semibold ${getSignedColorClass(m.rae)}">${formatSigned(m.rae, 2)}</td>
                      <td class="py-2.5 px-3 text-right font-mono text-[#1E3A8A]">${m.mean_p !== null ? m.mean_p.toFixed(1) : '—'}</td>
                      <td class="py-2.5 px-3 text-center">${getPressureTierBadge(m.tier)}</td>
                      <td class="py-2.5 px-3 text-center text-[#64748B] whitespace-nowrap">${m.is_out ? escapeHtml(m.dismissal_type || 'Out') : 'Not Out'}</td>
                      <td class="py-2.5 px-3 text-right font-mono font-black ${getSignedColorClass(m.hpc)}">${formatSigned(m.hpc, 2)}</td>
                      <td class="py-2.5 px-3 text-center">
                        <a href="#/batting/worm_graph?match=${encodeURIComponent(m.match_id)}" class="text-[#2563EB] hover:text-[#1E3A8A] font-bold text-[11px]" onclick="event.stopPropagation()">View &rarr;</a>
                      </td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        </section>

        ${renderBattingMetricExplainer({ compact: true })}
      </div>
    `;

    this.bindEvents();
    this.renderCharts(season_breakdown, match_log);
  }

  _miniStat(label, value, colorClass, tone) {
    const borderTone = tone === 'pink' ? 'border-t-[#EC4899]' : (tone === 'blue' ? 'border-t-[#3B82F6]' : 'border-t-[#CBD5E1]');
    return `
      <div class="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] border-t-2 ${borderTone}">
        <div class="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">${label}</div>
        <div class="text-base font-black mt-1 ${colorClass} truncate">${value}</div>
      </div>
    `;
  }

  _renderSelectedMatchInspector(m) {
    if (m.is_dnb) {
      return `
        <div class="p-4 rounded-xl bg-[#F8FAFC] border border-dashed border-[#94A3B8] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div class="flex items-center gap-2 mb-1">
              ${getPressureTierBadge('DNB')}
              <span class="text-xs font-bold text-[#0F172A]">${escapeHtml(m.teams)} (${escapeHtml(m.date)})</span>
            </div>
            <p class="text-xs text-[#64748B]">
              <strong>Not Batted:</strong> Did not face a delivery in ${escapeHtml(m.comp_name)}. Explicitly excluded from runs, average, pressure, and HPC calculations.
            </p>
          </div>
          <a href="#/batting/worm_graph?match=${encodeURIComponent(m.match_id)}" class="px-3.5 py-2 rounded-xl bg-[#1E3A8A] text-white text-xs font-bold hover:bg-[#1E40AF] whitespace-nowrap transition">
            Inspect Match Worm &rarr;
          </a>
        </div>
      `;
    }

    return `
      <div class="p-4 rounded-xl bg-gradient-to-r from-[#EFF6FF] to-[#FDF2F8] border border-[#BFDBFE] flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div class="space-y-1">
          <div class="flex flex-wrap items-center gap-2">
            <span class="badge-blue">${escapeHtml(m.comp_name)}</span>
            ${getPressureTierBadge(m.tier)}
            <span class="text-xs font-mono text-[#64748B]">${escapeHtml(m.date)} &bull; Inn ${m.inn}</span>
          </div>
          <div class="text-sm font-black text-[#0F172A]">${escapeHtml(m.teams)} <span class="font-medium text-xs text-[#64748B]">(${escapeHtml(m.result || m.venue)})</span></div>
        </div>
        <div class="flex flex-wrap items-center gap-4 text-xs">
          <div><span class="text-[10px] uppercase font-bold text-[#64748B] block">Score</span><strong class="text-[#0F172A]">${m.runs} (${m.balls}b)</strong></div>
          <div><span class="text-[10px] uppercase font-bold text-[#64748B] block">Expected</span><strong class="text-[#475569]">${m.exp_runs !== null ? m.exp_runs.toFixed(1) : '—'}</strong></div>
          <div><span class="text-[10px] uppercase font-bold text-[#64748B] block">RAE</span><strong class="${getSignedColorClass(m.rae)}">${formatSigned(m.rae, 2)}</strong></div>
          <div><span class="text-[10px] uppercase font-bold text-[#64748B] block">Pressure</span><strong class="text-[#1E3A8A]">${m.mean_p !== null ? m.mean_p.toFixed(1) : '—'} (Peak ${m.peak_p !== null ? m.peak_p.toFixed(0) : '—'})</strong></div>
          <div><span class="text-[10px] uppercase font-bold text-[#64748B] block">HPC</span><strong class="text-sm font-black ${getSignedColorClass(m.hpc)}">${formatSigned(m.hpc, 2)}</strong></div>
          <a href="#/batting/worm_graph?match=${encodeURIComponent(m.match_id)}" class="px-3.5 py-2 rounded-xl bg-[#1E3A8A] text-white text-xs font-bold hover:bg-[#1E40AF] transition">
            Open Worm Graph &rarr;
          </a>
        </div>
      </div>
    `;
  }

  bindEvents() {
    const pSel = document.getElementById('bp-player-select');
    if (pSel) {
      pSel.addEventListener('change', (e) => {
        window.location.hash = `#/batting/players/${encodeURIComponent(e.target.value)}`;
      });
    }

    const sSel = document.getElementById('bp-season-select');
    if (sSel) {
      sSel.addEventListener('change', (e) => {
        this.state.season = e.target.value;
        this.reloadScoped();
      });
    }

    const tSel = document.getElementById('bp-tourney-select');
    if (tSel) {
      tSel.addEventListener('change', (e) => {
        this.state.tournament = e.target.value;
        this.reloadScoped();
      });
    }

    const dnbChk = document.getElementById('bp-show-dnb');
    if (dnbChk) {
      dnbChk.addEventListener('change', (e) => {
        this.showDnb = e.target.checked;
        this.renderContent();
      });
    }

    document.querySelectorAll('[data-match-idx]').forEach((tr) => {
      tr.addEventListener('click', () => {
        this.selectedMatchIdx = parseInt(tr.dataset.matchIdx, 10);
        this.renderContent();
      });
    });
  }

  renderCharts(seasonBreakdown, matchLog) {
    if (typeof Chart === 'undefined') return;
    const batted = matchLog.filter((m) => !m.is_dnb);
    if (!batted.length) return;

    // 1. Career Cumulative HPC Graph
    const cumCtx = document.getElementById('chart-bp-career-cum');
    if (cumCtx) {
      this.charts.cum = new Chart(cumCtx, {
        type: 'line',
        data: {
          labels: batted.map((m, idx) => `#${idx + 1} (${m.date.slice(2, 7)})`),
          datasets: [{
            label: 'Cumulative HPC',
            data: batted.map((m) => m.cumulative_hpc),
            borderColor: '#1E3A8A',
            backgroundColor: 'rgba(59, 130, 246, 0.12)',
            fill: true,
            tension: 0.25,
            pointRadius: batted.length > 50 ? 1.5 : 3,
            borderWidth: 2.5,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { maxTicksLimit: 8, color: '#64748B', font: { size: 10 } }, grid: { display: false } },
            y: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B', font: { size: 10 } } },
          },
        },
      });
    }

    // 2. Season-Wise HPC Trend
    const sCtx = document.getElementById('chart-bp-season-trend');
    if (sCtx) {
      this.charts.season = new Chart(sCtx, {
        type: 'bar',
        data: {
          labels: seasonBreakdown.map((s) => s.season),
          datasets: [
            {
              label: 'Total HPC',
              data: seasonBreakdown.map((s) => s.total_hpc ?? 0),
              backgroundColor: seasonBreakdown.map((s) => ((s.total_hpc ?? 0) >= 0 ? '#3B82F6' : '#EC4899')),
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                afterLabel: (ctx) => {
                  const s = seasonBreakdown[ctx.dataIndex];
                  return `Mean HPC: ${formatSigned(s.mean_hpc, 2)} | Runs: ${s.actual_runs} (${s.innings_batted} inns)`;
                },
              },
            },
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 11 } } },
            y: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B', font: { size: 10 } } },
          },
        },
      });
    }

    // 3. Runs vs Expected Runs (Latest 30 batted stints)
    const reCtx = document.getElementById('chart-bp-runs-exp');
    if (reCtx) {
      const recent = batted.slice(-30);
      this.charts.runsExp = new Chart(reCtx, {
        type: 'bar',
        data: {
          labels: recent.map((m) => m.date.slice(5)),
          datasets: [
            { label: 'Actual Runs', data: recent.map((m) => m.runs), backgroundColor: '#3B82F6', borderRadius: 4 },
            { label: 'Expected Runs', data: recent.map((m) => m.exp_runs), backgroundColor: '#CBD5E1', borderRadius: 4 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } } },
          scales: {
            x: { grid: { display: false }, ticks: { maxTicksLimit: 10, color: '#64748B', font: { size: 9 } } },
            y: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B', font: { size: 10 } } },
          },
        },
      });
    }

    // 4. Pressure vs Contribution Scatter
    const pCtx = document.getElementById('chart-bp-pressure-hpc');
    if (pCtx) {
      const pts = batted.map((m) => ({
        x: m.mean_p,
        y: m.hpc,
        tier: m.tier,
        label: `${m.date} vs ${m.opponent} (${m.runs} off ${m.balls})`,
      }));
      this.charts.pressure = new Chart(pCtx, {
        type: 'scatter',
        data: {
          datasets: [{
            label: 'Innings',
            data: pts,
            backgroundColor: pts.map((pt) => {
              if (pt.tier === 'Extreme') return '#EC4899';
              if (pt.tier === 'High') return '#D97706';
              if (pt.tier === 'Medium') return '#3B82F6';
              return '#64748B';
            }),
            pointRadius: 4.5,
            pointHoverRadius: 6.5,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.raw.label}: P=${ctx.raw.x}, HPC=${formatSigned(ctx.raw.y, 2)}`,
              },
            },
          },
          scales: {
            x: { min: 0, max: 100, title: { display: true, text: 'Mean Pressure (0–100)', font: { size: 10 }, color: '#64748B' }, grid: { color: '#F1F5F9' } },
            y: { title: { display: true, text: 'Innings HPC', font: { size: 10 }, color: '#64748B' }, grid: { color: '#F1F5F9' } },
          },
        },
      });
    }

    // 5. Match-by-Match Contribution Bar Chart
    const mCtx = document.getElementById('chart-bp-match-hpc');
    if (mCtx) {
      this.charts.matchBar = new Chart(mCtx, {
        type: 'bar',
        data: {
          labels: batted.map((m, idx) => `#${idx + 1} ${m.date.slice(2)}`),
          datasets: [{
            label: 'Innings HPC',
            data: batted.map((m) => m.hpc),
            backgroundColor: batted.map((m) => ((m.hpc ?? 0) >= 0 ? '#3B82F6' : '#EC4899')),
            borderRadius: 3,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const m = batted[ctx.dataIndex];
                  return `${m.teams}: ${m.runs}(${m.balls}) | HPC ${formatSigned(m.hpc, 2)} | RAE ${formatSigned(m.rae, 2)}`;
                },
              },
            },
          },
          scales: {
            x: { ticks: { maxTicksLimit: 12, color: '#64748B', font: { size: 9 } }, grid: { display: false } },
            y: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B', font: { size: 10 } } },
          },
        },
      });
    }
  }
}

const instance = new BatterProfile();
export function renderBatterProfile(container, params) {
  return instance.render(container, params);
}
