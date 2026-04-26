from __future__ import annotations

from pathlib import Path
import random
from typing import Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from assets import getMainMenu, main_menu_keybord
from handles.db_handles import get_culture_answer_values, get_random_cultures, increment_field, update_streak
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
    wrong_needed = max(count - 1, 0)

    wrong_answers = await get_culture_answer_values(
        field_name=field,
        limit=wrong_needed,
        exclude_value=correct,
        culture_type=current_card.get("type") if field == "title" else None,
    )

    if field == "title" and len(wrong_answers) < wrong_needed:
        additional = await get_culture_answer_values(
            field_name=field,
            limit=wrong_needed - len(wrong_answers),
            exclude_value=correct,
        )
        wrong_answers.extend([item for item in additional if item not in wrong_answers])

    options = wrong_answers[:wrong_needed]
    options.append(correct)
    random.shuffle(options)
    return options

async def start_culture_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    query = update.callback_query
    await query.answer()

    raw_cards = await get_random_cultures(15)
    cards = [_normalize_card(card) for card in raw_cards]

    if not cards:
        await query.edit_message_text("❌ В базе данных нет карточек архитектуры.")
        return MAIN_MENU

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
        "active_category": None
    }

    await _show_culture_card(update, context, force_new_message=True)
    return START_TEST

async def culture_dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "culture_training":
        return await start_culture_mode(update, context, "training")

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

    return START_TEST

async def _show_culture_card(update: Update, context: ContextTypes.DEFAULT_TYPE, force_new_message: bool = False):
    query = update.callback_query
    session = _session(context)
    card = session["cards"][session["index"]]
    categories = _available_categories(card)

    caption = (
        f"🏛 **Архитектура: {session['mode'].capitalize()}**\n"
        f"Карточка №{session['total_passed'] + 1}\n\n"
        "Заполните все данные о строении на фото:"
    )

    keyboard = []
    ans = session["answers"]
    res = session["results"]
    is_checked = session["checked"]

    for key, label in categories:
        if is_checked:
            icon = "✅" if res.get(key) else "❌"
            btn_text = f"{icon} {ans.get(key, '—')}"
        elif key in ans:
            btn_text = f"🟡 {ans[key]}"
        else:
            btn_text = label
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"culture_category_{key}")])

    nav_btns = []
    if len(ans) == len(categories) and not is_checked:
        nav_btns.append(InlineKeyboardButton("🔍 Проверить", callback_data="culture_check"))

    if is_checked:
        nav_btns.append(InlineKeyboardButton("➡️ Дальше", callback_data="culture_next"))

    if nav_btns: keyboard.append(nav_btns)

    keyboard.append([InlineKeyboardButton("🏁 Завершить тренировку", callback_data="culture_finish")])
    keyboard.append([InlineKeyboardButton("📊 В меню", callback_data="culture_exit_main")])

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
    options = await _build_answers_pool(card, category)
    session["current_options"] = options

    text = f"❓ Выберите верный вариант для категории:\n**{CATEGORY_LABELS[category]}**"

    keyboard = []
    for i, opt in enumerate(options, 1):
        keyboard.append([InlineKeyboardButton(f"{i}. {opt}", callback_data=f"culture_pick_{i}")])

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
        session["answers"][category] = session["current_options"][idx - 1]
    await _show_culture_card(update, context)

async def _check_current_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = _session(context)
    card = session["cards"][session["index"]]
    categories = _available_categories(card)

    results = {}
    correct_all = True
    for key, _ in categories:
        is_correct = session["answers"].get(key) == card.get(key)
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

    await update_streak(telegram_id=update.effective_user.id)

    await _show_culture_card(update, context)

async def _next_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = _session(context)
    session["index"] += 1

    if session["index"] >= len(session["cards"]):
        new_cards = await get_random_cultures(10)
        session["cards"].extend([_normalize_card(c) for c in new_cards])

    session["answers"] = {}
    session["results"] = None
    session["checked"] = False
    await _show_culture_card(update, context, force_new_message=True)

async def _show_culture_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    session = _session(context)
    telegram_id = update.effective_user.id

    errors_text = "\n".join([f"• {CATEGORY_LABELS[k]}: {v}" for k, v in session["errors_by_category"].items() if v > 0])

    await increment_field(telegram_id, "culture_completed_cards", session["total_passed"])
    await increment_field(telegram_id, "culture_true_cards", session["correct_count"])
    await increment_field(telegram_id, "culture_completed_full", 1)

    text = (
        "📊 **Результаты тренировки**\n\n"
        f"✅ Правильно: {session['correct_count']}\n"
        f"❌ Ошибочно: {session['incorrect_count']}\n"
        f"📚 Всего карточек: {session['total_passed']}\n\n"
        "**Ошибки по категориям:**\n"
        f"{errors_text if errors_text else 'Ошибок нет!'}"
    )

    try:
        await query.message.delete()
    except:
        pass

    await context.bot.send_message(
        update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 В меню", callback_data="back_main")]]),
        parse_mode="Markdown"
    )
    context.user_data.pop("culture_session", None)
