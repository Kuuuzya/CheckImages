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
from google_search import GoogleImageSearchClient
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
google_client = GoogleImageSearchClient()
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
        "Я найду все места публикации через Google Search API (Google Lens) "
        "и с помощью алгоритмов и ChatGPT определю, есть ли среди них запрещенные фотобанки."
    )
    await message.reply(welcome_text)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "<b> Инструкция:</b>\n\n"
        "• Отправьте ссылку на картинку (например: <code>https://site.com/image.jpg</code>)\n"
        "• Или отправьте файл/фотографию прямо в чат.\n\n"
        "Бот выполнит обратно-поисковый запрос через Google Lens API и выявит наличие коммерческих фотобанков (Shutterstock, Getty, Lori, Adobe Stock и др.)."
    )
    await message.reply(help_text)

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status_msg = await message.reply(" Получил фото. Загружаю и запускаю поиск в Google Lens...")
    try:
        photo = message.photo[-1]
        buffer = io.BytesIO()
        await bot.download(photo.file_id, destination=buffer)
        image_bytes = buffer.getvalue()

        file_info = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_info.file_path}"

        await process_image_input(message, status_msg, image_bytes=image_bytes, image_url=file_url)
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        await status_msg.edit_text(" Произошла ошибка при обработке фотографии.")

@dp.message(F.document)
async def handle_document(message: types.Message):
    doc = message.document
    mime = (doc.mime_type or "").lower()
    filename = (doc.file_name or "").lower()

    if mime.startswith("image/") or filename.endswith(IMAGE_EXTENSIONS):
        status_msg = await message.reply(" Получил файл изображения. Загружаю и ищу в Google Lens...")
        try:
            buffer = io.BytesIO()
            await bot.download(doc.file_id, destination=buffer)
            image_bytes = buffer.getvalue()

            file_info = await bot.get_file(doc.file_id)
            file_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_info.file_path}"

            await process_image_input(message, status_msg, image_bytes=image_bytes, image_url=file_url)
        except Exception as e:
            logger.error(f"Ошибка при обработке документа-картинки: {e}")
            await status_msg.edit_text(" Произошла ошибка при обработке файла.")
    else:
        await message.reply(" Пожалуйста, присылайте файлы изображений (.jpg, .png, .webp и т.д.) или ссылки.")

@dp.message(F.text)
async def handle_text(message: types.Message):
    text = message.text.strip()
    urls = re.findall(URL_REGEX, text)
    
    if not urls:
        await message.reply(" Пожалуйста, отправьте корректную ссылку на изображение (HTTP/HTTPS) или загрузите фото/файл.")
        return

    image_url = urls[0]
    status_msg = await message.reply(" Принял ссылку. Ищу совпадения в Google Lens...")
    await process_image_input(message, status_msg, image_url=image_url)

async def process_image_input(
    message: types.Message,
    status_msg: types.Message,
    image_bytes: bytes = None,
    image_url: str = None
):
    try:
        await status_msg.edit_text(" Поиск точных совпадений через Google Lens API...")
        
        all_found_urls = set()
        err_messages = []

        # Поиск выполняет ТОЛЬКО ДВИЖОК GOOGLE (Google Lens / Google Cloud Vision)
        if settings.serpapi_key or settings.google_api_key:
            g_urls, g_err = await google_client.search_by_image_url(image_url)
            if g_err:
                err_messages.append(f"Google: {g_err}")
            else:
                all_found_urls.update(g_urls)
        else:
            err_messages.append("Google API ключи (SERPAPI_KEY или GOOGLE_API_KEY) не указаны в файле .env")

        await evaluate_results_and_reply(
            status_msg,
            list(all_found_urls),
            "\n".join(err_messages) if not all_found_urls and err_messages else "",
            image_bytes=image_bytes,
            image_url=image_url
        )
    except Exception as e:
        logger.error(f" Ошибка в процессе проверки: {e}", exc_info=True)
        await status_msg.edit_text(f" Произошла ошибка при выполнении проверки: {e}")

async def evaluate_results_and_reply(
    status_msg: types.Message,
    found_urls: list[str],
    error_msg: str,
    image_bytes: bytes = None,
    image_url: str = None
):
    if error_msg:
        await status_msg.edit_text(f"<b> Ошибка Google API:</b>\n{error_msg}")
        return

    if not found_urls:
        warning_text = (
            "<b> ПРЕДУПРЕЖДЕНИЕ!</b>\n\n"
            "Данное изображение <b>ранее нигде не было опубликовано</b> в Интернете "
            "(Google Lens не нашел ни одной точной копии этой картинки)."
        )
        await status_msg.edit_text(warning_text)
        return

    await status_msg.edit_text(f" Найдено источников через Google: {len(found_urls)}. Проверяю на совпадения с фотобанками...")
    photobanks_found = await verifier.verify_urls(
        found_urls,
        original_image_bytes=image_bytes,
        original_image_url=image_url
    )

    if photobanks_found:
        result_text = "<b>НАЙДЕНО! Запрещено!</b>\n\n"
        result_text += f"<b>Обнаружены совпадения в фотобанках ({len(photobanks_found)}):</b>\n\n"
        
        items_list = list(photobanks_found.items())
        for idx, (url, name) in enumerate(items_list, 1):
            line = f"{idx}. <b>{name}</b>:\n{url}\n\n"
            if len(result_text) + len(line) > 3900:
                result_text += f"<i>...и еще {len(items_list) - idx + 1} ссылок на фотобанки</i>"
                break
            result_text += line

        await status_msg.edit_text(result_text, disable_web_page_preview=True)
    else:
        clean_text = (
            "<b> Фотобанки не обнаружены.</b>\n\n"
            f"Проверено {len(found_urls)} источников через Google. Совпадений с коммерческими фотобанками не найдено."
        )
        await status_msg.edit_text(clean_text)

async def main():
    if not settings.telegram_bot_token:
        print(" ОШИБКА: TELEGRAM_BOT_TOKEN не задан!")
        return

    print(" Бот (Google Lens) успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
