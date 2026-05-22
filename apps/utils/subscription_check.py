import os
from telegram import Update
from telegram.ext import ContextTypes

IS_SUBSCRIPTION_ENABLED = os.getenv("CHECK_SUBSCRIPTION", "True").lower() == "true"

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not IS_SUBSCRIPTION_ENABLED:
        return True

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