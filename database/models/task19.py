from sqlalchemy import UniqueConstraint, String, ForeignKey, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db_engine import Base
from .event import EraModel

class Task19Model(Base):
    uid = (
        "question",
        "standard",
        "era_id",
    )
    __tablename__ = "task19"
    __table_args__ = (UniqueConstraint(*uid),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(String(400))
    standard: Mapped[str] = mapped_column(String(400))
    era_id: Mapped[int | None] = mapped_column(ForeignKey("eras.id"), nullable=True)

    era: Mapped["EraModel | None"] = relationship("EraModel")
    request: Mapped[list["Task19RequestModel"]] = relationship(back_populates="task")

class Task19RequestModel(Base):
    uid = (
        "user_id",
        "task_id",
        "student_answer",
        "ai_feedback",
    )
    __tablename__ = "request_task19"
    __table_args__ = (UniqueConstraint(*uid),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task19.id"))
    student_answer: Mapped[str] = mapped_column(Text)
    ai_feedback: Mapped[str] = mapped_column(Text)

    task: Mapped["Task19Model"] = relationship(back_populates="request")

