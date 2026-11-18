/**
 * CricImpact Phase 2 — Unified Platform Overview Page
 * Unites Batting and Bowling Analytics under the Pink + Blue design system,
 * featuring BCM (BCS, bWPA) and the independent PCS (Pressure Contribution Score) layer.
 */

import { APP_METADATA } from '../config/apiConfig.js';
import { pcsApiService } from '../services/pcsApiService.js';
import { formatNumber } from '../utils/formatting.js';

export class OverviewPage {
  constructor() {
    this.container = null;
  }

  async render(container) {
    this.container = container;
    const meta = APP_METADATA.CORPUS_SUMMARY;

    // Hydrate live PCS summary (Best Career PCS, Highest Pressure Spell, Positive Pressure Trend)
    let pcs = null;
    try {
      const res = await pcsApiService.getDashboard();
      pcs = res?.data || null;
    } catch (_) {
      pcs = null;
    }

    const bestCareer = pcs?.top_career_leaders?.[0];
    const bestSpell = pcs?.highest_spell_pcs;
    const posPct = pcs?.pcs_distribution?.positive_spells_pct;
    const bestCareerTxt = bestCareer ? `${bestCareer.bowler_name} (${bestCareer.pcs_career_shrunk.toFixed(2)})` : 'Jasprit Bumrah (64.14)';
    const bestSpellTxt = bestSpell ? `${bestSpell.pcs_spell.toFixed(2)} (${bestSpell.bowler_name})` : '98.02 Record';
    const posTrendTxt = posPct !== undefined ? `${posPct.toFixed(1)}% Spells > 50` : '50.00 Neutral';

    container.innerHTML = `
      <div class="space-y-6 animate-fade-in">
        <!-- Hero Header -->
        <div class="hero-gradient rounded-2xl p-6 md:p-8 shadow-md relative overflow-hidden">
          <div class="relative z-10 max-w-3xl">
            <div class="flex flex-wrap items-center gap-2 mb-3">
              <span class="px-2.5 py-1 text-[11px] font-black uppercase tracking-wider rounded-md bg-white/20 text-white backdrop-blur-sm">
                CricImpact 2.0
              </span>
              <span class="px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider rounded-md bg-white/20 text-white backdrop-blur-sm">
                Unified Contextual Analytics
              </span>
              <span class="text-xs text-white/80 font-mono">
                ${meta.SEASONS} &bull; ${formatNumber(meta.MATCHES)} Standard T20 Matches
              </span>
            </div>

            <h1 class="text-3xl md:text-4xl font-black text-white tracking-tight leading-tight">
              Cricket Performance Evaluated Beyond Conventional Scorecards.
            </h1>

            <p class="text-sm md:text-base text-white/90 mt-3 leading-relaxed">
              CricImpact Phase 2 unifies independent, statistically validated contribution models for both
              <strong>Batting (High-Pressure Player HPC)</strong> and <strong>Bowling (BCM Runs/bWPA & PCS Match Pressure)</strong>.
              Evaluate player value calibrated against match leverage, game context, and win probability swing.
            </p>

            <div class="flex flex-wrap items-center gap-3 mt-6">
              <a href="#/bowling/dashboard" class="px-4 py-2 rounded-lg bg-white text-[#0F172A] font-bold text-xs hover:bg-[#FDF2F8] hover:text-[#DB2777] shadow-sm transition">
                Explore Bowling Analytics &rarr;
              </a>
              <a href="#/batting/dashboard" class="px-4 py-2 rounded-lg bg-[#0F172A]/40 text-white border border-white/30 font-bold text-xs hover:bg-[#0F172A]/60 transition">
                Explore Batting Analytics &rarr;
              </a>
              <a href="#/bowling/compare" class="px-4 py-2 rounded-lg bg-white/10 text-white font-bold text-xs hover:bg-white/20 backdrop-blur-sm transition">
                Head-to-Head Comparison
              </a>
            </div>
          </div>
        </div>

        <!-- Three Pillars: Batting, Bowling Contribution (BCM), and Bowling Pressure (PCS) -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <!-- Batting Pillar -->
          <div class="card-base p-6 bg-white border border-[#E2E8F0] border-t-4 border-t-[#3B82F6] rounded-2xl shadow-sm hover:shadow-md transition flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-xl bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center font-black">
                    🏏
                  </div>
                  <div>
                    <h2 class="text-base font-black text-[#0F172A]">Batting Contribution</h2>
                    <span class="text-xs text-[#64748B]">High-Pressure Player (HPC)</span>
                  </div>
                </div>
                <span class="badge-blue">Stage 7C</span>
              </div>

              <p class="text-xs text-[#64748B] leading-relaxed mb-4">
                Evaluates batters based on Runs Above Expectation (RAE), pre-delivery match pressure (P&#x209C; &isin; [0, 100]),
                crisis recovery, and situational difficulty. DNB stints are strictly marked Not Batted and excluded from averages.
              </p>

              <div class="grid grid-cols-2 gap-2 text-xs py-3 border-y border-[#F1F5F9] my-4">
                <div>
                  <span class="text-[10px] font-bold uppercase text-[#94A3B8] block">Evaluated Stints</span>
                  <span class="text-sm font-black text-[#0F172A]">12,888 Batted</span>
                </div>
                <div>
                  <span class="text-[10px] font-bold uppercase text-[#94A3B8] block">Unique Batters</span>
                  <span class="text-sm font-black text-[#2563EB]">880 Players</span>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2 pt-2">
              <a href="#/batting/dashboard" class="btn-primary text-xs text-center">HPP Dashboard</a>
              <a href="#/batting/explorer" class="btn-secondary text-xs text-center">HPP Explorer</a>
              <a href="#/batting/compare" class="btn-secondary text-xs text-center">Compare</a>
              <a href="#/batting/worm_graph" class="btn-secondary text-xs text-center">Worm Graph</a>
            </div>
          </div>

          <!-- Bowling Contribution Pillar (BCM) -->
          <div class="card-base p-6 bg-white border border-[#E2E8F0] border-t-4 border-t-[#EC4899] rounded-2xl shadow-sm hover:shadow-md transition flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-xl bg-[#FDF2F8] text-[#DB2777] flex items-center justify-center font-black">
                    🎯
                  </div>
                  <div>
                    <h2 class="text-base font-black text-[#0F172A]">Bowling Contribution</h2>
                    <span class="text-xs text-[#64748B]">BCM Runs & Win Prob</span>
                  </div>
                </div>
                <span class="badge-pink">Stage B5.1</span>
              </div>

              <p class="text-xs text-[#64748B] leading-relaxed mb-4">
                Evaluates Expected Runs Prevented (ERP), Wicket Quality Multipliers (WQM), and Bowler Win Probability Added (bWPA)
                across Powerplay, Middle, and Death overs.
              </p>

              <div class="grid grid-cols-2 gap-2 text-xs py-3 border-y border-[#F1F5F9] my-4">
                <div>
                  <span class="text-[10px] font-bold uppercase text-[#94A3B8] block">All-Time Leader</span>
                  <span class="text-sm font-black text-[#DB2777]">Rashid Khan (+1,631)</span>
                </div>
                <div>
                  <span class="text-[10px] font-bold uppercase text-[#94A3B8] block">Spells Evaluated</span>
                  <span class="text-sm font-black text-[#0F172A]">9,482 Spells</span>
                </div>
              </div>
            </div>

            <div class="flex items-center gap-2 pt-2">
              <a href="#/bowling/dashboard" class="btn-pink text-xs flex-1 text-center">Bowling Dashboard</a>
              <a href="#/bowling/leaderboard" class="btn-secondary text-xs flex-1 text-center">BCM Leaderboard</a>
            </div>
          </div>

          <!-- Bowling Pressure Pillar (PCS) -->
          <div class="card-base p-6 bg-white border border-[#CBD5E1] border-t-4 border-t-[#1E3A8A] rounded-2xl shadow-sm hover:shadow-md transition flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-xl bg-[#EFF6FF] text-[#1E3A8A] flex items-center justify-center font-black">
                    ⚡
                  </div>
                  <div>
                    <h2 class="text-base font-black text-[#0F172A]">Pressure Contribution</h2>
                    <span class="text-xs text-[#1E3A8A] font-semibold">PCS Bipolar [0–100]</span>
                  </div>
                </div>
                <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#1E3A8A] text-white">
                  Stage B8 Live
                </span>
              </div>

              <p class="text-xs text-[#64748B] leading-relaxed mb-4">
                Independent layer quantifying match-context pressure generation. Measures dangerous stand containment (DCI),
                situational wickets (SWI), and suppression without volume tallying.
              </p>

              <div class="grid grid-cols-2 gap-2 text-xs py-3 border-y border-[#F1F5F9] my-4">
                <div>
                  <span class="text-[10px] font-bold uppercase text-[#94A3B8] block">Best Career PCS</span>
                  <span class="text-sm font-black text-[#1E3A8A]">${bestCareerTxt}</span>
                </div>
                <div>
                  <span class="text-[10px] font-bold uppercase text-[#94A3B8] block">Highest Pressure Spell</span>
                  <span class="text-sm font-black text-[#DB2777]">${bestSpellTxt}</span>
                </div>
                <div class="col-span-2 pt-1 border-t border-[#F8FAFC] flex items-center justify-between">
                  <span class="text-[10px] font-bold uppercase text-[#94A3B8]">Positive Pressure Trend</span>
                  <span class="text-xs font-black text-[#16A34A]">${posTrendTxt}</span>
                </div>
              </div>
            </div>

            <div class="flex items-center gap-2 pt-2">
              <a href="#/bowling/dashboard" class="px-3 py-1.5 rounded-lg bg-[#1E3A8A] text-white text-xs font-bold hover:bg-[#1E293B] transition text-center flex-1 shadow-xs">
                Pressure Telemetry
              </a>
              <a href="#/bowling/leaderboard" class="btn-secondary text-xs flex-1 text-center">
                PCS Rankings
              </a>
            </div>
          </div>
        </div>

        <!-- Three Complementary Dimensions of Bowling Analytics Callout -->
        <div class="card-base p-6 bg-gradient-to-r from-white via-[#F8FAFC] to-white border border-[#CBD5E1] rounded-2xl shadow-xs">
          <div class="flex items-center gap-2 mb-3">
            <span class="w-2.5 h-2.5 rounded-full bg-[#1E3A8A]"></span>
            <h3 class="text-sm font-black uppercase tracking-wider text-[#0F172A]">
              The Three Complementary Dimensions of Bowling Analytics
            </h3>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div class="p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
              <span class="font-bold text-blue-700 block mb-1">1. Run Prevention (BCS)</span>
              <p class="text-slate-600 leading-relaxed">
                Evaluates runs saved above expectation calibrated against venue par, phase dynamics, and situational leverage.
              </p>
            </div>
            <div class="p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
              <span class="font-bold text-pink-700 block mb-1">2. Win Impact (bWPA)</span>
              <p class="text-slate-600 leading-relaxed">
                Measures the net percentage swing in match win probability generated directly by the bowler's deliveries.
              </p>
            </div>
            <div class="p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
              <span class="font-bold text-[#1E3A8A] block mb-1">3. Match-Context Pressure (PCS)</span>
              <p class="text-slate-600 leading-relaxed">
                Evaluates continuous pressure dynamics, partnership suppression, and breakthrough wicket leverage on a 0–100 scale.
              </p>
            </div>
          </div>
        </div>

        <!-- Quick Launch Pad -->
        <div class="card-base p-6 bg-white border border-[#E2E8F0] rounded-2xl shadow-sm">
          <h3 class="text-sm font-bold uppercase tracking-wider text-[#0F172A] mb-4">Analytics Quick Launchpad</h3>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <a href="#/bowling/leaderboard" class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#1E3A8A] hover:bg-[#EFF6FF] transition block">
              <span class="font-bold text-[#0F172A] block mb-1">Bowling Leaderboard</span>
              <span class="text-[#64748B] text-[11px]">Rank 638 career bowlers across BCS, bWPA & PCS</span>
            </a>
            <a href="#/bowling/compare" class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#3B82F6] hover:bg-[#EFF6FF] transition block">
              <span class="font-bold text-[#0F172A] block mb-1">5-Bowler Comparison</span>
              <span class="text-[#64748B] text-[11px]">Side-by-side radar and phase comparison</span>
            </a>
            <a href="#/bowling/matches" class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#EC4899] hover:bg-[#FDF2F8] transition block">
              <span class="font-bold text-[#0F172A] block mb-1">Match & Spell Analysis</span>
              <span class="text-[#64748B] text-[11px]">Explore 798 scorecards and delivery transitions</span>
            </a>
            <a href="#/batting/worm_graph" class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#3B82F6] hover:bg-[#EFF6FF] transition block">
              <span class="font-bold text-[#0F172A] block mb-1">Win Probability Worm</span>
              <span class="text-[#64748B] text-[11px]">Live Win Probability swings per delivery</span>
            </a>
          </div>
        </div>
      </div>
    `;
  }
}

export function renderOverviewPage(container, params) {
  const page = new OverviewPage();
  return page.render(container, params);
}
