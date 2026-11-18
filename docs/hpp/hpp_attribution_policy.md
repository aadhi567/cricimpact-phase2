# CricImpact Phase 2 — Stage 7A: HPP Attribution Policy & Rules

**Document Version:** 1.0 (Draft Specification)  
**Author:** Google DeepMind Antigravity Architecture Team  
**Date:** November 14, 2026  
**Status:** READ-ONLY METHODOLOGY SPECIFICATION  
**Scope:** Authoritative Attribution Rules, Credit Splitting, and Anti-Double-Counting Protocols  

---

## 1. Core Principles of Credit Assignment

In competitive cricket analytics, win probability shifts at the team level, but fans, coaches, and selectors evaluate individual players. The primary objective of the **HPP Attribution Policy** is to define a mathematically sound, non-arbitrary mechanism for translating team-level win probability changes ($\Delta W$) into individual player contributions while strictly preventing double-counting, false inflation, and credit misallocation.

### Three Axioms of Attribution:
1. **Conservation of Impact:** On any given delivery, the sum of individual player credits and debits must balance the net team-level performance delta, leaving an explicit, visible residual rather than forcing artificial closures.
2. **Physical Responsibility:** A player is credited or debited only for events they physically execute or directly influence.
3. **Discipline Independence:** Batting performance and bowling performance are evaluated under separate ledgers; an individual's batting failures never directly cancel or alter their bowling accomplishments in the same match.

---

## 2. Delivery-Level Credit Decomposition Architecture

For every delivery $b$, the gross change in batting team win probability $\Delta W_{\text{bat}}(b)$ is decomposed into four orthogonal components:

$$\Delta W_{\text{bat}}(b) = \Delta W_{\text{striker}}(b) + \Delta W_{\text{non\_striker}}(b) + \Delta W_{\text{bowler\_error}}(b) + \Delta W_{\text{contextual\_drift}}(b)$$

$$\Delta W_{\text{bowl}}(b) = -\Delta W_{\text{bat}}(b)$$

### 2.1 The Striker's Share ($\Delta W_{\text{striker}}$)
- **Positive Bat Actions:** Runs scored off the bat (1, 2, 3, 4, 6) increase batting win probability. The striker receives the primary share of the positive swing:
  $$\Delta W_{\text{striker}}(b) = \Delta W_{\text{bat}}(b) - \Delta W_{\text{drift}}(b)$$
- **Dismissal Debits:** If the striker is dismissed (bowled, caught, lbw, stumped), the entire negative win probability swing is assigned as a debit to the dismissed striker:
  $$\Delta W_{\text{striker}}(b) = \Delta W_{\text{bat}}(b) \quad (< 0)$$

### 2.2 The Non-Striker's Share ($\Delta W_{\text{non\_striker}}$)
- **Normal Deliveries:** Receives $0.0$ direct WPA on boundaries, dot balls, or regular singles.
- **Strike Rotation Partnership Credit:** When a single is completed that transfers strike to a high-momentum partner in a chase, the non-striker receives a calculated **Strike Rotation Support Score** in their stint ledger, without deducting from the striker's run credit.
- **Run-Out Fault Attribution:** See Section 3.2.

### 2.3 The Bowler's Share ($\Delta W_{\text{bowler}}$)
- **Defensive Containment:** On a dot ball, the bowler earns positive bowling impact:
  $$\Delta W_{\text{bowler}}(b) = |\Delta W_{\text{bat}}(b)|$$
- **Unforced Bowling Errors:** On a wide or no-ball, the bowler is directly debited for the extra run, the extra ball required, and the resulting win probability loss:
  $$\Delta W_{\text{bowler\_error}}(b) = \Delta W_{\text{bowl}}(b) \quad (< 0)$$
- **Boundary Concessions:** When a four or six is hit, the bowler absorbs the full negative bowling swing:
  $$\Delta W_{\text{bowler}}(b) = -\Delta W_{\text{bat}}(b) \quad (< 0)$$

### 2.4 Contextual Drift ($\Delta W_{\text{contextual\_drift}}$)
- In a chase, every legal delivery bowled naturally increases the Required Run Rate if no boundary is scored. This structural decay exists even if the batter made solid contact for a dot ball.
- HPP separates natural clock decay from active batter failure, ensuring batters are not excessively penalized for defending good balls in early overs.

---

## 3. Mandatory Wicket Attribution Rules

Dismissal events produce the largest single-delivery win probability swings in cricket. Strict attribution guidelines are mandated:

### 3.1 Dismissal Attribution Matrix

| Dismissal Type | Bowler HPP Credit | Dismissed Batter Debit | Partner Debit | Fielder Credit | Official Rationale |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Bowled** | **100% Full Credit** | Full Dismissal Debit | 0% | 0% (None) | Bowler directly beat batter defense; unassisted execution. |
| **LBW** | **100% Full Credit** | Full Dismissal Debit | 0% | 0% (None) | Bowler trapped batter in front of stumps; unassisted execution. |
| **Caught** | **100% Full Credit** | Full Dismissal Debit | 0% | 0% (None) | Bowler induced the false shot/miscue; fielder execution not point-scored. |
| **Stumped** | **100% Full Credit** | Full Dismissal Debit | 0% | 0% (None) | Bowler deceived batter out of crease; keeper execution not point-scored. |
| **Run-Out (Striker Dismissed)** | **0% Bowler Credit** | 60%–100% Debit | 0%–40% Debit | 0% (None) | Running error; bowler did not induce the dismissal via bowling delivery. |
| **Run-Out (Non-Striker Dismissed)**| **0% Bowler Credit** | Full Dismissal Debit | Calling Fault Debit | 0% (None) | Running error; assigned based on crease fault rules. |

### 3.2 Run-Out Attribution Protocol
Because ball-by-ball datasets record `dismissed_player_id` but do not definitively record who called the run, HPP implements a principled, objective protocol:
1. **Default Assignment:** $100\%$ of the dismissal debit is assigned to the dismissed batter (`dismissed_player_id`), as they failed to make their ground.
2. **Bowler Credit:** Bowlers receive **strictly 0.0 wicket credit** for run-outs. A run-out is not a bowling dismissal. If the bowler completed the run-out throw or tag, that was a fielding act, which is explicitly excluded from HPP.
3. **Team Bowling Gain:** The bowling team earns positive team WPA, but the credit remains in the **Unattributed Team Bowling Ledger** rather than being credited to the bowler's bowling statistics.

### 3.3 Absolute Exclusion of Fielding HPP
- **Zero Fielder Points:** Fielders who take catches, inflict run-outs, or stop boundaries receive zero independent HPP points.
- **Why Fielding is Excluded:**
  - Modern T20 data lacks comprehensive camera-tracking telemetry across all 798 historical matches (e.g. catch difficulty probability, ground coverage speed, missed run-out opportunities).
  - Subjective fielding bonuses introduce severe noise into objective player ratings.
  - HPP maintains uncompromising analytical rigor by evaluating only the two directly measurable physical disciplines: **Batting and Bowling**.

---

## 4. Extras Attribution Policy

Cricket extras fall into two distinct physical categories: bowler-fault extras and team-context extras.

### 4.1 Bowler-Fault Extras (Wides & No-Balls)
- **Wide Ball:** Debited directly to the bowler. The batter faced 0 legal balls; the bowler conceded +1 run (plus any additional runs scored), bowled an extra delivery, and gave up win probability.
  $$\Delta W_{\text{bowler}}(b) = \Delta W_{\text{bowl}}(b) \quad (< 0)$$
  The batter's ledger is completely untouched.
- **No-Ball:** Concedes an illegal delivery and awards a free hit. The entire negative impact is assigned as a debit to the bowler. Any runs scored off the bat on the no-ball are credited to the batter, but the extra penalty run and free-hit risk are absorbed by the bowler.

### 4.2 Non-Bowler Extras (Byes & Leg-Byes)
- Byes and leg-byes represent ball traversal errors or deflections off the batter's equipment.
- **Bowler Exemption:** Under official MCC scoring laws, byes and leg-byes are not charged against the bowler's analysis. In HPP, they are **NOT** debited to the bowler's bowling HPP.
- **Batter Exemption:** They are not credited to the batter's personal batting score.
- **Attribution:** The resulting $\Delta W$ is assigned to the **Team Context Ledger**.

---

## 5. Supporting Batter Recognition Policy

In asymmetric partnerships where one batter dominates the scoring, the supporting batter must be properly evaluated:

### 5.1 The Supporting Batter Dilemma
- If Batter A hits 4 sixes in an over, Batter A generated $+0.28$ WPA.
- If Batter B faced 1 ball, nudged a single to put Batter A on strike, Batter B's direct WPA was only $+0.01$.
- However, Batter B's tactical discipline in rotating strike enabled Batter A's assault.

### 5.2 The Support Credit Protocol
During an established partnership ($R_{\text{part}} \ge 30$), when a supporting batter executes positive supportive actions, they earn **Supportive HPP Points**:
1. **Strike Rotation to Hot Hand:** Awarded for scoring a single on ball 1 or 2 of an over when the partner's rolling strike rate exceeds $160$.
2. **Dot-Ball Absorption:** Avoiding dot balls under high leverage ($\text{NLI} \ge 1.20$) protects team momentum.
3. **Non-Striker Partnership Share:** A fixed fraction ($15\%$) of the partnership's collective win probability gain is shared with the supporting batter, recognizing their collaborative role in maintaining the wicket resource.
4. **Boundary Conservation:** Batter A still retains $85\%$ of the direct acceleration credit, ensuring elite power-hitters remain properly ranked at the top.

---

## 6. Partnership Breaking Credit

### 6.1 Contextual Multiplier Formulation
A wicket that breaks a 100-run partnership is substantially more valuable than a wicket that terminates a 4-run tail-end stand. When a bowler takes a legal wicket, the **Partnership Breaking Bonus ($\text{PBB}$)** is computed as:

$$\text{PBB} = \min\left(25.0, \text{Base Wicket Credit} \cdot 0.20 \cdot \left(\frac{R_{\text{partnership}}}{50.0}\right) \cdot \overline{\text{ABC}}_{\text{partners}}\right)$$

Where:
- $R_{\text{partnership}}$ is the runs accumulated in the broken partnership.
- $\overline{\text{ABC}}_{\text{partners}}$ is the mean Stage 5C Batter Contribution rating of the two batters, ensuring higher bonuses for dismissing top-order stars.
- $\text{PBB}$ is hard-capped at $+25.0$ points to prevent extreme outlier spikes.

---

## 7. Anti-Double-Counting Protocols

To maintain mathematical integrity across all 190,575 deliveries, the following anti-double-counting constraints are strictly enforced:

### 7.1 Separation of Direct WPA and Performance Bonuses
- In many analytical systems, a bowler is awarded $+0.15$ for the wicket WPA, $+50$ points for taking a wicket, and another $+30$ points for breaking the partnership, tripling the same physical action.
- In HPP, **WPA is the fundamental baseline currency**. Performance features (such as shutdown deltas and partnership breakers) are applied as **contextual multipliers on WPA**, not as additive parallel points:
  $$\text{HPP}_{\text{event}} = \Delta W \cdot \text{Multiplier}(\text{Context})$$
- If $\Delta W = 0$, the multiplier produces zero inflation.

### 7.2 Non-Overlapping Window Guarantee
- Multi-ball windows (e.g. over-level shutdowns or 3-over stints) aggregate deliveries.
- When rolling aggregations are calculated, each delivery's underlying delta is logged uniquely by `(match_id, innings, innings_ball_num)`.
- In player match summaries, the player's total match HPP is the sum over their distinct, non-overlapping delivery participations:
  $$\text{Match HPP}_{\text{player}} = \sum_{b \in \mathcal{D}_{\text{player}}} \text{HPP}(b)$$
- Overlapping rolling windows are used **strictly for regime detection**, never for additive score accumulation.

### 7.3 Unattributed Residual Accounting
Any fraction of team win probability change that cannot be definitively attributed to a specific player's direct physical action (e.g. weather-related pitch easing, unforced fielding fumbles by unknown players, umpire delays) is recorded in the `UNATTRIBUTED_RESIDUAL` ledger. It is **never** artificially forced onto the bowler or batter to force a mathematical balance.

