from datetime import datetime, timedelta
from html import escape
from io import BytesIO
from typing import List, Dict
import logging

from sqlalchemy import select, and_, update, text, func, case, desc
from telegram import Update
from telegram.ext import ContextTypes

from database import load_culture_to_db, load_events_to_db, load_persons_to_db, database
from database.models import (
    EventModel,
    EraModel,
    UserAdStatsModel,
    UserCultureStatsModel,
    UserEventStatsModel,
    UserModel,
    UserPersonalityStatsModel,
    UserRatingModel,
    UserStreakModel,
    PersonCategoryModel,
    PersonModel,
    CategoryModel,
)

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
        rows_count: int = 0
        match filename:
            case 'culture.xlsx':
                rows_count = await load_culture_to_db(bio)
            case 'events.xlsx':
                rows_count = await load_events_to_db(bio)
            case 'persons.xlsx':
                rows_count = await load_persons_to_db(bio)
        
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

async def _create_user_satellites(session):
    event_stats = UserEventStatsModel(last_update_info=datetime.utcnow())
    culture_stats = UserCultureStatsModel(last_update_info=datetime.utcnow())
    personality_stats = UserPersonalityStatsModel(last_update_info=datetime.utcnow())
    streak = UserStreakModel()
    rating = UserRatingModel()
    ad_stats = UserAdStatsModel()
    session.add_all([event_stats, culture_stats, personality_stats, streak, rating, ad_stats])
    await session.flush()
    return event_stats, culture_stats, personality_stats, streak, rating, ad_stats


async def _ensure_user_satellites(session, user: UserModel) -> UserModel:
    changed = False
    if not user.event_stats:
        user.event_stats = UserEventStatsModel(last_update_info=datetime.utcnow())
        changed = True
    if not user.culture_stats:
        user.culture_stats = UserCultureStatsModel(last_update_info=datetime.utcnow())
        changed = True
    if not user.personality_stats:
        user.personality_stats = UserPersonalityStatsModel(last_update_info=datetime.utcnow())
        changed = True
    if not user.streak:
        user.streak = UserStreakModel()
        changed = True
    if not user.rating:
        user.rating = UserRatingModel()
        changed = True
    if not user.ad_stats:
        user.ad_stats = UserAdStatsModel()
        changed = True
    if changed:
        await session.flush()
    return user


async def add_user(telegram_id: int, username: str | None = None) -> UserModel:
    async with database.session() as session:
        stmt = select(UserModel).where(UserModel.telegram_id == telegram_id)
        user = await session.scalar(stmt)

        if user:
            await _ensure_user_satellites(session, user)
            if username is not None and user.username != username:
                user.username = username
            await session.commit()
            await session.refresh(user)
            return user

        event_stats, culture_stats, personality_stats, streak, rating, ad_stats = await _create_user_satellites(session)
        user = UserModel(
            username=username or "",
            telegram_id=telegram_id,
            event_stats_id=event_stats.id,
            culture_stats_id=culture_stats.id,
            personality_stats_id=personality_stats.id,
            streak_id=streak.id,
            rating_id=rating.id,
            ad_stats_id=ad_stats.id,
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


_FIELD_MODEL_MAP = {
    "training_completed_cards": UserEventStatsModel,
    "training_completed_full": UserEventStatsModel,
    "training_true_cards": UserEventStatsModel,
    "intensive_completed_cards": UserEventStatsModel,
    "intensive_completed_full": UserEventStatsModel,
    "intensive_true_cards": UserEventStatsModel,
    "marathon_completed_cards": UserEventStatsModel,
    "marathon_completed_full": UserEventStatsModel,
    "marathon_true_cards": UserEventStatsModel,
    "culture_completed_cards": UserCultureStatsModel,
    "culture_completed_full": UserCultureStatsModel,
    "culture_true_cards": UserCultureStatsModel,
    "personality_completed_cards": UserPersonalityStatsModel,
    "personality_completed_full": UserPersonalityStatsModel,
    "personality_true_cards": UserPersonalityStatsModel,
}

_FIELD_RELATION_ID = {
    UserEventStatsModel: UserModel.event_stats_id,
    UserCultureStatsModel: UserModel.culture_stats_id,
    UserPersonalityStatsModel: UserModel.personality_stats_id,
}


async def increment_field(telegram_id: int, field_name: str, value: int = 1):
    model = _FIELD_MODEL_MAP.get(field_name)
    if model is None or not hasattr(model, field_name):
        raise ValueError(f"Поле {field_name} не существует")

    async with database.session() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        if not user:
            return
        await _ensure_user_satellites(session, user)

        stats_id = getattr(user, {UserEventStatsModel: "event_stats_id", UserCultureStatsModel: "culture_stats_id", UserPersonalityStatsModel: "personality_stats_id"}[model])
        stats = await session.get(model, stats_id)
        if not stats:
            return

        now = datetime.utcnow()
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        new_week = stats.last_update_info is None or stats.last_update_info < start_of_week

        update_values = {}
        column = getattr(model, field_name)
        update_values[field_name] = column + value

        if new_week:
            for column_name in model.__table__.columns.keys():
                if column_name.startswith("week_"):
                    update_values[column_name] = 0

        week_field_name = f"week_{field_name}"
        if hasattr(model, week_field_name):
            week_column = getattr(model, week_field_name)
            update_values[week_field_name] = (week_column if not new_week else 0) + value

        update_values["last_update_info"] = now
        await session.execute(update(model).where(model.id == stats_id).values(**update_values))
        await session.commit()


async def get_user_by_telegram_id(telegram_id: int) -> UserModel | None:
    async with database.session() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        if user:
            await _ensure_user_satellites(session, user)
        return user


async def update_streak(telegram_id: int, reset_if_missed: bool = False) -> None:
    async with database.session() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        if not user:
            return
        await _ensure_user_satellites(session, user)
        streak = user.streak

        now = datetime.utcnow()
        streak_state = get_streak_state_by_last_activity(streak.last_activity, now=now)
        update_values = {}

        if streak_state == "today":
            return
        if reset_if_missed and streak_state != "older":
            return
        if streak_state == "yesterday":
            update_values["streak_days"] = UserStreakModel.streak_days + 1
        else:
            update_values["streak_days"] = 0 if reset_if_missed else 1
        if not reset_if_missed:
            update_values["last_activity"] = now

        await session.execute(update(UserStreakModel).where(UserStreakModel.id == user.streak_id).values(**update_values))
        await session.commit()


def get_streak_state_by_last_activity(last_activity: datetime | None, now: datetime | None = None) -> str:
    if now is None:
        now = datetime.utcnow()
    today = now.date()
    yesterday = today - timedelta(days=1)
    last_activity_date = last_activity.date() if last_activity else None
    if last_activity_date == today:
        return "today"
    if last_activity_date == yesterday:
        return "yesterday"
    return "older"


async def get_all_users() -> List[UserModel]:
    async with database.session() as session:
        result = await session.execute(select(UserModel).order_by(UserModel.id))
        users = list(result.scalars().all())
        for user in users:
            await _ensure_user_satellites(session, user)
        return users


async def register_ad_click(telegram_id: int) -> None:
    async with database.session() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        if not user:
            return
        await _ensure_user_satellites(session, user)
        ad = user.ad_stats

        now = datetime.utcnow()
        update_values = {"ad_clicks_total": UserAdStatsModel.ad_clicks_total + 1}

        if not ad.ad_last_click_at or ad.ad_last_click_at.isocalendar()[:2] != now.isocalendar()[:2]:
            update_values["ad_clicks_week"] = 1
            update_values["ad_clicked_week"] = 1
        else:
            update_values["ad_clicks_week"] = UserAdStatsModel.ad_clicks_week + 1

        if not ad.ad_last_click_at or (ad.ad_last_click_at.year, ad.ad_last_click_at.month) != (now.year, now.month):
            update_values["ad_clicks_month"] = 1
            update_values["ad_clicked_month"] = 1
        else:
            update_values["ad_clicks_month"] = UserAdStatsModel.ad_clicks_month + 1

        if not ad.ad_clicked_once:
            update_values["ad_clicked_once"] = 1
        update_values["ad_last_click_at"] = now

        await session.execute(update(UserAdStatsModel).where(UserAdStatsModel.id == user.ad_stats_id).values(**update_values))
        await session.commit()


async def get_ads_stats() -> Dict[str, int]:
    async with database.session() as session:
        stmt = select(
            func.coalesce(func.sum(UserAdStatsModel.ad_clicks_total), 0),
            func.coalesce(func.sum(UserAdStatsModel.ad_clicks_week), 0),
            func.coalesce(func.sum(UserAdStatsModel.ad_clicks_month), 0),
            func.coalesce(func.sum(case((UserAdStatsModel.ad_clicked_once > 0, 1), else_=0)), 0),
            func.coalesce(func.sum(case((UserAdStatsModel.ad_clicked_week > 0, 1), else_=0)), 0),
            func.coalesce(func.sum(case((UserAdStatsModel.ad_clicked_month > 0, 1), else_=0)), 0),
        )
        result = await session.execute(stmt)
        total, week, month, unique_total, unique_week, unique_month = result.one()
        return {
            "total": int(total),
            "week": int(week),
            "month": int(month),
            "unique_total": int(unique_total),
            "unique_week": int(unique_week),
            "unique_month": int(unique_month),
        }


async def _reset_rating_if_needed(session, rating: UserRatingModel) -> None:
    now = datetime.utcnow()
    if (rating.rating_year, rating.rating_month) != (now.year, now.month):
        rating.monthly_points = 0
        rating.rating_year = now.year
        rating.rating_month = now.month
        await session.flush()


async def add_rating_points(telegram_id: int, delta: float) -> float:
    async with database.session() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        if not user:
            return 0
        await _ensure_user_satellites(session, user)
        rating = user.rating
        await _reset_rating_if_needed(session, rating)
        old_points = float(rating.monthly_points or 0)
        new_points = max(0, old_points + delta)
        rating.monthly_points = new_points
        await session.commit()
        return new_points - old_points


def format_rating_delta(delta: float) -> str:
    if delta > 0:
        return f"📈 Рейтинг вырос на +{delta:g}"
    if delta < 0:
        return f"📉 Рейтинг упал на {delta:g}"
    return "➖ Рейтинг не изменился"


async def apply_date_rating_points(telegram_id: int, difficulty: int | None, is_correct: bool) -> float:
    positive = {1: 0.5, 2: 1.0, 3: 1.5}.get(difficulty, 0.5)
    negative = -0.25 if difficulty == 1 else -0.5
    return await add_rating_points(telegram_id, positive if is_correct else negative)


async def apply_chronology_rating_points(telegram_id: int, correct: int, total: int = 5) -> float:
    return await add_rating_points(telegram_id, correct * 0.5 - (total - correct) * 0.25)


async def apply_culture_rating_points(telegram_id: int, results: dict[str, bool]) -> float:
    weights = {
        "title": (0.5, -0.25),
        "city": (0.5, -0.25),
        "foundation_year": (1.0, -0.5),
        "ruler": (1.0, -0.5),
        "style": (1.5, -0.5),
        "architect": (1.5, -0.5),
    }
    delta = sum((weights[key][0] if is_correct else weights[key][1]) for key, is_correct in results.items() if key in weights)
    return await add_rating_points(telegram_id, delta)


async def get_rating_settings(telegram_id: int) -> UserRatingModel | None:
    user = await get_user_by_telegram_id(telegram_id)
    return user.rating if user else None


async def toggle_rating_participation(telegram_id: int) -> None:
    async with database.session() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        if not user:
            return
        await _ensure_user_satellites(session, user)
        user.rating.show_in_rating = 0 if user.rating.show_in_rating else 1
        await session.commit()


async def toggle_rating_display_as(telegram_id: int) -> None:
    async with database.session() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        if not user:
            return
        await _ensure_user_satellites(session, user)
        user.rating.display_as = 0 if user.rating.display_as else 1
        await session.commit()


def _format_rating_name(user: UserModel) -> str:
    display_name = user.username or f"Пользователь {user.telegram_id}"
    if user.rating.display_as == 0:
        return f'<a href="tg://user?id={user.telegram_id}">{escape(display_name)}</a>'
    return escape(display_name)


async def get_leaderboards(limit: int = 5, telegram_id: int | None = None) -> dict[str, object]:
    async with database.session() as session:
        now = datetime.utcnow()
        await session.execute(
            update(UserRatingModel)
            .where((UserRatingModel.rating_year != now.year) | (UserRatingModel.rating_month != now.month))
            .values(monthly_points=0, rating_year=now.year, rating_month=now.month)
        )
        points_stmt = (
            select(UserModel)
            .join(UserRatingModel, UserModel.rating_id == UserRatingModel.id)
            .where(UserRatingModel.show_in_rating == 1)
            .order_by(desc(UserRatingModel.monthly_points), UserModel.id)
        )
        streak_stmt = (
            select(UserModel)
            .join(UserRatingModel, UserModel.rating_id == UserRatingModel.id)
            .join(UserStreakModel, UserModel.streak_id == UserStreakModel.id)
            .where(UserRatingModel.show_in_rating == 1)
            .order_by(desc(UserStreakModel.streak_days), UserModel.id)
        )
        all_point_users = list((await session.execute(points_stmt)).scalars().all())
        all_streak_users = list((await session.execute(streak_stmt)).scalars().all())
        for user in all_point_users + all_streak_users:
            await _ensure_user_satellites(session, user)
            await _reset_rating_if_needed(session, user.rating)
        all_point_users.sort(key=lambda u: (u.rating.monthly_points, -u.id), reverse=True)
        all_streak_users.sort(key=lambda u: (u.streak.streak_days, -u.id), reverse=True)

        points_place = None
        streak_place = None
        if telegram_id is not None:
            for idx, user in enumerate(all_point_users, 1):
                if user.telegram_id == telegram_id:
                    points_place = idx
                    break
            for idx, user in enumerate(all_streak_users, 1):
                if user.telegram_id == telegram_id:
                    streak_place = idx
                    break

        return {
            "points": [(_format_rating_name(user), round(user.rating.monthly_points or 0, 2)) for user in all_point_users[:limit]],
            "streaks": [(_format_rating_name(user), user.streak.streak_days or 0) for user in all_streak_users[:limit]],
            "points_place": points_place,
            "streak_place": streak_place,
            "participants_count": len(all_point_users),
        }


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


async def get_person_categories() -> List[Dict]:
    async with database.session() as session:
        result = await session.execute(select(CategoryModel.id, CategoryModel.name).order_by(CategoryModel.name))
        return [{"id": id_, "name": name} for id_, name in result.all()]


async def get_personality_pairs(category_id: int | None = None, limit: int = 5) -> List[Dict]:
    conditions = [PersonCategoryModel.value.is_not(None), PersonCategoryModel.value != ""]
    if category_id is not None:
        conditions.append(PersonCategoryModel.category_id == category_id)

    async with database.session() as session:
        stmt = (
            select(
                PersonModel.id,
                PersonModel.person_name,
                PersonCategoryModel.value,
                CategoryModel.name.label("category_name"),
            )
            .join(PersonCategoryModel, PersonCategoryModel.person_id == PersonModel.id)
            .join(CategoryModel, CategoryModel.id == PersonCategoryModel.category_id)
            .where(and_(*conditions))
            .order_by(func.rand())
        )
        rows = (await session.execute(stmt)).all()

    pairs = []
    used_persons = set()
    used_values = set()
    for person_id, person_name, value, category_name in rows:
        value = str(value)
        if person_id in used_persons or value in used_values:
            continue
        pairs.append({
            "person_id": person_id,
            "person_name": str(person_name),
            "value": value,
            "category_name": str(category_name),
        })
        used_persons.add(person_id)
        used_values.add(value)
        if len(pairs) >= limit:
            break
    return pairs
