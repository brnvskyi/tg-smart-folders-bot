# Telegram Folder Bot

Бот для создания агрегационных каналов на основе папок Telegram.

## Возможности

- Авторизация через QR-код
- Создание каналов на основе папок
- Автоматическая пересылка сообщений
- Управление несколькими папками

## Установка

1. Клонируйте репозиторий:
bash
git clone https://github.com/mikhailmurzak/tg-smart-folders-bot.git
cd tg-smart-folders-bot

2. Установите pip (если не установлен):
bash
python3 get-pip.py

3. Установите зависимости:
bash
pip3 install -r requirements.txt

4. Создайте файл .env и добавьте необходимые переменные:
bash
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token

5. Запустите бота:
bash
python3 bot.py

## Получение API ключей

1. Получите `API_ID` и `API_HASH`:
   - Перейдите на https://my.telegram.org
   - Войдите в свой аккаунт
   - Перейдите в 'API development tools'
   - Создайте новое приложение
   - Скопируйте API_ID и API_HASH

2. Получите `BOT_TOKEN`:
   - Найдите @BotFather в Telegram
   - Отправьте команду /newbot
   - Следуйте инструкциям
   - Скопируйте полученный токен

## Использование

1. Отправьте команду /start боту
2. Отсканируйте QR-код для авторизации
3. Выберите папки для создания каналов
4. Готово! Бот будет пересылать сообщения из каналов выбранных папок

## Структура проекта
telegram-folder-bot/
├── bot.py # Основной файл бота
├── get-pip.py # Установщик pip
├── requirements.txt # Зависимости проекта
├── .env # Конфигурация (не включена в репозиторий)
├── logs/ # Директория для логов
└── user_data/ # Данные пользователей

## Разработка

1. Создайте fork репозитория
2. Создайте ветку для новой функции:
bash
git checkout -b feature/my-new-feature

3. Внесите изменения и создайте коммит:
bash
git add .
git commit -m "Add new feature"

4. Отправьте изменения в свой fork:
bash
git push origin feature/my-new-feature

5. Создайте Pull Request

## Требования

- Python 3.7 или выше
- pip (установщик включен в репозиторий)
- Доступ к Telegram API
- Стабильное интернет-соединение

## Лицензия

MIT