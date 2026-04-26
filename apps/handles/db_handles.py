from datetime import datetime, timedelta
from io import BytesIO
from typing import List, Dict
import logging

from sqlalchemy import select, and_, update, text
from telegram import Update
from telegram.ext import ContextTypes

from database import load_culture_to_db, load_events_to_db, database
from database.models import EventModel, EraModel, UserModel

logger = logging.getLogger(__name__)


async def load_datafile_to_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    filename: str = str(document.file_name)
    logger.info("Получен файл для загрузки: %s", filename)
    await update.message.reply_text(f"File: {filename}, Size: {document.file_size}")

    if document.mime_type not in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                              'application/vnd.ms-excel']:
        await update.message.reply_text(f'Wrong file extension.')

    file = await document.get_file()
    bio = BytesIO()
    await file.download_to_memory(bio)
    try:
        rows_count = (await load_culture_to_db(bio) if filename.find('culture')!=(-1) else await load_events_to_db(bio))
        await update.message.reply_text(f'Loaded {rows_count} rows')
    except Exception as e:
        logger.exception("Ошибка загрузки файла %s в БД", filename)
        await update.message.reply_text(f'load_datafile err: {str(e)}')


select_events_stmt = select(EventModel.name, EventModel.date)

async def get_events_name_date() -> List[Dict]:
    """Получает все события из базы данных"""
    async with database.session() as session:
        result = await session.execute(select_events_stmt)
        events = result.all()
        return [{'name': name, 'date': date} for name, date in events]

async def get_eras_name() -> List[Dict]:
    """Получает все эпохи из базы данных"""
    async with database.session() as session:
        result = await session.execute(
            select(EraModel.id, EraModel.name).order_by(EraModel.id)
        )
        eras = result.all()
        return [{'id': id, 'name': name} for id, name in eras]


async def get_events_with_filters(difficulty: int = None, era_id: int = None) -> List[Dict]:
    """Получает ВСЕ события с учетом фильтров сложности и эпохи"""
    async with database.session() as session:
        query = select_events_stmt

        conditions = []
        if difficulty is not None and difficulty != -1:
            conditions.append(EventModel.difficulty == difficulty)
        if era_id is not None and era_id != -1:
            conditions.append(EventModel.era_id == era_id)

        if conditions:
            if len(conditions) > 1:
                query = query.where(and_(*conditions))
            else:
                query = query.where(conditions[0])

        result = await session.execute(query)
        events = result.all()
        return [{'name': name, 'date': date} for name, date in events]

async def add_user(telegram_id: int) -> UserModel:
    async with database.session() as session:
        stmt = select(UserModel).where(UserModel.telegram_id == telegram_id)
        user = await session.scalar(stmt)

        if user:
            return user

        user = UserModel(
            username="",
            telegram_id=telegram_id,
            last_update_info=datetime.utcnow(),
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        return user


async def increment_field(
    telegram_id: int,
    field_name: str,
    value: int = 1,
):
    async with database.session() as session:

        stmt = select(UserModel).where(UserModel.telegram_id == telegram_id)
        user = await session.scalar(stmt)

        if not user:
            return

        now = datetime.utcnow()
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        new_week = user.last_update_info is None or user.last_update_info < start_of_week

        update_values = {}

        if not hasattr(UserModel, field_name):
            raise ValueError(f"Поле {field_name} не существует")

        column = getattr(UserModel, field_name)
        update_values[field_name] = column + value

        if new_week:
            for column_name in UserModel.__table__.columns.keys():
                if column_name.startswith("week_"):
                    update_values[column_name] = 0

        week_field_name = f"week_{field_name}"
        if hasattr(UserModel, week_field_name):
            week_column = getattr(UserModel, week_field_name)
            update_values[week_field_name] = (week_column if not new_week else 0) + value

        yesterday = (now - timedelta(days=1)).date()
        last_date = user.last_update_info.date() if user.last_update_info else None

        if last_date == yesterday:
            update_values["streak_days"] = UserModel.streak_days + 1
        elif last_date != now.date():
            update_values["streak_days"] = 1

        update_values["last_update_info"] = now

        stmt = update(UserModel).where(UserModel.telegram_id == telegram_id).values(**update_values)
        await session.execute(stmt)
        await session.commit()

async def get_user_by_telegram_id(telegram_id: int) -> UserModel | None:
    async with database.session() as session:
        stmt = select(UserModel).where(UserModel.telegram_id == telegram_id)
        return await session.scalar(stmt)

async def update_streak(telegram_id: int) -> None:
    async with database.session() as session:
        stmt = select(UserModel).where(UserModel.telegram_id == telegram_id)
        user = await session.scalar(stmt)

        if not user:
            return

        now = datetime.utcnow()
        today = now.date()
        yesterday = today - timedelta(days=1)
        day_before_yesterday = today - timedelta(days=2)

        last_activity_date = (
            user.last_activity.date() if user.last_activity else None
        )

        update_values = {}

        if last_activity_date == today:
            return

        if last_activity_date == yesterday:
            update_values["streak_days"] = UserModel.streak_days + 1

        else:
            update_values["streak_days"] = 1

        update_values["last_activity"] = now

        stmt = (
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(**update_values)
        )

        await session.execute(stmt)
        await session.commit()

async def get_all_users() -> List[UserModel]:
    """Получает всех пользователей из базы данных"""
    async with database.session() as session:
        stmt = select(UserModel).order_by(UserModel.id)
        result = await session.execute(stmt)
        users = result.scalars().all()
        return list(users)


async def get_random_cultures(limit: int = 5) -> List[Dict]:
    """Получает случайные элементы культуры из таблицы cultures."""
    async with database.session() as session:
        stmt = text("SELECT * FROM cultures ORDER BY RAND() LIMIT :limit")
        result = await session.execute(stmt, {"limit": limit})
        rows = result.mappings().all()
        return [dict(row) for row in rows]


async def get_all_cultures() -> List[Dict]:
    """Получает все элементы культуры в случайном порядке без повторов."""
    async with database.session() as session:
        stmt = text("SELECT * FROM cultures ORDER BY RAND()")
        result = await session.execute(stmt)
        rows = result.mappings().all()
        return [dict(row) for row in rows]


async def get_culture_answer_values(
    field_name: str,
    limit: int,
    exclude_value: str | None = None,
    culture_type: str | None = None,
) -> List[str]:
    field_map = {
        "title": "build_name",
        "architect": "author",
        "foundation_year": "date",
        "ruler": "king",
        "style": "style",
        "city": "city",
    }

    column_name = field_map.get(field_name)
    if not column_name:
        return []

    query_parts = [
        f"SELECT DISTINCT {column_name} AS value",
        "FROM cultures",
        f"WHERE {column_name} IS NOT NULL",
        f"AND {column_name} NOT IN ('', '—', 'None')",
    ]
    params: dict[str, str | int] = {"limit": limit}

    if exclude_value:
        query_parts.append(f"AND {column_name} != :exclude_value")
        params["exclude_value"] = exclude_value

    if culture_type:
        query_parts.append("AND type = :culture_type")
        params["culture_type"] = culture_type

    query_parts.append("ORDER BY RAND()")
    query_parts.append("LIMIT :limit")

    async with database.session() as session:
        stmt = text("\n".join(query_parts))
        result = await session.execute(stmt, params)
        rows = result.scalars().all()

    return [str(value) for value in rows]
