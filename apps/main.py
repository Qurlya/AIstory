import os
import asyncio
import logging
from datetime import time
from zoneinfo import ZoneInfo
from telegram.ext import Application, CommandHandler, ConversationHandler, CallbackQueryHandler, JobQueue, MessageHandler, filters

from handles.db_handles import load_datafile_to_db
from constants import SETTING_TEST, MAIN_MENU, TRAINING, START_TEST
from handles import (
    start, main_menu, training_menu, start_test_menu, handle_answer, next_question, cancel,
    era_diff_menu, settings_menu, continue_intensive_mode, start_test_with_all_questions,
    back_to_training_from_test, save_and_exit_marathon, handle_chronology, check_chronology, start_chronology_mode,
    culture_dispatch
)
from database import database
from handles.start_menu import check_subscription_after_start, notify_maintenance, send_daily_streak_reminder

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

BOT_TOKEN = os.getenv('BOT_TOKEN')
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def handle_bot_error(update, context):
    logger.error(
        "Unhandled telegram bot error. update=%s user_data_keys=%s",
        update,
        list(context.user_data.keys()) if context.user_data else [],
        exc_info=context.error,
    )


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(database.init())

    application = Application.builder().token(BOT_TOKEN).job_queue(JobQueue()).build()

    async def startup_tasks(app):
        await notify_maintenance(app)

        app.job_queue.run_daily(
            send_daily_streak_reminder,
            time=time(hour=12, minute=37, tzinfo=MOSCOW_TZ),
            days=(0,1,2,3,4,5,6),  # каждый день недели
            name="daily_streak",
        )

    application.post_init = startup_tasks

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(main_menu, pattern='^(training|intensive|marathon|culture|streak|stats|back_main)$'),
                CallbackQueryHandler(check_subscription_after_start, pattern='^check_sub_after_start$'),
            ],
            TRAINING: [
                CallbackQueryHandler(training_menu,
                                     pattern='^(chronology|date_event|event_date|back_main|back_training|continue_marathon|culture_training|culture_intensive|culture_exit_main)$')
            ],
            SETTING_TEST: [
                CallbackQueryHandler(era_diff_menu,
                                     pattern='^(difficulty|era|date_event|event_date|back_training|start_test|continue_marathon)$'),
                CallbackQueryHandler(settings_menu,
                                     pattern='^(diff_-1|diff_1|diff_2|diff_3|era_-1|era_[0-9]+|event_date|date_event)$')
            ],
            START_TEST: [
                CallbackQueryHandler(start_test_menu, pattern='^cancel_test$'),
                CallbackQueryHandler(handle_answer, pattern='^answer_[1-4]$'),
                CallbackQueryHandler(next_question, pattern='^next_question$'),
                CallbackQueryHandler(main_menu, pattern='^back_main$'),
                CallbackQueryHandler(era_diff_menu, pattern='^(difficulty|era)$'),
                CallbackQueryHandler(start_test_with_all_questions, pattern='^start_test$'),
                CallbackQueryHandler(back_to_training_from_test, pattern='^back_training$'),
                CallbackQueryHandler(continue_intensive_mode, pattern='^continue_intensive$'),
                CallbackQueryHandler(handle_chronology, pattern='^chronology_'),
                CallbackQueryHandler(check_chronology, pattern='^check_chronology$'),
                CallbackQueryHandler(start_chronology_mode, pattern='^chronology_retry$'),
                CallbackQueryHandler(save_and_exit_marathon, pattern='^save_and_exit$'),
                CallbackQueryHandler(culture_dispatch, pattern='^culture_'),
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Document.ALL, load_datafile_to_db))
    application.add_error_handler(handle_bot_error)

    application.run_polling()


if __name__ == '__main__':
    main()
