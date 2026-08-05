import asyncio
import io
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from yandex_search import YandexImageSearchClient
from verifier import ImageVerifier

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
) if settings.telegram_bot_token else None

dp = Dispatcher()
yandex_client = YandexImageSearchClient()
verifier = ImageVerifier()

URL_REGEX = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.heic')

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "<b> Добро пожаловать!</b>\n\n"
        "Я бот для проверки изображений на предмет использования коммерческих <b>фотобанков</b> и стоков.\n\n"
        "<b> Как пользоваться:</b>\n"
        "1. Отправьте мне <b>ссылку на картинку</b> (HTTP/HTTPS).\n"
        "2. Или прикрепите <b>фотографию</b> прямо в чат.\n"
        "3. Или отправьте <b>файл изображения</b> как документ.\n\n"
        "Я найду все места публикации изображения через Yandex Search API "
        "и с помощью алгоритмов и ChatGPT определю, есть ли среди них запрещенные фотобанки."
    )
    await message.reply(welcome_text)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "<b> Инструкция:</b>\n\n"
        "• Отправьте ссылку на картинку (например: <code>https://site.com/image.jpg</code>)\n"
        "• Или отправьте файл/фотографию прямо в чат.\n\n"
        "Бот выполнит обратно-поисковый запрос через Яндекс API и выявит наличие коммерческих фотобанков (Shutterstock, Getty, Lori, Adobe Stock и др.)."
    )
    await message.reply(help_text)

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """
    Обработчик присланной фотографии в чат
    """
    status_msg = await message.reply(" Получил фото. Загружаю и запускаю поиск в Яндексе...")
    try:
        # Берем фото наивысшего качества
        photo = message.photo[-1]
        buffer = io.BytesIO()
        await bot.download(photo.file_id, destination=buffer)
        image_bytes = buffer.getvalue()

        await process_image_bytes(message, status_msg, image_bytes)
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        await status_msg.edit_text(" Произошла ошибка при обработке фотографии.")

@dp.message(F.document)
async def handle_document(message: types.Message):
    """
    Обработчик присланных файлов (документов)
    """
    doc = message.document
    mime = (doc.mime_type or "").lower()
    filename = (doc.file_name or "").lower()

    if mime.startswith("image/") or filename.endswith(IMAGE_EXTENSIONS):
        status_msg = await message.reply(" Получил файл изображения. Загружаю и ищу в Яндексе...")
        try:
            buffer = io.BytesIO()
            await bot.download(doc.file_id, destination=buffer)
            image_bytes = buffer.getvalue()

            await process_image_bytes(message, status_msg, image_bytes)
        except Exception as e:
            logger.error(f"Ошибка при обработке документа-картинки: {e}")
            await status_msg.edit_text(" Произошла ошибка при обработке файла.")
    else:
        await message.reply(" Пожалуйста, присылайте файлы изображений (.jpg, .png, .webp и т.д.) или ссылки.")

@dp.message(F.text)
async def handle_text(message: types.Message):
    """
    Обработчик текстовых сообщений со ссылками
    """
    text = message.text.strip()
    urls = re.findall(URL_REGEX, text)
    
    if not urls:
        await message.reply(" Пожалуйста, отправьте корректную ссылку на изображение (HTTP/HTTPS) или загрузите фото/файл.")
        return

    image_url = urls[0]
    status_msg = await message.reply(" Принял ссылку. Ищу совпадения в Яндексе...")
    await process_image_url(message, status_msg, image_url)

async def process_image_bytes(message: types.Message, status_msg: types.Message, image_bytes: bytes):
    """
    Процесс обработки байтового файла картинки
    """
    try:
        await status_msg.edit_text(" Поиск публикаций изображения через Yandex Search API...")
        found_urls = await yandex_client.search_by_image_bytes(image_bytes)
        await evaluate_results_and_reply(status_msg, found_urls)
    except Exception as e:
        logger.error(f" Ошибка в процессе проверки: {e}", exc_info=True)
        await status_msg.edit_text(" Произошла ошибка при выполнении проверки.")

async def process_image_url(message: types.Message, status_msg: types.Message, image_url: str):
    """
    Процесс обработки URL ссылки на картинку
    """
    try:
        await status_msg.edit_text(" Поиск публикаций изображения через Yandex Search API...")
        found_urls = await yandex_client.search_by_image_url(image_url)
        await evaluate_results_and_reply(status_msg, found_urls)
    except Exception as e:
        logger.error(f" Ошибка в процессе проверки: {e}", exc_info=True)
        await status_msg.edit_text(" Произошла ошибка при выполнении проверки.")

async def evaluate_results_and_reply(status_msg: types.Message, found_urls: list[str]):
    """
    Анализирует найденные урлы на фотобанки и отправляет вердикт
    """
    if not found_urls:
        warning_text = (
            "<b> ПРЕДУПРЕЖДЕНИЕ!</b>\n\n"
            "Данное изображение <b>ранее нигде не было опубликовано</b> в Интернете "
            "(Яндекс не нашел ни одной копии этой картинки)."
        )
        await status_msg.edit_text(warning_text)
        return

    await status_msg.edit_text(f" Найдено источников: {len(found_urls)}. Проверяю на наличие фотобанков...")
    photobanks_found = await verifier.verify_urls(found_urls)

    if photobanks_found:
        result_text = "<b>НАЙДЕНО! Запрещено!</b>\n\n"
        result_text += "<b>Найдены следующие фотобанки:</b>\n"
        
        for idx, (url, name) in enumerate(photobanks_found.items(), 1):
            result_text += f"{idx}. <b>{name}</b>:\n{url}\n\n"

        await status_msg.edit_text(result_text, disable_web_page_preview=True)
    else:
        clean_text = (
            "<b> Фотобанки не обнаружены.</b>\n\n"
            f"Проверено {len(found_urls)} источников, совпадений с заблокированными фотобанками и стоками не найдено."
        )
        await status_msg.edit_text(clean_text)

async def main():
    if not settings.telegram_bot_token:
        print(" ОШИБКА: TELEGRAM_BOT_TOKEN не задан!")
        return

    print(" Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
