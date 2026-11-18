/**
 * CricImpact Phase 2 - Platform Settings & Architecture Reference
 * Stage B6: Integrated Batting & Bowling Analytics Frontend
 * 
 * Provides platform metadata, live backend health status, verified model parameters,
 * and design system documentation.
 */

import { bowlingApiService } from '../services/bowlingApiService.js';
import { priApiService } from '../services/priApiService.js';

export async function renderSettingsPage(container, params = {}) {
  container.innerHTML = `
    <div class="space-y-8 animate-fadeIn max-w-5xl">
      <!-- Header -->
      <div class="pb-4 border-b border-slate-200">
        <div class="flex items-center space-x-2 text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
          <span>System Architecture & Verification</span>
        </div>
        <h1 class="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">Platform Settings & Methodology</h1>
        <p class="text-slate-500 text-sm mt-1">
          CricImpact Phase 2 unified contribution platform configuration, API connectivity, and model parameters.
        </p>
      </div>

      <!-- Health & Connectivity Status -->
      <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-base font-bold text-slate-900 flex items-center space-x-2">
            <span id="health-indicator" class="w-3 h-3 rounded-full bg-amber-400 animate-pulse"></span>
            <span>API Connectivity Status</span>
          </h2>
          <button id="check-health-btn" class="text-xs font-bold px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700 transition-colors">
            Ping Backend
          </button>
        </div>

        <div id="health-details" class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-slate-600">
          <div class="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div class="font-bold text-slate-700">Bowling API Service:</div>
            <div id="api-status-text" class="text-slate-500 mt-1">Connecting...</div>
          </div>
          <div class="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div class="font-bold text-slate-700">Production Records:</div>
            <div class="text-slate-800 font-semibold mt-1">798 Matches &bull; 190,575 Deliveries</div>
          </div>
          <div class="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div class="font-bold text-slate-700">Protected Integrity:</div>
            <div class="text-emerald-600 font-bold mt-1">100% SHA-256 Verified</div>
          </div>
        </div>
      </div>

      <!-- Pressure Reliability Index (PRI) Metric Guide -->
      <section id="pri-metric-guide" class="bg-white rounded-2xl p-6 border border-[#BFDBFE] border-t-4 border-t-[#3B82F6] shadow-sm space-y-5">
        <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <span class="text-[10px] font-black uppercase tracking-wider text-[#3B82F6]">Metric Guide &bull; Stage PRI-3</span>
            <h2 class="text-lg font-black text-slate-900 mt-0.5">Pressure Reliability Index (PRI) Explained</h2>
            <p class="text-xs text-slate-500 mt-0.5">Simple, transparent definitions of how CricImpact identifies consistent performers under match pressure.</p>
          </div>
          <a href="#/pressure-reliability" class="px-3 py-1.5 rounded-lg bg-[#EFF6FF] text-[#1E3A8A] border border-[#BFDBFE] text-xs font-extrabold hover:bg-[#DBEAFE] transition">
            Open Pressure Reliability &rarr;
          </a>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-700">
          <div class="p-4 rounded-xl bg-[#EFF6FF]/70 border border-[#BFDBFE] space-y-1.5">
            <div class="font-black text-[#1E3A8A] text-sm">Batting PRI (T10)</div>
            <p class="leading-relaxed">
              Measures how consistently a batter produces <strong>positive HPC (HPC &gt; 0)</strong> in qualifying pressure innings.
              Neutral innings (HPC = 0) are never counted as positive, and Did Not Bat (DNB) appearances are strictly excluded.
            </p>
            <code class="block p-2 mt-2 bg-white rounded border border-[#BFDBFE] text-[#1E3A8A] font-mono text-[11px]">
              Qualifying Innings (T10): mean_p &ge; 40 OR peak_p &ge; 60
            </code>
          </div>

          <div class="p-4 rounded-xl bg-[#FDF2F8]/70 border border-[#FBCFE8] space-y-1.5">
            <div class="font-black text-[#9D174D] text-sm">Bowling PRI (EXO_2)</div>
            <p class="leading-relaxed">
              Measures how consistently a bowler produces <strong>positive PCS (PCS &gt; 50)</strong> in qualifying pressure spells.
              Evaluated strictly before each over begins so bowlers who break a dangerous partnership early remain credited. Neutral spells (PCS = 50) are never counted as positive.
            </p>
            <code class="block p-2 mt-2 bg-white rounded border border-[#FBCFE8] text-[#9D174D] font-mono text-[11px]">
              Qualifying Spells (EXO_2): max_over_entry_pti &ge; 35 AND legal_balls &ge; 12
            </code>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
            <div class="font-black text-[#16A34A]">Positive Reliability %</div>
            <p class="text-slate-600 leading-relaxed">
              Percentage of qualifying pressure opportunities where the player produced a strictly positive contribution (<code>Positive / Qualifying &times; 100</code>). Never shrunk or adjusted.
            </p>
          </div>
          <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
            <div class="font-black text-[#1E3A8A]">Pressure Quality</div>
            <p class="text-slate-600 leading-relaxed">
              Average contribution magnitude within qualifying pressure opportunities (<strong>Average HPC</strong> for batters, <strong>Average PCS</strong> for bowlers).
            </p>
          </div>
          <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
            <div class="font-black text-[#DB2777]">Min Pressure Innings / Spells</div>
            <p class="text-slate-600 leading-relaxed">
              A custom whole-number filter controlled directly by you (enter <code>0</code> for no minimum, or any threshold like <code>12</code> or <code>18</code>) without changing any player's stats.
            </p>
          </div>
        </div>

        <!-- Important Distinction Callout -->
        <div class="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-950 space-y-1.5">
          <div class="font-black text-amber-900">Important Distinction: Consistency vs Contribution Quality vs Career Greatness</div>
          <ul class="list-disc list-inside space-y-1 text-amber-900/90 leading-relaxed">
            <li><strong>PRI does not measure total career greatness.</strong> It specifically identifies who consistently delivers in difficult match situations.</li>
            <li><strong>Reliability Rate and Pressure Quality are separate dimensions:</strong> a player with high reliability may produce steady, moderate contributions, while an explosive match-winner may have high average contribution quality with lower consistency.</li>
            <li><strong>No Shrinkage &amp; No Composite Score:</strong> PRI never blends reliability and quality into a single opaque number and never pulls small samples toward a prior.</li>
          </ul>
        </div>
      </section>

      <!-- Bowling Contribution Model (BCM) Specification -->
      <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h2 class="text-base font-bold text-slate-900">Bowling Contribution Model (BCM) Architecture C</h2>
            <p class="text-xs text-slate-500">Statistically validated production parameters implemented in Stage B4</p>
          </div>
          <span class="text-xs font-bold px-2.5 py-1 rounded bg-blue-50 text-blue-700 border border-blue-200">Verified</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-700">
          <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
            <div class="font-bold text-slate-900 text-sm">1. Core Delivery Equation</div>
            <code class="block p-2 bg-white rounded border border-slate-200 text-pink-700 font-mono text-[11px]">
              BCS = L_d &times; [ERP + WQM &times; V_wkt] + Dot_Adj + RRR_Adj
            </code>
            <ul class="list-disc list-inside space-y-1 text-slate-600 text-[11px]">
              <li><strong>ERP:</strong> Expected Runs Prevented (baseline venue/state runs minus actual runs).</li>
              <li><strong>WQM:</strong> Wicket Quality Multiplier based on dismissed batter career & recent threat.</li>
              <li><strong>V_wkt:</strong> Context-dependent wicket resource value (innings 1 par curve vs innings 2 chase).</li>
              <li><strong>L_d:</strong> Match leverage multiplier (Approach D: scaled delivery leverage).</li>
            </ul>
          </div>

          <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
            <div class="font-bold text-slate-900 text-sm">2. Career Normalization (Bayes Shrinkage)</div>
            <code class="block p-2 bg-white rounded border border-slate-200 text-blue-700 font-mono text-[11px]">
              BCS_shrunk = (B &times; BCS_rate + M0 &times; &mu;_prior) / (B + M0) &times; B
            </code>
            <ul class="list-disc list-inside space-y-1 text-slate-600 text-[11px]">
              <li><strong>Prior M0:</strong> 48 balls (equivalent to 8 T20 overs).</li>
              <li><strong>Population Mean &mu;_prior:</strong> 0.00 runs/over neutral baseline.</li>
              <li><strong>Sample Size B:</strong> Bowler's total career legal balls bowled.</li>
              <li><strong>Total BCS vs Shrunk BCS:</strong> Preserved as distinct metrics in API and UI.</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Visual Identity & Color Palette -->
      <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div>
          <h2 class="text-base font-bold text-slate-900">Visual Identity Design System: Pink + Blue Light Theme</h2>
          <p class="text-xs text-slate-500">Accessible, high-contrast palette calibrated for cricket analytics</p>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3 text-center text-xs">
          <div class="p-3 rounded-xl border border-pink-200 bg-pink-500 text-white font-bold">
            <div>Primary Pink</div>
            <div class="font-mono text-[10px] mt-1">#EC4899</div>
          </div>
          <div class="p-3 rounded-xl border border-pink-300 bg-pink-600 text-white font-bold">
            <div>Deep Pink</div>
            <div class="font-mono text-[10px] mt-1">#DB2777</div>
          </div>
          <div class="p-3 rounded-xl border border-blue-200 bg-blue-500 text-white font-bold">
            <div>Primary Blue</div>
            <div class="font-mono text-[10px] mt-1">#3B82F6</div>
          </div>
          <div class="p-3 rounded-xl border border-blue-300 bg-blue-600 text-white font-bold">
            <div>Deep Blue</div>
            <div class="font-mono text-[10px] mt-1">#2563EB</div>
          </div>
          <div class="p-3 rounded-xl border border-blue-900 bg-blue-900 text-white font-bold">
            <div>Navy Blue</div>
            <div class="font-mono text-[10px] mt-1">#1E3A8A</div>
          </div>
          <div class="p-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-800 font-bold">
            <div>Light Slate BG</div>
            <div class="font-mono text-[10px] mt-1">#F8FAFC</div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Attach ping health handler
  const pingBtn = container.querySelector('#check-health-btn');
  const indicator = container.querySelector('#health-indicator');
  const statusText = container.querySelector('#api-status-text');

  async function checkHealth() {
    try {
      const [res, priRes] = await Promise.all([
        bowlingApiService.getDashboard(),
        priApiService.checkHealth().catch(() => null),
      ]);
      if (res && res.success) {
        indicator.className = 'w-3 h-3 rounded-full bg-emerald-500 shadow-sm';
        const priLabel = priRes?.service_initialized ? ` &bull; PRI (${priRes.artifacts_loaded}/10 artifacts) live` : '';
        statusText.innerHTML = `<span class="text-emerald-600 font-bold">Healthy &bull; ${res.data.total_matches} matches${priLabel}</span>`;
      } else {
        throw new Error('API reported unready state');
      }
    } catch (e) {
      indicator.className = 'w-3 h-3 rounded-full bg-rose-500';
      statusText.innerHTML = `<span class="text-rose-600 font-bold">Error: ${e.message}</span>`;
    }
  }

  if (pingBtn) {
    pingBtn.onclick = checkHealth;
  }
  checkHealth();

  if (params && params.section === 'pri-metric-guide') {
    const target = container.querySelector('#pri-metric-guide');
    if (target) {
      setTimeout(() => target.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60);
    }
  }
}
