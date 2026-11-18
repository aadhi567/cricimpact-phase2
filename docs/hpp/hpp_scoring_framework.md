# CricImpact Phase 2 — Stage 7A: HPP Scoring Framework & Formulations

**Document Version:** 1.0 (Draft Specification)  
**Author:** Google DeepMind Antigravity Architecture Team  
**Date:** November 14, 2026  
**Status:** READ-ONLY METHODOLOGY SPECIFICATION  
**Scope:** Mathematical Scoring Models, Formulations, Weighting Schemes, and Concrete Worked Examples  

---

## 1. Mathematical Architecture Overview

The High Pressure Player (HPP) score is a standardized, signed impact metric that measures a player's net contribution to their team's probability of victory in high-leverage situations.

### Core Mathematical Properties:
1. **Signed Decomposition:** For every match, stint, and player, HPP separates positive contributions ($\text{HPP}^+$) from negative contributions ($\text{HPP}^-$).
2. **Strict Identity:** $\text{HPP}_{\text{net}} \equiv \text{HPP}^+ - \text{HPP}^-$.
3. **Bounded Sensitivity:** Scores are anchored to Win Probability Added ($\Delta W$) scaled by Normalized Leverage ($L$) and Crisis Severity ($C$).
4. **Standardized Scale:** Match scores typically range from $-50.0$ to $+100.0$, with $0.0$ representing a neutral performance matching expected baseline.

---

## 2. Batting HPP Mathematical Formulation

A batter's total match score combines their performance during the **Build-Up Phase** (stabilization and platform construction) and the **Impact Phase** (boundary acceleration and target execution):

$$\text{Batting HPP}_{\text{match}} = \text{Batting HPP}_{\text{buildup}} + \text{Batting HPP}_{\text{impact}} + \text{Batting HPP}_{\text{support}}$$

### 2.1 Build-Up Phase Score ($\text{Batting HPP}_{\text{buildup}}$)
For all deliveries $b$ faced by the batter during the build-up phase ($b \in \mathcal{B}_{\text{buildup}}$):

$$\text{Batting HPP}_{\text{buildup}} = \sum_{b \in \mathcal{B}_{\text{buildup}}} \left[ \Delta W_{\text{str}}(b) \cdot 100 \cdot L(b) + \left(\frac{\text{Runs}(b) - \mathbb{E}[\text{Runs}(b)]}{2.0}\right) \cdot (1.0 + \text{CSI}(b)) \right]$$

- **Interpretation:** In the build-up phase, runs scored above expectation under high crisis ($\text{CSI}$) are rewarded heavily, even if raw win probability has not yet surged.
- **Negative Impact:** Dot balls faced in a chase penalize the batter via the negative $\Delta W_{\text{str}}(b)$ resulting from clock consumption.

### 2.2 Impact Phase Score ($\text{Batting HPP}_{\text{impact}}$)
For all deliveries $b$ faced during designated match-impact windows ($b \in \mathcal{B}_{\text{impact}}$):

$$\text{Batting HPP}_{\text{impact}} = \sum_{b \in \mathcal{B}_{\text{impact}}} \left[ \Delta W_{\text{str}}(b) \cdot 125 \cdot L(b) \cdot \left(\frac{\text{Actual SR}(b)}{\text{Required SR}(b) + 10.0}\right)^{0.5} \right]$$

- **Interpretation:** Boundaries hit during critical chase windows are magnified by leverage and strike rate ratio, capturing match-winning acceleration.

### 2.3 Supporting Partner Score ($\text{Batting HPP}_{\text{support}}$)
When acting as the secondary partner in an active high-impact stand:

$$\text{Batting HPP}_{\text{support}} = \sum_{b \in \mathcal{B}_{\text{support}}} \left[ \mathbb{I}_{\{\text{Rotated Strike}\}} \cdot 1.5 \cdot L(b) + (1.0 - \text{DotRate}) \cdot 2.0 \right]$$

---

## 3. Bowling HPP Mathematical Formulation

A bowler's total match score combines their containment in **Shutdown Overs**, continuous **Dot-Ball Pressure**, and **Wicket Impact**:

$$\text{Bowling HPP}_{\text{match}} = \text{Bowling HPP}_{\text{shutdown}} + \text{Bowling HPP}_{\text{dots}} + \text{Bowling HPP}_{\text{wickets}} - \text{Bowling HPP}_{\text{penalties}}$$

### 3.1 Shutdown Over Impact ($\text{Bowling HPP}_{\text{shutdown}}$)
Evaluated across each completed 6-ball over $o$ delivered by the bowler:

$$\text{Bowling HPP}_{\text{shutdown}}(o) = \max\left(0.0, \mathbb{E}[R(o)] - R_{\text{actual}}(o)\right) \cdot \overline{L}(o) \cdot 2.5$$

Where:
- $\mathbb{E}[R(o)]$ is the context-aware expected runs conceded in over $o$.
- $R_{\text{actual}}(o)$ is total runs conceded (including wides and no-balls).
- $\overline{L}(o)$ is the mean leverage across the over.
- If $R_{\text{actual}}(o) > \mathbb{E}[R(o)]$, this term is $0.0$ (expensive overs enter the negative ledger via penalties).

### 3.2 Dot-Ball Pressure ($\text{Bowling HPP}_{\text{dots}}$)
For each legal dot ball delivered ($b \in \mathcal{D}_{\text{dots}}$):

$$\text{Bowling HPP}_{\text{dots}} = \sum_{b \in \mathcal{D}_{\text{dots}}} \left[ |\Delta W_{\text{bowl}}(b)| \cdot 80 \cdot L(b) + 1.0 \cdot \mathbb{I}_{\{\text{Consecutive Dot}\}} \right]$$

### 3.3 Wicket Impact & Partnership Breaking ($\text{Bowling HPP}_{\text{wickets}}$)
For each legal dismissal $w \in \mathcal{W}_{\text{bowler}}$:

$$\text{Bowling HPP}_{\text{wickets}}(w) = |\Delta W_{\text{bowl}}(w)| \cdot 120 \cdot L(w) \cdot \left(\frac{\text{ABC}_{\text{batter}}}{50.0}\right) + \text{PBB}(w)$$

Where:
$$\text{PBB}(w) = \min\left(20.0, 5.0 \cdot \left(\frac{R_{\text{partnership}}}{40.0}\right)\right)$$

### 3.4 Bowling Penalties ($\text{Bowling HPP}_{\text{penalties}}$)
Bowler errors and boundary concessions directly enter the negative ledger:

$$\text{Bowling HPP}_{\text{penalties}} = \sum_{b \in \mathcal{B}_{\text{conceded}}} \left[ |\Delta W_{\text{bowl}}(b)| \cdot 100 \cdot L(b) + \mathbb{I}_{\{\text{Wide/NB}\}} \cdot 3.0 \cdot L(b) \right]$$

---

## 4. Signed Accounting & Aggregation Formulations

### 4.1 Match-Level Accumulation
For each player $p$ in match $m$:
$$\text{HPP}^+(p, m) = \sum_{b} \max(0, \text{HPP}(p, b))$$
$$\text{HPP}^-(p, m) = \sum_{b} |\min(0, \text{HPP}(p, b))|$$
$$\text{HPP}_{\text{net}}(p, m) = \text{HPP}^+(p, m) - \text{HPP}^-(p, m)$$

### 4.2 Multi-Match Aggregation
For any aggregation window $\mathcal{M}$ (season, tournament, career):
$$\text{Total HPP}^+(p, \mathcal{M}) = \sum_{m \in \mathcal{M}} \text{HPP}^+(p, m)$$
$$\text{Total HPP}^-(p, \mathcal{M}) = \sum_{m \in \mathcal{M}} \text{HPP}^-(p, m)$$
$$\text{Total HPP}_{\text{net}}(p, \mathcal{M}) = \text{Total HPP}^+(p, \mathcal{M}) - \text{Total HPP}^-(p, \mathcal{M})$$

### 4.3 Participation-Adjusted Averages
$$\text{Batting HPP}_{\text{avg}}(p, \mathcal{M}) = \frac{\sum_{m \in \mathcal{M}_{\text{batted}}} \text{Batting HPP}_{\text{net}}(p, m)}{|\mathcal{M}_{\text{batted}}|}$$

$$\text{Bowling HPP}_{\text{avg}}(p, \mathcal{M}) = \frac{\sum_{m \in \mathcal{M}_{\text{bowled}}} \text{Bowling HPP}_{\text{net}}(p, m)}{|\mathcal{M}_{\text{bowled}}|}$$

$$\text{Overall HPP}_{\text{avg}}(p, \mathcal{M}) = \frac{\sum_{m \in \mathcal{M}_{\text{eligible}}} \left(\text{Batting HPP}_{\text{net}}(p, m) + \text{Bowling HPP}_{\text{net}}(p, m)\right)}{|\mathcal{M}_{\text{eligible}}|}$$

---

## 5. Overall HPP Composite Rating Formulation

To combine Batting HPP and Bowling HPP into a single unified rating without unfairly inflating all-rounders or penalizing specialists:

### 5.1 Recommended Model: Standardized Dual-Threshold Composite (Model A)
1. **Z-Score Normalization:** Across the historical player population:
   $$Z_{\text{bat}}(p) = \frac{\text{Batting HPP}_{\text{avg}}(p) - \mu_{\text{bat}}}{\sigma_{\text{bat}}}$$
   $$Z_{\text{bowl}}(p) = \frac{\text{Bowling HPP}_{\text{avg}}(p) - \mu_{\text{bowl}}}{\sigma_{\text{bowl}}}$$
2. **Primary Discipline Selection:**
   $$Z_{\text{primary}}(p) = \max\left(Z_{\text{bat}}(p), Z_{\text{bowl}}(p)\right)$$
   $$Z_{\text{secondary}}(p) = \min\left(Z_{\text{bat}}(p), Z_{\text{bowl}}(p)\right)$$
3. **Controlled Secondary Discipline Bonus:**
   $$\text{Overall HPP}(p) = 50.0 + 15.0 \cdot \left[ Z_{\text{primary}}(p) + \lambda_{\text{all\_round}} \cdot \max(0.0, Z_{\text{secondary}}(p)) \right]$$
   Where $\lambda_{\text{all\_round}} = 0.30$.
   - **Specialist Batter:** If $Z_{\text{bat}} = +2.0$ (elite) and $Z_{\text{bowl}} = \text{NaN}$ (did not bowl), secondary contribution is $0.0$. Overall HPP = $50 + 15(2.0) = \mathbf{80.0}$.
   - **Genuine All-Rounder:** If $Z_{\text{bat}} = +1.5$ and $Z_{\text{bowl}} = +1.2$, Overall HPP = $50 + 15(1.5 + 0.30(1.2)) = \mathbf{77.9}$.
   - *Result:* An all-rounder with strong secondary utility receives an earned bonus, but cannot eclipse a historically generational specialist without elite performance in at least one discipline.

---

## 6. Concrete Worked Examples

### 6.1 Example 1: Batting HPP Calculation (Chase Rescue & Acceleration)
**Match Situation:** Chasing $175$ in an IPL match. Team is $35/3$ after 5 overs ($W_{\text{bat}} = 0.22$, $\text{CSI} = 0.65$, Crisis Recovery regime).
**Player:** Batter X enters at No. 5.

#### Phase 1: Build-Up Stint (Overs 6–11, 18 balls faced)
- **Performance:** Scores 22 runs off 18 balls (2 fours, 10 singles/twos, 6 dots).
- **Match State at Over 11:** Score reaches $85/3$ ($W_{\text{bat}}$ rises from $0.22 \to 0.40$).
- **Calculations:**
  - Direct $\Delta W_{\text{str}}$ over stint: $+0.12$.
  - Mean leverage: $\overline{L} = 1.15$. Mean $\text{CSI} = 0.55$.
  - $\text{Batting HPP}_{\text{buildup}} = (0.12 \times 100 \times 1.15) + (22 - 18) \times (1.0 + 0.55) = 13.80 + 6.20 = \mathbf{+20.00}$.

#### Phase 2: Impact Phase (Overs 15–19, 14 balls faced)
- **Match Situation at Over 15:** $120/4$, needing $55$ runs off 30 balls ($W_{\text{bat}} = 0.45$, $\text{NLI} = 1.65$).
- **Performance:** Scores 36 runs off 14 balls (3 sixes, 3 fours, 2 singles, 6 dots, SR 257.1).
- **Match State at Over 19:** Target reduced to $6$ runs off 6 balls ($W_{\text{bat}}$ rises from $0.45 \to 0.88$, $\Delta W = +0.43$).
- **Calculations:**
  - $\text{Batting HPP}_{\text{impact}} = 0.43 \times 125 \times 1.65 \times (257.1 / 120.0)^{0.5} = 0.43 \times 125 \times 1.65 \times 1.464 = \mathbf{+129.80}$.

#### Phase 3: Negative Incurred (Dots in Death Overs)
- 6 dot balls faced in impact phase incurred $\Delta W$ clock decay: $\mathbf{-18.50}$.

#### Match Net Result for Batter X:
- $\text{Batting HPP}^+ = 20.00 + 129.80 = \mathbf{+149.80}$
- $\text{Batting HPP}^- = \mathbf{18.50}$
- $\text{Batting HPP}_{\text{net}} = 149.80 - 18.50 = \mathbf{+131.30}$ (Match-Winning Super-Clutch Performance).

---

### 6.2 Example 2: Bowling HPP Calculation (Death Over Shutdown with Wicket)
**Match Situation:** Opponent chasing $168$. Needs $22$ runs from 12 balls ($W_{\text{bowl}} = 0.38$, $\text{NLI} = 1.75$).
**Player:** Bowler Y bowls the 19th over.
**Context:** Opponent was scoring at $11.0$ RPO over previous 4 overs. Expected runs for over 19: $\mathbb{E}[R] = 11.5$ runs.

#### Delivery Breakdown (Over 19):
1. **Ball 19.1:** 1 run (yorker to established star batter). $\Delta W_{\text{bowl}} = +0.03$. $L = 1.70$.
2. **Ball 19.2:** Dot ball (play and miss). $\Delta W_{\text{bowl}} = +0.07$. $L = 1.75$.
3. **Ball 19.3:** **WICKET (Clean Bowled)**. Star batter (ABC = 62.5) dismissed! Partnership of 55 runs broken.
   - $\Delta W_{\text{bowl}} = +0.22$. $L = 1.80$.
   - $\text{WIS} = 0.22 \times 120 \times 1.80 \times (62.5 / 50.0) = \mathbf{+59.40}$.
   - $\text{PBB} = \min(20.0, 5.0 \times (55 / 40)) = \mathbf{+6.88}$.
4. **Ball 19.4:** 1 run (incoming new batter). $\Delta W_{\text{bowl}} = +0.02$. $L = 1.65$.
5. **Ball 19.5:** Dot ball. $\Delta W_{\text{bowl}} = +0.06$. $L = 1.60$.
6. **Ball 19.6:** 2 runs. $\Delta W_{\text{bowl}} = +0.01$. $L = 1.55$.

#### Over Summary:
- **Actual Runs Conceded:** 4 runs ($1 + 0 + 0 + 1 + 0 + 2$).
- **Shutdown Over Delta:** $\mathbb{E}[R] - R_{\text{actual}} = 11.5 - 4.0 = \mathbf{+7.5 \text{ runs saved}}$.
- $\text{Bowling HPP}_{\text{shutdown}} = 7.5 \times 1.70 \times 2.5 = \mathbf{+31.88}$.
- **Wicket Impact:** $59.40 + 6.88 = \mathbf{+66.28}$.
- **Dot-Ball Pressure:** 2 dots $\times (0.065 \times 80 \times 1.68) = \mathbf{+17.47}$.
- **Penalties Incurred:** 4 runs conceded under high leverage: $\mathbf{-9.20}$.

#### Match Net Result for Bowler Y (from Over 19 alone):
- $\text{Bowling HPP}^+ = 31.88 + 66.28 + 17.47 = \mathbf{+115.63}$
- $\text{Bowling HPP}^- = \mathbf{9.20}$
- $\text{Bowling HPP}_{\text{net}} = 115.63 - 9.20 = \mathbf{+106.43}$ (Game-Changing Death Over Shutdown).

