import os
import sys
import shutil
import subprocess
from pathlib import Path
import configparser

def check_production_ready():
    """Check if system is ready for production deployment"""
    checks = [
        ("Python 3.8+", sys.version_info >= (3, 8)),
        ("OpenSSL", shutil.which("openssl") is not None),
        ("Systemd", os.path.exists("/lib/systemd/system")),
        ("Nginx", shutil.which("nginx") is not None),
    ]
    
    print("🔍 Checking production requirements:")
    all_ok = True
    
    for check_name, check_result in checks:
        status = "✅" if check_result else "❌"
        print(f"   {status} {check_name}")
        if not check_result:
            all_ok = False
    
    return all_ok

def generate_ssl_certificates(domain):
    """Generate SSL certificates for production"""
    print(f"🔐 Generating SSL certificates for {domain}...")
    
    cert_dir = Path("ssl")
    cert_dir.mkdir(exist_ok=True)
    
    # Generate private key
    subprocess.run([
        "openssl", "genrsa", "-out", str(cert_dir / "private.key"), "2048"
    ], check=True)
    
    # Generate CSR
    csr_conf = cert_dir / "csr.conf"
    csr_conf.write_text(f"""[ req ]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn

[ dn ]
C = US
ST = California
L = San Francisco
O = VantaVault
OU = Security
CN = {domain}

[ v3_req ]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = {domain}
DNS.2 = www.{domain}
""")
    
    subprocess.run([
        "openssl", "req", "-new", "-key", str(cert_dir / "private.key"),
        "-out", str(cert_dir / "certificate.csr"), "-config", str(csr_conf)
    ], check=True)
    
    # Generate self-signed certificate (for testing)
    # In production, use Let's Encrypt or proper CA
    subprocess.run([
        "openssl", "x509", "-req", "-days", "365",
        "-in", str(cert_dir / "certificate.csr"),
        "-signkey", str(cert_dir / "private.key"),
        "-out", str(cert_dir / "certificate.crt")
    ], check=True)
    
    print("✅ SSL certificates generated")

def create_production_config():
    """Create production configuration file"""
    config = configparser.ConfigParser()
    
    config['production'] = {
        'debug': 'false',
        'host': '0.0.0.0',
        'port': '443',
        'ssl_cert': 'ssl/certificate.crt',
        'ssl_key': 'ssl/private.key',
        'database_path': '/var/lib/vantavault/vantavault.db',
        'storage_path': '/var/lib/vantavault/encrypted_storage',
        'upload_path': '/var/lib/vantavault/uploads',
        'max_upload_size': '1073741824',  # 1GB
        'session_timeout': '1800',  # 30 minutes
    }
    
    config['security'] = {
        'require_https': 'true',
        'hsts': 'true',
        'csp': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
        'rate_limit': '100 per minute',
        'max_login_attempts': '5',
    }
    
    config['pwa'] = {
        'name': 'VantaVault',
        'short_name': 'VantaVault',
        'theme_color': '#000000',
        'background_color': '#000000',
        'display': 'standalone',
        'scope': '/',
        'start_url': '/',
    }
    
    with open('production.ini', 'w') as f:
        config.write(f)
    
    print("✅ Production configuration created")

def create_systemd_service():
    """Create systemd service file"""
    service_content = """[Unit]
Description=VantaVault - Secure Media Vault
After=network.target

[Service]
Type=simple
User=vantavault
Group=vantavault
WorkingDirectory=/opt/vantavault
Environment="PATH=/opt/vantavault/venv/bin"
ExecStart=/opt/vantavault/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    service_path = Path("/etc/systemd/system/vantavault.service")
    
    try:
        service_path.write_text(service_content)
        print("✅ Systemd service created")
        
        # Reload systemd
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        print("✅ Systemd reloaded")
        
    except PermissionError:
        print("⚠️  Run with sudo to create systemd service")
        print(f"📝 Service content saved to {service_path}")

def create_nginx_config(domain):
    """Create Nginx configuration"""
    nginx_config = f"""server {{
    listen 80;
    server_name {domain} www.{domain};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name {domain} www.{domain};
    
    ssl_certificate /opt/vantavault/ssl/certificate.crt;
    ssl_certificate_key /opt/vantavault/ssl/private.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    location / {{
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
    
    location /static {{
        alias /opt/vantavault/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }}
    
    # PWA requirements
    location /manifest.json {{
        add_header Cache-Control "public, max-age=3600";
    }}
    
    location /service-worker.js {{
        add_header Cache-Control "no-cache";
    }}
}}
"""
    
    nginx_path = Path(f"/etc/nginx/sites-available/{domain}")
    