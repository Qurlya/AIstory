from utils.subscription_check import check_subscription
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden
import logging
import os
from assets import (
    getMainMenu,
    getTrainingOptionalMenu,
    main_menu_keybord,
    culture_choose_menu,
    get_ads_text,
    get_streak_extinguished_text,
    get_streak_warning_text,
)
from assets.Menu import back_menu_keyboard, get_choose_train, subscribe_keyboard, noth_keyboard
from constants import MAIN_MENU, TRAINING
from handles.db_handles import (
    add_user,
    get_user_by_telegram_id,
    get_all_users,
    register_ad_click,
    get_ads_stats,
    update_streak,
    get_leaderboards,
    toggle_rating_display_as,
    toggle_rating_participation,
)
from handles.db_handles import get_streak_state_by_last_activity
import asyncio
import random
import pytz

moscow_tz = pytz.timezone("Europe/Moscow")
logger = logging.getLogger(__name__)

def get_admin_telegram_ids() -> set[int]:
    return {
        int(x.strip()) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip().isdigit()
    }


def get_main_keyboard_for_user(telegram_id: int):
    from assets.Menu import get_main_menu_keyboard
    return get_main_menu_keyboard(telegram_id in get_admin_telegram_ids())

SPECIAL_STREAK_MESSAGES = {
    1: "🎉 И ты начал! Первый день — самый важный. Ждём тебя завтра!",
    3: "📈 Уже 3 дня! Первая привычка формируется. Ты на верном пути!",
    7: "🏆 Целая неделя исторического стрика! Ты вошёл в ритм. Не сбавляй!",
    14: "✨ Две недели без перерыва! Твой прогресс уже заметен самому себе.",
    30: "🗓️ Месяц регулярных занятий! Ты — пример исторической дисциплины. Настоящий архивариус!",
    100: "🏛️ СТО ДНЕЙ! Твой стрик догнал Наполеона. Но твоя империя знаний только крепнет!",
}

DEFAULT_STREAK_MESSAGES = [
    "🔥 Полыхает! Огненная серия из {day} дней.",
    "📚 Цепочка знаний крепнет: {day} день подряд!",
    "⏳ Ты не пропускаешь уже {day} дней. Системность — ключ!",
    "✨ {day}-й день твоего исторического рывка. Завтра будет легче!",
    "🧠 Твой мозг благодарен за {day} дней регулярной тренировки.",
    "🗺️ Ты открываешь новые земли знаний уже {day} дней.",
    "📜 {day} дней летописи твоих побед. Внеси ещё одну запись завтра!",
    "👑 Ровно {day} дней. Этого хватило, чтобы свергнуть не одного короля.",
    "🏛️ Твоя {day}-дневная дисциплина достойна легионера!",
    "⚔️ {day} дней подряд. Примерно столько длилась Столетняя война... если верить названию.",
]

MOTIVATIONAL_MESSAGES = [
    "💪 Сегодня твой день! Начни хоть с одной карточки — и стрик пойдёт.",
    "🚀 Каждый большой путь начинается с маленького шага. Сделай его сегодня!",
    "🌟 Не откладывай на завтра то, что может сделать твой прогресс сегодня.",
    "📚 Каждая минута тренировок приближает тебя к цели. Давай начнём!",
]

def get_streak_message(days: int) -> str:
    if days > 0:
        if days in SPECIAL_STREAK_MESSAGES:
            return SPECIAL_STREAK_MESSAGES[days]
        return random.choice(DEFAULT_STREAK_MESSAGES).format(day=days)
    else:
        return random.choice(MOTIVATIONAL_MESSAGES)


EXTINGUISHED_MESSAGES = [
    "❄️ Твой исторический огонёк полностью погас (🔥 0 дней). Ты давно не занимался, самое время начать заново!",
    "💨 Ветер времени задул твой стрик (🔥 0 дней). Возвращайся к тренировкам, чтобы разжечь его вновь!",
    "🧊 Увы, твой стрик прервался и обнулился. Но Рим тоже не за один день строился, начни новую серию!"
]

WARNING_MESSAGES = [
    "⚠️ Внимание! Твой огонёк (🔥 {day} дней) может погаснуть! Заходи на тренировку, чтобы поддержать его сегодня.",
    "⏳ Твоя серия составляет 🔥 {day} дней. Вчера ты был молодец, но сегодня ещё не занимался. Не теряй прогресс!",
    "🔥 Твой стрик — {day} дней. Чтобы он не сгорел дотла, нужно пройти хотя бы один тест сегодня!"
]

BURNING_MESSAGES = [
    "✨ Твой огонёк ярко горит! Серия: 🔥 {day} дней. Сегодня ты уже позанимался, не забудь вернуться завтра!",
    "🛡️ Отличная работа! Сегодняшняя норма выполнена, стрик защищён (🔥 {day} дней). Жду тебя завтра!",
    "🏆 Ты на коне! Стрик составляет 🔥 {day} дней. Главное — не сбавлять темп завтра."
]

from datetime import datetime
async def send_daily_streak_reminder(context):
    bot = context.bot
    users = await get_all_users()

    today = datetime.now(moscow_tz).date()

    for user in users:
        try:
            await update_streak(user.telegram_id, reset_if_missed=True)

            user = await get_user_by_telegram_id(user.telegram_id)
            if not user:
                continue

            last_activity = user.last_activity
            if last_activity:
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=moscow_tz)
                last_activity = last_activity.astimezone(moscow_tz).date()

            delta_days = (today - last_activity).days if last_activity else None
            streak_days = user.streak_days

            if delta_days is None or delta_days >= 2:
                text = random.choice(EXTINGUISHED_MESSAGES)

            elif delta_days == 1:
                text = random.choice(WARNING_MESSAGES).format(day=streak_days)

            else:
                text = random.choice(BURNING_MESSAGES).format(day=streak_days)

            logger.info(
                "[STREAK] Отправляю %s - стрик %s, last_activity %s",
                user.telegram_id,
                streak_days,
                last_activity,
            )

            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(noth_keyboard)
            )

            await asyncio.sleep(0.05)

            logger.info("[STREAK] Сообщение успешно отправлено %s", user.telegram_id)

        except Forbidden:
            logger.warning("[STREAK] Пользователь %s заблокировал бота", user.telegram_id)
        except Exception:
            logger.exception("[STREAK] Ошибка отправки %s", user.telegram_id)

    return MAIN_MENU

async def notify_maintenance(application):
    is_notify_enabled = os.getenv("ENABLE_MAINTENANCE_NOTIFY", "False").lower() == "true"

    if not is_notify_enabled:
        return

    users = await get_all_users()

    for user in users:
        try:
            await application.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    "⚙️ Бот был перезапущен после технического обслуживания.\n\n"
                    "Пожалуйста, нажмите /start чтобы продолжить работу."
                )
            )

            await asyncio.sleep(0.05)

        except Forbidden:
            logger.warning("Пользователь %s заблокировал бота", user.telegram_id)

        except Exception:
            logger.exception("Не удалось отправить уведомление пользователю %s", user.telegram_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start с проверкой подписки"""
    is_subscribed = await check_subscription(update, context)

    if not is_subscribed:
        await update.message.reply_text(
            "🚫 Для использования бота необходимо подписаться на наш канал!\n\n"
            "🔔 После подписки нажмите кнопку 'Я подписался'",
            reply_markup=InlineKeyboardMarkup(subscribe_keyboard)
        )
        return MAIN_MENU

    telegram_id = update.effective_user.id
    if "user" not in context.user_data:
        db_user = await add_user(telegram_id, update.effective_user.full_name)
        context.user_data["user"] = db_user

    reply_markup = InlineKeyboardMarkup(get_main_keyboard_for_user(telegram_id))
    await update.message.reply_text(getMainMenu(), reply_markup=reply_markup)
    return MAIN_MENU


get_message_train_type = {
    "training": "тренировки 🎯",
    "marathon": "марафона 🏃",
    "intensive": "интенсива ⚡️"

}


async def check_subscription_after_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверяет подписку после нажатия кнопки"""
    query = update.callback_query
    await query.answer()


    is_subscribed = await check_subscription(update, context)

    if not is_subscribed:

        reply_markup = InlineKeyboardMarkup(subscribe_keyboard)

        try:
            await query.edit_message_text(
                "❌ Подписка не найдена!\n\n"
                "Пожалуйста, подпишитесь на канал и нажмите кнопку снова.\n"
                "🔄 Попробуйте ещё раз",
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                await query.message.reply_text(
                    "❌ Подписка всё ещё не найдена!\n\n"
                    "Пожалуйста, подпишитесь на канал и нажмите кнопку снова.",
                    reply_markup=reply_markup
                )
            else:
                raise e

        return MAIN_MENU

    if "user" not in context.user_data:
        user = update.effective_user
        telegram_id = user.id
        db_user = await add_user(telegram_id, update.effective_user.full_name)
        context.user_data["user"] = db_user

    telegram_id = update.effective_user.id
    reply_markup = InlineKeyboardMarkup(get_main_keyboard_for_user(telegram_id))

    await query.edit_message_text(
        getMainMenu(),
        reply_markup=reply_markup
    )
    return MAIN_MENU


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    
    is_subscribed = await check_subscription(update, context)
    
    if not is_subscribed:
        await query.message.reply_text(
            "🚫 Для использования бота необходимо подписаться на наш канал!\n\n"
            "🔔 После подписки нажмите кнопку 'Я подписался'",
            reply_markup=InlineKeyboardMarkup(subscribe_keyboard)
        )
        return MAIN_MENU

    if "user" not in context.user_data:
        telegram_id = user.id
        db_user = await add_user(telegram_id, update.effective_user.full_name)
        context.user_data["user"] = db_user

    telegram_id = user.id
    await update_streak(telegram_id, reset_if_missed=True)

    if query.data in ['training', 'marathon', 'intensive']:
        reply_markup = InlineKeyboardMarkup(get_choose_train(query.data == 'training'))

        await query.edit_message_text(
            getTrainingOptionalMenu(query.data),
            reply_markup=reply_markup
        )
        context.user_data['train_type'] = query.data
        return TRAINING

    elif query.data == 'culture':
        reply_markup = InlineKeyboardMarkup(culture_choose_menu)
        await query.edit_message_text(
            getTrainingOptionalMenu('culture'),
            reply_markup=reply_markup
        )
        context.user_data['train_type'] = 'culture'
        return TRAINING

    elif query.data == 'back_main':
        telegram_id = update.effective_user.id
        reply_markup = InlineKeyboardMarkup(get_main_keyboard_for_user(telegram_id))
        await query.edit_message_text(
            getMainMenu(),
            reply_markup=reply_markup
        )
    
    elif query.data == 'streak':
        user = update.effective_user
        telegram_id = user.id

        this_user = await get_user_by_telegram_id(telegram_id)
        if not this_user:
            reply_markup = InlineKeyboardMarkup(back_menu_keyboard)
            await query.edit_message_text("Не удалось найти данные по стрику.", reply_markup=reply_markup)
            return MAIN_MENU

        streak_state = get_streak_state_by_last_activity(this_user.last_activity)

        if streak_state == "older":
            message = get_streak_extinguished_text()
        elif streak_state == "yesterday":
            message = f"{get_streak_message(this_user.streak_days)}\n\n{get_streak_warning_text()}"
        else:
            message = "Твой огонёк горит 🔥"

        reply_markup = InlineKeyboardMarkup(back_menu_keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    elif query.data in ('rating', 'rating_toggle_participation', 'rating_toggle_display'):
        telegram_id = update.effective_user.id
        if query.data == 'rating_toggle_participation':
            await toggle_rating_participation(telegram_id)
        elif query.data == 'rating_toggle_display':
            await toggle_rating_display_as(telegram_id)

        user = await get_user_by_telegram_id(telegram_id)
        boards = await get_leaderboards(limit=5, telegram_id=telegram_id)
        points = boards['points']
        streaks = boards['streaks']

        def render_rows(rows, suffix):
            if not rows:
                return "Пока никто не участвует."
            return "\n".join(f"{idx}. {name} — {value:g} {suffix}" for idx, (name, value) in enumerate(rows, 1))

        points_place = boards.get('points_place')
        streak_place = boards.get('streak_place')
        points_place_text = f"{points_place} место" if points_place else "вы не участвуете"
        streak_place_text = f"{streak_place} место" if streak_place else "вы не участвуете"
        participation = "✅ Участвую в рейтинге" if user.rating.show_in_rating else "🚫 Не участвую в рейтинге"
        display = "🔗 Имя кликабельное" if user.rating.display_as == 0 else "👤 Имя без ссылки"
        message = (
            "🏆 Рейтинг\n\n"
            "📅 Ежемесячный рейтинг по очкам (топ-5):\n"
            f"{render_rows(points, 'оч.')}\n\n"
            "🔥 Рейтинг по стрикам (топ-5):\n"
            f"{render_rows(streaks, 'дн.')}\n\n"
            f"Ваши очки в текущем месяце: {user.rating.monthly_points:g}\n"
            f"Ваше место по очкам: {points_place_text}\n"
            f"Ваш стрик: {user.streak_days} дней\n"
            f"Ваше место по стрику: {streak_place_text}\n\n"
            "Очки месяца не опускаются ниже 0 и сбрасываются при наступлении нового календарного месяца."
        )
        keyboard = [
            [InlineKeyboardButton(participation, callback_data='rating_toggle_participation')],
            [InlineKeyboardButton(display, callback_data='rating_toggle_display')],
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_main')],
        ]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif query.data == 'stats':
        user = update.effective_user
        telegram_id = user.id

        user = await get_user_by_telegram_id(telegram_id)

        if not user:
            await query.edit_message_text(
                "📊 У вас пока нет статистики.\n\nПройдите первый тест!"
            )
            return MAIN_MENU

        training_total = user.training_completed_cards
        training_correct = user.training_true_cards
        training_percent = (training_correct / training_total * 100) if training_total > 0 else 0

        intensive_total = user.intensive_completed_cards
        intensive_correct = user.intensive_true_cards
        intensive_percent = (intensive_correct / intensive_total * 100) if intensive_total > 0 else 0

        marathon_total = user.marathon_completed_cards
        marathon_correct = user.marathon_true_cards
        marathon_percent = (marathon_correct / marathon_total * 100) if marathon_total > 0 else 0

        week_training_total = user.week_training_completed_cards
        week_training_correct = user.week_training_true_cards
        week_training_percent = (week_training_correct / week_training_total * 100) if week_training_total > 0 else 0

        week_intensive_total = user.week_intensive_completed_cards
        week_intensive_correct = user.week_intensive_true_cards
        week_intensive_percent = (
                week_intensive_correct / week_intensive_total * 100) if week_intensive_total > 0 else 0

        week_marathon_total = user.week_marathon_completed_cards
        week_marathon_correct = user.week_marathon_true_cards
        week_marathon_percent = (week_marathon_correct / week_marathon_total * 100) if week_marathon_total > 0 else 0

        culture_total = user.culture_completed_cards
        culture_correct = user.culture_true_cards
        culture_percent = (culture_correct / culture_total * 100) if culture_total > 0 else 0

        week_culture_total = user.week_culture_completed_cards
        week_culture_correct = user.week_culture_true_cards
        week_culture_percent = (week_culture_correct / week_culture_total * 100) if week_culture_total > 0 else 0

        # Формируем сообщение
        message = (
            f"📊 Ваша статистика\n\n"
            f"📈 Общая статистика:\n"
            f"🎯 Тренировка:\n"
            f"   • Карточки: {training_correct}/{training_total} ({training_percent:.1f}%)\n"
            f"   • Полностью пройдено: {user.training_completed_full}\n"
            f"⚡ Интенсив:\n"
            f"   • Карточки: {intensive_correct}/{intensive_total} ({intensive_percent:.1f}%)\n"
            f"   • Полностью пройдено: {user.intensive_completed_full}\n"
            f"🏃 Марафон:\n"
            f"   • Карточки: {marathon_correct}/{marathon_total} ({marathon_percent:.1f}%)\n"
            f"   • Полностью пройдено: {user.marathon_completed_full}\n"
            f"🏛 Архитектура:\n"
            f"   • Карточки: {culture_correct}/{culture_total} ({culture_percent:.1f}%)\n"
            f"   • Полностью пройдено: {user.culture_completed_full}\n\n"
            f"📅 За текущую неделю:\n"
            f"🎯 Тренировка:\n"
            f"   • Карточки: {week_training_correct}/{week_training_total} ({week_training_percent:.1f}%)\n"
            f"   • Полностью пройдено: {user.week_training_completed_full}\n"
            f"⚡ Интенсив:\n"
            f"   • Карточки: {week_intensive_correct}/{week_intensive_total} ({week_intensive_percent:.1f}%)\n"
            f"   • Полностью пройдено: {user.week_intensive_completed_full}\n"
            f"🏃 Марафон:\n"
            f"   • Карточки: {week_marathon_correct}/{week_marathon_total} ({week_marathon_percent:.1f}%)\n"
            f"   • Полностью пройдено: {user.week_marathon_completed_full}\n"
            f"🏛 Архитектура:\n"
            f"   • Карточки: {week_culture_correct}/{week_culture_total} ({week_culture_percent:.1f}%)\n"
            f"   • Полностью пройдено: {user.week_culture_completed_full}\n\n"
            f"🔥 Текущая серия: {user.streak_days} дней"
        )

        reply_markup = InlineKeyboardMarkup(back_menu_keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    elif query.data == 'ads':
        telegram_id = update.effective_user.id
        await register_ad_click(telegram_id)
        reply_markup = InlineKeyboardMarkup(back_menu_keyboard)
        await query.edit_message_text(get_ads_text(), reply_markup=reply_markup)

    elif query.data == 'admin':
        telegram_id = update.effective_user.id
        if telegram_id not in get_admin_telegram_ids():
            reply_markup = InlineKeyboardMarkup(back_menu_keyboard)
            await query.edit_message_text("У вас нет доступа к администрированию.", reply_markup=reply_markup)
            return MAIN_MENU

        stats = await get_ads_stats()
        message = (
            "🛠 Статистика по кнопке «Реклама»\n\n"
            f"📊 Общая:\n"
            f"• Всего нажатий: {stats['total']}\n"
            f"• Уникальных пользователей: {stats['unique_total']}\n\n"
            f"📅 За неделю:\n"
            f"• Нажатий: {stats['week']}\n"
            f"• Уникальных пользователей: {stats['unique_week']}\n\n"
            f"🗓 За месяц:\n"
            f"• Нажатий: {stats['month']}\n"
            f"• Уникальных пользователей: {stats['unique_month']}"
        )
        reply_markup = InlineKeyboardMarkup(back_menu_keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    return MAIN_MENU
