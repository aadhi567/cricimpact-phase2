# CricImpact Phase 2 — Stage 7A: HPP Feature Dictionary

**Document Version:** 1.0 (Draft Specification)  
**Author:** Google DeepMind Antigravity Architecture Team  
**Date:** November 14, 2026  
**Status:** READ-ONLY METHODOLOGY SPECIFICATION  
**Scope:** Complete Mathematical Feature Catalog for High Pressure Player (HPP) Modeling  

---

## 1. Overview and Feature Taxonomies

The HPP system utilizes a modular, multi-layered feature architecture. Every feature is categorized into one of six functional domains:
1. **Instantaneous Match Context & Pressure Features (`MCP_*`)**
2. **Win Probability Added & Decomposition Features (`WPA_*`)**
3. **Batting Impact & Stint Features (`BAT_*`)**
4. **Bowling Containment & Execution Features (`BWL_*`)**
5. **Impact Classification & Regime Tags (`IMP_*`)**
6. **Aggregation, Participation & Provenance Identifiers (`AGG_*`)**

---

## 2. Instantaneous Match Context & Pressure Features (`MCP_*`)

### 2.1 `MCP_NORMALIZED_LEVERAGE_INDEX` ($\text{NLI}$)
- **Identifier:** `mcp_normalized_leverage_index`
- **Definition:** Quantifies the sensitivity of the match outcome to the current delivery. Measures how close the match is to a $50/50$ knife-edge state, scaled by remaining match resources.
- **Mathematical Formula:**
  $$\text{NLI}(b) = 4 \cdot W_{\text{bat}}(b-1) \cdot (1.0 - W_{\text{bat}}(b-1)) \cdot \left[1.0 + 0.35 \cdot \left(\frac{120 - B_{\text{rem}}(b)}{120}\right) + 0.25 \cdot \mathbb{I}_{\{\text{inn}=2\}} \cdot \left(\frac{\text{RRR}(b)}{\text{CRR}(b) + 1.0}\right)\right]$$
- **Required Inputs:** $W_{\text{bat}}(b-1)$ (Stage 6B calibrated probability), $B_{\text{rem}}(b)$ (`legal_balls_remaining_before`), $\text{RRR}(b)$, $\text{CRR}(b)$, $\text{innings}(b)$.
- **Typical Range:** $[0.05, 2.00]$ (dimensionless; $1.00 = \text{par leverage}$).
- **Interpretation:** Values above $1.40$ indicate extreme high-leverage situations (close chases, death overs). Values below $0.40$ indicate dead rubbers or blowout states.
- **Edge Cases:** When $W \in \{0.01, 0.99\}$, $\text{NLI}$ approaches $0.05$. When $B_{\text{rem}} = 0$, leverage defaults to terminal evaluation.
- **Limitations:** Does not incorporate pitch deterioration or dew factor directly (captured via underlying Stage 6B model).

### 2.2 `MCP_CRISIS_SEVERITY_INDEX` ($\text{CSI}$)
- **Identifier:** `mcp_crisis_severity_index`
- **Definition:** Measures how severely a batting lineup has collapsed relative to baseline expectations, independent of chasing targets.
- **Mathematical Formula:**
  $$\text{CSI}(b) = 0.60 \cdot \left(\frac{W_{\text{lost}}(b)}{10}\right) + 0.40 \cdot \max\left(0.0, \frac{\text{Par Score}(b) - S(b)}{\text{Par Score}(b) + 1.0}\right)$$
- **Required Inputs:** $W_{\text{lost}}(b)$ (`wickets_lost_before`), $S(b)$ (`score_before`), $\text{Par Score}(b)$ (`venue_avg_first_inn_score` scaled to over).
- **Typical Range:** $[0.00, 1.00]$ (dimensionless).
- **Interpretation:** $\text{CSI} > 0.50$ signifies an acute batting crisis (e.g. 35/4 in powerplay). Performance under high $\text{CSI}$ qualifies directly for **Recovery HPP**.
- **Edge Cases:** If $W_{\text{lost}} = 0$, $\text{CSI}$ evaluates only run-rate deficit.
- **Limitations:** Par score is venue-based and does not reflect mid-game rain delays.

### 2.3 `MCP_REQUIRED_RUN_RATE` ($\text{RRR}$)
- **Identifier:** `mcp_required_run_rate`
- **Definition:** The runs required per 6 legal balls to win the match during a chase.
- **Mathematical Formula:**
  $$\text{RRR}(b) = \begin{cases} \frac{R_{\text{req}}(b) \cdot 6.0}{B_{\text{rem}}(b)} & \text{if } \text{innings} = 2 \text{ and } B_{\text{rem}} > 0 \\ 0.0 & \text{if } \text{innings} = 1 \end{cases}$$
- **Required Inputs:** $R_{\text{req}}(b)$ (`runs_required_before`), $B_{\text{rem}}(b)$ (`legal_balls_remaining_before`).
- **Typical Range:** $[0.0, 36.0]$ (runs per over).
- **Interpretation:** Core driver of chase pressure; rates above $12.0$ represent extreme difficulty.
- **Edge Cases:** When $B_{\text{rem}} = 0$ or $R_{\text{req}} \le 0$, clamped to boundary.

---

## 3. Win Probability Added & Decomposition Features (`WPA_*`)

### 3.1 `WPA_DELIVERY_BATTING` ($\Delta W_{\text{bat}}$)
- **Identifier:** `wpa_delivery_batting`
- **Definition:** Net change in batting team win probability resulting from delivery $b$.
- **Mathematical Formula:**
  $$\Delta W_{\text{bat}}(b) = W_{\text{bat}}(b) - W_{\text{bat}}(b-1)$$
- **Required Inputs:** $W_{\text{bat}}(b)$ (`calibrated_probability` oriented to batting team).
- **Typical Range:** $[-0.45, +0.45]$ (bounded probability units).
- **Interpretation:** Positive values indicate advantage generation; negative values indicate advantage erosion.

### 3.2 `WPA_DELIVERY_BOWLING` ($\Delta W_{\text{bowl}}$)
- **Identifier:** `wpa_delivery_bowling`
- **Definition:** Net change in bowling team win probability resulting from delivery $b$.
- **Mathematical Formula:**
  $$\Delta W_{\text{bowl}}(b) = -\Delta W_{\text{bat}}(b)$$
- **Required Inputs:** $\Delta W_{\text{bat}}(b)$.
- **Typical Range:** $[-0.45, +0.45]$.

### 3.3 `WPA_STRIKER_DIRECT` ($\Delta W_{\text{str}}$)
- **Identifier:** `wpa_striker_direct`
- **Definition:** The portion of delivery win probability change directly attributable to the striker's execution (bat runs or dismissal).
- **Mathematical Formula:**
  $$\Delta W_{\text{str}}(b) = \Delta W_{\text{bat}}(b) - \Delta W_{\text{drift}}(b) - \Delta W_{\text{extra}}(b)$$
- **Typical Range:** $[-0.40, +0.40]$.

### 3.4 `WPA_CONTEXTUAL_DRIFT` ($\Delta W_{\text{drift}}$)
- **Identifier:** `wpa_contextual_drift`
- **Definition:** The structural decay in win probability arising strictly from resource consumption (1 legal ball elapsed) in the absence of boundary or wicket events.
- **Mathematical Formula:**
  $$\Delta W_{\text{drift}}(b) = W_{\text{bat}}(S, W_{\text{lost}}, B_{\text{rem}} - 1) - W_{\text{bat}}(S, W_{\text{lost}}, B_{\text{rem}})$$
- **Typical Range:** $[-0.04, 0.00]$ in chase; $\approx 0.00$ in early innings 1.

---

## 4. Batting Impact & Stint Features (`BAT_*`)

### 4.1 `BAT_BUILDUP_STABILIZATION_SCORE`
- **Identifier:** `bat_buildup_stabilization_score`
- **Definition:** Measures a batter's ability to resist collapse, absorb pressure, and construct a stable platform prior to boundary acceleration.
- **Mathematical Formula:**
  $$\text{BSS} = \sum_{b \in \text{BuildUp}} \left[ (1.0 - \mathbb{I}_{\{\text{dot}\}}) \cdot 0.5 + \text{StrikeRotation}(b) \cdot 0.5 \right] \cdot \text{CSI}(b)$$
- **Required Inputs:** Deliveries in build-up phase, dot-ball indicator, single/two indicator, `mcp_crisis_severity_index`.
- **Typical Range:** $[0.0, 50.0]$ points.
- **Interpretation:** Rewards middle-order anchors who prevent batting routs before counter-attacking.

### 4.2 `BAT_IMPACT_ACCELERATION_SCORE`
- **Identifier:** `bat_impact_acceleration_score`
- **Definition:** Direct performance during the designated impact window, quantifying boundary production relative to required rates under high leverage.
- **Mathematical Formula:**
  $$\text{IAS} = \sum_{b \in \text{Impact}} \Delta W_{\text{str}}(b) \cdot \text{NLI}(b) \cdot \left(\frac{\text{Runs}(b) + 1.0}{\mathbb{E}[\text{Runs}(b)] + 1.0}\right)$$
- **Typical Range:** $[-30.0, +100.0]$ points.

### 4.3 `BAT_SUPPORTING_PARTNER_CREDIT`
- **Identifier:** `bat_supporting_partner_credit`
- **Definition:** Credit awarded to a non-striker or secondary batter who supports a dominant partner by rotating strike and avoiding dot balls.
- **Mathematical Formula:**
  $$\text{SPC} = \sum_{b \in \text{Partner}} \mathbb{I}_{\{\text{Single to Lead}\}} \cdot 0.5 \cdot \text{NLI}(b) + (1.0 - \text{DotRate}_{\text{support}}) \cdot 5.0$$
- **Typical Range:** $[0.0, 30.0]$ points.

### 4.4 `BAT_EXPECTED_RUNS_DELTA`
- **Identifier:** `bat_expected_runs_delta`
- **Definition:** Actual runs scored minus Stage 5C expected runs for that specific match context and phase.
- **Mathematical Formula:**
  $$\text{ERD} = \text{Runs}_{\text{actual}} - \mathbb{E}[\text{Runs}_{\text{Stage5C}}]$$
- **Typical Range:** $[-25.0, +60.0]$ runs.

---

## 5. Bowling Containment & Execution Features (`BWL_*`)

### 5.1 `BWL_SHUTDOWN_OVER_IMPACT`
- **Identifier:** `bwl_shutdown_over_impact`
- **Definition:** Measures bowling economy superiority during an entire 6-ball over relative to contextual opposition momentum.
- **Mathematical Formula:**
  $$\text{SOI} = \max\left(0.0, \mathbb{E}[R_{\text{over}}] - R_{\text{actual}}\right) \cdot \overline{\text{NLI}}_{\text{over}}$$
- **Required Inputs:** Actual runs conceded in over (including extras), expected runs for over $\mathbb{E}[R_{\text{over}}]$, mean over leverage.
- **Typical Range:** $[0.0, 40.0]$ points.
- **Interpretation:** Captures match-winning defensive spells where no wickets fell (e.g. 5-run 19th over in tight chase).

### 5.2 `BWL_DOT_BALL_PRESSURE_SCORE`
- **Identifier:** `bwl_dot_ball_pressure_score`
- **Definition:** Cumulative pressure generated by delivering legal dot balls that inflate the required run rate or consume first-innings resources.
- **Mathematical Formula:**
  $$\text{DPS} = \sum_{b \in \text{dots}} \text{NLI}(b) \cdot \left(\mathbb{E}[R(b)] + 0.5\right)$$
- **Typical Range:** $[0.0, 35.0]$ points.

### 5.3 `BWL_WICKET_IMPACT_SCORE`
- **Identifier:** `bwl_wicket_impact_score`
- **Definition:** Direct credit for legal dismissals (bowled, caught, lbw, stumped), scaled by the dismissed batter's quality and the pre-wicket match leverage.
- **Mathematical Formula:**
  $$\text{WIS} = \sum_{w \in \text{wkts}} |\Delta W_{\text{bowl}}(w)| \cdot \text{NLI}(w) \cdot \left(\frac{\text{ABC}_{\text{batter}}}{50.0}\right)$$
- **Typical Range:** $[0.0, 80.0]$ points per wicket.
- **Attribution Policy:** Run-outs receive $0.0$ bowler credit; caught/stumped receive $100\%$ bowler credit.

### 5.4 `BWL_PARTNERSHIP_BREAKER_BONUS`
- **Identifier:** `bwl_partnership_breaker_bonus`
- **Definition:** Bonus awarded for dismissing a batter involved in an established, dangerous partnership ($R_{\text{part}} \ge 40$).
- **Mathematical Formula:**
  $$\text{PBB} = \min\left(25.0, \text{WIS} \cdot 0.25 \cdot \left(\frac{R_{\text{partnership}}}{40.0}\right)\right)$$
- **Typical Range:** $[0.0, 25.0]$ points.

---

## 6. Impact Classification & Regime Tags (`IMP_*`)

### 6.1 `IMP_REGIME_TAG`
- **Identifier:** `imp_regime_tag`
- **Definition:** Categorical indicator classifying the delivery's strategic domain based on $W_{\text{bat}}(b-1)$:
  - `RECOVERY`: $W_{\text{bat}} < 0.35$ (for batting) or $W_{\text{bowl}} < 0.35$ (for bowling)
  - `CREATION`: $W \in [0.35, 0.65]$
  - `MAINTENANCE`: $W_{\text{bat}} \ge 0.65$ (for batting) or $W_{\text{bowl}} \ge 0.65$ (for bowling)

### 6.2 `IMP_CREATION_SCORE` ($\text{HPP}_{\text{create}}$)
- **Identifier:** `imp_creation_score`
- **Definition:** Value generated while driving the match from contested parity toward decisive dominance.

### 6.3 `IMP_MAINTENANCE_SCORE` ($\text{HPP}_{\text{maintain}}$)
- **Identifier:** `imp_maintenance_score`
- **Definition:** Value generated while defending and preserving an already established winning advantage.

### 6.4 `IMP_RECOVERY_SCORE` ($\text{HPP}_{\text{recover}}$)
- **Identifier:** `imp_recovery_score`
- **Definition:** Value generated while pulling a team out of a severe deficit state back into competitive contention.

---

## 7. Aggregation, Participation & Provenance Identifiers (`AGG_*`)

### 7.1 `AGG_DNB_FLAG`
- **Identifier:** `agg_dnb_flag`
- **Type:** Boolean (`True` / `False`).
- **Definition:** Set to `True` if a player was named in the playing XI but faced 0 legal balls.
- **Rule:** When `True`, batting statistics are strictly `NaN` (never $0.0$).

### 7.2 `AGG_DNBOWL_FLAG`
- **Identifier:** `agg_dnbowl_flag`
- **Type:** Boolean (`True` / `False`).
- **Definition:** Set to `True` if a player was named in the playing XI but delivered 0 legal balls.
- **Rule:** When `True`, bowling statistics are strictly `NaN` (never $0.0$).

### 7.3 `AGG_PREDICTION_PROVENANCE`
- **Identifier:** `agg_prediction_provenance`
- **Type:** String enum: `PRODUCTION_CALIBRATED` (2025–2026) vs `OOF_RETROSPECTIVE` (2022–2024).
- **Rule:** Tracks underlying model provenance for sensitivity auditing.

