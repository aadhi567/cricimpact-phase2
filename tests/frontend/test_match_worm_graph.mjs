/**
 * Automated Unit & Corpus-Wide Verification for Match Worm Graph Fixes:
 * 1. Key Turning Points duplicate prevention (preserving distinct events & chronological order).
 * 2. Dynamic team names for Pre-Match WP (Stage A/B) and Toss / XI Adjusted.
 *
 * Run with: node --test tests/frontend/test_match_worm_graph.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  deduplicateTurningPoints,
  renderPreMatchWpRows,
} from '../../frontend/src/pages/MatchWormGraph.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const TRAJ_DIR = path.join(ROOT, 'docs', 'worm_graph', 'trajectories');
const INDEX_PATH = path.join(ROOT, 'docs', 'worm_graph', 'match_index.json');

function loadMatch(id) {
  return JSON.parse(fs.readFileSync(path.join(TRAJ_DIR, `${id}.json`), 'utf-8'));
}

test('Match #50387 (GT vs CSK): duplicate Inn 2 Ov 1.1 wicket collapsed to 1 richest entry + final_result preserved', () => {
  const m = loadMatch(50387);
  assert.equal(m.moments.length, 3); // Raw has largest_positive_swing + major_wicket + final_result

  const deduped = deduplicateTurningPoints(m.moments);
  assert.equal(deduped.length, 2);
  assert.equal(deduped[0].innings, 2);
  assert.equal(deduped[0].over_ball, '1.1');
  assert.equal(deduped[0].event_summary, 'WICKET (Caught) (Mohammed Siraj to Sanju Samson)');
  assert.equal(deduped[0].delta_prob, 0.1775);
  assert.equal(deduped[0].team_favored, 'Gujarat Titans');

  assert.equal(deduped[1].moment_type, 'final_result');
  assert.ok(deduped[1].event_summary.includes('Gujarat Titans Won by 89 runs'));
});

test('Match #13523 (IND vs WI): triple duplicate on same delivery collapses cleanly to 1 richest entry', () => {
  const m = loadMatch(13523);
  const rawInn2_19_3 = m.moments.filter((x) => x.innings === 2 && x.over_ball === '19.3');
  assert.equal(rawInn2_19_3.length, 3);

  const deduped = deduplicateTurningPoints(m.moments);
  const kept = deduped.filter((x) => x.innings === 2 && x.over_ball === '19.3');
  assert.equal(kept.length, 1);
  assert.equal(kept[0].event_summary, 'WICKET (Caught) (Bhuvneshwar Kumar to Nicholas Pooran)');
  assert.equal(kept[0].delta_prob, 0.3137);
});

test('Match #14109 (final-ball winning SIX): delivery duplicate removed while distinct final_result milestone preserved', () => {
  const m = loadMatch(14109);
  const deduped = deduplicateTurningPoints(m.moments);
  const ov20_7 = deduped.filter((x) => x.innings === 2 && x.over_ball === '20.7');
  assert.equal(ov20_7.length, 2);
  assert.equal(ov20_7[0].event_summary, 'SIX (6 runs) (Odean Smith to Rahul Tewatia)');
  assert.equal(ov20_7[1].moment_type, 'final_result');
  assert.ok(ov20_7[1].event_summary.includes('Final Result:'));
});

test('Genuinely distinct events at the SAME over/ball (e.g. wide/no-ball + re-bowled delivery) are NOT wrongly removed', () => {
  const synthetic = [
    {
      moment_type: 'major_wicket',
      innings: 2,
      ball_index: 201,
      over_ball: '19.4',
      delta_prob: 0.145,
      team_favored: 'Team A',
      event_summary: 'WICKET (Stumped off Wide) (Bowler X to Batter Y)',
      score_context: 'Inn 2 | 160/4',
      team_a_prob_after: 0.65,
    },
    {
      moment_type: 'largest_negative_swing',
      innings: 2,
      ball_index: 202,
      over_ball: '19.4',
      delta_prob: 0.22,
      team_favored: 'Team B',
      event_summary: 'SIX (6 runs) (Bowler X to Batter Z)',
      score_context: 'Inn 2 | 161/5',
      team_a_prob_after: 0.43,
    },
  ];
  const deduped = deduplicateTurningPoints(synthetic);
  assert.equal(deduped.length, 2);
  assert.equal(deduped[0].ball_index, 201);
  assert.equal(deduped[1].ball_index, 202);
});

test('Explicit event_id deduplicates matching IDs while keeping distinct IDs at same over/ball', () => {
  const synthetic = [
    { event_id: 'ev-100', moment_type: 'major_wicket', innings: 1, over_ball: '5.2', delta_prob: 0.1, event_summary: 'WICKET by Bowler A' },
    { event_id: 'ev-100', moment_type: 'largest_positive_swing', innings: 1, over_ball: '5.2', delta_prob: 0.1, event_summary: 'WICKET (Bowler A to Batter B)' },
    { event_id: 'ev-101', moment_type: 'turning_point', innings: 1, over_ball: '5.2', delta_prob: 0.12, event_summary: 'SIX on free hit' },
  ];
  const deduped = deduplicateTurningPoints(synthetic);
  assert.equal(deduped.length, 2);
  assert.equal(deduped[0].event_summary, 'WICKET (Bowler A to Batter B)');
  assert.equal(deduped[1].event_id, 'ev-101');
});

test('Corpus-wide verification across all 798 matches: zero duplicate delivery events and strict chronological order', () => {
  const files = fs.readdirSync(TRAJ_DIR).filter((f) => f.endsWith('.json'));
  assert.equal(files.length, 798);

  let totalRaw = 0;
  let totalDeduped = 0;

  for (const fname of files) {
    const d = JSON.parse(fs.readFileSync(path.join(TRAJ_DIR, fname), 'utf-8'));
    const raw = d.moments || [];
    totalRaw += raw.length;
    const deduped = deduplicateTurningPoints(raw);
    totalDeduped += deduped.length;

    // Verify no duplicate non-final delivery states remain
    const seen = new Set();
    let prevInPlayKey = null;
    for (let i = 0; i < deduped.length; i++) {
      const mom = deduped[i];
      const isFinal = mom.moment_type === 'final_result';
      if (isFinal) {
        assert.equal(i, deduped.length - 1, `final_result must be last in match ${d.match_id}`);
        continue;
      }
      const key = `${mom.innings}|${mom.over_ball}|${mom.score_context}|${Math.abs(mom.delta_prob || 0).toFixed(4)}`;
      assert.equal(seen.has(key), false, `Duplicate turning point remained in match ${d.match_id}: ${key}`);
      seen.add(key);

      // Verify chronological order across in-play moments
      const [ov, bl] = String(mom.over_ball).split('.').map((n) => parseInt(n, 10));
      const curOrder = [Number(mom.innings), ov, bl];
      if (prevInPlayKey) {
        const cmp =
          curOrder[0] !== prevInPlayKey[0]
            ? curOrder[0] - prevInPlayKey[0]
            : curOrder[1] !== prevInPlayKey[1]
              ? curOrder[1] - prevInPlayKey[1]
              : curOrder[2] - prevInPlayKey[2];
        assert.ok(cmp >= 0, `Out-of-order turning points in match ${d.match_id}: ${prevInPlayKey} -> ${curOrder}`);
      }
      prevInPlayKey = curOrder;
    }
  }

  assert.ok(totalRaw > totalDeduped, `Expected duplicate removal across 798 matches (${totalRaw} -> ${totalDeduped})`);
});

test('Pre-Match WP & Toss/XI Adjusted dynamically render actual match team names and exact percentages', () => {
  const indexList = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf-8'));
  const byId = Object.fromEntries(indexList.map((x) => [String(x.id), x]));

  // 1. Match #50387: Gujarat Titans (58.6% / 58.8%) vs Chennai Super Kings (41.4% / 41.2%)
  const m50387 = loadMatch(50387);
  const pm50387 = byId['50387'].pre_match;
  const htmlA1 = renderPreMatchWpRows(pm50387.stage_a, m50387.team_a_name, m50387.team_b_name);
  const htmlB1 = renderPreMatchWpRows(pm50387.stage_b, m50387.team_a_name, m50387.team_b_name);

  assert.ok(htmlA1.includes('Gujarat Titans') && htmlA1.includes('58.6%'));
  assert.ok(htmlA1.includes('Chennai Super Kings') && htmlA1.includes('41.4%'));
  assert.ok(htmlB1.includes('Gujarat Titans') && htmlB1.includes('58.8%'));
  assert.ok(htmlB1.includes('Chennai Super Kings') && htmlB1.includes('41.2%'));

  // Verify order: Team A (Gujarat Titans) appears before Team B (Chennai Super Kings)
  assert.ok(htmlA1.indexOf('Gujarat Titans') < htmlA1.indexOf('Chennai Super Kings'));
  assert.ok(htmlA1.indexOf('58.6%') < htmlA1.indexOf('41.4%'));

  // 2. Switch to a completely different match: #50375 (Mumbai Indians vs Royal Challengers Bengaluru)
  const m50375 = loadMatch(50375);
  const pm50375 = byId['50375'].pre_match;
  const htmlA2 = renderPreMatchWpRows(pm50375.stage_a, m50375.team_a_name, m50375.team_b_name);
  assert.ok(htmlA2.includes('Mumbai Indians'));
  assert.ok(htmlA2.includes('Royal Challengers Bengaluru'));
  assert.equal(htmlA2.includes('Gujarat Titans'), false);

  // 3. Unavailable pre-match state handled gracefully
  const htmlNA = renderPreMatchWpRows({ available: false, team_a_prob: null, team_b_prob: null }, 'India', 'Australia');
  assert.ok(htmlNA.includes('Not Available'));
  assert.equal(htmlNA.includes('NaN'), false);
});
