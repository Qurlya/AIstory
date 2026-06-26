import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base


class UserEventStatsModel(Base):
    __tablename__ = "user_event_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    training_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    training_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    training_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    intensive_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    intensive_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    intensive_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    marathon_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    marathon_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    marathon_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_training_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_training_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_training_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_intensive_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_intensive_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_intensive_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_marathon_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_marathon_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_marathon_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_update_info: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)


class UserCultureStatsModel(Base):
    __tablename__ = "user_culture_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    culture_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    culture_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    culture_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_culture_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_culture_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_culture_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_update_info: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)


class UserPersonalityStatsModel(Base):
    __tablename__ = "user_personality_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    personality_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    personality_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    personality_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_personality_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_personality_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_personality_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_update_info: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)


class UserStreakModel(Base):
    __tablename__ = "user_streaks"

    id: Mapped[int] = mapped_column(primary_key=True)
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime(1970, 1, 1), nullable=False)


class UserRatingModel(Base):
    __tablename__ = "user_ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    show_in_rating: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    display_as: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    monthly_points: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    rating_year: Mapped[int] = mapped_column(Integer, default=lambda: datetime.datetime.utcnow().year, nullable=False)
    rating_month: Mapped[int] = mapped_column(Integer, default=lambda: datetime.datetime.utcnow().month, nullable=False)


class UserAdStatsModel(Base):
    __tablename__ = "user_ad_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    ad_clicks_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ad_clicks_week: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ad_clicks_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ad_clicked_once: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ad_clicked_week: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ad_clicked_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ad_last_click_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("telegram_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    telegram_id: Mapped[int] = mapped_column(nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    event_stats: Mapped[UserEventStatsModel | None] = relationship(
        lazy="selectin",
        primaryjoin=lambda: UserModel.id == foreign(UserEventStatsModel.id),
        uselist=False,
    )
    culture_stats: Mapped[UserCultureStatsModel | None] = relationship(
        lazy="selectin",
        primaryjoin=lambda: UserModel.id == foreign(UserCultureStatsModel.id),
        uselist=False,
    )
    personality_stats: Mapped[UserPersonalityStatsModel | None] = relationship(
        lazy="selectin",
        primaryjoin=lambda: UserModel.id == foreign(UserPersonalityStatsModel.id),
        uselist=False,
    )
    streak: Mapped[UserStreakModel | None] = relationship(
        lazy="selectin",
        primaryjoin=lambda: UserModel.id == foreign(UserStreakModel.id),
        uselist=False,
    )
    rating: Mapped[UserRatingModel | None] = relationship(
        lazy="selectin",
        primaryjoin=lambda: UserModel.id == foreign(UserRatingModel.id),
        uselist=False,
    )
    ad_stats: Mapped[UserAdStatsModel | None] = relationship(
        lazy="selectin",
        primaryjoin=lambda: UserModel.id == foreign(UserAdStatsModel.id),
        uselist=False,
    )

    def __getattr__(self, name: str):
        for related_name in ("event_stats", "culture_stats", "personality_stats", "streak", "rating", "ad_stats"):
            related = self.__dict__.get(related_name)
            if related is not None and hasattr(related, name):
                return getattr(related, name)
        raise AttributeError(name)
