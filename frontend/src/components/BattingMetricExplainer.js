/**
 * CricImpact Phase 2 — Batting Metric Explanations Component
 * Stage B9: Clear, accurate definitions of HPC, RAE, DNB, Runs, Expected Runs & Pressure.
 */

export function renderBattingMetricExplainer({ compact = false } = {}) {
  if (compact) {
    return `
      <section class="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-sm" aria-label="Metric Guide">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h3 class="text-xs font-black uppercase tracking-wider text-[#1E3A8A] flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-[#3B82F6]"></span>
            Batting HPP Metric Reference
          </h3>
          <span class="text-[11px] font-semibold text-[#64748B]">HPC is a pressure-adjusted run contribution metric — not a win-probability score</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          <div class="p-3 rounded-xl bg-[#EFF6FF] border border-[#BFDBFE]">
            <div class="font-black text-[#1E3A8A]">HPC (Batting Contribution)</div>
            <p class="text-[#475569] mt-1 leading-relaxed">Measures batting contribution relative to expected performance, adjusted for situational match pressure.</p>
          </div>
          <div class="p-3 rounded-xl bg-[#FDF2F8] border border-[#FBCFE8]">
            <div class="font-black text-[#BE185D]">RAE (Runs Above Expected)</div>
            <p class="text-[#475569] mt-1 leading-relaxed">Actual batter runs minus expected batter runs for the balls faced in that match context.</p>
          </div>
          <div class="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
            <div class="font-black text-[#0F172A]">Pressure (0–100 Scale)</div>
            <p class="text-[#475569] mt-1 leading-relaxed">Pre-delivery situational difficulty (Low &lt;25, Med 25–50, High 50–75, Extreme 75+).</p>
          </div>
          <div class="p-3 rounded-xl bg-[#F8FAFC] border border-dashed border-[#94A3B8]">
            <div class="font-black text-[#475569]">DNB (Did Not Bat)</div>
            <p class="text-[#475569] mt-1 leading-relaxed">Displayed explicitly as <strong>Not Batted</strong>. Never treated as zero and excluded from all averages.</p>
          </div>
        </div>
      </section>
    `;
  }

  return `
    <section class="bg-white border border-[#E2E8F0] rounded-2xl p-5 sm:p-6 shadow-sm space-y-5" aria-label="Batting Methodology and Metric Explanations">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#F1F5F9] pb-3">
        <div>
          <span class="text-[10px] font-black uppercase tracking-wider text-[#EC4899]">Metric Explanations</span>
          <h2 class="text-base font-black text-[#0F172A] mt-0.5">Understanding Batting HPP &amp; HPC Analytics</h2>
        </div>
        <span class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold bg-[#EFF6FF] text-[#1E3A8A] border border-[#BFDBFE]">
          Run-Contribution Engine (Not Win Probability)
        </span>
      </div>

      <!-- Core Definitions -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="p-4 rounded-xl bg-[#EFF6FF]/70 border border-[#BFDBFE]">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-black text-[#1E3A8A]">HPC</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-white text-[#2563EB] border border-[#BFDBFE]">Contribution</span>
          </div>
          <p class="text-xs text-[#334155] leading-relaxed">
            <strong>High-Pressure Contribution</strong> measures batting contribution relative to expected performance, adjusted for the situational pressure faced during the innings. Positive HPC indicates value added above expectation; negative HPC indicates underperformance.
          </p>
        </div>

        <div class="p-4 rounded-xl bg-[#FDF2F8]/70 border border-[#FBCFE8]">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-black text-[#BE185D]">RAE</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-white text-[#DB2777] border border-[#FBCFE8]">Runs Delta</span>
          </div>
          <p class="text-xs text-[#334155] leading-relaxed">
            <strong>Runs Above Expectation</strong> is simply <em>Actual Batter Runs minus Expected Batter Runs</em>. It captures raw scoring outperformance before asymmetric pressure weighting is applied.
          </p>
        </div>

        <div class="p-4 rounded-xl bg-[#F8FAFC] border border-dashed border-[#94A3B8]">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-black text-[#334155]">DNB</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-white text-[#64748B] border border-[#CBD5E1]">Not Batted</span>
          </div>
          <p class="text-xs text-[#334155] leading-relaxed">
            <strong>Did Not Bat</strong>. Players who did not face a delivery in a match are explicitly labeled <strong>Not Batted</strong>. DNB stints are never treated as zero and are strictly excluded from batting averages, mean HPC, and mean pressure calculations.
          </p>
        </div>
      </div>

      <!-- Clear 4-Way Distinction -->
      <div>
        <h3 class="text-xs font-black uppercase tracking-wider text-[#64748B] mb-2.5">Four Distinct Dimensions of a Batting Innings</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          <div class="p-3 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC]">
            <div class="font-extrabold text-[#0F172A] mb-1">1. Runs Scored</div>
            <p class="text-[#64748B] leading-relaxed">Raw runs credited to the batter on the official scorecard.</p>
          </div>
          <div class="p-3 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC]">
            <div class="font-extrabold text-[#3B82F6] mb-1">2. Expected Runs</div>
            <p class="text-[#64748B] leading-relaxed">Baseline runs an average batter is expected to score across those exact deliveries and match states.</p>
          </div>
          <div class="p-3 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC]">
            <div class="font-extrabold text-[#EC4899] mb-1">3. Batting Contribution (HPC)</div>
            <p class="text-[#64748B] leading-relaxed">Pressure-adjusted value above expectation — distinct from both raw runs and team win probability.</p>
          </div>
          <div class="p-3 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC]">
            <div class="font-extrabold text-[#1E3A8A] mb-1">4. Pressure (0–100)</div>
            <p class="text-[#64748B] leading-relaxed">Match difficulty faced prior to each delivery (wickets lost, required rate, phase, and score relative to par).</p>
          </div>
        </div>
      </div>
    </section>
  `;
}

export function getPressureTierBadge(tier) {
  const t = (tier || 'Low').toLowerCase();
  if (t === 'dnb') return `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tier-badge-dnb">Not Batted</span>`;
  if (t === 'extreme') return `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tier-badge-extreme">Extreme</span>`;
  if (t === 'high') return `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tier-badge-high">High</span>`;
  if (t === 'medium') return `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tier-badge-medium">Medium</span>`;
  return `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tier-badge-low">Low</span>`;
}

export function formatSigned(val, decimals = 2) {
  if (val === null || val === undefined || Number.isNaN(val)) return '—';
  const num = Number(val);
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(decimals)}`;
}

export function getSignedColorClass(val) {
  if (val === null || val === undefined || Number.isNaN(val)) return 'text-[#64748B]';
  if (val > 0) return 'text-[#16A34A]';
  if (val < 0) return 'text-[#DC2626]';
  return 'text-[#64748B]';
}

export function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
