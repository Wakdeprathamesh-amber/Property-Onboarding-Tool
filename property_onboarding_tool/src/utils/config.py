import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, continue without it

@dataclass
class ExtractionConfig:
    """Configuration for extraction parameters"""
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 5
    extraction_timeout_seconds: int = 300
    parallel_node_execution: bool = True
    enable_competitor_analysis: bool = True
    max_competitor_searches: int = 3

@dataclass
class APIConfig:
    """Configuration for external API integrations"""
    openai_api_key: str
    openai_api_base: str
    openai_model: str = "gpt-4o"
    perplexity_api_key: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.1

@dataclass
class DatabaseConfig:
    """Database configuration"""
    database_uri: str
    track_modifications: bool = False
    pool_size: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600

@dataclass
class AppConfig:
    """Main application configuration"""
    secret_key: str
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    cors_origins: str = "*"

class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self):
        self._extraction_config = None
        self._api_config = None
        self._database_config = None
        self._app_config = None
    
    @property
    def extraction(self) -> ExtractionConfig:
        """Get extraction configuration"""
        if self._extraction_config is None:
            self._extraction_config = ExtractionConfig(
                max_retry_attempts=int(os.getenv('MAX_RETRY_ATTEMPTS', '3')),
                retry_delay_seconds=int(os.getenv('RETRY_DELAY_SECONDS', '5')),
                extraction_timeout_seconds=int(os.getenv('EXTRACTION_TIMEOUT_SECONDS', '300')),
                parallel_node_execution=os.getenv('PARALLEL_NODE_EXECUTION', 'true').lower() == 'true',
                enable_competitor_analysis=os.getenv('ENABLE_COMPETITOR_ANALYSIS', 'true').lower() == 'true',
                max_competitor_searches=int(os.getenv('MAX_COMPETITOR_SEARCHES', '3'))
            )
        return self._extraction_config
    
    @property
    def api(self) -> APIConfig:
        """Get API configuration"""
        if self._api_config is None:
            self._api_config = APIConfig(
                openai_api_key=os.getenv('OPENAI_API_KEY', ''),
                openai_api_base=os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1'),
                openai_model=os.getenv('OPENAI_MODEL', 'gpt-4o'),
                perplexity_api_key=os.getenv('PERPLEXITY_API_KEY'),
                max_tokens=int(os.getenv('MAX_TOKENS', '4000')),
                temperature=float(os.getenv('TEMPERATURE', '0.1'))
            )
        return self._api_config
    
    @property
    def database(self) -> DatabaseConfig:
        """Get database configuration"""
        if self._database_config is None:
            # Default to SQLite for development
            default_db_uri = f"sqlite:///{os.path.join(os.path.dirname(__file__), '..', 'database', 'app.db')}"
            self._database_config = DatabaseConfig(
                database_uri=os.getenv('DATABASE_URI', default_db_uri),
                track_modifications=os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS', 'false').lower() == 'true',
                pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
                pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', '30')),
                pool_recycle=int(os.getenv('DB_POOL_RECYCLE', '3600'))
            )
        return self._database_config
    
    @property
    def app(self) -> AppConfig:
        """Get application configuration"""
        if self._app_config is None:
            self._app_config = AppConfig(
                secret_key=os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
                debug=os.getenv('DEBUG', 'false').lower() == 'true',
                host=os.getenv('HOST', '0.0.0.0'),
                port=int(os.getenv('PORT', '5000')),
                cors_origins=os.getenv('CORS_ORIGINS', '*')
            )
        return self._app_config
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate configuration and return any issues"""
        issues = []
        
        # Validate API configuration
        if not self.api.openai_api_key:
            issues.append("OPENAI_API_KEY is not set")
        
        # Validate database configuration
        if not self.database.database_uri:
            issues.append("DATABASE_URI is not set")
        
        # Validate app configuration
        if self.app.secret_key == 'dev-secret-key-change-in-production' and not self.app.debug:
            issues.append("SECRET_KEY should be changed in production")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'config_summary': {
                'extraction': {
                    'max_retry_attempts': self.extraction.max_retry_attempts,
                    'parallel_execution': self.extraction.parallel_node_execution,
                    'competitor_analysis': self.extraction.enable_competitor_analysis
                },
                'api': {
                    'openai_model': self.api.openai_model,
                    'has_openai_key': bool(self.api.openai_api_key),
                    'has_perplexity_key': bool(self.api.perplexity_api_key)
                },
                'database': {
                    'uri_type': 'sqlite' if 'sqlite' in self.database.database_uri else 'other',
                    'pool_size': self.database.pool_size
                },
                'app': {
                    'debug': self.app.debug,
                    'host': self.app.host,
                    'port': self.app.port
                }
            }
        }

# Global configuration instance
config = ConfigManager()

def get_config() -> ConfigManager:
    """Get the global configuration instance"""
    return config

