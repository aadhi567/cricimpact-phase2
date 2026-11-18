# CricImpact Phase 2 — Stage 7A: High Pressure Player (HPP) Methodology Specification

**Document Version:** 1.0 (Draft Specification)  
**Author:** Google DeepMind Antigravity Architecture Team  
**Date:** November 14, 2026  
**Status:** METHODOLOGY SPECIFICATION ONLY (Read-Only Blueprint — Implementation Deferred to Stage 7B)  
**Foundation Dependencies:** Stage 5B Match States (`match_states_standard_t20_v1.pkl.gz`), Stage 5C Batter Contribution (`stints`, `ABC`), Stage 6B Calibrated Win Probability Engine ($N = 190,575$ deliveries across 798 standard T20 matches).

---

## 1. Executive Architecture & System Principles

### 1.1 Core Mission
The **CricImpact High Pressure Player (HPP) Rating System** is an advanced analytical framework designed to evaluate, quantify, and rank cricket players according to their performance in critical, match-defining situations. Traditional cricket metrics—such as batting average, strike rate, bowling average, and economy rate—are context-blind: they treat a boundary hit when a team needs 12 runs from 2 balls with equal mathematical weight to a boundary hit when needing 80 runs from 60 balls.

The HPP system shifts the analytical paradigm from **volume-based accumulation** to **context-aware match-impact evaluation**. Grounded in the accepted Stage 6B Win Probability Engine, HPP measures how individual player actions directly influence a team's probability of victory under variable degrees of match pressure.

### 1.2 The Three Fundamental Forms of Match Impact
Unlike simplistic clutch metrics that only reward dramatic comebacks or final-over finishes, HPP recognizes three distinct, mathematically formalized dimensions of match impact:
1. **Win Probability Creation ($\text{HPP}_{\text{create}}$):** Actively engineering a winning advantage from a neutral or contested state.
2. **Win Probability Maintenance ($\text{HPP}_{\text{maintain}}$):** Protecting, consolidating, and sustaining an established advantage under opposition counter-pressure without allowing momentum decay.
3. **Win Probability Recovery ($\text{HPP}_{\text{recover}}$):** Rescuing a team from a severely degraded, low-probability crisis state back into contention.

### 1.3 Strict Discipline Scope: Batting and Bowling Only
HPP evaluates exactly two disciplines:
- **Batting HPP:** Quantifies run creation, strike rotation, crisis rebuilding, and acceleration under pressure.
- **Bowling HPP:** Quantifies shutdown containment, wicket impact, partnership breaking, and dot-ball suffocation under pressure.

#### Absolute Exclusion of Fielding HPP:
- **No Fielding Points:** Fielders and wicketkeepers receive zero independent HPP points.
- **No Fielding Category:** There is no fielding leaderboard, fielding HPP metric, or fielding component in the overall rating.
- **No Dual-Counting on Dismissals:** Catches, run-outs, and stumpings do not transfer HPP credit to fielders. Dismissal impact is handled strictly under approved bowling and batting attribution policies (e.g. bowler receives primary credit for caught dismissals; run-outs do not award bowler wicket credit).

### 1.4 Architecture Overview
```
+---------------------------------------------------------------------------------------------------+
|                                 CRICIMPACT PHASE 2 CORE ARCHITECTURE                              |
+---------------------------------------------------------------------------------------------------+
|  [Stage 5B: Match States]     --> Raw Delivery States, Crease Stints, Legal Balls, Scoreboards     |
|  [Stage 5C: Batter Contrib]   --> Contextual Batter Expectation Baselines (Strategy 4 / ABC)       |
|  [Stage 6B: Win Probability]  --> Calibrated Ball-by-Ball WP (P_A, P_B, Delta P across 798 matches)|
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                STAGE 7: HPP ANALYTICAL LAYER (NEW)                                |
+---------------------------------------------------------------------------------------------------+
|  1. Pressure Detection Engine (PDE)                                                               |
|     - Calculates instantaneous Normalized Leverage & Crisis Indices: L(b) in [0, 2], C(b) in [0, 1] |
|                                                                                                   |
|  2. Attribution & Impact Decomposition Engine (AIDE)                                              |
|     - Decomposes Delta WP into: Batter WPA, Bowler WPA, Contextual Drift, Unattributed Residual   |
|     - Classifies delivery into Creation, Maintenance, or Recovery Impact                         |
|                                                                                                   |
|  3. Discipline-Specific Scorers                                                                    |
|     - Batting HPP: Build-Up Stint vs Impact Phase Window; Supporting Batter Recognition           |
|     - Bowling HPP: Contextual Shutdown Overs, Dot-Ball Pressure, Wicket Attribution               |
|                                                                                                   |
|  4. Signed Metric Accumulator                                                                     |
|     - Tracks Positive HPP (+), Negative HPP (-), Net HPP, and Average HPP per match               |
|                                                                                                   |
|  5. Multi-Tier Historical Aggregator                                                              |
|     - Rollups: Match -> Tournament Season -> Calendar Year -> Career                              |
|     - Enforces Participation Rules: DNB != 0.0; Strict Discipline-Specific Denominators            |
|     - Evaluates Overall HPP Composite without all-rounder bias                                    |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Mathematical Foundations & Win Probability Added (WPA)

### 2.1 Delivery-Level Win Probability Added
Let $b \in \{1, 2, \dots, N_m\}$ denote the sequential delivery index within match $m$. Let $W_A(b)$ denote the calibrated probability that Team A (batting first) wins the match, evaluated at the conclusion of delivery $b$, with $W_A(0)$ denoting the pre-match anchor probability ($P_{\text{stage\_b}}$).

The instantaneous, delivery-level Win Probability Added from the perspective of the batting team ($T_{\text{bat}} \in \{A, B\}$) is defined as:

$$\Delta W_{\text{bat}}(b) = W_{\text{bat}}(b) - W_{\text{bat}}(b - 1)$$

Where:
$$W_{\text{bat}}(b) = \begin{cases} W_A(b) & \text{if } \text{innings}(b) = 1 \\ 1.0 - W_A(b) = W_B(b) & \text{if } \text{innings}(b) = 2 \end{cases}$$

By strict complementarity ($W_A(b) + W_B(b) = 1.0 \pm 10^{-4}$):
$$\Delta W_{\text{bowl}}(b) = -\Delta W_{\text{bat}}(b)$$

### 2.2 Cumulative Multi-Delivery Windows
For any contiguous sequence of deliveries $W = [b_s, b_e]$ within the same innings, cumulative win probability change is strictly telescoping:

$$\Delta W(W) = \sum_{b=b_s}^{b_e} \Delta W_{\text{bat}}(b) = W_{\text{bat}}(b_e) - W_{\text{bat}}(b_s - 1)$$

### 2.3 Decomposition of Delivery WPA
A common error in win-probability metrics is attributing $100\%$ of $\Delta W$ solely to the striker on every delivery. In cricket:
- On a dot ball, the bowler executed a defensive delivery, but the non-striker and pitch conditions also played a role.
- On a single, the batter rotated strike, transferring batting resources.
- On an extra (wide/no-ball), the bowler committed an unforced penalty.

The HPP system decomposes each delivery swing into four mutually exclusive components:
$$\Delta W_{\text{bat}}(b) = \Delta W_{\text{striker}}(b) + \Delta W_{\text{non\_striker}}(b) + \Delta W_{\text{bowler\_err}}(b) + \Delta W_{\text{drift}}(b)$$

Where:
- $\Delta W_{\text{striker}}(b)$: Direct impact of the batter's execution (bat runs, dismissals).
- $\Delta W_{\text{non\_striker}}(b)$: Strike rotation contribution, supporting presence, or non-striker run-out fault.
- $\Delta W_{\text{bowler\_err}}(b)$: Direct penalty from bowler execution errors (wides, no-balls).
- $\Delta W_{\text{drift}}(b)$: Contextual drift arising solely from resource decay (e.g. ball consumption without runs).

---

## 3. Three Dimensions of Player Impact: Creation, Maintenance, Recovery

Every delivery $b$ is classified into one of three structural match regimes based on the state prior to the delivery ($W_{\text{bat}}(b-1)$):

```
       Crisis / Deficit                Contested / Neutral               Advantage / Dominance
[0.00 ----------------------- 0.35] [0.35 ----------------------- 0.65] [0.65 ----------------------- 1.00]
         RECOVERY ZONE                        CREATION ZONE                       MAINTENANCE ZONE
```

### 3.1 Win Probability Creation ($\text{HPP}_{\text{create}}$)
- **State Condition:** The match is in a contested state: $W_{\text{bat}}(b-1) \in [0.35, 0.65]$.
- **Objective:** Establish a decisive advantage by driving $W_{\text{bat}}$ above $0.65$.
- **Batting Creation:** Striking boundaries, executing aggressive running, elevating current run rate well above par without losing wickets.
- **Bowling Creation:** Taking top-order wickets, delivering maiden/tight overs to suppress opponent win probability below $0.35$.

### 3.2 Win Probability Maintenance ($\text{HPP}_{\text{maintain}}$)
- **State Condition:** The team already holds an established advantage: $W_{\text{bat}}(b-1) \ge 0.65$ (or for bowling, $W_{\text{bowl}}(b-1) \ge 0.65$).
- **Objective:** Protect and consolidate the advantage, preventing counter-attacks or collapses.
- **Active Contribution Requirement:** A player does **NOT** receive high maintenance HPP simply by being present while the team is at $95\%$ win probability. Maintenance credit is awarded strictly based on **execution relative to contextual expectation**:
  $$\text{Maintenance Score}(b) = \max\left(0, \Delta W(b) - \mathbb{E}[\Delta W_{\text{drift}}(b)]\right)$$
  - *Example (Batting):* Chasing 180, team is 140/2 after 15 overs ($W \approx 0.85$). Batter scores 25 off 18 balls with clean strike rotation, matching the required 8.0 RRR and preventing a collapse. Full maintenance credit is awarded.
  - *Example (Bowling):* Opponent needs 45 runs from 24 balls ($W_{\text{bowl}} \approx 0.75$). Bowler concedes only 5 runs in over 17, pushing win probability to $0.90$. Outstanding maintenance credit is earned.

### 3.3 Win Probability Recovery ($\text{HPP}_{\text{recover}}$)
- **State Condition:** The team is in a severe crisis/deficit: $W_{\text{bat}}(b-1) < 0.35$ (or for bowling, opponent is heavily favored $W_{\text{bowl}}(b-1) < 0.35$).
- **Objective:** Rescue the team from imminent defeat back into competitive parity ($W \ge 0.50$).
- **Batting Recovery:** Counter-attacking after a top-order collapse (e.g. 25/3), building a stabilizing partnership, absorbing dot-ball pressure, and subsequently accelerating.
- **Bowling Recovery:** Delivering a double-wicket over or a 3-run shutdown over when the opposition is cruising at $80\%$ win probability.

---

## 4. Context-Aware Pressure Modeling Architecture

### 4.1 Separation of Pressure and Match Impact
A foundational design principle of HPP is that **Pressure** and **Impact** are independent analytical dimensions:
- **High Pressure, Low Impact:** A batter defends a good delivery in over 19 with 8 runs needed off 3 balls. Pressure is extreme ($L \approx 1.8$), but impact is small ($\Delta W \approx -0.05$).
- **Low Pressure, High Impact:** In over 3 of innings 1 ($W \approx 0.50$), a premier batter is clean bowled. Pressure is moderate, but match-changing impact is massive ($\Delta W = -0.12$).

### 4.2 Normalized Leverage Index ($\text{NLI}$)
The instantaneous match leverage $L(b)$ measures how much the match outcome hangs in the balance on delivery $b$. It is formulated as the theoretical swing sensitivity of the win probability function:

$$L(b) = 4 \cdot W_{\text{bat}}(b-1) \cdot (1.0 - W_{\text{bat}}(b-1)) \cdot \Phi(b)$$

Where:
- $4 \cdot W \cdot (1 - W) \in [0, 1]$ represents the parabolic win probability entropy, peaking at $1.0$ when $W = 0.50$ (knife-edge game) and approaching $0.0$ when $W \to 0$ or $1$.
- $\Phi(b)$ is the **Phase & Resource Urgency Multiplier**:
  $$\Phi(b) = 1.0 + \alpha_{\text{phase}} \cdot \left(\frac{120 - B_{\text{rem}}(b)}{120}\right) + \beta_{\text{chase}} \cdot \mathbb{I}_{\{\text{inn}=2\}} \cdot \left(\frac{\text{RRR}(b)}{\text{CRR}(b) + 1.0}\right)$$

Parameters $\alpha_{\text{phase}} \in [0.2, 0.5]$ and $\beta_{\text{chase}} \in [0.2, 0.5]$ will be formally calibrated in Stage 7B to ensure $L(b) \in [0.1, 2.0]$, with par leverage defined at $L_{\text{par}} = 1.0$.

### 4.3 Crisis Severity Index ($\text{CSI}$)
Measures how deeply a batting unit is compromised, independent of chase equations:
$$\text{CSI}(b) = \omega_w \cdot \left(\frac{W_{\text{lost}}(b)}{10}\right) + \omega_r \cdot \max\left(0, \frac{\text{Par Score}(b) - \text{Actual Score}(b)}{\text{Par Score}(b)}\right)$$
$\text{CSI}(b) \in [0, 1]$ elevates player credit when performing after rapid top-order dismissals (e.g. 3 wickets in the powerplay).

---

## 5. Multi-Scale Swing and Impact Window Detection

Rather than relying on arbitrary, single-delivery thresholds, HPP employs a multi-scale rolling detector to identify significant match movements:

### 5.1 Detection Scales
1. **Micro-Event (Single Delivery):** $|\Delta W(b)| \ge \theta_{\text{single}}$ (e.g. wickets, sixes in close chases).
2. **Over-Level Aggregate (Contiguous 6 Legal Balls):** $|\sum_{i=1}^6 \Delta W(b_i)| \ge \theta_{\text{over}}$ (e.g. shutdown overs, boundary barrages).
3. **Macro-Stint Window (Partnership or Crease Tenure):** Cumulative swing over a 15–30 ball window $|\Delta W_{\text{window}}| \ge \theta_{\text{macro}}$ (e.g. 40-run rescue partnerships).

### 5.2 Dynamic Contextual Thresholds
Thresholds are dynamically adjusted by match context rather than fixed globally:
$$\theta(b) = \theta_{\text{base}} \cdot \sqrt{\frac{B_{\text{rem}}(b)}{120}} \cdot \lambda_{\text{comp}}$$
Where $\lambda_{\text{comp}}$ accounts for competition scoring density (e.g. higher in IPL death overs, lower in low-scoring associate T20Is).

---

## 6. Batting HPP Methodology: Build-Up vs Impact Dynamics

### 6.1 The Two-Phase Batter Model
A major flaw in naive impact metrics is evaluating batters only during the explosive boundary-hitting finish while ignoring the foundational rebuilding that made the finish possible. HPP explicitly partitions a batter's innings into two temporal phases:

```
Batter Inning Timeline:
Entry (Ball e) ------------------------ Boundary Window Start (Ball s) ------------------- Exit/End (Ball x)
[               BUILD-UP PHASE               ] [                  IMPACT PHASE                  ]
* Dot avoidance, strike rotation              * Direct boundary hitting, acceleration
* Partnership stabilization, crisis defense   * Sharp win probability elevation
* Weight: gamma_bu in [0.30, 0.45]            * Weight: gamma_imp in [0.55, 0.70]
```

1. **Build-Up Phase ($b \in [e, s-1]$):**
   - Covers the deliveries faced from entry up to the onset of the decisive acceleration window.
   - Evaluates: Strike rotation percentage, dot-ball avoidance, partnership stabilization under crisis ($\text{CSI}$), and resistance to bowler pressure.
2. **Impact Phase ($b \in [s, x]$):**
   - Covers the deliveries during the active probability surge.
   - Evaluates: Direct boundary conversion, WPA creation, acceleration relative to required run rate.

### 6.2 Supporting Batter Recognition
In modern T20 cricket, massive chases frequently feature an asymmetric partnership:
- **Batter A (The Primary Accelerator):** Scores 52 off 24 balls (SR 216.7), generating $+0.35$ WPA.
- **Batter B (The Supporting Anchor):** Scores 18 off 14 balls (SR 128.6), takes singles on balls 1 and 2 of each over to give Batter A the strike, faces 0 dot balls, and loses 0 wickets.

#### Supporting Attribution Policy:
- Batter B is **NOT** assigned zero credit or penalized for a lower strike rate.
- Batter B receives explicit **Strike Rotation & Partnership Maintenance Credit**:
  $$\text{HPP}_{\text{support}} = \kappa_1 \cdot \text{Singles to Striker} + \kappa_2 \cdot (1 - \text{Dot Rate}) + \kappa_3 \cdot \Delta W_{\text{partnership\_sustain}}$$
- Batter A receives the primary acceleration credit, but Batter B's indispensable contribution to the partnership's survival is preserved in their Net HPP.

---

## 7. Bowling HPP Methodology: Shutdown, Dot Pressure & Wicket Impact

Bowling HPP evaluates a bowler's ability to suppress scoring and take decisive wickets, especially when the opposition is dominant.

### 7.1 The Contextual Shutdown Over
A bowler who delivers an over conceding only 4 runs when the required run rate is 11.5 per over has produced an enormous match impact, even if no wickets fell.

#### Contextual Expected Runs Conceded ($\mathbb{E}[R_{\text{over}}]$):
$$\mathbb{E}[R_{\text{over}}] = f(\text{Phase}, \text{Venue Par}, \text{Recent CRR}, W_{\text{rem}}, \text{Batter ABCs})$$
Where:
- If a team has been scoring at $12.5$ RPO over the last 4 overs, and the baseline death-over expectation is $11.0$ RPO, then conceding $5$ runs represents a net performance delta of:
  $$\text{Shutdown Delta} = \mathbb{E}[R_{\text{over}}] - R_{\text{actual}} = 11.0 - 5.0 = +6.0 \text{ runs saved}$$
- This run saving is multiplied by the delivery leverage index to compute $\text{HPP}_{\text{shutdown}}$.
- *Contrast:* Conceding 5 runs in the first over of a match when expectation was 6.5 runs earns a minor positive score, properly calibrated to context.

### 7.2 Dot-Ball Pressure Accumulation
Bowling consecutive dot balls creates mathematical compression in a chase by inflating the Required Run Rate:
$$\text{Dot Pressure Score} = \sum_{d \in \text{dots}} L(d) \cdot \Delta \text{RRR}(d)$$
Dot balls bowled against high-ABC batters or in high-leverage death overs receive significantly higher weighting than powerplay dot balls.

### 7.3 Mandatory Wicket Attribution Rules
Dismissal attribution follows strict physical responsibility guidelines:

| Dismissal Type | Bowler Wicket Credit | Batting Penalty | Fielding Points | Justification |
| :--- | :---: | :---: | :---: | :--- |
| **Bowled** | **100% Full Credit** | Full Dismissal Debit | None | Direct bowler execution defeat of batter defense. |
| **LBW** | **100% Full Credit** | Full Dismissal Debit | None | Direct bowler execution trapping batter in front. |
| **Caught** | **100% Full Credit** | Full Dismissal Debit | None (0%) | Bowler induced the miscue; fielder did not create the wicket opportunity. |
| **Stumped** | **100% Full Credit** | Full Dismissal Debit | None (0%) | Bowler deceived batter in flight/turn; wicketkeeper execution not separately point-scored. |
| **Run-Out** | **0% Bowler Credit** | Dismissed Batter Debit | None (0%) | Unforced running error; bowler did not physically induce the wicket. |

### 7.4 Partnership Breaking
When a bowler takes a wicket that terminates an established, high-momentum partnership ($R_{\text{part}} \ge 40$ runs), the bowler receives a bonus **Partnership Disruption Multiplier**:
$$\text{HPP}_{\text{break}} = \text{Base Wicket HPP} \cdot \left(1.0 + \mu \cdot \frac{R_{\text{partnership}}}{50}\right)$$
This credit is bounded to prevent double-counting with direct $\Delta W$ WPA.

---

## 8. Positive, Negative, Net, and Average HPP Framework

### 8.1 Dual-Sided Accounting
Every player action is signed. In competitive sports analytics, discarding negative contributions creates severe survivorship bias. HPP mandates dual-sided accounting across all matches and disciplines:

1. **Positive HPP ($\text{HPP}^+$):** The sum of all positive value-creating, maintaining, and recovering actions.
   $$\text{HPP}^+ = \sum_{b} \max(0, \text{HPP}(b))$$
2. **Negative HPP ($\text{HPP}^-$):** The sum of all negative value-destroying actions (e.g. dot-ball consumption in chases, boundary concession, unforced extras, soft dismissals). Stored as an absolute positive magnitude; displayed with a negative sign.
   $$\text{HPP}^- = \sum_{b} |\min(0, \text{HPP}(b))|$$
3. **Net HPP ($\text{HPP}_{\text{net}}$):** The overall net value generated by the player in the match:
   $$\text{HPP}_{\text{net}} = \text{HPP}^+ - \text{HPP}^-$$
4. **Average HPP ($\text{HPP}_{\text{avg}}$):** Net HPP normalized by eligible match appearances:
   $$\text{HPP}_{\text{avg}} = \frac{\sum_{m} \text{HPP}_{\text{net}}(m)}{N_{\text{eligible}}}$$

### 8.2 Team Outcome Independence
- A player on a **losing team** who scores 75 off 42 balls from 20/4 receives a high positive batting HPP ($+85.0$), correctly recognizing their heroic performance despite teammate failures.
- A player on a **winning team** who bowls 2 overs for 38 runs ($19.0$ RPO) in an easy defense receives a substantial negative bowling HPP ($-32.0$), preventing free-riding on team victories.

---

## 9. Multi-Tier Historical Aggregation & Participation Policies

### 9.1 Aggregation Hierarchy
HPP aggregates player records hierarchically using standard relational keys:
```
Match Level (N = 190,575 delivery states across 798 matches)
   |
   +--> Tournament Season (e.g. IPL 2024, T20I Series 2025)
   |
   +--> Calendar Year (2022, 2023, 2024, 2025, 2026)
   |
   +--> Custom Date / Competition Range (e.g. Last 24 Months, All ICC Tournaments)
   |
   +--> Career / All-Time Corpus (798 Standard T20 Matches)
```

### 9.2 Strict Participation Rules & Denominators

#### Rule 1: DNB (Did Not Bat) Non-Zeroing
- If a player is named in the playing XI but does not bat ($\text{DNB} = \text{True}$), their batting record for that match is **`NaN` / Excluded**.
- **Crucial Invariant:** DNB is **NEVER** assigned $0.0$ HPP. Assigning $0.0$ would artificially depress the player's career Average Batting HPP simply because their top order finished the chase.
- Batting averages use the **Batted Appearances Denominator**:
  $$\text{Batting HPP}_{\text{avg}} = \frac{\sum_{m \in \text{Batted}} \text{Batting HPP}_{\text{net}}(m)}{N_{\text{batted\_innings}}}$$

#### Rule 2: Did Not Bowl (DNBowl) Non-Zeroing
- If a specialist batter or player does not bowl in a match, their bowling record is **`NaN` / Excluded**.
- Bowling averages use the **Bowled Appearances Denominator**:
  $$\text{Bowling HPP}_{\text{avg}} = \frac{\sum_{m \in \text{Bowled}} \text{Bowling HPP}_{\text{net}}(m)}{N_{\text{bowled\_innings}}}$$

#### Rule 3: Overall Eligible-Match Denominator
- The Overall HPP Average uses the **Total Confirmed XI Match Appearances** ($N_{\text{matches}}$) where the player was selected and eligible to impact the match:
  $$\text{Overall HPP}_{\text{avg}} = \frac{\sum_{m} \left(\text{Batting HPP}_{\text{net}}(m) + \text{Bowling HPP}_{\text{net}}(m)\right)}{N_{\text{matches}}}$$

---

## 10. Overall HPP Composite Rating Formulation

### 10.1 Avoiding the All-Rounder Distortion
A naive summation of Batting HPP and Bowling HPP introduces a severe bias in favor of all-rounders: an all-rounder who contributes slightly above average with both bat and ball would routinely outrank the world's most dominant specialist batter or specialist bowler.

Conversely, averaging disciplines penalizes all-rounders for bowling an occasional over.

### 10.2 Proposed Composite Strategies (For Stage 7B Validation)
The specification proposes two candidate aggregation formulations to be validated in Stage 7B:

#### Candidate Model A: Independent Percentile Standardization (Recommended)
Standardizes Batting and Bowling HPP against their respective active population distributions before combining:
$$Z_{\text{bat}} = \frac{\text{Batting HPP}_{\text{net}} - \mu_{\text{bat}}}{\sigma_{\text{bat}}}, \quad Z_{\text{bowl}} = \frac{\text{Bowling HPP}_{\text{net}} - \mu_{\text{bowl}}}{\sigma_{\text{bowl}}}$$
$$\text{Overall HPP} = \max(Z_{\text{bat}}, Z_{\text{bowl}}) + \lambda_{\text{all\_round}} \cdot \min(Z_{\text{bat}}, Z_{\text{bowl}})$$
Where $\lambda_{\text{all\_round}} \in [0.25, 0.40]$ awards an explicit, controlled bonus for secondary discipline competence without eclipsing elite single-discipline specialization.

#### Candidate Model B: Activity-Weighted Volume Composite
Weights discipline contributions by balls faced and legal balls bowled relative to team innings capacity:
$$\text{Overall HPP} = w_{\text{bat}} \cdot \text{Batting HPP} + w_{\text{bowl}} \cdot \text{Bowling HPP}$$
Where weights are proportional to match involvement share.

---

## 11. Provenance Integrity: Handling Production vs 5-Fold OOF Predictions

As established in Stage 6B.8, the underlying Win Probability Engine draws from two distinct historical prediction sources:
1. **2022–2024 Retrospective Five-Fold GroupKFold OOF Predictions ($N = 477$ matches):**
   - Out-of-sample cross-validation predictions.
   - Preserves fold parameters ($\text{fold\_id} \in [0, 4]$) and fold-excluded Platt calibrators.
2. **2025–2026 Frozen Production-Calibrated Predictions ($N = 321$ matches):**
   - True chronologically forward-looking predictions (2025 validation, 2026 untouched test).

### 11.1 Methodological Guardrails
- **No Data Blending in Validation:** Validation benchmarks must report HPP metrics separately for 2022–2024 (OOF) and 2025–2026 (Production) to verify that cross-validation variance does not distort player rankings.
- **Preservation of 6B.8 Warnings:**
  - *2026 First-Innings Drift:* Because 2026 first-innings matches experienced higher run-scoring and an ECE of $11.41\%$, HPP calculations in 2026 first innings must apply conservative shrinkage to boundary WPA swings.
  - *OTHER_T20 Low-Sample:* OTHER_T20 matches ($N = 28$) must carry a low-sample provenance flag; player career aggregates must allow filtering out minor domestic leagues to prevent rating inflation against weaker opposition.

---

## 12. Anti-Double-Counting Protocols & Attribution Reconciliation

### 12.1 The Team-Level WPA Conservation Theorem
On any legal delivery $b$, the net win probability change of the batting team must equal the sum of player-attributed impacts plus the unattributed structural residual:

$$\Delta W_{\text{bat}}(b) \equiv \Delta W_{\text{striker}}(b) + \Delta W_{\text{non\_striker}}(b) + \Delta W_{\text{bowler\_err}}(b) + \Delta W_{\text{residual}}(b)$$

$$\Delta W_{\text{bowl}}(b) \equiv -\Delta W_{\text{bat}}(b)$$

### 12.2 Prohibited Attribution Patterns (Strictly Enforced)
1. **No Duplicate Wicket Awarding:** A dismissal cannot be credited to bowler WPA, wicket impact, and partnership breaking simultaneously without mutual orthogonalization.
2. **No Fielder Double-Dip:** No credit for catches or stumpings is diverted to fielders.
3. **No Overlapping Window Duplication:** If delivery 112 is part of an over shutdown ($[109, 114]$) and also a multi-over spell ($[103, 114]$), delivery 112's impact is counted exactly once in the player's cumulative match score.
4. **Transparent Residual Accounting:** If a batting team loses win probability purely due to required run rate inflation during a dot ball where the bowler bowled a wide line, the resulting $-\Delta W$ is apportioned between the bowler's positive dot pressure and the batting unit's negative resource decay, with the remainder tagged as structural drift.

---

## 13. System Invariants, Guardrails, and Boundary Constraints

### 13.1 Strict Invariant Checklist
1. **Mathematical Invariant:** $HPP_{\text{net}} = HPP^+ - HPP^-$ strictly holds for all players, matches, and aggregates.
2. **Discipline Isolation:** Batting HPP is strictly independent of bowling performance in the same match.
3. **Participation Invariant:** A DNB record never contributes $0.0$ to batting averages; a DNBowl record never contributes $0.0$ to bowling averages.
4. **Data Freeze:** Zero modifications to Stage 5B, 5C, 6B models, calibration artifacts, or trajectory JSONs.
5. **Phase Boundary:** This specification concludes Stage 7A. Implementation is strictly reserved for Stage 7B upon user authorization.

