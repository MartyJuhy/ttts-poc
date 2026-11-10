import math
import random
import unicodedata
from dataclasses import dataclass
from datetime import date
from itertools import combinations
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

EXTRA_FIRST_NAMES = [
    "Adam", "Antonín", "Bedřich", "Bohumil", "Dominik", "Emil", "Filip", "Gabriel", "Hynek", "Ivan",
    "Jakub", "Jan", "Jaroslav", "Jindřich", "Jiří", "Josef", "Kryštof", "Ladislav", "Libor", "Lukáš",
    "Marek", "Martin", "Matěj", "Michal", "Miloslav", "Miroslav", "Oldřich", "Patrik", "Pavel", "Petr",
    "Radim", "René", "Richard", "Rostislav", "Štěpán", "Tadeáš", "Tomáš", "Vladimír", "Vojtěch", "Zdeněk",
]
EXTRA_LAST_NAMES = [
    "Horák", "Zeman", "Kolář", "Navrátil", "Čermák", "Vaněk", "Šimek", "Doležal", "Kratochvíl", "Sedláček",
    "Havlík", "Vlček", "Soukup", "Holub", "Štěpánek", "Tichý", "Kopecký", "Vávra", "Malý", "Beran",
    "Slavík", "Kubát", "Bureš", "Straka", "Hruška", "Pešek", "Kadlec", "Matoušek", "Sýkora", "Valenta",
]
EXTRA_CLUBS = ["TJ Olomouc", "Sokol Hradec Králové", "SK České Budějovice", "TJ Zlín"]

PLAYER_COUNT = 200
YEARS = range(2022, 2027)
GROUP_COUNT = 8
GROUP_SIZE = 4
QUALIFIERS_PER_GROUP = 2
PLAYERS_PER_TOURNAMENT = GROUP_COUNT * GROUP_SIZE
KNOCKOUT_ROUNDS = ["Osmifinále", "Čtvrtfinále", "Semifinále", "Finále"]
GROUP_NAMES = "ABCDEFGH"


@dataclass
class PlayedMatch:
    player1_id: int
    player2_id: int
    winner_id: int
    sets: list[tuple[int, int]]


def plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def build_players(rng: random.Random) -> list[Player]:
    players = [
        Player(first_name=first, last_name=last, birth_year=birth, club=club)
        for first, last, birth, club in PLAYERS
    ]
    clubs = sorted({club for *_, club in PLAYERS}) + EXTRA_CLUBS
    names = [plain(f"{player.first_name} {player.last_name}") for player in players]
    while len(players) < PLAYER_COUNT:
        first, last = rng.choice(EXTRA_FIRST_NAMES), rng.choice(EXTRA_LAST_NAMES)
        name = plain(f"{first} {last}")
        # The chat finds players by full-name substring, so no name may contain another one.
        if any(name in existing or existing in name for existing in names):
            continue
        names.append(name)
        players.append(
            Player(first_name=first, last_name=last, birth_year=rng.randint(1965, 1992), club=rng.choice(clubs))
        )
    return players


def play_match(rng: random.Random, ratings: dict[int, float], player1_id: int, player2_id: int) -> PlayedMatch:
    player1_chance = 1 / (1 + math.exp(ratings[player2_id] - ratings[player1_id]))
    winner_id = player1_id if rng.random() < player1_chance else player2_id

    # Best of five: the match winner takes the last set and two of the earlier ones.
    earlier_sets = [True, True] + [False] * rng.randrange(3)
    rng.shuffle(earlier_sets)
    sets: list[tuple[int, int]] = []
    for match_winner_won in [*earlier_sets, True]:
        # A set goes to 11 points; from 10:10 on it is won by two points.
        loser_points = rng.choice([*range(10), 10, 11, 12])
        winner_points = 11 if loser_points <= 9 else loser_points + 2
        player1_won = match_winner_won == (winner_id == player1_id)
        sets.append((winner_points, loser_points) if player1_won else (loser_points, winner_points))
    return PlayedMatch(player1_id, player2_id, winner_id, sets)


def ratio(won: int, lost: int) -> float:
    return won / lost if lost else math.inf


def break_tie(rng: random.Random, tied: list[int], matches: list[PlayedMatch], slots: int) -> list[int]:
    """Rank players level on points by sets, then balls, from their mutual matches only; draw lots if still level."""
    sets_won = dict.fromkeys(tied, 0)
    sets_lost = dict.fromkeys(tied, 0)
    balls_won = dict.fromkeys(tied, 0)
    balls_lost = dict.fromkeys(tied, 0)
    for match in matches:
        if match.player1_id not in sets_won or match.player2_id not in sets_won:
            continue
        for score1, score2 in match.sets:
            player1_won_set = score1 > score2
            sets_won[match.player1_id] += player1_won_set
            sets_lost[match.player1_id] += not player1_won_set
            sets_won[match.player2_id] += not player1_won_set
            sets_lost[match.player2_id] += player1_won_set
            balls_won[match.player1_id] += score1
            balls_lost[match.player1_id] += score2
            balls_won[match.player2_id] += score2
            balls_lost[match.player2_id] += score1

    keys = {
        player_id: (
            ratio(sets_won[player_id], sets_lost[player_id]),
            ratio(balls_won[player_id], balls_lost[player_id]),
        )
        for player_id in tied
    }
    # Players with identical keys are shuffled first, so the stable sort leaves them in a random order.
    shuffled = rng.sample(tied, len(tied))
    return sorted(shuffled, key=lambda player_id: keys[player_id], reverse=True)[:slots]


def group_qualifiers(rng: random.Random, player_ids: list[int], matches: list[PlayedMatch]) -> list[int]:
    points = dict.fromkeys(player_ids, 0)
    for match in matches:
        points[match.winner_id] += 2

    qualifiers: list[int] = []
    for level in sorted(set(points.values()), reverse=True):
        slots = QUALIFIERS_PER_GROUP - len(qualifiers)
        if slots <= 0:
            break
        tied = [player_id for player_id in player_ids if points[player_id] == level]
        qualifiers.extend(tied if len(tied) <= slots else break_tie(rng, tied, matches, slots))
    return qualifiers


def to_match(tournament: Tournament, round_name: str, played: PlayedMatch) -> Match:
    return Match(
        tournament=tournament,
        played_at=tournament.date_from,
        player1_id=played.player1_id,
        player2_id=played.player2_id,
        winner_id=played.winner_id,
        round=round_name,
        sets=[
            MatchSet(set_number=number, player1_score=score1, player2_score=score2)
            for number, (score1, score2) in enumerate(played.sets, start=1)
        ],
    )


def play_tournament(
    rng: random.Random, ratings: dict[int, float], tournament: Tournament, player_ids: list[int]
) -> list[Match]:
    entrants = rng.sample(player_ids, PLAYERS_PER_TOURNAMENT)
    matches: list[Match] = []
    qualified: list[int] = []

    for index in range(GROUP_COUNT):
        group = entrants[index * GROUP_SIZE : (index + 1) * GROUP_SIZE]
        played = [play_match(rng, ratings, first, second) for first, second in combinations(group, 2)]
        matches.extend(to_match(tournament, f"Skupina {GROUP_NAMES[index]}", item) for item in played)
        qualified.extend(group_qualifiers(rng, group, played))

    # Random draw of the knockout bracket; players from the same group may meet again.
    rng.shuffle(qualified)
    for round_name in KNOCKOUT_ROUNDS:
        winners: list[int] = []
        for first, second in zip(qualified[::2], qualified[1::2]):
            played = play_match(rng, ratings, first, second)
            matches.append(to_match(tournament, round_name, played))
            winners.append(played.winner_id)
        qualified = winners
    return matches


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

        rng = random.Random(2026)
        players = build_players(rng)
        session.add_all(players)
        session.flush()
        player_ids = [player.id for player in players]
        ratings = {player_id: rng.gauss(0, 1) for player_id in player_ids}

        total = 0
        for year in YEARS:
            for name, city, month, day in TOURNAMENTS:
                start = date(year, month, day)
                # Each tournament lasts a single day and no two tournaments share a date.
                tournament = Tournament(name=name, city=city, date_from=start, date_to=start)
                session.add(tournament)
                matches = play_tournament(rng, ratings, tournament, player_ids)
                session.add_all(matches)
                total += len(matches)

        session.commit()
        return total


if __name__ == "__main__":
    inserted = seed_database()
    print(f"Seed complete; inserted {inserted} matches.")
