import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from history_api.database import get_session
from history_api.main import create_app
from history_api.seed import seed_database


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

    def test_seed_contains_two_hundred_matches_and_years(self) -> None:
        response = self.client.get("/api/history/matches")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 200)
        self.assertEqual(self.client.get("/api/history/years").json(), [2026, 2025, 2024, 2023, 2022])

    def test_seeded_set_scores_follow_table_tennis_rules(self) -> None:
        engine = create_engine(self.database_url)
        self.addCleanup(engine.dispose)
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT player1_score, player2_score FROM match_sets")).all()

        self.assertTrue(rows)
        for score1, score2 in rows:
            high, low = max(score1, score2), min(score1, score2)
            self.assertGreaterEqual(high, 11)
            self.assertGreaterEqual(high - low, 2)
            self.assertTrue(high == 11 or high - low == 2, f"{score1}:{score2}")

    def test_seeded_matches_are_best_of_five_and_consistent(self) -> None:
        items = self.client.get("/api/history/matches", params={"limit": 200}).json()["items"]

        self.assertEqual(len(items), 200)
        for item in items:
            p1 = sum(s["player1_score"] > s["player2_score"] for s in item["sets"])
            p2 = len(item["sets"]) - p1
            self.assertIn(item["score"], {"3:0", "3:1", "3:2", "0:3", "1:3", "2:3"})
            self.assertEqual(item["score"], f"{p1}:{p2}")
            last = item["sets"][-1]
            last_winner = item["player1"]["id"] if last["player1_score"] > last["player2_score"] else item["player2"]["id"]
            self.assertEqual(last_winner, item["winner_id"])
            self.assertEqual(max(p1, p2), 3)

    def test_seed_is_idempotent(self) -> None:
        self.assertEqual(seed_database(self.database_url), 0)
        self.assertEqual(self.client.get("/api/history/matches").json()["total"], 200)

    def test_seed_database_supports_read_only_sqlite_uri(self) -> None:
        database_path = Path(self.temp_dir.name) / "history.db"
        read_only_url = f"sqlite:///file:{database_path.as_posix()}?mode=ro&uri=true"
        read_only_engine = create_engine(read_only_url)
        self.addCleanup(read_only_engine.dispose)

        with read_only_engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT COUNT(*) FROM matches")), 200)
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
            json={"message": "Jaké zápasy odehrál Jan Novak?", "year": 2026},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Jan Novák", response.json()["reply"])
        self.assertTrue(response.json()["matches"])

    def test_chat_asks_for_player_when_name_is_missing(self) -> None:
        response = self.client.post("/api/history/chat", json={"message": "Jaké zápasy se hrály?"})

        self.assertIn("Nenašel jsem", response.json()["reply"])


if __name__ == "__main__":
    unittest.main()
