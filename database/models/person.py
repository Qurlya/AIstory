from sqlalchemy import UniqueConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

class PersonCategoryModel(Base):
    uid = (
        "category",
        "value",
        "person_id",
    )
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint(*uid),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(25))
    value: Mapped[str] = mapped_column(String(100))

    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"), nullable=True)
    person: Mapped["PersonModel | None"] = relationship(
        "PersonModel", back_populates="persons",
    )


class PersonModel(Base):
    uid = (
        "person_name",
    )
    __tablename__ = "persons"
    __table_args__ = (UniqueConstraint(*uid),)

    id: Mapped[int] = mapped_column(primary_key=True)
    person_name: Mapped[str] = mapped_column(String(50))
