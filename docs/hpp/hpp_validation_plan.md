# CricImpact Phase 2 — Stage 7A: HPP Validation Plan & Test Suite

**Document Version:** 1.0 (Draft Specification)  
**Author:** Google DeepMind Antigravity Architecture Team  
**Date:** November 14, 2026  
**Status:** READ-ONLY METHODOLOGY SPECIFICATION  
**Scope:** Comprehensive Validation Protocols, Statistical Benchmarks, and 15 Mandatory Scenario Test Cases  

---

## 1. Validation Philosophy & Non-Trivial Success Criteria

A frequent fallacy in sports analytics is validating a clutch or impact rating simply by checking whether players on winning teams receive high ratings. If a rating system merely mirrors team outcomes, it is not measuring individual skill under pressure; it is merely re-labeling match results.

### The CricImpact Validation Mandates:
1. **Decoupling from Team Outcome:** A player's HPP rating must reflect their individual execution under context, not their teammates' collective outcome.
2. **Discrimination of Context:** A 60-run innings scored in a blowout must produce a radically lower HPP rating than a 40-run innings scored from 20/4 in a knife-edge chase.
3. **Mathematical Symmetry:** Positive actions generate positive ratings; negative actions generate negative debits. Every delivery must balance to the team delta.
4. **Historical Consistency:** Ranking stability must hold across the five historical seasons (2022–2026) without wild rank inversions between OOF and production data.

---

## 2. The 15 Mandatory Scenario Test Cases

The following 15 test suites must be formally executed and verified during Stage 7B validation:

### Test Case 1: High-Scoring Batter in an Easy Situation (Low Leverage Accumulator)
- **Objective:** Verify that a batter scoring heavy runs in a low-leverage, non-competitive match does not receive an inflated HPP score.
- **Scenario:** Chasing 120, team reaches 90/1 in 10 overs ($W_{\text{bat}} = 0.98, \text{NLI} = 0.15$). Batter scores 50 off 30 balls to finish the match.
- **Expected Behavior:** $\text{Batting HPP}_{\text{net}}$ remains modest ($+10.0$ to $+20.0$), reflecting low leverage and maintenance of an already assured victory.
- **Failure Condition:** Batter receives top-tier clutch rating ($> +45.0$) simply due to raw volume of runs.

### Test Case 2: Supporting Batter Rotating Strike Under Pressure
- **Objective:** Verify that a secondary batter who rotates strike and avoids dots in an intense chase earns positive HPP without scoring boundaries.
- **Scenario:** Needing 60 off 30 balls ($L = 1.70$), Partner A hits 45 off 18 balls. Batter B scores 12 off 12 balls (all singles, 0 dots, gives strike to Partner A on balls 1 and 2).
- **Expected Behavior:** Batter B earns positive $\text{Batting HPP}_{\text{support}}$ ($+15.0$ to $+25.0$) and positive $\text{Batting HPP}_{\text{net}}$.
- **Failure Condition:** Batter B receives negative HPP due to low strike rate ($100.0$) despite perfect tactical execution.

### Test Case 3: Crisis Rebuilding After Early Wickets (Recovery HPP)
- **Objective:** Verify that rebuilding an innings after a top-order collapse earns substantial Recovery HPP.
- **Scenario:** Team is $20/4$ after 4 overs in Innings 1 ($W_{\text{bat}} = 0.18, \text{CSI} = 0.72$). Batter scores 65 off 48 balls to lift the team to 155.
- **Expected Behavior:** Batter receives massive positive $\text{HPP}_{\text{recover}}$ ($+60.0$ to $+90.0$).
- **Failure Condition:** Inability to classify innings into Recovery regime or failure to reward crisis stabilization.

### Test Case 4: Batter Contributing Prior to Later Probability Swing (Build-Up Phase)
- **Objective:** Verify that a batter who establishes the platform before a teammate's explosive finish is not discarded.
- **Scenario:** Batter scores 35 off 30 balls during overs 5–14 when the pitch is difficult ($W \approx 0.45$), setting up a 10-ball finish by the next batter.
- **Expected Behavior:** Batter earns substantial $\text{Batting HPP}_{\text{buildup}}$ credit.
- **Failure Condition:** Batter receives zero or negative credit because the win probability surge occurred in over 18 after their dismissal.

### Test Case 5: Six-Run Shutdown Over Without a Wicket
- **Objective:** Verify that elite bowling containment without wickets is rewarded appropriately.
- **Scenario:** Opponent needs 24 off 12 balls in a chase ($L = 1.80$). Bowler delivers over 19 conceding only 5 runs (1, 1, dot, 1, 1, 1), pushing target to 19 off 6 balls ($W_{\text{bowl}}$ jumps from $0.40 \to 0.82$).
- **Expected Behavior:** Bowler receives elite $\text{Bowling HPP}_{\text{shutdown}}$ ($+40.0$ to $+65.0$) despite $0$ wickets.
- **Failure Condition:** Bowler receives low score due to absence of traditional wicket stats.

### Test Case 6: Bowler Breaking an Established Partnership
- **Objective:** Verify contextual reward for terminating a dangerous, high-momentum stand.
- **Scenario:** Opposition has added 85 runs in 7 overs. Bowler takes the wicket of the set batter.
- **Expected Behavior:** Bowler receives base wicket credit plus the $\text{PBB}$ bonus.
- **Failure Condition:** Dismissal is scored with the exact same weight as dismissing a No. 10 batter in a 5-run stand.

### Test Case 7: Dot-Ball Pressure Creation
- **Objective:** Verify that bowling consecutive dot balls in a chase earns positive HPP via required run rate inflation.
- **Scenario:** Bowler delivers 4 dot balls in over 16, escalating RRR from $9.5 \to 12.2$.
- **Expected Behavior:** Positive $\text{Bowling HPP}_{\text{dots}}$ accumulated across the dot deliveries.
- **Failure Condition:** Bowler receives zero credit for dot balls unless a wicket falls.

### Test Case 8: Positive Performance on a Losing Team
- **Objective:** Verify that outstanding individual resistance on a losing team is fully recognized.
- **Scenario:** Batter scores 82 off 45 balls from 30/4, taking team to the brink of victory, but team loses off the final ball due to a bowler error.
- **Expected Behavior:** Batter's match $\text{HPP}_{\text{net}}$ is highly positive ($> +70.0$).
- **Failure Condition:** Batter receives negative or suppressed HPP because the team lost.

### Test Case 9: Negative Performance on a Winning Team
- **Objective:** Verify that poor performance is penalized even if teammates secure the victory.
- **Scenario:** Bowler concedes 48 runs in 3 overs ($16.0$ RPO) in an easy chase, but team chases it down anyway.
- **Expected Behavior:** Bowler's match $\text{Bowling HPP}_{\text{net}}$ is negative ($-25.0$ to $-45.0$).
- **Failure Condition:** Bowler receives positive or neutral score by riding on team victory.

### Test Case 10: DNB (Did Not Bat) Non-Zeroing Verification
- **Objective:** Verify that players who Did Not Bat are excluded from batting averages.
- **Scenario:** Player in confirmed XI did not bat in 5 out of 14 season matches.
- **Expected Behavior:** Batted innings count $= 9$; Batting average denominator $= 9$. Match batting scores are `NaN`.
- **Failure Condition:** DNB matches recorded as $0.0$, depressing season batting average.

### Test Case 11: Player Who Does Not Bowl (DNBowl Verification)
- **Objective:** Verify that specialist batters are not penalized for delivering 0 balls.
- **Scenario:** Specialist batter bowls 0 balls across 14 matches.
- **Expected Behavior:** Bowling statistics are strictly `NaN`; career bowling denominator is $0$; Overall HPP uses single-discipline profile without penalty.
- **Failure Condition:** Specialist batter receives $0.0$ bowling average or penalty in Overall rating.

### Test Case 12: Genuine All-Rounder Balance
- **Objective:** Verify that an all-rounder with solid dual contributions is rewarded fairly without eclipsing generational specialists.
- **Scenario:** All-rounder scores 30 off 18 balls and takes 2/28 in 4 overs. Compare against a specialist who scored 95 off 50 balls.
- **Expected Behavior:** Both receive strong ratings; specialist batter remains higher or equal on match impact.
- **Failure Condition:** All-rounder automatically tops the match leaderboard simply by adding two moderate numbers together.

### Test Case 13: Anti-Double-Counting on Overlapping Windows
- **Objective:** Verify that rolling-window detectors do not double-count delivery WPA in match totals.
- **Scenario:** A delivery is part of an over shutdown and a 3-over spell.
- **Expected Behavior:** The delivery's delta is summed exactly once in the match accumulator.
- **Failure Condition:** Match HPP exceeds the physical sum of delivery contributions.

### Test Case 14: Provenance Sensitivity (OOF vs Production Consistency)
- **Objective:** Verify that player career rankings do not experience artificial rank reversals between 2022–2024 (OOF) and 2025–2026 (Production).
- **Scenario:** Compute player rankings separately on OOF and Production partitions.
- **Expected Behavior:** Spearman rank correlation $\rho \ge 0.75$ among established players ($N \ge 15$ matches in both).
- **Failure Condition:** Systematic divergence where OOF players are heavily deflated or inflated relative to production players.

### Test Case 15: Low-Sample Competition Handling (OTHER_T20)
- **Objective:** Verify that minor domestic league matches do not distort global player ratings.
- **Scenario:** Player dominates a 3-match associate tournament against weak bowling.
- **Expected Behavior:** Bayesian shrinkage shrinks career rating toward global prior until $N \ge 15$ matches.
- **Failure Condition:** Low-sample player tops the global career HPP leaderboard after 3 matches.

---

## 3. Statistical Verification Benchmarks

During Stage 7B, the validation suite must compute and satisfy the following statistical benchmarks:

| Statistical Metric | Evaluation Scope | Acceptance Threshold | Failure Meaning |
| :--- | :--- | :---: | :--- |
| **Winner Decoupling** | Fraction of Top-3 Match Performers from Winning Team | $55\% \le f_{\text{win}} \le 80\%$ | If $> 90\%$, system is over-coupled to team victory; if $< 50\%$, system fails to reward winning contributions. |
| **Dual-Ledger Conservation** | Sum of Batter, Bowler, and Residual WPA vs Team Delta | Error $\le 10^{-5}$ | Leaking probability mass across deliveries. |
| **DNB Invariant** | Total Matches where DNB has $0.0$ Batting Score | Exactly 0 (0.0%) | Violates participation non-zeroing rule. |
| **Spearman Rank Stability** | Career Rank Correlation across Partition Halves | $\rho \ge 0.70$ | High noise / low predictive validity. |
| **Negative Score Prevalence** | Fraction of Active Match Appearances with $\text{HPP}_{\text{net}} < 0$ | $25\% \le f_{\text{neg}} \le 45\%$ | If $< 10\%$, system lacks negative accountability; if $> 60\%$, system is overly punitive. |

