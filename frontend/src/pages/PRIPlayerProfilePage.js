/**
 * CricImpact Phase 2 — Stage PRI-3: Dedicated Player Pressure Reliability Profile
 *
 * Independent Batter & Bowler PRI profiles displaying exact stored PRI-2 career,
 * season-wise, tournament-wise, and match-wise pressure reliability statistics.
 * Zero shrinkage, zero composite score, full access for all players.
 */

import { priApiService } from '../services/priApiService.js';
import { escapeHtml, formatSigned, getSignedColorClass } from '../components/BattingMetricExplainer.js';
import {
  getPosRelBadgeClass,
  getPosRelTextClass,
  getPosRelBarColor,
} from './PressureReliabilityPage.js';

let PROFILE_CHART = null;

function destroyProfileChart() {
  if (PROFILE_CHART) {
    try {
      PROFILE_CHART.destroy();
    } catch (_) {}
    PROFILE_CHART = null;
  }
}

export async function renderPRIPlayerProfile(container, params = {}, domain = 'batting') {
  destroyProfileChart();
  const isBat = domain === 'batting';
  const playerId = params.id;

  if (!playerId) {
    window.location.hash = `#/pressure-reliability/${isBat ? 'batting' : 'bowling'}`;
    return;
  }

  container.innerHTML = `
    <div class="space-y-4 animate-fadeIn">
      <div class="h-32 rounded-2xl bg-white border border-[#E2E8F0] animate-pulse"></div>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div class="h-24 rounded-xl bg-white border border-[#E2E8F0] animate-pulse"></div>
        <div class="h-24 rounded-xl bg-white border border-[#E2E8F0] animate-pulse"></div>
        <div class="h-24 rounded-xl bg-white border border-[#E2E8F0] animate-pulse"></div>
        <div class="h-24 rounded-xl bg-white border border-[#E2E8F0] animate-pulse"></div>
      </div>
      <div class="h-72 rounded-2xl bg-white border border-[#E2E8F0] animate-pulse"></div>
    </div>
  `;

  let payload = null;
  try {
    payload = isBat
      ? await priApiService.getBattingPlayerProfile(playerId)
      : await priApiService.getBowlingPlayerProfile(playerId);
  } catch (err) {
    container.innerHTML = `
      <div class="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-3">
        <h2 class="text-base font-black">${isBat ? 'Batter' : 'Bowler'} Pressure Reliability Profile Not Found</h2>
        <p class="text-xs">${escapeHtml(err.message)}</p>
        <a href="#/pressure-reliability/${isBat ? 'batting' : 'bowling'}" class="inline-flex px-3.5 py-2 rounded-lg bg-rose-600 text-white text-xs font-bold hover:bg-rose-700">&larr; Back to Pressure Reliability</a>
      </div>
    `;
    return;
  }

  const c = payload.career || {};
  const seasons = payload.seasons || [];
  const tournaments = payload.tournaments || [];
  const matchRows = isBat ? (payload.pressure_innings || []) : (payload.pressure_spells || []);

  const playerName = isBat ? c.batter_name : c.bowler_name;
  const opps = isBat ? c.pressure_innings : c.pressure_spells;
  const posN = isBat ? c.positive_hpc_innings : c.positive_pcs_spells;
  const negN = isBat ? c.negative_hpc_innings : c.negative_pcs_spells;
  const neuN = isBat ? c.neutral_hpc_innings : c.neutral_pcs_spells;
  const relPct = isBat ? c.positive_hpc_pct : c.positive_pcs_pct;
  const avgVal = isBat ? c.avg_hpc_under_pressure : c.avg_pcs_under_pressure;
  const totVal = isBat ? c.total_hpc_under_pressure : c.total_pressure_contribution_rpe;
  const hasOpps = Boolean(c.has_pressure_opportunities);

  document.title = `${playerName} — ${isBat ? 'Batting' : 'Bowling'} Pressure Reliability | CricImpact Phase 2`;

  const posBarPct = opps > 0 ? (posN / opps) * 100 : 0;
  const neuBarPct = opps > 0 ? (neuN / opps) * 100 : 0;
  const negBarPct = opps > 0 ? (negN / opps) * 100 : 0;

  const crossProfileHref = isBat
    ? `#/batting/players/${encodeURIComponent(playerName)}`
    : `#/bowling/players/${c.bowler_id}`;

  container.innerHTML = `
    <div class="space-y-6 animate-fadeIn pb-10">
      <!-- Top Breadcrumb & Actions -->
      <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
        <a href="#/pressure-reliability/${isBat ? 'batting' : 'bowling'}" class="inline-flex items-center gap-1.5 font-bold ${isBat ? 'text-[#2563EB]' : 'text-[#DB2777]'} hover:underline">
          <span>&larr; Back to ${isBat ? 'Batting' : 'Bowling'} Pressure Reliability</span>
        </a>
        <div class="flex items-center gap-2">
          <a href="${crossProfileHref}" class="px-3 py-1.5 rounded-lg bg-white border border-[#CBD5E1] text-[#334155] font-bold hover:bg-[#F8FAFC] transition">
            Open Full ${isBat ? 'HPP Batter' : 'BCM + PCS Bowler'} Profile &rarr;
          </a>
          <a href="#/settings?section=pri-metric-guide" class="px-3 py-1.5 rounded-lg bg-[#EFF6FF] border border-[#BFDBFE] text-[#1E3A8A] font-bold hover:bg-[#DBEAFE] transition">
            Metric Guide
          </a>
        </div>
      </div>

      <!-- Profile Hero Banner -->
      <div class="bg-white rounded-2xl border border-[#E2E8F0] border-t-4 ${isBat ? 'border-t-[#3B82F6]' : 'border-t-[#EC4899]'} p-5 sm:p-6 shadow-sm">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div class="flex flex-wrap items-center gap-2 mb-1.5">
              <span class="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase ${isBat ? 'bg-[#EFF6FF] text-[#1E3A8A]' : 'bg-[#FDF2F8] text-[#9D174D]'}">
                ${isBat ? 'Batting PRI (T10)' : 'Bowling PRI (EXO_2)'}
              </span>
              <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#F1F5F9] text-[#475569]">
                ${escapeHtml(c.primary_team || 'Team N/A')} &bull; ${c.total_matches || 0} Matches
              </span>
              ${
                !hasOpps
                  ? `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#FEF3C7] text-[#B45309]">No Pressure Opportunities</span>`
                  : ''
              }
            </div>
            <h1 class="text-2xl sm:text-3xl font-black text-[#0F172A] tracking-tight">${escapeHtml(playerName)}</h1>
            <p class="text-xs text-[#64748B] mt-1">
              ${
                isBat
                  ? `Evaluated across <strong>${opps}</strong> qualifying T10 pressure innings out of ${c.total_batted_innings} batted innings (${c.dnb_innings || 0} DNB strictly excluded).`
                  : `Evaluated across <strong>${opps}</strong> qualifying EXO_2 pressure spells out of ${c.total_spells} total spells.`
              }
            </p>
          </div>

          <!-- Highlighted Reliability Gauge -->
          <div class="p-4 rounded-2xl ${isBat ? 'bg-[#EFF6FF] border border-[#BFDBFE]' : 'bg-[#FDF2F8] border border-[#FBCFE8]'} min-w-[220px]">
            <div class="text-[10px] font-black uppercase tracking-wider text-[#64748B]">Observed Positive Reliability</div>
            ${
              hasOpps
                ? `
                  <div class="text-3xl font-black ${getPosRelTextClass(relPct)} mt-0.5">${Number(relPct).toFixed(2)}%</div>
                  <div class="text-xs font-bold text-[#334155] mt-1">
                    ${posN} Positive of <strong>${opps}</strong> ${isBat ? 'Pressure Innings' : 'Pressure Spells'}
                  </div>
                `
                : `
                  <div class="text-lg font-black text-[#64748B] mt-1">No Pressure Opportunities</div>
                  <div class="text-[11px] text-[#64748B] mt-0.5">Never assigned an artificial 0% score.</div>
                `
            }
          </div>
        </div>

        ${
          hasOpps
            ? `
            <!-- Pressure Outcome Polarity Split -->
            <div class="mt-5 pt-5 border-t border-[#F1F5F9]">
              <div class="space-y-1.5">
                <div class="flex items-center justify-between text-xs font-bold text-[#334155]">
                  <span>Pressure Outcome Breakdown</span>
                  <span>
                    <span class="text-[#16A34A]">${posN} Pos</span> &bull;
                    <span class="text-[#DC2626]">${negN} Neg</span> &bull;
                    <span class="text-[#64748B]">${neuN} Neu</span>
                  </span>
                </div>
                <div class="h-3 rounded-full overflow-hidden flex bg-[#E2E8F0]">
                  <div class="bg-[#16A34A]" style="width:${posBarPct}%" title="Positive: ${posN}"></div>
                  <div class="bg-[#94A3B8]" style="width:${neuBarPct}%" title="Neutral: ${neuN}"></div>
                  <div class="bg-[#DC2626]" style="width:${negBarPct}%" title="Negative: ${negN}"></div>
                </div>
                <p class="text-[11px] text-[#64748B]">
                  ${isBat ? 'Positive: HPC > 0 | Negative: HPC < 0 | Neutral: HPC = 0 (not counted positive).' : 'Positive: PCS > 50 | Negative: PCS < 50 | Neutral: PCS = 50 (not counted positive).'}
                </p>
              </div>
            </div>
          `
            : ''
        }
      </div>

      <!-- Career KPI Cards -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div class="bg-white rounded-xl border border-[#E2E8F0] p-3.5 shadow-xs">
          <div class="text-[10px] font-bold uppercase text-[#64748B]">${isBat ? 'Pressure Innings' : 'Pressure Spells'}</div>
          <div class="text-xl font-black text-[#0F172A] mt-0.5">${opps}</div>
        </div>
        <div class="bg-white rounded-xl border border-[#BBF7D0] p-3.5 shadow-xs">
          <div class="text-[10px] font-bold uppercase text-[#15803D]">${isBat ? 'Positive HPC' : 'Positive PCS'}</div>
          <div class="text-xl font-black text-[#16A34A] mt-0.5">${posN}</div>
        </div>
        <div class="bg-white rounded-xl border border-[#FECACA] p-3.5 shadow-xs">
          <div class="text-[10px] font-bold uppercase text-[#B91C1C]">${isBat ? 'Negative HPC' : 'Negative PCS'}</div>
          <div class="text-xl font-black text-[#DC2626] mt-0.5">${negN}</div>
        </div>
        <div class="bg-white rounded-xl border border-[#E2E8F0] p-3.5 shadow-xs">
          <div class="text-[10px] font-bold uppercase text-[#64748B]">${isBat ? 'Neutral HPC' : 'Neutral PCS'}</div>
          <div class="text-xl font-black text-[#475569] mt-0.5">${neuN}</div>
        </div>
        <div class="bg-white rounded-xl border border-[#E2E8F0] p-3.5 shadow-xs">
          <div class="text-[10px] font-bold uppercase text-[#64748B]">${isBat ? 'Avg HPC' : 'Avg PCS'}</div>
          <div class="text-xl font-black ${
            !hasOpps
              ? 'text-[#94A3B8]'
              : isBat
                ? getSignedColorClass(avgVal)
                : avgVal > 50
                  ? 'text-[#16A34A]'
                  : avgVal < 50
                    ? 'text-[#DC2626]'
                    : 'text-[#64748B]'
          } mt-0.5">${hasOpps ? (isBat ? formatSigned(avgVal, 2) : Number(avgVal).toFixed(2)) : '—'}</div>
        </div>
        <div class="bg-white rounded-xl border border-[#E2E8F0] p-3.5 shadow-xs">
          <div class="text-[10px] font-bold uppercase text-[#64748B]">${isBat ? 'Total HPC' : 'Total Contrib (RPE)'}</div>
          <div class="text-xl font-black ${hasOpps ? getSignedColorClass(totVal) : 'text-[#94A3B8]'} mt-0.5">${hasOpps ? formatSigned(totVal, 2) : '—'}</div>
        </div>
      </div>

      <!-- Season-Wise Reliability (Table + Chart) -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div class="lg:col-span-7 bg-white rounded-2xl border border-[#E2E8F0] p-5 shadow-sm space-y-3">
          <h2 class="text-sm font-black text-[#0F172A]">Season-Wise Pressure Reliability</h2>
          <div class="overflow-x-auto rounded-xl border border-[#E2E8F0]">
            <table class="w-full text-left border-collapse text-xs">
              <thead class="bg-[#F8FAFC] text-[#475569] text-[10px] uppercase font-extrabold">
                ${
                  isBat
                    ? `
                      <tr>
                        <th class="py-2.5 px-3">Season</th>
                        <th class="py-2.5 px-3 text-right">Total HPC</th>
                        <th class="py-2.5 px-3 text-right">POS REL</th>
                        <th class="py-2.5 px-3 text-right">Pressure Inns</th>
                        <th class="py-2.5 px-3 text-right">Avg HPC</th>
                        <th class="py-2.5 px-3 text-right text-[#15803D]">Pos</th>
                        <th class="py-2.5 px-3 text-right text-[#B91C1C]">Neg</th>
                        <th class="py-2.5 px-3 text-right">Neu</th>
                      </tr>
                    `
                    : `
                      <tr>
                        <th class="py-2.5 px-3">Season</th>
                        <th class="py-2.5 px-3 text-right">Opps</th>
                        <th class="py-2.5 px-3 text-right text-[#15803D]">Pos</th>
                        <th class="py-2.5 px-3 text-right text-[#B91C1C]">Neg</th>
                        <th class="py-2.5 px-3 text-right">Neu</th>
                        <th class="py-2.5 px-3 text-right">POS REL</th>
                        <th class="py-2.5 px-3 text-right">Avg PCS</th>
                      </tr>
                    `
                }
              </thead>
              <tbody class="divide-y divide-[#F1F5F9]">
                ${seasons
                  .map((s) => {
                    const n = isBat ? s.pressure_innings : s.pressure_spells;
                    const p = isBat ? s.positive_hpc_innings : s.positive_pcs_spells;
                    const ng = isBat ? s.negative_hpc_innings : s.negative_pcs_spells;
                    const nu = isBat ? s.neutral_hpc_innings : s.neutral_pcs_spells;
                    const r = isBat ? s.positive_hpc_pct : s.positive_pcs_pct;
                    const a = isBat ? s.avg_hpc_under_pressure : s.avg_pcs_under_pressure;
                    const tot = isBat ? s.total_hpc_under_pressure : s.total_pressure_contribution_rpe;
                    const relBadge = r !== null
                      ? `<span class="px-1.5 py-0.5 rounded font-black ${getPosRelBadgeClass(r)}">${Number(r).toFixed(1)}%</span>`
                      : '—';
                    if (isBat) {
                      return `
                        <tr class="hover:bg-[#F8FAFC]">
                          <td class="py-2 px-3 font-extrabold text-[#0F172A]">${escapeHtml(s.season)}</td>
                          <td class="py-2 px-3 text-right font-black ${tot !== null ? getSignedColorClass(tot) : 'text-[#94A3B8]'}">${tot !== null ? formatSigned(tot, 2) : '—'}</td>
                          <td class="py-2 px-3 text-right">${relBadge}</td>
                          <td class="py-2 px-3 text-right font-bold">${n}</td>
                          <td class="py-2 px-3 text-right font-bold">${a !== null ? formatSigned(a, 2) : '—'}</td>
                          <td class="py-2 px-3 text-right text-[#16A34A] font-bold">${p}</td>
                          <td class="py-2 px-3 text-right text-[#DC2626] font-bold">${ng}</td>
                          <td class="py-2 px-3 text-right text-[#64748B]">${nu}</td>
                        </tr>
                      `;
                    }
                    return `
                      <tr class="hover:bg-[#F8FAFC]">
                        <td class="py-2 px-3 font-extrabold text-[#0F172A]">${escapeHtml(s.season)}</td>
                        <td class="py-2 px-3 text-right font-bold">${n}</td>
                        <td class="py-2 px-3 text-right text-[#16A34A] font-bold">${p}</td>
                        <td class="py-2 px-3 text-right text-[#DC2626] font-bold">${ng}</td>
                        <td class="py-2 px-3 text-right text-[#64748B]">${nu}</td>
                        <td class="py-2 px-3 text-right">${relBadge}</td>
                        <td class="py-2 px-3 text-right font-bold">${a !== null ? Number(a).toFixed(2) : '—'}</td>
                      </tr>
                    `;
                  })
                  .join('')}
              </tbody>
            </table>
          </div>
        </div>

        <div class="lg:col-span-5 bg-white rounded-2xl border border-[#E2E8F0] p-5 shadow-sm space-y-3">
          <h2 class="text-sm font-black text-[#0F172A]">Seasonal Reliability Trajectory</h2>
          <div class="h-56 relative"><canvas id="pri-profile-season-chart"></canvas></div>
        </div>
      </div>

      <!-- Tournament-Wise Reliability Table -->
      <div class="bg-white rounded-2xl border border-[#E2E8F0] p-5 shadow-sm space-y-3">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-black text-[#0F172A]">Tournament-Wise Pressure Reliability</h2>
          <span class="text-[11px] text-[#64748B]">${tournaments.length} competitions (strictly separate per tournament)</span>
        </div>
        <div class="overflow-x-auto rounded-xl border border-[#E2E8F0]">
          <table class="w-full text-left border-collapse text-xs">
            <thead class="bg-[#F8FAFC] text-[#475569] text-[10px] uppercase font-extrabold">
              ${
                isBat
                  ? `
                    <tr>
                      <th class="py-2.5 px-3">Tournament</th>
                      <th class="py-2.5 px-3">Season</th>
                      <th class="py-2.5 px-3 text-right">Total HPC</th>
                      <th class="py-2.5 px-3 text-right">POS REL</th>
                      <th class="py-2.5 px-3 text-right">Pressure Inns</th>
                      <th class="py-2.5 px-3 text-right">Avg HPC</th>
                      <th class="py-2.5 px-3 text-right text-[#15803D]">Pos</th>
                      <th class="py-2.5 px-3 text-right text-[#B91C1C]">Neg</th>
                      <th class="py-2.5 px-3 text-right">Neu</th>
                    </tr>
                  `
                  : `
                    <tr>
                      <th class="py-2.5 px-3">Tournament</th>
                      <th class="py-2.5 px-3">Season</th>
                      <th class="py-2.5 px-3 text-right">Opps</th>
                      <th class="py-2.5 px-3 text-right text-[#15803D]">Pos</th>
                      <th class="py-2.5 px-3 text-right text-[#B91C1C]">Neg</th>
                      <th class="py-2.5 px-3 text-right">Neu</th>
                      <th class="py-2.5 px-3 text-right">POS REL</th>
                      <th class="py-2.5 px-3 text-right">Avg PCS</th>
                      <th class="py-2.5 px-3 text-right">Total RPE</th>
                    </tr>
                  `
              }
            </thead>
            <tbody class="divide-y divide-[#F1F5F9]">
              ${tournaments
                .map((t) => {
                  const n = isBat ? t.pressure_innings : t.pressure_spells;
                  const p = isBat ? t.positive_hpc_innings : t.positive_pcs_spells;
                  const ng = isBat ? t.negative_hpc_innings : t.negative_pcs_spells;
                  const nu = isBat ? t.neutral_hpc_innings : t.neutral_pcs_spells;
                  const r = isBat ? t.positive_hpc_pct : t.positive_pcs_pct;
                  const a = isBat ? t.avg_hpc_under_pressure : t.avg_pcs_under_pressure;
                  const tot = isBat ? t.total_hpc_under_pressure : t.total_pressure_contribution_rpe;
                  const relBadge = r !== null
                    ? `<span class="px-1.5 py-0.5 rounded font-black ${getPosRelBadgeClass(r)}">${Number(r).toFixed(1)}%</span>`
                    : '—';
                  if (isBat) {
                    return `
                      <tr class="hover:bg-[#F8FAFC]">
                        <td class="py-2 px-3 font-bold text-[#0F172A]">${escapeHtml(t.comp_name)}</td>
                        <td class="py-2 px-3 text-[#64748B]">${escapeHtml(t.season)}</td>
                        <td class="py-2 px-3 text-right font-black ${tot !== null ? getSignedColorClass(tot) : 'text-[#94A3B8]'}">${tot !== null ? formatSigned(tot, 2) : '—'}</td>
                        <td class="py-2 px-3 text-right">${relBadge}</td>
                        <td class="py-2 px-3 text-right font-bold">${n}</td>
                        <td class="py-2 px-3 text-right font-bold">${a !== null ? formatSigned(a, 2) : '—'}</td>
                        <td class="py-2 px-3 text-right text-[#16A34A] font-bold">${p}</td>
                        <td class="py-2 px-3 text-right text-[#DC2626] font-bold">${ng}</td>
                        <td class="py-2 px-3 text-right text-[#64748B]">${nu}</td>
                      </tr>
                    `;
                  }
                  return `
                    <tr class="hover:bg-[#F8FAFC]">
                      <td class="py-2 px-3 font-bold text-[#0F172A]">${escapeHtml(t.comp_name)}</td>
                      <td class="py-2 px-3 text-[#64748B]">${escapeHtml(t.season)}</td>
                      <td class="py-2 px-3 text-right font-bold">${n}</td>
                      <td class="py-2 px-3 text-right text-[#16A34A] font-bold">${p}</td>
                      <td class="py-2 px-3 text-right text-[#DC2626] font-bold">${ng}</td>
                      <td class="py-2 px-3 text-right text-[#64748B]">${nu}</td>
                      <td class="py-2 px-3 text-right">${relBadge}</td>
                      <td class="py-2 px-3 text-right font-bold">${a !== null ? Number(a).toFixed(2) : '—'}</td>
                      <td class="py-2 px-3 text-right font-bold ${tot !== null ? getSignedColorClass(tot) : 'text-[#94A3B8]'}">${tot !== null ? formatSigned(tot, 2) : '—'}</td>
                    </tr>
                  `;
                })
                .join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Match-Wise Qualifying Pressure Opportunities -->
      <div class="bg-white rounded-2xl border border-[#E2E8F0] p-5 shadow-sm space-y-3">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-black text-[#0F172A]">Match-Wise Qualifying Pressure ${isBat ? 'Innings (T10)' : 'Spells (EXO_2)'}</h2>
          <span class="text-[11px] text-[#64748B]">${matchRows.length} qualifying pressure appearances</span>
        </div>
        ${
          matchRows.length === 0
            ? `<div class="p-6 text-center rounded-xl bg-[#F8FAFC] border border-dashed border-[#CBD5E1] text-xs text-[#64748B]">No qualifying pressure ${isBat ? 'innings' : 'spells'} recorded for this player.</div>`
            : `
            <div class="overflow-x-auto rounded-xl border border-[#E2E8F0]">
              <table class="w-full text-left border-collapse text-xs">
                <thead class="bg-[#F8FAFC] text-[#475569] text-[10px] uppercase font-extrabold">
                  <tr>
                    <th class="py-2.5 px-3">Date</th>
                    <th class="py-2.5 px-3">Tournament</th>
                    <th class="py-2.5 px-3">Opponent</th>
                    ${
                      isBat
                        ? `
                          <th class="py-2.5 px-3 text-right">Runs (Balls)</th>
                          <th class="py-2.5 px-3 text-right">Mean P</th>
                          <th class="py-2.5 px-3 text-right">Peak P</th>
                          <th class="py-2.5 px-3 text-right">RAE</th>
                          <th class="py-2.5 px-3 text-right">HPC</th>
                          <th class="py-2.5 px-3 text-center">Outcome</th>
                        `
                        : `
                          <th class="py-2.5 px-3 text-right">Figures</th>
                          <th class="py-2.5 px-3 text-right">Econ</th>
                          <th class="py-2.5 px-3 text-right">Max Entry PTI</th>
                          <th class="py-2.5 px-3 text-right">Stand Breaks</th>
                          <th class="py-2.5 px-3 text-right">PCS Spell</th>
                          <th class="py-2.5 px-3 text-right">RPE</th>
                          <th class="py-2.5 px-3 text-center">Outcome</th>
                        `
                    }
                  </tr>
                </thead>
                <tbody class="divide-y divide-[#F1F5F9]">
                  ${matchRows
                    .map((m) => {
                      const out = isBat ? m.hpc_outcome : m.pcs_outcome;
                      const outBadge =
                        out === 'positive'
                          ? `<span class="px-2 py-0.5 rounded bg-[#DCFCE7] text-[#15803D] font-bold text-[10px]">Positive</span>`
                          : out === 'negative'
                            ? `<span class="px-2 py-0.5 rounded bg-[#FEE2E2] text-[#B91C1C] font-bold text-[10px]">Negative</span>`
                            : `<span class="px-2 py-0.5 rounded bg-[#F1F5F9] text-[#64748B] font-bold text-[10px]">Neutral</span>`;
                      return `
                        <tr class="hover:bg-[#F8FAFC]">
                          <td class="py-2 px-3 font-mono text-[11px] text-[#475569] whitespace-nowrap">${escapeHtml(m.match_date)}</td>
                          <td class="py-2 px-3 text-[#334155] max-w-[180px] truncate">${escapeHtml(m.comp_name)}</td>
                          <td class="py-2 px-3 font-semibold text-[#0F172A] whitespace-nowrap">vs ${escapeHtml(m.opponent_name || '—')}</td>
                          ${
                            isBat
                              ? `
                                <td class="py-2 px-3 text-right font-bold whitespace-nowrap">${m.runs}${m.is_out ? '' : '*'} (${m.balls})</td>
                                <td class="py-2 px-3 text-right font-mono">${Number(m.mean_p).toFixed(1)}</td>
                                <td class="py-2 px-3 text-right font-mono">${Number(m.peak_p).toFixed(1)}</td>
                                <td class="py-2 px-3 text-right font-bold ${getSignedColorClass(m.rae)}">${formatSigned(m.rae, 2)}</td>
                                <td class="py-2 px-3 text-right font-black ${getSignedColorClass(m.hpc)}">${formatSigned(m.hpc, 2)}</td>
                                <td class="py-2 px-3 text-center">${outBadge}</td>
                              `
                              : `
                                <td class="py-2 px-3 text-right font-bold whitespace-nowrap">${m.overs} ov • ${m.wickets}/${m.bowler_runs}</td>
                                <td class="py-2 px-3 text-right font-mono">${Number(m.economy).toFixed(2)}</td>
                                <td class="py-2 px-3 text-right font-mono">${Number(m.max_over_entry_pti).toFixed(1)}</td>
                                <td class="py-2 px-3 text-right font-bold">${m.stand_breaks_count || 0}</td>
                                <td class="py-2 px-3 text-right font-black ${m.pcs_spell > 50 ? 'text-[#16A34A]' : m.pcs_spell < 50 ? 'text-[#DC2626]' : 'text-[#64748B]'}">${Number(m.pcs_spell).toFixed(2)}</td>
                                <td class="py-2 px-3 text-right font-bold ${getSignedColorClass(m.total_rpe)}">${formatSigned(m.total_rpe, 2)}</td>
                                <td class="py-2 px-3 text-center">${outBadge}</td>
                              `
                          }
                        </tr>
                      `;
                    })
                    .join('')}
                </tbody>
              </table>
            </div>
          `
        }
      </div>
    </div>
  `;

  // Render Season Reliability Chart
  if (typeof Chart !== 'undefined' && seasons.length > 0) {
    const ctx = container.querySelector('#pri-profile-season-chart');
    if (ctx) {
      const evaluatedSeasons = seasons.filter((s) => s.has_pressure_opportunities);
      if (evaluatedSeasons.length > 0) {
        const vals = evaluatedSeasons.map((s) => (isBat ? s.positive_hpc_pct : s.positive_pcs_pct));
        PROFILE_CHART = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: evaluatedSeasons.map((s) => s.season),
            datasets: [
              {
                label: 'POS REL (Green ≥ 50%, Yellow < 50%)',
                data: vals,
                backgroundColor: vals.map((v) => getPosRelBarColor(v)),
                borderRadius: 6,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%` } },
            },
            plugins: { legend: { display: false } },
          },
        });
      }
    }
  }
}
