import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        patcher = mock.patch.dict(os.environ, {"CHAT_ENABLED": "true"})
        patcher.start()
        self.addCleanup(patcher.stop)
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

    def chat(self, message: str, **filters: int) -> dict:
        response = self.client.post("/api/history/chat", json={"message": message, **filters})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def pair_with_distinct_surnames(self) -> tuple[dict, dict]:
        """Return the two players of one seeded match, whose surnames differ."""
        item = next(
            item
            for item in self.client.get("/api/history/matches", params={"limit": 500}).json()["items"]
            if item["player1"]["name"].split()[-1] != item["player2"]["name"].split()[-1]
        )
        return item["player1"], item["player2"]

    def test_chat_head_to_head_returns_only_matches_between_the_two_players(self) -> None:
        first, second = self.pair_with_distinct_surnames()

        result = self.chat(f"{first['name']} vs {second['name']}")

        self.assertTrue(result["matches"])
        self.assertIn("Vzájemná bilance", result["reply"])
        for item in result["matches"]:
            self.assertEqual({item["player1"]["id"], item["player2"]["id"]}, {first["id"], second["id"]})

    def test_chat_head_to_head_lists_all_players_sharing_a_surname(self) -> None:
        players = self.client.get("/api/history/players").json()
        by_surname: dict[str, list[dict]] = {}
        for player in players:
            by_surname.setdefault(player["name"].split()[-1], []).append(player)
        shared = {surname: group for surname, group in by_surname.items() if len(group) > 1}
        self.assertTrue(shared)

        # Find a match between a player with a shared surname and an opponent with another surname.
        for item in self.client.get("/api/history/matches", params={"limit": 500}).json()["items"]:
            for own, opponent in ((item["player1"], item["player2"]), (item["player2"], item["player1"])):
                surname = own["name"].split()[-1]
                if surname in shared and surname != opponent["name"].split()[-1]:
                    group = shared[surname]
                    result = self.chat(f"{surname} vs {opponent['name']}")
                    for member in group:
                        self.assertIn(member["name"], result["reply"])
                    ids = {member["id"] for member in group}
                    self.assertIn(item["id"], {match["id"] for match in result["matches"]})
                    for match in result["matches"]:
                        pair = {match["player1"]["id"], match["player2"]["id"]}
                        self.assertIn(opponent["id"], pair)
                        self.assertTrue(pair & ids)
                    return
        self.fail("no match with a shared surname found")

    def test_chat_uses_selected_player_filter_as_first_side_of_head_to_head(self) -> None:
        first, second = self.pair_with_distinct_surnames()

        result = self.chat(f"jak hrál proti {second['name']}", player_id=first["id"])

        self.assertIn("Vzájemná bilance", result["reply"])
        for item in result["matches"]:
            self.assertEqual({item["player1"]["id"], item["player2"]["id"]}, {first["id"], second["id"]})

    def test_chat_ambiguous_surname_only_lists_players_active_in_selected_year(self) -> None:
        players = {p["id"]: p["name"] for p in self.client.get("/api/history/players").json()}
        surnames = [name.split()[-1] for name in players.values()]
        year = self.client.get("/api/history/years").json()[0]
        items = self.client.get("/api/history/matches", params={"year": year, "limit": 2000}).json()["items"]
        active = {i["player1"]["id"] for i in items} | {i["player2"]["id"] for i in items}
        surname = next(
            s
            for s in set(surnames)
            if surnames.count(s) > 1
            and 1 < sum(1 for pid, n in players.items() if n.split()[-1] == s and pid in active) < surnames.count(s)
        )
        inactive = [n for pid, n in players.items() if n.split()[-1] == surname and pid not in active]

        result = self.chat(f"Jak hrál {surname}?", year=year)

        self.assertIn(str(year), result["reply"])
        for name in inactive:
            self.assertNotIn(name, result["reply"])

    def test_chat_ambiguous_surname_shows_matches_of_all_and_lists_candidates(self) -> None:
        players = self.client.get("/api/history/players").json()
        surnames = [player["name"].split()[-1] for player in players]
        surname = next(name for name in surnames if surnames.count(name) > 1)
        group_ids = {p["id"] for p in players if p["name"].split()[-1] == surname}

        result = self.chat(f"Jak hrál {surname}?")

        self.assertIn("jsem našel", result["reply"])
        self.assertTrue(result["matches"])
        for item in result["matches"]:
            self.assertTrue({item["player1"]["id"], item["player2"]["id"]} & group_ids)

    def test_chat_first_name_only_finds_matches_of_all_players_with_it(self) -> None:
        players = self.client.get("/api/history/players").json()
        surnames = {p["name"].split()[-1] for p in players}
        first_names = [p["name"].split()[0] for p in players]
        first = next(n for n in first_names if first_names.count(n) > 1 and n not in surnames)
        group_ids = {p["id"] for p in players if p["name"].split()[0] == first}

        result = self.chat(f"Jak hrál {first}?")

        self.assertIn("jsem našel", result["reply"])
        self.assertTrue(result["matches"])
        for item in result["matches"]:
            self.assertTrue({item["player1"]["id"], item["player2"]["id"]} & group_ids)

    def test_chat_full_name_works_in_both_orders(self) -> None:
        player = self.client.get("/api/history/players").json()[0]
        first, last = player["name"].split()[0], player["name"].split()[-1]

        for text in (f"{first} {last}", f"{last} {first}"):
            result = self.chat(text)
            self.assertTrue(result["matches"], text)
            self.assertIn(player["name"], result["reply"])

    def test_chat_is_disabled_by_default_and_returns_503(self) -> None:
        with mock.patch.dict(os.environ, clear=False):
            os.environ.pop("CHAT_ENABLED", None)
            response = self.client.post("/api/history/chat", json={"message": "Jan Novák"})
            self.assertEqual(response.status_code, 503)
            os.environ["CHAT_ENABLED"] = "false"
            response = self.client.post("/api/history/chat", json={"message": "Jan Novák"})
            self.assertEqual(response.status_code, 503)

    def test_other_endpoints_work_when_chat_is_disabled(self) -> None:
        with mock.patch.dict(os.environ, {"CHAT_ENABLED": "false"}):
            self.assertEqual(self.client.get("/api/history/matches").status_code, 200)

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
