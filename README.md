# Telegram Bot: Проверка изображений на наличие в фотобанках (CheckImages)

Бот для Telegram, который принимает ссылку на картинку (или фото), выполняет обратный поиск по картинке через **Yandex Search API** (`search-images-by-pic`), выгружает список всех сайтов, где опубликовано это изображение, и с помощью встроенного списка фотобанков и **OpenAI ChatGPT API** проверяет, есть ли среди них лицензионные фотобанки или стоки.

Если фотобанк найден, бот отвечает:
> **НАЙДЕНО! Запрещено!**
> Ссылки на фотобанки...

---

## 🛠 Быстрый старт

### 1. Установка зависимостей

Убедитесь, что у вас установлен Python 3.10 или выше. Выполните команду:

```bash
pip install -r requirements.txt
```

### 2. Настройка конфигурации (`.env`)

Скопируйте файл `.env.example` в `.env`:

```bash
cp .env.example .env
```

Откройте файл `.env` и заполните ключи:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ  # Токен от @BotFather
YANDEX_API_KEY=AQVN...                              # API-ключ Yandex Cloud
YANDEX_FOLDER_ID=b1g...                             # Folder ID Yandex Cloud
OPENAI_API_KEY=sk-...                               # Ваш API-ключ OpenAI
OPENAI_MODEL=gpt-4o-mini                             # Модель ChatGPT (gpt-4o-mini, gpt-4o и т.д.)
```

---

##  Инструкции по получению ключей

### 1. Telegram Bot Token
1. Откройте [@BotFather](https://t.me/BotFather) в Telegram.
2. Отправьте команду `/newbot` и следуйте инструкциям.
3. Скопируйте полученный API token в поле `TELEGRAM_BOT_TOKEN` в `.env`.

### 2. Yandex Search API (Поиск по картинке)
Документация: [Yandex Search API: search-images-by-pic](https://aistudio.yandex.ru/docs/ru/search-api/operations/search-images-by-pic.html)

1. Зайдите в консоль [Yandex Cloud](https://console.yandex.cloud/) или [Yandex AI Studio](https://aistudio.yandex.ru/).
2. Создайте каталог (Folder) и скопируйте его **Folder ID** (укажите в `YANDEX_FOLDER_ID`).
3. Подключите сервис **Search API**.
4. Перейдите в раздел **Сервисные аккаунты** и создайте аккаунт с ролью `search-api.user`.
5. Создайте **API-ключ** для сервисного аккаунта и скопируйте его в `YANDEX_API_KEY`.

### 3. OpenAI API (ChatGPT)
1. Зайдите в личный кабинет [OpenAI Platform](https://platform.openai.com/api-keys).
2. Создайте новый API Key и скопируйте его в `OPENAI_API_KEY`.
3. Модель в `OPENAI_MODEL` по умолчанию установлена в `gpt-4o-mini` (быстрая и экономичная). Вы также можете использовать `gpt-4o`.

---

## 🚀 Запуск бота

Для запуска бота выполните:

```bash
python3 bot.py
```

При успешном запуске в консоли появится:
```text
 Бот успешно запущен и готов к работе!
```

---

## 📁 Структура проекта

- `bot.py` — основной файл запуска Telegram бота и обработки сообщений.
- `yandex_search.py` — модуль работы с Yandex Search API (обратный поиск изображений).
- `photobanks.py` — базы данных российских и международных фотобанков/стоков и логика сопоставления доменов.
- `verifier.py` — модуль проверки URL-адресов через локальную базу и OpenAI ChatGPT API.
- `config.py` — загрузка и валидация настроек из `.env`.
- `requirements.txt` — зависимости Python.
- `.env.example` — шаблон файла настроек.
