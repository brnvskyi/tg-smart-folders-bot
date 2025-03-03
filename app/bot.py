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
        """Initialize bot and register handlers"""
        try:
            logger.info("Starting bot initialization...")
            
            try:
                # Ensure bot is properly connected
                if not self.bot.is_connected():
                    await self.bot.connect()
                
                await self.bot.start(bot_token=settings.BOT_TOKEN)
            except FloodWaitError as e:
                wait_time = e.seconds
                minutes = wait_time // 60
                seconds = wait_time % 60
                logger.warning(
                    f"Hit rate limit during initialization. "
                    f"Waiting {minutes} minutes and {seconds} seconds before retry..."
                )
                await asyncio.sleep(wait_time)
                await self.bot.start(bot_token=settings.BOT_TOKEN)
            
            # Initialize handlers
            self.handlers = MessageHandlers(self)
            
            # Register command handlers
            @self.bot.on(events.NewMessage(pattern='/start'))
            async def start_handler(event):
                try:
                    user_id = event.sender_id
                    logger.info(f"Received /start command from user {user_id}")
                    
                    user_session = await self.get_user_session(user_id)
                    if not user_session:
                        await event.respond("❌ Не удалось инициализировать сессию. Попробуйте позже.")
                        return
                        
                    if not user_session.is_authorized:
                        await self.handlers.start_auth_process(event, user_session)
                    else:
                        await self.handlers.show_folders(event, user_session)
                        
                except Exception as e:
                    logger.error(f"Error in start handler: {e}")
                    await event.respond("❌ Произошла ошибка. Попробуйте позже.")

            @self.bot.on(events.NewMessage(pattern='/auth'))
            async def auth_handler(event):
                try:
                    user_id = event.sender_id
                    logger.info(f"Received /auth command from user {user_id}")
                    
                    user_session = await self.get_user_session(user_id)
                    if not user_session:
                        await event.respond("Failed to initialize user session. Please try again later.")
                        return
                    
                    await self.handlers.handle_auth_command(event, user_session)
                    
                except Exception as e:
                    logger.error(f"Error in auth handler: {e}")
                    await event.respond("An error occurred. Please try again later.")

            @self.bot.on(events.NewMessage(pattern='/manual'))
            async def manual_auth_handler(event):
                try:
                    user_id = event.sender_id
                    logger.info(f"Received /manual command from user {user_id}")
                    
                    user_session = await self.get_user_session(user_id)
                    if not user_session:
                        await event.respond("❌ Не удалось инициализировать сессию. Попробуйте позже.")
                        return
                    
                    await self.handlers.handle_manual_auth(event, user_session)
                    
                except Exception as e:
                    logger.error(f"Error in manual auth handler: {e}")
                    await event.respond("❌ Произошла ошибка. Попробуйте позже.")

            @self.bot.on(events.NewMessage())
            async def message_handler(event):
                try:
                    if event.message.text.startswith('/'):  # Skip commands
                        return
                        
                    user_id = event.sender_id
                    user_session = await self.get_user_session(user_id)
                    if not user_session:
                        return
                        
                    # Handle auth choice
                    if hasattr(user_session, 'awaiting_auth_choice') and user_session.awaiting_auth_choice:
                        user_session.awaiting_auth_choice = False
                        await self.handlers.handle_auth_choice(event, user_session)
                        return
                        
                    # Handle phone number input
                    if hasattr(user_session, 'awaiting_phone') and user_session.awaiting_phone:
                        phone = event.message.text.strip()
                        if not phone.startswith('+'):
                            await event.respond("📱 Пожалуйста, введите номер телефона в формате +79001234567")
                            return
                            
                        try:
                            # Initialize client with API credentials
                            if not user_session.client:
                                user_session.client = TelegramClient(
                                    MemorySession(),
                                    api_id=user_session.api_id,
                                    api_hash=user_session.api_hash
                                )
                            
                            if not user_session.client.is_connected():
                                await user_session.client.connect()
                            
                            # Send confirmation code
                            await user_session.client.send_code_request(phone)
                            user_session.phone = phone
                            user_session.awaiting_phone = False
                            user_session.awaiting_code = True
                            
                            await event.respond(
                                "📱 Код подтверждения отправлен на ваш номер.\n"
                                "Пожалуйста, введите полученный код:"
                            )
                        except FloodWaitError as e:
                            wait_time = e.seconds
                            minutes = wait_time // 60
                            seconds = wait_time % 60
                            await event.respond(
                                f"⚠️ Слишком много попыток. Пожалуйста, подождите {minutes} минут и {seconds} секунд."
                            )
                        except Exception as e:
                            logger.error(f"Error sending code: {e}")
                            await event.respond("❌ Ошибка при отправке кода. Пожалуйста, попробуйте позже.")
                        
                    # Handle confirmation code input
                    elif hasattr(user_session, 'awaiting_code') and user_session.awaiting_code:
                        code = event.message.text.strip()
                        try:
                            # Проверяем подключение клиента
                            if not user_session.client or not user_session.client.is_connected():
                                await event.respond("❌ Ошибка подключения. Пожалуйста, начните авторизацию заново с команды /auth")
                                return
                            
                            # Sign in with code
                            await user_session.client.sign_in(user_session.phone, code)
                            user_session.is_authorized = True
                            user_session.awaiting_code = False
                            
                            # Save session
                            user_session.session_string = user_session.client.session.save()
                            self.session_manager.save_session(user_session.user_id, {
                                'session_string': user_session.session_string,
                                'active_folders': user_session.active_folders
                            })
                            
                            await event.respond("✅ Авторизация успешно завершена! Теперь вы можете использовать бота.")
                            await self.handlers.show_folders(event, user_session)
                            
                        except Exception as e:
                            logger.error(f"Error signing in: {e}")
                            await event.respond("❌ Ошибка при авторизации. Возможно, код неверный. Попробуйте еще раз.")
                except Exception as e:
                    logger.error(f"Error in message handler: {e}")
                    await event.respond("An error occurred. Please try again later.")
            
            # Register callback handlers
            @self.bot.on(events.CallbackQuery(pattern=r"folder_(\d+)"))
            async def folder_callback_handler(event):
                try:
                    user_id = event.sender_id
                    user_session = await self.get_user_session(user_id)
                    if not user_session:
                        await event.answer("Session error. Please restart the bot.")
                        return
                        
                    await self.handlers.handle_folder_selection(event, user_session)
                    
                except Exception as e:
                    logger.error(f"Error in folder callback: {e}")
                    await event.answer("An error occurred. Please try again.")
            
            @self.bot.on(events.CallbackQuery(pattern=r"page_(\d+)"))
            async def page_callback_handler(event):
                try:
                    user_id = event.sender_id
                    user_session = await self.get_user_session(user_id)
                    if not user_session:
                        await event.answer("Session error. Please restart the bot.")
                        return
                        
                    page = int(event.data.decode().split('_')[1])
                    await event.answer("")
                    await self.handlers.show_folders(event, user_session, page=page)
                    
                except Exception as e:
                    logger.error(f"Error in page callback: {e}")
                    await event.answer("An error occurred. Please try again.")
            
            logger.info("Bot successfully initialized")
            logger.info("Bot is ready")
            
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