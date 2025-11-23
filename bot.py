# --------------------------------------------------------------------------------
# Базовый модуль
# --------------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------------
import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from handlers.user_private import user_private_router


# --------------------------------------------------------------------------------
# Настройки
# --------------------------------------------------------------------------------


bot = Bot(token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
bot.my_admins_list = []

dp = Dispatcher()

dp.include_router(user_private_router)


# --------------------------------------------------------------------------------
# Оповещение
# --------------------------------------------------------------------------------


async def on_startup(bot):
    print("бот запущен")


async def on_shutdown(bot):
    print("бот лег")


# --------------------------------------------------------------------------------
# Запуск
# --------------------------------------------------------------------------------


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.delete_my_commands(scope=types.BotCommandScopeAllPrivateChats())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


asyncio.run(main())
