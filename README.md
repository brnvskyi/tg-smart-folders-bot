# Smart Folders Bot

Telegram бот для создания умных папок и автоматической пересылки сообщений.

## Возможности

- Авторизация через QR-код или API credentials
- Создание каналов для папок Telegram
- Автоматическая пересылка сообщений из папок в каналы
- Мониторинг и метрики
- Защита от дубликатов сообщений

## Развертывание на Railway

1. Форкните репозиторий
2. Создайте новый проект на Railway.com
3. Подключите ваш репозиторий
4. Добавьте следующие переменные окружения:
   - `API_ID` - ID вашего Telegram приложения
   - `API_HASH` - Hash вашего Telegram приложения
   - `BOT_TOKEN` - Токен вашего бота
   - `DATA_DIR` - Путь для хранения данных (например, "./data")
   - `ENABLE_METRICS` - true/false для включения метрик
   - `FORWARD_DELAY` - Задержка между пересылками (в секундах)
   - `FOLDER_CACHE_TTL` - Время жизни кэша папок (в секундах)

5. Нажмите Deploy

## Локальная разработка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение:
   ```bash
   python -m venv venv
   source venv/bin/activate  # для Linux/Mac
   venv\Scripts\activate  # для Windows
   ```
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Создайте файл .env с необходимыми переменными окружения
5. Запустите бота:
   ```bash
   python -m app
   ```

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── bot.py           # Main bot class
│   ├── config.py        # Configuration management
│   ├── handlers.py      # Message handlers
│   ├── logger.py        # Logging setup
│   ├── session.py       # Session management
│   └── user_session.py  # User session handling
├── data/
│   ├── logs/           # Log files
│   └── user_data/      # Encrypted user sessions
├── main.py             # Entry point
├── requirements.txt    # Dependencies
└── .env               # Environment variables
```

## Requirements

- Python 3.8 or higher
- Telegram API credentials (API_ID and API_HASH)
- Bot token from @BotFather

## Security Features

- QR code-based authentication
- Optional session encryption
- Secure file permissions for sensitive data
- Circuit breaker pattern for handling connection issues
- Automatic session cleanup on authentication failures

## Error Handling

The bot implements robust error handling:
- Automatic reconnection with exponential backoff
- Circuit breaker pattern to prevent excessive reconnection attempts
- Structured logging with request tracking
- Graceful degradation on failures

## Logging

Logs are stored in `data/logs/` with the following features:
- Request ID tracking across log entries
- Rotating file handler (10MB per file, 5 backups)
- Configurable log level
- Comprehensive error reporting

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Telethon](https://github.com/LonamiWebs/Telethon) for the Telegram client implementation
- [Pydantic](https://pydantic-docs.helpmanual.io/) for configuration management
- [QRCode](https://github.com/lincolnloop/python-qrcode) for QR code generation