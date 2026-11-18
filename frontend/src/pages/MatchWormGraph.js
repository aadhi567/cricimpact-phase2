/**
 * CricImpact Phase 2 — Modernized Match Win Probability Worm Graph & HPP Breakdown
 * Stage B9: Light-theme Pink + Blue + Deep Navy interactive match visualization.
 * Preserves 100% of existing trajectory probabilities, key moments, and HPP/DNB scorecards.
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

const MOMENT_RICHNESS_PRIORITY = {
  largest_positive_swing: 3,
  largest_negative_swing: 3,
  major_wicket: 2,
  turning_point: 1,
  final_result: 4,
};

function parseOverBallOrder(overBall) {
  const parts = String(overBall ?? '').split('.');
  const ov = parseInt(parts[0], 10);
  const bl = parseInt(parts[1], 10);
  return [Number.isFinite(ov) ? ov : 999, Number.isFinite(bl) ? bl : 999];
}

/**
 * Deduplicate Key Turning Points caused by a single match delivery matching multiple
 * moment_type categories (e.g., largest_positive_swing + major_wicket + turning_point),
 * while strictly preserving genuinely distinct events (including final_result milestones
 * or separate deliveries at the same over.ball) and maintaining chronological order.
 */
export function deduplicateTurningPoints(moments = []) {
  if (!Array.isArray(moments) || moments.length === 0) return [];

  const dedupMap = new Map();

  moments.forEach((mom, origIdx) => {
    if (!mom || typeof mom !== 'object') return;

    const mType = String(mom.moment_type || '').toLowerCase();
    const summary = String(mom.event_summary || '').trim();
    const isFinal = mType === 'final_result' || /^final result:/i.test(summary);
    const category = isFinal ? 'final_result' : 'delivery';

    const explicitId = mom.event_id ?? mom.delivery_id ?? null;
    const hasBallIdx = mom.ball_index !== null && mom.ball_index !== undefined && mom.ball_index !== '';
    const deliveryLoc = hasBallIdx ? `ball_${mom.ball_index}` : `ob_${String(mom.over_ball ?? '').trim()}`;
    const scoreCtx = String(mom.score_context || '').trim().toLowerCase();
    const deltaKey = Math.abs(Number(mom.delta_prob || 0)).toFixed(4);
    const probAfterKey =
      mom.team_a_prob_after !== null && mom.team_a_prob_after !== undefined
        ? Number(mom.team_a_prob_after).toFixed(4)
        : 'na';
    const favoredKey = String(mom.team_favored || '').trim().toLowerCase();

    const dedupKey = explicitId !== null
      ? `${category}|id_${explicitId}`
      : `${category}|inn_${mom.innings ?? ''}|${deliveryLoc}|${scoreCtx}|d_${deltaKey}|p_${probAfterKey}|f_${favoredKey}`;

    const priority = MOMENT_RICHNESS_PRIORITY[mType] ?? 0;
    const candidate = { mom, priority, summaryLen: summary.length, origIdx, isFinal };

    const existing = dedupMap.get(dedupKey);
    if (!existing) {
      dedupMap.set(dedupKey, candidate);
    } else if (
      candidate.priority > existing.priority ||
      (candidate.priority === existing.priority && candidate.summaryLen > existing.summaryLen)
    ) {
      dedupMap.set(dedupKey, { ...candidate, origIdx: Math.min(existing.origIdx, candidate.origIdx) });
    }
  });

  const unique = Array.from(dedupMap.values());
  unique.sort((a, b) => {
    // Keep final_result milestone at the end chronologically
    if (a.isFinal !== b.isFinal) return a.isFinal ? 1 : -1;

    const innA = Number(a.mom.innings ?? 0);
    const innB = Number(b.mom.innings ?? 0);
    if (innA !== innB) return innA - innB;

    const bIdxA = a.mom.ball_index;
    const bIdxB = b.mom.ball_index;
    if (bIdxA !== null && bIdxA !== undefined && bIdxB !== null && bIdxB !== undefined && bIdxA !== bIdxB) {
      return Number(bIdxA) - Number(bIdxB);
    }

    const [ovA, blA] = parseOverBallOrder(a.mom.over_ball);
    const [ovB, blB] = parseOverBallOrder(b.mom.over_ball);
    if (ovA !== ovB) return ovA - ovB;
    if (blA !== blB) return blA - blB;

    return a.origIdx - b.origIdx;
  });

  return unique.map((u) => u.mom);
}

/**
 * Render compact Pre-Match WP (Stage A/B) and Toss / XI Adjusted probabilities
 * with dynamic team-name labels accurately mapped to team_a_prob / team_b_prob.
 */
export function renderPreMatchWpRows(stageObj, teamAName, teamBName) {
  if (
    !stageObj ||
    !stageObj.available ||
    stageObj.team_a_prob === null ||
    stageObj.team_a_prob === undefined ||
    stageObj.team_b_prob === null ||
    stageObj.team_b_prob === undefined
  ) {
    return `<div class="text-[11px] italic text-[#94A3B8]">Not Available</div>`;
  }

  const pA = (Number(stageObj.team_a_prob) * 100).toFixed(1);
  const pB = (Number(stageObj.team_b_prob) * 100).toFixed(1);
  const nameA = escapeHtml(teamAName || 'Team A');
  const nameB = escapeHtml(teamBName || 'Team B');

  return `
    <div class="space-y-0.5 text-[11px]">
      <div class="flex items-center justify-between gap-2">
        <span class="inline-flex items-center gap-1.5 text-[#334155] font-semibold truncate" title="${nameA}">
          <span class="w-1.5 h-1.5 rounded-full bg-[#EC4899] flex-shrink-0"></span>
          <span class="truncate">${nameA}</span>
        </span>
        <span class="font-mono font-black text-[#DB2777] whitespace-nowrap">${pA}%</span>
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="inline-flex items-center gap-1.5 text-[#334155] font-semibold truncate" title="${nameB}">
          <span class="w-1.5 h-1.5 rounded-full bg-[#3B82F6] flex-shrink-0"></span>
          <span class="truncate">${nameB}</span>
        </span>
        <span class="font-mono font-black text-[#2563EB] whitespace-nowrap">${pB}%</span>
      </div>
    </div>
  `;
}

export class MatchWormGraph {
  constructor() {
    this.container = null;
    this.filtersMeta = null;
    this.matchesList = [];
    this.matchData = null;
    this.chart = null;
    this.playTimer = null;
    this.currentBallIdx = 0;
    this.filterState = {
      season: 'all',
      tournament: 'all',
      team: 'all',
      search: '',
    };
  }

  cleanup() {
    if (this.playTimer) {
      clearInterval(this.playTimer);
      this.playTimer = null;
    }
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }

  async render(container, params = {}) {
    this.container = container;
    this.cleanup();
    container.innerHTML = renderLoadingSkeleton('Loading Match Win Probability Worm Graph...');

    try {
      const [meta, matchesRes] = await Promise.all([
        this.filtersMeta ? Promise.resolve(this.filtersMeta) : battingApiService.getFilters(),
        battingApiService.getMatches({ ...this.filterState, page: 1, page_size: 100 }),
      ]);
      this.filtersMeta = meta;
      this.matchesList = matchesRes.items || [];

      const requestedMatchId = params.match || params.id || (this.matchesList[0] ? this.matchesList[0].match_id : '13511');
      this.matchData = await battingApiService.getMatchDetail(requestedMatchId);
      this.currentBallIdx = Math.max(0, (this.matchData.points || []).length - 1);
      this.renderContent();
    } catch (err) {
      container.innerHTML = renderErrorState(
        `Failed to load Match Worm Graph: ${err.message}`,
        'window.location.reload()'
      );
    }
  }

  async applyMatchFilters() {
    try {
      const res = await battingApiService.getMatches({ ...this.filterState, page: 1, page_size: 100 });
      this.matchesList = res.items || [];
      if (this.matchesList.length > 0 && !this.matchesList.some((m) => m.match_id === this.matchData?.match_id)) {
        await this.loadMatch(this.matchesList[0].match_id);
      } else {
        this.renderContent();
      }
    } catch (err) {
      console.error('Match filter error:', err);
    }
  }

  async loadMatch(matchId) {
    this.cleanup();
    try {
      this.matchData = await battingApiService.getMatchDetail(matchId);
      this.currentBallIdx = Math.max(0, (this.matchData.points || []).length - 1);
      this.renderContent();
    } catch (err) {
      this.container.innerHTML = renderErrorState(
        `Unable to load match #${escapeHtml(matchId)}: ${err.message}`,
        'window.location.reload()'
      );
    }
  }

  renderContent() {
    this.cleanup();
    const m = this.matchData;
    const meta = this.filtersMeta;
    const pts = m.points || [];
    const curPt = pts[this.currentBallIdx] || pts[pts.length - 1] || null;
    document.title = `${m.team_a_name} vs ${m.team_b_name} — Worm Graph | CricImpact Phase 2`;

    const seasonOpts = [
      `<option value="all" ${this.filterState.season === 'all' ? 'selected' : ''}>All Seasons</option>`,
      ...meta.seasons.slice().reverse().map((s) => `<option value="${escapeHtml(s)}" ${this.filterState.season === s ? 'selected' : ''}>Season ${escapeHtml(s)}</option>`),
    ].join('');

    const teamOpts = [
      `<option value="all" ${this.filterState.team === 'all' ? 'selected' : ''}>All Teams</option>`,
      ...meta.teams.map((t) => `<option value="${escapeHtml(t)}" ${this.filterState.team === t ? 'selected' : ''}>${escapeHtml(t)}</option>`),
    ].join('');

    const matchOpts = this.matchesList.map((item) => {
      const sel = item.match_id === m.match_id ? 'selected' : '';
      return `<option value="${escapeHtml(item.match_id)}" ${sel}>${escapeHtml(item.date)} — ${escapeHtml(item.team_a)} vs ${escapeHtml(item.team_b)} (${escapeHtml(item.comp_name)})</option>`;
    });
    if (!this.matchesList.some((x) => x.match_id === m.match_id)) {
      matchOpts.unshift(`<option value="${escapeHtml(m.match_id)}" selected>${escapeHtml(m.match_date)} — ${escapeHtml(m.team_a_name)} vs ${escapeHtml(m.team_b_name)} (${escapeHtml(m.comp_name)})</option>`);
    }

    // Innings break probability & deduplicated chronological turning points
    const inn1End = pts.filter((p) => p.innings === 1).slice(-1)[0] || null;
    const pm = m.pre_match || {};
    const stageARows = renderPreMatchWpRows(pm.stage_a, m.team_a_name, m.team_b_name);
    const stageBRows = renderPreMatchWpRows(pm.stage_b, m.team_a_name, m.team_b_name);
    const turningPoints = deduplicateTurningPoints(m.moments || []);

    this.container.innerHTML = `
      <div class="space-y-6 animate-fade-in">
        <!-- Header & Match Switcher -->
        <section class="hero-gradient-batting rounded-2xl p-5 sm:p-6 shadow-md space-y-4">
          <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <div class="flex flex-wrap items-center gap-2 mb-1.5">
                <span class="px-2.5 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider bg-white/20 text-white">
                  Win Probability Worm &amp; HPP Match View
                </span>
                <span class="px-2.5 py-0.5 rounded-md text-[10px] font-bold bg-[#1E3A8A]/60 text-white border border-white/20">
                  Match #${escapeHtml(m.match_id)}
                </span>
                <span class="text-xs text-white/90 font-mono">${escapeHtml(m.match_date)} &bull; ${escapeHtml(m.venue_name)}</span>
              </div>
              <h1 id="page-main-heading" tabindex="-1" class="hero-title-fluid font-black text-white tracking-tight">
                ${escapeHtml(m.team_a_name)} vs ${escapeHtml(m.team_b_name)}
              </h1>
              <p class="text-xs text-white/90 mt-1">
                ${escapeHtml(m.comp_name)} &bull; <strong>${escapeHtml(m.result_text || 'Completed')}</strong>
                ${m.target_score ? ` &bull; Target: ${m.target_score}` : ''}
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <a href="#/bowling/match/${encodeURIComponent(m.match_id)}" class="px-3.5 py-2 rounded-xl bg-white text-[#1E3A8A] hover:bg-[#EFF6FF] font-bold text-xs shadow-sm transition">
                Bowling Spells &amp; PCS &rarr;
              </a>
              <a href="#/batting/dashboard" class="px-3.5 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white border border-white/25 font-bold text-xs transition">
                HPP Dashboard
              </a>
            </div>
          </div>

          <!-- Match Filter & Picker Bar -->
          <div class="pt-3 border-t border-white/20 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label for="wm-season" class="block text-[10px] font-bold uppercase tracking-wider text-white/80 mb-1">Season</label>
              <select id="wm-season" class="w-full px-3 py-2 text-xs font-semibold bg-white text-[#0F172A] rounded-xl border-0">
                ${seasonOpts}
              </select>
            </div>
            <div>
              <label for="wm-team" class="block text-[10px] font-bold uppercase tracking-wider text-white/80 mb-1">Filter by Team</label>
              <select id="wm-team" class="w-full px-3 py-2 text-xs font-semibold bg-white text-[#0F172A] rounded-xl border-0">
                ${teamOpts}
              </select>
            </div>
            <div class="sm:col-span-2">
              <label for="wm-match-select" class="block text-[10px] font-bold uppercase tracking-wider text-white/80 mb-1">Select Match (${this.matchesList.length} shown of 798)</label>
              <select id="wm-match-select" class="w-full px-3 py-2 text-xs font-semibold bg-white text-[#0F172A] rounded-xl border-0">
                ${matchOpts.join('')}
              </select>
            </div>
          </div>
        </section>

        <!-- Milestones Strip -->
        <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" aria-label="Match Probability Milestones">
          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-sm border-t-4 border-t-[#3B82F6] space-y-2">
            <div>
              <div class="text-[10px] font-bold uppercase tracking-wider text-[#64748B] mb-1">Pre-Match WP (Stage A/B)</div>
              <div id="wm-prematch-stage-a">${stageARows}</div>
            </div>
            <div class="pt-2 border-t border-[#F1F5F9]">
              <div class="text-[10px] font-bold uppercase tracking-wider text-[#1E3A8A] mb-1">Toss / XI Adjusted</div>
              <div id="wm-prematch-stage-b">${stageBRows}</div>
            </div>
          </div>
          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-sm border-t-4 border-t-[#EC4899]">
            <div class="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">Innings Break Split</div>
            <div class="text-sm font-black text-[#0F172A] mt-1">
              ${inn1End ? `${escapeHtml(m.team_a_name)} ${(inn1End.team_a_prob * 100).toFixed(1)}%` : '—'}
            </div>
            <div class="text-[11px] text-[#64748B] mt-0.5">
              ${inn1End ? `1st Inn: ${inn1End.score}/${inn1End.wickets} &bull; Target ${m.target_score || '—'}` : '—'}
            </div>
          </div>
          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-sm border-t-4 border-t-[#1E3A8A]">
            <div class="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">Selected Ball State</div>
            <div id="wm-live-score" class="text-sm font-black text-[#0F172A] mt-1">
              ${curPt ? `Inn ${curPt.innings} &bull; Ov ${curPt.over_ball} &bull; ${curPt.score}/${curPt.wickets}` : '—'}
            </div>
            <div id="wm-live-event" class="text-[11px] text-[#64748B] mt-0.5 truncate">
              ${curPt ? `${escapeHtml(curPt.event_label)} (${escapeHtml(curPt.striker_name)} vs ${escapeHtml(curPt.bowler_name)})` : '—'}
            </div>
          </div>
          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-sm border-t-4 border-t-[#16A34A]">
            <div class="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">Live Win Probability</div>
            <div id="wm-live-probs" class="text-sm font-black mt-1">
              ${curPt ? `<span class="text-[#DB2777]">${escapeHtml(m.team_a_name)} ${(curPt.team_a_prob * 100).toFixed(1)}%</span> &bull; <span class="text-[#2563EB]">${escapeHtml(m.team_b_name)} ${(curPt.team_b_prob * 100).toFixed(1)}%</span>` : '—'}
            </div>
            <div id="wm-live-delta" class="text-[11px] text-[#64748B] mt-0.5">
              ${curPt ? `Swing: ${formatSigned(curPt.delta_team_a_prob * 100, 1)}% &bull; ${curPt.runs_required !== null ? `Need ${curPt.runs_required} off ${curPt.legal_balls_remaining}` : 'Setting Target'}` : '—'}
            </div>
          </div>
        </section>

        <!-- Main Interactive Worm Graph + Key Moments -->
        <section class="grid grid-cols-1 lg:grid-cols-3 gap-5" aria-label="Interactive Win Probability Worm Chart">
          <div class="lg:col-span-2 bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 class="text-base font-black text-[#0F172A]">Win Probability Trajectory</h2>
                <p class="text-[11px] text-[#64748B]">Hover any delivery for ball-by-ball telemetry; drag scrubber to replay match momentum.</p>
              </div>
              <div class="flex items-center gap-3 text-xs font-bold">
                <span class="inline-flex items-center gap-1.5 text-[#DB2777]">
                  <span class="w-2.5 h-2.5 rounded-full bg-[#EC4899]"></span>${escapeHtml(m.team_a_name)}
                </span>
                <span class="inline-flex items-center gap-1.5 text-[#2563EB]">
                  <span class="w-2.5 h-2.5 rounded-full bg-[#3B82F6]"></span>${escapeHtml(m.team_b_name)}
                </span>
              </div>
            </div>

            <div class="relative h-72 sm:h-80 w-full">
              <canvas id="chart-worm-trajectory" aria-label="Match Win Probability Worm Chart" role="img"></canvas>
            </div>

            <!-- Interactive Scrubber & Playback Controls -->
            <div class="pt-3 border-t border-[#F1F5F9] flex flex-col sm:flex-row sm:items-center gap-3">
              <div class="flex items-center gap-2">
                <button type="button" id="wm-play-btn" class="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-[#3B82F6] to-[#EC4899] text-white text-xs font-bold shadow-xs hover:opacity-95 transition">
                  ▶ Replay
                </button>
                <button type="button" id="wm-end-btn" class="px-2.5 py-1.5 rounded-xl bg-[#F1F5F9] text-[#334155] text-xs font-bold hover:bg-[#E2E8F0] transition">
                  Full Match
                </button>
              </div>
              <div class="flex-1 flex items-center gap-2">
                <label for="wm-scrubber" class="text-[11px] font-bold text-[#64748B] whitespace-nowrap">Ball <span id="wm-ball-num">${this.currentBallIdx + 1}</span> / ${pts.length}</label>
                <input id="wm-scrubber" type="range" min="1" max="${Math.max(1, pts.length)}" value="${this.currentBallIdx + 1}" class="w-full accent-[#EC4899]">
              </div>
            </div>
          </div>

          <!-- Key Turning Points Panel -->
          <div class="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm flex flex-col justify-between space-y-4">
            <div>
              <h2 class="text-base font-black text-[#0F172A]">Key Turning Points</h2>
              <p class="text-[11px] text-[#64748B] mb-3">Click any turning point to jump the scrubber directly to that delivery.</p>
              <div id="wm-turning-points-list" class="space-y-2.5">
                ${turningPoints.length === 0 ? `<div class="text-xs text-[#64748B]">No key moments recorded for this match.</div>` : turningPoints.map((mom) => `
                  <button type="button" data-jump-ball="${mom.ball_index ?? ''}" class="w-full text-left p-3 rounded-xl bg-[#F8FAFC] hover:bg-[#EFF6FF] border border-[#E2E8F0] hover:border-[#BFDBFE] transition">
                    <div class="flex items-center justify-between gap-2 mb-1">
                      <span class="badge-pink">Inn ${mom.innings} &bull; Ov ${escapeHtml(mom.over_ball)}</span>
                      <span class="font-mono text-xs font-black text-[#1E3A8A]">Δ ${(Math.abs(mom.delta_prob || 0) * 100).toFixed(1)}%</span>
                    </div>
                    <div class="text-xs font-bold text-[#0F172A]">${escapeHtml(mom.event_summary)}</div>
                    <div class="text-[11px] text-[#64748B] mt-0.5">${escapeHtml(mom.score_context)} &bull; Favored: <strong>${escapeHtml(mom.team_favored)}</strong></div>
                  </button>
                `).join('')}
              </div>
            </div>

            <div class="pt-3 border-t border-[#F1F5F9] text-[11px] text-[#64748B]">
              <strong>Calibration:</strong> ${escapeHtml(m.calibration_method || 'Production calibrated')} (${escapeHtml(m.prediction_provenance || 'validated')})
            </div>
          </div>
        </section>

        <!-- Innings 1 & Innings 2 Batting HPP Scorecards (DNB Strictly Preserved) -->
        <section class="space-y-5" aria-label="Match Batting HPP Scorecards">
          ${this._renderInningsScorecard(1, m.team_a_name, m.innings_1_stints || [])}
          ${this._renderInningsScorecard(2, m.team_b_name, m.innings_2_stints || [])}
        </section>

        ${renderBattingMetricExplainer({ compact: true })}
      </div>
    `;

    this.bindEvents();
    this.renderWormChart();
  }

  _renderInningsScorecard(innNum, teamName, stints) {
    const accent = innNum === 1 ? 'border-t-[#EC4899]' : 'border-t-[#3B82F6]';
    const batted = stints.filter((s) => !s.is_dnb);
    const dnbCount = stints.length - batted.length;

    return `
      <div class="bg-white border border-[#E2E8F0] border-t-4 ${accent} rounded-2xl shadow-sm overflow-hidden">
        <div class="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 class="text-sm font-black text-[#0F172A]">Innings ${innNum} — ${escapeHtml(teamName || 'Team')} Batting HPP Breakdown</h2>
            <p class="text-[11px] text-[#64748B]">${batted.length} Batted${dnbCount > 0 ? ` &bull; ${dnbCount} Not Batted (DNB excluded from averages)` : ''}</p>
          </div>
        </div>

        <div class="table-wrapper" tabindex="0" role="region" aria-label="Innings ${innNum} Batting HPP Scorecard">
          <table class="text-xs text-left">
            <caption class="visually-hidden">Innings ${innNum} batting HPP scorecard for ${escapeHtml(teamName)}</caption>
            <thead class="bg-[#F8FAFC] text-[10px] font-bold uppercase tracking-wider text-[#64748B] border-b border-[#E2E8F0]">
              <tr>
                <th scope="col" class="py-2.5 px-3">Batter</th>
                <th scope="col" class="py-2.5 px-3 text-right">Runs (Balls)</th>
                <th scope="col" class="py-2.5 px-3 text-center">4s / 6s</th>
                <th scope="col" class="py-2.5 px-3 text-right">Exp Runs</th>
                <th scope="col" class="py-2.5 px-3 text-right">RAE</th>
                <th scope="col" class="py-2.5 px-3 text-right">Mean P (Peak)</th>
                <th scope="col" class="py-2.5 px-3 text-center">Tier</th>
                <th scope="col" class="py-2.5 px-3 text-center">Dismissal</th>
                <th scope="col" class="py-2.5 px-3 text-right">HPC</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[#F1F5F9]">
              ${stints.map((s) => {
                const profHref = `#/batting/players/${encodeURIComponent(s.name)}`;
                if (s.is_dnb) {
                  return `
                    <tr class="bg-[#F8FAFC]/80">
                      <th scope="row" class="py-2.5 px-3 font-semibold text-[#475569] whitespace-nowrap">
                        <a href="${profHref}" class="hover:text-[#DB2777]">${escapeHtml(s.name)}</a>
                      </th>
                      <td class="py-2.5 px-3 text-right italic text-[#64748B] font-semibold">Not Batted</td>
                      <td class="py-2.5 px-3 text-center text-[#94A3B8]">—</td>
                      <td class="py-2.5 px-3 text-right text-[#94A3B8]">—</td>
                      <td class="py-2.5 px-3 text-right text-[#94A3B8]">—</td>
                      <td class="py-2.5 px-3 text-right text-[#94A3B8]">—</td>
                      <td class="py-2.5 px-3 text-center">${getPressureTierBadge('DNB')}</td>
                      <td class="py-2.5 px-3 text-center text-[#64748B] font-semibold">Not Batted</td>
                      <td class="py-2.5 px-3 text-right font-mono text-[#94A3B8]">—</td>
                    </tr>
                  `;
                }
                return `
                  <tr class="hover:bg-[#F8FAFC] transition">
                    <th scope="row" class="py-2.5 px-3 font-bold text-[#0F172A] whitespace-nowrap">
                      <a href="${profHref}" class="hover:text-[#DB2777]">${escapeHtml(s.name)}</a>
                    </th>
                    <td class="py-2.5 px-3 text-right font-mono font-bold text-[#0F172A] whitespace-nowrap">${s.runs} <span class="text-[#64748B] font-normal">(${s.balls})</span></td>
                    <td class="py-2.5 px-3 text-center font-mono text-[#475569]">${s.fours} / ${s.sixes}</td>
                    <td class="py-2.5 px-3 text-right font-mono text-[#64748B]">${s.exp_runs !== null ? s.exp_runs.toFixed(1) : '—'}</td>
                    <td class="py-2.5 px-3 text-right font-mono font-semibold ${getSignedColorClass(s.rae)}">${formatSigned(s.rae, 2)}</td>
                    <td class="py-2.5 px-3 text-right font-mono text-[#1E3A8A] whitespace-nowrap">${s.mean_p !== null ? s.mean_p.toFixed(1) : '—'} <span class="text-[#94A3B8] text-[10px]">(${s.peak_p !== null ? s.peak_p.toFixed(0) : '—'})</span></td>
                    <td class="py-2.5 px-3 text-center">${getPressureTierBadge(s.tier)}</td>
                    <td class="py-2.5 px-3 text-center text-[#64748B] whitespace-nowrap">${s.is_out ? escapeHtml(s.dismissal_type || 'Out') : 'Not Out'}</td>
                    <td class="py-2.5 px-3 text-right font-mono font-black ${getSignedColorClass(s.hpc)}">${formatSigned(s.hpc, 2)}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  updateLiveReadout(idx) {
    const pts = this.matchData?.points || [];
    const pt = pts[idx];
    if (!pt) return;
    this.currentBallIdx = idx;

    const ballNumEl = document.getElementById('wm-ball-num');
    const scrubber = document.getElementById('wm-scrubber');
    const scoreEl = document.getElementById('wm-live-score');
    const eventEl = document.getElementById('wm-live-event');
    const probEl = document.getElementById('wm-live-probs');
    const deltaEl = document.getElementById('wm-live-delta');

    if (ballNumEl) ballNumEl.textContent = String(idx + 1);
    if (scrubber) scrubber.value = String(idx + 1);
    if (scoreEl) scoreEl.textContent = `Inn ${pt.innings} • Ov ${pt.over_ball} • ${pt.score}/${pt.wickets}`;
    if (eventEl) eventEl.textContent = `${pt.event_label} (${pt.striker_name} vs ${pt.bowler_name})`;
    if (probEl) {
      probEl.innerHTML = `<span class="text-[#DB2777]">${escapeHtml(this.matchData.team_a_name)} ${(pt.team_a_prob * 100).toFixed(1)}%</span> &bull; <span class="text-[#2563EB]">${escapeHtml(this.matchData.team_b_name)} ${(pt.team_b_prob * 100).toFixed(1)}%</span>`;
    }
    if (deltaEl) {
      const ctx = pt.runs_required !== null ? `Need ${pt.runs_required} off ${pt.legal_balls_remaining}` : 'Setting Target';
      deltaEl.textContent = `Swing: ${formatSigned(pt.delta_team_a_prob * 100, 1)}% • ${ctx}`;
    }

    if (this.chart) {
      const slicedA = pts.map((p, i) => (i <= idx ? +(p.team_a_prob * 100).toFixed(2) : null));
      const slicedB = pts.map((p, i) => (i <= idx ? +(p.team_b_prob * 100).toFixed(2) : null));
      this.chart.data.datasets[0].data = slicedA;
      this.chart.data.datasets[1].data = slicedB;
      this.chart.update('none');
    }
  }

  bindEvents() {
    const sSel = document.getElementById('wm-season');
    if (sSel) {
      sSel.addEventListener('change', (e) => {
        this.filterState.season = e.target.value;
        this.applyMatchFilters();
      });
    }

    const tSel = document.getElementById('wm-team');
    if (tSel) {
      tSel.addEventListener('change', (e) => {
        this.filterState.team = e.target.value;
        this.applyMatchFilters();
      });
    }

    const mSel = document.getElementById('wm-match-select');
    if (mSel) {
      mSel.addEventListener('change', (e) => {
        this.loadMatch(e.target.value);
      });
    }

    const scrubber = document.getElementById('wm-scrubber');
    if (scrubber) {
      scrubber.addEventListener('input', (e) => {
        if (this.playTimer) {
          clearInterval(this.playTimer);
          this.playTimer = null;
          const pb = document.getElementById('wm-play-btn');
          if (pb) pb.textContent = '▶ Replay';
        }
        this.updateLiveReadout(parseInt(e.target.value, 10) - 1);
      });
    }

    const playBtn = document.getElementById('wm-play-btn');
    if (playBtn) {
      playBtn.addEventListener('click', () => {
        const pts = this.matchData?.points || [];
        if (this.playTimer) {
          clearInterval(this.playTimer);
          this.playTimer = null;
          playBtn.textContent = '▶ Replay';
          return;
        }
        if (this.currentBallIdx >= pts.length - 1) {
          this.currentBallIdx = 0;
        }
        playBtn.textContent = '⏸ Pause';
        this.playTimer = setInterval(() => {
          if (this.currentBallIdx >= pts.length - 1) {
            clearInterval(this.playTimer);
            this.playTimer = null;
            playBtn.textContent = '▶ Replay';
            return;
          }
          this.updateLiveReadout(this.currentBallIdx + 1);
        }, 45);
      });
    }

    const endBtn = document.getElementById('wm-end-btn');
    if (endBtn) {
      endBtn.addEventListener('click', () => {
        if (this.playTimer) {
          clearInterval(this.playTimer);
          this.playTimer = null;
          const pb = document.getElementById('wm-play-btn');
          if (pb) pb.textContent = '▶ Replay';
        }
        const pts = this.matchData?.points || [];
        if (pts.length > 0) this.updateLiveReadout(pts.length - 1);
      });
    }

    document.querySelectorAll('[data-jump-ball]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const bIdx = parseInt(btn.dataset.jumpBall, 10);
        const pts = this.matchData?.points || [];
        const found = pts.findIndex((p) => p.ball_index === bIdx);
        if (found >= 0) {
          this.updateLiveReadout(found);
        }
      });
    });
  }

  renderWormChart() {
    if (typeof Chart === 'undefined') return;
    const ctx = document.getElementById('chart-worm-trajectory');
    if (!ctx) return;

    const m = this.matchData;
    const pts = m.points || [];
    const labels = pts.map((p) => `I${p.innings} ${p.over_ball}`);
    const innBreakIdx = pts.findIndex((p) => p.innings === 2);

    // Custom plugin for 50% equilibrium line & innings break marker
    const guideLinesPlugin = {
      id: 'wormGuideLines',
      beforeDatasetsDraw(chart) {
        const { ctx: c, chartArea: { left, right, top, bottom }, scales: { x, y } } = chart;
        c.save();
        // 50% line
        const y50 = y.getPixelForValue(50);
        c.strokeStyle = '#CBD5E1';
        c.lineWidth = 1;
        c.setLineDash([5, 5]);
        c.beginPath();
        c.moveTo(left, y50);
        c.lineTo(right, y50);
        c.stroke();

        // Innings break line
        if (innBreakIdx > 0) {
          const xBreak = x.getPixelForValue(innBreakIdx);
          c.strokeStyle = '#1E3A8A';
          c.lineWidth = 1.25;
          c.setLineDash([4, 4]);
          c.beginPath();
          c.moveTo(xBreak, top);
          c.lineTo(xBreak, bottom);
          c.stroke();
          c.fillStyle = '#1E3A8A';
          c.font = 'bold 10px sans-serif';
          c.fillText('Innings Break', xBreak + 5, top + 12);
        }
        c.restore();
      },
    };

    this.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: `${m.team_a_name} Win %`,
            data: pts.map((p) => +(p.team_a_prob * 100).toFixed(2)),
            borderColor: '#EC4899',
            backgroundColor: 'rgba(236, 72, 153, 0.08)',
            borderWidth: 2.5,
            fill: false,
            tension: 0.2,
            pointRadius: pts.map((p) => (p.is_wicket ? 4 : 0)),
            pointBackgroundColor: '#1E3A8A',
            pointHoverRadius: 6,
          },
          {
            label: `${m.team_b_name} Win %`,
            data: pts.map((p) => +(p.team_b_prob * 100).toFixed(2)),
            borderColor: '#3B82F6',
            backgroundColor: 'rgba(59, 130, 246, 0.08)',
            borderWidth: 2.5,
            fill: false,
            tension: 0.2,
            pointRadius: 0,
            pointHoverRadius: 5,
          },
        ],
      },
      plugins: [guideLinesPlugin],
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        onClick: (_, elements) => {
          if (elements.length > 0) {
            this.updateLiveReadout(elements[0].index);
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            titleColor: '#FFFFFF',
            bodyColor: '#E2E8F0',
            padding: 10,
            callbacks: {
              title: (items) => {
                const p = pts[items[0].dataIndex];
                return `Inn ${p.innings} • Ov ${p.over_ball} • ${p.score}/${p.wickets}`;
              },
              afterBody: (items) => {
                const p = pts[items[0].dataIndex];
                const lines = [
                  `Event: ${p.event_label}`,
                  `Batter: ${p.striker_name} | Bowler: ${p.bowler_name}`,
                  `WP Swing: ${formatSigned(p.delta_team_a_prob * 100, 1)}%`,
                ];
                if (p.runs_required !== null) {
                  lines.push(`Chase: Need ${p.runs_required} off ${p.legal_balls_remaining} balls`);
                }
                return lines;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { maxTicksLimit: 10, color: '#64748B', font: { size: 10 } },
            grid: { display: false },
          },
          y: {
            min: 0,
            max: 100,
            ticks: { callback: (v) => `${v}%`, color: '#64748B', font: { size: 10 } },
            grid: { color: '#F1F5F9' },
          },
        },
      },
    });
  }
}

const instance = new MatchWormGraph();
export function renderMatchWormGraph(container, params) {
  return instance.render(container, params);
}
