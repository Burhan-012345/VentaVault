/**
 * VantaVault - Authentication Module
 * Handles PIN and fingerprint authentication
 */

class PinLock {
    constructor() {
        this.pin = '';
        this.maxLength = 6;
        this.isSubmitting = false;
        this.allowFakeVault = false;
    }

    init() {
        this.setupEventListeners();
        this.updatePinDisplay();
        
        // Check if fingerprint is enabled
        this.checkFingerprintEnabled();
        
        // Auto-show fingerprint prompt if enabled
        setTimeout(() => {
            if (localStorage.getItem('fingerprintEnabled') === 'true') {
                this.attemptFingerprint();
            }
        }, 500);
    }

    setupEventListeners() {
        // Numeric keypad buttons
        document.querySelectorAll('.keypad-btn[data-key]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                if (this.isSubmitting) return;
                const key = e.target.dataset.key;
                this.addDigit(key);
            });
        });

        // Clear button
        document.getElementById('clearBtn').addEventListener('click', () => {
            this.clearPin();
        });

        // Submit button
        document.getElementById('submitBtn').addEventListener('click', () => {
            this.submitPin();
        });

        // Keyboard support
        document.addEventListener('keydown', (e) => {
            if (this.isSubmitting) return;

            if (e.key >= '0' && e.key <= '9') {
                this.addDigit(e.key);
            } else if (e.key === 'Backspace') {
                this.clearPin();
            } else if (e.key === 'Enter') {
                this.submitPin();
            }
        });

        // Visibility change (app minimization)
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                // Optional: Clear PIN when app comes back to foreground
                // this.clearPin();
            }
        });
    }

    addDigit(digit) {
        if (this.pin.length >= this.maxLength) return;
        
        this.pin += digit;
        this.updatePinDisplay();
        
        // Auto-submit when PIN length is reached
        if (this.pin.length === this.maxLength) {
            setTimeout(() => this.submitPin(), 300);
        }
        
        // Visual feedback
        const dots = document.querySelectorAll('.pin-dot');
        dots[this.pin.length - 1].classList.add('filled');
        
        // Play subtle sound or haptic feedback
        this.playFeedback();
    }

    clearPin() {
        if (this.pin.length === 0) return;
        
        this.pin = '';
        this.updatePinDisplay();
        
        // Clear dots
        document.querySelectorAll('.pin-dot').forEach(dot => {
            dot.classList.remove('filled');
        });
    }

    updatePinDisplay() {
        const display = document.getElementById('pinValue');
        display.textContent = '•'.repeat(this.pin.length);
    }

    async submitPin() {
        if (this.isSubmitting || this.pin.length < 4) return;
        
        this.isSubmitting = true;
        
        // Disable keypad
        document.querySelectorAll('.keypad-btn').forEach(btn => {
            btn.disabled = true;
        });
        
        // Visual feedback
        document.querySelectorAll('.pin-dot').forEach(dot => {
            dot.style.animation = 'pulse 0.5s ease-in-out';
        });
        
        try {
            const response = await fetch('/pin/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    pin: this.pin,
                    fake_vault: this.allowFakeVault
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Store last unlock time
                localStorage.setItem('lastUnlock', new Date().toISOString());
                
                if (data.vault_type === 'real') {
                    // Redirect to unlock animation
                    window.location.href = `/unlock/animation?token=${data.animation_token}`;
                } else {
                    // Redirect to fake vault
                    window.location.href = '/dashboard';
                }
            } else {
                // Failed attempt
                this.handleFailedAttempt();
            }
            
        } catch (error) {
            console.error('Authentication error:', error);
            this.handleFailedAttempt();
        } finally {
            this.isSubmitting = false;
            this.clearPin();
            
            // Re-enable keypad
            document.querySelectorAll('.keypad-btn').forEach(btn => {
                btn.disabled = false;
            });
            
            // Reset animations
            document.querySelectorAll('.pin-dot').forEach(dot => {
                dot.style.animation = '';
            });
        }
    }

    handleFailedAttempt() {
        // Shake animation
        const container = document.querySelector('.pin-lock-container');
        container.classList.add('shake');
        
        // Red glow
        document.querySelectorAll('.pin-dot').forEach(dot => {
            dot.style.borderColor = 'var(--color-danger)';
        });
        
        // Clear PIN after delay
        setTimeout(() => {
            container.classList.remove('shake');
            document.querySelectorAll('.pin-dot').forEach(dot => {
                dot.style.borderColor = '';
                dot.classList.remove('filled');
            });
            this.clearPin();
        }, 1000);
        
        // Log attempt (client-side)
        this.logFailedAttempt();
    }

    logFailedAttempt() {
        const attempts = parseInt(localStorage.getItem('failedAttempts') || '0') + 1;
        localStorage.setItem('failedAttempts', attempts.toString());
        localStorage.setItem('lastFailedAttempt', new Date().toISOString());
        
        // If too many attempts, show warning
        if (attempts >= 5) {
            this.showSecurityWarning();
        }
    }

    showSecurityWarning() {
        const warning = document.createElement('div');
        warning.className = 'security-warning';
        warning.innerHTML = `
            <div class="warning-content">
                <h3>⚠️ Security Alert</h3>
                <p>Multiple failed attempts detected. Please wait 30 seconds.</p>
                <div class="countdown">30</div>
            </div>
        `;
        
        document.querySelector('.pin-lock-container').appendChild(warning);
        
        // Countdown
        let countdown = 30;
        const countdownEl = warning.querySelector('.countdown');
        const interval = setInterval(() => {
            countdown--;
            countdownEl.textContent = countdown;
            
            if (countdown <= 0) {
                clearInterval(interval);
                warning.remove();
                localStorage.setItem('failedAttempts', '0');
            }
        }, 1000);
    }

    async attemptFingerprint() {
        try {
            // Check if WebAuthn is supported
            if (!window.PublicKeyCredential) {
                throw new Error('Fingerprint authentication not supported');
            }
            
            // Get authentication options from server
            const response = await fetch('/fingerprint/authenticate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: 'default_user' // In production, use actual user ID
                })
            });
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Fingerprint authentication failed');
            }
            
            // Convert options for WebAuthn API
            const publicKey = {
                ...data.options.publicKey,
                challenge: Uint8Array.from(atob(data.options.publicKey.challenge), c => c.charCodeAt(0)),
                allowCredentials: data.options.publicKey.allowCredentials.map(cred => ({
                    ...cred,
                    id: Uint8Array.from(atob(cred.id), c => c.charCodeAt(0))
                }))
            };
            
            // Request authentication
            const credential = await navigator.credentials.get({ publicKey });
            
            // Send response to server for verification
            const verificationResponse = await fetch('/fingerprint/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    id: credential.id,
                    rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
                    response: {
                        authenticatorData: btoa(String.fromCharCode(...new Uint8Array(credential.response.authenticatorData))),
                        clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
                        signature: btoa(String.fromCharCode(...new Uint8Array(credential.response.signature))),
                        userHandle: credential.response.userHandle ? 
                            btoa(String.fromCharCode(...new Uint8Array(credential.response.userHandle))) : null
                    },
                    type: credential.type
                })
            });
            
            const verificationData = await verificationResponse.json();
            
            if (verificationData.success) {
                // Store last unlock time
                localStorage.setItem('lastUnlock', new Date().toISOString());
                
                // Redirect to unlock animation
                window.location.href = `/unlock/animation?token=${verificationData.animation_token}`;
            } else {
                throw new Error('Verification failed');
            }
            
        } catch (error) {
            console.error('Fingerprint authentication error:', error);
            
            // Fall back to PIN
            document.getElementById('fingerprintPrompt').style.display = 'none';
            
            // Show message
            const message = document.createElement('div');
            message.className = 'fingerprint-fallback';
            message.textContent = 'Fingerprint failed. Please use PIN.';
            message.style.color = 'var(--color-warning)';
            message.style.marginTop = '1rem';
            message.style.textAlign = 'center';
            
            const container = document.querySelector('.pin-lock-container');
            container.appendChild(message);
            
            setTimeout(() => message.remove(), 3000);
        }
    }

    checkFingerprintEnabled() {
        // Check if fingerprint is enabled in settings
        fetch('/api/settings')
            .then(response => response.json())
            .then(settings => {
                if (settings.fingerprint_enabled) {
                    localStorage.setItem('fingerprintEnabled', 'true');
                    document.getElementById('fingerprintPrompt').style.display = 'block';
                }
            })
            .catch(() => {
                // Silently fail
            });
    }

    playFeedback() {
        // Haptic feedback (if available)
        if (navigator.vibrate) {
            navigator.vibrate(10);
        }
        
        // Audio feedback (optional)
        // const audio = new Audio('data:audio/wav;base64,xxx');
        // audio.volume = 0.1;
        // audio.play().catch(() => {});
    }
}

// Global function for HTML onclick
window.attemptFingerprint = () => {
    const pinLock = new PinLock();
    pinLock.attemptFingerprint();
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.pinLock = new PinLock();
    window.pinLock.init();
});