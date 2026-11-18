# CricImpact Phase 2 — Stage 7A: HPP Aggregation Specification

**Document Version:** 1.0 (Draft Specification)  
**Author:** Google DeepMind Antigravity Architecture Team  
**Date:** November 14, 2026  
**Status:** READ-ONLY METHODOLOGY SPECIFICATION  
**Scope:** Multi-Tier Aggregation Hierarchy, Participation Policies, Schema Contracts, and Provenance Handling  

---

## 1. Aggregation Architecture Overview

The High Pressure Player (HPP) system is structured as a hierarchical data pipeline. The foundational unit of observation is the **Delivery-Level Impact State** ($N = 190,575$). Deliveries are sequentially rolled up into **Crease Stints / Bowling Spells**, which roll up into **Player-Match Summaries**, which then aggregate across multi-year temporal and competition hierarchies:

```
[Level 1: Delivery Impact States]  (190,575 rows; ball-by-ball WPA, Leverage, Delta HPP)
             |
             v
[Level 2: Player Stints & Spells]  (Batting crease tenures, bowling spell overs)
             |
             v
[Level 3: Player-Match Records]    (Match ID, Player ID, Batting HPP, Bowling HPP, Signed +/-)
             |
             +-----------------------+-----------------------+
             |                       |                       |
             v                       v                       v
[Level 4A: Season Aggregates]  [Level 4B: Year Aggregates]  [Level 4C: Career Aggregates]
(e.g. IPL 2024)                 (2022, 2023, ..., 2026)      (All 798 Standard Matches)
```

---

## 2. Multi-Tier Temporal and Competition Scopes

The aggregation engine must support exact querying and reporting across six standardized scopes:

1. **Individual Match:** Atomic match evaluation ($N = 798$ standard matches).
2. **Competition Scope:** Filtered by `competition_category` (`IPL`, `T20I`, `OTHER_T20`).
3. **Tournament Season:** Filtered by `comp_id` and `season` (e.g. `IPL_2024`, `T20_WORLD_CUP_2024`).
4. **Calendar Year:** Filtered by `match_date` year ($2022, 2023, 2024, 2025, 2026$).
5. **Custom Date / Event Window:** Arbitrary time intervals (e.g. Last 24 Months, Post-2024 T20 World Cup).
6. **Career / Lifetime Corpus:** Consolidated record across all available standard T20 matches in the database.

---

## 3. Mandatory Metric Ledgers per Aggregation Entity

For every aggregation scope and every player $p$, the system maintains three distinct metric ledgers:

### 3.1 Batting Ledger
- **`BATTING_HPP_POS` ($\text{Batting HPP}^+$):** Gross positive batting HPP points accumulated.
- **`BATTING_HPP_NEG` ($\text{Batting HPP}^-$):** Gross negative batting HPP debits incurred (stored as positive magnitude).
- **`BATTING_HPP_NET` ($\text{Batting HPP}_{\text{net}}$):** $\text{Batting HPP}^+ - \text{Batting HPP}^-$.
- **`BATTING_HPP_AVG` ($\text{Batting HPP}_{\text{avg}}$):** Net batting HPP divided strictly by **Batted Innings** ($N_{\text{batted}}$).
- **`BATTED_INNINGS_COUNT` ($N_{\text{batted}}$):** Count of matches where the player faced $\ge 1$ ball.
- **`DNB_COUNT` ($N_{\text{dnb}}$):** Count of confirmed XI matches where the player Did Not Bat.

### 3.2 Bowling Ledger
- **`BOWLING_HPP_POS` ($\text{Bowling HPP}^+$):** Gross positive bowling HPP points accumulated.
- **`BOWLING_HPP_NEG` ($\text{Bowling HPP}^-$):** Gross negative bowling HPP debits incurred.
- **`BOWLING_HPP_NET` ($\text{Bowling HPP}_{\text{net}}$):** $\text{Bowling HPP}^+ - \text{Bowling HPP}^-$.
- **`BOWLING_HPP_AVG` ($\text{Bowling HPP}_{\text{avg}}$):** Net bowling HPP divided strictly by **Bowled Innings** ($N_{\text{bowled}}$).
- **`BOWLED_INNINGS_COUNT` ($N_{\text{bowled}}$):** Count of matches where the player bowled $\ge 1$ legal delivery.
- **`DNBOWL_COUNT` ($N_{\text{dnbowl}}$):** Count of confirmed XI matches where the player Did Not Bowl.

### 3.3 Overall Composite Ledger
- **`OVERALL_HPP_POS` ($\text{HPP}^+$):** $\text{Batting HPP}^+ + \text{Bowling HPP}^+$.
- **`OVERALL_HPP_NEG` ($\text{HPP}^-$):** $\text{Batting HPP}^- + \text{Bowling HPP}^-$.
- **`OVERALL_HPP_NET` ($\text{HPP}_{\text{net}}$):** $\text{Total HPP}^+ - \text{Total HPP}^-$.
- **`OVERALL_HPP_AVG` ($\text{HPP}_{\text{avg}}$):** $\text{Total HPP}_{\text{net}} / N_{\text{eligible\_matches}}$.
- **`OVERALL_HPP_RATING`:** Composite score combining standardized discipline percentiles (Model A).
- **`ELIGIBLE_MATCH_COUNT` ($N_{\text{eligible\_matches}}$):** Total confirmed XI selections.
- **`DUAL_DISCIPLINE_MATCH_COUNT` ($N_{\text{both}}$):** Matches where player both batted and bowled.

---

## 4. Strict Participation Rules & Denominators

### 4.1 The DNB Non-Zeroing Invariant (MANDATORY)
- **Problem Statement:** In many amateur cricket metrics, a player who Did Not Bat is assigned a score of $0.0$. In career averaging, this unfairly penalizes middle-order finishers whose top order chased down totals without losing wickets.
- **Strict Rule:** If $\text{DNB} = \text{True}$, the batting HPP score for that match is **`NaN` / Excluded**.
- **Denominator Contract:**
  $$\text{Batting HPP}_{\text{avg}} = \frac{\sum_{m \in \mathcal{M}, \text{batted}=1} \text{Batting HPP}_{\text{net}}(m)}{N_{\text{batted}}}$$
  A player with 10 matches and 6 batted innings has their batting average divided by **6, never 10**.

### 4.2 The Did Not Bowl (DNBowl) Non-Zeroing Invariant
- **Strict Rule:** If a specialist batter delivers 0 balls, their bowling HPP score for that match is **`NaN` / Excluded**.
- **Denominator Contract:**
  $$\text{Bowling HPP}_{\text{avg}} = \frac{\sum_{m \in \mathcal{M}, \text{bowled}=1} \text{Bowling HPP}_{\text{net}}(m)}{N_{\text{bowled}}}$$
  Bowling average is divided strictly by active bowling appearances.

### 4.3 The Overall Match Denominator
- For the Overall Match Average ($\text{Overall HPP}_{\text{avg}}$), the denominator is the total number of matches in which the player was in the playing XI ($N_{\text{eligible\_matches}}$).
- This represents the player's net contribution per team match selection.

---

## 5. Provenance Segregation in Historical Rollups

To preserve methodological transparency and adhere to the Stage 6B.8 acceptance conditions:

### 5.1 Partition Separation in Reporting
Whenever career or multi-year aggregates are displayed, the pipeline must maintain audit tags tracking prediction sources:
- **`MATCHES_OOF_RETROSPECTIVE`:** Matches originating from the 2022–2024 Five-Fold OOF training partition ($N \le 477$).
- **`MATCHES_PRODUCTION_CALIBRATED`:** Matches originating from the 2025–2026 production-calibrated partition ($N \le 321$).

### 5.2 Sensitivity Auditing Protocols
The system must support running career rankings under three filtering modes:
1. **Full Pooled Corpus (2022–2026):** Default production mode ($N = 798$ matches).
2. **Production-Only Subset (2025–2026):** Verifies ranking stability when restricted strictly to forward-looking production runs ($N = 321$ matches).
3. **Major Competitions Only (IPL + T20I):** Excludes OTHER_T20 to verify that low-sample domestic leagues do not distort leaderboards.

---

## 6. Authoritative Relational Schema Contracts

### Table 1: `player_match_hpp`
| Column Name | Data Type | Nullable | Primary Key | Description |
| :--- | :--- | :---: | :---: | :--- |
| `match_id` | `INTEGER` | No | PK | Unique match foreign key. |
| `player_id` | `INTEGER` | No | PK | Unique player foreign key. |
| `team_id` | `INTEGER` | No | No | Player's team foreign key. |
| `season` | `INTEGER` | No | No | Competition season (2022–2026). |
| `comp_category` | `VARCHAR(16)` | No | No | `IPL`, `T20I`, `OTHER_T20`. |
| `provenance` | `VARCHAR(32)` | No | No | `PRODUCTION` vs `OOF_RETROSPECTIVE`. |
| `batted_flag` | `BOOLEAN` | No | No | `True` if player faced $\ge 1$ ball. |
| `bowled_flag` | `BOOLEAN` | No | No | `True` if player bowled $\ge 1$ ball. |
| `batting_hpp_pos`| `FLOAT` | Yes | No | Positive batting HPP (null if DNB). |
| `batting_hpp_neg`| `FLOAT` | Yes | No | Negative batting HPP (null if DNB). |
| `batting_hpp_net`| `FLOAT` | Yes | No | Net batting HPP (null if DNB). |
| `bowling_hpp_pos`| `FLOAT` | Yes | No | Positive bowling HPP (null if DNBowl).|
| `bowling_hpp_neg`| `FLOAT` | Yes | No | Negative bowling HPP (null if DNBowl).|
| `bowling_hpp_net`| `FLOAT` | Yes | No | Net bowling HPP (null if DNBowl). |
| `overall_hpp_net`| `FLOAT` | No | No | Total net HPP in match. |

### Table 2: `player_aggregate_hpp`
| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `player_id` | `INTEGER` | Unique player foreign key. |
| `aggregation_scope`| `VARCHAR(32)` | `CAREER`, `SEASON`, `YEAR`, `COMPETITION`. |
| `scope_identifier` | `VARCHAR(64)` | e.g. `IPL_2024`, `YEAR_2025`, `ALL_CAREER`. |
| `eligible_matches` | `INTEGER` | Total confirmed XI appearances. |
| `batted_innings` | `INTEGER` | Total batted innings. |
| `bowled_innings` | `INTEGER` | Total bowled innings. |
| `batting_hpp_net` | `FLOAT` | Cumulative net batting HPP. |
| `batting_hpp_avg` | `FLOAT` | Net batting HPP / `batted_innings`. |
| `bowling_hpp_net` | `FLOAT` | Cumulative net bowling HPP. |
| `bowling_hpp_avg` | `FLOAT` | Net bowling HPP / `bowled_innings`. |
| `overall_hpp_net` | `FLOAT` | Cumulative net overall HPP. |
| `overall_hpp_avg` | `FLOAT` | Net overall HPP / `eligible_matches`. |
| `overall_hpp_rating`| `FLOAT` | Standardized composite score ($0–100$ scale). |

