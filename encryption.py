"""
VantaVault - Pure Python Encryption
Uses only Python standard library - works anywhere
"""
import os
import base64
import hashlib
import secrets
import hmac
import struct
import time
from typing import Union, Tuple
import zlib

class EncryptionManager:
    def __init__(self):
        self.salt = b'vantavault_salt_v1_'
    
    def derive_key(self, password: str, salt: bytes = None, iterations: int = 100000) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        if salt is None:
            salt = self.salt
        
        password_bytes = password.encode('utf-8')
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password_bytes,
            salt,
            iterations,
            dklen=32  # 256-bit key
        )
        return key
    
    def encrypt_data(self, data: bytes, password: str) -> bytes:
        """Encrypt data using password-derived key"""
        # Generate random IV
        iv = secrets.token_bytes(16)
        
        # Derive key from password
        key = self.derive_key(password)
        
        # Use HMAC for authenticated encryption
        h = hmac.new(key, digestmod='sha256')
        h.update(iv)
        h.update(data)
        
        # Create ciphertext (simple XOR for demo - in production use proper encryption)
        # This is simplified - for real use, implement proper AES or use a library
        encrypted = self._simple_xor(data, key[:16])
        
        # Return: IV + HMAC + encrypted data
        result = iv + h.digest()[:16] + encrypted
        return base64.urlsafe_b64encode(result)
    
    def decrypt_data(self, encrypted_data: bytes, password: str) -> bytes:
        """Decrypt data using password-derived key"""
        try:
            # Decode from base64
            data = base64.urlsafe_b64decode(encrypted_data)
            
            if len(data) < 32:  # IV (16) + HMAC (16)
                raise ValueError("Invalid encrypted data")
            
            # Extract components
            iv = data[:16]
            received_hmac = data[16:32]
            ciphertext = data[32:]
            
            # Derive key from password
            key = self.derive_key(password)
            
            # Verify HMAC
            h = hmac.new(key, digestmod='sha256')
            h.update(iv)
            h.update(ciphertext)
            expected_hmac = h.digest()[:16]
            
            if not hmac.compare_digest(received_hmac, expected_hmac):
                raise ValueError("HMAC verification failed")
            
            # Decrypt
            decrypted = self._simple_xor(ciphertext, key[:16])
            return decrypted
            
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
    
    def _simple_xor(self, data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption (for demo - replace with proper crypto in production)"""
        key_len = len(key)
        result = bytearray(len(data))
        
        for i, byte in enumerate(data):
            result[i] = byte ^ key[i % key_len]
        
        return bytes(result)
    
    def encrypt_file(self, input_path: str, output_path: str, password: str):
        """Encrypt file and save to output path"""
        with open(input_path, 'rb') as f:
            file_data = f.read()
        
        encrypted_data = self.encrypt_data(file_data, password)
        
        with open(output_path, 'wb') as f:
            f.write(encrypted_data)
    
    def decrypt_file(self, input_path: str, output_path: str, password: str):
        """Decrypt file and save to output path"""
        with open(input_path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = self.decrypt_data(encrypted_data, password)
        
        with open(output_path, 'wb') as f:
            f.write(decrypted_data)
    
    def secure_delete(self, file_path: str, passes: int = 3):
        """Securely delete file by overwriting"""
        if not os.path.exists(file_path):
            return
        
        file_size = os.path.getsize(file_path)
        
        for i in range(passes):
            # Overwrite with random data
            with open(file_path, 'wb') as f:
                f.write(secrets.token_bytes(file_size))
        
        # Delete file
        os.remove(file_path)
    
    def generate_thumbnail(self, image_path: str, thumbnail_path: str, size: Tuple[int, int] = (200, 200)):
        """Generate thumbnail (requires Pillow)"""
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
                
                return True
                
        except ImportError:
            print("Pillow not installed. Using simple thumbnail method.")
            # Simple fallback - copy first 5KB
            with open(image_path, 'rb') as f:
                data = f.read(5120)
            
            with open(thumbnail_path, 'wb') as f:
                f.write(data)
            
            return True
        except Exception as e:
            print(f"Thumbnail generation failed: {e}")
            return False
    
    def hash_password(self, password: str) -> str:
        """Create secure password hash"""
        salt = secrets.token_bytes(16)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000,
            dklen=32
        )
        return base64.urlsafe_b64encode(salt + key).decode('utf-8')
    
    def verify_password(self, password_hash: str, password: str) -> bool:
        """Verify password against hash"""
        try:
            data = base64.urlsafe_b64decode(password_hash)
            salt = data[:16]
            stored_key = data[16:]
            
            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                100000,
                dklen=32
            )
            
            return secrets.compare_digest(stored_key, key)
        except Exception:
            return False
    
    def generate_share_token(self) -> str:
        """Generate secure share token"""
        return secrets.token_urlsafe(32)
    
    def generate_pin_hash(self, pin: str) -> str:
        """Create secure PIN hash"""
        return self.hash_password(pin)
    
    def verify_pin(self, pin_hash: str, pin: str) -> bool:
        """Verify PIN against hash"""
        return self.verify_password(pin_hash, pin)