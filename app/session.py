from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import TextWithEntities
import json
import os
import time
import functools
from cryptography.fernet import Fernet
from .config import settings
from .logger import setup_logger

logger = setup_logger(__name__)

def circuit_breaker(max_failures=5, reset_timeout=300):
    def decorator(func):
        failures = 0
        last_failure_time = 0
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal failures, last_failure_time
            
            if failures >= max_failures:
                current_time = time.time()
                if current_time - last_failure_time < reset_timeout:
                    logger.warning(f"Circuit breaker open, skipping call to {func.__name__}")
                    return None
                failures = 0
            
            try:
                result = await func(*args, **kwargs)
                failures = 0
                return result
            except Exception as e:
                failures += 1
                last_failure_time = time.time()
                logger.error(f"Circuit breaker: Error in {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator

class SessionManager:
    def __init__(self):
        self.storage_dir = os.path.join(settings.DATA_DIR, 'user_data')
        self.encryption_key = settings.ENCRYPTION_KEY.encode() if settings.ENCRYPTION_KEY else None
    
    def _serialize_data(self, data):
        """Convert Telethon objects to JSON-serializable format"""
        if isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, TextWithEntities):
            return str(data)
        elif hasattr(data, 'to_dict'):
            return data.to_dict()
        return data
        
    def _encrypt_data(self, data: dict) -> bytes:
        if not self.encryption_key:
            return json.dumps(self._serialize_data(data)).encode()
        f = Fernet(self.encryption_key)
        return f.encrypt(json.dumps(self._serialize_data(data)).encode())
    
    def _decrypt_data(self, encrypted_data: bytes) -> dict:
        if not self.encryption_key:
            return json.loads(encrypted_data.decode())
        f = Fernet(self.encryption_key)
        return json.loads(f.decrypt(encrypted_data).decode())
    
    async def create_client(self, session_string=None) -> TelegramClient:
        client = TelegramClient(
            StringSession(session_string) if session_string else StringSession(),
            settings.API_ID,
            settings.API_HASH,
            device_model='Desktop',
            system_version='Windows 10',
            app_version='1.0',
            flood_sleep_threshold=120,
            request_retries=15,
            connection_retries=15,
            retry_delay=10,
            timeout=120,
            auto_reconnect=True
        )
        await client.connect()
        return client
    
    def save_session(self, user_id: int, data: dict):
        try:
            file_path = os.path.join(self.storage_dir, f'{user_id}.session')
            encrypted_data = self._encrypt_data(data)
            with open(file_path, 'wb') as f:
                f.write(encrypted_data)
            os.chmod(file_path, 0o600)  # Secure file permissions
            logger.info(f"Session data saved for user {user_id}")
        except Exception as e:
            logger.error(f"Error saving session for user {user_id}: {e}")
            raise
    
    def load_session(self, user_id: int) -> dict:
        try:
            file_path = os.path.join(self.storage_dir, f'{user_id}.session')
            if not os.path.exists(file_path):
                return {'active_folders': {}, 'folder_channels': {}}
            
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            data = self._decrypt_data(encrypted_data)
            logger.info(f"Session data loaded for user {user_id}")
            return data
        except Exception as e:
            logger.error(f"Error loading session for user {user_id}: {e}")
            return {'active_folders': {}, 'folder_channels': {}}
    
    @circuit_breaker(max_failures=5, reset_timeout=300)
    async def ensure_connected(self, client: TelegramClient) -> bool:
        if not client or not client.is_connected():
            await client.connect()
        return await client.is_user_authorized()
    
    async def cleanup_session(self, user_id: int):
        try:
            data = self.load_session(user_id)
            # Clear session string but keep folder data
            data['session_string'] = None
            self.save_session(user_id, data)
            logger.info(f"Session cleaned up for user {user_id}")
        except Exception as e:
            logger.error(f"Error cleaning up session for user {user_id}: {e}")
            raise 