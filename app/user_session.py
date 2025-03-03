from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import DialogFilter
import logging
import asyncio
from app.logger import setup_logger
from app.config import settings

logger = setup_logger(__name__)

class UserSession:
    def __init__(self, user_id: int, bot):
        self.user_id = user_id
        self.bot = bot
        self.client = None
        self.is_authorized = False
        self.session_string = None
        self.active_folders = {}
        self.folder_handlers = {}
        
        # Auth fields
        self.api_id = None
        self.api_hash = None
        self.phone = None
        self.awaiting_auth_choice = False
        self.awaiting_phone = False
        self.awaiting_code = False
    
    async def init_client(self) -> bool:
        """Initialize user client with improved error handling"""
        try:
            if self.session_string:
                # Try to restore from saved session
                self.client = TelegramClient(
                    StringSession(self.session_string),
                    api_id=settings.API_ID,
                    api_hash=settings.API_HASH
                )
            else:
                # Create new session
                self.client = TelegramClient(
                    StringSession(),
                    api_id=self.api_id or settings.API_ID,
                    api_hash=self.api_hash or settings.API_HASH
                )
            
            if not self.client.is_connected():
                await self.client.connect()
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing client for user {self.user_id}: {e}")
            return False
            
    async def ensure_connected(self) -> bool:
        """Ensure client is connected and authorized"""
        try:
            if not self.client or not self.client.is_connected():
                if not await self.init_client():
                    return False
            
            if not await self.client.is_user_authorized():
                self.is_authorized = False
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking connection for user {self.user_id}: {e}")
            return False
    
    async def restore_channels(self):
        """Restore channel connections with improved error handling"""
        try:
            if not await self.ensure_connected():
                logger.error("Failed to establish connection for channel restoration")
                return
            
            data = self.bot.session_manager.load_session(self.user_id)
            folder_channels = data.get('folder_channels', {})
            
            # Get current folders
            dialog_filters = await self.client(GetDialogFiltersRequest())
            current_folders = {
                str(f.id): f 
                for f in dialog_filters.filters 
                if isinstance(f, DialogFilter) and hasattr(f, 'id') and hasattr(f, 'title')
            }
            
            # Restore active folders
            for folder_id, channel_data in folder_channels.items():
                if folder_id in current_folders:
                    folder = current_folders[folder_id]
                    try:
                        channel_id = channel_data['channel_id']
                        
                        # Try to get channel through dialogs first
                        channel = None
                        async for dialog in self.client.iter_dialogs():
                            if dialog.is_channel and dialog.id == channel_id:
                                channel = dialog.entity
                                logger.info(f"Found channel {channel_id} in dialogs")
                                break
                        
                        if not channel:
                            logger.warning(f"Channel {channel_id} not found in dialogs, skipping")
                            continue
                        
                        self.active_folders[folder_id] = {
                            'channel_id': channel.id,
                            'title': channel_data['title']
                        }
                        await self.bot.handlers.setup_message_forwarding(self, folder, channel.id)
                        logger.info(f"Restored folder {folder.title} with channel {channel.id}")
                        
                    except Exception as e:
                        logger.error(f"Error restoring channel for folder {folder.title}: {e}")
                        # Keep the folder data even if we couldn't restore it
                        if folder_id not in self.active_folders:
                            self.active_folders[folder_id] = channel_data
            
            # Save updated data
            self.bot.session_manager.save_session(self.user_id, {
                'session_string': self.session_string,
                'active_folders': self.active_folders,
                'folder_channels': folder_channels
            })
            
        except Exception as e:
            logger.error(f"Error restoring channels: {e}", exc_info=True) 