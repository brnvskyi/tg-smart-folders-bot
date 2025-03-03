import ssl
import logging
from aiohttp import web
from typing import Optional
from app.logger import setup_logger
from app.config import settings

logger = setup_logger(__name__)

class WebhookServer:
    def __init__(self, bot):
        self.bot = bot
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        
    async def setup(self):
        """Setup webhook server"""
        if not settings.USE_WEBHOOKS:
            return
            
        try:
            self._app = web.Application()
            self._app.router.add_post(f'/{settings.BOT_TOKEN}', self.handle_webhook)
            
            self._runner = web.AppRunner(self._app)
            await self._runner.setup()
            
            # Setup SSL if configured
            ssl_context = None
            if settings.WEBHOOK_SSL_CERT and settings.WEBHOOK_SSL_PRIV:
                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(
                    settings.WEBHOOK_SSL_CERT,
                    settings.WEBHOOK_SSL_PRIV
                )
            
            self._site = web.TCPSite(
                self._runner,
                settings.WEBHOOK_HOST,
                settings.WEBHOOK_PORT,
                ssl_context=ssl_context
            )
            
            await self._site.start()
            logger.info(f"Webhook server started on port {settings.WEBHOOK_PORT}")
            
            # Set webhook in Telegram
            webhook_url = f"https://{settings.WEBHOOK_DOMAIN}:{settings.WEBHOOK_PORT}/{settings.BOT_TOKEN}"
            await self.bot.client.set_webhook(webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
            
        except Exception as e:
            logger.error(f"Failed to setup webhook server: {e}")
            # Fallback to polling
            await self.bot.client.delete_webhook()
            logger.info("Falling back to polling mode")
    
    async def stop(self):
        """Stop webhook server"""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        
        # Remove webhook
        try:
            await self.bot.client.delete_webhook()
        except Exception as e:
            logger.error(f"Error removing webhook: {e}")
        
        self._app = None
        self._runner = None
        self._site = None
    
    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming webhook updates"""
        try:
            update = await request.json()
            await self.bot.process_update(update)
            return web.Response(status=200)
        except Exception as e:
            logger.error(f"Error processing webhook update: {e}")
            return web.Response(status=500) 