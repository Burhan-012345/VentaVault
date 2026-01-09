"""
VantaVault - WebAuthn Fingerprint Authentication
Fixed Version
"""
import json
import base64
import secrets
from datetime import datetime
import sqlite3
from flask import Flask, request, jsonify, session

try:
    from webauthn import (
        generate_registration_options,
        verify_registration_response,
        generate_authentication_options,
        verify_authentication_response,
        options_to_json,
        base64url_to_bytes,
        bytes_to_base64url
    )
    from webauthn.helpers import (
        cose,
        json_loads_base64url_to_bytes,
        json_dumps_bytes_to_base64url,
        structs
    )
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        UserVerificationRequirement,
        RegistrationCredential,
        AuthenticationCredential,
        PublicKeyCredentialDescriptor
    )
    WEBAUTHN_AVAILABLE = True
except ImportError:
    WEBAUTHN_AVAILABLE = False

class WebAuthnManager:
    def __init__(self, app):
        self.app = app
        # Use app config for RP settings
        self.rp_id = app.config.get('WEBAUTHN_RP_ID', 'localhost')
        self.rp_name = app.config.get('WEBAUTHN_RP_NAME', 'VantaVault')
        self.origin = app.config.get('WEBAUTHN_ORIGIN', 'http://localhost:5000')
    
    def register_credential(self, user_id=None):
        """Register new fingerprint credential"""
        if not WEBAUTHN_AVAILABLE:
            return {'error': 'WebAuthn not available'}, 501
        
        # Use provided user_id or get from session
        if not user_id:
            user_id = session.get('user_id', 'default_user')
        
        # Generate registration options
        options = generate_registration_options(
            rp_id=self.rp_id,
            rp_name=self.rp_name,
            user_id=user_id.encode(),
            user_name=user_id,
            user_display_name="VantaVault User",
            authenticator_selection=AuthenticatorSelectionCriteria(
                user_verification=UserVerificationRequirement.PREFERRED
            ),
            challenge=secrets.token_bytes(32)
        )
        
        # Store challenge in session
        session['webauthn_challenge'] = options.challenge
        session['webauthn_user_id'] = user_id
        
        return json.loads(options_to_json(options))
    
    def verify_registration(self, request_data):
        """Verify registration response"""
        if not WEBAUTHN_AVAILABLE:
            return {'success': False, 'error': 'WebAuthn not available'}
        
        try:
            # Verify registration
            verification = verify_registration_response(
                credential=RegistrationCredential.parse_raw(json.dumps(request_data)),
                expected_challenge=session.get('webauthn_challenge'),
                expected_rp_id=self.rp_id,
                expected_origin=self.origin
            )
            
            user_id = session.get('webauthn_user_id')
            if not user_id:
                return {'success': False, 'error': 'User ID not found in session'}
            
            # Store credential in database
            self._store_credential(
                user_id,
                verification.credential_id,
                verification.credential_public_key
            )
            
            # Clear session data
            session.pop('webauthn_challenge', None)
            session.pop('webauthn_user_id', None)
            
            return {'success': True}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def authenticate(self, user_id=None):
        """Start fingerprint authentication"""
        if not WEBAUTHN_AVAILABLE:
            return {'success': False, 'error': 'WebAuthn not available'}
        
        try:
            # Use provided user_id or get from session
            if not user_id:
                user_id = session.get('user_id', 'default_user')
            
            # Get stored credentials
            credentials = self._get_credentials(user_id)
            if not credentials:
                return {'success': False, 'error': 'No credentials registered'}
            
            # Generate authentication options
            options = generate_authentication_options(
                rp_id=self.rp_id,
                challenge=secrets.token_bytes(32),
                allow_credentials=[
                    PublicKeyCredentialDescriptor(
                        id=cred['credential_id'],
                        type='public-key'
                    ) for cred in credentials
                ],
                user_verification=UserVerificationRequirement.PREFERRED
            )
            
            # Store challenge in session
            session['webauthn_challenge'] = options.challenge
            session['webauthn_user_id'] = user_id
            
            return {
                'success': True,
                'options': json.loads(options_to_json(options))
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def verify_authentication(self, request_data):
        """Verify authentication response"""
        if not WEBAUTHN_AVAILABLE:
            return {'success': False, 'error': 'WebAuthn not available'}
        
        try:
            user_id = session.get('webauthn_user_id')
            
            if not user_id:
                return {'success': False, 'error': 'No user ID in session'}
            
            # Get credential ID from request
            credential_id = base64url_to_bytes(request_data.get('id'))
            
            # Get stored credential
            credential = self._get_credential(user_id, credential_id)
            
            if not credential:
                return {'success': False, 'error': 'Credential not found'}
            
            # Verify authentication
            verification = verify_authentication_response(
                credential=AuthenticationCredential.parse_raw(json.dumps(request_data)),
                expected_challenge=session.get('webauthn_challenge'),
                expected_rp_id=self.rp_id,
                expected_origin=self.origin,
                credential_public_key=credential['public_key'],
                credential_current_sign_count=credential['sign_count']
            )
            
            # Update sign count
            self._update_sign_count(
                user_id,
                credential_id,
                verification.new_sign_count
            )
            
            # Clear session data
            session.pop('webauthn_challenge', None)
            session.pop('webauthn_user_id', None)
            
            # Store authentication success in session
            session['fingerprint_authenticated'] = True
            session['last_auth_time'] = datetime.now().isoformat()
            
            return {'success': True}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _store_credential(self, user_id, credential_id, public_key):
        """Store WebAuthn credential in database"""
        conn = sqlite3.connect(self.app.config['DATABASE'])
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webauthn_credentials (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                credential_id BLOB UNIQUE NOT NULL,
                public_key BLOB NOT NULL,
                sign_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT OR REPLACE INTO webauthn_credentials 
            (user_id, credential_id, public_key)
            VALUES (?, ?, ?)
        ''', (user_id, credential_id, public_key))
        
        conn.commit()
        conn.close()
    
    def _get_credentials(self, user_id):
        """Get WebAuthn credentials for user"""
        conn = sqlite3.connect(self.app.config['DATABASE'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, public_key, sign_count 
            FROM webauthn_credentials 
            WHERE user_id = ?
        ''', (user_id,))
        
        credentials = []
        for row in cursor.fetchall():
            credentials.append({
                'credential_id': row[0],
                'public_key': row[1],
                'sign_count': row[2]
            })
        
        conn.close()
        return credentials
    
    def _get_credential(self, user_id, credential_id):
        """Get specific WebAuthn credential"""
        conn = sqlite3.connect(self.app.config['DATABASE'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, public_key, sign_count 
            FROM webauthn_credentials 
            WHERE user_id = ? AND credential_id = ?
        ''', (user_id, credential_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'credential_id': row[0],
                'public_key': row[1],
                'sign_count': row[2]
            }
        
        return None
    
    def _update_sign_count(self, user_id, credential_id, new_sign_count):
        """Update sign count for credential"""
        conn = sqlite3.connect(self.app.config['DATABASE'])
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE webauthn_credentials 
            SET sign_count = ? 
            WHERE user_id = ? AND credential_id = ?
        ''', (new_sign_count, user_id, credential_id))
        
        conn.commit()
        conn.close()
    
    def is_fingerprint_enabled(self, user_id):
        """Check if fingerprint is enabled for user"""
        conn = sqlite3.connect(self.app.config['DATABASE'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM webauthn_credentials 
            WHERE user_id = ?
        ''', (user_id,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0