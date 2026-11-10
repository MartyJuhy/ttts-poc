import unicodedata
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Select, select
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
        normalized_message = normalize(request.message)
        players_in_message = [
            item
            for item in session.scalars(select(Player))
            if normalize(f"{item.first_name} {item.last_name}") in normalized_message
        ]

        if request.player_id is not None:
            player = session.get(Player, request.player_id)
            selected_players = [player] if player else []
        else:
            selected_players = players_in_message

        if not selected_players:
            return ChatResponse(
                reply="Nenašel jsem jednoznačné jméno hráče. Zkuste například „Jaké zápasy odehrál Jan Novák?“",
                matches=[],
            )
        if len(selected_players) > 1:
            names = ", ".join(f"{item.first_name} {item.last_name}" for item in selected_players)
            return ChatResponse(reply=f"V dotazu jsem našel více hráčů: {names}. Upřesněte prosím, kterého myslíte.", matches=[])

        player = selected_players[0]
        records = list(
            session.scalars(
                match_statement(request.year, request.tournament_id, player.id, None).limit(200)
            ).unique()
        )
        response_matches = [build_match_response(item) for item in records]
        name = f"{player.first_name} {player.last_name}"
        if not response_matches:
            reply = f"Pro hráče {name} jsem v tomto výběru žádné zápasy nenašel."
        else:
            year_text = f" v roce {request.year}" if request.year else ""
            reply = f"Zde jsou zápasy hráče {name}{year_text} ({len(response_matches)}):"
        return ChatResponse(reply=reply, matches=response_matches)

    return app


app = create_app()
