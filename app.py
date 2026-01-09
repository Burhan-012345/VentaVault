"""
VantaVault - Main Flask Application with First-Time PIN Setup
Complete version for Termux with Fingerprint Support
"""
import os
import sqlite3
import json
import time
import random
from datetime import datetime, timedelta
from functools import wraps
import base64
import sys
from pathlib import Path

from flask import Flask, render_template, request, jsonify, session, send_file, Response, redirect, send_from_directory
from werkzeug.utils import secure_filename

# Import custom modules
from vault import VaultManager
from encryption import EncryptionManager
from pwa import PWA_Manager
from animations import AnimationController
from fingerprint import WebAuthnManager  # Added fingerprint support

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload for Termux
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ENCRYPTED_STORAGE'] = 'encrypted_storage/'
app.config['DATABASE'] = 'database/vantavault.db'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# WebAuthn Configuration for Termux (use localhost for development)
app.config['WEBAUTHN_RP_ID'] = 'localhost'  # For production: your-domain.com
app.config['WEBAUTHN_RP_NAME'] = 'VantaVault'
app.config['WEBAUTHN_ORIGIN'] = 'http://localhost:5000'  # For production: https://your-domain.com

# Initialize managers
vault_manager = VaultManager(app.config['DATABASE'])
encryption_manager = EncryptionManager()
pwa_manager = PWA_Manager(app)
animations = AnimationController()
webauthn_manager = WebAuthnManager(app)  # Initialize fingerprint manager

# Ensure directories exist
for directory in ['uploads', 'encrypted_storage/real', 'encrypted_storage/fake', 'database', 'static/css', 'static/js', 'static/icons']:
    os.makedirs(directory, exist_ok=True)

# Session tracking
active_sessions = {}

def is_first_time():
    """Check if this is the first time app is launched"""
    # Check if database file exists
    if not os.path.exists(app.config['DATABASE']):
        return True
    
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    
    try:
        # Check if real_vault_settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='real_vault_settings'")
        if not cursor.fetchone():
            return True
        
        # Check if any PIN is set
        cursor.execute("SELECT pin_hash FROM real_vault_settings LIMIT 1")
        result = cursor.fetchone()
        return result is None or result[0] is None
        
    except sqlite3.Error:
        return True
    finally:
        conn.close()

def requires_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        session_id = session.get('session_id')
        if not session_id or session_id not in active_sessions:
            # Check for fingerprint authentication in session
            if not session.get('fingerprint_authenticated'):
                return jsonify({'error': 'Authentication required'}), 401
        
        session_data = active_sessions.get(session_id)
        if session_data:
            if time.time() - session_data['last_activity'] > 1800:  # 30 min timeout
                del active_sessions[session_id]
                session.clear()
                return jsonify({'error': 'Session expired'}), 401
            
            # Update last activity
            session_data['last_activity'] = time.time()
        
        return f(*args, **kwargs)
    return decorated

def log_auth_attempt(attempt_type, success, ip_address, user_agent):
    """Log authentication attempts for security"""
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO auth_logs (timestamp, attempt_type, success, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), attempt_type, 
          success, ip_address, user_agent))
    conn.commit()
    conn.close()

def get_client_info(request):
    """Get client IP and user agent"""
    ip = request.remote_addr
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    
    user_agent = request.user_agent.string if request.user_agent else 'Unknown'
    
    return ip, user_agent

@app.route('/')
def index():
    """Main entry point - check if first time"""
    if is_first_time():
        return redirect('/setup')
    return render_template('pin_lock.html')

@app.route('/setup')
def setup():
    """First-time PIN setup page"""
    if not is_first_time():
        return redirect('/')
    return render_template('pin_setup.html')

@app.route('/api/setup/pin', methods=['POST'])
def setup_pin():
    """Setup initial PIN for first-time users"""
    if not is_first_time():
        return jsonify({'error': 'Already initialized'}), 400
    
    data = request.get_json()
    pin = data.get('pin', '')
    confirm_pin = data.get('confirm_pin', '')
    
    # Validate PIN
    if not pin or not confirm_pin:
        return jsonify({'error': 'PIN required'}), 400
    
    if len(pin) != 6 or not pin.isdigit():
        return jsonify({'error': 'PIN must be 6 digits'}), 400
    
    if pin != confirm_pin:
        return jsonify({'error': 'PINs do not match'}), 400
    
    # Check for simple patterns
    if len(set(pin)) == 1:  # All same digit
        return jsonify({'error': 'PIN is too simple'}), 400
    
    if pin in ['123456', '654321', '000000', '111111', '222222', '333333', 
               '444444', '555555', '666666', '777777', '888888', '999999',
               '123123', '112233', '121212']:
        return jsonify({'error': 'PIN is too common'}), 400
    
    # Check for sequential numbers
    if pin in ['012345', '123456', '234567', '345678', '456789', '567890',
               '098765', '987654', '876543', '765432', '654321', '543210']:
        return jsonify({'error': 'PIN is too predictable'}), 400
    
    try:
        # Initialize database
        print("Initializing database...")
        vault_manager.initialize_database()
        
        # Generate random fake PIN
        fake_pin = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Update real vault with user's PIN
        vault_manager.update_pin('real', pin)
        
        # Update fake vault with random PIN
        vault_manager.update_pin('fake', fake_pin)
        
        # Add fake media for decoy mode
        print("Adding fake media...")
        vault_manager.add_fake_media()
        
        # Get client info
        ip, user_agent = get_client_info(request)
        
        # Create session for immediate access
        session_id = os.urandom(16).hex()
        session['session_id'] = session_id
        session['user_id'] = session_id  # Store user_id for fingerprint
        session['vault_type'] = 'real'
        session['authenticated'] = True
        
        active_sessions[session_id] = {
            'vault_type': 'real',
            'user_id': session_id,
            'created_at': time.time(),
            'last_activity': time.time(),
            'ip_address': ip
        }
        
        # Log the setup
        log_auth_attempt('SETUP', True, ip, user_agent)
        
        print(f"Vault created for user. Real PIN: {pin}, Fake PIN: {fake_pin}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'animation_token': animations.generate_token(),
            'message': 'Secure vault created successfully!'
        })
        
    except Exception as e:
        print(f"Setup error: {e}")
        return jsonify({'error': f'Setup failed: {str(e)}'}), 500

# ==================== FINGERPRINT ROUTES ====================

@app.route('/api/fingerprint/setup', methods=['POST'])
@requires_auth
def fingerprint_setup():
    """Start fingerprint setup process"""
    try:
        session_id = session.get('session_id')
        if not session_id or session_id not in active_sessions:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_id = active_sessions[session_id].get('user_id', session_id)
        options = webauthn_manager.register_credential(user_id)
        
        return jsonify(options)
        
    except Exception as e:
        return jsonify({'error': f'Fingerprint setup failed: {str(e)}'}), 500

@app.route('/api/fingerprint/verify-setup', methods=['POST'])
@requires_auth
def fingerprint_verify_setup():
    """Verify fingerprint setup"""
    try:
        data = request.get_json()
        result = webauthn_manager.verify_registration(data)
        
        # Get client info for logging
        ip, user_agent = get_client_info(request)
        
        if result.get('success'):
            log_auth_attempt('FINGERPRINT_SETUP', True, ip, user_agent)
        else:
            log_auth_attempt('FINGERPRINT_SETUP', False, ip, user_agent)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'Verification failed: {str(e)}'}), 500

@app.route('/api/fingerprint/authenticate', methods=['POST'])
def fingerprint_authenticate():
    """Start fingerprint authentication"""
    try:
        # Get user_id from session if available, otherwise use default
        session_id = session.get('session_id')
        user_id = None
        
        if session_id and session_id in active_sessions:
            user_id = active_sessions[session_id].get('user_id')
        else:
            # Try to get user_id from last successful login
            user_id = session.get('last_user_id')
        
        if not user_id:
            # For first-time fingerprint auth, we need to know which user
            return jsonify({'error': 'User not identified'}), 400
        
        result = webauthn_manager.authenticate(user_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 500

@app.route('/api/fingerprint/verify-auth', methods=['POST'])
def fingerprint_verify_auth():
    """Verify fingerprint authentication"""
    try:
        data = request.get_json()
        result = webauthn_manager.verify_authentication(data)
        
        # Get client info for logging
        ip, user_agent = get_client_info(request)
        
        if result.get('success'):
            # Authentication successful - create session
            session_id = os.urandom(16).hex()
            session['session_id'] = session_id
            session['vault_type'] = 'real'
            session['authenticated'] = True
            session['fingerprint_authenticated'] = True
            session['auth_method'] = 'fingerprint'
            session['auth_time'] = datetime.now().isoformat()
            
            # Get user_id from webauthn session
            user_id = session.get('webauthn_user_id')
            
            active_sessions[session_id] = {
                'vault_type': 'real',
                'user_id': user_id or session_id,
                'created_at': time.time(),
                'last_activity': time.time(),
                'ip_address': ip,
                'auth_method': 'fingerprint'
            }
            
            # Store last user_id for future fingerprint auth
            session['last_user_id'] = user_id or session_id
            
            log_auth_attempt('FINGERPRINT', True, ip, user_agent)
            
            # Add animation token for success response
            result['animation_token'] = animations.generate_token()
            result['session_id'] = session_id
            
        else:
            log_auth_attempt('FINGERPRINT', False, ip, user_agent)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'Verification failed: {str(e)}'}), 500

@app.route('/api/fingerprint/status', methods=['GET'])
@requires_auth
def fingerprint_status():
    """Check fingerprint status for current user"""
    try:
        session_id = session.get('session_id')
        if not session_id or session_id not in active_sessions:
            return jsonify({'enabled': False})
        
        user_id = active_sessions[session_id].get('user_id', session_id)
        enabled = webauthn_manager.is_fingerprint_enabled(user_id)
        
        return jsonify({'enabled': enabled})
        
    except Exception as e:
        return jsonify({'enabled': False, 'error': str(e)})

@app.route('/api/fingerprint/remove', methods=['DELETE'])
@requires_auth
def remove_fingerprint():
    """Remove fingerprint credential"""
    try:
        session_id = session.get('session_id')
        if not session_id or session_id not in active_sessions:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_id = active_sessions[session_id].get('user_id', session_id)
        
        # Remove credentials from database
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute('DELETE FROM webauthn_credentials WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Fingerprint removed'})
        
    except Exception as e:
        return jsonify({'error': f'Failed to remove fingerprint: {str(e)}'}), 500

# ==================== PIN AUTHENTICATION ====================

@app.route('/pin/verify', methods=['POST'])
def verify_pin():
    """Verify PIN and create session"""
    data = request.get_json()
    pin = data.get('pin', '')
    
    # Get client info
    ip, user_agent = get_client_info(request)
    
    # Check if IP is blocked
    if vault_manager.is_ip_blocked(ip):
        return jsonify({
            'success': False,
            'message': 'Too many failed attempts. Try again later.'
        }), 429
    
    # Log attempt
    log_auth_attempt('PIN', False, ip, user_agent)
    
    # Verify PIN
    vault_type = vault_manager.verify_pin(pin)
    
    if vault_type == 'real':
        # Create session for real vault
        session_id = os.urandom(16).hex()
        session['session_id'] = session_id
        session['user_id'] = session_id  # Store user_id for fingerprint
        session['vault_type'] = 'real'
        session['authenticated'] = True
        
        active_sessions[session_id] = {
            'vault_type': 'real',
            'user_id': session_id,
            'created_at': time.time(),
            'last_activity': time.time(),
            'ip_address': ip
        }
        
        log_auth_attempt('PIN', True, ip, user_agent)
        return jsonify({
            'success': True,
            'vault_type': 'real',
            'session_id': session_id,
            'animation_token': animations.generate_token()
        })
    
    elif vault_type == 'fake':
        # Create session for fake vault
        session_id = os.urandom(16).hex()
        session['session_id'] = session_id
        session['vault_type'] = 'fake'
        session['authenticated'] = True
        
        active_sessions[session_id] = {
            'vault_type': 'fake',
            'created_at': time.time(),
            'last_activity': time.time(),
            'ip_address': ip
        }
        
        return jsonify({
            'success': True,
            'vault_type': 'fake',
            'session_id': session_id
        })
    
    else:
        # Failed attempt
        vault_manager.log_failed_attempt(ip)
        return jsonify({
            'success': False,
            'message': 'Invalid PIN'
        }), 401

# ==================== OTHER ROUTES (unchanged from original) ====================

@app.route('/unlock/animation')
def unlock_animation():
    """Serve unlock animation page"""
    token = request.args.get('token')
    if not animations.validate_token(token):
        return redirect('/')
    
    return render_template('unlock_animation.html', token=token)

@app.route('/dashboard')
@requires_auth
def dashboard():
    """Main dashboard after unlock"""
    session_data = active_sessions.get(session.get('session_id'))
    if not session_data:
        return redirect('/')
    
    vault_type = session_data['vault_type']
    if vault_type == 'fake':
        return render_template('fake_vault.html')
    
    return render_template('dashboard.html')

@app.route('/api/media/upload', methods=['POST'])
@requires_auth
def upload_media():
    """Upload and encrypt media files"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    folder_id = request.form.get('folder_id', 'default')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Secure filename
    filename = secure_filename(file.filename)
    
    # Create uploads directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Save file temporarily
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    # Encrypt and store file
    try:
        encrypted_path, thumbnail_path = vault_manager.encrypt_and_store(
            file_path, 
            session_id,
            folder_id
        )
        
        # Store metadata
        vault_type = active_sessions[session_id]['vault_type']
        media_id = vault_manager.store_media_metadata(
            filename,
            encrypted_path,
            thumbnail_path,
            folder_id,
            vault_type
        )
        
        return jsonify({
            'success': True,
            'media_id': media_id,
            'filename': filename,
            'thumbnail': thumbnail_path
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500
    finally:
        # Clean up temp file if it exists
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

@app.route('/api/media/list')
@requires_auth
def list_media():
    """List media files in vault"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    folder_id = request.args.get('folder_id', 'default')
    
    media_list = vault_manager.get_media_list(vault_type, folder_id)
    return jsonify({'media': media_list})

@app.route('/api/media/<int:media_id>')
@requires_auth
def get_media(media_id):
    """Retrieve and decrypt media file"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    media_info = vault_manager.get_media_info(media_id, vault_type)
    
    if not media_info:
        return jsonify({'error': 'Media not found'}), 404
    
    try:
        # Decrypt file
        decrypted_path = vault_manager.decrypt_media(media_info['encrypted_path'], session_id)
        
        # Send file
        response = send_file(
            decrypted_path,
            mimetype=media_info['mimetype'],
            as_attachment=True,
            download_name=media_info['filename']
        )
        
        # Schedule cleanup of temp file
        def cleanup_temp():
            try:
                if os.path.exists(decrypted_path):
                    os.remove(decrypted_path)
            except:
                pass
        
        response.call_on_close(cleanup_temp)
        return response
        
    except Exception as e:
        print(f"Get media error: {e}")
        return jsonify({'error': 'Failed to retrieve media'}), 500

@app.route('/api/media/thumbnail/<int:media_id>')
@requires_auth
def get_thumbnail(media_id):
    """Get media thumbnail"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    media_info = vault_manager.get_media_info(media_id, vault_type)
    
    if not media_info or not media_info.get('thumbnail_path'):
        # Return default thumbnail
        return send_from_directory('static/icons', 'icon-192.png')
    
    try:
        return send_file(
            media_info['thumbnail_path'],
            mimetype='image/jpeg',
            as_attachment=False
        )
    except:
        # Fallback to default thumbnail
        return send_from_directory('static/icons', 'icon-192.png')

@app.route('/api/media/delete/<int:media_id>', methods=['DELETE'])
@requires_auth
def delete_media(media_id):
    """Delete media file (move to recycle bin)"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    
    if vault_manager.delete_media(media_id, vault_type, permanent=False):
        return jsonify({'success': True})
    
    return jsonify({'error': 'Failed to delete media'}), 500

@app.route('/api/folders', methods=['GET', 'POST'])
@requires_auth
def manage_folders():
    """Create or list folders"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    
    if request.method == 'POST':
        data = request.get_json()
        folder_name = data.get('name')
        
        if not folder_name or not folder_name.strip():
            return jsonify({'error': 'Folder name required'}), 400
        
        folder_id = vault_manager.create_folder(folder_name.strip(), vault_type)
        return jsonify({
            'success': True,
            'folder_id': folder_id,
            'folder_name': folder_name
        })
    
    else:
        folders = vault_manager.get_folders(vault_type)
        return jsonify({'folders': folders})

@app.route('/api/settings', methods=['GET', 'PUT'])
@requires_auth
def manage_settings():
    """Get or update settings"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    
    if vault_type != 'real':
        return jsonify({'error': 'Access denied'}), 403
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Update fingerprint setting separately if provided
        if 'fingerprint_enabled' in data:
            # This is handled by the fingerprint routes, but we can update a flag
            pass
        
        if vault_manager.update_settings(data):
            return jsonify({'success': True})
        return jsonify({'error': 'Failed to update settings'}), 500
    
    else:
        settings = vault_manager.get_settings()
        
        # Add fingerprint status to settings
        session_id = session.get('session_id')
        if session_id and session_id in active_sessions:
            user_id = active_sessions[session_id].get('user_id', session_id)
            settings['fingerprint_enabled'] = webauthn_manager.is_fingerprint_enabled(user_id)
        
        return jsonify(settings)

@app.route('/api/settings/fingerprint', methods=['POST'])
@requires_auth
def update_fingerprint_setting():
    """Update fingerprint setting preference"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    
    if vault_type != 'real':
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    # Store fingerprint preference in settings
    settings = {'fingerprint_enabled': enabled}
    if vault_manager.update_settings(settings):
        return jsonify({'success': True})
    
    return jsonify({'error': 'Failed to update fingerprint setting'}), 500

@app.route('/api/settings/pin', methods=['POST'])
@requires_auth
def change_pin():
    """Change PIN"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    
    if vault_type != 'real':
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    new_pin = data.get('new_pin')
    current_pin = data.get('current_pin')
    
    # Verify current PIN
    if not vault_manager.verify_pin(current_pin) == 'real':
        return jsonify({'error': 'Current PIN is incorrect'}), 401
    
    # Validate new PIN
    if not new_pin or len(new_pin) != 6 or not new_pin.isdigit():
        return jsonify({'error': 'PIN must be 6 digits'}), 400
    
    # Check for simple patterns
    if len(set(new_pin)) == 1:
        return jsonify({'error': 'PIN is too simple'}), 400
    
    if new_pin in ['123456', '654321', '000000', '111111', '222222', '333333', 
                   '444444', '555555', '666666', '777777', '888888', '999999']:
        return jsonify({'error': 'PIN is too common'}), 400
    
    if vault_manager.update_pin(vault_type, new_pin):
        # Log out all sessions
        session.clear()
        active_sessions.clear()
        
        return jsonify({
            'success': True,
            'message': 'PIN changed successfully. Please login again.'
        })
    
    return jsonify({'error': 'Failed to change PIN'}), 500

@app.route('/api/logs')
@requires_auth
def get_logs():
    """Get security logs (real vault only)"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    
    if vault_type != 'real':
        return jsonify({'error': 'Access denied'}), 403
    
    logs = vault_manager.get_security_logs()
    return jsonify({'logs': logs})

@app.route('/api/lock', methods=['POST'])
def lock_vault():
    """Lock the vault and clear session"""
    session_id = session.get('session_id')
    if session_id in active_sessions:
        del active_sessions[session_id]
    
    session.clear()
    return jsonify({'success': True})

@app.route('/api/share/create', methods=['POST'])
@requires_auth
def create_share():
    """Create temporary share link"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    media_id = data.get('media_id')
    expiry_hours = data.get('expiry_hours', 24)
    
    if not media_id:
        return jsonify({'error': 'Media ID required'}), 400
    
    share_token = vault_manager.create_share_link(
        media_id,
        expiry_hours,
        session_id
    )
    
    if not share_token:
        return jsonify({'error': 'Failed to create share link'}), 500
    
    return jsonify({
        'success': True,
        'share_token': share_token,
        'expiry': expiry_hours,
        'share_url': f'/share/{share_token}'
    })

@app.route('/share/<token>')
def access_share(token):
    """Access shared media"""
    media_data = vault_manager.access_share_link(token)
    
    if not media_data:
        return jsonify({'error': 'Share expired or invalid'}), 404
    
    try:
        # Send the file
        return send_file(
            media_data['path'],
            mimetype=media_data['mimetype'],
            as_attachment=True,
            download_name=media_data['filename']
        )
    except Exception as e:
        print(f"Share access error: {e}")
        return jsonify({'error': 'Failed to access shared media'}), 500

@app.route('/service-worker.js')
def service_worker():
    """Serve service worker"""
    return send_from_directory('static/js', 'service-worker.js')

@app.route('/manifest.json')
def manifest():
    """Serve web app manifest"""
    return send_from_directory('static', 'manifest.json')

@app.route('/gallery')
@requires_auth
def gallery():
    """Media gallery page"""
    session_data = active_sessions.get(session.get('session_id'))
    if not session_data:
        return redirect('/')
    
    vault_type = session_data['vault_type']
    if vault_type == 'fake':
        return render_template('fake_vault.html')
    
    return render_template('gallery.html')

@app.route('/settings')
@requires_auth
def settings():
    """Settings page"""
    session_data = active_sessions.get(session.get('session_id'))
    if not session_data:
        return redirect('/')
    
    vault_type = session_data['vault_type']
    if vault_type == 'fake':
        return render_template('fake_vault.html')
    
    return render_template('settings.html')

@app.route('/api/cleanup', methods=['POST'])
@requires_auth
def cleanup():
    """Clean up expired data"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    
    if vault_type != 'real':
        return jsonify({'error': 'Access denied'}), 403
    
    # Clean expired shares
    shares_deleted = vault_manager.cleanup_expired_shares()
    
    # Clean recycle bin
    recycle_deleted = vault_manager.cleanup_recycle_bin()
    
    return jsonify({
        'success': True,
        'shares_deleted': shares_deleted,
        'recycle_deleted': recycle_deleted
    })

@app.route('/api/storage/stats')
@requires_auth
def storage_stats():
    """Get storage statistics"""
    session_id = session.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401
    
    vault_type = active_sessions[session_id]['vault_type']
    stats = vault_manager.get_storage_stats(vault_type)
    return jsonify(stats)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'first_time': is_first_time(),
        'webauthn_available': webauthn_manager.WEBAUTHN_AVAILABLE if hasattr(webauthn_manager, 'WEBAUTHN_AVAILABLE') else False
    })

@app.route('/offline')
def offline():
    """Offline page for PWA"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>VantaVault - Offline</title>
        <style>
            body {
                background: #000;
                color: #fff;
                font-family: sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .container {
                text-align: center;
                padding: 2rem;
            }
            h1 {
                color: #f5f5f5;
                margin-bottom: 1rem;
            }
            p {
                color: #aaa;
                margin-bottom: 2rem;
            }
            .icon {
                font-size: 4rem;
                margin-bottom: 1rem;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">⚠️</div>
            <h1>Offline</h1>
            <p>You are currently offline. Please reconnect to access VantaVault.</p>
        </div>
    </body>
    </html>
    '''

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    print(f"Server error: {error}")
    return jsonify({'error': 'Server error'}), 500

@app.errorhandler(413)
def too_large(error):
    return jsonify({'error': 'File too large (max 100MB)'}), 413

@app.errorhandler(401)
def unauthorized(error):
    return jsonify({'error': 'Authentication required'}), 401

@app.errorhandler(403)
def forbidden(error):
    return jsonify({'error': 'Access denied'}), 403

@app.before_request
def check_maintenance():
    """Check for maintenance or other pre-request conditions"""
    # You can add maintenance mode checks here
    pass

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Add WebAuthn headers
    response.headers['Access-Control-Allow-Origin'] = app.config['WEBAUTHN_ORIGIN']
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    return response

def print_startup_info():
    """Print startup information"""
    print("\n" + "="*60)
    print("🚀 VANTAVAULT - Secure Media Vault with Fingerprint Support")
    print("="*60)
    
    if is_first_time():
        print("\n🎯 FIRST TIME SETUP DETECTED")
        print("   New users will create their own 6-digit PIN")
        print("   No default PINs - complete security from start")
    else:
        print("\n✅ Vault already initialized")
        print("   Using existing PIN for authentication")
    
    # Check fingerprint availability
    if hasattr(webauthn_manager, 'WEBAUTHN_AVAILABLE'):
        if webauthn_manager.WEBAUTHN_AVAILABLE:
            print("✅ Fingerprint authentication: AVAILABLE")
        else:
            print("⚠️  Fingerprint authentication: NOT AVAILABLE")
            print("   Install: pip install webauthn")
    
    # Get local IP address
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        print("\n🌐 ACCESS URLs:")
        print(f"   Termux browser: http://localhost:5000")
        print(f"   Phone browser:  http://{local_ip}:5000")
        print(f"   On same WiFi:   http://{local_ip}:5000")
    except:
        print("\n🌐 ACCESS URL:")
        print("   http://localhost:5000")
    
    print("\n⚠️  NOTE: Running without SSL (HTTP only)")
    print("   WebAuthn requires HTTPS for full functionality")
    print("   For testing, run: flask run --cert=adhoc")
    print("="*60 + "\n")

if __name__ == '__main__':
    print_startup_info()
    
    # Run without SSL for Termux
    try:
        app.run(
            host='0.0.0.0', 
            port=5000, 
            debug=True, 
            threaded=True,
            use_reloader=False  # Disable reloader for Termux
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down VantaVault...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)