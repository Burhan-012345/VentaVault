#!/usr/bin/env python3
"""
VantaVault - Database Initialization
"""
import sqlite3
import hashlib
import os

def initialize_database():
    # Create database directory
    os.makedirs('database', exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect('database/vantavault.db')
    cursor = conn.cursor()
    
    # Create tables (same as in vault.py)
    cursor.executescript('''
        -- Real vault settings
        CREATE TABLE IF NOT EXISTS real_vault_settings (
            id INTEGER PRIMARY KEY,
            pin_hash TEXT NOT NULL,
            fingerprint_enabled BOOLEAN DEFAULT 0,
            auto_lock_minutes INTEGER DEFAULT 5,
            stealth_mode BOOLEAN DEFAULT 0,
            decoy_mode BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Fake vault settings
        CREATE TABLE IF NOT EXISTS fake_vault_settings (
            id INTEGER PRIMARY KEY,
            pin_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Insert default PINs
        INSERT OR IGNORE INTO real_vault_settings (pin_hash) 
        VALUES (?)  -- SHA256 hash of "0000"
        '''.replace('?', f"'{hashlib.sha256('0000'.encode()).hexdigest()}'"))
    
    cursor.execute('''
        INSERT OR IGNORE INTO fake_vault_settings (pin_hash) 
        VALUES (?)
        '''.replace('?', f"'{hashlib.sha256('123456'.encode()).hexdigest()}'"))
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")
    print("🔐 Default PIN for real vault: 0000")
    print("🔐 Default PIN for fake vault: 123456")

if __name__ == '__main__':
    initialize_database()