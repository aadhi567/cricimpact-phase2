/**
 * Stage PRI-3: Automated Frontend Unit & Contract Test Suite (Node native test runner)
 * Run with: node --test tests/frontend/test_pri_frontend.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { PRI_BASE, PRI_API_ENDPOINTS } from '../../frontend/src/config/apiConfig.js';
import { priApiService } from '../../frontend/src/services/priApiService.js';
import {
  validateCustomMinInput,
  getPosRelBadgeClass,
  getPosRelTextClass,
  getPosRelBarColor,
} from '../../frontend/src/pages/PressureReliabilityPage.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');

function readText(relPath) {
  return fs.readFileSync(path.join(ROOT, relPath), 'utf-8');
}

test('PRI_API_ENDPOINTS match backend /api/pri contract', () => {
  assert.equal(PRI_BASE, '/api/pri');
  assert.equal(PRI_API_ENDPOINTS.HEALTH, '/api/pri/health');
  assert.equal(PRI_API_ENDPOINTS.OVERVIEW, '/api/pri/overview');
  assert.equal(PRI_API_ENDPOINTS.FILTERS, '/api/pri/filters');
  assert.equal(PRI_API_ENDPOINTS.BATTING_CAREER, '/api/pri/batting/career');
  assert.equal(PRI_API_ENDPOINTS.BATTING_SEASON, '/api/pri/batting/season');
  assert.equal(PRI_API_ENDPOINTS.BATTING_TOURNAMENT, '/api/pri/batting/tournament');
  assert.equal(PRI_API_ENDPOINTS.BOWLING_CAREER, '/api/pri/bowling/career');
  assert.equal(PRI_API_ENDPOINTS.BOWLING_SEASON, '/api/pri/bowling/season');
  assert.equal(PRI_API_ENDPOINTS.BOWLING_TOURNAMENT, '/api/pri/bowling/tournament');
  assert.equal(PRI_API_ENDPOINTS.BATTING_PLAYER(1699), '/api/pri/batting/players/1699');
  assert.equal(PRI_API_ENDPOINTS.BOWLING_PLAYER(6523), '/api/pri/bowling/players/6523');
  assert.equal(PRI_API_ENDPOINTS.BATTING_COMPARE([1699, 6396]), '/api/pri/batting/compare?player_ids=1699,6396');
  assert.equal(PRI_API_ENDPOINTS.BOWLING_COMPARE([6523, 2984]), '/api/pri/bowling/compare?player_ids=6523,2984');
});

test('Custom minimum opportunity input accepts valid non-negative whole integers', () => {
  for (const [raw, expected] of [
    ['0', 0],
    ['', 0],
    ['1', 1],
    ['12', 12],
    ['18', 18],
    [' 25 ', 25],
    ['150', 150],
  ]) {
    const res = validateCustomMinInput(raw);
    assert.equal(res.valid, true, `Expected valid for "${raw}"`);
    assert.equal(res.value, expected);
    assert.equal(res.error, null);
  }
});

test('Custom minimum opportunity input strictly rejects negative, decimal, and invalid inputs', () => {
  for (const bad of ['-1', '-15', '5.5', '0.1', '12.0', 'abc', '12x', 'NaN', 'Infinity']) {
    const res = validateCustomMinInput(bad);
    assert.equal(res.valid, false, `Expected invalid for "${bad}"`);
    assert.equal(res.value, null);
    assert.ok(res.error && res.error.length > 5);
  }
});

test('priApiService._buildQuery encodes scope, custom min, team, search, sort & pagination', () => {
  const q = priApiService._buildQuery({
    min_opportunities: 12,
    season: '2025',
    team: 'India',
    search: 'Surya',
    sort_by: 'positive_hpc_pct',
    order: 'desc',
    page: 2,
    page_size: 20,
  });
  assert.ok(q.includes('min_opportunities=12'));
  assert.ok(q.includes('season=2025'));
  assert.ok(q.includes('team=India'));
  assert.ok(q.includes('search=Surya'));
  assert.ok(q.includes('sort_by=positive_hpc_pct'));
  assert.ok(q.includes('page=2'));
  assert.ok(q.includes('page_size=20'));
});

test('Navigation sidebar and index.html register Pressure Reliability routes cleanly', () => {
  const navSrc = readText('frontend/src/components/Navigation.js');
  const htmlSrc = readText('frontend/index.html');

  assert.ok(navSrc.includes('href="#/pressure-reliability"'));
  assert.ok(navSrc.includes('Pressure Reliability'));

  assert.ok(htmlSrc.includes("router.addRoute('/pressure-reliability'"));
  assert.ok(htmlSrc.includes("router.addRoute('/pressure-reliability/batting'"));
  assert.ok(htmlSrc.includes("router.addRoute('/pressure-reliability/bowling'"));
  assert.ok(htmlSrc.includes("router.addRoute('/pressure-reliability/batting/player/:id'"));
  assert.ok(htmlSrc.includes("router.addRoute('/pressure-reliability/bowling/player/:id'"));
});

test('PressureReliabilityPage includes required titles, tabs, custom min inputs & 5 charts with ZERO Wilson CI UI', () => {
  const src = readText('frontend/src/pages/PressureReliabilityPage.js');

  assert.ok(src.includes('Most Reliable Batters Under Pressure'));
  assert.ok(src.includes('Most Reliable Bowlers Under Pressure'));
  assert.ok(src.includes('Batting Reliability'));
  assert.ok(src.includes('Bowling Reliability'));
  assert.ok(src.includes('Minimum Pressure Innings'));
  assert.ok(src.includes('Minimum Pressure Spells'));
  assert.ok(src.includes('not individual player ratings'));

  // All 5 domain charts + comparison chart
  for (const canvasId of [
    'pri-chart-polarity',
    'pri-chart-season-rate',
    'pri-chart-season-avg',
    'pri-chart-season-total',
    'pri-chart-scatter',
    'pri-chart-compare',
  ]) {
    assert.ok(src.includes(canvasId), `Missing chart canvas: ${canvasId}`);
  }

  // Strictly NO Wilson CI elements anywhere in PressureReliabilityPage
  for (const forbidden of ['wilson', 'ci95', 'ci90', 'renderCiBar', '95% CI', '90% CI', 'Confidence Interval', 'sample_confidence_tier', 'Provisional']) {
    assert.equal(src.toLowerCase().includes(forbidden.toLowerCase()), false, `Found forbidden Wilson CI UI token "${forbidden}" in PressureReliabilityPage.js`);
  }
});

test('PRIPlayerProfilePage handles career, season, tournament, match tables & zero-opportunity state with ZERO Wilson CI UI', () => {
  const src = readText('frontend/src/pages/PRIPlayerProfilePage.js');
  assert.ok(src.includes('Season-Wise Pressure Reliability'));
  assert.ok(src.includes('Tournament-Wise Pressure Reliability'));
  assert.ok(src.includes('Match-Wise Qualifying Pressure'));
  assert.ok(src.includes('No Pressure Opportunities'));
  assert.ok(src.includes('Never assigned an artificial 0% score'));

  // Strictly NO Wilson CI elements anywhere in PRIPlayerProfilePage
  for (const forbidden of ['wilson', 'ci95', 'ci90', '95% CI', '90% CI', 'Confidence Interval', 'sample_confidence_tier', 'Provisional']) {
    assert.equal(src.toLowerCase().includes(forbidden.toLowerCase()), false, `Found forbidden Wilson CI UI token "${forbidden}" in PRIPlayerProfilePage.js`);
  }
});

test('SettingsPage integrates PRI Metric Guide without Wilson CI UI', () => {
  const src = readText('frontend/src/pages/SettingsPage.js');
  assert.ok(src.includes('id="pri-metric-guide"'));
  assert.ok(src.includes('Batting PRI (T10)'));
  assert.ok(src.includes('Bowling PRI (EXO_2)'));
  assert.ok(src.includes('mean_p &ge; 40 OR peak_p &ge; 60'));
  assert.ok(src.includes('max_over_entry_pti &ge; 35 AND legal_balls &ge; 12'));
  assert.ok(src.includes('Positive Reliability %'));
  assert.ok(src.includes('Pressure Quality'));
  assert.ok(src.includes('PRI does not measure total career greatness'));

  for (const forbidden of ['wilson', 'Confidence Interval']) {
    assert.equal(src.toLowerCase().includes(forbidden.toLowerCase()), false, `Found forbidden Wilson CI token "${forbidden}" in SettingsPage.js`);
  }
});

test('POS REL color coding: Green for >= 50%, Yellow for < 50%, NEVER red', () => {
  // >= 50% -> Green
  for (const v of [50, 50.0, 56.52, 100]) {
    assert.ok(getPosRelBadgeClass(v).includes('#DCFCE7') && getPosRelBadgeClass(v).includes('#15803D'));
    assert.ok(getPosRelTextClass(v).includes('#16A34A'));
    assert.ok(getPosRelBarColor(v).includes('22, 163, 74'));
  }

  // < 50% -> Yellow (never red)
  for (const v of [0, 26.93, 49.99]) {
    const badge = getPosRelBadgeClass(v);
    const txt = getPosRelTextClass(v);
    const bar = getPosRelBarColor(v);
    assert.ok(badge.includes('#FEF9C3') && badge.includes('#854D0E'), `Expected yellow badge for ${v}, got ${badge}`);
    assert.ok(txt.includes('#CA8A04'), `Expected yellow text for ${v}, got ${txt}`);
    assert.ok(bar.includes('234, 179, 8'), `Expected yellow bar for ${v}, got ${bar}`);
    for (const redToken of ['#FEF2F2', '#FEE2E2', '#B91C1C', '#DC2626', 'red', 'rose']) {
      assert.equal(badge.toLowerCase().includes(redToken.toLowerCase()), false);
      assert.equal(txt.toLowerCase().includes(redToken.toLowerCase()), false);
      assert.equal(bar.toLowerCase().includes(redToken.toLowerCase()), false);
    }
  }
});

test('Batting leaderboard and comparison visuals enforce order: Rank -> Player -> Total HPC -> POS REL -> Pressure Innings', () => {
  const priSrc = readText('frontend/src/pages/PressureReliabilityPage.js');
  const dashSrc = readText('frontend/src/pages/BattingDashboard.js');
  const profSrc = readText('frontend/src/pages/PRIPlayerProfilePage.js');

  // 1. PRI Batting Leaderboard header order
  const thRank = priSrc.indexOf('>Rank</th>');
  const thPlayer = priSrc.indexOf('>Player</th>');
  const thTotalHpc = priSrc.indexOf('>Total HPC</th>');
  const thPosRel = priSrc.indexOf('>POS REL</th>');
  const thPressInns = priSrc.indexOf('>Pressure Innings</th>');
  assert.ok(thRank > 0 && thPlayer > thRank && thTotalHpc > thPlayer && thPosRel > thTotalHpc && thPressInns > thPosRel,
    'PRI Batting Leaderboard must follow Rank -> Player -> Total HPC -> POS REL -> Pressure Innings');

  // 2. PRI Batting Comparison cards order (Total HPC before POS REL before Pressure Innings)
  const cmpStart = priSrc.indexOf('if (isBat) {\n            return `');
  assert.ok(cmpStart > 0);
  const cmpBlock = priSrc.slice(cmpStart, cmpStart + 1200);
  const cTot = cmpBlock.indexOf('>Total HPC</div>');
  const cRel = cmpBlock.indexOf('>POS REL</div>');
  const cInns = cmpBlock.indexOf('>Pressure Innings</div>');
  assert.ok(cTot > 0 && cRel > cTot && cInns > cRel,
    'PRI Batting Comparison cards must follow Total HPC -> POS REL -> Pressure Innings');

  // 3. Batting Dashboard Top 10 Spotlight places Total HPC before POS REL
  const dTot = dashSrc.indexOf('>Total HPC</th>');
  const dRel = dashSrc.indexOf('>POS REL</th>');
  assert.ok(dTot > 0 && dRel > dTot, 'Batting Dashboard Top 10 must place Total HPC before POS REL');

  // 4. Batter PRI Profile Season & Tournament tables place Total HPC before POS REL before Pressure Inns
  const pTot = profSrc.indexOf('>Total HPC</th>');
  const pRel = profSrc.indexOf('>POS REL</th>');
  const pInns = profSrc.indexOf('>Pressure Inns</th>');
  assert.ok(pTot > 0 && pRel > pTot && pInns > pRel,
    'Batter PRI Profile tables must place Total HPC -> POS REL -> Pressure Inns');
});
