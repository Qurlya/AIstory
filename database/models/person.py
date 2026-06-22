from sqlalchemy import UniqueConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

class PersonCategoryModel(Base):
    uid = (
        "category_id",
        "value",
        "person_id",
    )
    __tablename__ = "person_categories"
    __table_args__ = (UniqueConstraint(*uid),)

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(100))

    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    person: Mapped["PersonModel"] = relationship(
        "PersonModel", back_populates="categories",
    )
    category: Mapped["CategoryModel"] = relationship(
        "CategoryModel", back_populates="person_categories",
    )


class CategoryModel(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(25), unique=True)

    person_categories: Mapped[list["PersonCategoryModel"]] = relationship(
        "PersonCategoryModel", back_populates="category"
    )


class PersonModel(Base):
    uid = (
        "person_name",
    )
    __tablename__ = "persons"
    __table_args__ = (UniqueConstraint(*uid),)

    id: Mapped[int] = mapped_column(primary_key=True)
    person_name: Mapped[str] = mapped_column(String(50))

    categories: Mapped[list["PersonCategoryModel"]] = relationship(
        "PersonCategoryModel", back_populates="person"
    )