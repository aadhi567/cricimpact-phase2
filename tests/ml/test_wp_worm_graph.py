"""Unit tests for Stage 6B.7 Historical Win Probability Worm Graph."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from ml.win_probability.worm_graph import (
    InningsBreakMilestone,
    MatchDefiningMoment,
    MatchPredictionMilestones,
    PreMatchMilestone,
    WormGraphGenerator,
    WormGraphPoint,
    WormGraphTrajectory,
    compute_cricket_over_ball,
    format_completed_overs_notation,
)


@pytest.fixture(scope="module")
def worm_generator() -> WormGraphGenerator:
    """Instantiate WormGraphGenerator with loaded standard T20 datasets."""
    df_matches = pd.read_csv("data/raw/matches.csv")
    df_match_states = pd.read_pickle("data/processed/match_states/match_states_standard_t20_v1.pkl.gz")
    df_ball_by_ball = pd.read_csv("data/raw/ball_by_ball.csv")
    df_teams = pd.read_csv("data/raw/teams.csv")
    df_calibrated = pd.read_pickle("data/processed/calibration/test_2026_calibrated_predictions_v1.pkl.gz")

    return WormGraphGenerator(
        df_matches=df_matches,
        df_match_states=df_match_states,
        df_ball_by_ball=df_ball_by_ball,
        df_teams=df_teams,
        df_calibrated_predictions=df_calibrated,
    )


def test_worm_graph_point_validation() -> None:
    """Verify WormGraphPoint enforces probability bounds and strict complementarity."""
    # Valid point
    pt = WormGraphPoint(
        match_ball_index=1,
        innings=1,
        innings_ball_num=1,
        over_ball="0.1",
        score=0,
        wickets=0,
        runs_required=None,
        legal_balls_remaining=None,
        team_a_prob=0.55,
        team_b_prob=0.45,
        delta_team_a_prob=0.0,
        runs_on_ball=0,
        is_wicket=False,
        is_four=False,
        is_six=False,
        is_no_ball=False,
        is_wide=False,
        event_label="Dot ball",
        striker_name="Player A",
        bowler_name="Bowler B",
    )
    assert pt.team_a_prob == 0.55
    assert pt.team_b_prob == 0.45

    # Out of bounds
    with pytest.raises(ValueError, match="out of bounds"):
        WormGraphPoint(
            match_ball_index=1,
            innings=1,
            innings_ball_num=1,
            over_ball="0.1",
            score=0,
            wickets=0,
            runs_required=None,
            legal_balls_remaining=None,
            team_a_prob=1.05,
            team_b_prob=-0.05,
            delta_team_a_prob=0.0,
            runs_on_ball=0,
            is_wicket=False,
            is_four=False,
            is_six=False,
            is_no_ball=False,
            is_wide=False,
            event_label="Dot ball",
            striker_name="Player A",
            bowler_name="Bowler B",
        )

    # Non-complementary probabilities
    with pytest.raises(ValueError, match="sum to 1.0"):
        WormGraphPoint(
            match_ball_index=1,
            innings=1,
            innings_ball_num=1,
            over_ball="0.1",
            score=0,
            wickets=0,
            runs_required=None,
            legal_balls_remaining=None,
            team_a_prob=0.60,
            team_b_prob=0.30,
            delta_team_a_prob=0.0,
            runs_on_ball=0,
            is_wicket=False,
            is_four=False,
            is_six=False,
            is_no_ball=False,
            is_wide=False,
            event_label="Dot ball",
            striker_name="Player A",
            bowler_name="Bowler B",
        )


def test_worm_graph_trajectory_generation(worm_generator: WormGraphGenerator) -> None:
    """Verify trajectory generation on showcase match 50375 (RCB vs MI)."""
    traj = worm_generator.generate_trajectory(50375)

    assert traj.match_id == 50375
    assert traj.team_a_name == "Mumbai Indians"
    assert traj.team_b_name == "Royal Challengers Bengaluru"
    assert traj.winner_name == "Royal Challengers Bengaluru"
    assert traj.innings_1_balls == 123
    assert traj.innings_2_balls == 131
    assert traj.total_balls == 254
    assert len(traj.points) == 254

    # Colors must be distinct
    assert traj.team_a_color != traj.team_b_color

    # Verify every point is complementary and bounded
    for pt in traj.points:
        assert 0.009 <= pt.team_a_prob <= 0.991
        assert 0.009 <= pt.team_b_prob <= 0.991
        assert abs(pt.team_a_prob + pt.team_b_prob - 1.0) < 1e-4


def test_worm_graph_event_markers(worm_generator: WormGraphGenerator) -> None:
    """Verify detection of wickets, boundaries, and cricket events."""
    traj = worm_generator.generate_trajectory(50375)

    has_wicket = any(p.is_wicket for p in traj.points)
    has_four = any(p.is_four for p in traj.points)
    has_six = any(p.is_six for p in traj.points)

    assert has_wicket, "Match must have at least one wicket event"
    assert has_four, "Match must have at least one four event"
    assert has_six, "Match must have at least one six event"

    # Wickets should have descriptive label
    wkt_pts = [p for p in traj.points if p.is_wicket]
    assert any("WICKET" in p.event_label for p in wkt_pts)


def test_worm_graph_defining_moments(worm_generator: WormGraphGenerator) -> None:
    """Verify extraction of match-defining moments panel data."""
    traj = worm_generator.generate_trajectory(50375)

    assert len(traj.moments) >= 4

    types = [m.moment_type for m in traj.moments]
    assert "largest_positive_swing" in types
    assert "largest_negative_swing" in types
    assert "major_wicket" in types
    assert "final_result" in types

    for m in traj.moments:
        assert m.delta_prob > 0.0
        assert m.team_favored in [traj.team_a_name, traj.team_b_name]


def test_worm_graph_innings_break_and_terminal_override(worm_generator: WormGraphGenerator) -> None:
    """Verify seamless transition between innings and terminal probability convergence."""
    traj = worm_generator.generate_trajectory(50375)

    # Point at innings 1 end
    pt_i1_end = traj.points[traj.innings_1_balls - 1]
    assert pt_i1_end.innings == 1

    # Point at innings 2 start
    pt_i2_start = traj.points[traj.innings_1_balls]
    assert pt_i2_start.innings == 2

    # Final point must reflect the winner (RCB won, so Team B prob must be >= 0.90)
    final_pt = traj.points[-1]
    assert final_pt.team_b_prob >= 0.90
    assert final_pt.team_a_prob <= 0.10


def test_match_index_coverage() -> None:
    """Verify match index coverage across all 883 matches and 798 standard T20s."""
    import json
    index_path = Path("docs/worm_graph/match_index.json")
    assert index_path.exists(), "match_index.json must exist in docs/worm_graph"

    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    assert len(index_data) == 883, f"Expected 883 total matches, got {len(index_data)}"

    # Check status counts
    available_prod = [m for m in index_data if m["status"] == "available"]
    available_oof = [m for m in index_data if m["status"] == "available_oof"]
    pending = [m for m in index_data if m["status"] == "pending_authorization"]
    excluded = [m for m in index_data if m["status"] == "excluded"]

    assert len(available_prod) == 321, f"Expected 321 production matches, got {len(available_prod)}"
    assert len(available_oof) == 477, f"Expected 477 OOF retrospective matches, got {len(available_oof)}"
    assert len(pending) == 0, f"Expected 0 pending matches, got {len(pending)}"
    assert len(excluded) == 85, f"Expected 85 excluded matches, got {len(excluded)}"

    # Check standard T20 competition counts
    standard = available_prod + available_oof
    assert len(standard) == 798, f"Expected 798 standard matches, got {len(standard)}"

    ipl = [m for m in standard if m["comp"] == "IPL"]
    t20i = [m for m in standard if m["comp"] == "T20I"]
    other = [m for m in standard if m["comp"] == "OTHER_T20"]

    assert len(ipl) == 351, f"Expected 351 IPL matches, got {len(ipl)}"
    assert len(t20i) == 419, f"Expected 419 T20I matches, got {len(t20i)}"
    assert len(other) == 28, f"Expected 28 OTHER_T20 matches, got {len(other)}"


def test_trajectory_files_exist_and_valid() -> None:
    """Verify all 798 exported trajectory files exist and conform to schema."""
    import json
    traj_dir = Path("docs/worm_graph/trajectories")
    files = list(traj_dir.glob("*.json"))
    assert len(files) == 798, f"Expected 798 trajectory files in docs/worm_graph/trajectories, got {len(files)}"

    # Check production showcase match 50375
    with open(traj_dir / "50375.json", "r", encoding="utf-8") as f:
        data_prod = json.load(f)

    assert data_prod["match_id"] == 50375
    assert len(data_prod["points"]) == 254
    assert len(data_prod["moments"]) >= 4
    for pt in data_prod["points"]:
        p_a, p_b = pt[7], pt[8]
        assert 0.009 <= p_a <= 0.991
        assert 0.009 <= p_b <= 0.991
        assert abs(p_a + p_b - 1.0) <= 1e-4

    # Check newly generated 2022 OOF match (e.g. 13511)
    with open(traj_dir / "13511.json", "r", encoding="utf-8") as f:
        data_oof = json.load(f)

    assert data_oof["match_id"] == 13511
    assert data_oof["prediction_provenance"] == "oof_5fold_retrospective"
    assert "fold_id" in data_oof
    assert 0 <= data_oof["fold_id"] <= 4
    assert len(data_oof["points"]) == 224
    assert len(data_oof["moments"]) >= 3
    for pt in data_oof["points"]:
        p_a, p_b = pt[7], pt[8]
        assert 0.009 <= p_a <= 0.991
        assert 0.009 <= p_b <= 0.991
        assert abs(p_a + p_b - 1.0) <= 1e-4


def test_cricket_over_numbering_formula() -> None:
    """Verify standard cricket over-numbering formula and completed overs notation."""
    # 1. First legal delivery -> 0.1
    assert compute_cricket_over_ball(1) == "0.1"

    # 2. Sixth legal delivery -> 0.6
    assert compute_cricket_over_ball(6) == "0.6"

    # 3. Seventh legal delivery -> 1.1
    assert compute_cricket_over_ball(7) == "1.1"

    # 4. 12th legal delivery -> 1.6
    assert compute_cricket_over_ball(12) == "1.6"

    # 5. 13th legal delivery -> 2.1
    assert compute_cricket_over_ball(13) == "2.1"

    # 6. 120th legal delivery -> 19.6
    assert compute_cricket_over_ball(120) == "19.6"

    # Completed overs notation:
    # 120 legal balls completed -> 20.0
    assert format_completed_overs_notation(120) == "20.0"

    # 85 legal balls completed -> 14.1 (14 overs + 1 ball)
    assert format_completed_overs_notation(85) == "14.1"

    # 84 legal balls completed -> 14.0 (14 full overs)
    assert format_completed_overs_notation(84) == "14.0"

    # 0 legal balls completed -> 0.0
    assert format_completed_overs_notation(0) == "0.0"

    # Invalid input handling
    with pytest.raises(ValueError, match="must be >= 1"):
        compute_cricket_over_ball(0)


def test_cricket_over_numbering_with_extras_and_shortened(worm_generator: WormGraphGenerator) -> None:
    """Verify that multiple deliveries due to extras retain over label, and shortened/all-out work."""
    traj = worm_generator.generate_trajectory(50375)

    # Innings 1 ends at 123 deliveries (extra balls bowled)
    assert traj.innings_1_balls == 123
    assert len(traj.points) == 254

    # Verify no impossible over labels like "20.6" or "19.7" exist
    for pt in traj.points:
        over_str, ball_str = pt.over_ball.split(".")
        over_n = int(over_str)
        ball_n = int(ball_str)
        assert 0 <= over_n <= 19, f"Over number {over_n} out of valid range [0, 19] for ball {pt.match_ball_index}"
        assert 1 <= ball_n <= 6, f"Ball number {ball_n} out of valid range [1, 6] for ball {pt.match_ball_index}"

    # Verify that wide / no-ball deliveries retain the same over_ball as next delivery
    for i in range(len(traj.points) - 1):
        curr_pt = traj.points[i]
        next_pt = traj.points[i + 1]
        if curr_pt.innings == next_pt.innings and (curr_pt.is_wide or curr_pt.is_no_ball):
            # Extra delivery does not increment legal ball count, so next ball should attempt same or next
            # Specifically, if balls_remaining stayed the same, over_ball must be identical
            if curr_pt.legal_balls_remaining == next_pt.legal_balls_remaining:
                assert curr_pt.over_ball == next_pt.over_ball, (
                    f"Extra at ball {curr_pt.match_ball_index} should retain over_ball {curr_pt.over_ball}, "
                    f"got {next_pt.over_ball}"
                )


def test_milestone_dataclasses_and_invariants() -> None:
    """Verify milestone dataclasses enforce probabilities [0, 1], complementarity, and fallbacks."""
    # PreMatchMilestone valid
    pm_a = PreMatchMilestone(
        available=True,
        stage_name="Stage A",
        team_a_prob=0.52,
        team_b_prob=0.48,
    )
    pm_b = PreMatchMilestone(
        available=True,
        stage_name="Stage B",
        team_a_prob=0.55,
        team_b_prob=0.45,
    )
    assert abs(pm_a.team_a_prob + pm_a.team_b_prob - 1.0) < 1e-6
    assert abs(pm_b.team_a_prob + pm_b.team_b_prob - 1.0) < 1e-6

    # PreMatchMilestone invalid bounds
    with pytest.raises(ValueError, match="out of bounds"):
        PreMatchMilestone(
            available=True,
            stage_name="Stage A",
            team_a_prob=1.05,
            team_b_prob=-0.05,
        )

    # PreMatchMilestone non-complementary
    with pytest.raises(ValueError, match="must sum to 1.0"):
        PreMatchMilestone(
            available=True,
            stage_name="Stage A",
            team_a_prob=0.50,
            team_b_prob=0.40,
        )

    # InningsBreakMilestone valid
    ib = InningsBreakMilestone(
        available=True,
        first_innings_score=196,
        first_innings_wickets=8,
        first_innings_overs="20.0",
        target_score=197,
        team_a_prob=0.42,
        team_b_prob=0.58,
        state_identifier="Inn 1 End (Over 19.6)",
    )
    assert ib.target_score == 197
    assert abs(ib.team_a_prob + ib.team_b_prob - 1.0) < 1e-6

    # InningsBreakMilestone non-complementary
    with pytest.raises(ValueError, match="must sum to 1.0"):
        InningsBreakMilestone(
            available=True,
            first_innings_score=150,
            first_innings_wickets=10,
            first_innings_overs="18.2",
            target_score=151,
            team_a_prob=0.60,
            team_b_prob=0.30,
            state_identifier="Inn 1 End",
        )

    # MatchPredictionMilestones complete
    milestones = MatchPredictionMilestones(match_id=50375, stage_a=pm_a, stage_b=pm_b, innings_break=ib)
    m_dict = milestones.to_dict()
    assert "stage_a" in m_dict
    assert "stage_b" in m_dict
    assert "innings_break" in m_dict
    assert m_dict["innings_break"]["target_score"] == 197


def test_match_50375_milestone_extraction(worm_generator: WormGraphGenerator) -> None:
    """Verify trajectory generation extracts valid milestones for showcase match 50375."""
    traj = worm_generator.generate_trajectory(50375)
    assert traj.milestones is not None
    assert traj.milestones.innings_break is not None

    ib = traj.milestones.innings_break
    # Mumbai Indians scored 166/7 (Target 167) against RCB
    assert ib.first_innings_score == 166
    assert ib.first_innings_wickets == 7
    assert ib.target_score == 167
    assert ib.first_innings_overs == "20.0"
    assert "19.6" in ib.state_identifier or "Inn 1 End" in ib.state_identifier
    assert abs(ib.team_a_prob + ib.team_b_prob - 1.0) < 1e-4

    # Verify that Innings Break milestone strictly matches the final ball of Innings 1
    pt_break = traj.points[traj.innings_1_balls - 1]
    assert abs(ib.team_a_prob - pt_break.team_a_prob) < 1e-6
    assert abs(ib.team_b_prob - pt_break.team_b_prob) < 1e-6


def test_match_index_milestones_and_excluded_integrity() -> None:
    """Verify match index has pre-match milestones for all 798 standard and clean nulls for 85 excluded."""
    import json
    index_path = Path("docs/worm_graph/match_index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        matches = json.load(f)

    assert len(matches) == 883

    standard = [m for m in matches if m["status"] in ("available", "available_oof")]
    excluded = [m for m in matches if m["status"] == "excluded"]

    assert len(standard) == 798
    assert len(excluded) == 85

    # Standard matches must all have valid pre-match data
    for m in standard:
        assert "pre_match" in m, f"Match {m['id']} missing pre_match field"
        pm = m["pre_match"]
        sa = pm["stage_a"]
        sb = pm["stage_b"]
        assert sa["available"] is True
        assert sb["available"] is True
        assert 0.0 <= sa["team_a_prob"] <= 1.0
        assert 0.0 <= sa["team_b_prob"] <= 1.0
        assert abs(sa["team_a_prob"] + sa["team_b_prob"] - 1.0) < 1e-4
        assert 0.0 <= sb["team_a_prob"] <= 1.0
        assert 0.0 <= sb["team_b_prob"] <= 1.0
        assert abs(sb["team_a_prob"] + sb["team_b_prob"] - 1.0) < 1e-4

    # Excluded matches must have available=False and null probabilities (no fabrication)
    for m in excluded:
        assert "pre_match" in m, f"Excluded match {m['id']} missing pre_match field"
        pm = m["pre_match"]
        sa = pm["stage_a"]
        sb = pm["stage_b"]
        assert sa["available"] is False
        assert sa["team_a_prob"] is None
        assert sa["team_b_prob"] is None
        assert sb["available"] is False
        assert sb["team_a_prob"] is None
        assert sb["team_b_prob"] is None




