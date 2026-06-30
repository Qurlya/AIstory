from __future__ import annotations

from sqlalchemy import UniqueConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from database.db_engine import Base

class EraModel(Base):
    uid = (
        "name",
    )
    __tablename__ = "eras"
    __table_args__ = (UniqueConstraint(*uid),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

    #events: Mapped[list["EventModel"]] = relationship("EventModel", back_populates="era")
