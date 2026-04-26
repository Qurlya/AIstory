import datetime

from sqlalchemy import String, DateTime, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.sql import func
from sqlalchemy.orm import mapped_column

from database import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("telegram_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(String(100), nullable=True)
    telegram_id: Mapped[int] = mapped_column(nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ===============================
    # 🔹 TRAINING
    # ===============================

    training_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    training_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    training_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ===============================
    # 🔹 INTENSIVE
    # ===============================

    intensive_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    intensive_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    intensive_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ===============================
    # 🔹 MARATHON
    # ===============================

    marathon_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    marathon_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    marathon_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ===============================
    # 🔹 НЕДЕЛЬНАЯ TRAINING
    # ===============================

    week_training_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_training_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_training_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ===============================
    # 🔹 НЕДЕЛЬНАЯ INTENSIVE
    # ===============================

    week_intensive_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_intensive_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_intensive_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ===============================
    # 🔹 НЕДЕЛЬНАЯ MARATHON
    # ===============================

    week_marathon_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_marathon_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_marathon_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ===============================
    # 🔹 CULTURE
    # ===============================

    culture_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    culture_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    culture_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ===============================
    # 🔹 НЕДЕЛЬНАЯ CULTURE
    # ===============================

    week_culture_completed_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_culture_completed_full: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_culture_true_cards: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ===============================
    # 🔥 STREAK (огонёк)
    # ===============================

    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime(1970, 1, 1, 0, 0, 0))

    last_update_info: Mapped[datetime.datetime] = mapped_column()
