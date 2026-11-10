import random
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from history_api.database import DATABASE_URL
from history_api.models import Base, Match, MatchSet, Player, Tournament


PLAYERS = [
    ("Jan", "Novák", 1978, "Sokol Praha"),
    ("Petr", "Svoboda", 1975, "SK Brno"),
    ("Jiří", "Dvořák", 1980, "Sokol Plzeň"),
    ("Milan", "Král", 1972, "TJ Ostrava"),
    ("Karel", "Černý", 1977, "Sokol Praha"),
    ("Pavel", "Marek", 1982, "SK Brno"),
    ("Martin", "Veselý", 1976, "TJ Liberec"),
    ("Tomáš", "Pokorný", 1979, "Sokol Plzeň"),
    ("Lukáš", "Hájek", 1984, "TJ Ostrava"),
    ("David", "Jelínek", 1973, "SK Brno"),
    ("Robert", "Němec", 1971, "Sokol Praha"),
    ("Roman", "Fiala", 1981, "TJ Liberec"),
    ("Michal", "Procházka", 1974, "Sokol Plzeň"),
    ("Radek", "Beneš", 1983, "TJ Ostrava"),
    ("Ondřej", "Kučera", 1978, "SK Brno"),
    ("Václav", "Mareš", 1970, "Sokol Praha"),
    ("Aleš", "Pospíšil", 1975, "TJ Liberec"),
    ("Stanislav", "Polák", 1985, "Sokol Plzeň"),
    ("Pavel", "Krejčí", 1979, "TJ Ostrava"),
    ("Josef", "Růžička", 1976, "SK Brno"),
    ("František", "Bartoš", 1972, "Sokol Praha"),
    ("Kamil", "Urban", 1981, "TJ Liberec"),
    ("Daniel", "Kříž", 1986, "Sokol Plzeň"),
    ("Viktor", "Blažek", 1974, "TJ Ostrava"),
]

TOURNAMENTS = [
    ("Jarní pohár", "Praha", 3, 15),
    ("Memoriál veteránů", "Brno", 5, 20),
    ("Letní turnaj", "Plzeň", 7, 12),
    ("Podzimní liga", "Ostrava", 10, 5),
]

ROUNDS = ["Skupina", "Skupina", "Osmifinále", "Čtvrtfinále", "Semifinále", "Finále"]


def seed_database(database_url: str = DATABASE_URL) -> int:
    if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:////"):
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        if session.scalar(select(func.count()).select_from(Match)):
            return 0

        players = [
            Player(first_name=first, last_name=last, birth_year=birth, club=club)
            for first, last, birth, club in PLAYERS
        ]
        session.add_all(players)
        session.flush()

        tournaments: list[Tournament] = []
        for year in range(2022, 2027):
            for name, city, month, day in TOURNAMENTS:
                start = date(year, month, day)
                tournament = Tournament(
                    name=name,
                    city=city,
                    date_from=start,
                    date_to=start + timedelta(days=1),
                )
                tournaments.append(tournament)
        session.add_all(tournaments)
        session.flush()

        rng = random.Random(2026)
        for index in range(200):
            player1_index = index % len(players)
            player2_index = (index * 7 + 5) % len(players)
            if player1_index == player2_index:
                player2_index = (player2_index + 1) % len(players)

            winner_index = player1_index if rng.random() < 0.5 else player2_index
            loser_sets = rng.randrange(3)
            winner_sets = 3
            tournament = tournaments[index % len(tournaments)]
            match = Match(
                tournament_id=tournament.id,
                played_at=tournament.date_from + timedelta(days=index % 2),
                player1_id=players[player1_index].id,
                player2_id=players[player2_index].id,
                winner_id=players[winner_index].id,
                round=ROUNDS[min(index % len(ROUNDS), len(ROUNDS) - 1)],
            )
            session.add(match)
            session.flush()

            # The match winner always takes the last set; the loser's sets are spread among the earlier ones.
            earlier_sets = [True] * (winner_sets - 1) + [False] * loser_sets
            rng.shuffle(earlier_sets)
            set_winners_are_match_winner = [*earlier_sets, True]
            for set_number, match_winner_won in enumerate(set_winners_are_match_winner, start=1):
                player1_won = match_winner_won == (winner_index == player1_index)
                # Set to 11 points, win by 2: 11:0-9, otherwise a deuce set ending N+2:N.
                loser_score = rng.choice([*range(0, 10), 10, 11, 12])
                winner_score = 11 if loser_score <= 9 else loser_score + 2
                session.add(
                    MatchSet(
                        match_id=match.id,
                        set_number=set_number,
                        player1_score=winner_score if player1_won else loser_score,
                        player2_score=loser_score if player1_won else winner_score,
                    )
                )

        session.commit()
        return 200


if __name__ == "__main__":
    inserted = seed_database()
    print(f"Seed complete; inserted {inserted} matches.")
