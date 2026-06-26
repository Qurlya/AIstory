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
    get_personality_distractor_values,
    get_personality_pairs,
    increment_field,
    update_streak,
)

PERSONALITY_CATEGORY_ANY = -1
PERSONALITY_MATCHES_PER_TEST = 4
PERSONALITY_DISTRACTORS_PER_TEST = 2
PERSONALITY_INTENSIVE_TESTS = 7
PERSONALITY_LONG_FACT_LIMIT = 20


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


async def _resolve_personality_category(category_id: int) -> int | None:
    if category_id != PERSONALITY_CATEGORY_ANY:
        return category_id

    categories = await get_person_categories()
    random.shuffle(categories)
    for category in categories:
        pairs = await get_personality_pairs(category["id"], limit=PERSONALITY_MATCHES_PER_TEST)
        if len(pairs) >= PERSONALITY_MATCHES_PER_TEST:
            return category["id"]
    return None


async def _build_personality_test(category_id: int, pairs: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    category_filter = pairs[0].get("category_id") if pairs else await _resolve_personality_category(category_id)
    if category_filter is None:
        return None
    pairs = pairs or await get_personality_pairs(category_filter, limit=PERSONALITY_MATCHES_PER_TEST)
    if len(pairs) < PERSONALITY_MATCHES_PER_TEST:
        return None

    correct_values = [pair["value"] for pair in pairs]
    distractors = await get_personality_distractor_values(
        category_filter,
        exclude_values=correct_values,
        limit=PERSONALITY_DISTRACTORS_PER_TEST,
    )
    values = correct_values + distractors
    random.shuffle(values)
    return {"pairs": pairs, "values": values, "category_id": category_filter}


async def _start_current_personality_test(update: Update, context: ContextTypes.DEFAULT_TYPE, test_data: dict[str, Any]):
    session = _session(context)
    session.update({
        "active": True,
        "pairs": test_data["pairs"],
        "values": test_data["values"],
        "current_category_id": test_data.get("category_id"),
        "matches": {},
        "selected_person": None,
        "used_values": set(),
    })
    await render_personality(update, context)
    return START_TEST


async def start_personality_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int):
    query = update.callback_query
    await query.answer()

    mode = context.user_data.get("personality_mode", "training")
    first_test = await _build_personality_test(category_id)

    if first_test is None:
        await query.edit_message_text(
            "❌ Недостаточно уникальных личностей и значений для режима «Личности».",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 Главное меню", callback_data="back_main")]]),
        )
        return MAIN_MENU

    context.user_data["personality_session"] = {
        "active": True,
        "mode": mode,
        "category_id": category_id,
        "test_number": 1,
        "tests_total": PERSONALITY_INTENSIVE_TESTS if mode == "intensive" else 1,
        "intensive_wrong_tests": [],
        "rework_mode": False,
        "rating_delta": 0,
    }
    return await _start_current_personality_test(update, context, first_test)


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
    has_long_facts = any(len(value) > PERSONALITY_LONG_FACT_LIMIT for value in values)

    keyboard = []
    for i, pair in enumerate(pairs):
        marker = "🟡 " if i == selected else "🔗 " if i in matches else ""
        keyboard.append([InlineKeyboardButton(f"{marker}— {pair['person_name']}", callback_data=f"personality_person_{i}")])
    for i, value in enumerate(values):
        marker = "🔒 " if i in used_values else ""
        button_value = str(i + 1) if has_long_facts or len(value) > PERSONALITY_LONG_FACT_LIMIT else value
        keyboard.append([InlineKeyboardButton(f"{marker}{button_value}", callback_data=f"personality_value_{i}")])

    keyboard.extend([
        [InlineKeyboardButton("✅ Проверить", callback_data="personality_check")],
        [InlineKeyboardButton("⬅️ Выйти досрочно", callback_data="personality_cancel")],
    ])

    selected_line = ""
    if selected is not None:
        selected_line = f"\nВыбрана личность: {pairs[selected]['person_name']}\n"

    facts_text = ""
    if has_long_facts:
        facts_text = "\nФакты:\n" + "\n".join(f"{i + 1}. {value}" for i, value in enumerate(values)) + "\n"

    progress_text = ""
    if session.get("mode") == "intensive":
        progress_text = f"Раунд: {session.get('test_number', 1)}/{session.get('tests_total', PERSONALITY_INTENSIVE_TESTS)}\n"
        if session.get("rework_mode"):
            progress_text = "Повтор ошибок\n" + progress_text

    text = (
        "👤 Личности: сопоставьте личность и факт\n\n"
        f"{progress_text}"
        f"{facts_text}"
        f"{selected_line}\n"
        "Сначала нажмите плашку с личностью, затем плашку факта. "
        "Длинные факты вынесены в текст и выбираются по номеру."
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
            await query.answer("Сначала выберите личность", show_alert=True)
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
    pairs = session.get("pairs", [])
    if len(session.get("matches", {})) < len(pairs):
        await query.answer("⚠️ Сопоставьте все личности!", show_alert=True)
        return START_TEST

    correct = 0
    wrong_pairs = []
    result_lines = []
    for person_index, value_index in session["matches"].items():
        pair = pairs[person_index]
        selected_value = session["values"][value_index]
        ok = selected_value == pair["value"]
        correct += int(ok)
        if not ok:
            wrong_pairs.append(pair)
        result_lines.append(("✅" if ok else "❌") + f" {pair['person_name']} — {selected_value}" + ("" if ok else f"\n   Правильно: {pair['value']}"))

    total = len(pairs)
    rating_delta = await apply_chronology_rating_points(update.effective_user.id, correct, total)
    session["rating_delta"] = session.get("rating_delta", 0) + rating_delta
    await increment_field(update.effective_user.id, "personality_completed_cards", total)
    await increment_field(update.effective_user.id, "personality_true_cards", correct)
    if correct == total:
        await update_streak(update.effective_user.id)

    if session.get("mode") == "intensive":
        if correct < total:
            session.setdefault("intensive_wrong_tests", []).append({
                "pairs": [dict(pair) for pair in pairs],
                "values": list(session["values"]),
            })
        return await _after_intensive_test(update, context, correct, total, result_lines, rating_delta)

    await increment_field(update.effective_user.id, "personality_completed_full", 1)
    keyboard = [
        [InlineKeyboardButton("🔁 Попробовать снова", callback_data="personality_retry")],
        [InlineKeyboardButton("📊 Главное меню", callback_data="back_main")],
    ]
    text = _format_result_text("📊 Результат режима «Личности»", correct, total, rating_delta, result_lines)
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data.pop("personality_session", None)
    return START_TEST


def _format_result_text(title: str, correct: int, total: int, rating_delta: float, result_lines: list[str], note: str = "") -> str:
    return (
        f"{title}\n\n"
        f"Правильно: {correct}/{total}\n"
        f"Процент: {(correct / total * 100):.1f}%\n"
        f"{format_rating_delta(rating_delta)}"
        f"{note}\n\n"
        + "\n\n".join(result_lines)
    )


async def _after_intensive_test(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    correct: int,
    total: int,
    result_lines: list[str],
    rating_delta: float,
):
    query = update.callback_query
    session = _session(context)
    test_number = session.get("test_number", 1)
    tests_total = session.get("tests_total", PERSONALITY_INTENSIVE_TESTS)
    is_rework = session.get("rework_mode", False)

    if not is_rework and test_number < tests_total:
        keyboard = [[InlineKeyboardButton("➡️ Следующее сопоставление", callback_data="personality_continue_intensive")]]
        note = f"\n\nРаунд {test_number}/{tests_total}. Дальше будет новое сопоставление."
    else:
        wrong_count = len(session.get("intensive_wrong_tests", []))
        if wrong_count:
            keyboard = [[InlineKeyboardButton("➡️ Повторить ошибки", callback_data="personality_continue_intensive")]]
            note = f"\n\nОшибочных карточек: {wrong_count}. Повторяем только их, пока всё не будет верно."
        else:
            await increment_field(update.effective_user.id, "personality_completed_full", 1)
            keyboard = [[InlineKeyboardButton("👤 Выбрать категорию", callback_data="personality_intensive")]]
            note = "\n\n🎉 Интенсив завершён: все сопоставления решены правильно."
            context.user_data.pop("personality_session", None)
    keyboard.append([InlineKeyboardButton("⬅️ Выйти досрочно", callback_data="personality_cancel")])
    text = _format_result_text("📊 Результат интенсива «Личности»", correct, total, rating_delta, result_lines, note)
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return START_TEST


async def _continue_personality_intensive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session = _session(context)

    if not session.get("rework_mode") and session.get("test_number", 1) < session.get("tests_total", PERSONALITY_INTENSIVE_TESTS):
        session["test_number"] = session.get("test_number", 1) + 1
        test_data = await _build_personality_test(session.get("category_id", PERSONALITY_CATEGORY_ANY))
        if test_data is None:
            await query.answer("Недостаточно данных для следующего сопоставления", show_alert=True)
            return START_TEST
        return await _start_current_personality_test(update, context, test_data)

    wrong_tests = session.get("intensive_wrong_tests", [])
    if not wrong_tests:
        await query.answer("Ошибок для повторения нет", show_alert=True)
        return START_TEST

    next_test = wrong_tests.pop(0)
    session.update({
        "rework_mode": True,
        "test_number": 1,
        "tests_total": max(1, len(wrong_tests) + 1),
    })
    return await _start_current_personality_test(update, context, next_test)
