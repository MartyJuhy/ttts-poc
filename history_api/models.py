from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    birth_year: Mapped[int] = mapped_column(Integer, nullable=False)
    club: Mapped[str] = mapped_column(String(120), nullable=False)


class Tournament(Base):
    __tablename__ = "tournaments"
    __table_args__ = (CheckConstraint("date_to >= date_from", name="valid_tournament_dates"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)

    matches: Mapped[list["Match"]] = relationship(back_populates="tournament")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("player1_id != player2_id", name="different_players"),
        CheckConstraint("winner_id = player1_id OR winner_id = player2_id", name="winner_is_player"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), nullable=False)
    played_at: Mapped[date] = mapped_column(Date, nullable=False)
    player1_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    player2_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    winner_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    round: Mapped[str] = mapped_column(String(40), nullable=False)

    tournament: Mapped[Tournament] = relationship(back_populates="matches")
    player1: Mapped[Player] = relationship(foreign_keys=[player1_id])
    player2: Mapped[Player] = relationship(foreign_keys=[player2_id])
    sets: Mapped[list["MatchSet"]] = relationship(
        back_populates="match", cascade="all, delete-orphan", order_by="MatchSet.set_number"
    )


class MatchSet(Base):
    __tablename__ = "match_sets"
    __table_args__ = (
        UniqueConstraint("match_id", "set_number", name="unique_match_set"),
        CheckConstraint("set_number > 0", name="positive_set_number"),
        CheckConstraint("player1_score >= 0 AND player2_score >= 0", name="nonnegative_set_scores"),
        CheckConstraint("player1_score != player2_score", name="set_has_winner"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    player1_score: Mapped[int] = mapped_column(Integer, nullable=False)
    player2_score: Mapped[int] = mapped_column(Integer, nullable=False)

    match: Mapped[Match] = relationship(back_populates="sets")
