import random
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from history_api.database import get_session
from history_api.main import create_app
from history_api.seed import PlayedMatch, group_qualifiers, seed_database

# 20 tournaments x (8 groups x 6 matches + 8 + 4 + 2 + 1 knockout matches)
TOTAL_MATCHES = 20 * 63


class HistoryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "history.db"
        database_url = f"sqlite:///{database_path.as_posix()}"
        self.database_url = database_url
        seed_database(database_url)
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)

        app = create_app()

        def override_session():
            with session_factory() as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        self.client = TestClient(app)
        self.addCleanup(self.temp_dir.cleanup)
        self.addCleanup(engine.dispose)
        self.addCleanup(self.client.close)

    def test_seed_contains_expected_matches_and_years(self) -> None:
        response = self.client.get("/api/history/matches", params={"limit": 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], TOTAL_MATCHES)
        self.assertEqual(self.client.get("/api/history/years").json(), [2026, 2025, 2024, 2023, 2022])
        self.assertEqual(len(self.client.get("/api/history/players").json()), 200)

    def query(self, sql: str) -> list:
        engine = create_engine(self.database_url)
        self.addCleanup(engine.dispose)
        with engine.connect() as connection:
            return list(connection.execute(text(sql)).all())

    def test_seeded_set_scores_follow_table_tennis_rules(self) -> None:
        rows = self.query("SELECT player1_score, player2_score FROM match_sets")

        self.assertTrue(rows)
        for score1, score2 in rows:
            high, low = max(score1, score2), min(score1, score2)
            self.assertGreaterEqual(high, 11)
            self.assertGreaterEqual(high - low, 2)
            self.assertTrue(high == 11 or high - low == 2, f"{score1}:{score2}")

    def test_seeded_matches_are_best_of_five_and_consistent(self) -> None:
        matches = self.query("SELECT id, player1_id, player2_id, winner_id FROM matches")
        sets_by_match: dict[int, list[tuple[int, int]]] = {}
        for match_id, score1, score2 in self.query(
            "SELECT match_id, player1_score, player2_score FROM match_sets ORDER BY match_id, set_number"
        ):
            sets_by_match.setdefault(match_id, []).append((score1, score2))

        self.assertEqual(len(matches), TOTAL_MATCHES)
        for match_id, player1_id, player2_id, winner_id in matches:
            sets = sets_by_match[match_id]
            player1_sets = sum(score1 > score2 for score1, score2 in sets)
            player2_sets = len(sets) - player1_sets
            self.assertEqual(max(player1_sets, player2_sets), 3)
            self.assertLessEqual(min(player1_sets, player2_sets), 2)
            expected_winner = player1_id if player1_sets == 3 else player2_id
            self.assertEqual(winner_id, expected_winner)
            self.assertEqual(sets[-1][0] > sets[-1][1], winner_id == player1_id)

    def test_tournaments_last_one_day_and_never_share_a_date(self) -> None:
        tournaments = self.query("SELECT id, date_from, date_to FROM tournaments")

        self.assertEqual(len(tournaments), 20)
        self.assertEqual(len({row[1] for row in tournaments}), len(tournaments))
        self.assertTrue(all(row[1] == row[2] for row in tournaments))
        played = self.query("SELECT COUNT(*) FROM matches m JOIN tournaments t ON t.id = m.tournament_id WHERE m.played_at != t.date_from")
        self.assertEqual(played[0][0], 0)

    def test_tournament_structure_groups_and_knockout(self) -> None:
        tournament_ids = [row[0] for row in self.query("SELECT id FROM tournaments")]
        knockout = ["Osmifinále", "Čtvrtfinále", "Semifinále", "Finále"]
        for tournament_id in tournament_ids:
            rows = self.query(
                f"SELECT round, player1_id, player2_id, winner_id FROM matches WHERE tournament_id = {tournament_id}"
            )
            by_round: dict[str, list[tuple[int, int, int]]] = {}
            for round_name, player1_id, player2_id, winner_id in rows:
                by_round.setdefault(round_name, []).append((player1_id, player2_id, winner_id))

            groups = [f"Skupina {name}" for name in "ABCDEFGH"]
            self.assertEqual(set(by_round), {*groups, *knockout})
            entrants: set[int] = set()
            for group in groups:
                self.assertEqual(len(by_round[group]), 6)
                members = {player for match in by_round[group] for player in match[:2]}
                self.assertEqual(len(members), 4)
                self.assertFalse(entrants & members, "a player is registered in two groups")
                entrants |= members
                pairs = {frozenset(match[:2]) for match in by_round[group]}
                self.assertEqual(len(pairs), 6, "group is not a full round robin")
            self.assertEqual(len(entrants), 32)

            self.assertEqual([len(by_round[name]) for name in knockout], [8, 4, 2, 1])
            qualified = {player for match in by_round["Osmifinále"] for player in match[:2]}
            self.assertEqual(len(qualified), 16)
            self.assertTrue(qualified <= entrants)
            # Every knockout round is played only by the winners of the previous one.
            for previous, current in zip(knockout, knockout[1:]):
                winners = {match[2] for match in by_round[previous]}
                self.assertEqual({player for match in by_round[current] for player in match[:2]}, winners)

            pair_counts: dict[frozenset[int], int] = {}
            for round_matches in by_round.values():
                for player1_id, player2_id, _ in round_matches:
                    pair = frozenset((player1_id, player2_id))
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1
            self.assertLessEqual(max(pair_counts.values()), 2)

    def test_group_qualifiers_have_most_points_and_tie_breaks(self) -> None:
        rng = random.Random(1)
        win = [(11, 5)] * 3

        def match(first: int, second: int, winner: int) -> PlayedMatch:
            sets = win if winner == first else [(5, 11)] * 3
            return PlayedMatch(first, second, winner, list(sets))

        # 1 and 2 beat everyone else; 1 beat 2, so both qualify regardless of order.
        matches = [match(1, 2, 1), match(1, 3, 1), match(1, 4, 1), match(2, 3, 2), match(2, 4, 2), match(3, 4, 3)]
        self.assertEqual(set(group_qualifiers(rng, [1, 2, 3, 4], matches)), {1, 2})

        # 1 wins all, 2/3/4 each have one win; the mutual 2-3-4 circle gives equal sets,
        # so the balls from mutual matches decide, here in favour of player 3.
        circle = [
            PlayedMatch(2, 3, 3, [(5, 11), (5, 11), (5, 11)]),
            PlayedMatch(3, 4, 3, [(11, 0), (11, 0), (11, 0)]),
            PlayedMatch(4, 2, 4, [(11, 9), (11, 9), (11, 9)]),
        ]
        matches = [match(1, 2, 1), match(1, 3, 1), match(1, 4, 1), *circle]
        self.assertEqual(set(group_qualifiers(rng, [1, 2, 3, 4], matches)), {1, 3})

    def test_seed_is_idempotent(self) -> None:
        self.assertEqual(seed_database(self.database_url), 0)
        self.assertEqual(self.client.get("/api/history/matches", params={"limit": 1}).json()["total"], TOTAL_MATCHES)

    def test_seed_database_supports_read_only_sqlite_uri(self) -> None:
        database_path = Path(self.temp_dir.name) / "history.db"
        read_only_url = f"sqlite:///file:{database_path.as_posix()}?mode=ro&uri=true"
        read_only_engine = create_engine(read_only_url)
        self.addCleanup(read_only_engine.dispose)

        with read_only_engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT COUNT(*) FROM matches")), TOTAL_MATCHES)
        with self.assertRaises(OperationalError):
            with read_only_engine.begin() as connection:
                connection.execute(text("DELETE FROM matches"))

    def test_filters_by_year_player_and_tournament(self) -> None:
        tournaments = self.client.get("/api/history/tournaments", params={"year": 2026}).json()
        self.assertEqual(len(tournaments), 4)

        player = self.client.get("/api/history/players", params={"search": "Jan Novak"}).json()[0]
        response = self.client.get(
            "/api/history/matches",
            params={"year": 2026, "player_id": player["id"], "tournament_id": tournaments[0]["id"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(player["id"] in (item["player1"]["id"], item["player2"]["id"]) for item in response.json()["items"]))

    def test_chat_answers_with_seeded_player_results(self) -> None:
        response = self.client.post(
            "/api/history/chat",
            json={"message": "Jaké zápasy odehrál Jan Novak?"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Jan Novák", response.json()["reply"])
        self.assertTrue(response.json()["matches"])

    def test_chat_asks_for_player_when_name_is_missing(self) -> None:
        response = self.client.post("/api/history/chat", json={"message": "Jaké zápasy se hrály?"})

        self.assertIn("Nenašel jsem", response.json()["reply"])


if __name__ == "__main__":
    unittest.main()
