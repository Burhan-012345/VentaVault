/**
 * VantaVault - Main Application Module
 * Handles core app functionality, PWA installation, and theme management
 */

class VantaVaultApp {
    constructor() {
        this.isPWA = false;
        this.isStandalone = false;
        this.theme = 'dark';
        this.isTouchDevice = false;
        this.isMobile = false;
        this.init();
    }

    init() {
        this.detectDeviceType();
        this.detectPWA();
        this.setupTheme();
        this.setupInstallPrompt();
        this.setupServiceWorker();
        this.setupVisibilityHandlers();
        this.setupKeyboardShortcuts();
        this.setupErrorHandling();
        this.setupMobileFeatures();
        this.setupMobileInstall();
        this.setupPerformanceMonitoring();
    }

    detectDeviceType() {
        // Detect touch device
        this.isTouchDevice = 'ontouchstart' in window || 
                            navigator.maxTouchPoints > 0 || 
                            navigator.msMaxTouchPoints > 0;
        
        // Detect mobile device
        const userAgent = navigator.userAgent.toLowerCase();
        this.isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent);
        
        // Add device classes to body
        if (this.isTouchDevice) {
            document.body.classList.add('touch-device');
        }
        if (this.isMobile) {
            document.body.classList.add('mobile-device');
        }
        
        // Detect iOS specifically
        this.isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        
        // Detect Android
        this.isAndroid = /android/i.test(userAgent);
    }

    detectPWA() {
        // Check if running as PWA
        if (window.matchMedia('(display-mode: standalone)').matches ||
            window.navigator.standalone ||
            document.referrer.includes('android-app://')) {
            this.isPWA = true;
            this.isStandalone = true;
            document.body.classList.add('pwa-mode');
            document.body.classList.add('standalone-mode');
        }
    }

    setupTheme() {
        // Load saved theme or detect system preference
        const savedTheme = localStorage.getItem('vantavault_theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme) {
            this.theme = savedTheme;
        } else if (systemPrefersDark) {
            this.theme = 'dark';
        } else {
            this.theme = 'light';
        }
        
        this.applyTheme();
        
        // Watch for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem('vantavault_theme')) {
                this.theme = e.matches ? 'dark' : 'light';
                this.applyTheme();
            }
        });
    }

    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        localStorage.setItem('vantavault_theme', this.theme);
        
        // Update meta theme-color for PWA
        const themeColor = this.theme === 'dark' ? '#000000' : '#ffffff';
        document.querySelector('meta[name="theme-color"]').setAttribute('content', themeColor);
        
        // Update iOS status bar color
        if (this.isIOS) {
            document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]')
                .setAttribute('content', this.theme === 'dark' ? 'black-translucent' : 'default');
        }
    }

    toggleTheme() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        this.applyTheme();
        
        // Show notification
        this.showNotification(`Switched to ${this.theme} theme`);
    }

    setupInstallPrompt() {
        let deferredPrompt;
        
        window.addEventListener('beforeinstallprompt', (e) => {
            // Prevent Chrome 67 and earlier from automatically showing the prompt
            e.preventDefault();
            deferredPrompt = e;
            
            // Show install button if not already installed
            if (!this.isPWA) {
                this.showInstallButton();
            }
        });
        
        window.addEventListener('appinstalled', () => {
            this.isPWA = true;
            this.isStandalone = true;
            deferredPrompt = null;
            document.body.classList.add('pwa-mode');
            document.body.classList.add('standalone-mode');
            
            // Hide install button
            this.hideInstallButton();
            
            // Show welcome message
            this.showNotification('VantaVault installed successfully!', 'success');
            
            // Log installation
            if (window.gtag) {
                gtag('event', 'install', {
                    'event_category': 'engagement',
                    'event_label': 'pwa_install'
                });
            }
        });
        
        // Expose install function
        window.installPWA = async () => {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                
                if (outcome === 'accepted') {
                    console.log('User accepted the install prompt');
                    if (window.gtag) {
                        gtag('event', 'install_accept', {
                            'event_category': 'engagement'
                        });
                    }
                } else {
                    console.log('User dismissed the install prompt');
                    if (window.gtag) {
                        gtag('event', 'install_decline', {
                            'event_category': 'engagement'
                        });
                    }
                }
                deferredPrompt = null;
            }
        };
    }

    showInstallButton() {
        // Don't show on iOS (different installation process)
        if (this.isIOS) return;
        
        // Create install button
        const installBtn = document.createElement('button');
        installBtn.id = 'installBtn';
        installBtn.className = 'install-btn';
        installBtn.setAttribute('aria-label', 'Install VantaVault app');
        installBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            <span class="install-text">Install App</span>
        `;
        installBtn.onclick = window.installPWA;
        
        // Style the button
        installBtn.style.cssText = `
            position: fixed;
            bottom: calc(20px + env(safe-area-inset-bottom, 0px));
            left: 20px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.75rem 1.5rem;
            border-radius: var(--border-radius);
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            z-index: 1000;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            font-size: 0.9rem;
            min-height: 44px;
        `;
        
        installBtn.addEventListener('mouseenter', () => {
            installBtn.style.background = 'var(--glass-border)';
            installBtn.style.transform = 'translateY(-2px)';
            installBtn.style.boxShadow = '0 6px 16px rgba(0, 0, 0, 0.2)';
        });
        
        installBtn.addEventListener('mouseleave', () => {
            installBtn.style.background = 'var(--bg-card)';
            installBtn.style.transform = 'translateY(0)';
            installBtn.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
        });
        
        // Touch feedback
        installBtn.addEventListener('touchstart', () => {
            installBtn.style.transform = 'scale(0.98)';
        });
        
        installBtn.addEventListener('touchend', () => {
            installBtn.style.transform = 'scale(1)';
        });
        
        document.body.appendChild(installBtn);
        
        // Auto-hide after 10 seconds on mobile
        if (this.isMobile) {
            setTimeout(() => {
                if (installBtn.parentElement) {
                    installBtn.style.opacity = '0';
                    installBtn.style.transform = 'translateY(20px)';
                    setTimeout(() => {
                        if (installBtn.parentElement) {
                            installBtn.remove();
                        }
                    }, 300);
                }
            }, 10000);
        }
    }

    hideInstallButton() {
        const installBtn = document.getElementById('installBtn');
        if (installBtn) {
            installBtn.style.opacity = '0';
            installBtn.style.transform = 'translateY(20px)';
            setTimeout(() => {
                if (installBtn.parentElement) {
                    installBtn.remove();
                }
            }, 300);
        }
    }

    setupServiceWorker() {
        if ('serviceWorker' in navigator) {
            // Register service worker
            navigator.serviceWorker.register('/service-worker.js')
                .then(registration => {
                    console.log('ServiceWorker registration successful');
                    
                    // Check for updates
                    registration.addEventListener('updatefound', () => {
                        const newWorker = registration.installing;
                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                this.showUpdateNotification();
                            }
                        });
                    });
                    
                    // Periodic update check (every 6 hours)
                    setInterval(() => {
                        registration.update();
                    }, 6 * 60 * 60 * 1000);
                })
                .catch(error => {
                    console.error('ServiceWorker registration failed:', error);
                });
            
            // Listen for messages from service worker
            navigator.serviceWorker.addEventListener('message', event => {
                if (event.data && event.data.type === 'NEW_VERSION') {
                    this.showUpdateNotification();
                }
                if (event.data && event.data.type === 'SYNC_COMPLETE') {
                    this.showNotification('Background sync complete', 'success');
                }
                if (event.data && event.data.type === 'OFFLINE_UPLOAD') {
                    this.showNotification('File uploaded when back online', 'success');
                }
            });
            
            // Background sync support
            if ('sync' in registration) {
                // Register background sync
                registration.sync.register('upload-sync')
                    .then(() => console.log('Background sync registered'))
                    .catch(err => console.error('Background sync registration failed:', err));
            }
        }
    }

    showUpdateNotification() {
        const notification = document.createElement('div');
        notification.className = 'update-notification';
        notification.setAttribute('role', 'alert');
        notification.innerHTML = `
            <div class="update-content">
                <strong>🔄 Update Available</strong>
                <p>A new version of VantaVault is available</p>
                <div class="update-actions">
                    <button onclick="location.reload()" class="btn btn-primary" aria-label="Update now">
                        Update Now
                    </button>
                    <button onclick="this.parentElement.parentElement.parentElement.remove()" 
                            class="btn btn-secondary" aria-label="Update later">
                        Later
                    </button>
                </div>
            </div>
        `;
        
        notification.style.cssText = `
            position: fixed;
            top: calc(20px + env(safe-area-inset-top, 0px));
            right: 20px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius);
            padding: 1rem;
            z-index: 10000;
            backdrop-filter: blur(10px);
            max-width: 300px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            animation: slideInRight 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 30 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 30000);
    }

    setupVisibilityHandlers() {
        // Handle app visibility changes
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                // App is minimized/backgrounded
                this.onAppHidden();
                
                // Track time spent
                if (this.sessionStart) {
                    const timeSpent = Date.now() - this.sessionStart;
                    console.log(`Session duration: ${Math.round(timeSpent / 1000)}s`);
                }
            } else {
                // App is visible again
                this.onAppVisible();
                this.sessionStart = Date.now();
            }
        });
        
        // Handle page unload
        window.addEventListener('beforeunload', (e) => {
            // Don't show confirmation for normal navigation within app
            if (window.location.pathname !== '/' && 
                !window.location.pathname.includes('/api/')) {
                return;
            }
            
            // Show confirmation if there are pending uploads
            if (window.gallery && window.gallery.uploadQueue && window.gallery.uploadQueue.length > 0) {
                e.preventDefault();
                e.returnValue = 'You have pending uploads. Are you sure you want to leave?';
                return e.returnValue;
            }
            
            // Save scroll position
            sessionStorage.setItem('scroll_pos', window.scrollY);
        });
        
        // Restore scroll position
        window.addEventListener('load', () => {
            const scrollPos = sessionStorage.getItem('scroll_pos');
            if (scrollPos) {
                setTimeout(() => {
                    window.scrollTo(0, parseInt(scrollPos));
                    sessionStorage.removeItem('scroll_pos');
                }, 100);
            }
        });
    }

    onAppHidden() {
        // Auto-lock if enabled
        const autoLock = localStorage.getItem('auto_lock_enabled') !== 'false';
        const lockOnMinimize = localStorage.getItem('lock_on_minimize') === 'true';
        
        if (autoLock && lockOnMinimize && window.location.pathname !== '/') {
            // Store current location to return after unlock
            const currentPath = window.location.pathname + window.location.search;
            sessionStorage.setItem('return_path', currentPath);
            
            // Store scroll position
            sessionStorage.setItem('scroll_pos', window.scrollY);
            
            // Navigate to lock screen
            setTimeout(() => {
                window.location.href = '/';
            }, 100);
        }
        
        // Save any unsaved data
        this.saveDraftData();
    }

    onAppVisible() {
        // Check if we need to return to previous location
        const returnPath = sessionStorage.getItem('return_path');
        if (returnPath && returnPath !== '/') {
            sessionStorage.removeItem('return_path');
            window.location.href = returnPath;
        }
        
        // Check network status
        this.checkNetworkStatus();
    }

    saveDraftData() {
        // Save any form data or drafts
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            const formData = new FormData(form);
            const data = {};
            formData.forEach((value, key) => {
                data[key] = value;
            });
            if (Object.keys(data).length > 0) {
                sessionStorage.setItem(`form_draft_${form.id}`, JSON.stringify(data));
            }
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger shortcuts in input fields
            if (e.target.tagName === 'INPUT' || 
                e.target.tagName === 'TEXTAREA' ||
                e.target.isContentEditable) {
                return;
            }
            
            // Ctrl/Cmd + T: Toggle theme
            if ((e.ctrlKey || e.metaKey) && e.key === 't') {
                e.preventDefault();
                this.toggleTheme();
            }
            
            // Ctrl/Cmd + L: Lock vault
            if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
                e.preventDefault();
                this.lockVault();
            }
            
            // Ctrl/Cmd + U: Upload files
            if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
                e.preventDefault();
                this.openUpload();
            }
            
            // Ctrl/Cmd + ,: Open settings
            if ((e.ctrlKey || e.metaKey) && e.key === ',') {
                e.preventDefault();
                this.openSettings();
            }
            
            // F1: Help
            if (e.key === 'F1') {
                e.preventDefault();
                this.showHelp();
            }
            
            // Escape: Clear selection/close modals
            if (e.key === 'Escape') {
                this.handleEscape();
            }
            
            // Space: Play/pause video in viewer
            if (e.key === ' ' && document.querySelector('.media-viewer')) {
                e.preventDefault();
                const video = document.querySelector('.media-viewer video');
                if (video) {
                    video.paused ? video.play() : video.pause();
                }
            }
            
            // Arrow keys: Navigate gallery
            if (e.key.startsWith('Arrow') && window.gallery) {
                this.handleArrowKeys(e);
            }
        });
    }

    handleArrowKeys(e) {
        const viewer = document.querySelector('.media-viewer');
        if (viewer) {
            // Navigation in media viewer
            e.preventDefault();
            if (e.key === 'ArrowRight') {
                window.gallery.nextMedia();
            } else if (e.key === 'ArrowLeft') {
                window.gallery.prevMedia();
            }
        } else if (window.gallery && window.gallery.currentMedia) {
            // Navigation in gallery grid
            const items = Array.from(document.querySelectorAll('.media-item'));
            const currentIndex = items.findIndex(item => 
                item.dataset.id === window.gallery.currentMedia.id);
            
            if (currentIndex !== -1) {
                let newIndex = currentIndex;
                if (e.key === 'ArrowRight') newIndex++;
                if (e.key === 'ArrowLeft') newIndex--;
                if (e.key === 'ArrowDown') newIndex += Math.floor(window.innerWidth / 150); // Approx columns
                if (e.key === 'ArrowUp') newIndex -= Math.floor(window.innerWidth / 150);
                
                if (newIndex >= 0 && newIndex < items.length) {
                    items[newIndex].focus();
                    window.gallery.currentMedia = { id: items[newIndex].dataset.id };
                }
            }
        }
    }

    lockVault() {
        if (window.location.pathname !== '/') {
            fetch('/api/lock', { method: 'POST' })
                .then(() => {
                    window.location.href = '/';
                })
                .catch(() => {
                    window.location.href = '/';
                });
        }
    }

    openUpload() {
        if (window.location.pathname.includes('/gallery')) {
            if (typeof showUploadModal === 'function') {
                showUploadModal();
            }
        } else {
            window.location.href = '/gallery?upload=true';
        }
    }

    openSettings() {
        if (window.location.pathname !== '/settings') {
            window.location.href = '/settings';
        }
    }

    showHelp() {
        const helpModal = document.createElement('div');
        helpModal.className = 'modal';
        helpModal.setAttribute('role', 'dialog');
        helpModal.setAttribute('aria-labelledby', 'help-title');
        helpModal.innerHTML = `
            <div class="modal-content" style="max-width: 600px;">
                <h2 id="help-title">VantaVault Help & Shortcuts</h2>
                
                <div class="help-section">
                    <h3>📋 Keyboard Shortcuts</h3>
                    <div class="shortcut-list">
                        <div class="shortcut-item">
                            <kbd>Ctrl/Cmd + L</kbd>
                            <span>Lock vault</span>
                        </div>
                        <div class="shortcut-item">
                            <kbd>Ctrl/Cmd + U</kbd>
                            <span>Upload files</span>
                        </div>
                        <div class="shortcut-item">
                            <kbd>Ctrl/Cmd + T</kbd>
                            <span>Toggle theme</span>
                        </div>
                        <div class="shortcut-item">
                            <kbd>Ctrl/Cmd + ,</kbd>
                            <span>Open settings</span>
                        </div>
                        <div class="shortcut-item">
                            <kbd>F1</kbd>
                            <span>Show help</span>
                        </div>
                        <div class="shortcut-item">
                            <kbd>Escape</kbd>
                            <span>Clear selection/Close modal</span>
                        </div>
                        <div class="shortcut-item">
                            <kbd>Space</kbd>
                            <span>Play/pause video</span>
                        </div>
                        <div class="shortcut-item">
                            <kbd>Arrow Keys</kbd>
                            <span>Navigate gallery</span>
                        </div>
                    </div>
                </div>
                
                <div class="help-section">
                    <h3>👆 Touch Gestures (Mobile)</h3>
                    <div class="shortcut-list">
                        <div class="shortcut-item">
                            <span>📱 Tap & hold</span>
                            <span>Select item / Open context menu</span>
                        </div>
                        <div class="shortcut-item">
                            <span>📱 Swipe left/right</span>
                            <span>Navigate between items</span>
                        </div>
                        <div class="shortcut-item">
                            <span>📱 Pinch zoom</span>
                            <span>Zoom in/out on photos</span>
                        </div>
                        <div class="shortcut-item">
                            <span>📱 Pull down</span>
                            <span>Refresh gallery</span>
                        </div>
                    </div>
                </div>
                
                <div class="help-section">
                    <h3>🔒 Security Tips</h3>
                    <ul>
                        <li>Always use a strong, unique PIN (not 0000)</li>
                        <li>Enable fingerprint authentication for convenience</li>
                        <li>Use decoy mode for plausible deniability</li>
                        <li>Enable auto-lock for security</li>
                        <li>Regularly backup your encrypted vault</li>
                        <li>Use secure deletion for sensitive files</li>
                    </ul>
                </div>
                
                <div class="help-section">
                    <h3>📱 Mobile Features</h3>
                    <ul>
                        <li>Install to home screen for native app experience</li>
                        <li>Works offline - access your vault anywhere</li>
                        <li>Camera upload directly to vault</li>
                        <li>Face/Touch ID authentication</li>
                        <li>Optimized for touch interactions</li>
                    </ul>
                </div>
                
                <div class="modal-actions">
                    <button class="btn" onclick="this.closest('.modal').remove()" aria-label="Close help">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(helpModal);
        
        // Focus first button for accessibility
        setTimeout(() => {
            helpModal.querySelector('button').focus();
        }, 100);
    }

    handleEscape() {
        // Close any open modals
        const modals = document.querySelectorAll('.modal');
        if (modals.length > 0) {
            const lastModal = modals[modals.length - 1];
            lastModal.style.animation = 'fadeOut 0.2s ease';
            setTimeout(() => {
                if (lastModal.parentElement) {
                    lastModal.remove();
                }
            }, 200);
            return;
        }
        
        // Clear gallery selection
        if (window.gallery && window.gallery.selectedMedia && window.gallery.selectedMedia.size > 0) {
            window.gallery.clearSelection();
            return;
        }
        
        // Close media viewer
        const viewer = document.querySelector('.media-viewer');
        if (viewer) {
            if (typeof closeMediaViewer === 'function') {
                closeMediaViewer();
            } else {
                viewer.remove();
            }
            return;
        }
        
        // Close dropdowns
        const dropdowns = document.querySelectorAll('.dropdown.show');
        dropdowns.forEach(dropdown => {
            dropdown.classList.remove('show');
        });
    }

    setupErrorHandling() {
        // Global error handler
        window.addEventListener('error', (event) => {
            console.error('Global error:', event.error);
            this.showNotification('An error occurred. Please try again.', 'error');
            
            // Log error to analytics if available
            if (window.gtag) {
                gtag('event', 'exception', {
                    'description': event.error.message,
                    'fatal': false
                });
            }
        });
        
        // Unhandled promise rejection
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            this.showNotification('An error occurred. Please try again.', 'error');
        });
        
        // Network status monitoring
        window.addEventListener('online', () => {
            this.showNotification('Back online', 'success');
            this.checkPendingUploads();
        });
        
        window.addEventListener('offline', () => {
            this.showNotification('You are offline. Some features may be unavailable.', 'warning');
        });
        
        // Fetch error handling
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            try {
                const response = await originalFetch(...args);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response;
            } catch (error) {
                console.error('Fetch error:', error);
                throw error;
            }
        };
    }

    checkPendingUploads() {
        // Check if there are pending uploads when coming back online
        if (window.gallery && window.gallery.uploadQueue && window.gallery.uploadQueue.length > 0) {
            this.showNotification('Resuming pending uploads...', 'info');
            // Trigger upload queue processing
            if (typeof window.gallery.processUploadQueue === 'function') {
                window.gallery.processUploadQueue();
            }
        }
    }

    setupMobileFeatures() {
        this.setupTouchGestures();
        this.setupMobileViewport();
        this.setupOrientationHandler();
        this.setupKeyboardAvoidance();
        this.setupPullToRefresh();
        this.setupMobileGestures();
    }

    setupTouchGestures() {
        if (!this.isTouchDevice) return;
        
        // Prevent text selection on long press
        document.addEventListener('contextmenu', (e) => {
            if (e.target.tagName !== 'INPUT' && 
                e.target.tagName !== 'TEXTAREA' &&
                e.target.tagName !== 'SELECT' &&
                !e.target.isContentEditable) {
                e.preventDefault();
                return false;
            }
        }, { passive: false });
        
        // Improve touch scrolling
        document.addEventListener('touchmove', (e) => {
            // Allow touch scrolling
        }, { passive: true });
        
        // Add touch-active class for feedback
        document.addEventListener('touchstart', (e) => {
            if (e.target.tagName === 'BUTTON' || 
                e.target.tagName === 'A' ||
                e.target.closest('button') ||
                e.target.closest('a')) {
                e.target.classList.add('touch-active');
            }
        }, { passive: true });
        
        document.addEventListener('touchend', (e) => {
            document.querySelectorAll('.touch-active').forEach(el => {
                el.classList.remove('touch-active');
            });
        }, { passive: true });
    }

    setupMobileViewport() {
        // Fix viewport height for mobile browsers
        const setVh = () => {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
            document.documentElement.style.setProperty('--window-height', `${window.innerHeight}px`);
            
            // Update CSS custom property for safe areas
            document.documentElement.style.setProperty('--safe-top', 'env(safe-area-inset-top, 0px)');
            document.documentElement.style.setProperty('--safe-bottom', 'env(safe-area-inset-bottom, 0px)');
            document.documentElement.style.setProperty('--safe-left', 'env(safe-area-inset-left, 0px)');
            document.documentElement.style.setProperty('--safe-right', 'env(safe-area-inset-right, 0px)');
        };
        
        setVh();
        
        // Debounced resize handler
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(setVh, 100);
        });
        
        window.addEventListener('orientationchange', () => {
            // Force reflow to fix layout issues
            document.body.classList.add('orientation-changing');
            setTimeout(() => {
                setVh();
                document.body.classList.remove('orientation-changing');
                
                // Show orientation hint
                if (this.isMobile && window.innerWidth > window.innerHeight) {
                    this.showNotification('Landscape mode - best for viewing media', 'info');
                }
            }, 100);
        });
    }

    setupOrientationHandler() {
        let lastOrientation = window.orientation;
        
        window.addEventListener('orientationchange', () => {
            const newOrientation = window.orientation;
            
            // Only trigger on actual change
            if (newOrientation !== lastOrientation) {
                lastOrientation = newOrientation;
                
                // Add visual feedback during orientation change
                document.documentElement.classList.add('orienting');
                setTimeout(() => {
                    document.documentElement.classList.remove('orienting');
                }, 500);
                
                // Force reflow for critical elements
                const reflowElements = [
                    '.gallery-grid',
                    '.modal-content',
                    '.media-viewer',
                    '.settings-container'
                ];
                
                reflowElements.forEach(selector => {
                    const element = document.querySelector(selector);
                    if (element) {
                        element.style.display = 'none';
                        // Trigger reflow
                        void element.offsetHeight;
                        element.style.display = '';
                    }
                });
                
                // Log orientation change
                console.log(`Orientation changed to: ${newOrientation}`);
            }
        });
    }

    setupKeyboardAvoidance() {
        if (!this.isMobile) return;
        
        let activeInput = null;
        
        document.addEventListener('focusin', (e) => {
            if (e.target.matches('input, textarea, select, [contenteditable="true"]')) {
                activeInput = e.target;
                document.body.classList.add('keyboard-visible');
                
                // Scroll input into view with offset for headers
                setTimeout(() => {
                    if (activeInput && activeInput.scrollIntoView) {
                        const inputRect = activeInput.getBoundingClientRect();
                        const offset = 100; // Space for keyboard
                        
                        if (inputRect.bottom > (window.innerHeight - offset)) {
                            window.scrollTo({
                                top: window.scrollY + (inputRect.bottom - window.innerHeight) + offset,
                                behavior: 'smooth'
                            });
                        }
                    }
                }, 300);
            }
        });
        
        document.addEventListener('focusout', () => {
            setTimeout(() => {
                if (document.activeElement.tagName !== 'INPUT' &&
                    document.activeElement.tagName !== 'TEXTAREA' &&
                    document.activeElement.tagName !== 'SELECT' &&
                    !document.activeElement.isContentEditable) {
                    document.body.classList.remove('keyboard-visible');
                    activeInput = null;
                }
            }, 100);
        });
        
        // Handle iOS keyboard dismissal
        if (this.isIOS) {
            document.addEventListener('touchstart', (e) => {
                if (activeInput && !activeInput.contains(e.target)) {
                    activeInput.blur();
                }
            });
        }
    }

    setupPullToRefresh() {
        if (!this.isTouchDevice || this.isStandalone) return;
        
        let startY = 0;
        let currentY = 0;
        let refreshTriggered = false;
        
        document.addEventListener('touchstart', (e) => {
            // Only trigger at top of page
            if (window.scrollY === 0) {
                startY = e.touches[0].pageY;
            }
        }, { passive: true });
        
        document.addEventListener('touchmove', (e) => {
            if (startY === 0) return;
            
            currentY = e.touches[0].pageY;
            const distance = currentY - startY;
            
            // Only trigger pull-to-refresh on downward swipe
            if (distance > 0 && distance < 150) {
                e.preventDefault();
            }
        }, { passive: false });
        
        document.addEventListener('touchend', () => {
            if (startY === 0) return;
            
            const distance = currentY - startY;
            
            if (distance > 100 && !refreshTriggered) {
                refreshTriggered = true;
                this.triggerPullToRefresh();
            }
            
            startY = 0;
            currentY = 0;
            setTimeout(() => refreshTriggered = false, 1000);
        });
    }

    triggerPullToRefresh() {
        // Show refresh indicator
        this.showNotification('Refreshing...', 'info');
        
        // Reload gallery if on gallery page
        if (window.location.pathname.includes('/gallery') && window.gallery) {
            if (typeof window.gallery.loadGallery === 'function') {
                window.gallery.loadGallery();
            }
        }
        
        // Force service worker update check
        if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({ type: 'CHECK_UPDATES' });
        }
    }

    setupMobileGestures() {
        if (!this.isTouchDevice) return;
        
        // Handle swipe to close for modals
        document.addEventListener('touchstart', (e) => {
            const modal = e.target.closest('.modal-content');
            if (modal) {
                const modalContainer = modal.closest('.modal');
                if (modalContainer) {
                    modalContainer.dataset.startX = e.touches[0].clientX;
                    modalContainer.dataset.startY = e.touches[0].clientY;
                }
            }
        }, { passive: true });
        
        document.addEventListener('touchmove', (e) => {
            const modal = e.target.closest('.modal-content');
            if (modal) {
                const modalContainer = modal.closest('.modal');
                if (modalContainer && modalContainer.dataset.startX) {
                    const startX = parseInt(modalContainer.dataset.startX);
                    const currentX = e.touches[0].clientX;
                    const diffX = currentX - startX;
                    
                    // Only allow horizontal swipe
                    if (Math.abs(diffX) > 10) {
                        modal.style.transform = `translateX(${diffX}px)`;
                        modal.style.opacity = `${1 - Math.abs(diffX) / 300}`;
                    }
                }
            }
        }, { passive: true });
        
        document.addEventListener('touchend', (e) => {
            const modal = e.target.closest('.modal-content');
            if (modal) {
                const modalContainer = modal.closest('.modal');
                if (modalContainer && modalContainer.dataset.startX) {
                    const startX = parseInt(modalContainer.dataset.startX);
                    const endX = e.changedTouches[0].clientX;
                    const diffX = endX - startX;
                    
                    // Reset or close modal based on swipe distance
                    if (Math.abs(diffX) > 100) {
                        modalContainer.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
                        modal.style.transform = `translateX(${diffX > 0 ? '100%' : '-100%'})`;
                        modal.style.opacity = '0';
                        
                        setTimeout(() => {
                            if (modalContainer.parentElement) {
                                modalContainer.remove();
                            }
                        }, 300);
                    } else {
                        modal.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
                        modal.style.transform = 'translateX(0)';
                        modal.style.opacity = '1';
                        
                        setTimeout(() => {
                            modal.style.transition = '';
                        }, 200);
                    }
                    
                    delete modalContainer.dataset.startX;
                    delete modalContainer.dataset.startY;
                }
            }
        }, { passive: true });
    }

    setupMobileInstall() {
        // Show iOS install instructions
        if (this.isIOS && !this.isStandalone) {
            // Check if we've shown this recently
            const lastShown = localStorage.getItem('ios_install_shown');
            const oneWeekAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
            
            if (!lastShown || parseInt(lastShown) < oneWeekAgo) {
                setTimeout(() => {
                    this.showNotification(
                        'Install VantaVault: Tap <span style="font-size: 1.2em;">↗️</span> then "Add to Home Screen"',
                        'info',
                        8000
                    );
                    localStorage.setItem('ios_install_shown', Date.now().toString());
                }, 5000);
            }
        }
        
        // Android Chrome install prompt
        if (this.isAndroid && !this.isStandalone && 'beforeinstallprompt' in window) {
            // Already handled by setupInstallPrompt
        }
    }

    setupPerformanceMonitoring() {
        // Monitor page load performance
        if ('performance' in window) {
            window.addEventListener('load', () => {
                const perfData = performance.getEntriesByType('navigation')[0];
                if (perfData) {
                    console.log('Page load performance:', {
                        dns: perfData.domainLookupEnd - perfData.domainLookupStart,
                        tcp: perfData.connectEnd - perfData.connectStart,
                        request: perfData.responseEnd - perfData.requestStart,
                        domContentLoaded: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
                        load: perfData.loadEventEnd - perfData.loadEventStart
                    });
                    
                    // Log to analytics
                    if (window.gtag && perfData.loadEventEnd) {
                        gtag('event', 'timing_complete', {
                            'name': 'page_load',
                            'value': Math.round(perfData.loadEventEnd),
                            'event_category': 'Performance'
                        });
                    }
                }
            });
        }
        
        // Monitor memory usage (if supported)
        if ('memory' in performance) {
            setInterval(() => {
                const memory = performance.memory;
                console.log('Memory usage:', {
                    used: Math.round(memory.usedJSHeapSize / 1048576) + 'MB',
                    total: Math.round(memory.totalJSHeapSize / 1048576) + 'MB',
                    limit: Math.round(memory.jsHeapSizeLimit / 1048576) + 'MB'
                });
                
                // Warn if memory usage is high
                if (memory.usedJSHeapSize > memory.jsHeapSizeLimit * 0.8) {
                    console.warn('High memory usage detected');
                    this.showNotification('High memory usage. Consider closing unused tabs.', 'warning');
                }
            }, 30000);
        }
        
        // Monitor FPS
        let lastTime = performance.now();
        let frames = 0;
        
        const measureFPS = () => {
            const currentTime = performance.now();
            frames++;
            
            if (currentTime > lastTime + 1000) {
                const fps = Math.round((frames * 1000) / (currentTime - lastTime));
                lastTime = currentTime;
                frames = 0;
                
                // Log low FPS
                if (fps < 30) {
                    console.warn(`Low FPS: ${fps}`);
                }
            }
            
            requestAnimationFrame(measureFPS);
        };
        
        requestAnimationFrame(measureFPS);
    }

    showNotification(message, type = 'info', duration = 3000) {
        // Create notification container if it doesn't exist
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: calc(20px + env(safe-area-inset-top, 0px));
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                max-width: min(350px, calc(100vw - 40px));
                pointer-events: none;
            `;
            document.body.appendChild(container);
        }
        
        // Create notification
        const notification = document.createElement('div');
        notification.className = `app-notification ${type}`;
        notification.setAttribute('role', 'alert');
        notification.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">
                    ${type === 'success' ? '✅' : 
                      type === 'error' ? '❌' : 
                      type === 'warning' ? '⚠️' : 'ℹ️'}
                </span>
                <span class="notification-message">${message}</span>
            </div>
            <button class="notification-close" onclick="this.parentElement.remove()" aria-label="Close notification">
                ×
            </button>
        `;
        
        // Add haptic feedback for mobile
        if (this.isTouchDevice && navigator.vibrate) {
            switch(type) {
                case 'success':
                    navigator.vibrate(50);
                    break;
                case 'error':
                    navigator.vibrate([100, 50, 100]);
                    break;
                case 'warning':
                    navigator.vibrate(100);
                    break;
            }
        }
        
        container.appendChild(notification);
        
        // Auto-remove after delay
        setTimeout(() => {
            if (notification.parentElement) {
                notification.style.opacity = '0';
                notification.style.transform = 'translateX(100%)';
                notification.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                    }
                }, 300);
            }
        }, duration);
        
        return notification;
    }

    // Utility functions
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    formatDate(date) {
        const now = new Date();
        const diffMs = now - new Date(date);
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return new Date(date).toLocaleDateString();
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text)
            .then(() => this.showNotification('Copied to clipboard', 'success'))
            .catch(() => {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.opacity = '0';
                document.body.appendChild(textArea);
                textArea.select();
                
                try {
                    document.execCommand('copy');
                    this.showNotification('Copied to clipboard', 'success');
                } catch (err) {
                    this.showNotification('Failed to copy', 'error');
                }
                
                document.body.removeChild(textArea);
            });
    }

    // Offline detection
    checkConnection() {
        return navigator.onLine;
    }

    // Battery status (for power-saving features)
    async getBatteryStatus() {
        if ('getBattery' in navigator) {
            try {
                const battery = await navigator.getBattery();
                return {
                    level: battery.level,
                    charging: battery.charging,
                    chargingTime: battery.chargingTime,
                    dischargingTime: battery.dischargingTime
                };
            } catch {
                return null;
            }
        }
        return null;
    }

    // Storage quota
    async getStorageQuota() {
        if ('storage' in navigator && 'estimate' in navigator.storage) {
            try {
                const estimate = await navigator.storage.estimate();
                return {
                    usage: estimate.usage,
                    quota: estimate.quota,
                    percent: estimate.usage && estimate.quota ? 
                        (estimate.usage / estimate.quota * 100).toFixed(1) : 0
                };
            } catch {
                return null;
            }
        }
        return null;
    }

    // Check network status
    checkNetworkStatus() {
        if (!navigator.onLine) {
            this.showNotification('You are offline. Some features may be unavailable.', 'warning');
            return false;
        }
        
        // Check connection speed
        if ('connection' in navigator) {
            const connection = navigator.connection;
            if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
                this.showNotification('Slow connection detected. Uploads may be slower.', 'info');
            }
        }
        
        return true;
    }

    // Save data to local storage with compression
    saveData(key, data) {
        try {
            const compressed = JSON.stringify(data);
            localStorage.setItem(key, compressed);
            return true;
        } catch (error) {
            console.error('Failed to save data:', error);
            return false;
        }
    }

    // Load data from local storage
    loadData(key) {
        try {
            const data = localStorage.getItem(key);
            return data ? JSON.parse(data) : null;
        } catch (error) {
            console.error('Failed to load data:', error);
            return null;
        }
    }

    // Clear expired data
    clearExpiredData() {
        const now = Date.now();
        const keys = Object.keys(localStorage);
        
        keys.forEach(key => {
            if (key.startsWith('cache_')) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    if (data && data.expires && data.expires < now) {
                        localStorage.removeItem(key);
                    }
                } catch {
                    // Ignore invalid JSON
                }
            }
        });
    }

    // Debounce function for performance
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Throttle function for performance
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.vantaVault = new VantaVaultApp();
    
    // Add global error boundary
    window.addEventListener('unhandledrejection', (event) => {
        console.error('Unhandled promise rejection:', event.reason);
        if (window.vantaVault) {
            window.vantaVault.showNotification('An error occurred. Please try again.', 'error');
        }
    });
    
    // Prevent zoom on double-tap (mobile)
    let lastTouchEnd = 0;
    document.addEventListener('touchend', function(event) {
        const now = Date.now();
        if (now - lastTouchEnd <= 300) {
            event.preventDefault();
        }
        lastTouchEnd = now;
    }, { passive: false });
    
    // Handle back button on mobile
    if (window.history && window.history.pushState) {
        history.pushState(null, null, location.href);
        window.onpopstate = function() {
            history.go(1);
        };
    }
    
    // Add CSS for mobile optimizations
    const mobileStyles = document.createElement('style');
    mobileStyles.textContent = `
        /* Mobile notification styles */
        .app-notification {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius);
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            animation: slideInRight 0.3s ease;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            pointer-events: auto;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }
        
        .app-notification.success {
            border-color: rgba(0, 255, 0, 0.3);
            background: rgba(0, 255, 0, 0.1);
        }
        
        .app-notification.error {
            border-color: rgba(255, 51, 51, 0.3);
            background: rgba(255, 51, 51, 0.1);
        }
        
        .app-notification.warning {
            border-color: rgba(255, 165, 0, 0.3);
            background: rgba(255, 165, 0, 0.1);
        }
        
        .notification-content {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex: 1;
        }
        
        .notification-icon {
            font-size: 1.2rem;
            flex-shrink: 0;
        }
        
        .notification-message {
            color: var(--text-primary);
            flex: 1;
            font-size: 0.9rem;
            line-height: 1.4;
        }
        
        .notification-close {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 1.5rem;
            cursor: pointer;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: background 0.3s ease;
            flex-shrink: 0;
            padding: 0;
        }
        
        .notification-close:hover,
        .notification-close:focus {
            background: rgba(255, 255, 255, 0.1);
        }
        
        @keyframes slideInRight {
            from {
                opacity: 0;
                transform: translateX(100%);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        @keyframes slideOutRight {
            from {
                opacity: 1;
                transform: translateX(0);
            }
            to {
                opacity: 0;
                transform: translateX(100%);
            }
        }
        
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
        
        /* Mobile device classes */
        .touch-device button,
        .touch-device .btn,
        .touch-device .folder-btn,
        .touch-device .settings-nav-btn {
            min-height: 44px;
            min-width: 44px;
        }
        
        .touch-device input[type="text"],
        .touch-device input[type="password"],
        .touch-device input[type="email"],
        .touch-device textarea,
        .touch-device select {
            font-size: 16px !important;
        }
        
        .touch-active {
            opacity: 0.7;
            transform: scale(0.98);
        }
        
        /* Orientation change handling */
        .orienting * {
            transition: none !important;
        }
        
        /* Keyboard visible state */
        .keyboard-visible .app-container {
            padding-bottom: 300px; /* Space for keyboard */
        }
        
        /* Safe area support */
        .safe-area-top {
            padding-top: env(safe-area-inset-top);
        }
        
        .safe-area-bottom {
            padding-bottom: env(safe-area-inset-bottom);
        }
        
        /* Mobile scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 3px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        /* Hide scrollbar on mobile when not scrolling */
        .hide-scrollbar {
            -ms-overflow-style: none;
            scrollbar-width: none;
        }
        
        .hide-scrollbar::-webkit-scrollbar {
            display: none;
        }
        
        /* Install button mobile styles */
        @media (max-width: 768px) {
            #installBtn .install-text {
                display: none;
            }
            
            #installBtn {
                padding: 0.75rem;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                justify-content: center;
            }
            
            #installBtn svg {
                margin: 0;
            }
        }
        
        /* Help modal mobile styles */
        @media (max-width: 600px) {
            .help-section {
                margin: 1rem 0;
            }
            
            .shortcut-item {
                flex-direction: column;
                align-items: flex-start;
                gap: 0.5rem;
            }
            
            .shortcut-item kbd {
                width: 100%;
                text-align: left;
                padding: 0.5rem;
            }
        }
    `;
    document.head.appendChild(mobileStyles);
});

// PWA installation tracking
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready.then(registration => {
        // Send installation status to service worker
        registration.active.postMessage({
            type: 'APP_INFO',
            isPWA: window.matchMedia('(display-mode: standalone)').matches,
            isMobile: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
        });
    });
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { VantaVaultApp };
}

// Make app globally available
if (typeof window !== 'undefined') {
    window.VantaVaultApp = VantaVaultApp;
}