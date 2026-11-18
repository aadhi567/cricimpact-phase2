"""Stage 6B.7 Historical Win Probability Worm Graph Generator.

Generates ball-by-ball continuous win probability trajectories across both innings
with dual-team probability lines (P_A + P_B = 100%), event markers, interactive tooltips,
and match-defining moments panels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from ml.win_probability.calibration import WinProbabilityCalibrator
from ml.win_probability.chase_model import ChaseModel
from ml.win_probability.first_innings_model import FirstInningsModel
from ml.win_probability.schema import TARGET_BATTING_WIN

TEAM_PALETTES: Final[dict[str, str]] = {
    "Mumbai Indians": "#004BA0",
    "Royal Challengers Bengaluru": "#D11919",
    "Chennai Super Kings": "#F9CD05",
    "Kolkata Knight Riders": "#3A225D",
    "Delhi Capitals": "#0078FF",
    "Gujarat Titans": "#1B2133",
    "Rajasthan Royals": "#EA1A85",
    "Sunrisers Hyderabad": "#F26522",
    "Lucknow Super Giants": "#A72056",
    "Punjab Kings": "#DD1F2D",
    "India": "#0078FF",
    "Australia": "#FFB81C",
    "England": "#CC0000",
    "Pakistan": "#006629",
    "South Africa": "#007A3D",
    "New Zealand": "#222222",
    "West Indies": "#7B1113",
    "Sri Lanka": "#002B7F",
    "Afghanistan": "#005EB8",
    "Bangladesh": "#006A4E",
    "Ireland": "#169B62",
    "Zimbabwe": "#D40000",
    "United Arab Emirates": "#990000",
    "Oman": "#BA0C2F",
    "Scotland": "#002B7F",
    "Netherlands": "#FF4F00",
}

DEFAULT_COLOR_A: Final[str] = "#0078FF"
DEFAULT_COLOR_B: Final[str] = "#FF4B4B"


def compute_cricket_over_ball(legal_ball_number: int) -> str:
    """Compute standard cricket over.ball notation from 1-based legal ball count.

    Formula:
        over_number = floor((legal_ball_number - 1) / 6)
        ball_number = ((legal_ball_number - 1) % 6) + 1

    Examples:
        legal_ball_number = 1   -> "0.1"
        legal_ball_number = 6   -> "0.6"
        legal_ball_number = 7   -> "1.1"
        legal_ball_number = 120 -> "19.6"
    """
    if legal_ball_number <= 0:
        raise ValueError(f"legal_ball_number must be >= 1, got {legal_ball_number}")
    over_number = (legal_ball_number - 1) // 6
    ball_number = ((legal_ball_number - 1) % 6) + 1
    return f"{over_number}.{ball_number}"


def format_completed_overs_notation(legal_balls_completed: int) -> str:
    """Format completed overs for an innings summary (e.g. 20.0 or 14.1)."""
    if legal_balls_completed < 0:
        raise ValueError(f"legal_balls_completed must be >= 0, got {legal_balls_completed}")
    overs = legal_balls_completed // 6
    balls = legal_balls_completed % 6
    return f"{overs}.{balls}"


@dataclass(frozen=True)
class PreMatchMilestone:
    """Pre-match milestone prediction for a single stage."""

    available: bool
    stage_name: str
    team_a_prob: float | None = None
    team_b_prob: float | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.available:
            if self.team_a_prob is None or self.team_b_prob is None:
                raise ValueError("Probabilities must be provided when available=True")
            if not (0.0 <= self.team_a_prob <= 1.0) or not (0.0 <= self.team_b_prob <= 1.0):
                raise ValueError(f"Probabilities out of bounds: team_a={self.team_a_prob}, team_b={self.team_b_prob}")
            if abs(self.team_a_prob + self.team_b_prob - 1.0) > 1e-4:
                raise ValueError(f"Probabilities must sum to 1.0, got {self.team_a_prob + self.team_b_prob}")

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "stage_name": self.stage_name,
            "team_a_prob": self.team_a_prob,
            "team_b_prob": self.team_b_prob,
            "description": self.description,
        }


@dataclass(frozen=True)
class InningsBreakMilestone:
    """Innings-break milestone state and win probability."""

    available: bool
    team_a_prob: float | None = None
    team_b_prob: float | None = None
    first_innings_score: int = 0
    first_innings_wickets: int = 0
    first_innings_overs: str = ""
    target_score: int = 0
    state_identifier: str = ""

    def __post_init__(self) -> None:
        if self.available:
            if self.team_a_prob is None or self.team_b_prob is None:
                raise ValueError("Probabilities must be provided when available=True")
            if not (0.0 <= self.team_a_prob <= 1.0) or not (0.0 <= self.team_b_prob <= 1.0):
                raise ValueError(f"Probabilities out of bounds: team_a={self.team_a_prob}, team_b={self.team_b_prob}")
            if abs(self.team_a_prob + self.team_b_prob - 1.0) > 1e-4:
                raise ValueError(f"Probabilities must sum to 1.0, got {self.team_a_prob + self.team_b_prob}")

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "team_a_prob": self.team_a_prob,
            "team_b_prob": self.team_b_prob,
            "first_innings_score": self.first_innings_score,
            "first_innings_wickets": self.first_innings_wickets,
            "first_innings_overs": self.first_innings_overs,
            "target_score": self.target_score,
            "state_identifier": self.state_identifier,
        }


@dataclass(frozen=True)
class MatchPredictionMilestones:
    """Consolidated 3-milestone structure for a match."""

    match_id: int
    stage_a: PreMatchMilestone
    stage_b: PreMatchMilestone
    innings_break: InningsBreakMilestone

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "stage_a": self.stage_a.to_dict(),
            "stage_b": self.stage_b.to_dict(),
            "innings_break": self.innings_break.to_dict(),
        }


@dataclass(frozen=True)
class WormGraphPoint:
    """Individual ball-by-ball win probability observation."""

    match_ball_index: int
    innings: int
    innings_ball_num: int
    over_ball: str
    score: int
    wickets: int
    runs_required: int | None
    legal_balls_remaining: int | None
    team_a_prob: float
    team_b_prob: float
    delta_team_a_prob: float
    runs_on_ball: int
    is_wicket: bool
    is_four: bool
    is_six: bool
    is_no_ball: bool
    is_wide: bool
    event_label: str
    striker_name: str
    bowler_name: str

    def __post_init__(self) -> None:
        """Validate probability bounds and exact complementarity."""
        if not (0.009 <= self.team_a_prob <= 0.991):
            raise ValueError(f"team_a_prob out of bounds [0.01, 0.99]: {self.team_a_prob}")
        if not (0.009 <= self.team_b_prob <= 0.991):
            raise ValueError(f"team_b_prob out of bounds [0.01, 0.99]: {self.team_b_prob}")
        if abs(self.team_a_prob + self.team_b_prob - 1.0) > 1e-4:
            raise ValueError(f"Probabilities must sum to 1.0: {self.team_a_prob} + {self.team_b_prob}")


@dataclass(frozen=True)
class MatchDefiningMoment:
    """Critical turning point or major probability swing during the match."""

    moment_type: str  # 'largest_positive_swing', 'largest_negative_swing', 'major_wicket', 'turning_point', 'final_result'
    innings: int
    over_ball: str
    delta_prob: float
    team_favored: str
    event_summary: str
    score_context: str
    team_a_prob_after: float
    team_b_prob_after: float


@dataclass
class WormGraphTrajectory:
    """Complete match win probability trajectory and turning points."""

    match_id: int
    match_date: str
    competition_category: str
    venue_name: str
    team_a_name: str
    team_b_name: str
    team_a_color: str
    team_b_color: str
    winner_name: str
    result_text: str
    innings_1_balls: int
    innings_2_balls: int
    total_balls: int
    target_score: int
    points: list[WormGraphPoint] = field(default_factory=list)
    moments: list[MatchDefiningMoment] = field(default_factory=list)
    milestones: MatchPredictionMilestones | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert trajectory to serializable dictionary."""
        return {
            "match_id": self.match_id,
            "match_date": self.match_date,
            "competition_category": self.competition_category,
            "venue_name": self.venue_name,
            "team_a_name": self.team_a_name,
            "team_b_name": self.team_b_name,
            "team_a_color": self.team_a_color,
            "team_b_color": self.team_b_color,
            "winner_name": self.winner_name,
            "result_text": self.result_text,
            "innings_1_balls": self.innings_1_balls,
            "innings_2_balls": self.innings_2_balls,
            "total_balls": self.total_balls,
            "target_score": self.target_score,
            "points": [asdict(p) for p in self.points],
            "moments": [asdict(m) for m in self.moments],
            "milestones": asdict(self.milestones) if self.milestones else None,
        }


class WormGraphGenerator:
    """Generates continuous historical Win Probability Worm Graphs."""

    def __init__(
        self,
        df_matches: pd.DataFrame,
        df_match_states: pd.DataFrame,
        df_ball_by_ball: pd.DataFrame,
        df_teams: pd.DataFrame,
        df_calibrated_predictions: pd.DataFrame | None = None,
    ) -> None:
        """Initialize with historical cricket tables and calibrated predictions."""
        self.df_matches = df_matches.copy()
        self.df_match_states = df_match_states.copy()
        self.df_ball_by_ball = df_ball_by_ball.copy()
        self.df_teams = df_teams.copy()
        self.team_map = dict(zip(self.df_teams["team_id"], self.df_teams["team_name"]))

        self.df_calibrated_predictions = df_calibrated_predictions

    def _determine_event_label(self, row: pd.Series) -> str:
        """Generate human-readable cricket event description."""
        runs = int(row.get("runs", 0))
        is_wkt = bool(row.get("is_wicket", False))
        is_four = bool(row.get("is_four", False))
        is_six = bool(row.get("is_six", False))
        ext_type = str(row.get("extras_type", ""))
        d_type = str(row.get("dismissal_type", "out"))

        if is_wkt:
            return f"WICKET ({d_type})"
        if is_six:
            return f"SIX ({runs} runs)"
        if is_four:
            return f"FOUR ({runs} runs)"
        if "nb" in ext_type.lower():
            return f"NO-BALL ({runs} runs)"
        if "wd" in ext_type.lower() or "wide" in ext_type.lower():
            return f"WIDE ({runs} runs)"
        if runs == 0:
            return "Dot ball"
        return f"{runs} run" if runs == 1 else f"{runs} runs"

    def generate_trajectory(self, match_id: int) -> WormGraphTrajectory:
        """Build continuous ball-by-ball win probability trajectory for a match."""
        m_rows = self.df_matches[self.df_matches["match_id"] == match_id]
        if len(m_rows) == 0:
            raise ValueError(f"Match {match_id} not found in matches database.")
        m_meta = m_rows.iloc[0]

        bbb = self.df_ball_by_ball[self.df_ball_by_ball["match_id"] == match_id].sort_values(
            ["innings", "innings_ball_num"]
        ).copy()
        if len(bbb) == 0:
            raise ValueError(f"No ball-by-ball records found for match {match_id}.")

        states = self.df_match_states[self.df_match_states["match_id"] == match_id].sort_values(
            ["innings", "innings_ball_num"]
        ).copy()
        if len(states) == 0:
            raise ValueError(f"No match states found for match {match_id}.")

        # Identify batting teams
        t1_rows = bbb[bbb["innings"] == 1]
        t2_rows = bbb[bbb["innings"] == 2]
        if len(t1_rows) == 0 or len(t2_rows) == 0:
            raise ValueError(f"Match {match_id} does not have both innings 1 and 2.")

        team1_id = t1_rows["batting_team_id"].iloc[0]
        team2_id = t2_rows["batting_team_id"].iloc[0]
        team_a_name = self.team_map.get(team1_id, str(m_meta.get("home_team", "Team A")))
        team_b_name = self.team_map.get(team2_id, str(m_meta.get("away_team", "Team B")))

        team_a_color = TEAM_PALETTES.get(team_a_name, DEFAULT_COLOR_A)
        team_b_color = TEAM_PALETTES.get(team_b_name, DEFAULT_COLOR_B)
        if team_a_color == team_b_color:
            team_b_color = "#FFA500"  # Ensure distinguishable colors

        # Retrieve predictions
        if self.df_calibrated_predictions is not None:
            preds = self.df_calibrated_predictions[
                self.df_calibrated_predictions["match_id"] == match_id
            ].sort_values(["innings", "innings_ball_num"]).copy()
        else:
            raise RuntimeError("Calibrated predictions dataframe is required.")

        # Merge prediction, BBB, and state details
        merged = pd.merge(
            preds,
            bbb[
                [
                    "innings",
                    "innings_ball_num",
                    "overid",
                    "over_ball_num",
                    "striker_name",
                    "bowler_name",
                    "runs",
                    "is_four",
                    "is_six",
                    "is_wicket",
                    "dismissal_type",
                    "extras_type",
                ]
            ],
            on=["innings", "innings_ball_num"],
            how="left",
        )

        merged = pd.merge(
            merged,
            states[
                [
                    "innings",
                    "innings_ball_num",
                    "runs_required_before",
                    "legal_balls_remaining_before",
                    "target_runs",
                ]
            ],
            on=["innings", "innings_ball_num"],
            how="left",
        )

        # Consistent orientation: Team A = Batting 1st, Team B = Chasing
        # Inns 1: prob is P(batting 1st wins) = P(Team A)
        # Inns 2: prob is P(chasing team wins) = P(Team B) => P(Team A) = 1.0 - prob
        prob_col = "calibrated_probability" if "calibrated_probability" in merged.columns else "probability"
        p_raw = merged[prob_col].values

        p_team_a = np.where(merged["innings"] == 1, p_raw, 1.0 - p_raw)
        p_team_a = np.clip(p_team_a, 0.01, 0.99)
        p_team_b = 1.0 - p_team_a

        merged["p_team_a"] = p_team_a
        merged["p_team_b"] = p_team_b
        merged["delta_p_team_a"] = merged["p_team_a"].diff().fillna(0.0)

        # Build points
        points: list[WormGraphPoint] = []
        for idx, (_, row) in enumerate(merged.iterrows(), start=1):
            inn = int(row["innings"])
            runs_req = None if inn == 1 or pd.isna(row.get("runs_required_before")) else int(row["runs_required_before"])
            balls_rem = 120 if pd.isna(row.get("legal_balls_remaining_before")) else int(row["legal_balls_remaining_before"])
            legal_completed = max(0, 120 - balls_rem)
            over_ball = compute_cricket_over_ball(legal_completed + 1)
            ext_type = str(row.get("extras_type", ""))

            pt = WormGraphPoint(
                match_ball_index=idx,
                innings=inn,
                innings_ball_num=int(row["innings_ball_num"]),
                over_ball=over_ball,
                score=int(row.get("score_before", 0)),
                wickets=int(row.get("wickets_lost_before", 0)),
                runs_required=runs_req,
                legal_balls_remaining=balls_rem,
                team_a_prob=float(round(row["p_team_a"], 4)),
                team_b_prob=float(round(row["p_team_b"], 4)),
                delta_team_a_prob=float(round(row["delta_p_team_a"], 4)),
                runs_on_ball=int(row.get("runs", 0)),
                is_wicket=bool(row.get("is_wicket", False)),
                is_four=bool(row.get("is_four", False)),
                is_six=bool(row.get("is_six", False)),
                is_no_ball="nb" in ext_type.lower(),
                is_wide="wd" in ext_type.lower() or "wide" in ext_type.lower(),
                event_label=self._determine_event_label(row),
                striker_name=str(row.get("striker_name", "")),
                bowler_name=str(row.get("bowler_name", "")),
            )
            points.append(pt)

        # Detect Match-Defining Moments
        moments = self._extract_defining_moments(points, team_a_name, team_b_name, m_meta)

        i1_len = len(merged[merged["innings"] == 1])
        i2_len = len(merged[merged["innings"] == 2])
        target_score = int(merged["target_runs"].dropna().iloc[0]) if "target_runs" in merged.columns and not merged["target_runs"].dropna().empty else 0

        winner_name = self.team_map.get(m_meta.get("win_team_id"), str(m_meta.get("winner", "")))

        # Build Innings Break Milestone from actual end of Innings 1 state
        i1_pts = [p for p in points if p.innings == 1]
        if i1_pts:
            i1_end = i1_pts[-1]
            final_runs = i1_end.score + i1_end.runs_on_ball
            final_wkts = i1_end.wickets + (1 if i1_end.is_wicket else 0)
            balls_rem_last = i1_end.legal_balls_remaining if i1_end.legal_balls_remaining is not None else 0
            was_legal = not (i1_end.is_wide or i1_end.is_no_ball)
            i1_completed = min(120, max(0, 120 - balls_rem_last + (1 if was_legal else 0)))
            i1_overs_str = format_completed_overs_notation(i1_completed)

            ib_milestone = InningsBreakMilestone(
                available=True,
                team_a_prob=i1_end.team_a_prob,
                team_b_prob=i1_end.team_b_prob,
                first_innings_score=final_runs,
                first_innings_wickets=final_wkts,
                first_innings_overs=i1_overs_str,
                target_score=target_score,
                state_identifier=f"Inn 1 End (Over {i1_end.over_ball}, Ball {len(i1_pts)})",
            )
        else:
            ib_milestone = InningsBreakMilestone(available=False)

        milestones = MatchPredictionMilestones(
            match_id=match_id,
            stage_a=PreMatchMilestone(available=False, stage_name="Stage A"),
            stage_b=PreMatchMilestone(available=False, stage_name="Stage B"),
            innings_break=ib_milestone,
        )

        return WormGraphTrajectory(
            match_id=match_id,
            match_date=str(m_meta.get("match_date", ""))[:10],
            competition_category=str(m_meta.get("competition_category", "T20")),
            venue_name=str(m_meta.get("venue_country", "Stadium")),
            team_a_name=team_a_name,
            team_b_name=team_b_name,
            team_a_color=team_a_color,
            team_b_color=team_b_color,
            winner_name=winner_name,
            result_text=str(m_meta.get("result", "")),
            innings_1_balls=i1_len,
            innings_2_balls=i2_len,
            total_balls=len(points),
            target_score=target_score,
            points=points,
            moments=moments,
            milestones=milestones,
        )

    def _extract_defining_moments(
        self,
        points: list[WormGraphPoint],
        team_a_name: str,
        team_b_name: str,
        m_meta: pd.Series,
    ) -> list[MatchDefiningMoment]:
        """Extract top swings, major wickets, and key turning points from actual predictions."""
        if not points:
            return []

        moments: list[MatchDefiningMoment] = []

        # 1. Largest Positive Swing for Team A
        max_a_pt = max(points, key=lambda p: p.delta_team_a_prob)
        if max_a_pt.delta_team_a_prob > 0.05:
            moments.append(
                MatchDefiningMoment(
                    moment_type="largest_positive_swing",
                    innings=max_a_pt.innings,
                    over_ball=max_a_pt.over_ball,
                    delta_prob=max_a_pt.delta_team_a_prob,
                    team_favored=team_a_name,
                    event_summary=f"{max_a_pt.event_label} ({max_a_pt.bowler_name} to {max_a_pt.striker_name})",
                    score_context=f"Inn {max_a_pt.innings} | {max_a_pt.score}/{max_a_pt.wickets}",
                    team_a_prob_after=max_a_pt.team_a_prob,
                    team_b_prob_after=max_a_pt.team_b_prob,
                )
            )

        # 2. Largest Positive Swing for Team B (most negative for Team A)
        min_a_pt = min(points, key=lambda p: p.delta_team_a_prob)
        if min_a_pt.delta_team_a_prob < -0.05:
            moments.append(
                MatchDefiningMoment(
                    moment_type="largest_negative_swing",
                    innings=min_a_pt.innings,
                    over_ball=min_a_pt.over_ball,
                    delta_prob=abs(min_a_pt.delta_team_a_prob),
                    team_favored=team_b_name,
                    event_summary=f"{min_a_pt.event_label} ({min_a_pt.bowler_name} to {min_a_pt.striker_name})",
                    score_context=f"Inn {min_a_pt.innings} | {min_a_pt.score}/{min_a_pt.wickets}",
                    team_a_prob_after=min_a_pt.team_a_prob,
                    team_b_prob_after=min_a_pt.team_b_prob,
                )
            )

        # 3. Top Wicket Swings
        wicket_pts = [p for p in points if p.is_wicket]
        if wicket_pts:
            top_wkt = max(wicket_pts, key=lambda p: abs(p.delta_team_a_prob))
            favored = team_a_name if top_wkt.delta_team_a_prob > 0 else team_b_name
            moments.append(
                MatchDefiningMoment(
                    moment_type="major_wicket",
                    innings=top_wkt.innings,
                    over_ball=top_wkt.over_ball,
                    delta_prob=abs(top_wkt.delta_team_a_prob),
                    team_favored=favored,
                    event_summary=f"{top_wkt.event_label} by {top_wkt.bowler_name}",
                    score_context=f"Inn {top_wkt.innings} | {top_wkt.score}/{top_wkt.wickets}",
                    team_a_prob_after=top_wkt.team_a_prob,
                    team_b_prob_after=top_wkt.team_b_prob,
                )
            )

        # 4. Critical Turning Point (Lead change late in match)
        lead_swaps = []
        for i in range(1, len(points)):
            prev_p = points[i - 1].team_a_prob
            curr_p = points[i].team_a_prob
            if (prev_p - 0.5) * (curr_p - 0.5) < 0 and points[i].innings == 2:
                lead_swaps.append(points[i])

        if lead_swaps:
            tp = max(lead_swaps, key=lambda p: abs(p.delta_team_a_prob))
            favored = team_a_name if tp.team_a_prob > 0.5 else team_b_name
            moments.append(
                MatchDefiningMoment(
                    moment_type="turning_point",
                    innings=tp.innings,
                    over_ball=tp.over_ball,
                    delta_prob=abs(tp.delta_team_a_prob),
                    team_favored=favored,
                    event_summary=f"Lead Change: {tp.event_label}",
                    score_context=f"Inn {tp.innings} | {tp.score}/{tp.wickets}",
                    team_a_prob_after=tp.team_a_prob,
                    team_b_prob_after=tp.team_b_prob,
                )
            )

        # 5. Final Result
        last_pt = points[-1]
        winner_name = self.team_map.get(m_meta.get("win_team_id"), str(m_meta.get("winner", "")))
        moments.append(
            MatchDefiningMoment(
                moment_type="final_result",
                innings=last_pt.innings,
                over_ball=last_pt.over_ball,
                delta_prob=abs(last_pt.delta_team_a_prob),
                team_favored=winner_name,
                event_summary=f"Final Result: {str(m_meta.get('result', 'Match Completed'))}",
                score_context=f"Final Ball | {last_pt.score}/{last_pt.wickets}",
                team_a_prob_after=last_pt.team_a_prob,
                team_b_prob_after=last_pt.team_b_prob,
            )
        )

        return moments

