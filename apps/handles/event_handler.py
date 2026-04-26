from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
import logging
import random
import pickle
import base64
from datetime import datetime

from assets import getMainMenu, getTrainingOptionalMenu, getTrainingTestMenu, getIntensiveTestMenu, getMarathonTestMenu, getDifficultyMenu, get_choose_train, \
    main_menu_keybord, era_diff_keyboard, notification_and_back_keyboard
from constants import MAIN_MENU, TRAINING, START_TEST, SETTING_TEST
from utils import generate_smart_answers_event_date, generate_smart_answers_date_event, normalize_date_format
from .db_handles import get_eras_name, get_events_with_filters, increment_field, update_streak
from .culture_handler import culture_dispatch
logger = logging.getLogger(__name__)

difficulty_id_to_name = {
    -1: "Любая",
    1: "Легкая",
    2: "Средняя",
    3: "Сложная",
}

train_type_to_str = {
    'training': 'тренировки 🎯',
    'marathon': 'марафона 🏃',
    'intensive': 'интенсива ⚡️',
}


async def get_era_name_by_id(era_id):
    if era_id == -1:
        return "Любая"
    elif era_id:
        eras = await get_eras_name()
        for era in eras:
            if era['id'] == era_id:
                return era['name']
    else:
        return "Не выбрана"


def get_test_type_callback(content):
    if content[0] == 'name':
        return 'event_date'
    return 'date_event'


def get_menu_type(type, era, diff):
    match type:
        case 'marathon':
            return getMarathonTestMenu(diff)
        case 'intensive':
            return getIntensiveTestMenu(era)
        case _:
            return getTrainingTestMenu(diff, era)
        

def get_test_type(data):
    return ('name', 'date') if data == 'event_date' else ('date', 'name')


def update_test_menu(keybord: list[list[InlineKeyboardButton]], train_type: str, prefs: bool, has_saved_progress: bool = False):
    temp_board = keybord.copy()

    if train_type == 'marathon':
        temp_board = [btn for btn in temp_board if btn[0].callback_data != "era"]
        
        if has_saved_progress:
            temp_board.insert(0, [InlineKeyboardButton("🔄 Продолжить марафон", callback_data='continue_marathon')])

    elif train_type == 'intensive':
        temp_board = [btn for btn in temp_board if btn[0].callback_data != "difficulty"]
            
    if prefs:
        temp_board.append(
            [InlineKeyboardButton("✅ Начать тест", callback_data='start_test')]
        )

    return temp_board


def save_marathon_progress(context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('train_type') != 'marathon':
        return
    
    progress_data = {
        'questions': context.user_data.get('test_questions', []),
        'answered_questions': list(context.user_data.get('test_answered_questions', set())),
        'score': context.user_data.get('test_score', 0),
        'current_index': context.user_data.get('test_current_index', 0),
        'difficulty': context.user_data.get('test_difficulty'),
        'test_type': context.user_data.get('test_type'),
        'timestamp': datetime.now().isoformat(),
        'total_questions': context.user_data.get('test_total_questions', 0),
        'correct_answers_indices': list(context.user_data.get('correct_answers_indices', set()))
    }
    
    try:
        context.user_data['marathon_progress'] = base64.b64encode(pickle.dumps(progress_data)).decode('utf-8')
        context.user_data['has_marathon_progress'] = True
    except Exception:
        logger.exception("Ошибка при сохранении прогресса марафона")

    return START_TEST


def load_marathon_progress(context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get('has_marathon_progress'):
        return False
    
    try:
        serialized = context.user_data.get('marathon_progress')
        if not serialized:
            return False
        
        progress_data = pickle.loads(base64.b64decode(serialized.encode('utf-8')))
        
        context.user_data['test_questions'] = progress_data['questions']
        context.user_data['test_answered_questions'] = set(progress_data['answered_questions'])
        context.user_data['test_score'] = progress_data['score']
        context.user_data['test_current_index'] = progress_data['current_index']
        context.user_data['test_difficulty'] = progress_data['difficulty']
        context.user_data['test_type'] = progress_data['test_type']
        context.user_data['test_total_questions'] = progress_data['total_questions']
        context.user_data['correct_answers_indices'] = set(progress_data['correct_answers_indices'])
        context.user_data['test_train_type'] = 'marathon'
        
        return True
    
    except Exception:
        logger.exception("Ошибка при загрузке прогресса марафона")
        return False


def clear_marathon_progress(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('marathon_progress', None)
    context.user_data.pop('has_marathon_progress', None)


async def training_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    era_id = context.user_data.get("era_id")
    era_name = await get_era_name_by_id(era_id)

    difficulty_id = context.user_data.get("difficulty")
    difficulty_name = difficulty_id_to_name[difficulty_id] if difficulty_id else "Не выбрана"

    train_type = context.user_data.get('train_type', 'training')
    
    if query.data in ('event_date', 'date_event'):
        context.user_data["test_type"] = get_test_type(query.data)

        has_difficulty = difficulty_id is not None
        has_era = era_id is not None
       
        has_saved_progress = context.user_data.get('has_marathon_progress', False) and train_type == 'marathon'

        date_event_keyboard = era_diff_keyboard.copy()
        date_event_keyboard = update_test_menu(
            date_event_keyboard, 
            train_type, 
            (train_type == 'marathon' and has_difficulty) or (train_type != 'marathon' and has_difficulty and has_era) or (train_type == 'intensive' and has_era),
            has_saved_progress
        )
        
        date_event_keyboard.extend(notification_and_back_keyboard)

        reply_markup = InlineKeyboardMarkup(date_event_keyboard)
        
        menu_text = get_menu_type(train_type, era_name, difficulty_name)
        
        if has_saved_progress:
            menu_text += "\n\n📥 У вас есть сохраненный марафон. Нажмите 'Продолжить марафон' чтобы продолжить."
            
        await query.edit_message_text(menu_text, reply_markup=reply_markup)
        return SETTING_TEST

    elif query.data in ('culture_training', 'culture_intensive'):
        return await culture_dispatch(update, context)

    elif query.data == 'back_training':
        reply_markup = InlineKeyboardMarkup(get_choose_train(train_type == 'training'))
        await query.edit_message_text(getTrainingOptionalMenu(train_type), reply_markup=reply_markup)
        return TRAINING
    elif query.data == 'chronology':
        await start_chronology_mode(update, context)
        return START_TEST
    elif query.data == 'continue_marathon':
        if load_marathon_progress(context):
            await show_next_question_all(update, context)
            return START_TEST
        else:
            await query.answer("❌ Не удалось загрузить сохраненный прогресс", show_alert=True)
            return SETTING_TEST
    elif query.data == 'back_main':
        reply_markup = InlineKeyboardMarkup(main_menu_keybord)
        await query.edit_message_text(getMainMenu(), reply_markup=reply_markup)
        return MAIN_MENU

    return TRAINING


async def era_diff_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    train_type = context.user_data.get('train_type', 'training')
    test_type = context.user_data.get("test_type")
    
    if query.data == "difficulty":
        saved_difficulty_id = context.user_data.get("difficulty")

        difficulty_keyboard = []

        for difficulty_id, difficulty_name in difficulty_id_to_name.items():
            if saved_difficulty_id == difficulty_id:
                button_text = f"✅ {difficulty_name}"
            else:
                button_text = difficulty_name

            difficulty_keyboard.append(
                [InlineKeyboardButton(button_text, callback_data=f'diff_{difficulty_id}')]
            )

        difficulty_keyboard.append(
            [InlineKeyboardButton("⬅️ Назад", callback_data=get_test_type_callback(test_type))]
        )

        reply_markup = InlineKeyboardMarkup(difficulty_keyboard)
        await query.edit_message_text(getDifficultyMenu(), reply_markup=reply_markup)
        return SETTING_TEST

    elif query.data == "era" and train_type != 'marathon':
        saved_era_id = context.user_data.get("era_id")
        eras = await get_eras_name()

        era_keyboard = []

        if saved_era_id == -1:
            button_text = f"✅ Любая"
        else:
            button_text = "Любая"
        era_keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=f'era_{-1}')]
        )

        for era in eras:
            era_id = era['id']
            era_name = era['name']

            if saved_era_id == era_id:
                button_text = f"✅ {era_name}"
            else:
                button_text = era_name

            era_keyboard.append(
                [InlineKeyboardButton(button_text, callback_data=f'era_{era_id}')]
            )

        era_keyboard.append(
            [InlineKeyboardButton("⬅️ Назад", callback_data=str(get_test_type_callback(test_type)))]
        )

        reply_markup = InlineKeyboardMarkup(era_keyboard)
        await query.edit_message_text("Выберите эпоху:", reply_markup=reply_markup)
        return SETTING_TEST

    elif query.data == "event_date" or query.data == "date_event":
        context.user_data["test_type"] = get_test_type(query.data)
        train_type = context.user_data.get('train_type', 'training')

        difficulty_id = context.user_data.get("difficulty")
        era_id = context.user_data.get("era_id")

        difficulty_name = difficulty_id_to_name[difficulty_id] if difficulty_id else "Не выбрана"
        era_name = await get_era_name_by_id(era_id)

        has_difficulty = difficulty_id is not None
        has_era = era_id is not None
        has_saved_progress = context.user_data.get('has_marathon_progress', False) and train_type == 'marathon'

        date_event_keyboard = era_diff_keyboard.copy()

        date_event_keyboard = update_test_menu(
            date_event_keyboard, 
            train_type, 
            (train_type == 'marathon' and has_difficulty) or (train_type != 'marathon' and has_difficulty and has_era) or (train_type == 'intensive' and has_era),
            has_saved_progress
        )

        date_event_keyboard.extend(notification_and_back_keyboard)

        reply_markup = InlineKeyboardMarkup(date_event_keyboard)
        
        menu_text = get_menu_type(train_type, era_name, difficulty_name)
        
        if has_saved_progress:
            menu_text += "\n\n📥 У вас есть сохраненный марафон. Нажмите 'Продолжить марафон' чтобы продолжить."
            
        await query.edit_message_text(menu_text, reply_markup=reply_markup)
        return SETTING_TEST

    elif query.data == "back_training":
        reply_markup = InlineKeyboardMarkup(get_choose_train(train_type == 'training'))
        await query.edit_message_text(getTrainingOptionalMenu(context.user_data.get('train_type')), reply_markup=reply_markup)
        return TRAINING

    elif query.data == "start_test":
        difficulty_id = context.user_data.get("difficulty")
        era_id = context.user_data.get("era_id")
        train_type = context.user_data.get('train_type', 'training')

        if train_type == 'marathon':
            if not difficulty_id:
                await query.answer("Сначала выберите сложность!", show_alert=True)
                return SETTING_TEST
            
        elif train_type == 'intensive':
            if not era_id:
                await query.answer("Сначала выберите эпоху!", show_alert=True)
                return SETTING_TEST

        elif not difficulty_id or not era_id:
            await query.answer("Сначала выберите сложность и эпоху!", show_alert=True)
            return SETTING_TEST

        await start_test_with_all_questions(update, context)
        return START_TEST
    
    elif query.data == 'continue_marathon':
        if load_marathon_progress(context):
            await show_next_question_all(update, context)
            return START_TEST
        else:
            await query.answer("❌ Не удалось загрузить сохраненный прогресс", show_alert=True)
            return SETTING_TEST

    return SETTING_TEST


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    current_difficulty = context.user_data.get("difficulty")
    current_era = context.user_data.get("era_id")
    train_type = context.user_data.get('train_type', 'training')
    has_saved_progress = context.user_data.get('has_marathon_progress', False) and train_type == 'marathon'
    
    if data in ('event_date', 'date_event'):
        context.user_data["test_type"] = get_test_type(query.data)
        
        difficulty_name = difficulty_id_to_name[current_difficulty] if current_difficulty else "Не выбрана"
        era_name = await get_era_name_by_id(current_era)
        
        final_keyboard = era_diff_keyboard.copy()        
        final_keyboard = update_test_menu(
            final_keyboard, 
            train_type, 
            (train_type == 'marathon' and current_difficulty) or (train_type == 'intensive' and current_era),
            has_saved_progress
        )
        
        final_keyboard.extend(notification_and_back_keyboard)
        
        reply_markup = InlineKeyboardMarkup(final_keyboard)
        
        menu_text = get_menu_type(train_type, era_name, difficulty_name)
        
        if has_saved_progress:
            menu_text += "\n\n📥 У вас есть сохраненный марафон. Нажмите 'Продолжить марафон' чтобы продолжить."
            
        await query.edit_message_text(menu_text, reply_markup=reply_markup)
        return SETTING_TEST

    parts = data.split("_")

    if len(parts) >= 2:
        sett = parts[0]
        try:
            id_value = int(parts[1])
        except ValueError:
            id_value = None

        if sett == "diff" and id_value:
            context.user_data["difficulty"] = id_value
            
            if train_type == 'marathon':
                difficulty_name = difficulty_id_to_name[id_value] if id_value else "Не выбрана"
                
                final_keyboard = era_diff_keyboard.copy()
                final_keyboard = [btn for btn in final_keyboard if btn[0].callback_data != "era"]
                
                if has_saved_progress:
                    final_keyboard.insert(0, [InlineKeyboardButton("🔄 Продолжить марафон", callback_data='continue_marathon')])
                
                final_keyboard.append(
                    [InlineKeyboardButton("✅ Начать тест", callback_data='start_test')]
                )
                final_keyboard.extend(notification_and_back_keyboard)
                
                reply_markup = InlineKeyboardMarkup(final_keyboard)
                menu_text = f"🏃 Марафон\n\nВыберите сложность:\n• {difficulty_name}\n\nНачните тест, чтобы пройти все эпохи подряд!"
                
                if has_saved_progress:
                    menu_text += "\n\n📥 У вас есть сохраненный марафон. Нажмите 'Продолжить марафон' чтобы продолжить."
                    
                await query.edit_message_text(menu_text, reply_markup=reply_markup)
                return SETTING_TEST
            
            elif not current_era and train_type != 'intensive':
                era_keyboard = []
                eras = await get_eras_name()
                
                button_text = f"✅ Любая" if current_era == -1 else "Любая"
                era_keyboard.append(
                    [InlineKeyboardButton(button_text, callback_data=f'era_{-1}')]
                )
                
                for era in eras:
                    era_id = era['id']
                    era_name = era['name']
                    button_text = f"✅ {era_name}" if current_era == era_id else era_name
                    era_keyboard.append(
                        [InlineKeyboardButton(button_text, callback_data=f'era_{era_id}')]
                    )
                
                reply_markup = InlineKeyboardMarkup(era_keyboard)
                await query.edit_message_text("Выберите эпоху:", reply_markup=reply_markup)
                return SETTING_TEST
            
            else:
                difficulty_name = difficulty_id_to_name[id_value] if id_value else "Не выбрана"
                era_name = await get_era_name_by_id(current_era)
                
                final_keyboard = era_diff_keyboard.copy()
                
                if train_type == 'intensive':
                    final_keyboard = [btn for btn in final_keyboard if btn[0].callback_data != "difficulty"]
                
                if (train_type == 'intensive' and current_era ) or \
                (train_type == 'training' and id_value and current_era):
                    final_keyboard.append(
                        [InlineKeyboardButton("✅ Начать тест", callback_data='start_test')]
                    )
                
                final_keyboard.extend(notification_and_back_keyboard)
                
                reply_markup = InlineKeyboardMarkup(final_keyboard)
                menu_text = get_menu_type(train_type, era_name, difficulty_name)
                await query.edit_message_text(menu_text, reply_markup=reply_markup)
                return SETTING_TEST

        elif sett == "era" and id_value and train_type != 'marathon':
            context.user_data["era_id"] = id_value
            
            if not current_difficulty and train_type != 'intensive':
                difficulty_keyboard = []
                for difficulty_id, difficulty_name in difficulty_id_to_name.items():
                    button_text = f"✅ {difficulty_name}" if current_difficulty == difficulty_id else difficulty_name
                    difficulty_keyboard.append(
                        [InlineKeyboardButton(button_text, callback_data=f'diff_{difficulty_id}')]
                    )
                
                reply_markup = InlineKeyboardMarkup(difficulty_keyboard)
                await query.edit_message_text(getDifficultyMenu(), reply_markup=reply_markup)
                return SETTING_TEST
            
            else:
                difficulty_name = difficulty_id_to_name[current_difficulty] if current_difficulty else "Не выбрана"
                era_name = await get_era_name_by_id(id_value)
                
                final_keyboard = era_diff_keyboard.copy()

                if train_type == 'intensive':
                    final_keyboard = [btn for btn in final_keyboard if btn[0].callback_data != "difficulty"]
                
                if (train_type == 'intensive' and era_name) or \
                (train_type == 'training' and id_value and era_name):
                    final_keyboard.append(
                        [InlineKeyboardButton("✅ Начать тест", callback_data='start_test')]
                    )
                
                final_keyboard.extend(notification_and_back_keyboard)
                
                reply_markup = InlineKeyboardMarkup(final_keyboard)
                menu_text = get_menu_type(train_type, era_name, difficulty_name)
                await query.edit_message_text(menu_text, reply_markup=reply_markup)
                return SETTING_TEST
    
    elif not current_difficulty and train_type != 'intensive':
        difficulty_keyboard = []
        for difficulty_id, difficulty_name in difficulty_id_to_name.items():
            button_text = f"✅ {difficulty_name}" if current_difficulty == difficulty_id else difficulty_name
            difficulty_keyboard.append(
                [InlineKeyboardButton(button_text, callback_data=f'diff_{difficulty_id}')]
            )
        
        reply_markup = InlineKeyboardMarkup(difficulty_keyboard)
        await query.edit_message_text(getDifficultyMenu(), reply_markup=reply_markup)
        return SETTING_TEST
    
    elif not current_era and train_type != 'marathon' and train_type != 'intensive':
        era_keyboard = []
        eras = await get_eras_name()
        
        button_text = f"✅ Любая" if current_era == -1 else "Любая"
        era_keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=f'era_{-1}')]
        )
        
        for era in eras:
            era_id = era['id']
            era_name = era['name']
            button_text = f"✅ {era_name}" if current_era == era_id else era_name
            era_keyboard.append(
                [InlineKeyboardButton(button_text, callback_data=f'era_{era_id}')]
            )
        
        reply_markup = InlineKeyboardMarkup(era_keyboard)
        await query.edit_message_text("Выберите эпоху:", reply_markup=reply_markup)
        return SETTING_TEST
    
    else:
        difficulty_name = difficulty_id_to_name[current_difficulty] if current_difficulty else "Не выбрана"
        era_name = await get_era_name_by_id(current_era)
        
        final_keyboard = era_diff_keyboard.copy()
        
        final_keyboard = update_test_menu(
            final_keyboard, 
            train_type, 
            (train_type == 'marathon' and current_difficulty) or (train_type == 'intensive' and current_era) or (train_type == 'training' and current_difficulty and current_era),
            has_saved_progress
        )
        
        final_keyboard.extend(notification_and_back_keyboard)
        
        reply_markup = InlineKeyboardMarkup(final_keyboard)
        
        menu_text = get_menu_type(train_type, era_name, difficulty_name)
        
        if has_saved_progress:
            menu_text += "\n\n📥 У вас есть сохраненный марафон. Нажмите 'Продолжить марафон' чтобы продолжить."
            
        await query.edit_message_text(menu_text, reply_markup=reply_markup)
        return SETTING_TEST


async def start_test_with_all_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    difficulty_id = context.user_data.get("difficulty")
    era_id = context.user_data.get("era_id")
    train_type = context.user_data.get('train_type', 'training')

    if train_type == 'marathon':
        clear_marathon_progress(context)

    context.user_data['test_questions'] = []
    context.user_data['test_current_index'] = 0
    context.user_data['test_score'] = 0
    context.user_data['test_difficulty'] = difficulty_id
    context.user_data['test_era'] = -1 if train_type == 'marathon' else era_id
    context.user_data['test_train_type'] = train_type

    if train_type == 'marathon':
        questions = []
        
        eras = await get_eras_name()
        
        for era in eras:
            era_id = era['id']
            era_questions = await get_events_with_filters(
                None,  # difficulty_id if difficulty_id != -1 else None,
                era_id
            )
            
            if era_questions:
                random.shuffle(era_questions)
                for question in era_questions:
                    question['era_id'] = era_id
                    question['era_name'] = era['name']
                questions.extend(era_questions)
        
        if not questions and difficulty_id != -1:
            questions = await get_events_with_filters(
                None,  # difficulty_id,
                None
            )
            for question in questions:
                question['era_id'] = -1
                question['era_name'] = "Неизвестно"
                
    else:
        questions = await get_events_with_filters(
            None,  # difficulty_id if difficulty_id != -1 else None,
            era_id if era_id != -1 else None
        )
        random.shuffle(questions)

    if not questions:
        await query.edit_message_text(
            "❌ Не удалось найти вопросы с выбранными параметрами.\n"
        )

        return SETTING_TEST

    context.user_data['test_questions'] = questions
    context.user_data['test_total_questions'] = len(questions)
    context.user_data['test_answered_questions'] = set()

    await show_next_question_all(update, context)
    return START_TEST


async def show_next_question_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = context.user_data.get('test_questions', [])
    total_questions = context.user_data.get('test_total_questions', 0)
    answered_questions = context.user_data.get('test_answered_questions', set())

    if len(answered_questions) >= total_questions:
        await show_final_results(update, context)
        return

    current_index = context.user_data.get('test_current_index', 0)
    current_question = None

    while current_index < total_questions:
        if current_index not in answered_questions:
            current_question = questions[current_index]
            context.user_data['test_current_index'] = current_index
            break
        current_index += 1

    if not current_question:
        await show_final_results(update, context)
        return

    all_questions = questions

    test_type = context.user_data.get('test_type')
    
    if test_type[0] == 'name':
        answers = await generate_smart_answers_event_date(current_question, all_questions)
    else:
        answers = await generate_smart_answers_date_event(current_question, all_questions)

    context.user_data['current_answers'] = answers
    context.user_data['current_question'] = current_question
    context.user_data['correct_answer'] = current_question[test_type[1]]
    
    era_info = ""
    train_type = context.user_data.get('test_train_type', 'training')
    if train_type == 'marathon' and 'era_name' in current_question:
        era_info = f"\n🏛 Эпоха: {current_question['era_name']}"

    keyboard = []
    numbered_answers = [f"{i}. {answer}" for i, answer in enumerate(answers, 1)]
    for i, _ in enumerate(answers, 1):
        keyboard.append([InlineKeyboardButton(str(i), callback_data=f'answer_{i}')])

    if train_type == 'marathon':
        keyboard.append([InlineKeyboardButton("💾 Сохранить и выйти", callback_data='save_and_exit')])
    
    keyboard.append([InlineKeyboardButton("❌ Завершить тест", callback_data='cancel_test')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if test_type[0] == 'name':
        name_1, name_2 = 'Событие', 'правильную дату'
    else:
        name_1, name_2 = 'Дата', 'правильное событие'
        
    text = (f"📝 Вопрос {len(answered_questions) + 1}/{total_questions}\n"
            f"🎚 Сложность: {difficulty_id_to_name.get(context.user_data.get('test_difficulty'), 'Любая')}"
            f"{era_info}\n\n"
            f"{name_1}: {current_question[test_type[0]]}\n\n"
            f"Выберите {name_2}:\n"
            f"{chr(10).join(numbered_answers)}")

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def show_final_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() if query else None

    user = update.effective_user
    telegram_id = user.id
    
    score = context.user_data.get('test_score', 0)
    answered = len(context.user_data.get('test_answered_questions', set()))
    total = context.user_data.get('test_total_questions', 0)
    train_type = context.user_data.get('train_type', 'training')
    
    incorrect_questions = []
    if train_type == 'intensive' and 'test_questions' in context.user_data and 'test_answered_questions' in context.user_data:
        questions = context.user_data.get('test_questions', [])
        answered_questions_indices = context.user_data.get('test_answered_questions', set())
        
        for idx, question in enumerate(questions):
            if idx in answered_questions_indices:
                context.user_data.setdefault('all_questions_history', []).append({
                    'question': question,
                    'index': idx,
                    'correct': idx in context.user_data.get('correct_answers_indices', set())
                })
                
                if idx not in context.user_data.get('correct_answers_indices', set()):
                    incorrect_questions.append(question)

    if answered == 0:
        percentage = 0
    else:
        percentage = (score / answered) * 100

    difficulty_id = context.user_data.get('test_difficulty')
    difficulty_name = difficulty_id_to_name[difficulty_id] if difficulty_id else "Любая"
        
    keyboard = []
    
    if train_type == 'intensive' and incorrect_questions:
        context.user_data['incorrect_questions'] = incorrect_questions
        context.user_data['intensive_round'] = context.user_data.get('intensive_round', 1) + 1
        
        keyboard.append(
            [InlineKeyboardButton("➡️ Продолжить интенсив", callback_data='continue_intensive')]
        )
    
    keyboard.extend(
        [
            [InlineKeyboardButton("🔄 Начать заново", callback_data='back_training')],
            [InlineKeyboardButton("📊 Главное меню", callback_data='back_main')],
        ]
    )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    round_info = ""
    if train_type == 'intensive':
        current_round = context.user_data.get('intensive_round', 1)
        round_info = f" (Раунд {current_round})"
    
    if train_type == 'marathon':
        text = (f"🏁 Марафон завершен{round_info}!\n\n"
                f"Настройки теста:\n"
                f"• Сложность: {difficulty_name}\n"
                f"• Все эпохи подряд\n\n"
                f"Всего вопросов: {total}\n"
                f"Отвечено: {answered}\n"
                f"Правильных ответов: {score}\n"
                f"Процент правильных: {percentage:.1f}%\n\n")

        await increment_field(telegram_id, 'marathon_completed_cards', answered)
        if total == answered:
            await increment_field(telegram_id, 'marathon_completed_full', 1)
        await increment_field(telegram_id, 'marathon_true_cards', score)
        
        clear_marathon_progress(context)

    elif train_type == 'intensive':
        era_id = context.user_data.get('test_era', -1)
        era_name = await get_era_name_by_id(era_id)
        
        text = (f"⚡️ Интенсив завершен{round_info}!\n\n"
                f"Настройки теста:\n"
                f"• Сложность: {difficulty_name}\n"
                f"• Эпоха: {era_name}\n\n"
                f"Всего вопросов: {total}\n"
                f"Отвечено: {answered}\n"
                f"Правильных ответов: {score}\n"
                f"Процент правильных: {percentage:.1f}%\n")

        await increment_field(telegram_id, 'intensive_completed_cards', answered)
        if total == answered:
            await increment_field(telegram_id, 'intensive_completed_full', 1)
        await increment_field(telegram_id, 'intensive_true_cards', score)
        
        if incorrect_questions:
            text += f"\n❌ Неправильных ответов: {len(incorrect_questions)}\n"
            text += "Нажмите 'Продолжить интенсив' для повторения неправильных ответов!\n"
        else:
            text += "\n🎉 Отлично! Все ответы правильные!"
    else:
        era_id = context.user_data.get('test_era', -1)
        era_name = await get_era_name_by_id(era_id)

        if answered >= 10:
            fire = "Огонек горит 🔥"
        else:
            fire = ""
        text = (f"🎉 Тест завершен!\n\n"
                f"Настройки теста:\n"
                f"• Сложность: {difficulty_name}\n"
                f"• Эпоха: {era_name}\n\n"
                f"Всего вопросов: {total}\n"
                f"Отвечено: {answered}\n"
                f"Правильных ответов: {score}\n"
                f"Процент правильных: {percentage:.1f}%\n\n"
                f"{fire}")



        await increment_field(telegram_id, 'training_completed_cards', answered)
        await increment_field(telegram_id, 'training_completed_full', 1) if total == answered else None
        await increment_field(telegram_id, 'training_true_cards', score)


    if answered == 0:
        text += "Вы не ответили ни на один вопрос."
    elif percentage >= 90:
        text += "🏅 Отлично! Вы настоящий историк!"
    elif percentage >= 70:
        text += "👍 Хорошо! Продолжайте в том же духе!"
    elif percentage >= 50:
        text += "📚 Неплохо, но есть куда расти!"
    else:
        text += "💪 Не отчаивайтесь! Практика делает мастера!"

    keys_to_delete = ['test_questions', 'test_current_index', 'test_score',
                      'test_total_questions', 'test_difficulty', 'test_era', 
                      'test_answered_questions', 'current_answers', 
                      'current_question', 'correct_answer', 'correct_answers_indices']
    
    for key in keys_to_delete:
        if key in context.user_data:
            del context.user_data[key]

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def back_to_training_from_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    train_type = context.user_data.get('train_type', 'training')
    
    reply_markup = InlineKeyboardMarkup(get_choose_train(train_type == 'training'))
    await query.edit_message_text(
        getTrainingOptionalMenu(train_type),
        reply_markup=reply_markup
    )
    return TRAINING


async def continue_intensive_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if 'incorrect_questions' not in context.user_data or not context.user_data['incorrect_questions']:
        await query.edit_message_text(
            "❌ Ошибка: нет неправильных ответов для повторения.\n"
            "Начните новый тест."
        )
        return
    
    incorrect_questions = context.user_data['incorrect_questions']
    
    context.user_data['test_questions'] = incorrect_questions.copy()
    context.user_data['test_current_index'] = 0
    context.user_data['test_score'] = 0
    context.user_data['test_total_questions'] = len(incorrect_questions)
    context.user_data['test_answered_questions'] = set()
    context.user_data['correct_answers_indices'] = set()
    context.user_data['test_train_type'] = 'intensive'
    
    del context.user_data['incorrect_questions']
    
    await query.edit_message_text(
        f"⚡️ Продолжение интенсива (Раунд {context.user_data.get('intensive_round', 2)})\n"
        f"Вопросов для повторения: {len(incorrect_questions)}\n\n"
        "Начинаем тест с неправильными ответами..."
    )
    
    await show_next_question_all(update, context)
    return START_TEST


async def handle_answer_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    answer_num = int(query.data.split('_')[1])

    answers = context.user_data.get('current_answers', [])
    correct_answer = context.user_data.get('correct_answer', '')
    current_question = context.user_data.get('current_question', {})
    current_index = context.user_data.get('test_current_index', 0)
    answered_questions = context.user_data.get('test_answered_questions', set())
    test_type = context.user_data.get('test_type')

    if answer_num <= len(answers):
        selected_answer = answers[answer_num - 1]

        try:
            normalized_selected = normalize_date_format(selected_answer)
            normalized_correct = normalize_date_format(correct_answer)

            is_correct = normalized_selected == normalized_correct
        except Exception:
            is_correct = selected_answer == correct_answer

        if is_correct:
            context.user_data['test_score'] = context.user_data.get('test_score', 0) + 1
            correct_indices = context.user_data.setdefault('correct_answers_indices', set())
            correct_indices.add(current_index)
        else:
            if 'correct_answers_indices' in context.user_data and current_index in context.user_data['correct_answers_indices']:
                context.user_data['correct_answers_indices'].remove(current_index)

        answered_questions.add(current_index)
        context.user_data['test_answered_questions'] = answered_questions
        if len(answered_questions) >= 10:
            await update_streak(telegram_id=update.effective_user.id)
        result_text = "✅ Правильно!" if is_correct else "❌ Неправильно!"
        try:
            explanation = f"\n\nПравильный ответ: {normalize_date_format(correct_answer)}"
        except Exception:
            explanation = f"\n\nПравильный ответ: {correct_answer}"

        keyboard = []
        detailed_answers = []
        for i, answer in enumerate(answers, 1):
            try:
                normalized_answer = normalize_date_format(answer)
                normalized_correct = normalize_date_format(correct_answer)
                if normalized_answer == normalized_correct:
                    button_text = "✅"
                    detailed_answers.append(f"{i}. ✅ {answer}")
                elif i == answer_num and not is_correct:
                    button_text = "❌"
                    detailed_answers.append(f"{i}. ❌ {answer}")
                else:
                    button_text = str(i)
                    detailed_answers.append(f"{i}. {answer}")
            except Exception:
                if answer == correct_answer:
                    button_text = "✅"
                    detailed_answers.append(f"{i}. ✅ {answer}")
                elif i == answer_num and not is_correct:
                    button_text = "❌"
                    detailed_answers.append(f"{i}. ❌ {answer}")
                else:
                    button_text = str(i)
                    detailed_answers.append(f"{i}. {answer}")

            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'disabled_{i}')])

        await update_streak(telegram_id=update.effective_chat.id)
        
        if context.user_data.get('test_train_type') == 'marathon':
            save_marathon_progress(context)
            
        keyboard.append([InlineKeyboardButton("➡️ Следующий вопрос", callback_data='next_question')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        era_info = ""
        train_type = context.user_data.get('test_train_type', 'training')
        if train_type == 'marathon' and 'era_name' in current_question:
            era_info = f"\n🏛 Эпоха: {current_question['era_name']}"
            
        name_ = 'Событие' if test_type[0] == 'name' else 'Дата'
        text = (f"📝 Вопрос {len(answered_questions)}/{context.user_data.get('test_total_questions', 0)}\n"
                f"🎚 Сложность: {difficulty_id_to_name.get(context.user_data.get('test_difficulty'), 'Любая')}"
                f"{era_info}\n\n"
                f"{name_}: {current_question.get(test_type[0], '')}\n\n"
                f"{result_text}{explanation}\n\n"
                f"Варианты:\n{chr(10).join(detailed_answers)}")

        await query.edit_message_text(text, reply_markup=reply_markup)

    return START_TEST


async def next_question_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    total_questions = context.user_data.get('test_total_questions', 0)
    answered_questions = context.user_data.get('test_answered_questions', set())

    if len(answered_questions) >= total_questions:
        return await show_final_results(update, context)

    current_index = context.user_data.get('test_current_index', 0)
    context.user_data['test_current_index'] = current_index + 1

    await show_next_question_all(update, context)
    return START_TEST


async def start_test_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'cancel_test':
        await show_final_results(update, context)

    return START_TEST


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await handle_answer_all(update, context)


async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await next_question_all(update, context)


async def finish_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_final_results(update, context)


async def cancel_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if context.user_data.get('test_train_type') == 'marathon':
        save_marathon_progress(context)
        await query.edit_message_text(
            "💾 Прогресс марафона сохранен!\n\n"
            "Вы можете продолжить позже, выбрав 'Продолжить марафон' в меню настроек.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ В меню", callback_data='back_main')]
            ])
        )
        return MAIN_MENU
    
    await show_final_results(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(getMainMenu())
    return ConversationHandler.END


async def save_and_exit_marathon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if context.user_data.get('test_train_type') == 'marathon':
        save_marathon_progress(context)
        
        keys_to_clear = ['current_answers', 'current_question', 'correct_answer']
        for key in keys_to_clear:
            context.user_data.pop(key, None)
        
        await query.edit_message_text(
            "💾 Прогресс марафона успешно сохранен!\n\n"
            "Вы можете продолжить позже, выбрав 'Продолжить марафон' в меню марафона.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏃 Вернуться к марафону", callback_data='back_training')],
                [InlineKeyboardButton("📊 Главное меню", callback_data='back_main')]
            ])
        )
        return TRAINING
    
    return START_TEST


async def start_chronology_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    era_id = context.user_data.get("era_id")
    train_type = context.user_data.get('train_type', 'training')

    questions = await get_events_with_filters(None, era_id if era_id != -1 else None)

    if not questions or len(questions) < 5:
        await query.edit_message_text(
            "❌ Недостаточно вопросов для режима хронологии."
        )
        return

    random.shuffle(questions)
    questions = questions[:5]

    context.user_data.update({
        'chronology_active': True,
        'chronology_questions': questions,
        'chronology_dates': [q['date'] for q in questions],
        'chronology_events': random.sample([q['name'] for q in questions], 5),
        'chronology_pairs': {},
        'chronology_selected_date': None,
        'chronology_used_events': set(),
        'test_train_type': train_type
    })

    await render_chronology(update, context)


async def render_chronology(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not context.user_data.get('chronology_active'):
        return

    dates = context.user_data.get('chronology_dates', [])
    events = context.user_data.get('chronology_events', [])
    pairs = context.user_data.get('chronology_pairs', {})
    selected_date = context.user_data.get('chronology_selected_date')
    used_events = context.user_data.get('chronology_used_events', set())

    keyboard = []

    for i in range(5):
        date_text = dates[i]

        if i == selected_date:
            date_text = "🟡 " + date_text

        if i in pairs:
            date_text = "🔗 " + date_text

        keyboard.append([
            InlineKeyboardButton(date_text, callback_data=f"chronology_date_{i}")
        ])


    for i in range(5):
        event_text = events[i]

        if i in used_events:
            event_text = "🔒 " + event_text

        keyboard.append([
            InlineKeyboardButton(event_text, callback_data=f"chronology_event_{i}")
        ])

    keyboard.extend([
        [InlineKeyboardButton("✅ Проверить", callback_data="check_chronology")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="cancel_test")],
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)


    try:
        await query.edit_message_text(
            "🧠 Сопоставьте даты и события:\n\n"
            "1️⃣ Выберите дату\n"
            "2️⃣ Затем выберите событие\n"
            "Можно менять выбор до проверки.",
            reply_markup=reply_markup
        )
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise

async def handle_chronology(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "chronology_retry":
        await start_chronology_mode(update, context)
        return

    if not context.user_data.get('chronology_active'):
        await query.answer("⚠️ Сессия завершена. Начните заново.", show_alert=True)
        return

    pairs = context.user_data.get('chronology_pairs', {})
    used_events = context.user_data.get('chronology_used_events', set())

    if data.startswith("chronology_date_"):
        index = int(data.split("_")[-1])
        context.user_data['chronology_selected_date'] = index

    elif data.startswith("chronology_event_"):
        event_index = int(data.split("_")[-1])
        selected_date = context.user_data.get('chronology_selected_date')

        if selected_date is None:
            return

        if event_index in used_events:
            await query.answer("⚠️ Это событие уже использовано", show_alert=True)
            return

        if selected_date in pairs:
            old_event = pairs[selected_date]
            used_events.discard(old_event)

        pairs[selected_date] = event_index
        used_events.add(event_index)

        context.user_data['chronology_selected_date'] = None

    await render_chronology(update, context)


async def check_chronology(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not context.user_data.get('chronology_active'):
        return

    pairs = context.user_data.get('chronology_pairs', {})
    questions = context.user_data.get('chronology_questions', [])
    shuffled_events = context.user_data.get('chronology_events', [])

    if len(pairs) < 5:
        await query.answer("⚠️ Сопоставьте все 5 пар!", show_alert=True)
        return

    correct = 0
    result_lines = []

    for date_index, event_index in pairs.items():
        correct_event = questions[date_index]['name']
        selected_event = shuffled_events[event_index]
        date_value = questions[date_index]['date']

        if correct_event == selected_event:
            correct += 1
            result_lines.append(f"✅ {date_value} — {selected_event}")
        else:
            result_lines.append(
                f"❌ {date_value}\n"
                f"   Ваш ответ: {selected_event}\n"
                f"   Правильно: {correct_event}"
            )

    percent = (correct / 5) * 100

    if correct == 5:
        await update_streak(telegram_id=update.effective_user.id)

    text = (
        f"📊 Результат хронологии\n\n"
        f"Правильно: {correct}/5\n"
        f"Процент: {percent:.1f}%\n\n"
        + "\n\n".join(result_lines)
    )

    keyboard = [
        [InlineKeyboardButton("🔁 Попробовать снова", callback_data="chronology_retry")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")],
    ]

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise

    for key in [
        'chronology_active',
        'chronology_questions',
        'chronology_dates',
        'chronology_events',
        'chronology_pairs',
        'chronology_selected_date',
        'chronology_used_events'
    ]:
        context.user_data.pop(key, None)
