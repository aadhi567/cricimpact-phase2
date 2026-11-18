/**
 * CricImpact Phase 2 — Modernized Head-to-Head Batter Comparison Page
 * Stage B9: Compare 2–5 batters across Runs, Avg, SR, HPC, RAE, Positive %,
 * Pressure Performance, Career Trends, Season Splits, and Shared Matches.
 * Strictly preserves existing HPP/HPC metrics with NO new combined batting score.
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

const PALETTE = ['#EC4899', '#3B82F6', '#1E3A8A', '#16A34A', '#D97706'];

export class BatterComparison {
  constructor() {
    this.container = null;
    this.allPlayers = null;
    this.filtersMeta = null;
    this.data = null;
    this.charts = {};
    this.selected = ['Abhishek Sharma', 'Suryakumar Yadav', 'Virat Kohli'];
    this.scope = { season: 'all', tournament: 'all' };
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

    if (params && params.players) {
      const parsed = String(params.players)
        .split(',')
        .map((s) => decodeURIComponent(s.trim()))
        .filter(Boolean);
      if (parsed.length >= 2) {
        this.selected = Array.from(new Set(parsed)).slice(0, 5);
      }
    }

    container.innerHTML = renderLoadingSkeleton('Loading Head-to-Head Batter Comparison...');

    try {
      const [playersRes, meta, cmpRes] = await Promise.all([
        this.allPlayers ? Promise.resolve({ players: this.allPlayers }) : battingApiService.getPlayers(),
        this.filtersMeta ? Promise.resolve(this.filtersMeta) : battingApiService.getFilters(),
        battingApiService.comparePlayers(this.selected, this.scope),
      ]);
      this.allPlayers = playersRes.players;
      this.filtersMeta = meta;
      this.data = cmpRes;
      this.selected = cmpRes.players.map((p) => p.batter_name);
      this.renderContent();
    } catch (err) {
      container.innerHTML = renderErrorState(
        `Failed to load Batter Comparison: ${err.message}`,
        'window.location.reload()'
      );
    }
  }

  async refreshComparison() {
    if (this.selected.length < 2) return;
    try {
      this.data = await battingApiService.comparePlayers(this.selected, this.scope);
      this.renderContent();
    } catch (err) {
      this.container.innerHTML = renderErrorState(
        `Comparison update failed: ${err.message}`,
        'window.location.reload()'
      );
    }
  }

  renderContent() {
    this.destroyCharts();
    const { players, seasons, common_matches, total_common_matches } = this.data;
    const meta = this.filtersMeta;

    const addableOptions = (this.allPlayers || [])
      .filter((p) => !this.selected.includes(p.batter_name))
      .map((p) => `<option value="${escapeHtml(p.batter_name)}">${escapeHtml(p.batter_name)} (${p.actual_runs} runs, ${p.innings_batted} inns)</option>`)
      .join('');

    const seasonOpts = [
      `<option value="all" ${this.scope.season === 'all' ? 'selected' : ''}>All Seasons</option>`,
      ...meta.seasons.slice().reverse().map((s) => `<option value="${escapeHtml(s)}" ${this.scope.season === s ? 'selected' : ''}>Season ${escapeHtml(s)}</option>`),
    ].join('');

    const tourneyOpts = [
      `<option value="all" ${this.scope.tournament === 'all' ? 'selected' : ''}>All Tournaments</option>`,
      ...meta.tournaments.map((t) => `<option value="${escapeHtml(t.comp_name)}" ${this.scope.tournament === t.comp_name ? 'selected' : ''}>${escapeHtml(t.comp_name)}</option>`),
    ].join('');

    this.container.innerHTML = `
      <div class="space-y-6 animate-fade-in">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E2E8F0]">
          <div>
            <div class="flex items-center gap-2 text-[11px] font-black uppercase tracking-wider text-[#3B82F6] mb-1">
              <span>Batting Analytics</span>
              <span>&bull;</span>
              <span class="text-[#EC4899]">Head-to-Head Comparison</span>
            </div>
            <h1 id="page-main-heading" tabindex="-1" class="hero-title-fluid font-black text-[#0F172A] tracking-tight">
              Batter Comparison Studio
            </h1>
            <p class="text-xs text-[#64748B] mt-1">
              Compare 2–5 batters side-by-side across Runs, Average, Strike Rate, HPC, RAE, Pressure Performance, and Shared Matches.
            </p>
          </div>
          <a href="#/batting/explorer" class="px-3.5 py-2 rounded-xl bg-white border border-[#E2E8F0] text-xs font-bold text-[#334155] hover:border-[#3B82F6] transition self-start md:self-auto">
            &larr; HPP Explorer
          </a>
        </div>

        <!-- Selector & Scope Bar -->
        <section class="bg-white border border-[#E2E8F0] rounded-2xl p-4 sm:p-5 shadow-sm space-y-4" aria-label="Comparison Controls">
          <div class="flex flex-wrap items-center gap-2">
            ${players.map((p, idx) => `
              <span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold text-white shadow-xs" style="background-color: ${PALETTE[idx % PALETTE.length]}">
                <a href="#/batting/players/${encodeURIComponent(p.batter_name)}" class="text-white hover:underline">${escapeHtml(p.batter_name)}</a>
                ${players.length > 2 ? `<button type="button" data-remove-batter="${escapeHtml(p.batter_name)}" aria-label="Remove ${escapeHtml(p.batter_name)}" class="ml-1 text-white/80 hover:text-white font-black">&times;</button>` : ''}
              </span>
            `).join('')}
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-[#F1F5F9]">
            <div>
              <label for="cmp-add-batter" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Add Batter (Max 5)</label>
              <select id="cmp-add-batter" ${this.selected.length >= 5 ? 'disabled' : ''} class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A] disabled:opacity-50">
                <option value="">+ Select a batter to add...</option>
                ${addableOptions}
              </select>
            </div>
            <div>
              <label for="cmp-season" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Season Scope</label>
              <select id="cmp-season" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${seasonOpts}
              </select>
            </div>
            <div>
              <label for="cmp-tourney" class="block text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Tournament Scope</label>
              <select id="cmp-tourney" class="w-full px-3 py-2 text-xs font-semibold bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A]">
                ${tourneyOpts}
              </select>
            </div>
          </div>
        </section>

        <!-- Side-by-Side Metrics Matrix -->
        <section class="bg-white border border-[#E2E8F0] rounded-2xl shadow-sm overflow-hidden" aria-label="Comparison Table">
          <div class="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between">
            <h2 class="text-sm font-black text-[#0F172A]">Side-by-Side Metric Breakdown</h2>
            <span class="text-[11px] text-[#64748B]">Validated HPP metrics &bull; DNB excluded from averages</span>
          </div>
          <div class="table-wrapper" tabindex="0" role="region" aria-label="Batter Comparison Matrix">
            <table class="text-xs text-left">
              <caption class="visually-hidden">Head-to-head batting metric comparison</caption>
              <thead class="bg-[#F8FAFC] text-[10px] font-bold uppercase tracking-wider text-[#64748B] border-b border-[#E2E8F0]">
                <tr>
                  <th scope="col" class="py-3 px-4">Metric</th>
                  ${players.map((p, idx) => `
                    <th scope="col" class="py-3 px-4 text-right whitespace-nowrap">
                      <span class="inline-block w-2 h-2 rounded-full mr-1.5" style="background-color: ${PALETTE[idx % PALETTE.length]}"></span>
                      <a href="#/batting/players/${encodeURIComponent(p.batter_name)}" class="text-[#0F172A] hover:text-[#DB2777]">${escapeHtml(p.batter_name)}</a>
                    </th>
                  `).join('')}
                </tr>
              </thead>
              <tbody class="divide-y divide-[#F1F5F9]">
                ${this._renderMetricRow('Matches / Innings (DNB)', players, (s) => `${s.total_matches} / ${s.innings_batted}${s.dnb_count > 0 ? ` (${s.dnb_count} DNB)` : ''}`)}
                ${this._renderMetricRow('Total Runs', players, (s) => formatNumber(s.actual_runs), 'font-black text-[#0F172A]')}
                ${this._renderMetricRow('Batting Average', players, (s) => s.batting_average !== null ? s.batting_average.toFixed(2) : '—')}
                ${this._renderMetricRow('Strike Rate', players, (s) => s.strike_rate !== null ? s.strike_rate.toFixed(1) : '—')}
                ${this._renderMetricRow('Balls Faced (4s / 6s)', players, (s) => `${formatNumber(s.balls_faced)} (${s.fours}/${s.sixes})`)}
                ${this._renderMetricRow('Expected Runs', players, (s) => s.expected_runs !== null ? s.expected_runs.toFixed(1) : '—')}
                ${this._renderMetricRow('Total RAE', players, (s) => formatSigned(s.total_rae, 2), '', (s) => getSignedColorClass(s.total_rae))}
                ${this._renderMetricRow('Total HPC', players, (s) => formatSigned(s.total_hpc, 2), 'font-black', (s) => getSignedColorClass(s.total_hpc))}
                ${this._renderMetricRow('Average HPC / Inn', players, (s) => formatSigned(s.mean_hpc, 2), 'font-bold', (s) => getSignedColorClass(s.mean_hpc))}
                ${this._renderMetricRow('Positive Contribution %', players, (s) => s.positive_contribution_pct !== null ? `${s.positive_contribution_pct.toFixed(1)}%` : '—', 'font-bold text-[#1E3A8A]')}
                ${this._renderMetricRow('Avg Pressure Faced', players, (s) => s.avg_pressure_faced !== null ? `${s.avg_pressure_faced.toFixed(2)} / 100` : '—')}
                ${this._renderMetricRow('Crisis HPC (High + Ext)', players, (s) => formatSigned(s.crisis_total_hpc, 2), 'font-bold', (s) => getSignedColorClass(s.crisis_total_hpc))}
              </tbody>
            </table>
          </div>
        </section>

        <!-- Visual Comparison Charts Grid -->
        <section class="grid grid-cols-1 lg:grid-cols-2 gap-5" aria-label="Comparison Visualizations">
          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
            <h3 class="text-sm font-black text-[#0F172A]">Contribution Comparison (HPC, RAE &amp; Crisis)</h3>
            <p class="text-[11px] text-[#64748B] mb-3">Side-by-side total contribution metrics</p>
            <div class="relative h-64 w-full">
              <canvas id="chart-cmp-bars" aria-label="Contribution Bar Chart" role="img"></canvas>
            </div>
          </div>

          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
            <h3 class="text-sm font-black text-[#0F172A]">Career Cumulative HPC Trend</h3>
            <p class="text-[11px] text-[#64748B] mb-3">Cumulative batting contribution over career batted innings</p>
            <div class="relative h-64 w-full">
              <canvas id="chart-cmp-career" aria-label="Career Cumulative HPC Comparison Chart" role="img"></canvas>
            </div>
          </div>

          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
            <h3 class="text-sm font-black text-[#0F172A]">Season-by-Season Total HPC</h3>
            <p class="text-[11px] text-[#64748B] mb-3">Year-over-year contribution comparison across ${seasons.join(', ') || 'available seasons'}</p>
            <div class="relative h-64 w-full">
              <canvas id="chart-cmp-seasons" aria-label="Season Comparison Chart" role="img"></canvas>
            </div>
          </div>

          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm">
            <h3 class="text-sm font-black text-[#0F172A]">Pressure Tier Performance</h3>
            <p class="text-[11px] text-[#64748B] mb-3">Total HPC across Low, Medium, High &amp; Extreme match pressure</p>
            <div class="relative h-64 w-full">
              <canvas id="chart-cmp-pressure" aria-label="Pressure Tier Comparison Chart" role="img"></canvas>
            </div>
          </div>
        </section>

        <!-- Match-Level Head-to-Head Shared Matches -->
        <section class="bg-white border border-[#E2E8F0] rounded-2xl shadow-sm overflow-hidden" aria-label="Shared Match Comparison">
          <div class="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 class="text-sm font-black text-[#0F172A]">Shared Match-Level Comparison</h2>
              <p class="text-[11px] text-[#64748B]">Matches where at least two selected batters featured together (${total_common_matches} found)</p>
            </div>
          </div>

          ${common_matches.length === 0 ? `
            <div class="p-8 text-center text-xs text-[#64748B]">No shared matches found among these batters in the current filter scope.</div>
          ` : `
            <div class="table-wrapper" tabindex="0" role="region" aria-label="Shared Matches Comparison Table">
              <table class="text-xs text-left">
                <caption class="visually-hidden">Match-level comparison of shared appearances</caption>
                <thead class="bg-[#F8FAFC] text-[10px] font-bold uppercase tracking-wider text-[#64748B] border-b border-[#E2E8F0]">
                  <tr>
                    <th scope="col" class="py-2.5 px-3">Date</th>
                    <th scope="col" class="py-2.5 px-3">Match</th>
                    ${players.map((p) => `<th scope="col" class="py-2.5 px-3 text-center">${escapeHtml(p.batter_name)}</th>`).join('')}
                    <th scope="col" class="py-2.5 px-3 text-center">Worm</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-[#F1F5F9]">
                  ${common_matches.map((m) => `
                    <tr class="hover:bg-[#F8FAFC] transition">
                      <td class="py-2.5 px-3 font-mono text-[#64748B] whitespace-nowrap">${escapeHtml(m.date)}</td>
                      <th scope="row" class="py-2.5 px-3 font-semibold text-[#0F172A]">
                        <div>${escapeHtml(m.teams)}</div>
                        <div class="text-[10px] text-[#64748B] font-normal">${escapeHtml(m.comp_name)}</div>
                      </th>
                      ${players.map((p) => {
                        const st = m.players[p.batter_name];
                        if (!st) return `<td class="py-2.5 px-3 text-center text-[#CBD5E1]">—</td>`;
                        if (st.is_dnb) return `<td class="py-2.5 px-3 text-center">${getPressureTierBadge('DNB')}</td>`;
                        return `
                          <td class="py-2.5 px-3 text-center whitespace-nowrap">
                            <div class="font-mono font-bold text-[#0F172A]">${st.runs} <span class="text-[#64748B] font-normal">(${st.balls})</span></div>
                            <div class="font-mono text-[11px] font-black ${getSignedColorClass(st.hpc)}">HPC ${formatSigned(st.hpc, 1)}</div>
                          </td>
                        `;
                      }).join('')}
                      <td class="py-2.5 px-3 text-center">
                        <a href="#/batting/worm_graph?match=${encodeURIComponent(m.match_id)}" class="text-[#2563EB] hover:text-[#1E3A8A] font-bold text-[11px]">Worm &rarr;</a>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `}
        </section>

        ${renderBattingMetricExplainer({ compact: true })}
      </div>
    `;

    this.bindEvents();
    this.renderCharts(players, seasons);
  }

  _renderMetricRow(label, players, formatter, baseClass = '', dynamicClassFn = null) {
    return `
      <tr class="hover:bg-[#F8FAFC]">
        <th scope="row" class="py-2.5 px-4 font-bold text-[#334155] whitespace-nowrap">${label}</th>
        ${players.map((p) => {
          const dyn = dynamicClassFn ? dynamicClassFn(p.summary) : '';
          return `<td class="py-2.5 px-4 text-right font-mono ${baseClass} ${dyn} whitespace-nowrap">${formatter(p.summary)}</td>`;
        }).join('')}
      </tr>
    `;
  }

  bindEvents() {
    document.querySelectorAll('[data-remove-batter]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const name = btn.dataset.removeBatter;
        this.selected = this.selected.filter((n) => n !== name);
        this.refreshComparison();
      });
    });

    const addSel = document.getElementById('cmp-add-batter');
    if (addSel) {
      addSel.addEventListener('change', (e) => {
        const val = e.target.value;
        if (val && !this.selected.includes(val) && this.selected.length < 5) {
          this.selected.push(val);
          this.refreshComparison();
        }
      });
    }

    const sSel = document.getElementById('cmp-season');
    if (sSel) {
      sSel.addEventListener('change', (e) => {
        this.scope.season = e.target.value;
        this.refreshComparison();
      });
    }

    const tSel = document.getElementById('cmp-tourney');
    if (tSel) {
      tSel.addEventListener('change', (e) => {
        this.scope.tournament = e.target.value;
        this.refreshComparison();
      });
    }
  }

  renderCharts(players, seasons) {
    if (typeof Chart === 'undefined') return;

    // 1. Contribution Bar Chart
    const barCtx = document.getElementById('chart-cmp-bars');
    if (barCtx) {
      this.charts.bars = new Chart(barCtx, {
        type: 'bar',
        data: {
          labels: ['Total HPC', 'Total RAE', 'Crisis HPC'],
          datasets: players.map((p, idx) => ({
            label: p.batter_name,
            data: [p.summary.total_hpc ?? 0, p.summary.total_rae ?? 0, p.summary.crisis_total_hpc ?? 0],
            backgroundColor: PALETTE[idx % PALETTE.length],
            borderRadius: 6,
          })),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } } },
          scales: {
            x: { grid: { display: false } },
            y: { grid: { color: '#F1F5F9' }, ticks: { font: { size: 10 }, color: '#64748B' } },
          },
        },
      });
    }

    // 2. Career Cumulative HPC Trend
    const carCtx = document.getElementById('chart-cmp-career');
    if (carCtx) {
      const maxLen = Math.max(...players.map((p) => p.cumulative_trend.length), 1);
      const xLabels = Array.from({ length: maxLen }, (_, i) => `Inn ${i + 1}`);
      this.charts.career = new Chart(carCtx, {
        type: 'line',
        data: {
          labels: xLabels,
          datasets: players.map((p, idx) => ({
            label: p.batter_name,
            data: p.cumulative_trend.map((pt) => pt.cumulative_hpc),
            borderColor: PALETTE[idx % PALETTE.length],
            backgroundColor: 'transparent',
            borderWidth: 2.5,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.25,
          })),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } } },
          scales: {
            x: { ticks: { maxTicksLimit: 8, color: '#64748B', font: { size: 10 } }, grid: { display: false } },
            y: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B', font: { size: 10 } } },
          },
        },
      });
    }

    // 3. Season-by-Season HPC Comparison
    const seaCtx = document.getElementById('chart-cmp-seasons');
    if (seaCtx) {
      this.charts.seasons = new Chart(seaCtx, {
        type: 'bar',
        data: {
          labels: seasons,
          datasets: players.map((p, idx) => {
            const byYr = Object.fromEntries(p.season_breakdown.map((sb) => [sb.season, sb.total_hpc ?? 0]));
            return {
              label: p.batter_name,
              data: seasons.map((yr) => byYr[yr] ?? 0),
              backgroundColor: PALETTE[idx % PALETTE.length],
              borderRadius: 5,
            };
          }),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } } },
          scales: {
            x: { grid: { display: false } },
            y: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B', font: { size: 10 } } },
          },
        },
      });
    }

    // 4. Pressure Tier Performance
    const prCtx = document.getElementById('chart-cmp-pressure');
    if (prCtx) {
      const tiers = ['Low', 'Medium', 'High', 'Extreme'];
      this.charts.pressure = new Chart(prCtx, {
        type: 'bar',
        data: {
          labels: tiers,
          datasets: players.map((p, idx) => {
            const byT = Object.fromEntries(p.by_pressure_tier.map((t) => [t.tier, t.total_hpc ?? 0]));
            return {
              label: p.batter_name,
              data: tiers.map((t) => byT[t] ?? 0),
              backgroundColor: PALETTE[idx % PALETTE.length],
              borderRadius: 5,
            };
          }),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } } },
          scales: {
            x: { grid: { display: false } },
            y: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B', font: { size: 10 } } },
          },
        },
      });
    }
  }
}

const instance = new BatterComparison();
export function renderBatterComparison(container, params) {
  return instance.render(container, params);
}
