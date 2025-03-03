from telethon import events, Button
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.functions.channels import CreateChannelRequest
from telethon.tl.types import DialogFilter
from telethon.errors import FloodWaitError
import qrcode
from io import BytesIO
import asyncio
import time
from app.logger import setup_logger
from app.config import settings
from app.cache import async_cached, folder_cache
from app.queue_manager import MessageQueue
from app.monitoring import metrics
from telethon.sync import TelegramClient
from telethon.sessions import MemorySession

logger = setup_logger(__name__)

class MessageHandlers:
    def __init__(self, bot):
        self.bot = bot
        self.message_queue = MessageQueue()
        self.message_cache = {}  # Cache for deduplication
        self.cache_ttl = 60  # TTL for message cache in seconds
        
    def _get_message_key(self, message):
        """Generate unique key for message deduplication"""
        return f"{message.chat_id}:{message.id}:{int(time.time() / self.cache_ttl)}"
        
    def _is_duplicate(self, message):
        """Check if message is a duplicate"""
        key = self._get_message_key(message)
        if key in self.message_cache:
            return True
        self.message_cache[key] = time.time()
        # Cleanup old cache entries
        current_time = time.time()
        self.message_cache = {
            k: v for k, v in self.message_cache.items()
            if current_time - v < self.cache_ttl
        }
        return False
        
    @async_cached(ttl=settings.FOLDER_CACHE_TTL)
    async def get_dialog_filters(self, user_session):
        """Get dialog filters with caching"""
        return await user_session.client(GetDialogFiltersRequest())
        
    async def show_folders(self, event, user_session, page=0):
        try:
            dialog_filters = await self.get_dialog_filters(user_session)
            page_size = 8  # Number of folders per page
            
            # Filter valid folders
            valid_folders = [
                f for f in dialog_filters.filters 
                if isinstance(f, DialogFilter) and hasattr(f, 'id') and hasattr(f, 'title') and f.title
            ]
            
            total_folders = len(valid_folders)
            total_pages = (total_folders + page_size - 1) // page_size
            
            # Update metrics
            metrics.update_active_folders(total_folders)
            
            # Get folders for current page
            start_idx = page * page_size
            end_idx = start_idx + page_size
            current_page_filters = valid_folders[start_idx:end_idx]
            
            buttons = []
            for folder in current_page_filters:
                folder_id_str = str(folder.id)
                is_active = folder_id_str in user_session.active_folders
                status = "[✓]" if is_active else "[ ]"
                button_text = f"{status} {folder.title}"
                buttons.append([Button.inline(button_text, f"folder_{folder.id}")])
            
            # Add navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append(Button.inline("◀️ Back", f"page_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(Button.inline("Next ▶️", f"page_{page+1}"))
            
            if nav_buttons:
                buttons.append(nav_buttons)
            
            # Store current page in event for reference
            event.current_page = page
            
            await event.respond(
                f"Select folders to create channels (Page {page+1}/{total_pages}):",
                buttons=buttons
            )
            
        except Exception as e:
            logger.error(f"Error showing folders: {e}")
            await event.respond("Error getting folder list. Please try again later.")
    
    async def handle_folder_selection(self, event, user_session):
        """Handle folder selection callback"""
        try:
            # Extract folder ID from callback data
            folder_id = int(event.data.decode().split('_')[1])
            
            try:
                # Answer callback immediately with empty response
                await event.answer("")
            except Exception as e:
                logger.warning(f"Could not answer callback: {e}")
            
            # Get folder info
            dialog_filters = await self.get_dialog_filters(user_session)
            selected_folder = next(
                (f for f in dialog_filters.filters 
                 if isinstance(f, DialogFilter) and hasattr(f, 'id') and f.id == folder_id),
                None
            )
            
            if not selected_folder:
                await event.respond("Folder not found")
                return
            
            try:
                # Toggle folder activation
                folder_id_str = str(folder_id)
                if folder_id_str in user_session.active_folders:
                    await self.deactivate_folder(user_session, folder_id_str)
                    await event.respond(f"Folder {selected_folder.title} deactivated")
                else:
                    await self.activate_folder(user_session, selected_folder)
                    await event.respond(f"Folder {selected_folder.title} activated")
                
                # Update folder list
                current_page = getattr(event, 'current_page', 0)
                await self.show_folders(event, user_session, page=current_page)
                
            except Exception as e:
                logger.error(f"Error toggling folder {folder_id}: {e}")
                await event.respond("Failed to process folder selection")
                
        except ValueError:
            logger.error("Invalid folder ID in callback data")
            await event.respond("Invalid folder selection")
        except Exception as e:
            logger.error(f"Error handling folder selection: {e}")
            await event.respond("An error occurred while processing your request")
    
    async def activate_folder(self, user_session, folder):
        try:
            # Try to use existing channel first
            channel = await self.get_or_create_channel(user_session, folder)
            if not channel:
                return False
            
            folder_id_str = str(folder.id)
            user_session.active_folders[folder_id_str] = {
                'channel_id': channel.id,
                'title': folder.title
            }
            
            # Setup message forwarding with queue
            await self.setup_message_forwarding(user_session, folder, channel.id)
            return True
            
        except Exception as e:
            logger.error(f"Error activating folder: {e}")
            return False
    
    async def deactivate_folder(self, user_session, folder_id_str):
        try:
            # Stop message queue processing
            if folder_id_str in user_session.active_folders:
                channel_id = user_session.active_folders[folder_id_str]['channel_id']
                self.message_queue.stop_processing(channel_id)
            
            if folder_id_str in user_session.folder_handlers:
                user_session.client.remove_event_handler(
                    user_session.folder_handlers[folder_id_str]
                )
                del user_session.folder_handlers[folder_id_str]
            
            if folder_id_str in user_session.active_folders:
                del user_session.active_folders[folder_id_str]
                
        except Exception as e:
            logger.error(f"Error deactivating folder: {e}")
    
    def _get_folder_title(self, folder):
        """Get readable folder title"""
        if hasattr(folder, 'title'):
            if hasattr(folder.title, 'text'):
                return folder.title.text
            return str(folder.title)
        return "Unnamed folder"

    async def get_or_create_channel(self, user_session, folder):
        try:
            folder_id_str = str(folder.id)
            folder_title = self._get_folder_title(folder)
            data = self.bot.session_manager.load_session(user_session.user_id)
            folder_channels = data.get('folder_channels', {})
            
            if folder_id_str in folder_channels:
                try:
                    channel_data = folder_channels[folder_id_str]
                    
                    # Try to get channel through dialogs first
                    channel = None
                    async for dialog in user_session.client.iter_dialogs():
                        if dialog.is_channel and dialog.id == channel_data['channel_id']:
                            channel = dialog.entity
                            logger.info(f"Found channel {channel_data['channel_id']} for folder '{folder_title}'")
                            break
                    
                    if channel:
                        # Проверяем, что мы все еще администратор канала
                        if channel.admin_rights:
                            return channel
                        else:
                            logger.warning(f"Lost admin rights in channel {channel.id} for folder '{folder_title}', creating new one")
                    else:
                        logger.warning(f"Channel {channel_data['channel_id']} for folder '{folder_title}' not found in dialogs, creating new one")
                        
                    # Удаляем старую информацию о канале
                    del folder_channels[folder_id_str]
                    self.bot.session_manager.save_session(user_session.user_id, {
                        'session_string': user_session.session_string,
                        'active_folders': user_session.active_folders,
                        'folder_channels': folder_channels
                    })
                    
                except Exception as e:
                    logger.error(f"Error getting existing channel for folder '{folder_title}': {e}")
            
            # Create new channel
            try:
                result = await user_session.client(CreateChannelRequest(
                    title=f"📁 {folder_title}",
                    about=f"Aggregator for folder {folder_title}",
                    megagroup=False
                ))
                
                if not result or not result.chats:
                    logger.error(f"Failed to create channel for folder '{folder_title}': Empty response")
                    return None
                    
                channel = result.chats[0]
                
                # Verify channel creation
                if not channel or not channel.id:
                    logger.error(f"Failed to create channel for folder '{folder_title}': Invalid channel data")
                    return None
                
                # Save channel info
                folder_channels[folder_id_str] = {
                    'channel_id': channel.id,
                    'title': folder_title,
                    'created_at': int(time.time())
                }
                self.bot.session_manager.save_session(user_session.user_id, {
                    'session_string': user_session.session_string,
                    'active_folders': user_session.active_folders,
                    'folder_channels': folder_channels
                })
                
                logger.info(f"Created new channel {channel.id} for folder '{folder_title}'")
                return channel
                
            except FloodWaitError as e:
                logger.warning(f"FloodWaitError while creating channel for folder '{folder_title}': {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
                return await self.get_or_create_channel(user_session, folder)
                
        except Exception as e:
            logger.error(f"Error in get_or_create_channel for folder '{self._get_folder_title(folder)}': {e}")
            return None
    
    async def setup_message_forwarding(self, user_session, folder, channel_id):
        """Настройка пересылки сообщений для папки"""
        folder_title = self._get_folder_title(folder)
        logger.info(f"Настройка пересылки для папки '{folder_title}'")
        
        folder_id_str = str(folder.id)
        
        # Удаляем существующий обработчик для этой папки, если есть
        if folder_id_str in user_session.folder_handlers:
            try:
                old_handler = user_session.folder_handlers[folder_id_str]
                user_session.client.remove_event_handler(old_handler)
                logger.info(f"Удален старый обработчик для папки '{folder_title}'")
            except Exception as e:
                logger.error(f"Ошибка при удалении старого обработчика для папки '{folder_title}': {e}")
        
        # Кэшируем список peer_ids для папки
        included_peers = []
        for peer in folder.include_peers:
            try:
                if hasattr(peer, 'channel_id'):
                    included_peers.append(peer.channel_id)
                elif hasattr(peer, 'chat_id'):
                    included_peers.append(peer.chat_id)
                elif hasattr(peer, 'user_id'):
                    included_peers.append(peer.user_id)
            except Exception as e:
                logger.error(f"Ошибка при получении peer ID для папки '{folder_title}': {e}")
                continue
        
        if not included_peers:
            logger.warning(f"Папка '{folder_title}' не содержит каналов")
            return
            
        async def forward_handler(event):
            try:
                if not event.message:
                    return
                    
                if not await user_session.ensure_connected():
                    logger.warning("Не удалось восстановить соединение")
                    return

                # Проверяем на дубликаты
                if self._is_duplicate(event.message):
                    logger.debug("Пропущено дублирующееся сообщение")
                    return

                chat = await event.get_chat()
                if not chat:
                    return
                    
                logger.info(f"Получено сообщение из чата {chat.id} для папки '{folder_title}'")
                
                if chat.id in included_peers:
                    # Добавляем небольшую задержку для избежания флуда
                    await asyncio.sleep(settings.FORWARD_DELAY)
                    
                    try:
                        await user_session.client.forward_messages(
                            channel_id,
                            event.message,
                            silent=True
                        )
                        logger.info(f"Сообщение успешно переслано в канал {channel_id} папки '{folder_title}'")
                        
                        # Обновляем метрики
                        metrics.increment_forwarded_messages()
                        
                    except FloodWaitError as e:
                        logger.warning(f"Флуд-ожидание {e.seconds} секунд для папки '{folder_title}'")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        logger.error(f"Ошибка при пересылке для папки '{folder_title}': {e}")
                        if "Could not find the input entity" in str(e):
                            await user_session.init_client()
                
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения для папки '{folder_title}': {e}", exc_info=True)
        
        # Регистрируем новый обработчик с фильтром по чатам
        handler = user_session.client.add_event_handler(
            forward_handler,
            events.NewMessage(chats=included_peers)
        )
        user_session.folder_handlers[folder_id_str] = handler
        logger.info(f"Зарегистрирован новый обработчик для папки '{folder_title}' с {len(included_peers)} каналами")
    
    async def start_auth_process(self, event, user_session):
        """Начать процесс авторизации пользователя"""
        try:
            # Инициализируем клиент с данными из настроек бота
            if not user_session.client:
                user_session.client = TelegramClient(
                    MemorySession(),
                    api_id=settings.API_ID,
                    api_hash=settings.API_HASH
                )
            
            if not user_session.client.is_connected():
                await user_session.client.connect()
            
            # Генерируем QR-код
            qr_login = await user_session.client.qr_login()
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_login.url)
            qr.make(fit=True)
            
            # Создаем изображение QR-кода
            img = qr.make_image(fill_color="black", back_color="white")
            img_buffer = BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # Отправляем приветствие и QR-код
            welcome_text = (
                "👋 Добро пожаловать в Smart Folders Bot!\n\n"
                "📱 Для быстрой авторизации отсканируйте QR-код:\n"
                "1. Откройте Telegram на телефоне\n"
                "2. Перейдите в Настройки → Устройства\n"
                "3. Нажмите 'Подключить устройство'\n"
                "4. Отсканируйте QR-код\n\n"
                "❓ Если не получается использовать QR-код, отправьте команду /manual для авторизации через API credentials"
            )
            
            await event.respond(welcome_text, file=img_buffer)
            
            try:
                # Ждем подтверждения авторизации
                logger.info("Waiting for QR login confirmation...")
                user = await qr_login.wait()
                
                # Сохраняем сессию
                user_session.is_authorized = True
                user_session.session_string = user_session.client.session.save()
                self.bot.session_manager.save_session(user_session.user_id, {
                    'session_string': user_session.session_string,
                    'active_folders': user_session.active_folders
                })
                
                await event.respond("✅ Авторизация успешно завершена!")
                await self.show_folders(event, user_session)
                
            except asyncio.TimeoutError:
                logger.warning("QR login timeout")
                await event.respond(
                    "⚠️ Время ожидания истекло.\n"
                    "Попробуйте еще раз отправив /start\n"
                    "Или используйте ручную авторизацию через /manual"
                )
            except Exception as e:
                logger.error(f"Error during QR login: {e}")
                await event.respond(
                    "❌ Ошибка при авторизации через QR-код.\n"
                    "Попробуйте еще раз отправив /start\n"
                    "Или используйте ручную авторизацию через /manual"
                )
                
        except Exception as e:
            logger.error(f"Error in QR auth process: {e}")
            await event.respond(
                "❌ Не удалось создать QR-код.\n"
                "Пожалуйста, используйте ручную авторизацию:\n"
                "Отправьте команду /manual"
            )

    async def handle_manual_auth(self, event, user_session):
        """Запуск процесса ручной авторизации через API credentials"""
        auth_text = (
            "Для ручной авторизации выполните следующие шаги:\n\n"
            "1️⃣ Перейдите на https://my.telegram.org/apps\n"
            "2️⃣ Войдите в свой аккаунт\n"
            "3️⃣ Создайте новое приложение\n"
            "4️⃣ Скопируйте API ID и API Hash\n"
            "5️⃣ Отправьте их боту в формате:\n"
            "/auth API_ID API_HASH\n\n"
            "Например: /auth 123456 abcdef1234567890abcdef"
        )
        await event.respond(auth_text)

    async def handle_auth_choice(self, event, user_session):
        """Обработка выбора способа авторизации"""
        choice = event.message.text.strip()
        
        if choice == "1" or choice == "1️⃣":
            # QR-код
            try:
                # Инициализируем клиент с данными из настроек бота
                if not user_session.client:
                    user_session.client = TelegramClient(
                        MemorySession(),
                        api_id=settings.API_ID,
                        api_hash=settings.API_HASH
                    )
                
                if not user_session.client.is_connected():
                    await user_session.client.connect()
                
                # Генерируем QR-код
                qr_login = await user_session.client.qr_login()
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(qr_login.url)
                qr.make(fit=True)
                
                # Создаем изображение QR-кода
                img = qr.make_image(fill_color="black", back_color="white")
                img_buffer = BytesIO()
                img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                # Отправляем QR-код и инструкции
                await event.respond(
                    "📱 Отсканируйте этот QR-код в официальном приложении Telegram:\n\n"
                    "1. Откройте Telegram на телефоне\n"
                    "2. Перейдите в Настройки → Устройства\n"
                    "3. Нажмите 'Подключить устройство'\n"
                    "4. Отсканируйте этот QR-код",
                    file=img_buffer
                )
                
                try:
                    # Ждем подтверждения авторизации
                    logger.info("Waiting for QR login confirmation...")
                    user = await qr_login.wait()
                    
                    # Сохраняем сессию
                    user_session.is_authorized = True
                    user_session.session_string = user_session.client.session.save()
                    self.bot.session_manager.save_session(user_session.user_id, {
                        'session_string': user_session.session_string,
                        'active_folders': user_session.active_folders
                    })
                    
                    await event.respond("✅ Авторизация через QR-код успешно завершена!")
                    await self.show_folders(event, user_session)
                    
                except asyncio.TimeoutError:
                    logger.warning("QR login timeout")
                    await event.respond(
                        "⚠️ Время ожидания авторизации истекло.\n"
                        "Попробуйте еще раз или используйте авторизацию через API credentials:\n"
                        "/auth API_ID API_HASH"
                    )
                except Exception as e:
                    logger.error(f"Error during QR login: {e}")
                    await event.respond(
                        "❌ Ошибка при авторизации через QR-код.\n"
                        "Попробуйте использовать альтернативный способ:\n"
                        "/auth API_ID API_HASH"
                    )
                
            except Exception as e:
                logger.error(f"Error creating QR code: {e}")
                await event.respond(
                    "❌ Не удалось создать QR-код.\n"
                    "Пожалуйста, используйте авторизацию через API credentials:\n"
                    "/auth API_ID API_HASH"
                )
                
        elif choice == "2" or choice == "2️⃣":
            # API credentials
            auth_text = (
                "Для авторизации через API credentials выполните следующие шаги:\n\n"
                "1️⃣ Перейдите на https://my.telegram.org/apps\n"
                "2️⃣ Войдите в свой аккаунт\n"
                "3️⃣ Создайте новое приложение\n"
                "4️⃣ Скопируйте API ID и API Hash\n"
                "5️⃣ Отправьте их боту в формате:\n"
                "/auth API_ID API_HASH\n\n"
                "Например: /auth 123456 abcdef1234567890abcdef"
            )
            await event.respond(auth_text)
        else:
            await event.respond(
                "❌ Неверный выбор!\n"
                "Отправьте 1️⃣ для QR-кода или 2️⃣ для API credentials"
            )

    async def handle_auth_command(self, event, user_session):
        """Обработка команды /auth"""
        try:
            # Получаем API ID и API Hash из сообщения
            args = event.message.text.split()[1:]
            if len(args) != 2:
                await event.respond(
                    "❌ Неверный формат команды!\n"
                    "Используйте: /auth API_ID API_HASH\n"
                    "Например: /auth 123456 abcdef1234567890abcdef"
                )
                return

            api_id = args[0]
            api_hash = args[1]

            try:
                api_id = int(api_id)
            except ValueError:
                await event.respond("❌ API ID должен быть числом!")
                return

            # Сохраняем API credentials
            user_session.api_id = api_id
            user_session.api_hash = api_hash
            
            # Запрашиваем номер телефона
            user_session.awaiting_phone = True
            await event.respond(
                "📱 Пожалуйста, отправьте ваш номер телефона в международном формате:\n"
                "Например: +79001234567"
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке команды /auth: {e}")
            await event.respond("❌ Произошла ошибка. Пожалуйста, попробуйте позже.") 