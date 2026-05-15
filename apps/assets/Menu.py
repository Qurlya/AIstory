from telegram import InlineKeyboardButton

main_menu_keybord = [
        [InlineKeyboardButton("🎯 Тренировка", callback_data='training')],
        [InlineKeyboardButton("⚡ Интенсив", callback_data='intensive')],
        [InlineKeyboardButton("🏃 Марафон", callback_data='marathon')],
        [InlineKeyboardButton("🏛 Архитектура", callback_data='culture')],
        [InlineKeyboardButton("🔥 Держи стрик", callback_data='streak')],
        [InlineKeyboardButton("📣 Помощь при поступлении", callback_data='ads')],
        [InlineKeyboardButton("📊 Моя статистика", callback_data='stats')],
]


def get_main_menu_keyboard(is_admin: bool = False) -> list:
    keyboard = [row[:] for row in main_menu_keybord]
    if is_admin:
        keyboard.append([InlineKeyboardButton("🛠 Администрирование", callback_data='admin')])
    return keyboard

choose_train_menu = [
        [InlineKeyboardButton("Хронология", callback_data='chronology')],
        [InlineKeyboardButton("Дата - Событие", callback_data='date_event')],
        [InlineKeyboardButton("Событие - Дата", callback_data='event_date')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_main')],
]


def get_choose_train(is_training: bool = False) -> list:
    if is_training:
        return choose_train_menu
    return choose_train_menu[1:]
    

era_diff_keyboard = [
        [InlineKeyboardButton("🏺 Эпоха", callback_data='era')],
        [InlineKeyboardButton("🎚 Сложность", callback_data='difficulty')],
]

notification_and_back_keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_training')],
]

back_menu_keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_main')],
]

subscribe_keyboard = [
        [InlineKeyboardButton("📢 Подписаться на канал", url="https://t.me/aisthistory")],
        [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub_after_start")],
]

noth_keyboard = [
        [InlineKeyboardButton("📊 Главное меню", callback_data="back_main")],
]

culture_choose_menu = [
        [InlineKeyboardButton("🎯 Тренировка", callback_data='culture_training')],
        [InlineKeyboardButton("⚡ Интенсив", callback_data='culture_intensive')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_main')],
]
