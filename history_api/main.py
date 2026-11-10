import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from history_api.database import get_session
from history_api.models import Match, Player, Tournament


class PlayerSummary(BaseModel):
    id: int
    name: str
    birth_year: int
    club: str


class MatchSetResponse(BaseModel):
    set_number: int
    player1_score: int
    player2_score: int


class MatchResponse(BaseModel):
    id: int
    played_at: date
    tournament_id: int
    tournament: str
    city: str
    round: str
    player1: PlayerSummary
    player2: PlayerSummary
    winner_id: int
    score: str
    sets: list[MatchSetResponse]


class MatchesResponse(BaseModel):
    items: list[MatchResponse]
    total: int


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    year: int | None = Field(default=None, ge=1900, le=2100)
    tournament_id: int | None = Field(default=None, ge=1)
    player_id: int | None = Field(default=None, ge=1)


class ChatResponse(BaseModel):
    reply: str
    matches: list[MatchResponse]


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def player_summary(player: Player) -> PlayerSummary:
    return PlayerSummary(
        id=player.id,
        name=f"{player.first_name} {player.last_name}",
        birth_year=player.birth_year,
        club=player.club,
    )


def build_match_response(match: Match) -> MatchResponse:
    player1_sets = sum(item.player1_score > item.player2_score for item in match.sets)
    player2_sets = sum(item.player2_score > item.player1_score for item in match.sets)
    return MatchResponse(
        id=match.id,
        played_at=match.played_at,
        tournament_id=match.tournament.id,
        tournament=match.tournament.name,
        city=match.tournament.city,
        round=match.round,
        player1=player_summary(match.player1),
        player2=player_summary(match.player2),
        winner_id=match.winner_id,
        score=f"{player1_sets}:{player2_sets}",
        sets=[
            MatchSetResponse(
                set_number=item.set_number,
                player1_score=item.player1_score,
                player2_score=item.player2_score,
            )
            for item in match.sets
        ],
    )


def match_statement(
    year: int | None,
    tournament_id: int | None,
    player_id: int | None,
    opponent_id: int | None,
) -> Select[tuple[Match]]:
    statement = (
        select(Match)
        .join(Match.tournament)
        .options(
            joinedload(Match.tournament),
            joinedload(Match.player1),
            joinedload(Match.player2),
            selectinload(Match.sets),
        )
        .order_by(Match.played_at.desc(), Match.id.desc())
    )
    if year is not None:
        statement = statement.where(
            Tournament.date_from >= date(year, 1, 1),
            Tournament.date_from < date(year + 1, 1, 1),
        )
    if tournament_id is not None:
        statement = statement.where(Match.tournament_id == tournament_id)
    if player_id is not None:
        statement = statement.where((Match.player1_id == player_id) | (Match.player2_id == player_id))
    if opponent_id is not None:
        statement = statement.where((Match.player1_id == opponent_id) | (Match.player2_id == opponent_id))
    return statement


@dataclass
class Mention:
    """One player reference in a chat message; several candidates when the name is not unique."""

    label: str
    players: list[Player]


def find_mentions(message: str, players: list[Player]) -> list[Mention]:
    tokens = re.findall(r"\w+", normalize(message))
    used: set[int] = set()
    mentions: list[Mention] = []

    # Full names ("first last" or "last first") are unambiguous references.
    for start in range(len(tokens) - 1):
        if start in used or start + 1 in used:
            continue
        pair = (tokens[start], tokens[start + 1])
        matching = [
            player
            for player in players
            if pair in {
                (normalize(player.first_name), normalize(player.last_name)),
                (normalize(player.last_name), normalize(player.first_name)),
            }
        ]
        if matching:
            used.update((start, start + 1))
            mentions.append(Mention(f"{matching[0].first_name} {matching[0].last_name}", matching))

    # A bare surname may belong to several players; all of them become candidates.
    # Only when no surname matches is the word tried as a first name.
    for index, token in enumerate(tokens):
        if index in used:
            continue
        matching = [player for player in players if normalize(player.last_name) == token]
        label_of = lambda player: player.last_name  # noqa: E731
        if not matching:
            matching = [player for player in players if normalize(player.first_name) == token]
            label_of = lambda player: player.first_name  # noqa: E731
        if matching:
            used.add(index)
            mentions.append(Mention(label_of(matching[0]), matching))

    unique: list[Mention] = []
    seen: set[frozenset[int]] = set()
    for mention in mentions:
        key = frozenset(player.id for player in mention.players)
        if key not in seen:
            seen.add(key)
            unique.append(mention)
    return unique


def full_name(player: Player) -> str:
    return f"{player.first_name} {player.last_name}"


def head_to_head_reply(first: Mention, second: Mention, records: list[Match]) -> str:
    parts: list[str] = []
    for mention in (first, second):
        if len(mention.players) > 1:
            names = ", ".join(full_name(player) for player in mention.players)
            parts.append(f"Pod jménem „{mention.label}“ je více hráčů ({names}), zobrazuji všechny.")

    wins: dict[tuple[int, int], dict[int, int]] = {}
    for record in records:
        pair = (min(record.player1_id, record.player2_id), max(record.player1_id, record.player2_id))
        pair_wins = wins.setdefault(pair, {pair[0]: 0, pair[1]: 0})
        pair_wins[record.winner_id] += 1

    people = {player.id: player for mention in (first, second) for player in mention.players}
    summaries = []
    for (low, high), pair_wins in sorted(wins.items()):
        total = pair_wins[low] + pair_wins[high]
        summaries.append(
            f"{full_name(people[low])} {pair_wins[low]}:{pair_wins[high]} {full_name(people[high])} ({total} z.)"
        )
    if not summaries:
        parts.append(f"{first.label} a {second.label} spolu v tomto výběru nehráli.")
    else:
        parts.append("Vzájemná bilance: " + "; ".join(summaries) + ".")
    return " ".join(parts)


def chat_enabled() -> bool:
    # Read per request so the Cloud Run env var can be flipped without code changes.
    return os.getenv("CHAT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def create_app() -> FastAPI:
    app = FastAPI(title="TTTS Historical Results API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174", "https://ttts-poc.web.app"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/history/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/history/years", response_model=list[int])
    def years(session: Annotated[Session, Depends(get_session)]) -> list[int]:
        return sorted(
            {item.year for item in session.scalars(select(Tournament.date_from).distinct())},
            reverse=True,
        )

    @app.get("/api/history/tournaments")
    def tournaments(
        session: Annotated[Session, Depends(get_session)],
        year: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    ) -> list[dict[str, int | str]]:
        statement = select(Tournament).order_by(Tournament.date_from.desc(), Tournament.name)
        if year is not None:
            statement = statement.where(
                Tournament.date_from >= date(year, 1, 1),
                Tournament.date_from < date(year + 1, 1, 1),
            )
        return [
            {
                "id": item.id,
                "name": item.name,
                "city": item.city,
                "year": item.date_from.year,
            }
            for item in session.scalars(statement)
        ]

    @app.get("/api/history/players", response_model=list[PlayerSummary])
    def players(
        session: Annotated[Session, Depends(get_session)],
        search: Annotated[str, Query(max_length=100)] = "",
    ) -> list[PlayerSummary]:
        candidates = session.scalars(select(Player).order_by(Player.last_name, Player.first_name))
        normalized_search = normalize(search.strip())
        return [
            player_summary(item)
            for item in candidates
            if not normalized_search
            or normalized_search
            in normalize(f"{item.first_name} {item.last_name} {item.club}")
        ]

    @app.get("/api/history/matches", response_model=MatchesResponse)
    def matches(
        session: Annotated[Session, Depends(get_session)],
        year: Annotated[int | None, Query(ge=1900, le=2100)] = None,
        tournament_id: int | None = None,
        player_id: int | None = None,
        opponent_id: int | None = None,
        search: Annotated[str, Query(max_length=100)] = "",
        limit: Annotated[int, Query(ge=1, le=2000)] = 200,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> MatchesResponse:
        records = list(
            session.scalars(
                match_statement(year, tournament_id, player_id, opponent_id)
            ).unique()
        )
        normalized_search = normalize(search.strip())
        if normalized_search:
            records = [
                item
                for item in records
                if normalized_search
                in normalize(
                    f"{item.player1.first_name} {item.player1.last_name} "
                    f"{item.player2.first_name} {item.player2.last_name} "
                    f"{item.tournament.name} {item.tournament.city}"
                )
            ]
        total = len(records)
        return MatchesResponse(
            items=[build_match_response(item) for item in records[offset : offset + limit]],
            total=total,
        )

    @app.post("/api/history/chat", response_model=ChatResponse)
    def chat(
        request: ChatRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ChatResponse:
        if not chat_enabled():
            raise HTTPException(status_code=503, detail="Chat is currently disabled.")
        all_players = list(session.scalars(select(Player)))
        mentions = find_mentions(request.message, all_players)

        if request.year is not None or request.tournament_id is not None:
            scope = match_statement(request.year, request.tournament_id, None, None).subquery()
            active_ids = set(session.scalars(select(scope.c.player1_id))) | set(
                session.scalars(select(scope.c.player2_id))
            )
            scoped: list[Mention] = []
            for mention in mentions:
                active = [p for p in mention.players if p.id in active_ids]
                if active:
                    scoped.append(Mention(mention.label, active))
            if mentions and not scoped:
                period = f" v roce {request.year}" if request.year else " ve vybraném turnaji"
                return ChatResponse(
                    reply=f"Hráče z dotazu jsem{period} mezi odehranými zápasy nenašel. Zkuste jiný rok.",
                    matches=[],
                )
            mentions = scoped

        if request.player_id is not None:
            selected = session.get(Player, request.player_id)
            if selected is None:
                mentions = []
            else:
                others = [m for m in mentions if all(p.id != selected.id for p in m.players)]
                mentions = [Mention(full_name(selected), [selected]), *others]

        if not mentions:
            return ChatResponse(
                reply=(
                    "Nenašel jsem jednoznačné jméno hráče. Zkuste například „Jaké zápasy odehrál Jan Novák?“ "
                    "nebo „Novák vs Svoboda“."
                ),
                matches=[],
            )
        if len(mentions) > 2:
            names = ", ".join(mention.label for mention in mentions)
            return ChatResponse(reply=f"V dotazu jsem našel více hráčů: {names}. Upřesněte prosím, kterého myslíte.", matches=[])

        if len(mentions) == 2:
            first, second = mentions
            first_ids = [player.id for player in first.players]
            second_ids = [player.id for player in second.players]
            statement = match_statement(request.year, request.tournament_id, None, None).where(
                or_(
                    and_(Match.player1_id.in_(first_ids), Match.player2_id.in_(second_ids)),
                    and_(Match.player1_id.in_(second_ids), Match.player2_id.in_(first_ids)),
                )
            )
            records = list(session.scalars(statement.limit(500)).unique())
            return ChatResponse(
                reply=head_to_head_reply(first, second, records),
                matches=[build_match_response(item) for item in records],
            )

        mention = mentions[0]
        player_ids = [item.id for item in mention.players]
        limit = 200
        statement = match_statement(request.year, request.tournament_id, None, None).where(
            or_(Match.player1_id.in_(player_ids), Match.player2_id.in_(player_ids))
        )
        records = list(session.scalars(statement.limit(limit + 1)).unique())
        truncated = len(records) > limit
        records = records[:limit]
        response_matches = [build_match_response(item) for item in records]
        year_text = f" v roce {request.year}" if request.year else ""

        if len(mention.players) == 1:
            name = full_name(mention.players[0])
            if not response_matches:
                reply = f"Pro hráče {name} jsem v tomto výběru žádné zápasy nenašel."
            else:
                reply = f"Zde jsou zápasy hráče {name}{year_text} ({len(response_matches)}):"
        else:
            names = ", ".join(full_name(item) for item in mention.players)
            reply = (
                f"Pod „{mention.label}“{year_text} jsem našel {len(mention.players)} hráčů: {names}. "
                f"Zobrazuji zápasy všech ({len(response_matches)}"
                f"{'+, zobrazeno prvních ' + str(limit) if truncated else ''}). "
                "Chcete-li to zúžit, upřesněte jméno a příjmení, např. „"
                f"{full_name(mention.players[0])}“."
            )
        return ChatResponse(reply=reply, matches=response_matches)

    return app


app = create_app()
