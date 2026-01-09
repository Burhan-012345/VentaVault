"""
VantaVault - Configuration Settings
Centralized configuration for all environments
"""
import os
import secrets
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Security settings
SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes

# Database settings
DATABASE_PATH = BASE_DIR / 'database' / 'vantavault.db'
DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

# File storage
UPLOAD_FOLDER = BASE_DIR / 'uploads'
ENCRYPTED_STORAGE = BASE_DIR / 'encrypted_storage'
REAL_STORAGE = ENCRYPTED_STORAGE / 'real'
FAKE_STORAGE = ENCRYPTED_STORAGE / 'fake'

# File upload limits
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp',  # Images
    'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv',  # Videos
    'pdf', 'txt', 'md'  # Documents
}

# PWA settings
PWA_NAME = "VantaVault"
PWA_SHORT_NAME = "VantaVault"
PWA_DESCRIPTION = "High-security media vault"
PWA_THEME_COLOR = "#000000"
PWA_BACKGROUND_COLOR = "#000000"
PWA_DISPLAY = "standalone"
PWA_SCOPE = "/"
PWA_START_URL = "/"
PWA_ICONS = [
    {
        "src": "/static/icons/icon-192.png",
        "sizes": "192x192",
        "type": "image/png"
    },
    {
        "src": "/static/icons/icon-512.png",
        "sizes": "512x512",
        "type": "image/png"
    }
]

# WebAuthn settings
WEBAUTHN_RP_ID = "localhost"  # Change in production
WEBAUTHN_RP_NAME = "VantaVault"
WEBAUTHN_ORIGIN = "https://localhost:5000"  # Change in production

# Security features
MAX_LOGIN_ATTEMPTS = 5
LOGIN_TIMEOUT_MINUTES = 30
AUTO_LOCK_MINUTES = 5
STEALTH_MODE = False
DECOY_MODE = True

# Default PINs (change on first login)
DEFAULT_REAL_PIN = "0000"
DEFAULT_FAKE_PIN = "123456"

# Encryption settings
ENCRYPTION_KEY_DERIVATION_ITERATIONS = 100000
ENCRYPTION_SALT = b'vantavault_salt_'
SECURE_DELETE_PASSES = 3

# Share link settings
DEFAULT_SHARE_EXPIRY_HOURS = 24
MAX_SHARE_EXPIRY_HOURS = 720  # 30 days
DEFAULT_MAX_VIEWS = 1

# Recycle bin settings
RECYCLE_BIN_EXPIRY_DAYS = 7
AUTO_EMPTY_RECYCLE_BIN = True

# Logging settings
LOG_FILE = BASE_DIR / 'logs' / 'vantavault.log'
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Feature flags
FEATURE_FINGERPRINT = True
FEATURE_PWA = True
FEATURE_SHARE_LINKS = True
FEATURE_RECYCLE_BIN = True
FEATURE_STEALTH_MODE = True
FEATURE_DECOY_MODE = True

class DevelopmentConfig:
    """Development configuration"""
    DEBUG = True
    TESTING = True
    SECRET_KEY = 'dev-secret-key-change-in-production'
    DATABASE_PATH = BASE_DIR / 'database' / 'vantavault_dev.db'
    WEBAUTHN_RP_ID = "localhost"
    WEBAUTHN_ORIGIN = "https://localhost:5000"
    SESSION_COOKIE_SECURE