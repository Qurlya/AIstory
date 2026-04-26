from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden
import logging
from assets import getMainMenu, getTrainingOptionalMenu, main_menu_keybord, culture_choose_menu
from assets.Menu import back_menu_keyboard, get_choose_train, subscribe_keyboard, noth_keyboard
from constants import MAIN_MENU, TRAINING
from handles.db_handles import add_user, get_user_by_telegram_id, get_all_users
import asyncio
import random
import pytz

moscow_tz = pytz.timezone("Europe/Moscow")
logger = logging.getLogger(__name__)

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


async def send_daily_streak_reminder(context):
    bot = context.bot
    users = await get_all_users()

    for user in users:
        try:
            last_activity = user.last_activity
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=moscow_tz)
            last_activity = last_activity.astimezone(moscow_tz).date()

            text = get_streak_message(user.streak_days)

            logger.info(
                "[STREAK] Отправляю %s - стрик %s, last_activity %s",
                user.telegram_id,
                user.streak_days,
                last_activity,
            )

            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(noth_keyboard)
            )

            logger.info("[STREAK] Сообщение успешно отправлено %s", user.telegram_id)

        except Forbidden:
            logger.warning("[STREAK] Пользователь %s заблокировал бота", user.telegram_id)
        except Exception:
            logger.exception("[STREAK] Ошибка отправки %s", user.telegram_id)

    return MAIN_MENU


async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id

    try:
        chat_member = await context.bot.get_chat_member(
            chat_id="-1003732977673",
            user_id=user_id,
        )

        subscribed_statuses = ['member', 'administrator', 'creator']

        return chat_member.status in subscribed_statuses

    except Exception as e:
        print(f"Ошибка при проверке подписки: {e}")
        return False


async def notify_maintenance(application):

    users = await get_all_users()

    for user in users:
        try:
            await application.bot.send_message(
                chat_id=user.telegram_id,   # ✅ правильно
                text=(
                    "⚙️ Бот был перезапущен после технического обслуживания.\n\n"
                    "Пожалуйста, нажмите /start чтобы продолжить работу."
                )
            )

            await asyncio.sleep(0.05)  # защита от flood limit

        except Forbidden:
            logger.warning("Пользователь %s заблокировал бота", user.telegram_id)

        except Exception:
            logger.exception("Не удалось отправить уведомление пользователю %s", user.telegram_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start с проверкой подписки"""

    if "user" not in context.user_data:
        user = update.effective_user
        telegram_id = user.id
        db_user = await add_user(telegram_id)
        context.user_data["user"] = db_user

    reply_markup = InlineKeyboardMarkup(main_menu_keybord)
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

    if "user" not in context.user_data:
        user = update.effective_user
        telegram_id = user.id
        db_user = await add_user(telegram_id)
        context.user_data["user"] = db_user

    reply_markup = InlineKeyboardMarkup(main_menu_keybord)

    await query.edit_message_text(
        getMainMenu(),
        reply_markup=reply_markup
    )
    return MAIN_MENU


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if "user" not in context.user_data:
        user = update.effective_user
        telegram_id = user.id
        db_user = await add_user(telegram_id)
        context.user_data["user"] = db_user

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
        reply_markup = InlineKeyboardMarkup(main_menu_keybord)
        await query.edit_message_text(
            getMainMenu(),
            reply_markup=reply_markup
        )
    
    elif query.data == 'streak':
        user = update.effective_user
        telegram_id = user.id

        this_user = await get_user_by_telegram_id(telegram_id)

        message = get_streak_message(this_user.streak_days)

        reply_markup = InlineKeyboardMarkup(back_menu_keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

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

    return MAIN_MENU
