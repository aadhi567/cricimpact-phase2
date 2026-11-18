"""Comprehensive tests for Stage B8 Additional Requirements:
1. Hide Pakistan Players from the Overall Leaderboard
2. Add Tournament Filter Based on Existing Tournament File
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

KNOWN_PAKISTAN_PLAYERS = [
    "Shaheen Afridi",
    "Haris Rauf",
    "Mohammad Nawaz",
    "Shadab Khan",
    "Naseem Shah",
    "Abrar Ahmed",
    "Sufiyan Muqeem",
    "Hasan Ali",
    "Mohammad Hasnain",
    "Abbas Afridi",
    "Faheem Ashraf",
    "Usman Qadir",
]

KNOWN_NON_PAKISTAN_PLAYERS = [
    "Jasprit Bumrah",
    "Sunil Narine",
    "Rashid Khan",
    "Bhuvneshwar Kumar",
    "Axar Patel",
    "Varun Chakravarthy",
    "Trent Boult",
    "Arshdeep Singh",
    "Josh Hazlewood",
    "Wanindu Hasaranga",
]


class TestTournamentsEndpoint:
    """Test /api/bowling/tournaments and /api/pcs/tournaments endpoints."""

    def test_bowling_tournaments_metadata(self):
        res = client.get("/api/bowling/tournaments")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["total"] == 141
        assert len(data["items"]) == 141

        # Check fields of each tournament item
        first = data["items"][0]
        assert "comp_id" in first
        assert "comp_name" in first
        assert "display_name" in first
        assert "season" in first
        assert "match_format" in first
        assert "match_count" in first
        assert "spells_count" in first

    def test_pcs_tournaments_metadata(self):
        res = client.get("/api/pcs/tournaments")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["total"] == 141
        assert len(data["items"]) == 141


class TestPakistanExclusionFromOverallLeaderboard:
    """Test that Pakistan players are authoritatively excluded from the default overall leaderboard."""

    def test_bcm_default_leaderboard_excludes_pakistan(self):
        res = client.get("/api/bowling/leaderboard?min_balls=60&page_size=100")
        assert res.status_code == 200
        data = res.json()
        items = data["items"]

        # Ensure no Pakistan players in items
        names = [it["bowler_name"] for it in items]
        for pak_name in KNOWN_PAKISTAN_PLAYERS:
            assert pak_name not in names, f"{pak_name} found in default BCM leaderboard!"

        # Ensure contiguous sequential ranking
        ranks = [it["rank"] for it in items]
        assert ranks == list(range(1, len(items) + 1))

    def test_pcs_default_leaderboard_excludes_pakistan(self):
        res = client.get("/api/pcs/leaderboard?min_balls=60&page_size=100")
        assert res.status_code == 200
        data = res.json()
        items = data["items"]

        # Ensure no Pakistan players in items
        names = [it["bowler_name"] for it in items]
        for pak_name in KNOWN_PAKISTAN_PLAYERS:
            assert pak_name not in names, f"{pak_name} found in default PCS leaderboard!"

        # Ensure contiguous sequential ranking
        ranks = [it["rank"] for it in items]
        assert ranks == list(range(1, len(items) + 1))

    def test_non_pakistan_players_not_excluded(self):
        res = client.get("/api/bowling/leaderboard?min_balls=60&page_size=100")
        assert res.status_code == 200
        data = res.json()
        names = [it["bowler_name"] for it in data["items"]]

        # Prominent non-Pakistan players should be present
        for non_pak in ["Bhuvneshwar Kumar", "Rashid Khan", "Axar Patel"]:
            assert non_pak in names, f"Non-Pakistan player {non_pak} was mistakenly excluded!"


class TestPakistanPlayerProfilesPreserved:
    """Test that individual player profiles, career statistics, and spells remain 100% accessible."""

    def test_bcm_pakistan_player_profiles_intact(self):
        # Shaheen Afridi (bowler_id=6355)
        res = client.get("/api/bowling/players/6355")
        assert res.status_code == 200
        data = res.json()
        assert data["bowler_name"] == "Shaheen Afridi"
        assert data["career_summary"]["wickets"] == 63
        assert data["career_summary"]["legal_balls"] == 934
        assert len(data["season_breakdown"]) > 0
        assert len(data["top_spells"]) > 0

        # Haris Rauf (bowler_id=7364)
        res = client.get("/api/bowling/players/7364")
        assert res.status_code == 200
        data = res.json()
        assert data["bowler_name"] == "Haris Rauf"
        assert data["career_summary"]["wickets"] == 72
        assert data["career_summary"]["legal_balls"] == 974

    def test_pcs_pakistan_player_profiles_intact(self):
        # Shaheen Afridi (bowler_id=6355)
        res = client.get("/api/pcs/players/6355")
        assert res.status_code == 200
        data = res.json()
        assert data["bowler_name"] == "Shaheen Afridi"
        assert data["career"]["wickets"] == 63
        assert len(data["spells_history"]) > 0

        # Mohammad Nawaz (bowler_id=2490)
        res = client.get("/api/pcs/players/2490")
        assert res.status_code == 200
        data = res.json()
        assert data["bowler_name"] == "Mohammad Nawaz"
        assert data["career"]["wickets"] == 61


class TestTournamentLevelFiltering:
    """Test filtering leaderboard by tournament."""

    def test_bcm_tournament_filter_ipl_2024(self):
        # By competition name
        res = client.get("/api/bowling/leaderboard?tournament=IPL 2024&min_balls=60")
        assert res.status_code == 200
        data = res.json()
        assert data["tournament_filter"] == "IPL 2024"
        assert data["pagination"]["total_items"] == 79
        items = data["items"]
        assert len(items) > 0

        # Jasprit Bumrah should be #1 in IPL 2024
        top = items[0]
        assert top["bowler_name"] == "Jasprit Bumrah"
        assert top["rank"] == 1
        assert top["total_bcs"] == 307.20
        assert top["wickets"] == 18

        # Statistics reflect only IPL 2024 matches (e.g. 12 matches, not full career)
        assert top["matches"] == 12

    def test_pcs_tournament_filter_ipl_2024(self):
        res = client.get("/api/pcs/leaderboard?tournament=IPL 2024&min_balls=60")
        assert res.status_code == 200
        data = res.json()
        assert data["tournament_filter"] == "IPL 2024"
        assert data["pagination"]["total_items"] == 79
        items = data["items"]

        # Jasprit Bumrah top PCS bowler in IPL 2024
        top = items[0]
        assert top["bowler_name"] == "Jasprit Bumrah"
        assert top["rank"] == 1
        assert top["pcs_shrunk"] == 63.92
        assert top["pcs_raw"] == 66.25

    def test_tournament_filter_by_comp_id(self):
        # By numeric comp_id 2193 (IPL 2024)
        res = client.get("/api/bowling/leaderboard?tournament=2193&min_balls=60")
        assert res.status_code == 200
        data = res.json()
        assert data["pagination"]["total_items"] == 79
        assert data["items"][0]["bowler_name"] == "Jasprit Bumrah"

    def test_combined_filter_asia_cup_excludes_pakistan(self):
        # Mens Twenty20 Asia Cup 2022 (comp_id 1533) features Pakistan
        res = client.get("/api/bowling/leaderboard?tournament=1533&min_balls=1&page_size=100")
        assert res.status_code == 200
        data = res.json()
        items = data["items"]

        names = [it["bowler_name"] for it in items]
        # None of the 9 Pakistan bowlers who played in Asia Cup 2022 should appear
        for pak_name in KNOWN_PAKISTAN_PLAYERS:
            assert pak_name not in names, f"{pak_name} appeared in tournament view!"

        # Non-Pakistan bowlers who played in Asia Cup 2022 should appear
        assert "Bhuvneshwar Kumar" in names
        assert "Mujeeb Ur Rahman" in names
        assert "Maheesh Theekshana" in names

        # Rankings are contiguous 1..N
        ranks = [it["rank"] for it in items]
        assert ranks == list(range(1, len(items) + 1))

    def test_tournament_sorting_and_min_balls(self):
        # Test sorting by wickets
        res = client.get("/api/bowling/leaderboard?tournament=IPL 2024&sort_by=wickets&order=desc&min_balls=60")
        assert res.status_code == 200
        data = res.json()
        items = data["items"]
        wickets = [it["wickets"] for it in items]
        assert wickets == sorted(wickets, reverse=True)

        # Test increasing min_balls threshold reduces item count
        res_high_balls = client.get("/api/bowling/leaderboard?tournament=IPL 2024&min_balls=200")
        assert res_high_balls.status_code == 200
        data_high = res_high_balls.json()
        assert data_high["pagination"]["total_items"] < 79
        assert all(it["legal_balls"] >= 200 for it in data_high["items"])
