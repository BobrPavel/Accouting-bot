# --------------------------------------------------------------------------------
# Модуль обработки команд из приватных чатов
# --------------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------------

from io import BytesIO
import mimetypes
from sre_parse import State
from aiogram import types, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup



# --------------------------------------------------------------------------------
# Настройки
# --------------------------------------------------------------------------------


user_private_router = Router()


# --------------------------------------------------------------------------------
# Обработчики
# --------------------------------------------------------------------------------


@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Приветсвую! Я бот для генерации актов и счетов. Отправь мне файл с вашими реквизитам")



# --------------------------------------------------------------------------------
# FSM для получения файлов с реквизитами
# --------------------------------------------------------------------------------


class ReqFiles(StatesGroup):
    waiting_my_file = State()
    waiting_client_file = State()
    chatting = State()


@user_private_router.message(F.document)
async def handle_file(message: types.Message, state: FSMContext, bot):
    current_state = await state.get_state()

    doc = message.document
    file_id = doc.file_id
    file_name = doc.file_name

    mime_type, _ = mimetypes.guess_type(file_name)
    if not mime_type:
        mime_type = "application/octet-stream"


    # Временное имя файла
    if current_state == ReqFiles.waiting_my_file.state:
        next_state = ReqFiles.waiting_client_file
        prompt = "Теперь отправьте **файл с реквизитами заказчика**."

    elif current_state == ReqFiles.waiting_client_file.state:
        next_state = ReqFiles.chatting
        prompt = "Файл реквизитов заказчика получен! 🎉\nТеперь можете писать, что хотите сгенерировать — акт, счёт или оба документа."

    else:
        await message.answer("Сначала отправьте файл с ревизитами")
        return

    # ---- Скачиваем файл в память ----
    buffer = BytesIO()
    buffer.name = file_name

    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, buffer)
    buffer.seek(0)



    # ---- Если это первый файл, то ждём второй ----
    if next_state != ReqFiles.chatting:
        await message.answer(prompt)
        await state.set_state(next_state)
        return
    elif next_state == ReqFiles.chatting:
        await message.answer(prompt)

        # ---- Переходим в режим диалога ----
        await state.set_state(ReqFiles.chatting)


@user_private_router.message(ReqFiles.chatting)
async def agent_chat(message: types.Message, state: FSMContext):
    pass