"""
Configuration Management for Pizza Hut TV
Loads environment-specific settings from .env files
"""
import os
from dotenv import load_dotenv

class Config:
    """Base configuration"""
    
    def __init__(self):
        # Determine environment
        self.ENV = os.environ.get('FLASK_ENV', 'development')
        
        # Load appropriate .env file
        if self.ENV == 'production':
            load_dotenv('.env.production')
        else:
            load_dotenv('.env.development')
        
        # Load all settings
        self.FLASK_ENV = os.getenv('FLASK_ENV', 'development')
        self.FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'
        
        # Database
        self.DATABASE_PATH = os.getenv('DATABASE_PATH', 'database.db')
        
        # Server
        self.SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
        self.SERVER_PORT = int(os.getenv('SERVER_PORT', '5002'))
        
        # Logging
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        
        # Feature Flags
        self.ENABLE_DEBUG_ROUTES = os.getenv('ENABLE_DEBUG_ROUTES', 'False') == 'True'
        self.ENABLE_MOCK_DATA = os.getenv('ENABLE_MOCK_DATA', 'False') == 'True'
        
        # URLs
        self.BASE_URL = os.getenv('BASE_URL', 'http://localhost:5002')
    
    def is_development(self):
        return self.FLASK_ENV == 'development'
    
    def is_production(self):
        return self.FLASK_ENV == 'production'
    
    def __repr__(self):
        return f"<Config env={self.FLASK_ENV} debug={self.FLASK_DEBUG}>"

# Global config instance
config = Config()
