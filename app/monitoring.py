import time
from typing import Dict, Optional
import asyncio
from aiohttp import web
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from app.logger import setup_logger
from app.config import settings

logger = setup_logger(__name__)

# Define metrics
message_forward_total = Counter(
    'telegram_message_forwards_total',
    'Total number of forwarded messages',
    ['status']
)

message_forward_duration = Histogram(
    'telegram_message_forward_duration_seconds',
    'Time spent forwarding messages',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

active_users = Gauge(
    'telegram_active_users',
    'Number of active users'
)

active_folders = Gauge(
    'telegram_active_folders',
    'Number of active folders'
)

queue_size = Gauge(
    'telegram_queue_size',
    'Current size of message queues',
    ['channel_id']
)

class MetricsCollector:
    def __init__(self):
        self.forwarded_messages = 0
        self.active_folders = 0
        self.active_users = set()
        self.errors = 0
        self._server: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
    
    async def start(self):
        """Start metrics server if enabled"""
        if not settings.ENABLE_METRICS:
            return
        
        try:
            app = web.Application()
            app.router.add_get('/metrics', self._metrics_handler)
            
            self._server = app
            self._runner = web.AppRunner(app)
            await self._runner.setup()
            
            self._site = web.TCPSite(
                self._runner,
                settings.METRICS_HOST,
                settings.METRICS_PORT
            )
            await self._site.start()
            
            logger.info(f"Metrics server started on {settings.METRICS_HOST}:{settings.METRICS_PORT}")
            
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
    
    async def stop(self):
        """Stop metrics server"""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        
        self._server = None
        self._runner = None
        self._site = None
    
    async def _metrics_handler(self, request):
        """Handle metrics endpoint request"""
        return web.Response(
            body=generate_latest(),
            content_type='text/plain'
        )
    
    def increment_forwarded_messages(self):
        """Увеличить счетчик пересланных сообщений"""
        self.forwarded_messages += 1
        if self.forwarded_messages % 100 == 0:
            logger.info(f"Всего переслано сообщений: {self.forwarded_messages}")
    
    def update_active_folders(self, count):
        """Обновить количество активных папок"""
        self.active_folders = count
        logger.info(f"Активных папок: {count}")
    
    def add_active_user(self, user_id):
        """Добавить активного пользователя"""
        self.active_users.add(user_id)
        logger.info(f"Активных пользователей: {len(self.active_users)}")
    
    def increment_errors(self):
        """Увеличить счетчик ошибок"""
        self.errors += 1
        if self.errors % 10 == 0:
            logger.warning(f"Количество ошибок: {self.errors}")
    
    def get_stats(self):
        """Получить текущую статистику"""
        return {
            'forwarded_messages': self.forwarded_messages,
            'active_folders': self.active_folders,
            'active_users': len(self.active_users),
            'errors': self.errors
        }

# Create global metrics collector instance
metrics = MetricsCollector() 