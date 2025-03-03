"""
Main entry point for the bot
"""

import asyncio
import logging
from app.bot import TelegramBot
from app.logger import setup_logger
from app.config import settings
from app.monitoring import metrics

logger = setup_logger(__name__)

async def main():
    """Main function"""
    try:
        # Initialize bot
        bot = TelegramBot()
        
        # Start metrics server if enabled
        if settings.ENABLE_METRICS:
            await metrics.start()
            
        # Start bot
        await bot.start()
        
        # Keep running
        await bot.run_forever()
        
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise
    finally:
        if settings.ENABLE_METRICS:
            await metrics.stop()

if __name__ == "__main__":
    try:
        # Run main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise 