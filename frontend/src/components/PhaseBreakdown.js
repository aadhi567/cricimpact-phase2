/**
 * CricImpact Phase 2 — PhaseBreakdown Component
 * Displays distinct visual panels for Powerplay (Blue), Middle (Pink), and Death (Deep Blue) overs.
 */

import { formatBCS, formatBWPA, formatEconomy, formatPercent, formatNumber } from '../utils/formatting.js';

export function renderPhasePanels(phaseList = []) {
  const phaseMap = {};
  phaseList.forEach((p) => {
    phaseMap[p.phase.toLowerCase()] = p;
  });

  const pp = phaseMap['powerplay'] || {};
  const mid = phaseMap['middle'] || {};
  const death = phaseMap['death'] || {};

  return `
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- Powerplay (Overs 1-6) -->
      <div class="card-base bg-white border border-[#E2E8F0] border-t-4 border-t-[#3B82F6] rounded-xl p-4 shadow-sm">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-[#3B82F6]"></span>
            <span class="text-xs font-black uppercase tracking-wider text-[#0F172A]">Powerplay (Ov 1–6)</span>
          </div>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#EFF6FF] text-[#2563EB]">Field Restrictions</span>
        </div>

        <div class="grid grid-cols-2 gap-3 py-2 border-y border-[#F1F5F9] my-2">
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Total BCS</span>
            <span class="text-base font-black text-[#2563EB]">${formatBCS(pp.total_bcs)}</span>
          </div>
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Total bWPA</span>
            <span class="text-base font-black text-[#0F172A]">${formatBWPA(pp.total_bwpa)}</span>
          </div>
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Economy</span>
            <span class="text-sm font-bold text-[#0F172A]">${formatEconomy(pp.economy)}</span>
          </div>
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Wickets</span>
            <span class="text-sm font-bold text-[#0F172A]">${formatNumber(pp.wickets)}</span>
          </div>
        </div>

        <div class="flex items-center justify-between text-[11px] text-[#64748B] pt-1">
          <span>Legal Deliveries: <strong class="text-[#0F172A]">${formatNumber(pp.legal_balls)}</strong></span>
          <span>Dot Ball %: <strong class="text-[#0F172A]">${formatPercent(pp.dot_pct)}</strong></span>
        </div>
      </div>

      <!-- Middle Overs (Overs 7-16) -->
      <div class="card-base bg-white border border-[#E2E8F0] border-t-4 border-t-[#EC4899] rounded-xl p-4 shadow-sm">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-[#EC4899]"></span>
            <span class="text-xs font-black uppercase tracking-wider text-[#0F172A]">Middle Overs (Ov 7–16)</span>
          </div>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#FDF2F8] text-[#DB2777]">Run Control & Spin</span>
        </div>

        <div class="grid grid-cols-2 gap-3 py-2 border-y border-[#F1F5F9] my-2">
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Total BCS</span>
            <span class="text-base font-black text-[#DB2777]">${formatBCS(mid.total_bcs)}</span>
          </div>
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Total bWPA</span>
            <span class="text-base font-black text-[#0F172A]">${formatBWPA(mid.total_bwpa)}</span>
          </div>
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Economy</span>
            <span class="text-sm font-bold text-[#0F172A]">${formatEconomy(mid.economy)}</span>
          </div>
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Wickets</span>
            <span class="text-sm font-bold text-[#0F172A]">${formatNumber(mid.wickets)}</span>
          </div>
        </div>

        <div class="flex items-center justify-between text-[11px] text-[#64748B] pt-1">
          <span>Legal Deliveries: <strong class="text-[#0F172A]">${formatNumber(mid.legal_balls)}</strong></span>
          <span>Dot Ball %: <strong class="text-[#0F172A]">${formatPercent(mid.dot_pct)}</strong></span>
        </div>
      </div>

      <!-- Death Overs (Overs 17-20) -->
      <div class="card-base bg-white border border-[#E2E8F0] border-t-4 border-t-[#1E3A8A] rounded-xl p-4 shadow-sm">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-[#1E3A8A]"></span>
            <span class="text-xs font-black uppercase tracking-wider text-[#0F172A]">Death Overs (Ov 17–20)</span>
          </div>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#DBEAFE] text-[#1E3A8A]">High Leverage Surge</span>
        </div>

        <div class="grid grid-cols-2 gap-3 py-2 border-y border-[#F1F5F9] my-2">
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Total BCS</span>
            <span class="text-base font-black text-[#1E3A8A]">${formatBCS(death.total_bcs)}</span>
          </div>
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Total bWPA</span>
            <span class="text-base font-black text-[#0F172A]">${formatBWPA(death.total_bwpa)}</span>
          </div>
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Economy</span>
            <span class="text-sm font-bold text-[#0F172A]">${formatEconomy(death.economy)}</span>
          </div>
          <div>
            <span class="text-[10px] font-bold uppercase text-[#64748B] block">Wickets</span>
            <span class="text-sm font-bold text-[#0F172A]">${formatNumber(death.wickets)}</span>
          </div>
        </div>

        <div class="flex items-center justify-between text-[11px] text-[#64748B] pt-1">
          <span>Legal Deliveries: <strong class="text-[#0F172A]">${formatNumber(death.legal_balls)}</strong></span>
          <span>Dot Ball %: <strong class="text-[#0F172A]">${formatPercent(death.dot_pct)}</strong></span>
        </div>
      </div>
    </div>
  `;
}

export const renderPhaseBreakdown = renderPhasePanels;
