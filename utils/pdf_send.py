# --------------------------------------------------------------------------------
# Утилита отправки pdf файлов
# --------------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------------


import os
import shutil


from aiogram import types
from aiogram.types import FSInputFile 


# --------------------------------------------------------------------------------
# Функция отправки
# --------------------------------------------------------------------------------


async def send_all_pdfs(message: types.Message, folder_path: str):
    for filename in os.listdir(folder_path):
        # ---- Проверяем является ли файл в папке pdf файлом и отправляем его ----
        if filename.lower().endswith(".pdf"):
            file_path = os.path.join(folder_path, filename)
            await message.answer_document(FSInputFile(file_path))
    
    # ---- По окончании процесса удаляем папку, чтобы не хранить персональные данные ----
    shutil.rmtree(folder_path)
    return