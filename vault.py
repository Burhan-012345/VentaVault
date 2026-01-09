"""
VantaVault - Vault Management System
Complete version with first-time PIN setup support
"""
import sqlite3
import os
import json
import hashlib
import time
import secrets
import base64
import random
from datetime import datetime, timedelta
import shutil
from pathlib import Path

class VaultManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.real_storage = 'encrypted_storage/real/'
        self.fake_storage = 'encrypted_storage/fake/'
        
        # Ensure storage directories
        for path in [self.real_storage, self.fake_storage]:
            os.makedirs(path, exist_ok=True)
        
        # Check and fix schema on initialization
        self.check_and_fix_schema()
    
    def is_first_time(self):
        """Check if this is the first time app is launched"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if real_vault_settings table exists and has data
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='real_vault_settings'")
            if not cursor.fetchone():
                return True
            
            cursor.execute("SELECT COUNT(*) FROM real_vault_settings")
            count = cursor.fetchone()[0]
            return count == 0
            
        except:
            return True
        finally:
            conn.close()
    
    def check_and_fix_schema(self):
        """Check database schema and fix issues"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if failed_attempts table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='failed_attempts'")
            if cursor.fetchone():
                # Check if block_expiry column exists
                cursor.execute("PRAGMA table_info(failed_attempts)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'block_expiry' not in columns:
                    print("Adding missing column: block_expiry to failed_attempts table")
                    cursor.execute('''
                        ALTER TABLE failed_attempts 
                        ADD COLUMN block_expiry TIMESTAMP
                    ''')
                    conn.commit()
                    print("✅ Schema updated successfully")
        except Exception as e:
            print(f"Schema check error: {e}")
        finally:
            conn.close()
    
    def initialize_database(self, real_pin=None, fake_pin=None):
        """Initialize SQLite database with all required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Real vault settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS real_vault_settings (
                id INTEGER PRIMARY KEY,
                pin_hash TEXT NOT NULL,
                fingerprint_enabled BOOLEAN DEFAULT 0,
                auto_lock_minutes INTEGER DEFAULT 5,
                stealth_mode BOOLEAN DEFAULT 0,
                decoy_mode BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Fake vault settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fake_vault_settings (
                id INTEGER PRIMARY KEY,
                pin_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Real media metadata
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS real_media (
                id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                encrypted_path TEXT NOT NULL,
                thumbnail_path TEXT,
                folder_id TEXT DEFAULT 'default',
                file_size INTEGER NOT NULL,
                mimetype TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                duration INTEGER,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                is_hidden BOOLEAN DEFAULT 0,
                is_deleted BOOLEAN DEFAULT 0,
                deletion_date TIMESTAMP,
                tags TEXT,
                description TEXT,
                UNIQUE(encrypted_path)
            )
        ''')
        
        # Fake media metadata
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fake_media (
                id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL,
                encrypted_path TEXT NOT NULL,
                thumbnail_path TEXT,
                folder_id TEXT DEFAULT 'default',
                file_size INTEGER NOT NULL,
                mimetype TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(encrypted_path)
            )
        ''')
        
        # Folders
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                vault_type TEXT CHECK(vault_type IN ('real', 'fake')) NOT NULL,
                parent_id TEXT,
                color TEXT DEFAULT '#666666',
                icon TEXT DEFAULT '📁',
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
            )
        ''')
        
        # Authentication logs - FIXED: Added 'SETUP' to allowed values
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auth_logs (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                attempt_type TEXT NOT NULL CHECK(attempt_type IN ('PIN', 'Fingerprint', 'SETUP')),
                success BOOLEAN NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                device_info TEXT,
                vault_type TEXT CHECK(vault_type IN ('real', 'fake')),
                failure_reason TEXT
            )
        ''')
        
        # Failed attempts tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS failed_attempts (
                id INTEGER PRIMARY KEY,
                ip_address TEXT NOT NULL,
                attempts INTEGER DEFAULT 1,
                last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_blocked BOOLEAN DEFAULT 0,
                block_expiry TIMESTAMP,
                UNIQUE(ip_address)
            )
        ''')
        
        # Share links
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS share_links (
                id INTEGER PRIMARY KEY,
                token TEXT UNIQUE NOT NULL,
                media_id INTEGER NOT NULL,
                expiry_time TIMESTAMP NOT NULL,
                view_count INTEGER DEFAULT 0,
                max_views INTEGER DEFAULT 1,
                password_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                last_accessed TIMESTAMP,
                FOREIGN KEY (media_id) REFERENCES real_media(id) ON DELETE CASCADE
            )
        ''')
        
        # Recycle bin
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recycle_bin (
                id INTEGER PRIMARY KEY,
                media_id INTEGER NOT NULL,
                deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                auto_delete_at TIMESTAMP,
                vault_type TEXT CHECK(vault_type IN ('real', 'fake')) NOT NULL,
                original_path TEXT,
                deletion_reason TEXT,
                FOREIGN KEY (media_id) REFERENCES real_media(id) ON DELETE CASCADE
            )
        ''')
        
        # WebAuthn credentials
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webauthn_credentials (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                credential_id BLOB UNIQUE NOT NULL,
                public_key BLOB NOT NULL,
                sign_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP
            )
        ''')
        
        # App settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User activity log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT
            )
        ''')
        
        # Initialize default PINs if not exists
        cursor.execute('SELECT COUNT(*) FROM real_vault_settings')
        if cursor.fetchone()[0] == 0:
            if real_pin:
                real_pin_hash = self._hash_pin(real_pin)
            else:
                real_pin_hash = self._hash_pin('0000')  # Default fallback
            
            cursor.execute('''
                INSERT INTO real_vault_settings (pin_hash, fingerprint_enabled)
                VALUES (?, ?)
            ''', (real_pin_hash, 0))
        
        cursor.execute('SELECT COUNT(*) FROM fake_vault_settings')
        if cursor.fetchone()[0] == 0:
            if fake_pin:
                fake_pin_hash = self._hash_pin(fake_pin)
            else:
                # Generate random 6-digit fake PIN
                fake_pin = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                fake_pin_hash = self._hash_pin(fake_pin)
            
            cursor.execute('''
                INSERT INTO fake_vault_settings (pin_hash)
                VALUES (?)
            ''', (fake_pin_hash,))
        
        # Initialize default app settings
        default_settings = [
            ('theme', 'dark', 'appearance'),
            ('auto_lock_minutes', '5', 'security'),
            ('stealth_mode', '0', 'security'),
            ('decoy_mode', '1', 'security'),
            ('fingerprint_enabled', '0', 'security'),
            ('thumbnail_quality', '85', 'media'),
            ('recycle_bin_expiry_days', '7', 'privacy'),
            ('max_upload_size_mb', '100', 'storage'),
            ('share_expiry_hours', '24', 'sharing'),
            ('auto_backup', '0', 'backup'),
            ('backup_frequency_days', '7', 'backup'),
            ('font_size', 'medium', 'accessibility'),
            ('animations_enabled', '1', 'appearance'),
            ('high_contrast', '0', 'accessibility'),
            ('first_run_completed', '0', 'system')
        ]
        
        for key, value, category in default_settings:
            cursor.execute('''
                INSERT OR IGNORE INTO app_settings (key, value, category)
                VALUES (?, ?, ?)
            ''', (key, value, category))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Database initialized at: {self.db_path}")
        return True
    
    def _hash_pin(self, pin: str) -> str:
        """Create secure PIN hash using PBKDF2-HMAC-SHA256"""
        salt = secrets.token_bytes(16)
        pin_bytes = pin.encode('utf-8')
        
        key = hashlib.pbkdf2_hmac(
            'sha256',
            pin_bytes,
            salt,
            100000,  # 100k iterations
            dklen=32  # 256-bit key
        )
        
        return base64.urlsafe_b64encode(salt + key).decode('utf-8')
    
    def _verify_pin_hash(self, pin_hash: str, pin: str) -> bool:
        """Verify PIN against hash"""
        try:
            data = base64.urlsafe_b64decode(pin_hash)
            salt = data[:16]
            stored_key = data[16:]
            
            key = hashlib.pbkdf2_hmac(
                'sha256',
                pin.encode('utf-8'),
                salt,
                100000,
                dklen=32
            )
            
            return secrets.compare_digest(stored_key, key)
        except Exception:
            return False
    
    def verify_pin(self, pin: str):
        """Verify PIN and return vault type (real/fake) or None"""
        if not pin or len(pin) < 4:
            return None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check real vault first
        cursor.execute('SELECT pin_hash FROM real_vault_settings LIMIT 1')
        real_row = cursor.fetchone()
        
        if real_row and self._verify_pin_hash(real_row[0], pin):
            conn.close()
            return 'real'
        
        # Check fake vault
        cursor.execute('SELECT pin_hash FROM fake_vault_settings LIMIT 1')
        fake_row = cursor.fetchone()
        
        if fake_row and self._verify_pin_hash(fake_row[0], pin):
            conn.close()
            return 'fake'
        
        conn.close()
        return None
    
    def update_pin(self, vault_type: str, new_pin: str) -> bool:
        """Update PIN for vault"""
        if len(new_pin) < 4 or len(new_pin) > 6:
            return False
        
        pin_hash = self._hash_pin(new_pin)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if vault_type == 'real':
            cursor.execute('''
                UPDATE real_vault_settings 
                SET pin_hash = ?, updated_at = CURRENT_TIMESTAMP
            ''', (pin_hash,))
        elif vault_type == 'fake':
            cursor.execute('''
                UPDATE fake_vault_settings 
                SET pin_hash = ?
            ''', (pin_hash,))
        else:
            conn.close()
            return False
        
        conn.commit()
        conn.close()
        return True
    
    def setup_initial_pins(self, real_pin: str, fake_pin: str = None) -> bool:
        """Setup initial PINs for first-time users"""
        if not real_pin or len(real_pin) != 6:
            return False
        
        # Generate random fake PIN if not provided
        if not fake_pin:
            fake_pin = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Initialize database with provided PINs
        return self.initialize_database(real_pin, fake_pin)
    
    def log_auth_attempt(self, attempt_type: str, success: bool, 
                         ip_address: str = None, user_agent: str = None,
                         vault_type: str = None, failure_reason: str = None):
        """Log authentication attempt"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO auth_logs 
            (timestamp, attempt_type, success, ip_address, user_agent, vault_type, failure_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), attempt_type, success, 
              ip_address, user_agent, vault_type, failure_reason))
        
        conn.commit()
        conn.close()
    
    def log_failed_attempt(self, ip_address: str):
        """Log failed authentication attempt"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT attempts, is_blocked FROM failed_attempts 
            WHERE ip_address = ? AND last_attempt > datetime('now', '-1 hour')
        ''', (ip_address,))
        
        result = cursor.fetchone()
        if result:
            attempts, is_blocked = result
            if attempts >= 5:
                # Block for 1 hour
                block_expiry = datetime.now() + timedelta(hours=1)
                cursor.execute('''
                    UPDATE failed_attempts 
                    SET is_blocked = 1, block_expiry = ?, last_attempt = CURRENT_TIMESTAMP
                    WHERE ip_address = ?
                ''', (block_expiry.isoformat(), ip_address))
            else:
                cursor.execute('''
                    UPDATE failed_attempts 
                    SET attempts = attempts + 1, last_attempt = CURRENT_TIMESTAMP
                    WHERE ip_address = ?
                ''', (ip_address,))
        else:
            cursor.execute('''
                INSERT INTO failed_attempts (ip_address, attempts)
                VALUES (?, 1)
            ''', (ip_address,))
        
        conn.commit()
        conn.close()
    
    def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if IP is blocked"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT is_blocked, block_expiry FROM failed_attempts 
            WHERE ip_address = ?
        ''', (ip_address,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            is_blocked, block_expiry = result
            if is_blocked and block_expiry:
                if datetime.now() < datetime.fromisoformat(block_expiry):
                    return True
                else:
                    # Unblock expired
                    self.unblock_ip(ip_address)
        
        return False
    
    def unblock_ip(self, ip_address: str):
        """Unblock IP address"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE failed_attempts 
            SET is_blocked = 0, attempts = 0, block_expiry = NULL
            WHERE ip_address = ?
        ''', (ip_address,))
        
        conn.commit()
        conn.close()
    
    def encrypt_and_store(self, file_path: str, session_id: str, folder_id: str = 'default'):
        """Encrypt and store media file"""
        # Generate unique filename
        file_ext = Path(file_path).suffix
        timestamp = int(time.time())
        unique_name = f"{session_id}_{timestamp}{file_ext}"
        
        try:
            # Read file
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Simple XOR encryption with session_id as key
            key = hashlib.sha256(session_id.encode()).digest()
            encrypted_data = self._xor_encrypt(file_data, key)
            
            # Save encrypted file
            encrypted_path = os.path.join(self.real_storage, unique_name)
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Create thumbnail
            thumbnail_path = encrypted_path + '.thumb'
            self._create_thumbnail(file_path, thumbnail_path)
            
            # Clean up original
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return encrypted_path, thumbnail_path
            
        except Exception as e:
            print(f"Error encrypting file: {e}")
            return None, None
    
    def _xor_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption"""
        key_len = len(key)
        encrypted = bytearray(len(data))
        
        for i, byte in enumerate(data):
            encrypted[i] = byte ^ key[i % key_len]
        
        return bytes(encrypted)
    
    def _create_thumbnail(self, image_path: str, thumbnail_path: str, size: tuple = (200, 200)):
        """Create thumbnail for image"""
        try:
            from PIL import Image
            
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (0, 0, 0))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # Create thumbnail
                img.thumbnail(size)
                
                # Save thumbnail
                img.save(thumbnail_path, 'JPEG', quality=85)
                
                # Encrypt thumbnail
                with open(thumbnail_path, 'rb') as f:
                    thumb_data = f.read()
                
                key = hashlib.sha256(b'thumbnail_key').digest()
                encrypted_thumb = self._xor_encrypt(thumb_data, key)
                
                with open(thumbnail_path, 'wb') as f:
                    f.write(encrypted_thumb)
                
                return True
                
        except ImportError:
            print("Pillow not installed. Using simple thumbnail method.")
            # Simple fallback
            return self._create_simple_thumbnail(image_path, thumbnail_path)
        except Exception as e:
            print(f"Thumbnail creation failed: {e}")
            return self._create_simple_thumbnail(image_path, thumbnail_path)
    
    def _create_simple_thumbnail(self, image_path: str, thumbnail_path: str):
        """Create simple thumbnail (fallback)"""
        try:
            # Copy first 5KB as "thumbnail"
            with open(image_path, 'rb') as f:
                data = f.read(5120)
            
            key = hashlib.sha256(b'thumbnail_key').digest()
            encrypted_data = self._xor_encrypt(data, key)
            
            with open(thumbnail_path, 'wb') as f:
                f.write(encrypted_data)
            
            return True
        except Exception:
            return False
    
    def store_media_metadata(self, filename: str, encrypted_path: str, 
                            thumbnail_path: str, folder_id: str, vault_type: str):
        """Store media metadata in database"""
        if not os.path.exists(encrypted_path):
            return None
        
        # Get file info
        file_size = os.path.getsize(encrypted_path)
        mimetype = self._guess_mimetype(filename)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if vault_type == 'real':
            cursor.execute('''
                INSERT INTO real_media 
                (filename, original_filename, encrypted_path, thumbnail_path, 
                 folder_id, file_size, mimetype, upload_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (filename, filename, encrypted_path, thumbnail_path, 
                  folder_id, file_size, mimetype))
        else:
            cursor.execute('''
                INSERT INTO fake_media 
                (filename, encrypted_path, thumbnail_path, folder_id, file_size, mimetype)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (filename, encrypted_path, thumbnail_path, folder_id, file_size, mimetype))
        
        media_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return media_id
    
    def _guess_mimetype(self, filename: str) -> str:
        """Guess mimetype from filename"""
        ext = Path(filename).suffix.lower()
        
        mime_types = {
            # Images
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.tiff': 'image/tiff',
            '.ico': 'image/x-icon',
            
            # Videos
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.mkv': 'video/x-matroska',
            '.webm': 'video/webm',
            '.flv': 'video/x-flv',
            '.wmv': 'video/x-ms-wmv',
            '.m4v': 'video/x-m4v',
            '.3gp': 'video/3gpp',
            
            # Audio
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
            '.flac': 'audio/flac',
            
            # Documents
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        }
        
        return mime_types.get(ext, 'application/octet-stream')
    
    def get_media_list(self, vault_type: str, folder_id: str = 'default', 
                      include_hidden: bool = False, limit: int = None):
        """Get list of media files"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if vault_type == 'real':
            query = '''
                SELECT id, filename, original_filename, thumbnail_path, 
                       upload_date, file_size, mimetype, is_hidden, folder_id
                FROM real_media
                WHERE folder_id = ? AND is_deleted = 0
            '''
            if not include_hidden:
                query += ' AND is_hidden = 0'
            query += ' ORDER BY upload_date DESC'
            
            if limit:
                query += f' LIMIT {limit}'
            
            cursor.execute(query, (folder_id,))
        else:
            query = '''
                SELECT id, filename, thumbnail_path, upload_date, file_size, mimetype, folder_id
                FROM fake_media
                WHERE folder_id = ?
                ORDER BY upload_date DESC
            '''
            if limit:
                query += f' LIMIT {limit}'
            
            cursor.execute(query, (folder_id,))
        
        media_list = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return media_list
    
    def get_media_info(self, media_id: int, vault_type: str):
        """Get media file information"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if vault_type == 'real':
            cursor.execute('SELECT * FROM real_media WHERE id = ?', (media_id,))
        else:
            cursor.execute('SELECT * FROM fake_media WHERE id = ?', (media_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def decrypt_media(self, encrypted_path: str, session_id: str):
        """Decrypt media file"""
        if not os.path.exists(encrypted_path):
            return None
        
        try:
            with open(encrypted_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt using session_id as key
            key = hashlib.sha256(session_id.encode()).digest()
            decrypted_data = self._xor_encrypt(encrypted_data, key)
            
            # Create temporary file for serving
            temp_path = f'temp_{int(time.time())}_{secrets.token_hex(8)}.tmp'
            with open(temp_path, 'wb') as f:
                f.write(decrypted_data)
            
            return temp_path
            
        except Exception as e:
            print(f"Error decrypting file: {e}")
            return None
    
    def delete_media(self, media_id: int, vault_type: str, permanent: bool = False, 
                    reason: str = None) -> bool:
        """Delete media file"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get file info before deletion
        if vault_type == 'real':
            cursor.execute('''
                SELECT encrypted_path, thumbnail_path FROM real_media 
                WHERE id = ? AND is_deleted = 0
            ''', (media_id,))
        else:
            cursor.execute('''
                SELECT encrypted_path, thumbnail_path FROM fake_media 
                WHERE id = ?
            ''', (media_id,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
        
        encrypted_path, thumbnail_path = result
        
        if permanent:
            # Permanent deletion
            if vault_type == 'real':
                cursor.execute('DELETE FROM real_media WHERE id = ?', (media_id,))
            else:
                cursor.execute('DELETE FROM fake_media WHERE id = ?', (media_id,))
            
            # Delete files
            for path in [encrypted_path, thumbnail_path]:
                if path and os.path.exists(path):
                    self._secure_delete(path)
        else:
            # Move to recycle bin (real vault only)
            if vault_type == 'real':
                cursor.execute('''
                    UPDATE real_media 
                    SET is_deleted = 1, deletion_date = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (media_id,))
                
                # Add to recycle bin
                expiry_days = self.get_setting('recycle_bin_expiry_days', 7)
                auto_delete_at = datetime.now() + timedelta(days=int(expiry_days))
                
                cursor.execute('''
                    INSERT INTO recycle_bin 
                    (media_id, vault_type, auto_delete_at, original_path, deletion_reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (media_id, vault_type, auto_delete_at, encrypted_path, reason))
            else:
                # For fake vault, just delete
                cursor.execute('DELETE FROM fake_media WHERE id = ?', (media_id,))
                if encrypted_path and os.path.exists(encrypted_path):
                    os.remove(encrypted_path)
                if thumbnail_path and os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
        
        conn.commit()
        conn.close()
        return True
    
    def restore_media(self, media_id: int) -> bool:
        """Restore media from recycle bin"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if in recycle bin
        cursor.execute('''
            SELECT media_id, vault_type FROM recycle_bin 
            WHERE media_id = ?
        ''', (media_id,))
        
        if not cursor.fetchone():
            conn.close()
            return False
        
        # Restore media
        cursor.execute('''
            UPDATE real_media 
            SET is_deleted = 0, deletion_date = NULL
            WHERE id = ?
        ''', (media_id,))
        
        # Remove from recycle bin
        cursor.execute('DELETE FROM recycle_bin WHERE media_id = ?', (media_id,))
        
        conn.commit()
        conn.close()
        return True
    
    def _secure_delete(self, file_path: str, passes: int = 3):
        """Securely delete file by overwriting"""
        if not os.path.exists(file_path):
            return
        
        try:
            file_size = os.path.getsize(file_path)
            
            for i in range(passes):
                # Overwrite with random data
                with open(file_path, 'wb') as f:
                    f.write(secrets.token_bytes(file_size))
            
            # Delete file
            os.remove(file_path)
        except Exception as e:
            print(f"Secure delete failed: {e}")
            try:
                os.remove(file_path)
            except:
                pass
    
    def create_folder(self, name: str, vault_type: str, parent_id: str = None) -> str:
        """Create new folder"""
        # Generate folder ID
        folder_id = hashlib.md5(f"{name}_{vault_type}_{time.time()}".encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO folders (id, name, vault_type, parent_id)
            VALUES (?, ?, ?, ?)
        ''', (folder_id, name, vault_type, parent_id))
        
        conn.commit()
        conn.close()
        
        return folder_id
    
    def get_folders(self, vault_type: str, parent_id: str = None):
        """Get list of folders"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if parent_id:
            cursor.execute('''
                SELECT id, name, color, icon, sort_order, created_at
                FROM folders 
                WHERE vault_type = ? AND parent_id = ?
                ORDER BY sort_order, name
            ''', (vault_type, parent_id))
        else:
            cursor.execute('''
                SELECT id, name, color, icon, sort_order, created_at
                FROM folders 
                WHERE vault_type = ? AND parent_id IS NULL
                ORDER BY sort_order, name
            ''', (vault_type,))
        
        folders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return folders
    
    def update_folder(self, folder_id: str, name: str = None, color: str = None, 
                     icon: str = None, sort_order: int = None):
        """Update folder information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if color is not None:
            updates.append("color = ?")
            params.append(color)
        if icon is not None:
            updates.append("icon = ?")
            params.append(icon)
        if sort_order is not None:
            updates.append("sort_order = ?")
            params.append(sort_order)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(folder_id)
            
            query = f"UPDATE folders SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
        
        conn.commit()
        conn.close()
        return True
    
    def delete_folder(self, folder_id: str, move_to_default: bool = True):
        """Delete folder"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get vault type
        cursor.execute('SELECT vault_type FROM folders WHERE id = ?', (folder_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
        
        vault_type = result[0]
        
        if move_to_default:
            # Move media to default folder
            if vault_type == 'real':
                cursor.execute('''
                    UPDATE real_media 
                    SET folder_id = 'default'
                    WHERE folder_id = ?
                ''', (folder_id,))
            else:
                cursor.execute('''
                    UPDATE fake_media 
                    SET folder_id = 'default'
                    WHERE folder_id = ?
                ''', (folder_id,))
        
        # Delete folder
        cursor.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
        
        conn.commit()
        conn.close()
        return True
    
    def update_settings(self, settings: dict):
        """Update vault settings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for key, value in settings.items():
            if key == 'pin':
                # Update real vault PIN
                pin_hash = self._hash_pin(value)
                cursor.execute('''
                    UPDATE real_vault_settings 
                    SET pin_hash = ?, updated_at = CURRENT_TIMESTAMP
                ''', (pin_hash,))
            elif key in ['fingerprint_enabled', 'auto_lock_minutes', 'stealth_mode', 'decoy_mode']:
                cursor.execute(f'''
                    UPDATE real_vault_settings 
                    SET {key} = ?, updated_at = CURRENT_TIMESTAMP
                ''', (value,))
            else:
                # Store in app_settings
                cursor.execute('''
                    INSERT OR REPLACE INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (key, str(value)))
        
        conn.commit()
        conn.close()
        return True
    
    def get_settings(self):
        """Get all settings"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get real vault settings
        cursor.execute('SELECT * FROM real_vault_settings LIMIT 1')
        vault_settings = cursor.fetchone()
        
        settings = {}
        if vault_settings:
            settings = dict(vault_settings)
            # Don't return PIN hash
            if 'pin_hash' in settings:
                del settings['pin_hash']
        
        # Get app settings
        cursor.execute('SELECT key, value FROM app_settings')
        app_settings = cursor.fetchall()
        
        for key, value in app_settings:
            # Try to convert to appropriate type
            if value.isdigit():
                settings[key] = int(value)
            elif value.lower() in ['true', 'false']:
                settings[key] = value.lower() == 'true'
            else:
                settings[key] = value
        
        conn.close()
        return settings
    
    def get_setting(self, key: str, default=None):
        """Get specific setting"""
        settings = self.get_settings()
        return settings.get(key, default)
    
    def get_security_logs(self, limit: int = 100, vault_type: str = None):
        """Get security logs"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if vault_type:
            cursor.execute('''
                SELECT * FROM auth_logs 
                WHERE vault_type = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (vault_type, limit))
        else:
            cursor.execute('''
                SELECT * FROM auth_logs 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
        
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return logs
    
    def create_share_link(self, media_id: int, expiry_hours: int = 24, 
                         max_views: int = 1, password: str = None):
        """Create temporary share link"""
        token = secrets.token_urlsafe(32)
        expiry_time = datetime.now() + timedelta(hours=expiry_hours)
        
        password_hash = None
        if password:
            password_hash = self._hash_pin(password)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO share_links 
            (token, media_id, expiry_time, max_views, password_hash)
            VALUES (?, ?, ?, ?, ?)
        ''', (token, media_id, expiry_time, max_views, password_hash))
        
        conn.commit()
        conn.close()
        
        return token
    
    def access_share_link(self, token: str):
        """Access shared media"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.*, m.encrypted_path, m.filename, m.mimetype
            FROM share_links s
            JOIN real_media m ON s.media_id = m.id
            WHERE s.token = ? AND s.expiry_time > CURRENT_TIMESTAMP
        ''', (token,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None
        
        # Update view count
        cursor.execute('''
            UPDATE share_links 
            SET view_count = view_count + 1, last_accessed = CURRENT_TIMESTAMP
            WHERE token = ?
        ''', (token,))
        
        conn.commit()
        conn.close()
        
        # Decrypt the file temporarily
        if result:
            return {
                'path': result[10],  # encrypted_path
                'filename': result[11],  # filename
                'mimetype': result[12]  # mimetype
            }
        return None
    
    def cleanup_expired_shares(self):
        """Clean up expired share links"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM share_links 
            WHERE expiry_time <= CURRENT_TIMESTAMP
        ''')
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
    
    def cleanup_recycle_bin(self):
        """Permanently delete items from recycle bin"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get items ready for permanent deletion
        cursor.execute('''
            SELECT rb.media_id, rb.original_path
            FROM recycle_bin rb
            WHERE rb.auto_delete_at <= CURRENT_TIMESTAMP
        ''')
        
        items_to_delete = cursor.fetchall()
        deleted = 0
        
        for media_id, original_path in items_to_delete:
            # Permanent delete from media table
            cursor.execute('DELETE FROM real_media WHERE id = ?', (media_id,))
            
            # Delete the file
            if original_path and os.path.exists(original_path):
                try:
                    os.remove(original_path)
                except:
                    pass
            
            # Delete from recycle bin
            cursor.execute('DELETE FROM recycle_bin WHERE media_id = ?', (media_id,))
            deleted += 1
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def get_storage_stats(self, vault_type: str):
        """Get storage statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if vault_type == 'real':
            cursor.execute('''
                SELECT 
                    COUNT(*) as file_count,
                    SUM(file_size) as total_size,
                    COUNT(DISTINCT folder_id) as folder_count,
                    MIN(upload_date) as oldest_file,
                    MAX(upload_date) as newest_file
                FROM real_media 
                WHERE is_deleted = 0
            ''')
        else:
            cursor.execute('''
                SELECT 
                    COUNT(*) as file_count,
                    SUM(file_size) as total_size,
                    COUNT(DISTINCT folder_id) as folder_count,
                    MIN(upload_date) as oldest_file,
                    MAX(upload_date) as newest_file
                FROM fake_media
            ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'file_count': result[0] or 0,
                'total_size': result[1] or 0,
                'folder_count': result[2] or 0,
                'oldest_file': result[3],
                'newest_file': result[4]
            }
        return {
            'file_count': 0,
            'total_size': 0,
            'folder_count': 0,
            'oldest_file': None,
            'newest_file': None
        }
    
    def add_fake_media(self):
        """Add fake media for decoy mode"""
        fake_files = [
            'photo001.jpg',
            'vacation.png',
            'screenshot.png',
            'document.pdf',
            'selfie.jpg',
            'recipe.txt'
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if fake media already exists
        cursor.execute('SELECT COUNT(*) FROM fake_media')
        count = cursor.fetchone()[0]
        
        if count > 0:
            conn.close()
            return
        
        # Add fake media entries
        for filename in fake_files:
            fake_path = os.path.join(self.fake_storage, filename)
            file_size = random.randint(1024, 1024 * 1024)  # 1KB to 1MB
            
            cursor.execute('''
                INSERT INTO fake_media 
                (filename, encrypted_path, thumbnail_path, folder_id, file_size, mimetype, upload_date)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now', '-' || ? || ' days'))
            ''', (
                filename,
                fake_path,
                fake_path + '.thumb',
                'default',
                file_size,
                self._guess_mimetype(filename),
                random.randint(0, 30)  # Random date in last 30 days
            ))
        
        conn.commit()
        conn.close()
        print(f"✅ Added {len(fake_files)} fake media items for decoy mode")