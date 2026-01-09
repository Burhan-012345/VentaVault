#!/usr/bin/env python3
"""
VantaVault - Run Script
Start the VantaVault PWA with proper configuration
"""
import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def check_dependencies():
    """Check if all required Python packages are installed"""
    required = ['flask', 'cryptography', 'pillow']
    missing = []
    
    for package in required:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    return missing

def setup_environment():
    """Setup required directories and files"""
    directories = [
        'templates',
        'static/css',
        'static/js',
        'static/icons',
        'database',
        'encrypted_storage/real',
        'encrypted_storage/fake',
        'uploads'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print("✅ Environment setup complete")

def generate_icons():
    """Generate placeholder icons if they don't exist"""
    icon_sizes = [192, 512]
    
    for size in icon_sizes:
        icon_path = f'static/icons/icon-{size}.png'
        if not Path(icon_path).exists():
            # Create simple placeholder icon
            from PIL import Image, ImageDraw
            
            img = Image.new('RGB', (size, size), color='black')
            draw = ImageDraw.Draw(img)
            
            # Draw vault icon
            border = size // 10
            draw.rectangle([border, border, size-border, size-border], 
                          outline='white', width=border//2)
            
            # Draw lock
            lock_height = size // 3
            lock_width = size // 4
            lock_x = (size - lock_width) // 2
            lock_y = size // 2 - lock_height // 2
            
            draw.rectangle([lock_x, lock_y, lock_x+lock_width, lock_y+lock_height],
                          outline='white', width=border//2)
            
            img.save(icon_path)
            print(f"✅ Generated icon: {icon_path}")

def initialize_database():
    """Initialize the SQLite database"""
    from app import vault_manager
    vault_manager.initialize_database()
    print("✅ Database initialized")

def print_banner():
    """Print VantaVault banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║   ██╗   ██╗ █████╗ ███╗   ██╗████████╗ █████╗        ║
    ║   ██║   ██║██╔══██╗████╗  ██║╚══██╔══╝██╔══██╗       ║
    ║   ██║   ██║███████║██╔██╗ ██║   ██║   ███████║       ║
    ║   ╚██╗ ██╔╝██╔══██║██║╚██╗██║   ██║   ██╔══██║       ║
    ║    ╚████╔╝ ██║  ██║██║ ╚████║   ██║   ██║  ██║       ║
    ║     ╚═══╝  ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝       ║
    ║                                                       ║
    ║   ██╗   ██╗ █████╗ ██╗   ██╗██╗   ██╗██╗   ██╗       ║
    ║   ██║   ██║██╔══██╗██║   ██║██║   ██║██║   ██║       ║
    ║   ██║   ██║███████║██║   ██║██║   ██║██║   ██║       ║
    ║   ╚██╗ ██╔╝██╔══██║██║   ██║██║   ██║██║   ██║       ║
    ║    ╚████╔╝ ██║  ██║╚██████╔╝╚██████╔╝╚██████╔╝       ║
    ║     ╚═══╝  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝  ╚═════╝        ║
    ║                                                       ║
    ║            High-Security Media Vault PWA              ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝
    """
    print(banner)

def main():
    """Main entry point"""
    print_banner()
    
    # Check dependencies
    missing = check_dependencies()
    if missing:
        print("❌ Missing dependencies:")
        for dep in missing:
            print(f"   - {dep}")
        print("\nInstall with: pip install -r requirements.txt")
        sys.exit(1)
    
    print("✅ All dependencies installed")
    
    # Setup environment
    setup_environment()
    
    # Generate icons
    generate_icons()
    
    # Initialize database
    initialize_database()
    
    # Start Flask app
    print("\n🚀 Starting VantaVault...")
    print("🔒 Using self-signed SSL certificate")
    print("🌐 Server will be available at: https://localhost:5000")
    print("📱 Open in Chrome and install as PWA for best experience")
    print("\n⚙️  Default PINs:")
    print("   - Real vault: 0000")
    print("   - Fake vault: 123456")
    print("\n⚠️  Important: Accept the SSL certificate warning in your browser")
    
    # Open browser after delay
    time.sleep(2)
    
    try:
        # Import and run the app
        from app import app
        
        # Start Flask in a separate thread to keep console responsive
        import threading
        
        def run_app():
            app.run(
                ssl_context='adhoc',
                host='0.0.0.0',
                port=5000,
                debug=True,
                use_reloader=False
            )
        
        # Start Flask thread
        flask_thread = threading.Thread(target=run_app, daemon=True)
        flask_thread.start()
        
        # Wait a moment for server to start
        time.sleep(3)
        
        # Open browser
        print("\n🌐 Opening browser...")
        webbrowser.open('https://localhost:5000')
        
        # Keep script running
        print("\n🔄 Server is running. Press Ctrl+C to stop.")
        print("\n📋 Useful URLs:")
        print("   - Main app: https://localhost:5000")
        print("   - Dashboard: https://localhost:5000/dashboard")
        print("   - Settings: https://localhost:5000/settings")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down VantaVault...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting VantaVault: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()