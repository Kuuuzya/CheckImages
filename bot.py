import asyncio
import logging
import re
from urllib.parse import urlparse
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

# Инициализация бота и диспетчера
bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
) if settings.telegram_bot_token else None

dp = Dispatcher()
yandex_client = YandexImageSearchClient()
verifier = ImageVerifier()

URL_REGEX = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Обработчик команды /start
    """
    welcome_text = (
        "<b> Добро пожаловать!</b>\n\n"
        "Я бот для проверки изображений на предмет использования коммерческих <b>фотобанков</b> и стоков.\n\n"
        "<b> Как пользоваться:</b>\n"
        "1. Отправьте мне <b>ссылку на картинку</b> в тексте сообщения.\n"
        "2. Или просто пришлите <b>фотографию</b> прямо в чат.\n\n"
        "Я найду все места публикации изображения через Yandex Search API "
        "и с помощью алгоритмов и ChatGPT определю, есть ли среди них запрещенные фотобанки."
    )
    await message.reply(welcome_text)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """
    Обработчик команды /help
    """
    help_text = (
        "<b> Инструкция:</b>\n\n"
        "• Отправьте ссылку на изображение (например: <code>https://example.com/image.jpg</code>)\n"
        "• Или отправьте файл фотографии в чат.\n\n"
        "Бот выполнит обратно-поисковый запрос через Яндекс API и выявит наличие лицензионных фотобанков (Shutterstock, Getty, Lori, Adobe Stock и др.)."
    )
    await message.reply(help_text)

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """
    Обработчик загруженных фотографий
    """
    status_msg = await message.reply(" Получил фото. Получаю ссылку и запускаю проверку...")
    try:
        # Берем фото наивысшего качества
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        # Формируем прямую ссылку на фото через Telegram API
        file_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_info.file_path}"

        await process_image_url(message, status_msg, file_url)
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        await status_msg.edit_text(" Произошла ошибка при обработке фотографии.")

@dp.message(F.text)
async def handle_text(message: types.Message):
    """
    Обработчик текстовых сообщений со ссылками
    """
    text = message.text.strip()
    
    # Ищем ссылки в тексте
    urls = re.findall(URL_REGEX, text)
    if not urls:
        await message.reply(" Пожалуйста, отправьте корректную ссылку на изображение (HTTP/HTTPS) или загрузите фото.")
        return

    image_url = urls[0]
    status_msg = await message.reply(f" Принял ссылку. Ищу совпадения в Яндексе...")
    await process_image_url(message, status_msg, image_url)

async def process_image_url(message: types.Message, status_msg: types.Message, image_url: str):
    """
    Основной процесс проверки ссылки на изображение
    """
    try:
        # 1. Поиск совпадений через Яндекс API
        await status_msg.edit_text(" Поиск публикаций изображения через Yandex Search API...")
        found_urls = await yandex_client.search_by_image_url(image_url)

        if not found_urls:
            warning_text = (
                "<b> ПРЕДУПРЕЖДЕНИЕ!</b>\n\n"
                "Данное изображение <b>ранее нигде не было опубликовано</b> в Интернете "
                "(Яндекс не нашел ни одной копии этой картинки)."
            )
            await status_msg.edit_text(warning_text)
            return

        # 2. Проверка найденных URL на фотобанки (локально + ChatGPT)
        await status_msg.edit_text(f" Найдено источников: {len(found_urls)}. Проверяю на наличие фотобанков...")
        photobanks_found = await verifier.verify_urls(found_urls)

        # 3. Формирование ответа по спецификации
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

    except Exception as e:
        logger.error(f" Ошибка в процессе проверки: {e}", exc_info=True)
        await status_msg.edit_text(" Произошла ошибка при выполнении проверки. Попробуйте позже.")

async def main():
    if not settings.telegram_bot_token:
        print(" ОШИБКА: TELEGRAM_BOT_TOKEN не задан в .env файле!")
        print(" Пожалуйста, создайте файл .env на основе .env.example и укажите токен.")
        return

    print(" Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
