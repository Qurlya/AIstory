from __future__ import annotations

from pathlib import Path
import random
from typing import Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from assets import getMainMenu, main_menu_keybord
from handles.db_handles import get_all_cultures, get_culture_answer_values, increment_field, update_streak
from constants import MAIN_MENU, START_TEST

CATEGORY_DEFS = [
    ("title", "Название строения"),
    ("architect", "Архитектор"),
    ("foundation_year", "Год основания"),
    ("ruler", "При каком правителе построено"),
    ("style", "Архитектурный стиль"),
    ("city", "Город (локация)"),
]

CATEGORY_LABELS = {key: label for key, label in CATEGORY_DEFS}
PHOTO_DIR = Path("assets/culture_photos")

def _normalize_card(raw: dict[str, Any]) -> dict[str, str]:
    return {
        "title": str(raw.get("build_name")),
        "architect": str(raw.get("author")),
        "foundation_year": str(raw.get("date")),
        "ruler": str(raw.get("king")),
        "style": str(raw.get("style")),
        "city": str(raw.get("city")),
        "type": str(raw.get("type")),
        "img_name": str(raw.get("img_name")),
    }


def _is_value_present(value: str | None) -> bool:
    return bool(value and value not in ("—", "None", ""))


def _available_categories(card: dict[str, str]) -> list[tuple[str, str]]:
    return [
        (key, label)
        for key, label in CATEGORY_DEFS
        if not (key == "architect" and not _is_value_present(card.get("architect")))
    ]

def _session(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    return context.user_data.setdefault("culture_session", {})

async def _build_answers_pool(current_card: dict[str, str], field: str, count: int = 5) -> list[str]:
    correct = current_card[field]
    options = await get_culture_answer_values(
        field_name=field,
        limit=count,
        culture_type=current_card.get("type") if field == "title" else None,
    )

    unique_options: list[str] = []
    for option in options:
        if option not in unique_options:
            unique_options.append(option)

    if correct not in unique_options:
        if len(unique_options) >= count:
            unique_options[-1] = correct
        else:
            unique_options.append(correct)

    if field == "title" and len(unique_options) < count:
        additional = await get_culture_answer_values(
            field_name=field,
            limit=count,
        )
        for value in additional:
            if value not in unique_options:
                unique_options.append(value)
            if len(unique_options) >= count:
                break

    if len(unique_options) < count:
        unique_options.extend([correct] * (count - len(unique_options)))

    options = unique_options[:count]
    if correct not in options:
        options[-1] = correct

    random.shuffle(options)
    return options

async def start_culture_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    query = update.callback_query

    if context.user_data.get("culture_starting"):
        await query.answer("⏳ Тренировка уже запускается")
        return START_TEST

    context.user_data["culture_starting"] = True
    await query.answer()

    raw_cards = await get_all_cultures()
    cards = [_normalize_card(card) for card in raw_cards]

    try:
        if not cards:
            await query.edit_message_text("❌ В базе данных нет карточек архитектуры.")
            return MAIN_MENU

        if mode == "intensive":
            cards = cards[:5]

        context.user_data["culture_session"] = {
            "mode": mode,
            "cards": cards,
            "index": 0,
            "total_passed": 0,
            "correct_count": 0,
            "incorrect_count": 0,
            "errors_by_category": {key: 0 for key, _ in CATEGORY_DEFS},
            "answers": {},
            "results": None,
            "checked": False,
            "active_category": None,
            "options_by_card": {},
            "intensive_wrong_cards": [],
            "intensive_round": 1,
        }

        await _show_culture_card(update, context, force_new_message=True)
        return START_TEST
    finally:
        context.user_data["culture_starting"] = False

async def culture_dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "culture_training":
        return await start_culture_mode(update, context, "training")
    if data == "culture_intensive":
        return await start_culture_mode(update, context, "intensive")

    if data == "culture_exit_main":
        context.user_data.pop("culture_session", None)
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=getMainMenu(),
            reply_markup=InlineKeyboardMarkup(main_menu_keybord)
        )
        return MAIN_MENU

    if data == "culture_open_categories":
        await _show_culture_card(update, context)
    elif data.startswith("culture_category_"):
        await _show_category_question(update, context, data.replace("culture_category_", ""))
    elif data.startswith("culture_pick_"):
        await _select_category_answer(update, context, int(data.replace("culture_pick_", "")))
    elif data == "culture_check":
        await _check_current_card(update, context)
    elif data == "culture_next":
        await _next_card(update, context)
    elif data == "culture_finish":
        await _show_culture_final(update, context)
    elif data == "culture_continue_intensive":
        await _continue_culture_intensive(update, context)

    return START_TEST

train_type_en_to_ru = {
    'intensive': 'интенсив',
    'training': 'тренировка',
}

async def _show_culture_card(update: Update, context: ContextTypes.DEFAULT_TYPE, force_new_message: bool = False):
    query = update.callback_query
    session = _session(context)
    card = session["cards"][session["index"]]
    categories = _available_categories(card)

    caption = (
        f"🏛 **Архитектура: {train_type_en_to_ru[session['mode']].capitalize()}**\n"
        f"Карточка №{session['index'] + 1} из {len(session['cards'])}\n\n"
        "Заполните все данные о строении на фото:"
    )

    keyboard = []
    ans = session["answers"]
    res = session["results"]
    is_checked = session["checked"]

    for key, label in categories:
        selected = ans.get(key)
        selected_value = selected.get("value") if isinstance(selected, dict) else None

        if is_checked:
            icon = "✅" if res.get(key) else "❌"
            btn_text = f"{icon} {label}"
        elif selected_value:
            btn_text = f"🟡 {selected_value}"
        else:
            btn_text = label
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"culture_category_{key}")])

    if is_checked:
        answers_lines = []
        for key, label in categories:
            selected = ans.get(key)
            selected_value = selected.get("value") if isinstance(selected, dict) else "—"
            correct_value = card.get(key, "—")
            if res.get(key):
                answers_lines.append(f"• {label}: {selected_value}")
            else:
                answers_lines.append(f"• {label}: {selected_value} ({correct_value})")
        caption += "\n\n**Ваши ответы:**\n" + "\n".join(answers_lines)

    nav_btns = []
    if len(ans) == len(categories) and not is_checked:
        nav_btns.append(InlineKeyboardButton("🔍 Проверить", callback_data="culture_check"))

    if is_checked:
        nav_btns.append(InlineKeyboardButton("➡️ Дальше", callback_data="culture_next"))

    if nav_btns: keyboard.append(nav_btns)

    keyboard.append([InlineKeyboardButton(f"🏁 Завершить {train_type_en_to_ru[session['mode']]}", callback_data="culture_finish")])
    keyboard.append([InlineKeyboardButton("📊 Главное меню", callback_data="culture_exit_main")])

    image_path = PHOTO_DIR / card["img_name"]

    if force_new_message:
        try:
            await query.message.delete()
        except:
            pass
        if image_path.exists():
            await context.bot.send_photo(update.effective_chat.id, photo=open(image_path, "rb"), caption=caption,
                                         reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await context.bot.send_message(update.effective_chat.id, text=f"⚠️ Фото не найдено\n\n{caption}",
                                           reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        try:
            await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard),
                                             parse_mode="Markdown")
        except:
            await query.edit_message_text(text=caption, reply_markup=InlineKeyboardMarkup(keyboard),
                                          parse_mode="Markdown")

async def _show_category_question(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    query = update.callback_query
    session = _session(context)
    session["active_category"] = category

    card = session["cards"][session["index"]]
    card_index = session["index"]

    options_by_card = session.setdefault("options_by_card", {})
    card_options = options_by_card.setdefault(card_index, {})

    options = card_options.get(category)
    if options is None:
        options = await _build_answers_pool(card, category)
        card_options[category] = options

    session["current_options"] = options

    options_text = "\n".join([f"{i}. {opt}" for i, opt in enumerate(options, 1)])
    text = (
        f"❓ Выберите верный вариант для категории:\n**{CATEGORY_LABELS[category]}**\n\n"
        f"{options_text}"
    )

    keyboard = []
    for i, _ in enumerate(options, 1):
        keyboard.append([InlineKeyboardButton(str(i), callback_data=f"culture_pick_{i}")])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="culture_open_categories")])

    try:
        await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(keyboard),
                                         parse_mode="Markdown")
    except:
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def _select_category_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int):
    session = _session(context)
    category = session["active_category"]
    if category and "current_options" in session:
        session["answers"][category] = {
            "index": idx,
            "value": session["current_options"][idx - 1],
        }
    await _show_culture_card(update, context)

async def _check_current_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = _session(context)
    card = session["cards"][session["index"]]
    categories = _available_categories(card)

    results = {}
    correct_all = True
    for key, _ in categories:
        selected = session["answers"].get(key)
        selected_value = selected.get("value") if isinstance(selected, dict) else None
        is_correct = selected_value == card.get(key)
        results[key] = is_correct
        if not is_correct:
            correct_all = False
            session["errors_by_category"][key] += 1

    session["results"] = results
    session["checked"] = True
    session["total_passed"] += 1
    if correct_all:
        session["correct_count"] += 1
    else:
        session["incorrect_count"] += 1
        if session.get("mode") == "intensive":
            session["intensive_wrong_cards"].append(card)

    await update_streak(telegram_id=update.effective_user.id)

    await _show_culture_card(update, context)

async def _next_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = _session(context)
    session["index"] += 1

    if session["index"] >= len(session["cards"]):
        await _show_culture_final(update, context)
        return

    session["answers"] = {}
    session["results"] = None
    session["checked"] = False
    await _show_culture_card(update, context, force_new_message=True)

async def _show_culture_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    session = _session(context)
    telegram_id = update.effective_user.id

    has_pending_intensive = session.get("mode") == "intensive" and bool(session.get("intensive_wrong_cards"))

    errors_lines = []
    for key, _ in CATEGORY_DEFS:
        errors_count = session["errors_by_category"].get(key, 0)
        errors_lines.append(f"{CATEGORY_LABELS[key]}: {errors_count}")
    errors_text = "\n".join(errors_lines)

    text = (
        "📊 **Результаты тренировки**\n\n"
        f"✅ Правильно: {session['correct_count']}\n"
        f"❌ Ошибочно: {session['incorrect_count']}\n"
        f"📚 Всего карточек: {session['total_passed']}\n\n"
        "**Ошибки по категориям:**\n"
        f"{errors_text}"
    )

    if has_pending_intensive:
        text += (
            f"\n\n⚡️ В интенсиве осталось карточек на повтор: {len(session['intensive_wrong_cards'])}\n"
            "Нажмите «Продолжить интенсив», чтобы пройти неверные карточки ещё раз."
        )

    try:
        await query.message.delete()
    except:
        pass

    if has_pending_intensive:
        keyboard = [
            [InlineKeyboardButton("➡️ Продолжить интенсив", callback_data="culture_continue_intensive")],
            [InlineKeyboardButton("📊 Главное меню", callback_data="culture_exit_main")],
        ]
    else:
        await increment_field(telegram_id, "culture_completed_cards", session["total_passed"])
        await increment_field(telegram_id, "culture_true_cards", session["correct_count"])
        await increment_field(telegram_id, "culture_completed_full", 1)
        keyboard = [[InlineKeyboardButton("📊 Главное меню", callback_data="back_main")]]

    await context.bot.send_message(
        update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    if not has_pending_intensive:
        context.user_data.pop("culture_session", None)


async def _continue_culture_intensive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = _session(context)
    if session.get("mode") != "intensive" or not session.get("intensive_wrong_cards"):
        await _show_culture_final(update, context)
        return

    session["cards"] = session["intensive_wrong_cards"]
    session["intensive_wrong_cards"] = []
    session["intensive_round"] = session.get("intensive_round", 1) + 1
    session["index"] = 0
    session["answers"] = {}
    session["results"] = None
    session["checked"] = False
    session["active_category"] = None
    session["options_by_card"] = {}
    await _show_culture_card(update, context, force_new_message=True)
