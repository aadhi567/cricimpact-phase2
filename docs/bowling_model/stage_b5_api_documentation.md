# CricImpact Phase 2 — Stage B5: Bowling Analytics API Documentation

## 1. Overview & Architecture

The **CricImpact Bowling Analytics API** provides high-performance, strictly read-only access to the verified Stage B4 **Bowling Contribution Model (BCM)** outputs. The API exposes granular bowling analytics across 798 standard T20 matches, 190,575 delivery transitions, 9,482 bowler match spells, 1,587 season records, and 638 career bowlers.

### Core Architectural Principles
1. **Strictly Read-Only Access**: The API layer serves historical outputs from verified production artifacts (`bowling_career_summary_v1.pkl.gz`, `bowling_season_summary_v1.pkl.gz`, `bowling_match_spells_v1.pkl.gz`, `bowling_delivery_contributions_v1.pkl.gz`). No model recalculation occurs at the API layer.
2. **In-Memory Singleton Service**: `BowlingDataService` loads and indexes all data during application lifespan startup, providing sub-millisecond O(1) lookups for player profiles, match spells, and delivery sequences.
3. **Strict Metric Isolation**: Bowling Contribution Score ($BCS$, denominated in runs) and Bowler Win Probability Added ($bWPA$, denominated in probability swing $[-1.0, +1.0]$) are maintained in strict isolation and are never conflated.
4. **Cricket Domain Formatting**: Overs are presented in both decimal and standard cricket notation (` legal_balls // 6 . legal_balls % 6 `), with economy strictly calculated as $\text{Runs} \times 6.0 / \text{Legal Balls}$.
5. **Standards-Compliant JSON**: All `NaN` and `Infinity` float values are converted to standard JSON `null`.

---

## 2. Server Information

- **Base URL**: `http://127.0.0.1:8000`
- **API Prefix**: `/api/bowling`
- **OpenAPI Schema**: `/openapi.json`
- **Interactive Documentation**: `/docs` (Swagger UI) and `/redoc` (ReDoc)

---

## 3. Endpoint Catalog

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` / `/api/health` | Health check & verified corpus data summary |
| `GET` | `/api/bowling/dashboard` | Corpus-wide KPIs, BCS distributions, phase breakdown, top performers |
| `GET` | `/api/bowling/leaderboard` | Paginated, filterable, and sortable bowling leaderboard |
| `GET` | `/api/bowling/players/{player_id}` | Detailed bowler profile with career, phase splits, seasons, and spells |
| `GET` | `/api/bowling/compare` | Head-to-head comparison between 2 and 5 bowlers |
| `GET` | `/api/bowling/matches` | Paginated match directory with top match bowler summaries |
| `GET` | `/api/bowling/matches/{match_id}/spells` | All bowling spells for a specific match |
| `GET` | `/api/bowling/spells/{spell_id}/deliveries` | Ball-by-ball delivery transitions and model metrics for a spell |

---

## 4. Endpoint Specifications

### 4.1. System Health Check
**Endpoint**: `GET /health` or `GET /api/health`

Returns the operational status of the service and confirms loaded dataset row counts.

#### Response Example (200 OK)
```json
{
  "status": "healthy",
  "service_initialized": true,
  "corpus_matches": 798,
  "career_bowlers": 638,
  "match_spells": 9482,
  "deliveries": 190575
}
```

---

### 4.2. Bowling Analytics Dashboard
**Endpoint**: `GET /api/bowling/dashboard`

Provides macro-level indicators across the entire Phase 2 bowling corpus.

#### Response Schema
- `total_matches`: Total standard T20 matches evaluated (798).
- `total_spells`: Total bowling spells (9,482).
- `total_deliveries`: Total balls bowled including extras (190,575).
- `legal_balls`: Total legal deliveries (182,504).
- `total_wickets`: Total bowler-credited wickets (9,662).
- `total_bowler_runs`: Total runs conceded off bowler spells.
- `overall_economy`: Corpus economy rate (8.71).
- `dot_ball_pct`: Corpus dot ball percentage.
- `bcs_distribution`: Statistical distribution of spell BCS ($mean$, $median$, $std$, $min$, $max$, $p25$, $p75$, $positive\_share\_pct$, $negative\_share\_pct$).
- `phase_breakdown`: List of metrics aggregated by match phase (`powerplay`, `middle`, `death`).
- `top_career_bcs`: Top 5 bowlers by career BCS.
- `top_career_bwpa`: Top 5 bowlers by career bWPA.
- `top_match_spells`: Top 5 individual match spells by BCS.

#### Curl Example
```bash
curl -X GET "http://127.0.0.1:8000/api/bowling/dashboard" -H "accept: application/json"
```

---

### 4.3. Bowling Leaderboard
**Endpoint**: `GET /api/bowling/leaderboard`

Filterable, sortable, and paginated leaderboard of bowler contributions.

#### Query Parameters
| Parameter | Type | Default | Description |
|---|---|---|---|
| `season` | string | `null` | Filter by season (e.g. `'2024'`, `'2023/24'`) or omit/`'all'` for career. |
| `phase` | string | `null` | Filter by match phase (`'powerplay'`, `'middle'`, `'death'`). |
| `min_balls` | integer | `60` | Minimum legal balls threshold ($\ge 0$). |
| `sort_by` | string | `'total_bcs'` | Sort metric: `total_bcs`, `shrunk_bcs` (`total_bcs_shrunk`), `total_bwpa`, `bcs_per_over`, `shrunk_bcs_per_over`, `wickets`, `economy`, `dot_pct`, `strike_rate`, `bowling_average`, `legal_balls`, `total_erp`. |
| `order` | string | `'desc'` | Sort order (`'desc'` or `'asc'`). |
| `page` | integer | `1` | 1-based page number ($\ge 1$). |
| `page_size` | integer | `20` | Results per page ($1 \le \text{page\_size} \le 100$). |

#### Curl Example
```bash
curl -X GET "http://127.0.0.1:8000/api/bowling/leaderboard?phase=death&min_balls=60&sort_by=total_bcs&page=1&page_size=5"
```

#### Response Example (200 OK)
```json
{
  "status": "success",
  "season_filter": null,
  "phase_filter": "death",
  "min_balls_filter": 60,
  "sort_by": "total_bcs",
  "order": "desc",
  "pagination": {
    "total_items": 178,
    "total_pages": 36,
    "current_page": 1,
    "page_size": 5
  },
  "items": [
    {
      "rank": 1,
      "bowler_id": 4722,
      "bowler_name": "Rashid Khan",
      "matches": 117,
      "spells": 117,
      "legal_balls": 516,
      "overs": 86.0,
      "overs_formatted": "86.0",
      "bowler_runs": 723,
      "wickets": 45,
      "maidens": 0,
      "dot_balls": 182,
      "boundaries": 66,
      "economy": 8.41,
      "dot_pct": 35.3,
      "boundary_pct": 12.8,
      "strike_rate": 11.5,
      "bowling_average": 16.07,
      "total_erp": 48.04,
      "mean_leverage": 1.223,
      "mean_wqm": 1.0,
      "total_bcs": 437.52,
      "bcs_per_over": 5.09,
      "shrunk_bcs_per_over": null,
      "total_bcs_shrunk": null,
      "shrunk_bcs": null,
      "total_bwpa": 3.3093
    }
  ]
}
```

---

### 4.4. Bowler Profile
**Endpoint**: `GET /api/bowling/players/{player_id}`

Fetches the complete historical dossier for a single bowler.

#### Path Parameters
- `player_id` (integer, required): Unique identifier of the bowler (e.g. `4722` for Rashid Khan, `6464` for Arshdeep Singh).

#### Response Schema
- `bowler_id`: Integer ID.
- `bowler_name`: Full player name.
- `career_summary`: Complete career leaderboard item.
- `phase_splits`: 3-phase performance breakdown (`powerplay`, `middle`, `death`).
- `season_breakdown`: Year-by-year performance list.
- `top_spells`: Top 5 matches ranked by match spell BCS.
- `recent_spells`: 5 most recent match spells.

#### Curl Example
```bash
curl -X GET "http://127.0.0.1:8000/api/bowling/players/4722"
```

---

### 4.5. Bowler Comparison
**Endpoint**: `GET /api/bowling/compare`

Facilitates head-to-head comparison between 2 and 5 bowlers.

#### Query Parameters
- `player_ids` (string, required): Comma-separated list of player IDs (e.g. `?player_ids=4722,6464,6256`).

#### Validation Constraints
- Must contain between 2 and 5 player IDs.
- Duplicate IDs are rejected with HTTP 422.
- Non-existent player IDs return HTTP 404.

#### Curl Example
```bash
curl -X GET "http://127.0.0.1:8000/api/bowling/compare?player_ids=4722,6464,6256"
```

---

### 4.6. Matches Directory & Match Spells
**Endpoint 1**: `GET /api/bowling/matches`
Lists matches with metadata, competing teams, total spells, and top match bowler.

#### Query Parameters
- `season`: Optional season filter.
- `team`: Optional team substring search.
- `sort_by`: `'match_date'`, `'total_bcs'`, or `'match_id'`.
- `order`: `'desc'` or `'asc'`.
- `page`: Page index.
- `page_size`: Page limit.

**Endpoint 2**: `GET /api/bowling/matches/{match_id}/spells`
Retrieves all bowling spells from both innings of a match, sorted by innings and spell BCS.

#### Curl Example
```bash
curl -X GET "http://127.0.0.1:8000/api/bowling/matches/13511/spells"
```

---

### 4.7. Spell Delivery Transitions
**Endpoint**: `GET /api/bowling/spells/{spell_id}/deliveries`

Exposes ball-by-ball transition data and mathematical attribution for a single spell.

#### Path Parameters
- `spell_id` (string, required): Unique spell key structured as `{match_id}_{innings}_{bowler_id}` (e.g. `13511_1_2633` for Jason Holder).

#### Delivery Features Returned
- **Match State Context**: `overid`, `over_ball_num`, `innings_phase`, `score_before`, `score_after`, `wickets_lost_before`, `wickets_lost_after`, `required_run_rate`, `current_run_rate`.
- **Participants**: `striker_id`, `striker_name`, `non_striker_id`, `non_striker_name`, `dismissed_player_name`.
- **Outcomes**: `batter_runs`, `bowler_runs`, `team_runs`, `extras_type`, `is_legal_delivery`, `is_dot_ball`, `is_boundary`, `is_wicket_event`, `is_bowler_wkt`, `dismissal_type`.
- **BCM Attribution Factors**:
  - `exp_bowler_runs`: Expected runs for delivery state.
  - `erp`: Expected runs prevented ($\text{ExpRuns} - \text{ChargedRuns}$).
  - `WQM`: Wicket Quality Multiplier ($[0.4, 2.5]$).
  - `V_wkt`: Context-dependent physical wicket value ($[2.0, 18.0]$).
  - `leverage`: Match leverage multiplier ($[0.5, 2.0]$).
  - `dot_pressure_index`: Dot ball pressure index.
  - `rrr_pressure_index`: Chase pressure index.
  - `bcs`: Delivery Bowling Contribution Score (runs).
  - `bwpa`: Delivery Bowler Win Probability Added ($[-1.0, 1.0]$).

#### Curl Example
```bash
curl -X GET "http://127.0.0.1:8000/api/bowling/spells/13511_1_2633/deliveries"
```

---

## 5. Error Handling Schema

All error responses adhere to standard JSON schemas with descriptive error details:

```json
{
  "status": "error",
  "error": "HTTP Exception",
  "detail": "Bowler with player_id 999999 not found in career database."
}
```

- `404 Not Found`: Returned when a requested player, match, or spell ID does not exist.
- `422 Unprocessable Entity`: Returned when query parameter validations fail (e.g. comparison player count $<2$ or $>5$, duplicate player IDs, invalid page/sort values).
- `500 Internal Server Error`: Returned if an unhandled internal exception occurs.
