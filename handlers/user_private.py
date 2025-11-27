# --------------------------------------------------------------------------------
# Модуль обработки команд из приватных чатов
# --------------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------------


import os
import json
import uuid
import mimetypes
import subprocess

from io import BytesIO
from typing import Sequence
from dataclasses import dataclass, asdict

from aiogram import Bot, types, Router, F
from aiogram.types import FSInputFile 
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from langchain_core.language_models import LanguageModelLike
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langchain_gigachat.chat_models import GigaChat
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from common.texts import *
from utils.pdf_send import send_all_pdfs

# --------------------------------------------------------------------------------
# Дата классы
# --------------------------------------------------------------------------------


@dataclass
class Bank_customer:
    """Банковские реквизиты заказчика"""
    name: str  # наименование банка
    BIC: str  # БИК
    current_account: str  # расчётный счёт
    corporate_account: str  # корреспондентский счёт


@dataclass
class Bank_executor:
    """Банковские реквизиты исполнителя"""
    name: str  # наименование банка
    BIC: str  # БИК
    current_account: str  # расчётный счёт
    corporate_account: str  # корреспондентский счёт


@dataclass
class Executor:
    """Исполнитель"""
    name: str  # полное название юридического лица, наприемер, ООО «Рога и копыта»
    INN: str  # ИНН
    OGRN: str  # ОГРН или ОГРНИП
    address: str  # юридический адрес
    signatory: str  # подписант
    bank: Bank_customer  # банковские реквизиты заказчика

@dataclass
class Customer:
    """Заказчик"""
    name: str  # полное название юридического лица, наприемер, ООО «Рога и копыта»
    INN: str  # ИНН
    OGRN: str  # ОГРН или ОГРНИП
    address: str  # юридический адрес
    signatory: str  # подписант
    bank: Bank_executor  # банковские реквизиты заказчика


@dataclass
class Job:
    task: str  # выполненная задача
    price: int  # цена за задачу



# --------------------------------------------------------------------------------
# Инструменты агента
# --------------------------------------------------------------------------------


@tool
def generate_pdf_act(customer: Customer, executor: Executor, jobs: list[Job],  user_id: int) -> None:
    """
    Генерирует PDF-акт, в котором заполнены данные
    клиента, его банковские реквизиты, а также выполненные задачи

    Args:
        customer (Customer): данные клиента
        jobs (list[Job]): список выполненных задач для внесения в акт

    Returns:
        None
    """

    
    # ---- Все временные файлы и pdf файл с актом сохраняются в typst/<user_id> ----
    user_folder = os.path.join("typst", str(user_id))
    os.makedirs(user_folder, exist_ok=True)

    
    # ---- Создаём пути к json и pdf ----
    act_json_path = os.path.join(user_folder, "act.json")
    act_pdf_path = os.path.join(user_folder, "act.pdf")


    # ---- Сохраняем JSON ----
    act_json = {
        "customer": asdict(customer),
        "executor": asdict(executor),
        "jobs": list(map(
            lambda j: asdict(j), jobs
        )),
    }

    with open(act_json_path, "w", encoding="utf-8") as f:
        json.dump(act_json, f, ensure_ascii=False, indent=2)

    

    # ---- Загружаем шаблон ----
    typst_template_path = "typst/act.typ"
    with open(typst_template_path, "r", encoding="utf-8") as f:
        template = f.read()

    
    relative_json_path = "act.json"

    template = template.replace(
        '#let act = json("act.json")',
        f'#let act = json("{relative_json_path}")'
    )

    temp_typ_path = os.path.join(user_folder, "act_user.typ")

    with open(temp_typ_path, "w", encoding="utf-8") as f:
        f.write(template)


    # ---- Создаём команду для компиляции pdf файла и исполняем её ----
    command = [
        TYPST_BIN,
        "compile",
        "--root",
        "./typst",
        temp_typ_path,
        act_pdf_path
    ]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
    except subprocess.CalledProcessError as e:
        print(e.stderr)



# --------------------------------------------------------------------------------
# Агент
# --------------------------------------------------------------------------------


class LLMAgent:
    def __init__(self, model: LanguageModelLike, tools: Sequence[BaseTool]):
        self._model = model
        self._agent = create_react_agent(
            model,
            tools=tools,
            checkpointer=MemorySaver())
        self._config: RunnableConfig = {
                "configurable": {"thread_id": uuid.uuid4().hex}}

    def upload_file(self, file):
        print(f"upload file {file} to LLM")
        file_uploaded_id = self._model.upload_file(file).id_  # type: ignore
        return file_uploaded_id

    def invoke(
        self,
        content: str,
        attachments: list[str]|None=None,
        temperature: float=0.1
    ) -> str:
        """Отправляет сообщение в чат"""
        message: dict = {
            "role": "user",
            "content": content,
            **({"attachments": attachments} if attachments else {}) 
        }
        return self._agent.invoke(
            {
                "messages": [message],
                "temperature": temperature
            },
            config=self._config)["messages"][-1].content


# --------------------------------------------------------------------------------
# Настройки и константы
# --------------------------------------------------------------------------------


user_private_router = Router()

TYPST_BIN = os.path.join("typst", "typst.exe")

SYSTEM_PROMPT = (
        "Твоя задача сгенерировать бухгалтерский докумет (пока ты можешь генерировать только акт выполненых работ)"
        "Для этого тебе надо взять реквизиты контрагента и реквизиты исполнителя из памяти,"
        "Никакие данные не придумывай, всё необходимое строго запроси у пользователя "
        "Все реквизиты тебе переданы в память. Для генерации документов используй данные тебе иснрументы "
        "Имя и отчество подписанта сокращаем до одной первой буквы, например, Иванов А.Е. "
        "Если в сообщении содержится [USER_ID:XXXX], передавай это значение в инструмент как параметр user_id"
        "Название компании оборачиваем в кавычки ёлочкой, например, "
        "ООО «Рога и копыта», то есть до названия компании ставим « и после названия ставим ». "
    )




# --------------------------------------------------------------------------------
# Инициализация агента
# --------------------------------------------------------------------------------


model = GigaChat(
    model="GigaChat-2-Max",
    verify_ssl_certs=False,
)
agent = LLMAgent(model, tools=[generate_pdf_act])


# --------------------------------------------------------------------------------
# Обработчики
# --------------------------------------------------------------------------------

# ---- Команда старт ----
@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(hello_text)


# ---- Команда info (информирует пользователя) ----
@user_private_router.message(Command("информация"))
async def info_cmd(message: types.Message):
    await message.answer(hello_text)


# ---- Команда "команды" (информирует пользователя о имеющихся в его распоряжении командах) ----
@user_private_router.message(Command("команды"))
async def cmd_cmd(message: types.Message):
    await message.answer(commands_text)


# ---- Команда документы (информирует пользователя о тех документах, которые может генерировать бот) ----
@user_private_router.message(Command("документы"))
async def documents_cmd(message: types.Message):
    await message.answer(documents_text)


# ---- Команда новый (обнуляет предыдущие действия) ----
@user_private_router.message(Command("новый"))
async def new_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отправьте файл с реквизитами исполнителя")
    await state.set_state(ReqFiles.waiting_executor_file)


# ---- Команда реквизиты (запускает FSM для создания файла с реквизитами, которые введёт пользователь) ----
@user_private_router.message(Command("реквизиты"))
async def requisites_cmd(message: types.Message, state: FSMContext):
    pass
    


# --------------------------------------------------------------------------------
# FSM для получения файлов с реквизитами и диалога с пользователем
# --------------------------------------------------------------------------------


class ReqFiles(StatesGroup):
    waiting_executor_file = State()
    waiting_client_file = State()
    chatting = State()


# ---- Универсальная функция для получения файлов с реквизитами ----
@user_private_router.message(StateFilter(ReqFiles.waiting_executor_file, ReqFiles.waiting_client_file), F.document)
async def handle_file(message: types.Message, state: FSMContext, bot):
    current_state = await state.get_state()


    doc = message.document
    file_id = doc.file_id
    file_name = doc.file_name

    mime_type, _ = mimetypes.guess_type(file_name)
    if not mime_type:
        mime_type = "application/octet-stream"


    # ---- Временное имя файла ----
    if current_state == ReqFiles.waiting_executor_file.state:
        file_label = "my"
        next_state = ReqFiles.waiting_client_file
        prompt = "Файл реквизитов исполнителя получен! Теперь отправьте файл с реквизитами заказчик."

    elif current_state == ReqFiles.waiting_client_file.state:
        file_label = "client"
        next_state = ReqFiles.chatting
        prompt = (
        "Файл реквизитов заказчика получен!\n"
        "Теперь отравьте работы для включения в акт, например:\n"
        "\n1) Поставка стеклотары - 40 000 рублей.\n"
        "2) Поставка этикеток - 30 000 рублей."
        )
        


    else:
        await message.answer("Сначала отправьте файл с ревизитами")
        return

    # ---- Скачиваем файл в память ----
    buffer = BytesIO()
    buffer.name = file_name

    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, buffer)
    buffer.seek(0)


    # ---- Загружаем файл в LLM ----
    llm_file_id = agent.upload_file(buffer)


    # ---- Сохраняем file_id в FSM ----
    await state.update_data({f"{file_label}_file_id": llm_file_id})

    # ---- Если это первый файл → просто ждём второй ----
    if next_state != ReqFiles.chatting:
        await message.answer(prompt)
        await state.set_state(next_state)
        return
    elif next_state == ReqFiles.chatting:
        # Загружаем оба file_id
        await message.answer(prompt)
        data = await state.get_data()
        my_file_id = data.get("my_file_id")
        client_file_id = data.get("client_file_id")

        # ---- Отправляем system_prompt агенту и получаем ответ----
        agent.invoke(
            content=SYSTEM_PROMPT,
            attachments=[my_file_id, client_file_id]
        )
        


        # ---- Переходим в режим диалога и отправляем ответ агента ----
        await state.set_state(ReqFiles.chatting)





@user_private_router.message(ReqFiles.chatting)
async def agent_chat(message: types.Message, state: FSMContext, bot: Bot):

    # ---- Получаем данные из FSM и user_id ----
    user_id = message.from_user.id
    data = await state.get_data()
    client_reqs_file_id = data.get("client_file_id")


    # ---- Вызываем агента, передаём ему данные ----
    response = agent.invoke(
        content=f"[USER_ID:{user_id}]\n{message.text}",
        attachments=[client_reqs_file_id]
    )

    
    # ---- Создаём путь к папке с файлами ----
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder_path = os.path.join(base_dir, "typst", str(user_id))


    # ---- проверка, существует ли директория (она существует только если произошла генерация). Если директории нет, то агент - отвечает на обвчные вопросы ----
    if os.path.isdir(folder_path):
        await message.answer(response)
        await send_all_pdfs(message, folder_path)
    else:
        await message.answer(response)

    

