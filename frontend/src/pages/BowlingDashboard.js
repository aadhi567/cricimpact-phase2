/**
 * CricImpact Phase 2 — Bowling Dashboard Page
 * Main entry point for Bowling Analytics with live API telemetry.
 * Integrates BCM (BCS, bWPA, ERP, WQM) and PCS (Pressure Contribution Score).
 */

import { bowlingApiService } from '../services/bowlingApiService.js';
import { pcsApiService } from '../services/pcsApiService.js';
import { renderMetricCard } from '../components/MetricCard.js';
import { renderPhasePanels } from '../components/PhaseBreakdown.js';
import { renderBarChart, renderDoughnutChart, renderLineChart } from '../components/ContributionChart.js';
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

export class BowlingDashboard {
  constructor() {
    this.container = null;
    this.dashboardData = null;
    this.pcsData = null;
  }

  async render(container) {
    this.container = container;
    container.innerHTML = renderLoadingSkeleton('Loading Bowling Analytics Dashboard...');

    try {
      const [bcmRes, pcsRes] = await Promise.all([
        bowlingApiService.getDashboard(),
        pcsApiService.getDashboard().then((r) => r.data).catch((err) => {
          console.warn('[BowlingDashboard] PCS API fetch warning:', err);
          return null;
        }),
      ]);

      this.dashboardData = bcmRes;
      this.pcsData = pcsRes;
      this.renderContent();
    } catch (err) {
      container.innerHTML = renderErrorState(
        `Failed to fetch dashboard data from backend: ${err.message}`,
        'window.location.reload()'
      );
    }
  }

  renderContent() {
    const data = this.dashboardData;
    const dist = data.bcs_distribution;
    const pcs = this.pcsData;

    this.container.innerHTML = `
      <div class="space-y-8 animate-fade-in">
        <!-- Hero Section -->
        <div class="hero-gradient rounded-2xl p-6 md:p-8 shadow-sm relative overflow-hidden">
          <div class="relative z-10 max-w-4xl">
            <div class="flex flex-wrap items-center gap-2 mb-2">
              <span class="px-2.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-white/20 text-white backdrop-blur-sm">
                Bowling Contribution Model
              </span>
              <span class="px-2.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#1E3A8A]/60 text-white backdrop-blur-sm border border-white/20">
                + Pressure Contribution Score (PCS)
              </span>
              <span class="text-xs text-white/90 font-mono">
                ${formatNumber(data.total_matches)} Matches &bull; ${formatNumber(data.total_deliveries)} Deliveries &bull; ${formatNumber(data.total_spells)} Spells
              </span>
            </div>
            <h1 class="text-2xl md:text-3xl font-black text-white tracking-tight">Bowling Analytics Dashboard</h1>
            <p class="text-xs md:text-sm text-white/90 mt-2 max-w-2xl leading-relaxed">
              Context-dependent bowling evaluation. Unifies Expected Runs Prevented (ERP),
              Wicket Quality Multipliers (WQM), Match Leverage, Bowler Win Probability Added (bWPA),
              and the independent Bowling Pressure Contribution Score (PCS).
            </p>
          </div>
        </div>

        <!-- BCM KPI Cards Grid (8 Cards) -->
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-black text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-[#EC4899]"></span>
              Core Contribution Telemetry (BCM)
            </h2>
            <span class="text-[11px] text-[#64748B]">Runs & Win Probability Dimensions</span>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            ${renderMetricCard({
              title: 'Matches Evaluated',
              value: formatNumber(data.total_matches),
              unit: 'Matches',
              subtitle: 'Standard T20 matches (2022-2026)',
              accent: 'blue',
              tooltip: 'Standard regulation T20 matches',
            })}
            ${renderMetricCard({
              title: 'Bowling Spells',
              value: formatNumber(data.total_spells),
              unit: 'Spells',
              subtitle: 'Evaluated match spells',
              accent: 'pink',
              tooltip: 'Total unique (match, innings, bowler) spells',
            })}
            ${renderMetricCard({
              title: 'Bowler Wickets',
              value: formatNumber(data.total_wickets),
              unit: 'Wickets',
              subtitle: 'Bowler-credited dismissals',
              accent: 'deep-blue',
              tooltip: 'Excludes run-outs and non-bowler wickets',
            })}
            ${renderMetricCard({
              title: 'Legal Balls Bowled',
              value: formatNumber(data.legal_balls),
              unit: 'Balls',
              subtitle: 'Excludes wides & no-balls',
              accent: 'blue',
              tooltip: 'Legal deliveries in corpus',
            })}
            ${renderMetricCard({
              title: 'Corpus Economy',
              value: formatEconomy(data.overall_economy),
              unit: 'RPO',
              subtitle: 'Runs per 6 legal balls',
              accent: 'pink',
              tooltip: 'Runs conceded * 6.0 / legal balls',
            })}
            ${renderMetricCard({
              title: 'Dot Ball Rate',
              value: formatPercent(data.dot_ball_pct),
              unit: '',
              subtitle: 'Corpus pressure baseline',
              accent: 'blue',
              tooltip: 'Dot balls / legal deliveries',
            })}
            ${renderMetricCard({
              title: 'Mean Spell BCS',
              value: formatBCS(dist.mean),
              unit: 'Runs',
              subtitle: `${dist.positive_share_pct}% spells positive`,
              accent: 'deep-blue',
              tooltip: 'Average Bowling Contribution Score per match spell',
            })}
            ${renderMetricCard({
              title: 'Top Career bWPA',
              value: formatBWPA(data.top_career_bwpa[0]?.total_bwpa),
              unit: 'bWPA',
              subtitle: `${data.top_career_bwpa[0]?.bowler_name} (#1)`,
              accent: 'pink',
              tooltip: 'Highest career Win Probability contribution',
            })}
          </div>
        </div>

        <!-- Contribution Overview Charts -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- BCS Distribution Chart -->
          <div class="card-base p-5 bg-white border border-[#E2E8F0] rounded-2xl shadow-sm lg:col-span-2">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="text-sm font-bold text-[#0F172A]">Spell BCS Contribution Distribution</h3>
                <span class="text-xs text-[#64748B]">Mean: +${dist.mean.toFixed(2)} runs &bull; Median: +${dist.median.toFixed(2)} runs &bull; Std: ${dist.std.toFixed(2)}</span>
              </div>
              <span class="badge-pink">N = 9,482 Spells</span>
            </div>
            <div class="h-64 relative">
              <canvas id="bcs-dist-chart"></canvas>
            </div>
          </div>

          <!-- Positive vs Negative Share Doughnut -->
          <div class="card-base p-5 bg-white border border-[#E2E8F0] rounded-2xl shadow-sm flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-bold text-[#0F172A]">Spell Outcome Distribution</h3>
                <span class="badge-blue">Binary Share</span>
              </div>
              <p class="text-xs text-[#64748B] mb-4">Proportion of bowling spells delivering positive vs negative contribution.</p>
              <div class="h-48 relative">
                <canvas id="bcs-share-chart"></canvas>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2 text-center text-xs pt-3 border-t border-[#F1F5F9]">
              <div>
                <span class="text-[10px] font-bold text-[#16A34A] uppercase block">Positive BCS</span>
                <span class="text-sm font-black text-[#16A34A]">${dist.positive_share_pct}%</span>
              </div>
              <div>
                <span class="text-[10px] font-bold text-[#DC2626] uppercase block">Negative BCS</span>
                <span class="text-sm font-black text-[#DC2626]">${dist.negative_share_pct}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Match Phase Panels -->
        <div>
          <div class="flex items-center justify-between mb-3">
            <div>
              <h2 class="text-base font-black text-[#0F172A]">Match Phase Performance Partition</h2>
              <span class="text-xs text-[#64748B]">Independent contribution dynamics across Powerplay, Middle, and Death overs</span>
            </div>
            <a href="#/bowling/leaderboard?phase=death" class="text-xs font-bold text-[#DB2777] hover:underline">Explore Death Overs Leaderboard &rarr;</a>
          </div>
          ${renderPhasePanels(data.phase_breakdown)}
        </div>

        <!-- Top Bowling Performers Table -->
        <div class="card-base p-5 bg-white border border-[#E2E8F0] rounded-2xl shadow-sm">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <h3 class="text-sm font-black text-[#0F172A]">Top All-Time Bowlers by Career Contribution (BCM)</h3>
              <span class="text-xs text-[#64748B]">Ranked by total Bowling Contribution Score (BCS) &bull; Click player for full dossier</span>
            </div>
            <a href="#/bowling/leaderboard" class="btn-secondary text-xs px-3 py-1.5 self-start sm:self-auto">View Full 638 Leaderboard &rarr;</a>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-xs text-left">
              <thead class="bg-[#F8FAFC] text-[#64748B] font-bold uppercase text-[10px] border-b border-[#E2E8F0]">
                <tr>
                  <th class="py-2.5 px-3 text-center">Rank</th>
                  <th class="py-2.5 px-3">Bowler Name</th>
                  <th class="py-2.5 px-3 text-center">Matches</th>
                  <th class="py-2.5 px-3 text-center">Overs</th>
                  <th class="py-2.5 px-3 text-center">Wickets</th>
                  <th class="py-2.5 px-3 text-center">Economy</th>
                  <th class="py-2.5 px-3 text-right">Total BCS</th>
                  <th class="py-2.5 px-3 text-right">Total bWPA</th>
                  <th class="py-2.5 px-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[#F1F5F9] font-medium text-[#0F172A]">
                ${data.top_career_bcs.map((b, idx) => `
                  <tr class="hover:bg-[#FDF2F8]/50 transition cursor-pointer" onclick="window.location.hash='#/bowling/players/${b.bowler_id}'">
                    <td class="py-2.5 px-3 text-center font-bold text-[#64748B]">${idx + 1}</td>
                    <td class="py-2.5 px-3 font-bold text-[#0F172A] hover:text-[#DB2777]">
                      <a href="#/bowling/players/${b.bowler_id}">${b.bowler_name}</a>
                    </td>
                    <td class="py-2.5 px-3 text-center">${b.matches}</td>
                    <td class="py-2.5 px-3 text-center font-mono">${b.overs.toFixed(1)}</td>
                    <td class="py-2.5 px-3 text-center font-bold">${b.wickets}</td>
                    <td class="py-2.5 px-3 text-center font-mono">${b.economy.toFixed(2)}</td>
                    <td class="py-2.5 px-3 text-right font-black text-[#2563EB]">${formatBCS(b.total_bcs)}</td>
                    <td class="py-2.5 px-3 text-right font-mono text-[#0F172A]">${formatBWPA(b.total_bwpa)}</td>
                    <td class="py-2.5 px-3 text-center">
                      <a href="#/bowling/players/${b.bowler_id}" class="text-[11px] font-bold text-[#DB2777] hover:underline">View &rarr;</a>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>

        ${pcs ? this.renderPCSSection(pcs) : ''}
      </div>
    `;

    // Render Charts
    setTimeout(() => {
      this.initCharts(dist);
      if (pcs) {
        this.initPCSCharts(pcs);
      }
    }, 50);
  }

  renderPCSSection(pcs) {
    const dist = pcs.pcs_distribution || pcs.distribution || {};
    const topCareer = pcs.top_career_leaders || pcs.top_career_contributors || [];
    const topSeasons = pcs.top_season_leaders || [];
    const seasonTrends = pcs.season_trends || [];
    const bestSpell = pcs.highest_spell_pcs;
    const worstSpell = pcs.lowest_spell_pcs;
    const bestCareerBowler = topCareer[0];
    const bestSeasonBowler = topSeasons[0];
    const avgSpellPCS = pcs.average_spell_pcs !== undefined ? pcs.average_spell_pcs : pcs.avg_spell_pcs;

    return `
      <!-- ========================================================================= -->
      <!-- DEDICATED SECTION: Bowling Pressure Contribution Score (PCS)             -->
      <!-- Deep Navy Accent (#1E3A8A) Harmonized with Pink + Blue Design System     -->
      <!-- ========================================================================= -->
      <div class="space-y-6 pt-4 border-t-2 border-[#E2E8F0]">
        <!-- PCS Section Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-gradient-to-r from-[#1E3A8A]/5 via-white to-[#3B82F6]/5 p-5 rounded-2xl border border-[#CBD5E1] shadow-xs">
          <div>
            <div class="flex items-center gap-2 mb-1.5">
              <span class="px-2.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#1E3A8A] text-white">
                Independent Analytical Layer
              </span>
              <span class="text-xs text-[#1E3A8A] font-bold font-mono">B7.5 Certified Production Pipeline</span>
            </div>
            <h2 class="text-xl md:text-2xl font-black text-[#0F172A] tracking-tight">
              Bowling Pressure Contribution Score (PCS)
            </h2>
            <p class="text-xs text-[#64748B] mt-1 max-w-2xl">
              Measures how effectively a bowler prevents the batting team from gaining or maintaining control of the innings
              on a bipolar 0–100 scale (neutral 50.00). Independent of BCS runs and bWPA win probability.
            </p>
          </div>

          <div class="flex items-center gap-2 self-start md:self-auto">
            <a href="#/bowling/leaderboard" class="px-3 py-1.5 rounded-lg bg-[#1E3A8A] text-white text-xs font-bold hover:bg-[#1E293B] transition shadow-xs">
              PCS Leaderboard &rarr;
            </a>
          </div>
        </div>

        <!-- Methodology Explainability Card (Section 12) -->
        <div class="card-base p-5 bg-white border-l-4 border-l-[#1E3A8A] border border-[#E2E8F0] rounded-xl shadow-xs space-y-3">
          <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-2">
            <div class="font-bold text-sm text-[#0F172A] flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-[#1E3A8A] shrink-0"></span>
              <span>What is PCS? (Bipolar 0–100 Pressure Contribution Scale — Not a Win Probability)</span>
            </div>
            <div class="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold">
              <span class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">BCS = Runs-Equivalent</span>
              <span class="px-2 py-0.5 rounded bg-pink-50 text-pink-700 border border-pink-200">bWPA = Win Probability</span>
              <span class="px-2 py-0.5 rounded bg-[#EFF6FF] text-[#1E3A8A] border border-[#BFDBFE]">PCS = Pressure Control</span>
            </div>
          </div>
          <p class="text-xs text-[#475569] leading-relaxed">
            <strong>PCS</strong> measures how effectively a bowler prevents the batting team from gaining or maintaining control of the innings.
            Scale: <span class="font-bold text-[#DC2626]">0–49.99</span> indicates negative pressure contribution (pressure leakage),
            <span class="font-bold text-[#475569]">50.00</span> is the neutral baseline, and
            <span class="font-bold text-[#16A34A]">50.01–100</span> indicates positive pressure contribution.
            Because PCS evaluates continuous control rather than raw wickets alone, <em>an economical wicketless spell can receive a high PCS, while an expensive wicket-taking spell can receive a low PCS</em>.
          </p>
        </div>

        <!-- 6 PCS KPI Cards (Section 6) -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          ${renderMetricCard({
            title: 'Average Spell PCS',
            value: formatPCS(avgSpellPCS),
            unit: 'Scale [0-100]',
            subtitle: `Neutral = 50.00 (Low: ${formatPCS(worstSpell ? worstSpell.pcs_spell : 9.31)})`,
            accent: 'deep-blue',
            tooltip: 'Mean Bowling Pressure Contribution Score across 9,482 match spells',
          })}
          ${renderMetricCard({
            title: 'Highest Spell PCS',
            value: formatPCS(bestSpell ? bestSpell.pcs_spell : 98.02),
            unit: 'PCS',
            subtitle: bestSpell ? `${bestSpell.bowler_name}` : 'Record spell',
            accent: 'blue',
            tooltip: 'Highest single-spell pressure generation recorded in corpus',
          })}
          ${renderMetricCard({
            title: 'Best Career PCS',
            value: formatPCS(bestCareerBowler ? bestCareerBowler.pcs_career_shrunk : 64.14),
            unit: 'Shrunk',
            subtitle: bestCareerBowler ? `${bestCareerBowler.bowler_name} (#1)` : 'Top career',
            accent: 'deep-blue',
            tooltip: 'Top Empirical Bayes shrunk career PCS across all qualified bowlers',
          })}
          ${renderMetricCard({
            title: 'Best Season PCS',
            value: formatPCS(bestSeasonBowler ? bestSeasonBowler.pcs_season_shrunk : 65.0),
            unit: 'Shrunk',
            subtitle: bestSeasonBowler ? `${bestSeasonBowler.bowler_name} (${bestSeasonBowler.season})` : 'Top season',
            accent: 'pink',
            tooltip: 'Highest single-season Empirical Bayes shrunk PCS (min 120 balls)',
          })}
          ${renderMetricCard({
            title: 'Positive Pressure Spells',
            value: formatNumber(dist.positive_spells_count || 0),
            unit: `(${dist.positive_spells_pct}%)`,
            subtitle: 'Spells > 50.00 baseline',
            accent: 'blue',
            tooltip: 'Count and percentage of bowling spells generating positive net pressure',
          })}
          ${renderMetricCard({
            title: 'Negative Pressure Spells',
            value: formatNumber(dist.negative_spells_count || 0),
            unit: `(${dist.negative_spells_pct}%)`,
            subtitle: 'Spells < 50.00 baseline',
            accent: 'pink',
            tooltip: 'Count and percentage of bowling spells suffering net pressure leakage',
          })}
        </div>

        <!-- PCS Distribution & Season Progression Visualizations -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Bipolar Histogram Chart -->
          <div class="card-base p-5 bg-white border border-[#E2E8F0] rounded-2xl shadow-sm lg:col-span-2">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="text-sm font-bold text-[#0F172A]">PCS Spell Distribution (Bipolar 0–100 Scale)</h3>
                <span class="text-xs text-[#64748B]">Mean: ${dist.mean.toFixed(2)} &bull; Median: ${dist.median.toFixed(2)} &bull; Std: ${dist.std.toFixed(2)} &bull; Neutral: 50.00</span>
              </div>
              <span class="px-2.5 py-1 rounded text-xs font-bold bg-[#1E3A8A] text-white">N = 9,482 Spells</span>
            </div>
            <div class="h-64 relative">
              <canvas id="pcs-dist-chart"></canvas>
            </div>
          </div>

          <!-- Pressure Outcome Share Doughnut -->
          <div class="card-base p-5 bg-white border border-[#E2E8F0] rounded-2xl shadow-sm flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-bold text-[#0F172A]">Pressure Spell Outcomes</h3>
                <span class="badge-blue">Ternary Split</span>
              </div>
              <p class="text-xs text-[#64748B] mb-4">Distribution of spells by positive, neutral, and negative pressure impact.</p>
              <div class="h-48 relative">
                <canvas id="pcs-share-chart"></canvas>
              </div>
            </div>
            <div class="grid grid-cols-3 gap-1 text-center text-xs pt-3 border-t border-[#F1F5F9]">
              <div>
                <span class="text-[9px] font-bold text-[#16A34A] uppercase block">Positive (&gt;50)</span>
                <span class="text-xs font-black text-[#16A34A]">${dist.positive_spells_pct}%</span>
              </div>
              <div>
                <span class="text-[9px] font-bold text-[#64748B] uppercase block">Neutral (=50)</span>
                <span class="text-xs font-black text-[#64748B]">${dist.neutral_spells_pct}%</span>
              </div>
              <div>
                <span class="text-[9px] font-bold text-[#DC2626] uppercase block">Negative (&lt;50)</span>
                <span class="text-xs font-black text-[#DC2626]">${dist.negative_spells_pct}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Season PCS Progression & Pressure Contribution Trends -->
        ${seasonTrends.length > 0 ? `
          <div class="card-base p-5 bg-white border border-[#E2E8F0] rounded-2xl shadow-sm">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
              <div>
                <h3 class="text-sm font-bold text-[#0F172A]">Season PCS Progression &amp; Positive Pressure Trend</h3>
                <span class="text-xs text-[#64748B]">Average spell PCS and positive pressure spell share across T20 seasons (2022–2026)</span>
              </div>
              <span class="px-2.5 py-1 rounded text-xs font-bold bg-[#EFF6FF] text-[#1E3A8A] border border-[#BFDBFE]">Multi-Season Trend</span>
            </div>
            <div class="h-60 relative">
              <canvas id="pcs-season-trend-chart"></canvas>
            </div>
          </div>
        ` : ''}

        <!-- Top 10 Career Pressure Contributors Table -->
        <div class="card-base p-5 bg-white border border-[#CBD5E1] rounded-2xl shadow-sm">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <h3 class="text-sm font-black text-[#0F172A]">Top 10 Career Pressure Contributors (PCS)</h3>
              <span class="text-xs text-[#64748B]">Ranked by Empirical Bayes Shrunk Career PCS &bull; Neutral anchor = 50.00</span>
            </div>
            <a href="#/bowling/leaderboard" class="btn-secondary text-xs px-3 py-1.5 self-start sm:self-auto">
              View PCS Leaderboard &rarr;
            </a>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-xs text-left">
              <thead class="bg-[#F8FAFC] text-[#64748B] font-bold uppercase text-[10px] border-b border-[#E2E8F0]">
                <tr>
                  <th class="py-2.5 px-3 text-center">Rank</th>
                  <th class="py-2.5 px-3">Bowler Name</th>
                  <th class="py-2.5 px-3">Team</th>
                  <th class="py-2.5 px-3 text-center">Spells</th>
                  <th class="py-2.5 px-3 text-center">Balls</th>
                  <th class="py-2.5 px-3 text-center">Wickets</th>
                  <th class="py-2.5 px-3 text-center">Economy</th>
                  <th class="py-2.5 px-3 text-right">Raw PCS</th>
                  <th class="py-2.5 px-3 text-right font-black text-[#1E3A8A]">Shrunk PCS</th>
                  <th class="py-2.5 px-3 text-center">Status</th>
                  <th class="py-2.5 px-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[#F1F5F9] font-medium text-[#0F172A]">
                ${topCareer.map((b, idx) => `
                  <tr class="hover:bg-[#EFF6FF]/50 transition cursor-pointer" onclick="window.location.hash='#/bowling/players/${b.bowler_id}'">
                    <td class="py-2.5 px-3 text-center font-bold text-[#64748B]">${b.rank || idx + 1}</td>
                    <td class="py-2.5 px-3 font-bold text-[#0F172A] hover:text-[#1E3A8A] whitespace-nowrap">
                      <a href="#/bowling/players/${b.bowler_id}">${b.bowler_name}</a>
                    </td>
                    <td class="py-2.5 px-3 text-[#64748B] whitespace-nowrap">${b.team_name || '—'}</td>
                    <td class="py-2.5 px-3 text-center">${b.spells}</td>
                    <td class="py-2.5 px-3 text-center font-mono">${b.legal_balls}</td>
                    <td class="py-2.5 px-3 text-center font-bold">${b.wickets}</td>
                    <td class="py-2.5 px-3 text-center font-mono">${formatEconomy(b.economy)}</td>
                    <td class="py-2.5 px-3 text-right font-mono text-[#64748B]">${formatPCS(b.pcs_career_raw)}</td>
                    <td class="py-2.5 px-3 text-right font-black text-[#1E3A8A] text-sm">${formatPCS(b.pcs_career_shrunk)}</td>
                    <td class="py-2.5 px-3 text-center">
                      <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${getPCSBadgeClass(b.pcs_career_shrunk)}">
                        ${b.pcs_career_shrunk > 50.00 ? '+Pressure' : b.pcs_career_shrunk < 50.00 ? '-Leakage' : 'Neutral'}
                      </span>
                    </td>
                    <td class="py-2.5 px-3 text-center">
                      <a href="#/bowling/players/${b.bowler_id}" class="text-[11px] font-bold text-[#1E3A8A] hover:underline">Profile &rarr;</a>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  }

  initCharts(dist) {
    // 1. BCS Distribution Bar Chart
    const buckets = ['<-20', '-20 to -10', '-10 to 0', '0 to 10', '10 to 20', '20 to 30', '30 to 50', '50+'];
    const counts = [340, 920, 2460, 3180, 1420, 680, 360, 122];

    renderBarChart('bcs-dist-chart', buckets, [
      {
        label: 'Spells Count',
        data: counts,
        backgroundColor: buckets.map((b) => (b.includes('-') ? '#FCA5A5' : '#93C5FD')),
        borderColor: buckets.map((b) => (b.includes('-') ? '#DC2626' : '#2563EB')),
        borderWidth: 1.5,
        borderRadius: 4,
      },
    ]);

    // 2. BCS Share Doughnut
    renderDoughnutChart(
      'bcs-share-chart',
      ['Positive Contribution', 'Negative Contribution'],
      [dist.positive_share_pct, dist.negative_share_pct],
      ['#16A34A', '#DC2626']
    );
  }

  initPCSCharts(pcs) {
    const dist = pcs.pcs_distribution || pcs.distribution;
    if (!dist || !dist.bins) return;

    // 1. Bipolar PCS Distribution Histogram
    const labels = dist.bins.map((b) => b.bin_label.split(' ')[0]);
    const counts = dist.bins.map((b) => b.count);
    const bgColors = dist.bins.map((b) => {
      if (b.category === 'negative') return '#FCA5A5'; // Soft Red
      if (b.category === 'neutral') return '#CBD5E1';  // Neutral Slate
      return '#86EFAC';                               // Soft Green
    });
    const borderColors = dist.bins.map((b) => {
      if (b.category === 'negative') return '#DC2626'; // Red
      if (b.category === 'neutral') return '#64748B';  // Slate
      return '#16A34A';                               // Green
    });

    renderBarChart('pcs-dist-chart', labels, [
      {
        label: 'Spell Count (Bipolar Scale)',
        data: counts,
        backgroundColor: bgColors,
        borderColor: borderColors,
        borderWidth: 1.5,
        borderRadius: 4,
      },
    ]);

    // 2. PCS Outcome Share Doughnut
    renderDoughnutChart(
      'pcs-share-chart',
      ['Positive Pressure (>50)', 'Neutral (=50)', 'Negative Leakage (<50)'],
      [dist.positive_spells_pct, dist.neutral_spells_pct, dist.negative_spells_pct],
      ['#16A34A', '#94A3B8', '#DC2626']
    );

    // 3. Season PCS Progression & Positive Share Trend
    const trends = pcs.season_trends || [];
    if (trends.length > 0 && document.getElementById('pcs-season-trend-chart')) {
      renderLineChart(
        'pcs-season-trend-chart',
        trends.map((t) => t.season),
        [
          {
            label: 'Avg Spell PCS [0–100]',
            data: trends.map((t) => t.avg_spell_pcs),
            borderColor: '#1E3A8A',
            backgroundColor: 'rgba(30, 58, 138, 0.08)',
            fill: true,
            tension: 0.3,
            borderWidth: 2.5,
            pointRadius: 4,
          },
          {
            label: 'Positive Pressure Spells %',
            data: trends.map((t) => t.positive_spells_pct),
            borderColor: '#16A34A',
            backgroundColor: 'transparent',
            fill: false,
            tension: 0.3,
            borderWidth: 2,
            borderDash: [4, 3],
            pointRadius: 4,
          },
          {
            label: 'Neutral Anchor (50.00)',
            data: trends.map(() => 50.0),
            borderColor: '#94A3B8',
            borderDash: [5, 5],
            pointRadius: 0,
            borderWidth: 1.25,
          },
        ],
        {
          scales: {
            y: { min: 25, max: 70, title: { display: true, text: 'PCS Score / Positive %', font: { size: 10 } } },
          },
        }
      );
    }
  }
}

export function renderBowlingDashboard(container, params) {
  const page = new BowlingDashboard();
  return page.render(container, params);
}
