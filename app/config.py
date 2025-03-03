from pydantic import Field
from pydantic_settings import BaseSettings
import os
from typing import Optional

class Settings(BaseSettings):
    # API Settings
    API_ID: int = Field(..., description="Telegram API ID")
    API_HASH: str = Field(..., description="Telegram API Hash")
    BOT_TOKEN: str = Field(..., description="Telegram Bot Token")
    
    # Directory Settings
    DATA_DIR: str = Field("./data", description="Base directory for data storage")

    @property
    def LOGS_DIR(self) -> str:
        return os.path.join(self.DATA_DIR, "logs")

    @property
    def USER_DATA_DIR(self) -> str:
        return os.path.join(self.DATA_DIR, "user_data")

    @property
    def ANALYTICS_DIR(self) -> str:
        return os.path.join(self.DATA_DIR, "analytics")

    @property
    def BACKUPS_DIR(self) -> str:
        return os.path.join(self.DATA_DIR, "backups")
    
    # Connection Settings
    WEBHOOK_URL: Optional[str] = Field(None, description="Webhook URL for bot updates")
    WEBHOOK_HOST: str = Field("0.0.0.0", description="Webhook server host")
    WEBHOOK_PORT: int = Field(8443, description="Webhook server port")
    
    # Security Settings
    ENCRYPTION_KEY: Optional[str] = Field(None, description="Key for session encryption")
    ADMIN_IDS: list[int] = Field(default_factory=list, description="List of admin user IDs")
    
    # Logging Settings
    LOG_LEVEL: str = Field("INFO", description="Logging level")
    LOG_FORMAT: str = Field(
        "%(asctime)s - [%(request_id)s] - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )
    LOG_MAX_SIZE: int = Field(10 * 1024 * 1024, description="Maximum log file size in bytes")
    LOG_BACKUP_COUNT: int = Field(5, description="Number of log file backups to keep")
    
    # Queue Settings
    QUEUE_MAX_SIZE: int = Field(1000, description="Maximum queue size per channel")
    QUEUE_TIMEOUT: int = Field(60, description="Queue processing timeout in seconds")
    FORWARD_DELAY: float = Field(0.5, description="Delay between forwards in seconds")
    
    # Cache Settings
    FOLDER_CACHE_TTL: int = Field(300, description="Folder list cache TTL in seconds")
    ENABLE_REDIS_CACHE: bool = Field(False, description="Use Redis for caching")
    REDIS_URL: Optional[str] = Field(None, description="Redis connection URL")
    
    # Performance Settings
    MAX_CONCURRENT_FORWARDS: int = Field(5, description="Maximum concurrent forward operations")
    BATCH_SIZE: int = Field(10, description="Batch size for operations")
    
    # Monitoring Settings
    ENABLE_METRICS: bool = Field(False, description="Enable Prometheus metrics")
    METRICS_HOST: str = Field("0.0.0.0", description="Metrics server host")
    METRICS_PORT: int = Field(9090, description="Metrics server port")
    
    # Webhook Settings
    ENABLE_WEBHOOK: bool = Field(False, description="Enable webhook mode")
    CERT_FILE: Optional[str] = Field(None, description="Path to certificate file")
    KEY_FILE: Optional[str] = Field(None, description="Path to private key file")
    
    # Analytics Settings
    ENABLE_ANALYTICS: bool = Field(False, description="Enable analytics collection")
    ANALYTICS_FLUSH_INTERVAL: int = Field(300, description="Analytics flush interval in seconds")
    
    # Internationalization Settings
    DEFAULT_LANGUAGE: str = Field("ru", description="Default bot language")
    AVAILABLE_LANGUAGES: list[str] = Field(default_factory=lambda: ["ru", "en"])
    
    # Background Tasks
    CLEANUP_INTERVAL: int = Field(3600, description="Cleanup interval in seconds")
    SESSION_TIMEOUT: int = Field(7 * 24 * 3600, description="Session timeout in seconds")
    
    # Rate Limiting
    RATE_LIMIT: int = Field(30, description="Rate limit per minute")
    RATE_LIMIT_BURST: int = Field(5, description="Rate limit burst size")

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Create necessary directories
        for directory in [self.DATA_DIR, self.LOGS_DIR, self.USER_DATA_DIR, 
                         self.ANALYTICS_DIR, self.BACKUPS_DIR]:
            os.makedirs(directory, exist_ok=True)

# Create settings instance
settings = Settings() 