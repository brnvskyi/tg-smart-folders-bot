import asyncio
import sys
from app.bot import TelegramBot
from app.logger import setup_logger

logger = setup_logger(__name__)

async def main():
    try:
        bot = TelegramBot()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        sys.exit(1) 