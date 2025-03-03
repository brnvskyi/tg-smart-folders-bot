from telethon import TelegramClient, events
from telethon.sessions import MemorySession
import asyncio
from .config import settings
from .logger import setup_logger
from .session import SessionManager
from .handlers import MessageHandlers
from .user_session import UserSession
from telethon.errors import FloodWaitError

logger = setup_logger(__name__)

class TelegramBot:
    def __init__(self):
        """Initialize bot instance"""
        self.bot = TelegramClient(
            MemorySession(),
            api_id=settings.API_ID,
            api_hash=settings.API_HASH
        )
        self.users = {}
        self.session_manager = SessionManager()
        self.handlers = None
    
    async def setup(self):
        """Initialize bot and register event handlers"""
        try:
            logger.info("Starting bot initialization...")
            
            # Initialize bot with alternative servers
            self.bot = TelegramClient(
                'bot', 
                settings.API_ID, 
                settings.API_HASH,
                connection_retries=None,
                system_version="4.16.30-vxCUSTOM",
                device_model="VPS",
                app_version="1.0",
                use_ipv6=True,
                server=('149.154.167.50', 443)  # Alternative Telegram server
            )
            await self.bot.start(bot_token=settings.BOT_TOKEN)
            
            # Register handlers
            self.bot.add_event_handler(self.handle_start, events.NewMessage(pattern='/start'))
            self.bot.add_event_handler(self.handle_help, events.NewMessage(pattern='/help'))
            self.bot.add_event_handler(self.handle_auth, events.NewMessage(pattern='/auth'))
            self.bot.add_event_handler(self.handle_message, events.NewMessage)
            
            logger.info("Bot initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Error during bot initialization: {e}")
            raise
    
    async def get_user_session(self, user_id: int) -> UserSession:
        """Get or create user session with improved error handling"""
        try:
            if user_id not in self.users:
                self.users[user_id] = UserSession(user_id, self)
            return self.users[user_id]
        except Exception as e:
            logger.error(f"Error getting user session: {e}", exc_info=True)
            raise
    
    async def check_connections(self):
        """Periodically check and maintain connections"""
        while True:
            try:
                for user_id, session in self.users.items():
                    if session.is_authorized:
                        try:
                            # Check connection state
                            if not session.client or not session.client.is_connected():
                                logger.warning(f"Detected disconnection for user {user_id}")
                                if not await session.ensure_connected():
                                    logger.warning(f"Failed to restore connection for user {user_id}")
                                    continue
                            
                            # Check authorization
                            try:
                                if not await session.client.is_user_authorized():
                                    logger.warning(f"Detected authorization loss for user {user_id}")
                                    session.is_authorized = False
                                    if not await session.init_client():
                                        logger.error(f"Failed to reinitialize client for user {user_id}")
                                        continue
                            except Exception as e:
                                logger.error(f"Error checking authorization for user {user_id}: {e}")
                                continue
                            
                            # Check functionality with simple request
                            try:
                                me = await session.client.get_me()
                                if not me:
                                    logger.warning(f"Failed to get user info for {user_id}")
                                    if not await session.init_client():
                                        logger.error(f"Failed to reinitialize client for user {user_id}")
                            except Exception as e:
                                logger.error(f"Error checking functionality for user {user_id}: {e}")
                                if not await session.init_client():
                                    logger.error(f"Failed to reinitialize client for user {user_id}")
                                
                        except Exception as e:
                            logger.error(f"Error checking user {user_id}: {e}")
                            
            except Exception as e:
                logger.error(f"Error in connection check: {e}", exc_info=True)
                
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def run(self):
        """Run the bot"""
        try:
            max_retries = settings.MAX_RECONNECT_ATTEMPTS
            retry_delay = settings.RETRY_DELAY
            
            for attempt in range(max_retries):
                try:
                    await self.setup()
                    await self.bot.run_until_disconnected()
                    break
                    
                except FloodWaitError as e:
                    wait_time = e.seconds
                    minutes = wait_time // 60
                    seconds = wait_time % 60
                    logger.warning(
                        f"Hit rate limit on attempt {attempt + 1}/{max_retries}. "
                        f"Waiting {minutes} minutes and {seconds} seconds before retry..."
                    )
                    await asyncio.sleep(wait_time)
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.error(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(f"Critical error running bot: {e}")
                        raise
                        
        except Exception as e:
            logger.error(f"Critical error running bot: {e}")
            raise 