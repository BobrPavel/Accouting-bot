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

from aiogram import types, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from langchain_core.language_models import LanguageModelLike
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langchain_gigachat.chat_models import GigaChat
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver



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
def generate_pdf_act(customer: Customer, executor: Executor, jobs: list[Job]) -> None:
    """
    Генерирует PDF-акт, в котором заполнены данные
    клиента, его банковские реквизиты, а также выполненные задачи

    Args:
        customer (Customer): данные клиента
        jobs (list[Job]): список выполненных задач для внесения в акт

    Returns:
        None
    """
    act_json = {
        "customer": asdict(customer),
        "executor": asdict(executor),
        "jobs": list(map(
            lambda j: asdict(j), jobs
        ))
    }
    with open(os.path.join("typst", "act.json"), "w", encoding="utf-8") as f:
        json.dump(act_json, f, ensure_ascii=False)
    command = [TYPST_BIN, "compile", "--root", "./typst", "typst/act.typ"]
    try:
        subprocess.run(command,
                       check=True,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, 
                       text=True,
                       encoding="utf-8")
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
# Настройки
# --------------------------------------------------------------------------------


user_private_router = Router()

TYPST_BIN = os.path.join("typst", "typst.exe")

SYSTEM_PROMPT = (
        "Твоя задача сгенерировать акт выполненых работ"
        "Для этого тебе надо взять реквизиты контрагента и реквизиты исполнителя из памяти,"
        "Запроси работы для включения в акт (наименования задач и их стоимость), работ может быть несколько. "
        "Если пользователь указывает в качетсве работы курс, то для документов берём одну работу, в точности такую "
        "\"Обучение одного сотрудника на курсе «Хардкорная веб-разработка»\", стоимостью 170 тыс руб."
        "Никакие данные не придумывай, всё необходимое строго запроси у "
        "пользователя. Все реквизиты тебе переданы в память. Для генерации документов используй данные тебе иснрументы "
        "Имя и отчество подписанта сокращаем до одной первой буквы, "
        "например, Иванов А.Е. "
        "Название компании оборачиваем в кавычки ёлочкой, например, "
        "ООО «Рога и копыта», то есть до названия компании ставим « и после названия "
        "ставим »."
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


@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await message.answer("Приветсвую! Я бот для генерации актов и счетов. Отправь мне файл с вашими реквизитам")
    await state.set_state(ReqFiles.waiting_my_file)


@user_private_router.message(Command("new"))
async def new_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Всё что было, то забыто. Пора начать всё с чистого листа. Отправьте файл с реквизитами исполнителя")
    await state.set_state(ReqFiles.waiting_my_file)


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
        file_label = "my"
        next_state = ReqFiles.waiting_client_file
        prompt = "Файл реквизитов исполнителя получен! Теперь отправьте файл с реквизитами заказчик."

    elif current_state == ReqFiles.waiting_client_file.state:
        file_label = "client"
        next_state = ReqFiles.chatting
        prompt = "Файл реквизитов заказчика получен!"

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

        # ---- Отправляем system_prompt агенту ----
        agent.invoke(
            content=SYSTEM_PROMPT,
            attachments=[my_file_id, client_file_id]
        )

        # ---- Переходим в режим диалога ----
        await state.set_state(ReqFiles.chatting)





@user_private_router.message(ReqFiles.chatting)
async def agent_chat(message: types.Message, state: FSMContext):

    data = await state.get_data()
    client_reqs_file_id = data.get("client_file_id")

    # Вызываем агента
    response = agent.invoke(
        content=message.text,
        attachments=[client_reqs_file_id]
    )

    await message.answer(response)

