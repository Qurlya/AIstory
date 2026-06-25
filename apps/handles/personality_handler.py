import random
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from assets import getMainMenu, get_main_menu_keyboard
from constants import MAIN_MENU, START_TEST, TRAINING
from handles.db_handles import (
    apply_chronology_rating_points,
    format_rating_delta,
    get_person_categories,
    get_personality_pairs,
    increment_field,
    update_streak,
)

PERSONALITY_CATEGORY_ANY = -1


def _session(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    return context.user_data.setdefault("personality_session", {})


async def show_personality_format_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🎯 Тренировка", callback_data="personality_training")],
        [InlineKeyboardButton("⚡ Интенсив", callback_data="personality_intensive")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")],
    ]
    await query.edit_message_text(
        "👤 Личности\n\nВыберите формат:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TRAINING


async def show_personality_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str | None = None):
    query = update.callback_query
    await query.answer()
    if mode:
        context.user_data["personality_mode"] = mode

    categories = await get_person_categories()
    keyboard = [[InlineKeyboardButton("Любая", callback_data=f"personality_category_{PERSONALITY_CATEGORY_ANY}")]]
    keyboard.extend(
        [InlineKeyboardButton(category["name"], callback_data=f"personality_category_{category['id']}")]
        for category in categories
    )
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="personality")])

    await query.edit_message_text(
        "👤 Личности\n\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TRAINING


async def start_personality_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int):
    query = update.callback_query
    await query.answer()

    mode = context.user_data.get("personality_mode", "training")
    category_filter = None if category_id == PERSONALITY_CATEGORY_ANY else category_id
    pairs = await get_personality_pairs(category_filter, limit=5)

    if len(pairs) < 5:
        await query.edit_message_text(
            "❌ Недостаточно уникальных личностей и значений для режима «Личности».",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 Главное меню", callback_data="back_main")]]),
        )
        return MAIN_MENU

    values = [pair["value"] for pair in pairs]
    random.shuffle(values)
    context.user_data["personality_session"] = {
        "active": True,
        "mode": mode,
        "round": 1,
        "pairs_source": pairs,
        "pairs": pairs,
        "values": values,
        "matches": {},
        "selected_person": None,
        "used_values": set(),
        "category_id": category_id,
        "rating_delta": 0,
    }
    await render_personality(update, context)
    return START_TEST


async def render_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    session = _session(context)
    if not session.get("active"):
        return

    pairs = session["pairs"]
    values = session["values"]
    matches = session["matches"]
    selected = session.get("selected_person")
    used_values = session.get("used_values", set())

    keyboard = []
    for i, pair in enumerate(pairs):
        marker = "🟡 " if i == selected else "🔗 " if i in matches else ""
        keyboard.append([InlineKeyboardButton(f"{marker}{pair['person_name']}", callback_data=f"personality_person_{i}")])
    for i, _ in enumerate(values):
        marker = "🔒 " if i in used_values else ""
        keyboard.append([InlineKeyboardButton(f"{marker}{i + 1}", callback_data=f"personality_value_{i}")])

    keyboard.extend([
        [InlineKeyboardButton("✅ Проверить", callback_data="personality_check")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="personality_cancel")],
    ])

    value_lines = [f"{i + 1}. {value}" for i, value in enumerate(values)]
    selected_line = ""
    if selected is not None:
        selected_line = f"\nВыбрана личность: {pairs[selected]['person_name']}\n"
    text = (
        "👤 Личности: сопоставьте личность и факт\n\n"
        "Факты:\n" + "\n".join(value_lines) + "\n"
        f"{selected_line}\n"
        "Сначала нажмите плашку с личностью, затем цифровую плашку факта."
    )
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


async def personality_dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "personality":
        return await show_personality_format_menu(update, context)
    if data == "personality_training":
        return await show_personality_categories(update, context, "training")
    if data == "personality_intensive":
        return await show_personality_categories(update, context, "intensive")
    if data.startswith("personality_category_"):
        return await start_personality_mode(update, context, int(data.rsplit("_", 1)[1]))
    if data == "personality_retry":
        category_id = _session(context).get("category_id", PERSONALITY_CATEGORY_ANY)
        return await start_personality_mode(update, context, category_id)
    if data == "personality_continue_intensive":
        return await _continue_personality_intensive(update, context)
    if data == "personality_cancel":
        context.user_data.pop("personality_session", None)
        await query.answer()
        from handles.start_menu import get_admin_telegram_ids
        await query.edit_message_text(
            getMainMenu(),
            reply_markup=InlineKeyboardMarkup(get_main_menu_keyboard(update.effective_user.id in get_admin_telegram_ids())),
        )
        return MAIN_MENU

    await query.answer()
    session = _session(context)
    if not session.get("active"):
        await query.answer("⚠️ Сессия завершена. Начните заново.", show_alert=True)
        return START_TEST

    if data.startswith("personality_person_"):
        session["selected_person"] = int(data.rsplit("_", 1)[1])
    elif data.startswith("personality_value_"):
        value_index = int(data.rsplit("_", 1)[1])
        selected_person = session.get("selected_person")
        if selected_person is None:
            return START_TEST
        if value_index in session["used_values"]:
            await query.answer("⚠️ Это значение уже использовано", show_alert=True)
            return START_TEST
        if selected_person in session["matches"]:
            session["used_values"].discard(session["matches"][selected_person])
        session["matches"][selected_person] = value_index
        session["used_values"].add(value_index)
        session["selected_person"] = None
    elif data == "personality_check":
        return await _check_personality(update, context)

    await render_personality(update, context)
    return START_TEST


async def _check_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    session = _session(context)
    if len(session.get("matches", {})) < len(session.get("pairs", [])):
        await query.answer("⚠️ Сопоставьте все пары!", show_alert=True)
        return START_TEST

    correct = 0
    wrong_pairs = []
    result_lines = []
    for person_index, value_index in session["matches"].items():
        pair = session["pairs"][person_index]
        selected_value = session["values"][value_index]
        ok = selected_value == pair["value"]
        correct += int(ok)
        if not ok:
            wrong_pairs.append(pair)
        result_lines.append(("✅" if ok else "❌") + f" {pair['person_name']} — {selected_value}" + ("" if ok else f"\n   Правильно: {pair['value']}"))

    total = len(session["pairs"])
    rating_delta = await apply_chronology_rating_points(update.effective_user.id, correct, total)
    await increment_field(update.effective_user.id, "personality_completed_cards", total)
    await increment_field(update.effective_user.id, "personality_true_cards", correct)
    if correct == total:
        await increment_field(update.effective_user.id, "personality_completed_full", 1)
        await update_streak(update.effective_user.id)

    keyboard = []
    if session["mode"] == "intensive" and wrong_pairs:
        session["wrong_pairs"] = wrong_pairs
        keyboard.append([InlineKeyboardButton("➡️ Продолжить интенсив", callback_data="personality_continue_intensive")])
    else:
        if session["mode"] == "intensive":
            keyboard.append([InlineKeyboardButton("👤 Выбрать категорию", callback_data="personality_intensive")])
        else:
            keyboard.append([InlineKeyboardButton("🔁 Попробовать снова", callback_data="personality_retry")])
    keyboard.append([InlineKeyboardButton("📊 Главное меню", callback_data="back_main")])

    intensive_note = ""
    if session["mode"] == "intensive":
        intensive_note = (
            "\n\n❌ Нажмите «Продолжить интенсив», чтобы повторить только ошибки."
            if wrong_pairs
            else "\n\n🎉 Интенсив завершён: все карточки решены правильно."
        )

    text = (
        f"📊 Результат режима «Личности»\n\n"
        f"Правильно: {correct}/{total}\n"
        f"Процент: {(correct / total * 100):.1f}%\n"
        f"{format_rating_delta(rating_delta)}\n"
        f"{intensive_note}\n\n" + "\n\n".join(result_lines)
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    if not (session["mode"] == "intensive" and wrong_pairs):
        context.user_data.pop("personality_session", None)
    return START_TEST


async def _continue_personality_intensive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session = _session(context)
    wrong_pairs = session.get("wrong_pairs", [])
    if not wrong_pairs:
        await query.answer("Ошибок для повторения нет", show_alert=True)
        return START_TEST
    values = [pair["value"] for pair in wrong_pairs]
    random.shuffle(values)
    session.update({
        "active": True,
        "pairs": wrong_pairs,
        "values": values,
        "matches": {},
        "selected_person": None,
        "used_values": set(),
        "wrong_pairs": [],
        "round": session.get("round", 1) + 1,
    })
    await render_personality(update, context)
    return START_TEST
