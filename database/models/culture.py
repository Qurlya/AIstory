from enum import Enum

from sqlalchemy import Enum as SqlEnum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CultureType(str, Enum):
    ADMINISTRATIVE = "административное"
    TOWER = "башня"
    SKYSCRAPER = "высотка"
    PALACE = "дворец"
    HOUSE = "дом"
    MEMORIAL = "мемориал"
    MONUMENT = "монумент"
    SCULPTURE = "скульптура"
    TEMPLE = "храм"

class CultureModel(Base):
    uid = (
        "img_name",
        "date",
        "build_name",
        "author",
        "city",
        "king",
        "style",
    )
    __tablename__ = "cultures"
    __table_args__ = (UniqueConstraint(*uid),)

    id: Mapped[int] = mapped_column(primary_key=True)
    img_name: Mapped[str] = mapped_column(String(25))
    build_name: Mapped[str] = mapped_column(String(50))
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date: Mapped[str] = mapped_column(String(50))
    city: Mapped[str] = mapped_column(String(50))
    king: Mapped[str] = mapped_column(String(50))
    style: Mapped[str] = mapped_column(String(50))
    type: Mapped[CultureType] = mapped_column(
        SqlEnum(
            CultureType,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            name="culture_type",
        )
    )
